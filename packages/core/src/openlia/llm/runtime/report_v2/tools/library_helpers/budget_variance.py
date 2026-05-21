"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: finance/skills/financial-analyst/scripts/budget_variance_analyzer.py
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperSchema,
    register_library_helper,
)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


class BudgetVarianceAnalyzer:
    """Analyze budget variances with materiality filtering and classification."""

    def __init__(
        self,
        data: dict[str, Any],
        threshold_pct: float = 10.0,
        threshold_amt: float = 50000.0,
    ) -> None:
        self.line_items: list[dict[str, Any]] = data.get("line_items", [])
        self.period: str = data.get("period", "Current Period")
        self.company: str = data.get("company", "Company")
        self.threshold_pct = threshold_pct
        self.threshold_amt = threshold_amt
        self.variances: list[dict[str, Any]] = []
        self.material_variances: list[dict[str, Any]] = []
        self.summary: dict[str, Any] = {}

    def classify_favorability(self, line_type: str, variance_amount: float) -> str:
        """Classify variance as favorable or unfavorable."""
        if line_type.lower() in ("revenue", "income", "sales"):
            return "Favorable" if variance_amount > 0 else "Unfavorable"
        else:
            return "Favorable" if variance_amount < 0 else "Unfavorable"

    def calculate_variances(self) -> list[dict[str, Any]]:
        """Calculate variances for all line items."""
        self.variances = []
        for item in self.line_items:
            name = item.get("name", "Unknown")
            line_type = item.get("type", "expense")
            department = item.get("department", "General")
            category = item.get("category", "Other")
            actual = item.get("actual", 0)
            budget = item.get("budget", 0)
            prior_year = item.get("prior_year", None)

            budget_var_amt = actual - budget
            budget_var_pct = safe_divide(budget_var_amt, budget) * 100
            py_var_amt = (actual - prior_year) if prior_year is not None else None
            py_var_pct = (
                safe_divide(py_var_amt, prior_year) * 100 if prior_year is not None else None
            )
            favorability = self.classify_favorability(line_type, budget_var_amt)
            is_material = (
                abs(budget_var_pct) >= self.threshold_pct
                or abs(budget_var_amt) >= self.threshold_amt
            )

            self.variances.append(
                {
                    "name": name,
                    "type": line_type,
                    "department": department,
                    "category": category,
                    "actual": actual,
                    "budget": budget,
                    "prior_year": prior_year,
                    "budget_variance_amount": budget_var_amt,
                    "budget_variance_pct": round(budget_var_pct, 2),
                    "prior_year_variance_amount": py_var_amt,
                    "prior_year_variance_pct": (
                        round(py_var_pct, 2) if py_var_pct is not None else None
                    ),
                    "favorability": favorability,
                    "is_material": is_material,
                }
            )
        self.material_variances = [v for v in self.variances if v["is_material"]]
        return self.variances

    def department_summary(self) -> dict[str, dict[str, Any]]:
        """Summarize variances by department."""
        departments: dict[str, dict[str, float]] = {}
        for v in self.variances:
            dept = v["department"]
            if dept not in departments:
                departments[dept] = {
                    "total_actual": 0.0,
                    "total_budget": 0.0,
                    "total_variance": 0.0,
                    "favorable_count": 0,
                    "unfavorable_count": 0,
                    "line_count": 0,
                }
            departments[dept]["total_actual"] += v["actual"]
            departments[dept]["total_budget"] += v["budget"]
            departments[dept]["total_variance"] += v["budget_variance_amount"]
            departments[dept]["line_count"] += 1
            if v["favorability"] == "Favorable":
                departments[dept]["favorable_count"] += 1
            else:
                departments[dept]["unfavorable_count"] += 1
        for dept_data in departments.values():
            dept_data["variance_pct"] = round(
                safe_divide(dept_data["total_variance"], dept_data["total_budget"]) * 100,
                2,
            )
        return departments

    def category_summary(self) -> dict[str, dict[str, Any]]:
        """Summarize variances by category."""
        categories: dict[str, dict[str, float]] = {}
        for v in self.variances:
            cat = v["category"]
            if cat not in categories:
                categories[cat] = {
                    "total_actual": 0.0,
                    "total_budget": 0.0,
                    "total_variance": 0.0,
                    "line_count": 0,
                }
            categories[cat]["total_actual"] += v["actual"]
            categories[cat]["total_budget"] += v["budget"]
            categories[cat]["total_variance"] += v["budget_variance_amount"]
            categories[cat]["line_count"] += 1
        for cat_data in categories.values():
            cat_data["variance_pct"] = round(
                safe_divide(cat_data["total_variance"], cat_data["total_budget"]) * 100,
                2,
            )
        return categories

    def generate_executive_summary(self) -> dict[str, Any]:
        """Generate an executive summary of the variance analysis."""
        total_actual = sum(
            v["actual"]
            for v in self.variances
            if v["type"].lower() in ("revenue", "income", "sales")
        )
        total_budget = sum(
            v["budget"]
            for v in self.variances
            if v["type"].lower() in ("revenue", "income", "sales")
        )
        total_expense_actual = sum(
            v["actual"]
            for v in self.variances
            if v["type"].lower() not in ("revenue", "income", "sales")
        )
        total_expense_budget = sum(
            v["budget"]
            for v in self.variances
            if v["type"].lower() not in ("revenue", "income", "sales")
        )
        revenue_variance = total_actual - total_budget
        expense_variance = total_expense_actual - total_expense_budget
        favorable_count = sum(1 for v in self.variances if v["favorability"] == "Favorable")
        unfavorable_count = sum(1 for v in self.variances if v["favorability"] == "Unfavorable")
        self.summary = {
            "period": self.period,
            "company": self.company,
            "total_line_items": len(self.variances),
            "material_variances_count": len(self.material_variances),
            "favorable_count": favorable_count,
            "unfavorable_count": unfavorable_count,
            "revenue": {
                "actual": total_actual,
                "budget": total_budget,
                "variance_amount": revenue_variance,
                "variance_pct": round(safe_divide(revenue_variance, total_budget) * 100, 2),
            },
            "expenses": {
                "actual": total_expense_actual,
                "budget": total_expense_budget,
                "variance_amount": expense_variance,
                "variance_pct": round(safe_divide(expense_variance, total_expense_budget) * 100, 2),
            },
            "net_impact": revenue_variance - expense_variance,
            "materiality_thresholds": {
                "percentage": self.threshold_pct,
                "amount": self.threshold_amt,
            },
        }
        return self.summary

    def run_analysis(self) -> dict[str, Any]:
        """Run the complete variance analysis."""
        self.calculate_variances()
        dept_summary = self.department_summary()
        cat_summary = self.category_summary()
        exec_summary = self.generate_executive_summary()
        return {
            "executive_summary": exec_summary,
            "all_variances": self.variances,
            "material_variances": self.material_variances,
            "department_summary": dept_summary,
            "category_summary": cat_summary,
        }


