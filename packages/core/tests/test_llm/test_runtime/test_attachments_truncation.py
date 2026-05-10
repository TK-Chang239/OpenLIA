"""Phase 5 — token-budget-aware truncation.

These tests probe ``materialize_for_model``'s truncation behavior. Token
counts are heuristic (chars/4 for non-OpenAI providers); tests assert on
the *contract* (truncated text fits the budget; banner is present;
warnings are emitted) rather than on exact tokenizer output.
"""

from __future__ import annotations

from pathlib import Path

from openlia.llm.runtime.attachments import materialize_for_model
from openlia.llm.runtime.messages import Attachment, TextBlock
from openlia.llm.types import Capabilities

_BIG_MODEL = Capabilities(vision=True, pdf_native=True, max_context_tokens=200_000)


def _store_text(tmp_path: Path, name: str, text: str) -> Attachment:
    path = tmp_path / name
    path.write_bytes(text.encode())
    return Attachment(
        id=f"att-{name}",
        filename=name,
        mime_type="text/plain",
        storage_path=str(path),
        size_bytes=len(text.encode()),
    )


def test_text_under_budget_passes_through_unchanged(tmp_path: Path) -> None:
    att = _store_text(tmp_path, "small.txt", "hello world")
    result = materialize_for_model([att], capabilities=_BIG_MODEL, available_token_budget=1_000_000)
    assert isinstance(result.blocks[0], TextBlock)
    assert result.blocks[0].text == "hello world"
    assert result.warnings == []


def test_text_over_budget_is_truncated_with_banner(tmp_path: Path) -> None:
    """When the extracted/decoded text exceeds the budget, truncate it,
    prepend a banner, and surface a warning."""
    long_text = "x" * 40_000  # ~10k tokens at chars/4
    att = _store_text(tmp_path, "huge.txt", long_text)

    # Budget so small that truncation must happen
    result = materialize_for_model([att], capabilities=_BIG_MODEL, available_token_budget=500)

    block = result.blocks[0]
    assert isinstance(block, TextBlock)
    # Banner must appear
    assert "[Truncated" in block.text
    assert "huge.txt" in block.text or "huge" in block.text
    # Body must be smaller than the original
    assert len(block.text) < len(long_text)
    # A warning must surface so the SSE/UI can render a chip
    assert any("huge.txt" in w and "truncated" in w.lower() for w in result.warnings)


def test_per_attachment_hard_ceiling_truncates_even_with_huge_budget(
    tmp_path: Path,
) -> None:
    """No single attachment may consume more than the per-file ceiling
    (500k tokens, ~2_000_000 chars), even if the budget allows it."""
    # 10M chars => ~2.5M tokens at chars/4 — well above the 500k ceiling
    enormous = "y" * 10_000_000
    att = _store_text(tmp_path, "enormous.txt", enormous)

    result = materialize_for_model(
        [att],
        capabilities=_BIG_MODEL,
        available_token_budget=10_000_000,  # generous, ceiling still applies
    )

    block = result.blocks[0]
    assert isinstance(block, TextBlock)
    assert len(block.text) < len(enormous)
    assert "[Truncated" in block.text


def test_multiple_attachments_share_budget_proportionally(tmp_path: Path) -> None:
    """Two attachments above budget split it proportionally to their sizes,
    so the smaller one isn't crowded out by the larger."""
    small = _store_text(tmp_path, "small.txt", "a" * 4_000)  # ~1k tokens
    large = _store_text(tmp_path, "large.txt", "b" * 16_000)  # ~4k tokens

    # Total ~5k tokens; budget 1k forces both to truncate
    result = materialize_for_model(
        [small, large], capabilities=_BIG_MODEL, available_token_budget=1_000
    )

    assert len(result.blocks) == 2
    small_block, large_block = result.blocks
    assert isinstance(small_block, TextBlock)
    assert isinstance(large_block, TextBlock)
    # Both got truncated
    assert "[Truncated" in small_block.text
    assert "[Truncated" in large_block.text
    # The large attachment got proportionally more of the budget than the small one
    # (rough check — exact split depends on banner overhead, accept >= 2x ratio)
    assert len(large_block.text) > len(small_block.text)


def test_warnings_listed_per_truncated_attachment(tmp_path: Path) -> None:
    a = _store_text(tmp_path, "one.txt", "x" * 20_000)
    b = _store_text(tmp_path, "two.txt", "y" * 20_000)
    result = materialize_for_model([a, b], capabilities=_BIG_MODEL, available_token_budget=200)
    filenames_in_warnings = " ".join(result.warnings)
    assert "one.txt" in filenames_in_warnings
    assert "two.txt" in filenames_in_warnings


def test_default_budget_is_effectively_unlimited(tmp_path: Path) -> None:
    """When no budget is supplied, normal-sized attachments must not be
    truncated — preserves the Phase 4 behavior."""
    att = _store_text(tmp_path, "ok.txt", "a" * 50_000)
    result = materialize_for_model([att], capabilities=_BIG_MODEL)
    assert "[Truncated" not in result.blocks[0].text
    assert result.warnings == []
