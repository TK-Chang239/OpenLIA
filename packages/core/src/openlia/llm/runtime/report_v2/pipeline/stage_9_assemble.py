"""Stage 9: assemble — re-export of build_report_v2 for pipeline integration."""

from openlia.llm.runtime.report_v2.rendering.assembler import build_report_v2

__all__ = ["build_report_v2"]
