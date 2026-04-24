from __future__ import annotations


def test_openlia_top_level_exports_formula_symbols():
    import openlia

    names = {
        "FormulaEngine",
        "EvaluationContext",
        "FormulaError",
        "RequirementRef",
        "extract_requirements",
        "parse",
        "Expression",
    }
    for name in names:
        assert hasattr(openlia, name), name