def execute(**params: Any) -> dict[str, Any]:
    """Analyze budget variances with materiality filtering.

    Params:
        line_items: list of dicts with name, type, department,
            category, actual, budget, prior_year (required)
        period: label for the analysis period
        company: company name
        threshold_pct: materiality threshold as percentage (default 10.0)
        threshold_amt: materiality threshold as dollar amount (default 50000.0)
    """
    data = {
        "line_items": params["line_items"],
        "period": params.get("period", "Current Period"),
        "company": params.get("company", "Company"),
    }
    analyzer = BudgetVarianceAnalyzer(
        data,
        threshold_pct=params.get("threshold_pct", 10.0),
        threshold_amt=params.get("threshold_amt", 50000.0),
    )
    return analyzer.run_analysis()


SCHEMA = HelperSchema(
    name="budget_variance",
    description=(
        "Analyze actual vs budget vs prior year performance with materiality "
        "threshold filtering, favorable/unfavorable classification, and "
        "department/category breakdown."
    ),
    params={
        "line_items": HelperParam(
            type="list[dict]",
            description=(
                "Budget line items. Each dict: name, type (revenue|expense), department, "
                "category, actual, budget, optional prior_year."
            ),
            required=True,
        ),
        "period": HelperParam(
            type="str",
            default="Current Period",
            description="Label for the analysis period.",
            required=False,
        ),
        "company": HelperParam(
            type="str",
            default="Company",
            description="Company name for the report header.",
            required=False,
        ),
        "threshold_pct": HelperParam(
            type="float",
            default=10.0,
            description="Materiality threshold as percentage variance (default 10%).",
            required=False,
        ),
        "threshold_amt": HelperParam(
            type="float",
            default=50000.0,
            description="Materiality threshold as dollar amount (default $50K).",
            required=False,
        ),
    },
)

register_library_helper("budget_variance", execute, SCHEMA)
