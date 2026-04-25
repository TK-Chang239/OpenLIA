# Releasing OpenLIA

OpenLIA ships as one Docker image (`ghcr.io/TK-Chang239/openlia`) plus
two PyPI packages (`openlia-core`, `openlia`). Releases are tag-driven:
pushing a SemVer tag triggers `.github/workflows/release.yml`, which
builds and publishes everything.

## Versioning

OpenLIA follows [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

- `MAJOR` — breaking API or schema migrations that need manual ops.
- `MINOR` — backward-compatible features, new departments, new endpoints.
- `PATCH` — bug fixes only.
- Pre-releases: `0.2.0-rc.1` style. The release workflow marks tags
  containing `-` as GitHub pre-releases automatically.

## Pre-flight checklist

1. Versions in **both** package manifests must match the tag:
   - `packages/core/pyproject.toml::project.version`
   - `packages/server/pyproject.toml::project.version`
2. Re-generate the lockfile if any deps moved: `uv lock`.
3. Run the full local gate:
   ```bash
   bash scripts/acceptance.sh
   ```
4. Update `CHANGELOG.md`:
   - Promote the `[Unreleased]` block to `[X.Y.Z] — YYYY-MM-DD`.
   - Add a fresh empty `[Unreleased]` block at the top.
   - Update the link references at the bottom of the file.
5. Commit on `main` with message `release: vX.Y.Z`.

## Tag and push

```bash
git tag -a vX.Y.Z -m "OpenLIA vX.Y.Z"
git push origin vX.Y.Z
```

The tag push fires the release workflow.

## Release workflow side-effects

`.github/workflows/release.yml` runs three jobs in parallel:

1. **Docker** — builds a multi-arch image (`linux/amd64`,
   `linux/arm64`) and pushes the following tags to GHCR:
   - `ghcr.io/TK-Chang239/openlia:X.Y.Z`
   - `ghcr.io/TK-Chang239/openlia:X.Y`
   - `ghcr.io/TK-Chang239/openlia:X`
   - `ghcr.io/TK-Chang239/openlia:latest` (only on default-branch tags)
2. **Python** — runs `uv build --package openlia-core` and
   `uv build --package openlia`, then publishes the wheels to PyPI via
   trusted publishing if `PYPI_API_TOKEN` is configured. Without the
   token the workflow logs `PYPI_API_TOKEN unset — wheels built but not
   published.` and exits 0 (no failure on first-time / dry-run releases).
3. **Release notes** — creates a GitHub Release with auto-generated
   notes pulled from merged PRs since the previous tag.

## Post-release verification

```bash
# Docker
docker pull ghcr.io/TK-Chang239/openlia:X.Y.Z
docker run --rm -p 8000:8000 ghcr.io/TK-Chang239/openlia:X.Y.Z &
curl -fsS http://127.0.0.1:8000/healthz

# PyPI (clean venv)
python -m venv /tmp/openlia-verify
/tmp/openlia-verify/bin/pip install openlia==X.Y.Z
/tmp/openlia-verify/bin/openlia --help
```

## Rolling a broken release

If `vX.Y.Z` is unusable:

1. Yank the wheels on PyPI:
   - `pip-yank openlia-core==X.Y.Z` or use the PyPI web UI.
   - Same for `openlia==X.Y.Z`.
2. Delete the GHCR tag (web UI: *Packages > openlia > Tags > Delete*).
3. Tag a hotfix:
   ```bash
   git tag -a vX.Y.(Z+1) -m "Hotfix for vX.Y.Z"
   git push origin vX.Y.(Z+1)
   ```
   Patch versions stay monotonic; never reuse a yanked tag number.
