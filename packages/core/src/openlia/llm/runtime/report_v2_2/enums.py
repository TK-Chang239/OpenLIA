from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    """Closed L1 category enum — 19 values per schema-and-skills §3.1."""

    # Valuation
    COMPARABLES = "comparables"
    DCF = "dcf"
    ALTERNATIVE_VALUATION = "alternative_valuation"
    DECISION = "decision"
    # Business / fundamentals
    BUSINESS_QUALITY = "business_quality"
    STATEMENT_INTEGRITY = "statement_integrity"
    CREDIT_SOLVENCY = "credit_solvency"
    FORENSIC = "forensic"
    # Risk / macro / non-fundamental
    RISK_MACRO = "risk_macro"
    SAAS_KPIS = "saas_kpis"
    SIGNALS = "signals"
    # Qualitative / NLP / unstructured-source helpers
    LLM_NLP = "llm_nlp"
    # Outputs and infrastructure
    OUTPUT = "output"
    ADAPTER = "adapter"
    # Sector modules (Wave 1)
    SECTOR_BANKS = "sector_banks"
    SECTOR_REITS = "sector_reits"
    SECTOR_PHARMA = "sector_pharma"
    SECTOR_ENERGY = "sector_energy"
    SECTOR_INSURANCE = "sector_insurance"


class VerifierIssueType(StrEnum):
    """Closed parent enum — 18 values (14 original from report_v2 + 4 from PR 0.3 materialization).

    Per schema-and-skills §5.1 and impl-plan §16.
    The 14 original values mirror report_v2/schemas/verifier_issue.py IssueType.
    The 4 materialization types come from artifact-injection §8.
    Detail codes ride inside the parent via VerifierIssue.detail_code — do not add new
    parent types for finer-grained conditions; use detail_code instead.
    """

    # --- 14 original (mirrors report_v2 IssueType) ---
    # structural
    BLOCK_SHAPE = "block_shape"
    TOMBSTONE = "tombstone"
    YEAR_SLIP = "year_slip"
    # citation
    CITATION_MISSING = "citation_missing"
    CITATION_UNRESOLVED = "citation_unresolved"
    CITATION_ORPHANED = "citation_orphaned"
    # coverage
    ARTIFACT_MISSING = "artifact_missing"
    CONTENT_TOO_SPARSE = "content_too_sparse"
    DIRECTIVE_UNMET = "directive_unmet"
    # quality
    FACTUAL_INCONSISTENCY = "factual_inconsistency"
    NUMERIC_INCONSISTENCY = "numeric_inconsistency"
    INCOHERENT_PROSE = "incoherent_prose"
    # artifact-build
    REQUIRED_PARAM_UNRESOLVABLE = "required_param_unresolvable"
    HELPER_UNAVAILABLE = "helper_unavailable"

    # --- 4 new values used by PR 0.3 materialization but declared here in PR 0.1 ---
    BLOCK_ARTIFACT_TOO_LARGE = "block_artifact_too_large"
    BLOCK_PLAN_ARTIFACT_MISSING = "block_plan_artifact_missing"
    BLOCK_SECTION_PLAN_INVALID = "block_section_plan_invalid"
    BLOCK_HEADLINE_MISSING_QUANTITATIVE = "block_headline_missing_quantitative"


class Fidelity(StrEnum):
    """Three-value fidelity enum per artifact-injection §2."""

    HEADLINE = "headline"  # ~30-80 tokens; one-liner with the key number
    SUMMARY = "summary"  # ~200-400 tokens; compact table / chart caption
    FULL = "full"  # ~800-2000 tokens; complete artifact
