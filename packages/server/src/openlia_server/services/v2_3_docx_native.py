"""Native OOXML footnote support for the v2.3 docx renderer.

python-docx 1.x has no high-level footnote API. We:

1. Build a ``word/footnotes.xml`` package part with one ``<w:footnote>``
   per resolved citation. The standard ``separator`` + ``continuationSeparator``
   entries (ids -1 and 0) are included so Word renders the line above
   the footnote area.
2. Register the part as a relationship target from the main document.
3. Append it under the ``footnotes`` Content-Types entry so the file is
   a valid OOXML package.
4. Walk the rendered paragraphs and replace every ``[^N]`` text run with
   a real ``<w:footnoteReference w:id="N">`` run.

The result opens in Word / LibreOffice with real footnote markers that
hyperlink to the bottom of the page, instead of inline ``[^1]`` text and
a separate References section.
"""

from __future__ import annotations

import re
from typing import Any

from docx.opc.constants import CONTENT_TYPE, RELATIONSHIP_TYPE
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml.ns import nsmap, qn
from lxml import etree

# Inline footnote-marker pattern produced by ``schemas.resolve()``.
_FOOTNOTE_MARK_RE = re.compile(r"\[\^(\d+)\]")

# Standard separator content. Word uses ``-1`` for the top divider and
# ``0`` for the continuation divider. Real footnotes start at ``1``.
_FOOTNOTES_XML_HEAD = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:type="separator" w:id="-1">
    <w:p><w:r><w:separator/></w:r></w:p>
  </w:footnote>
  <w:footnote w:type="continuationSeparator" w:id="0">
    <w:p><w:r><w:continuationSeparator/></w:r></w:p>
  </w:footnote>"""
_FOOTNOTES_XML_TAIL = "</w:footnotes>"


def attach_native_footnotes(doc: Any, footnote_texts: list[str]) -> None:
    """Attach a native footnotes part to ``doc`` and rewrite ``[^N]`` markers.

    ``footnote_texts[i-1]`` is the body of footnote ``i`` (1-indexed to
    match the markers produced by ``schemas.resolve()``).
    """
    if not footnote_texts:
        return

    _ensure_footnotes_part(doc, footnote_texts)
    _rewrite_inline_markers(doc)


# ---------------------------------------------------------------------------
# Footnotes part
# ---------------------------------------------------------------------------


def _ensure_footnotes_part(doc: Any, footnote_texts: list[str]) -> None:
    body_xml = []
    for idx, text in enumerate(footnote_texts, start=1):
        safe = _escape_text(text)
        body_xml.append(
            f"""<w:footnote w:id="{idx}">
  <w:p>
    <w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>
    <w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>
    <w:r><w:t xml:space="preserve"> {safe}</w:t></w:r>
  </w:p>
</w:footnote>"""
        )
    xml_str = _FOOTNOTES_XML_HEAD + "\n" + "\n".join(body_xml) + "\n" + _FOOTNOTES_XML_TAIL

    package = doc.part.package
    partname = PackURI("/word/footnotes.xml")
    part = Part(
        partname=partname,
        content_type=CONTENT_TYPE.WML_FOOTNOTES,
        blob=xml_str.encode("utf-8"),
        package=package,
    )
    doc.part.relate_to(part, RELATIONSHIP_TYPE.FOOTNOTES)


# ---------------------------------------------------------------------------
# Inline marker rewrite
# ---------------------------------------------------------------------------


def _rewrite_inline_markers(doc: Any) -> None:
    body = doc.part.element.body
    # ``.iter(qn('w:p'))`` walks every paragraph including those nested
    # inside tables / sections.
    for paragraph in body.iter(qn("w:p")):
        _rewrite_paragraph(paragraph)


def _rewrite_paragraph(paragraph: Any) -> None:
    # Collect every w:t descendant and walk left-to-right. We must rebuild
    # the paragraph piecewise because a footnote reference is a sibling
    # <w:r>, not text inside an existing run.
    for text_el in list(paragraph.iter(qn("w:t"))):
        text = text_el.text or ""
        if not _FOOTNOTE_MARK_RE.search(text):
            continue
        _split_run_on_markers(text_el)


def _split_run_on_markers(text_el: Any) -> None:
    """Replace ``[^N]`` substrings inside a single ``w:t`` with a
    footnote-reference run. We do this by editing the parent run's
    parent paragraph: removing the original run, then inserting a
    sequence of (text-run, ref-run, text-run, ref-run, …)."""
    run = text_el.getparent()  # w:r
    paragraph = run.getparent()  # w:p
    parent_idx = list(paragraph).index(run)

    text = text_el.text or ""
    parts: list[tuple[str, Any]] = []  # ("text", "...") or ("ref", id)
    cursor = 0
    for match in _FOOTNOTE_MARK_RE.finditer(text):
        if match.start() > cursor:
            parts.append(("text", text[cursor : match.start()]))
        parts.append(("ref", int(match.group(1))))
        cursor = match.end()
    if cursor < len(text):
        parts.append(("text", text[cursor:]))

    # Remove the original run.
    paragraph.remove(run)

    # Insert replacements at the original index.
    for offset, (kind, value) in enumerate(parts):
        if kind == "text":
            new_run = _clone_run_text(run, value)
        else:
            new_run = _make_footnote_ref_run(value)
        paragraph.insert(parent_idx + offset, new_run)


def _clone_run_text(template_run: Any, text_value: str) -> Any:
    """Create a new w:r whose run properties match `template_run` and
    whose text is `text_value`. Preserves bold/italic/style from the
    original split point."""
    new_run = etree.SubElement(etree.Element(qn("w:r")), qn("w:r"))
    # Make it a top-level fresh element.
    new_run = etree.Element(qn("w:r"))
    rpr = template_run.find(qn("w:rPr"))
    if rpr is not None:
        new_run.append(_deepcopy(rpr))
    t = etree.SubElement(new_run, qn("w:t"))
    t.text = text_value
    t.set(qn("xml:space"), "preserve")
    return new_run


def _make_footnote_ref_run(footnote_id: int) -> Any:
    """Build:
    <w:r>
      <w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>
      <w:footnoteReference w:id="N"/>
    </w:r>
    """
    r = etree.Element(qn("w:r"))
    rpr = etree.SubElement(r, qn("w:rPr"))
    rstyle = etree.SubElement(rpr, qn("w:rStyle"))
    rstyle.set(qn("w:val"), "FootnoteReference")
    ref = etree.SubElement(r, qn("w:footnoteReference"))
    ref.set(qn("w:id"), str(footnote_id))
    return r


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deepcopy(element: Any) -> Any:
    return etree.fromstring(etree.tostring(element))


def _escape_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = ["attach_native_footnotes"]


# Sanity guard — touch nsmap so the unused-import lint stays quiet (it's
# used implicitly by qn()'s namespace resolution).
_ = nsmap
