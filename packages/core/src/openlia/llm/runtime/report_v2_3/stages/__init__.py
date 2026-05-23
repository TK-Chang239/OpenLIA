"""v2.3 pipeline stages. Each stage reads + writes a slice of ReportState."""

from .assemble import AssembleStage as RealAssembleStage
from .base import (
    ASSEMBLE_SLOT_KEY,
    PIPELINE_ORDER,
    AssembleStage,
    Stage,
    StageContext,
)
from .clarify import ClarifyStage
from .compute import ComputeStage
from .noop import NoOpAssembleStage, NoOpStage
from .plan import PlanStage
from .research import ResearchStage
from .synthesize import SynthesizeStage
from .verify import VerifyStage
from .visualize import VisualizeStage
from .write import WriteStage

__all__ = [
    "ASSEMBLE_SLOT_KEY",
    "PIPELINE_ORDER",
    "AssembleStage",
    "ClarifyStage",
    "ComputeStage",
    "NoOpAssembleStage",
    "NoOpStage",
    "PlanStage",
    "RealAssembleStage",
    "ResearchStage",
    "Stage",
    "StageContext",
    "SynthesizeStage",
    "VerifyStage",
    "VisualizeStage",
    "WriteStage",
]
