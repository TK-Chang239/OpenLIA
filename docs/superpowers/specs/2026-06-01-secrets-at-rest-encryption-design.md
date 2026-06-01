# Connector secrets-at-rest encryption — design

Date: 2026-06-01
Status: Approved (brainstorming), pending implementation plan
Scope owner: connector subsystem (server persistence layer)

## Problem

Connector API keys / credentials live in the `connectors.secrets` JSON column in
**plaintext**. Anyone with read access to the database file (or a backup) reads every
provider key directly. PR #230 corrected the add-connector UI, which previously claimed
secrets were "Stored encrypted on the server" — the wording now truthfully says "Stored
on the server, never sent to the LLM". This effort makes the encryption claim real.

## Goals

1. Encrypt the `connectors.secrets` column at rest with an authenticated symmetric cipher.
2. Require **zero changes** at the many existing read/write call sites — they keep seeing a
   plaintext `dict[str, str]`.
3. Key from an operator-supplied `OPENLIA_SECRET_KEY`; personal mode auto-provisions a key
   file; company mode requires the env var. Fail loudly when a key is missing while
   encrypted rows exist.
4. Migrate all existing plaintext rows so "encrypted at rest" holds the moment the upgrade
   is deployed.
5. Restore the truthful "encrypted" wording in the UI.

## Non-goals

- Encrypting any column other than `connectors.secrets`.
- Key rotation tooling / re-encryption-with-new-key workflows (a wrong/changed key fails
  loudly; rotation is future work).
- Per-value or field-level encryption — the whole `secrets` dict is encrypted as one blob.
- Hardware KMS / cloud secret managers / OS keyring integration.
- Changes to `packages/core` — it stays free of crypto and key handling.

## Decisions (locked during brainstorming)

- **Approach:** transparent column encryption via a SQLAlchemy `TypeDecorator`
  (`EncryptedJSON`), mirroring the existing `UTCDateTime` decorator in `db/base.py`. The
  alternative — explicit `encrypt()`/`decrypt()` calls at each call site — touches more
  code and risks missing a path. The decorator confines the change to one column swap.
- **Cipher:** Fernet (from `cryptography`, already a server dependency `>=42.0`).
- **Key source:** `OPENLIA_SECRET_KEY` env var when set. Else, personal mode
  (`OPENLIA_MODE != company`) reads or auto-generates a key file at
  `openlia_home() / "secret.key"` (`chmod 600`). Else (company, unset) → raise.
- **Key format:** strict — must be a valid Fernet key (urlsafe-base64, 32 bytes). On
  missing/invalid, raise with the exact generation command. No passphrase derivation.
- **Migration:** eager Alembic data migration encrypts every existing row; the read path
  also tolerates legacy plaintext as a safety net.

## Architecture

### 1. `packages/server/src/openlia_server/db/secrets_crypto.py` (new)

Isolated, testable key management + cipher. No SQLAlchemy imports.

- `resolve_key() -> bytes`:
  - If `OPENLIA_SECRET_KEY` is set, return it (encoded).
  - Else if `os.getenv("OPENLIA_MODE", "personal").lower() != "company"`: read
    `openlia_home() / "secret.key"`; if absent, generate via `Fernet.generate_key()`,
    write it `chmod 600`, return it.
  - Else raise `SecretKeyMissingError` with a message instructing the operator to set
    `OPENLIA_SECRET_KEY` and how to generate one.
  - Validate the resolved key is a usable Fernet key; on failure raise
    `SecretKeyInvalidError` with the generation command.
