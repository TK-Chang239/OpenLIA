"""LLM client protocols for v2.3 stages.

Each stage that calls an LLM depends on a narrow client protocol, not on the
Anthropic SDK directly. This keeps stages testable with in-process fakes and
lets the runner factory inject a real client per request (with the model
resolved via the per-user `er_v2_3_model_assignments` mapping).
"""

from .clarifier import ClarifierClient, ClarifierRequest, FakeClarifierClient
from .llm_clarifier import LLMClarifierClient
from .synthesizer import (
    FakeSynthesizerClient,
    SynthesizerClient,
    SynthesizerRequest,
)
from .writer import FakeWriterClient, WriterClient, WriterRequest

__all__ = [
    "ClarifierClient",
    "ClarifierRequest",
    "FakeClarifierClient",
    "FakeSynthesizerClient",
    "FakeWriterClient",
    "LLMClarifierClient",
    "SynthesizerClient",
    "SynthesizerRequest",
    "WriterClient",
    "WriterRequest",
]
