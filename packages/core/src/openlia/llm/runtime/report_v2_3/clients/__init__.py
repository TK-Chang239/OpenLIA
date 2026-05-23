"""LLM client protocols for v2.3 stages.

Each stage that calls an LLM depends on a narrow client protocol, not on the
Anthropic SDK directly. This keeps stages testable with in-process fakes and
lets the runner factory inject a real client per request (with the model
resolved via the per-user `er_v2_3_model_assignments` mapping).
"""

from .clarifier import ClarifierClient, ClarifierRequest, FakeClarifierClient
from .compute import ComputeClient, ComputeRequest, FakeComputeClient
from .llm_clarifier import LLMClarifierClient
from .llm_researcher import (
    MAX_RESEARCH_TURNS,
    FakeToolLLMClient,
    LLMResearcherClient,
    ToolLLMClient,
    ToolTurnResponse,
)
from .llm_stage_clients import (
    LLMComputeClient,
    LLMPlannerClient,
    LLMSynthesizerClient,
    LLMVerifierClient,
    LLMWriterClient,
)
from .planner import FakePlannerClient, PlannerClient, PlannerRequest
from .researcher import FakeResearcherClient, ResearcherClient, ResearchRequest
from .synthesizer import (
    FakeSynthesizerClient,
    SynthesizerClient,
    SynthesizerRequest,
)
from .verifier import FakeVerifierClient, VerifierClient, VerifierRequest
from .writer import FakeWriterClient, WriterClient, WriterRequest

__all__ = [
    "MAX_RESEARCH_TURNS",
    "ClarifierClient",
    "ClarifierRequest",
    "ComputeClient",
    "ComputeRequest",
    "FakeClarifierClient",
    "FakeComputeClient",
    "FakePlannerClient",
    "FakeResearcherClient",
    "FakeSynthesizerClient",
    "FakeToolLLMClient",
    "FakeVerifierClient",
    "FakeWriterClient",
    "LLMClarifierClient",
    "LLMComputeClient",
    "LLMPlannerClient",
    "LLMResearcherClient",
    "LLMSynthesizerClient",
    "LLMVerifierClient",
    "LLMWriterClient",
    "PlannerClient",
    "PlannerRequest",
    "ResearchRequest",
    "ResearcherClient",
    "SynthesizerClient",
    "SynthesizerRequest",
    "ToolLLMClient",
    "ToolTurnResponse",
    "VerifierClient",
    "VerifierRequest",
    "WriterClient",
    "WriterRequest",
]
