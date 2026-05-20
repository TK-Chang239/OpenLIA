"""Post-section validators for report_v2 (WS4).

Validators run after section markdown is written but before the report is
finalised. Hard failures raise structured exceptions; soft failures are
surfaced via telemetry and do not block the run.
"""

from openlia.llm.runtime.report_v2.validators.numeric_consistency import (
    NumericValidationError,
    ValidatorFailure,
    ValidatorReport,
    validate_sections,
)

__all__ = [
    "NumericValidationError",
    "ValidatorFailure",
    "ValidatorReport",
    "validate_sections",
]
