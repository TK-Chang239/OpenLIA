"""v3 rendering pipeline.

Three layers:

  - ``chart_renderer``       v3 ChartSpec -> PNG bytes via matplotlib
  - ``citation_rewriter``    [^source_id] -> [^N], bibliography block
  - ``report_assembler``     full HTML document (cover + sections + bib)
"""

from .chart_renderer import RenderedChart, render_chart_png
from .citation_rewriter import (
    BibliographyEntry,
    RewrittenSection,
    build_bibliography,
    rewrite_section_markdown,
)
from .report_assembler import AssembledReport, assemble_html

__all__ = [
    "AssembledReport",
    "BibliographyEntry",
    "RenderedChart",
    "RewrittenSection",
    "assemble_html",
    "build_bibliography",
    "render_chart_png",
    "rewrite_section_markdown",
]
