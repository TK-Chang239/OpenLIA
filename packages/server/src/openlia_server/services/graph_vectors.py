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
from sqlalchemy import select
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


def upsert_artifact_summary(
    db: Session,
    *,
    user_id: str,
    artifact_kind: str,
    artifact_id: str,
    summary_text: str,
    provider: EmbeddingProvider,
    model_name: str,
) -> GraphArtifactSummary:
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
