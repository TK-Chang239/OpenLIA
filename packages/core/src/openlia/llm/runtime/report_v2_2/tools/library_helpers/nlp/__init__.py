"""NLP / unstructured-source helpers — PR 4.2.

8 helpers:
  - pdf_ingest (ADAPTER): pdfplumber text + table extraction
  - transcript_tone_analysis (LLM_NLP): earnings call tone classification
  - tone_shift_qoq (LLM_NLP): QoQ tone shift analysis
  - mda_extraction (LLM_NLP): MD&A structured insight extraction
  - risk_factors_extraction (LLM_NLP): Item 1A risk factor extraction
  - forward_looking_statements (LLM_NLP): forward-looking statement extraction
  - guidance_tracker (LLM_NLP): guidance vs actuals track record
  - customer_concentration_extraction (LLM_NLP): customer concentration disclosures
"""

from . import (  # noqa: F401
    customer_concentration_extraction,
    forward_looking_statements,
    guidance_tracker,
    mda_extraction,
    pdf_ingest,
    risk_factors_extraction,
    tone_shift_qoq,
    transcript_tone_analysis,
)
