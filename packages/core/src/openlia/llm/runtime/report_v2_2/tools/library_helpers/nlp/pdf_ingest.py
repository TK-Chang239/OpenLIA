"""pdf_ingest — extract text and tables from a PDF using pdfplumber.

Registered name: "pdf_ingest"
Category: ADAPTER

Accepts a file path (str | Path) or raw bytes.  Returns per-page text,
tables as list-of-rows, and document metadata.  No LLM is used; this is
a pure structural extraction helper.

Per helpers-design §2.4 (pdfplumber fallback path).
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any


def execute(
    pdf_path: str | Path | None = None,
    pdf_bytes: bytes | None = None,
    pages: list[int] | None = None,
    extract_tables: bool = True,
) -> dict[str, Any]:
    """Extract text and tables from a PDF.

    Args:
        pdf_path: Filesystem path to the PDF.  Mutually exclusive with pdf_bytes.
        pdf_bytes: Raw PDF bytes.  Mutually exclusive with pdf_path.
        pages: 1-indexed page numbers to extract.  None = all pages.
        extract_tables: Whether to extract tables via pdfplumber.  Defaults True.

    Returns:
        Dict with:
          - metadata: page_count, file_size_bytes, sha256, extraction_quality
          - pages: list of {page_number, text} dicts
          - tables: list of {page_number, rows: list[list[str | None]]} dicts
            (only present when extract_tables=True)

    Raises:
        ValueError: If neither or both of pdf_path/pdf_bytes are supplied,
            or if a requested page number is out of range.
        ImportError: If pdfplumber is not installed.
        OSError: If pdf_path cannot be read.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber is required for pdf_ingest. Install via: uv add pdfplumber"
        ) from exc

    if pdf_path is None and pdf_bytes is None:
        raise ValueError("Exactly one of pdf_path or pdf_bytes must be supplied.")
    if pdf_path is not None and pdf_bytes is not None:
        raise ValueError("Supply only one of pdf_path or pdf_bytes, not both.")

    if pdf_bytes is None:
        raw = Path(pdf_path).read_bytes()  # type: ignore[arg-type]
    else:
        raw = pdf_bytes

    file_size = len(raw)
    sha256 = hashlib.sha256(raw).hexdigest()

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        total_pages = len(pdf.pages)

        if pages is not None:
            invalid = [p for p in pages if p < 1 or p > total_pages]
            if invalid:
                raise ValueError(
                    f"Requested page numbers out of range [1, {total_pages}]: {invalid}"
                )
            page_indices = [p - 1 for p in pages]
        else:
            page_indices = list(range(total_pages))

        extracted_pages: list[dict[str, Any]] = []
        extracted_tables: list[dict[str, Any]] = []

        for idx in page_indices:
            page = pdf.pages[idx]
            page_num = idx + 1

            text = page.extract_text() or ""
            extracted_pages.append({"page_number": page_num, "text": text})

            if extract_tables:
                raw_tables = page.extract_tables() or []
                for table in raw_tables:
                    # pdfplumber rows: list[list[str | None]]
                    rows: list[list[str | None]] = [
                        [cell if cell is not None else None for cell in row] for row in table
                    ]
                    extracted_tables.append({"page_number": page_num, "rows": rows})

    extraction_quality = "high"
    empty_page_count = sum(1 for p in extracted_pages if not p["text"].strip())
    if total_pages > 0 and empty_page_count / len(extracted_pages) > 0.5:
        extraction_quality = "low"
    elif total_pages > 0 and empty_page_count / len(extracted_pages) > 0.2:
        extraction_quality = "medium"

    result: dict[str, Any] = {
        "metadata": {
            "page_count": total_pages,
            "pages_extracted": len(extracted_pages),
            "file_size_bytes": file_size,
            "sha256": sha256,
            "extraction_quality": extraction_quality,
        },
        "pages": extracted_pages,
    }
    if extract_tables:
        result["tables"] = extracted_tables

    return result


from openlia.llm.runtime.report_v2_2 import (  # noqa: E402
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper  # noqa: E402

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="pdf_ingest",
        category=Category.ADAPTER,
        one_liner="Extract text and tables from a PDF using pdfplumber.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Structural text and table extraction from SEC filings, earnings decks, "
            "or any PDF document. Produces per-page text and tables-as-rows for "
            "downstream LLM-NLP helpers (mda_extraction, risk_factors_extraction, etc.)."
        ),
        when_to_use=[
            "Pre-processing step before any NLP helper that operates on filing text.",
            "Extracting tables from financial statements embedded in a PDF.",
            "When the caller has a PDF path or bytes and needs raw text.",
        ],
        when_not_to_use=[
            "When text is already available as a plain string — skip ingest overhead.",
            "For image-only (fully scanned) PDFs where pdfplumber yields empty text — "
            "use the multimodal pdf_ingest path (Anthropic API) instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "pdf_path": HelperParam(
                type="str | Path | None",
                required=False,
                default=None,
                description="Filesystem path to the PDF. Mutually exclusive with pdf_bytes.",
            ),
            "pdf_bytes": HelperParam(
                type="bytes | None",
                required=False,
                default=None,
                description="Raw PDF bytes. Mutually exclusive with pdf_path.",
            ),
            "pages": HelperParam(
                type="list[int] | None",
                required=False,
                default=None,
                description="1-indexed page numbers to extract. None = all pages.",
            ),
            "extract_tables": HelperParam(
                type="bool",
                required=False,
                default=True,
                description="Whether to extract tables. Defaults True.",
            ),
        },
        outputs=[
            HelperOutput(
                name="pdf_ingest_output",
                type="pdf_ingest_output",
                description=(
                    "metadata (page_count, file_size_bytes, sha256, extraction_quality), "
                    "pages list (page_number, text), tables list (page_number, rows)."
                ),
            ),
        ],
        produces_artifacts=["pdf_ingest_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[VerifierIssueType.BLOCK_SHAPE],
)

register_helper(_SCHEMA, execute)
