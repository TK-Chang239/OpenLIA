# Composer Attachments Design

## Purpose

Specifies how files attached in chat composers (Secretary, Equity Research) reach the LLM. Today the composer renders chips for attached files but the contents never leave the browser — `ChatRunner.run()` exposes a dead `attachments` parameter, and no upload pipeline, materialization layer, or provider routing exists. Filed as issue #97 (verification audit) and #98 (the bug).

This spec defines the upload, persistence, materialization, and lifecycle for composer attachments end-to-end. It is consumed by `llm-runtime-design.md` (which currently declares vision/image inputs out of scope) and supersedes that exclusion.

## Scope

In scope:

- Single multipart submit per message (atomic-at-send), Secretary and Equity Research routes only.
- Local-filesystem storage backend under `OPENLIA_ATTACHMENTS_DIR` (default `${data_dir}/attachments`).
- File scope: text (`.txt`/`.md`/`.csv`/`.json`/`.log` and source code), images (`.png`/`.jpg`/`.webp`/`.gif`), PDFs, Office (`.docx`/`.xlsx`/`.pptx`).
- Capability-routed materialization: provider-native blocks where supported, server-side text extraction otherwise, strict reject when neither path exists (image + non-vision model).
- Truncation policy that adapts to the selected model's context window.
- Lifecycle: synchronous `after_commit` unlink + hourly janitor for stragglers.

Out of scope:

- Other departments (Earnings Update, Morning Briefing, Macro Research, Retail Sentiment, Panic Thermometer) are not chat-style and do not gain attachments.
- S3-compatible / pluggable storage backends. Local filesystem only.
- OCR for images. An image attached to a non-vision model is rejected, not OCR'd.
- Reuse of an attachment across multiple messages. Each multipart submit creates new rows.
- Background extraction. Extraction is synchronous within the upload request.

---

## Locked Decisions

| # | Decision | Choice |
|---|---|---|
| Q1 | Upload model | Atomic-at-send: single multipart request creates message + attachments + opens SSE stream |
| Q2 | File scope | Text + images + PDFs + Office docs |
| Q3 | Storage | Local filesystem under `OPENLIA_ATTACHMENTS_DIR`, sharded by UUID prefix, server-generated names |
| Q4 | Capability mismatch | Strict reject only when irreducible (image + non-vision model). Server-side extraction is canonical for non-native formats, not a fallback |
| Q5 | Materialization | Runtime owns extraction. Builds neutral `TextBlock`/`ImageBlock`/`DocumentBlock` vocabulary; provider adapters translate to API-specific shapes |
| Q6 | Department scope | Secretary + Equity Research |
| Q7 | Token budget | Model-aware truncation. Per-attachment hard ceiling 500k tokens. Multi-attachment proportional split. Banner-in-text + UI warning chip when truncated |
| Q8 | Lifecycle | `after_commit` SQLAlchemy hook unlinks file on row delete. Hourly janitor sweeps orphans > 1h. CASCADE chain: user → session → message → attachment → file |
| Q9 | Caching | Cache extracted text on `chat_attachments.extracted_text` at upload |
| - | Per-file cap | 25 MB |
| - | Per-message file count | 10 |
| - | Mime policy | Strict allowlist, both client-side (UX) and server-side (security) |
| - | Validation failure | JSON 4xx with per-file errors before SSE opens. All-or-nothing |
| - | Upload UX | Per-file determinate progress bar → "processing..." → SSE stream. Send disabled throughout |

---

## Architecture

```
┌─────────────────────────┐
│ Composer (React)        │  ChatInput (Secretary), ErComposer (ER)
│ - client validation     │  size, count, mime allowlist
│ - FormData multipart    │
│ - per-file progress     │
└──────────┬──────────────┘
           │ POST multipart/form-data
           │   text=...
           │   session_id=...
           │   files[]=...
           ▼
┌─────────────────────────┐
│ Department route        │  /api/departments/{secretary|equity-research}/chat
│ - parse multipart       │
│ - persist ChatMessage   │
│ - persist_attachments   │  → 4xx JSON on validation failure (SSE never opens)
│ - call runner           │
│ - SSE response          │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Attachment service      │  packages/server/.../services/attachments.py
│ - validate(size,count,  │
│   mime)                 │
│ - storage.save(bytes)   │
│ - materializer.extract  │  text extraction at upload time
│ - persist row           │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Storage backend         │  packages/server/.../services/attachment_storage.py
│ - filesystem under      │
│   OPENLIA_ATTACHMENTS_  │
│   DIR                   │
│ - sharded UUID names    │
└─────────────────────────┘

ChatRunner.run(messages, attachments=...)
           │
           ▼
┌─────────────────────────┐
│ Materializer            │  packages/core/.../llm/runtime/attachments.py
│ - per-attachment        │
│   classify by mime +    │
│   model capabilities    │
│ - build neutral blocks  │
│ - apply truncation      │
│ - emit warnings         │
└──────────┬──────────────┘
           │
           ▼ list[ContentBlock]
┌─────────────────────────┐
│ Provider adapter        │  anthropic, openai, gemini, ollama, openrouter, openai_compat
│ render_content_blocks() │
│ → provider-native       │
│   message content       │
└─────────────────────────┘
```

