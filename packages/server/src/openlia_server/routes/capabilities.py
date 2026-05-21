"""GET /capabilities — expose the v2.2 capability manifest to the frontend."""

from __future__ import annotations

from fastapi import APIRouter
from openlia.llm.runtime.report_v2.capability_manifest import load_manifest

router = APIRouter()


@router.get("/capabilities")
def get_capabilities() -> dict:
    return load_manifest().model_dump()
