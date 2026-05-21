from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProseBlock(BaseModel):
    type: Literal["prose"] = "prose"
    text: str


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class KPICell(BaseModel):
    label: str
    value: str
    unit: str | None = None
    delta: str | None = None


class KPIStripBlock(BaseModel):
    type: Literal["kpi_strip"] = "kpi_strip"
    cells: list[KPICell]


class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    format: Literal["svg_inline", "png_base64"]
    payload: str
    caption: str | None = None


class QuoteBlock(BaseModel):
    type: Literal["quote_block"] = "quote_block"
    quote: str
    source: str
    citation_id: str | None = None


class SkipBannerBlock(BaseModel):
    type: Literal["skip_banner"] = "skip_banner"
    section_name: str
    reason: str


class DegradedBannerBlock(BaseModel):
    type: Literal["degraded_banner"] = "degraded_banner"
    section_name: str
    reason: str
    issue_list: list[str]


class ExcelAttachmentBlock(BaseModel):
    type: Literal["excel_attachment"] = "excel_attachment"
    filename: str
    download_url: str
    row_count: int
    sheet_count: int
