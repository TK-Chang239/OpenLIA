"""Vector storage for the cross-session memory graph (slice 10).

Two seams:

* ``embed_and_store_construct`` populates the embedding columns on a
  ``GraphUserConstruct`` so slice-12 retrieval can rank by cosine.
* ``upsert_artifact_summary`` (and ``list_artifact_summaries``) manages
  the ``graph_artifact_summaries`` table — one summary embedding per
  (user, artifact). Re-calling with the same key updates in place; a
  model swap is reflected by ``embedding_model``.

Vectors are packed little-endian float32 BLOBs. Brute-force cosine
matching (slice 12) decodes on read. We stay below sqlite-vec's
threshold for the foreseeable future.
"""

from __future__ import annotations

import struct
import uuid

from openlia.llm.embeddings import EmbeddingProvider
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from openlia_server.db.models.graph import GraphArtifactSummary, GraphUserConstruct


def pack_vector(vec: list[float]) -> bytes:
    """Little-endian float32 packing — matches numpy's default tobytes()
    so slice-12 cosine can use ``np.frombuffer(..., dtype='<f4')``
    without a copy."""
    return struct.pack(f"<{len(vec)}f", *vec)


def unpack_vector(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"<{dim}f", blob))


def embed_and_store_construct(
    db: Session,
    *,
    construct: GraphUserConstruct,
    provider: EmbeddingProvider,
    model_name: str,
) -> GraphUserConstruct:
    [vec] = provider.embed([construct.statement])
    construct.embedding = pack_vector(vec)
    construct.embedding_model = model_name
    db.flush()
    return construct


_VALID_TONES: frozenset[str] = frozenset({"bullish", "bearish", "neutral"})
_VALID_HORIZONS: frozenset[str] = frozenset({"short", "medium", "long"})