---

## Interfaces

### Storage backend

```python
# packages/server/src/openlia_server/services/attachment_storage.py

def save(content: bytes, *, original_filename: str) -> str:
    """Write bytes to the configured storage root.
    Returns the absolute storage_path. Server generates the on-disk name
    (UUID + preserved extension); original_filename is metadata only."""

def read(storage_path: str) -> bytes:
    """Read bytes back. Raises FileNotFoundError if storage_path is gone."""

def unlink(storage_path: str) -> None:
    """Remove the file. Idempotent; no error if already missing."""

def configured_root() -> Path:
    """Returns the resolved root directory. Used by janitor."""
```

### Attachment dataclass (replaces existing speculative shape)

```python
# packages/core/src/openlia/llm/runtime/messages.py

@dataclass(frozen=True)
class Attachment:
    id: str
    filename: str
    mime_type: str
    storage_path: str
    size_bytes: int
```

The current `Attachment(kind, url, mime_type)` has zero call sites and is documented as "reserved for vision inputs. v1 runners accept but never forward them." Replacing it is safe.

### Neutral content blocks

```python
# packages/core/src/openlia/llm/runtime/messages.py

@dataclass(frozen=True)
class TextBlock:
    text: str
    source_filename: str | None = None  # populated when from an attachment, used in banners

@dataclass(frozen=True)
class ImageBlock:
    bytes: bytes
    mime_type: str
    source_filename: str

@dataclass(frozen=True)
class DocumentBlock:
    bytes: bytes
    mime_type: str
    source_filename: str

ContentBlock = TextBlock | ImageBlock | DocumentBlock
```

### Materializer

```python
# packages/core/src/openlia/llm/runtime/attachments.py

@dataclass(frozen=True)
class MaterializationResult:
    blocks: list[ContentBlock]
    warnings: list[str]   # surfaced in SSE stream and persisted on assistant message metadata

def materialize_for_model(
    attachments: Iterable[Attachment],
    *,
    capabilities: Capabilities,
    available_token_budget: int,
    extracted_text_cache: Mapping[str, str] | None = None,  # by attachment id
) -> MaterializationResult: ...

class AttachmentNotSupportedError(Exception):
    """Raised when an attachment has no viable materialization path
    for the selected model (e.g. image + non-vision model)."""
```

### Capability extension

```python
# packages/core/src/openlia/llm/types.py

@dataclass(frozen=True)
class Capabilities:
    # ...existing fields...
    pdf_native: bool = False
```

Populated in `model_defaults.py`: True for Anthropic and Gemini families; False for OpenAI, Ollama, OpenRouter (default), OpenAI-compat.

### Provider adapter contract

```python
class LLMProvider:
    def render_content_blocks(
        self, blocks: list[ContentBlock]
    ) -> list[Any]:  # provider-specific message content array
        ...
```

The runtime guarantees that `blocks` only contains types the provider supports for the active model — adapters do not need defensive checks.

### Persistence service

```python
# packages/server/src/openlia_server/services/attachments.py

@dataclass(frozen=True)
class FileUpload:
    filename: str
    mime_type: str
    content: bytes

@dataclass(frozen=True)
class ValidationError:
    filename: str
    reason: Literal[
        "file_too_large",
        "too_many_files",
        "type_not_allowed",
        "extraction_failed",
    ]

def validate_uploads(uploads: list[FileUpload]) -> list[ValidationError]: ...

def persist_attachments(
    db: Session,
    *,
    message_id: str,
    uploads: list[FileUpload],
) -> list[ChatAttachment]:
    """Stores files, extracts text, persists rows. All-or-nothing:
    raises if any validation fails (call validate_uploads first)."""
```

### Schema additions

