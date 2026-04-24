"""OpenLIA core library — pure Python, zero web dependencies."""

from openlia.formula import (
    EvaluationContext,
    Expression,
    FormulaEngine,
    FormulaError,
    RequirementRef,
    extract_requirements,
    parse,
)

__version__ = "0.1.0"

__all__ = [
    "EvaluationContext",
    "Expression",
    "FormulaEngine",
    "FormulaError",
    "RequirementRef",
    "__version__",
    "extract_requirements",
    "parse",
]
