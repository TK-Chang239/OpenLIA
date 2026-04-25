"""OpenLIA formula engine — deterministic, safe expression DSL."""

from openlia.formula.derived import (
    RESERVED_NAMES,
    compute_derived_scalars,
    compute_derived_series,
)
from openlia.formula.engine import (
    EvaluationContext,
    FormulaEngine,
    FormulaError,
    FormulaResult,
    ParsedFormula,
    ParseError,
    TypeMismatchError,
    UnknownIdentifierError,
    parse_formula,
)
from openlia.formula.parser import Expression, parse
from openlia.formula.requirements import RequirementRef, extract_requirements
from openlia.formula.rules import (
    PanelResult,
    Rule,
    RuleSet,
    compute_streak,
    evaluate_ruleset,
)

__all__ = [
    "RESERVED_NAMES",
    "EvaluationContext",
    "Expression",
    "FormulaEngine",
    "FormulaError",
    "FormulaResult",
    "PanelResult",
    "ParseError",
    "ParsedFormula",
    "RequirementRef",
    "Rule",
    "RuleSet",
    "TypeMismatchError",
    "UnknownIdentifierError",
    "compute_derived_scalars",
    "compute_derived_series",
    "compute_streak",
    "evaluate_ruleset",
    "extract_requirements",
    "parse",
    "parse_formula",
]