```sql
ALTER TABLE chat_attachments ADD COLUMN extracted_text TEXT NULL;
ALTER TABLE chat_attachments ADD COLUMN extracted_at TIMESTAMP NULL;
```

Existing columns (`id`, `message_id`, `filename`, `mime_type`, `size_bytes`, `storage_path`, `created_at`) preserved. The `message_id NOT NULL FK CASCADE` is kept — atomic-at-send means a message always exists before its attachments.

### Route shape

```
POST /api/departments/secretary/chat
POST /api/departments/equity-research/chat

Content-Type: multipart/form-data

Form fields:
  message: string (required)
  session_id: string | null
  files: file[] (optional, max 10)

Success response:
  Content-Type: text/event-stream
  ... SSE events ...

Validation failure response (before SSE opens):
  HTTP 400
  Content-Type: application/json
  {
    "errors": [
      {"filename": "huge.pdf", "reason": "file_too_large"},
      {"filename": "secret.zip", "reason": "type_not_allowed"}
    ]
  }
```

---

## Mime allowlist

| Category | Mime types | Materialization |
|---|---|---|
| Text | `text/plain`, `text/markdown`, `text/csv`, `application/json`, `text/x-*` (source code) | TextBlock (raw decode) |
| Image | `image/png`, `image/jpeg`, `image/webp`, `image/gif` | ImageBlock if vision; else reject |
| PDF | `application/pdf` | DocumentBlock if pdf_native; else extract via pypdf → TextBlock |
| Word | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Extract via python-docx → TextBlock |
| Excel | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.ms-excel` | Extract via openpyxl → TextBlock |
| PowerPoint | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | Extract via python-pptx → TextBlock |

Anything outside this list is rejected as `type_not_allowed`. Server validates by sniffing magic bytes (via `python-magic` or stdlib `imghdr`/`mimetypes`), not by trusting the client-provided mime.

## Truncation policy

```
available_budget = capabilities.max_context_tokens
                 - reserved_for_system_and_history
                 - reserved_for_response

per_attachment_hard_ceiling = 500_000  # tokens

If sum(extracted_token_counts) <= available_budget:
    pass through unmodified
Else:
    proportional split: each attachment gets
        budget_i = floor(available_budget * (size_i / sum(sizes)))
    truncate text to fit budget_i
    prepend banner:
        "[Truncated: showing first ~N tokens of ~M total. Some content omitted.]"
    accumulate warning in MaterializationResult.warnings
```

Token counting uses `tiktoken` (cl100k_base) for OpenAI-family models; for others, a chars/4 estimate is sufficient (this is a budget heuristic, not billing).

---

## Lifecycle

### Synchronous unlink on commit

```python
# packages/server/src/openlia_server/db/models/content.py

@event.listens_for(Session, "after_commit")
def _unlink_attachment_files_after_commit(session):
    for obj in session.info.get("pending_attachment_unlinks", ()):
        attachment_storage.unlink(obj)
    session.info["pending_attachment_unlinks"] = ()

@event.listens_for(ChatAttachment, "before_delete")
def _stage_attachment_unlink(mapper, connection, target):
    sess = Session.object_session(target)
    sess.info.setdefault("pending_attachment_unlinks", []).append(target.storage_path)
```

This pattern ensures: paths are captured before delete (the row is gone after commit), and unlinks only fire on successful commit (rollback leaves files intact). CASCADE deletes from message-delete or session-delete trigger the `before_delete` event for each cascaded attachment row.

### Janitor

A periodic task in the FastAPI lifespan, hourly:

```python
def gc_orphaned_attachments(db: Session, *, grace_seconds: int = 3600) -> int:
    referenced = {row.storage_path for row in db.query(ChatAttachment.storage_path)}
    root = attachment_storage.configured_root()
    cutoff = time.time() - grace_seconds
    removed = 0
    for path in root.rglob("*"):
        if path.is_file() and str(path) not in referenced and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