- `get_fernet() -> Fernet`: cached singleton built from `resolve_key()`.
- `encrypt(plaintext: str) -> str` / `decrypt(token: str) -> str`. `decrypt` raises
  `SecretDecryptError` ("secret decryption failed; OPENLIA_SECRET_KEY may have changed or
  the data is corrupt") on `InvalidToken`.
- A test seam to reset the cached Fernet (so tests can swap keys / data dirs).

### 2. `EncryptedJSON(TypeDecorator)` in `db/base.py`

Next to `UTCDateTime`. `impl = Text`, `cache_ok = True`.

- `process_bind_param(value: dict | None, dialect) -> str | None`: `None` → `None`;
  otherwise `encrypt(json.dumps(value))`.
- `process_result_value(value: str | None, dialect) -> dict`: `None`/empty → `{}`; try
  `json.loads(decrypt(value))`; on `SecretDecryptError`, if the raw value parses as JSON
  (legacy plaintext, pre-migration / out-of-band insert) return that dict, otherwise
  re-raise.

### 3. `Connector.secrets` column

Change the type from `JSON` to `EncryptedJSON` in `db/models/connectors.py`. Nothing else
in the model changes; the Python-side value stays `dict[str, str]`, so
`connectors_service`, `dispatcher_factory._prepare_connector`, `_validate_launch`,
`eu_v2_wiring.resolve_eodhd_api_key`, and the `secret_keys` listing in
`routes/connectors.py` are all untouched.

### 4. Alembic migration

New revision under `db/migrations/versions/`:
- Upgrade: ensure the column is `Text` (SQLite is dynamically typed; use batch alter if the
  dialect needs it), then iterate every `connectors` row, read the raw stored value, and if
  it is plaintext JSON, rewrite it as a Fernet token using `secrets_crypto.encrypt`. Rows
  already encrypted (idempotent re-run) are detected and skipped.
- Downgrade: decrypt each row back to plaintext JSON and (if applicable) restore the JSON
  column type.
- The migration imports `secrets_crypto`, so `resolve_key()` must succeed when it runs
  (company deployments must have `OPENLIA_SECRET_KEY` set before `alembic upgrade`).

### 5. Startup key check

In the app factory / bootstrap: when `OPENLIA_MODE == company`, eagerly call
`resolve_key()` at startup so a misconfigured server fails immediately with a clear message
rather than at first connector access. Personal mode auto-provisions, so no eager check is
required there (but auto-provisioning at startup is acceptable).

### 6. UI wording

Revert the two help texts to state encryption truthfully:
- `frontend/src/setup/steps/SmartPasteMcpForm.tsx` — the "Detected secrets" hint.
- `frontend/src/setup/steps/AddConnectorForm.tsx` — the API keys / secrets fieldset hint.
Wording: "Stored encrypted on the server, never sent to the LLM."

## Data flow

write: service sets `row.secrets = {"KEY": "value"}`
  -> EncryptedJSON.process_bind_param -> json.dumps -> Fernet.encrypt -> Text token at rest

read: ORM loads row
  -> EncryptedJSON.process_result_value -> Fernet.decrypt -> json.loads -> dict
  -> `_build_transport` substitutes `{NAME}` from the dict; `secret_keys` lists `.keys()`

## Error handling

- Company mode, no key at startup -> `SecretKeyMissingError`, server refuses to start.
- Invalid key value -> `SecretKeyInvalidError` with the `Fernet.generate_key()` command.
- Wrong/rotated key against existing ciphertext -> `SecretDecryptError` on read (not silent
  corruption).
- Legacy plaintext row encountered post-deploy (e.g. inserted out-of-band) -> tolerated on
  read; re-encrypted on next write.

## Testing

- `secrets_crypto`: encrypt/decrypt round-trip; key from `OPENLIA_SECRET_KEY`; personal
  auto-gen into a temp `openlia_home` (file created, `0600`); company + unset key raises;
  invalid key raises with a helpful message; `decrypt` of a wrong-key token raises
  `SecretDecryptError`.
- `EncryptedJSON`: bound DB value is a Fernet token and does NOT contain the plaintext
  substring; result decrypts to the original dict; `None` -> `{}`; legacy-plaintext JSON
  tolerated on read.
- Migration: seed a plaintext `connectors` row, run the upgrade, assert the raw stored
  value is a token and the ORM-read value round-trips; downgrade restores plaintext.
- Integration: `create_connector` persists ciphertext (assert via a raw SQL read);
  `dispatcher_factory` build and `eu_v2_wiring.resolve_eodhd_api_key` read the decrypted
  value; `GET /connectors/{id}` still returns the correct `secret_keys`.

## Open questions

- Exact key-file name (`secret.key`) and whether to also honor an explicit
  `OPENLIA_SECRET_KEY_FILE` override — default to `openlia_home()/secret.key`; settle any
  override in the plan.
- Whether the Alembic data migration runs in the same process that has the key, for all
  supported deploy flows (documented assumption: key available at `alembic upgrade` time).
