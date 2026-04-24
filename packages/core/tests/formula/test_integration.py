"""Cross-module integration coverage.

The real assertions land in Task 10. This stub just pins the canonical
import surface so downstream plans fail fast if a name drifts.
"""

import pytest


def test_public_api_exports():
    from openlia.formula import (  # noqa: F401
        EvaluationContext,
        Expression,
        FormulaEngine,
        FormulaError,
        RequirementRef,
        extract_requirements,
        parse,
    )


@pytest.mark.skip(reason="Integration assertions land in Task 10")
def test_threshold_rule_end_to_end():
    raise AssertionError