```

CLI escape hatch: `openlia attachments gc` (added in `cli.py`).

---

## Build sequence (vertical TDD slices)

Each phase is a vertical slice. Within a phase, write **one test → minimal impl → next test**. No horizontal "all tests then all code." The tracer bullet is Phase 1 — proves filesystem IO end-to-end before any LLM, runtime, or HTTP code is touched.

Phases are listed in dependency order. Each phase can be reviewed and merged independently *if* it doesn't ship to a user-facing surface (Phases 1–9 are internal; Phases 10+ are user-visible).

| Phase | Scope | Public interface tested | Tracer bullet test |
|---|---|---|---|
| 1 | Storage service | `save / read / unlink` | "save bytes, read them back, unlink" |
| 2 | Capability metadata | `Capabilities.pdf_native` | "Anthropic Sonnet has pdf_native=True; OpenAI gpt-5.4 has False" |
| 3 | Attachment + content blocks | dataclass shapes | "Attachment(id, filename, mime, path, size) instantiates" |
| 4 | Materializer | `materialize_for_model` | "txt file → TextBlock(text=file contents)" |
| 5 | Truncation | `materialize_for_model` with constrained budget | "1MB text + 4k context model → truncated TextBlock with banner" |
| 6 | ChatRunner consumes attachments | `ChatRunner.run(attachments=...)` | "run() with one attachment produces an LLMRequest whose user message contains the materialized blocks" |
| 7 | Provider adapters | `render_content_blocks` per adapter | "Anthropic adapter renders ImageBlock as `{type:'image', source:{type:'base64', ...}}`" |
| 8 | Schema migration | migration up/down | "alembic upgrade head adds extracted_text column" |
| 9 | Persistence service | `validate_uploads`, `persist_attachments` | "valid pdf upload becomes a ChatAttachment row with extracted_text populated" |
| 10 | Secretary route multipart | `POST /departments/secretary/chat` (multipart) | "multipart submit with text + 1 file persists message + attachment + opens SSE" |
| 11 | ER route multipart | `POST /departments/equity-research/chat` (multipart) | mirror of 10 |
| 12 | Lifecycle | `after_commit` hook + janitor | "deleting a ChatAttachment row commits, file disappears from disk" |
| 13 | useChatStream multipart | hook contract | "send(text, files) builds FormData and surfaces upload progress" |
| 14 | ChatInput composer | rendered behavior | "selecting a too-big file shows error chip without uploading" |
| 15 | ErComposer | rendered behavior | mirror of 14 |
| 16 | Browser smoke | manual + full suite | "attach PDF in Secretary, model summarizes its contents" |

### Per-phase done definition

Each phase done means:
- All RED tests written for that phase are GREEN.
- Pre-existing tests in adjacent modules still pass (`uv run pytest` for backend phases, `npm test` for frontend phases).
- `uv run ruff check . && uv run ruff format .` clean.
- For phases that touch core types, `npm run build` and `tsc --noEmit` clean.

### Acceptance criteria (whole feature)

- [ ] User can attach text, image, PDF, and Office files in the Secretary composer
- [ ] User can attach the same file types in the Equity Research composer
- [ ] Uploaded attachments are persisted with metadata, scoped to their parent message, and isolated per session
- [ ] The final LLM request built by the runtime includes attachment content as appropriate provider content blocks
- [ ] An image attached to a non-vision model is rejected at send time with a clear error and a model-switch hint
- [ ] A PDF on Anthropic/Gemini uses the native document path; on other providers it extracts to text
- [ ] Office documents always extract to text and are usable on every provider
- [ ] Truncation banner appears in the user message when the extracted content was clipped to fit the model's context
- [ ] Files are unlinked from disk when their `chat_attachments` row is deleted (via cascade or otherwise) and committed
- [ ] Hourly janitor removes orphan files older than 1h; manual `openlia attachments gc` works
- [ ] Per-file 25 MB and per-message 10-file caps enforced both client and server side
- [ ] Validation failures return 4xx JSON with per-file reasons; SSE never opens for failed uploads
- [ ] Existing test suites still pass; new tests cover the materializer, persistence, route conversion, and lifecycle

---

## Risks and open questions

- **Multipart + SSE timing under (A) atomic-at-send.** A 25 MB Office doc upload + extraction = several seconds where the user has hit submit but no SSE events have streamed yet. Mitigated by composer "processing..." state, but if user feedback during dogfood is poor we may need to revisit Q1 and split upload from send.
- **Token estimator accuracy for non-OpenAI models.** Chars/4 is rough. If users report unexpected truncation on Anthropic/Gemini, swap in provider-specific tokenizers.
- **`python-magic` system dep.** Installing `python-magic` requires libmagic on the host. If that's a deploy headache, fall back to allowlist-by-extension with extension-mime cross-check (less secure but no system dep).
- **Janitor and concurrency.** If multiple workers run the janitor simultaneously, they race on `unlink`. `missing_ok=True` makes this safe but wasteful. Pin to one worker (the lifespan-managed task) and don't expose it on a per-request path.