def upsert_artifact_summary(
    db: Session,
    *,
    user_id: str,
    artifact_kind: str,
    artifact_id: str,
    summary_text: str,
    provider: EmbeddingProvider,
    model_name: str,
    subject: str | None = None,
    tagline: str | None = None,
    findings_text: str | None = None,
    entities_mentioned: list[str] | None = None,
    tone: str | None = None,
    horizon: str | None = None,
) -> GraphArtifactSummary:
    if tone is not None and tone not in _VALID_TONES:
        raise ValueError(f"invalid tone {tone!r}; expected one of {sorted(_VALID_TONES)} or None")
    if horizon is not None and horizon not in _VALID_HORIZONS:
        raise ValueError(
            f"invalid horizon {horizon!r}; expected one of {sorted(_VALID_HORIZONS)} or None"
        )

    [vec] = provider.embed([summary_text])
    blob = pack_vector(vec)

    stmt = select(GraphArtifactSummary).where(
        GraphArtifactSummary.user_id == user_id,
        GraphArtifactSummary.artifact_kind == artifact_kind,
        GraphArtifactSummary.artifact_id == artifact_id,
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        existing.summary_text = summary_text
        existing.embedding = blob
        existing.embedding_model = model_name
        existing.subject = subject
        existing.tagline = tagline
        existing.findings_text = findings_text
        existing.entities_mentioned = entities_mentioned
        existing.tone = tone
        existing.horizon = horizon
        db.flush()
        return existing

    row = GraphArtifactSummary(
        id=str(uuid.uuid4()),
        user_id=user_id,
        artifact_kind=artifact_kind,
        artifact_id=artifact_id,
        summary_text=summary_text,
        embedding=blob,
        embedding_model=model_name,
        subject=subject,
        tagline=tagline,
        findings_text=findings_text,
        entities_mentioned=entities_mentioned,
        tone=tone,
        horizon=horizon,
    )
    db.add(row)
    db.flush()
    return row


def list_artifact_summaries(
    db: Session,
    *,
    user_id: str,
) -> list[GraphArtifactSummary]:
    stmt = select(GraphArtifactSummary).where(GraphArtifactSummary.user_id == user_id)
    return list(db.execute(stmt).scalars())


def _fts_scores(
    db: Session,
    *,
    user_id: str,
    query_text: str,
) -> dict[str, float]:
    """Run an FTS5 MATCH and return ``{summary_id: normalized_bm25}``.

    SQLite returns ``bm25()`` rank where lower is better (negative is
    typical), so we negate and shift so higher = better, then divide by
    the max so the top hit is ~1.0. Returns ``{}`` if the backend has no
    FTS table (e.g. Postgres) or the query yields zero hits / is invalid
    FTS5 syntax.
    """
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return {}

    # FTS5 MATCH treats some chars as syntax. Quote each token to keep
    # this robust against arbitrary user input — quoted tokens are
    # treated as literals, and whitespace between them is implicit AND
    # which FTS5 widens to OR via the standard quoted-prefix scheme
    # below. We use OR explicitly so a partial match still surfaces.
    tokens = [t for t in query_text.split() if t]
    if not tokens:
        return {}
    fts_query = " OR ".join(f'"{t.replace(chr(34), chr(34) + chr(34))}"' for t in tokens)

    try:
        rows = db.execute(
            text(
                "SELECT s.id AS sid, bm25(graph_artifact_summaries_fts) AS rank "
                "FROM graph_artifact_summaries s "
                "JOIN graph_artifact_summaries_fts fts ON fts.rowid = s.rowid "
                "WHERE s.user_id = :uid "
                "AND graph_artifact_summaries_fts MATCH :q"
            ),
            {"uid": user_id, "q": fts_query},
        ).all()
    except Exception:
        # Malformed FTS query or missing FTS table — degrade to no
        # keyword signal rather than break the recall path.
        return {}

    if not rows:
        return {}

    # bm25(): lower (more negative) is more relevant. Convert to a
    # higher-is-better score then normalize so max == 1.0.
    raw = {r.sid: -float(r.rank) for r in rows}
    peak = max(raw.values())
    if peak <= 0.0:
        return {sid: 0.0 for sid in raw}
    return {sid: v / peak for sid, v in raw.items()}


def recall_artifacts(
    db: Session,
    *,
    user_id: str,
    query_text: str,
    provider: EmbeddingProvider,
    top_k: int = 5,
    cosine_weight: float = 0.6,
) -> list[tuple[GraphArtifactSummary, float]]:
    """Hybrid keyword + cosine ranking of artifact summaries.

    Combines two signals:

    1. Cosine similarity between the query embedding and each row's
       stored summary embedding (existing brute-force path, normalized
       to a 0..1 range by dividing by the cohort max).
    2. FTS5 ``bm25()`` rank on the SQLite shadow table, negated so
       higher is better and divided by the cohort max so the top hit is
       ~1.0.

    Final = ``cosine_weight * cosine + (1 - cosine_weight) * fts``.
    Rows whose ``embedding_model`` differs from the provider's current
    model are skipped on the cosine side; they can still surface via
    FTS.

    On non-SQLite backends (no FTS table) this degrades cleanly to
    pure cosine, matching the pre-hybrid behavior.
    """
    import numpy as np

    rows = list_artifact_summaries(db, user_id=user_id)
    if not rows:
        return []

    [q_vec] = provider.embed([query_text])
    q = np.asarray(q_vec, dtype=np.float32)
    q_norm = float(np.linalg.norm(q))

    cosine_raw: dict[str, float] = {}
    if q_norm > 0.0:
        for row in rows:
            if row.embedding is None:
                continue
            v = np.frombuffer(row.embedding, dtype=np.float32)
            if v.shape[0] != provider.dim:
                continue
            v_norm = float(np.linalg.norm(v))
            if v_norm == 0.0:
                continue
            cosine_raw[row.id] = float(np.dot(q, v) / (q_norm * v_norm))

    # Normalize cosine by its cohort max so it lives on the same ~0..1
    # axis as the FTS score. Pure-cosine callers (cosine_weight=1.0)
    # still want the unnormalized score so they get the historical
    # behavior; keep both.
    cosine_peak = max(cosine_raw.values(), default=0.0)

    fts_scores = _fts_scores(db, user_id=user_id, query_text=query_text)

    fts_weight = 1.0 - cosine_weight
    candidate_ids: set[str] = set(cosine_raw) | set(fts_scores)
    if not candidate_ids:
        return []

    by_id = {row.id: row for row in rows}
    scored: list[tuple[GraphArtifactSummary, float]] = []
    for rid in candidate_ids:
        cos = cosine_raw.get(rid, 0.0)
        fts = fts_scores.get(rid, 0.0)
        if cosine_weight >= 1.0:
            # Backward compat: pure cosine, unnormalized so a perfect
            # match still scores 1.0.
            score = cos
        else:
            cos_n = (cos / cosine_peak) if cosine_peak > 0.0 else 0.0
            score = cosine_weight * cos_n + fts_weight * fts
        scored.append((by_id[rid], score))

    scored.sort(key=lambda r: r[1], reverse=True)
    return scored[:top_k]
