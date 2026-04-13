#!/usr/bin/env python3
"""
Stock Update Report Style Extraction Pipeline

Extracts writing patterns from professional investment bank research reports
to produce a style guide for LLM report generation.

Phase 1: Per-report section extraction (PDF -> structured JSON)
Phase 2: Cross-report pattern analysis (grouped by section type)
Phase 3: Exemplar selection (best 2-3 examples per section)
Phase 4: Style guide synthesis (final markdown guide)

Usage:
    uv run --with anthropic python scripts/extraction/pipeline.py
    uv run --with anthropic python scripts/extraction/pipeline.py --phase 1
    uv run --with anthropic python scripts/extraction/pipeline.py --reports-dir path/to/pdfs
    uv run --with anthropic python scripts/extraction/pipeline.py --model claude-opus-4-20250514
"""

import argparse
import base64
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic

from prompts import (
    PHASE1_EXTRACT,
    PHASE1_SYSTEM,
    PHASE2_CROSS_REPORT,
    PHASE2_SYSTEM,
    PHASE3_EXEMPLAR_SELECTION,
    PHASE3_SYSTEM,
    PHASE4_STYLE_GUIDE,
    PHASE4_SYSTEM,
)

DEFAULT_REPORTS_DIR = Path("example_reports")
OUTPUT_DIR = Path("scripts/extraction/output")
DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8192

SECTION_IDS = [
    "investment_thesis",
    "event_analysis",
    "financial_results",
    "estimate_revisions",
    "valuation_and_target",
    "scenarios",
    "risks",
]

SECTION_TITLES = {
    "investment_thesis": "Investment Thesis / Key Takeaway",
    "event_analysis": "Event Analysis",
    "financial_results": "Financial Results Summary",
    "estimate_revisions": "Estimate Revisions",
    "valuation_and_target": "Valuation and Price Target",
    "scenarios": "Bull / Bear / Base Scenarios",
    "risks": "Risks",
}


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1
        if lines[end].strip() == "```":
            text = "\n".join(lines[start:end])
        else:
            text = "\n".join(lines[start:])
    return json.loads(text)


def call_llm(
    client: anthropic.Anthropic,
    *,
    system: str,
    prompt: str,
    model: str,
    pdf_path: Path | None = None,
) -> str:
    content: list[dict] = []
    if pdf_path:
        pdf_data = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_data,
            },
        })
    content.append({"type": "text", "text": prompt})

    message = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return message.content[0].text


def find_reports(reports_dir: Path) -> list[Path]:
    pdfs = sorted(reports_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {reports_dir}")
        sys.exit(1)
    return pdfs


def phase1(client: anthropic.Anthropic, reports_dir: Path, model: str) -> list[dict]:
    output_dir = OUTPUT_DIR / "phase1"
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = find_reports(reports_dir)
    print(f"Phase 1: Extracting sections from {len(reports)} reports")

    results = []
    for i, pdf_path in enumerate(reports, 1):
        stem = pdf_path.stem
        output_file = output_dir / f"{stem}.json"

        if output_file.exists():
            print(f"  [{i}/{len(reports)}] {stem} -- cached, skipping")
            results.append(json.loads(output_file.read_text()))
            continue

        print(f"  [{i}/{len(reports)}] {stem} -- extracting...")
        response = call_llm(
            client,
            system=PHASE1_SYSTEM,
            prompt=PHASE1_EXTRACT,
            model=model,
            pdf_path=pdf_path,
        )

        try:
            result = parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"    Failed to parse JSON: {e}")
            raw_file = output_dir / f"{stem}.raw.txt"
            raw_file.write_text(response)
            print(f"    Raw response saved to {raw_file}")
            continue

        result["_source_file"] = pdf_path.name
        output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        results.append(result)
        print(f"    Extracted {len(result.get('sections', []))} sections")

    print(f"Phase 1 complete: {len(results)}/{len(reports)} reports processed")
    return results


def phase2(client: anthropic.Anthropic, phase1_results: list[dict], model: str) -> dict:
    output_dir = OUTPUT_DIR / "phase2"
    output_dir.mkdir(parents=True, exist_ok=True)

    sections_by_id: dict[str, list[dict]] = defaultdict(list)
    for result in phase1_results:
        source = result.get("_source_file", "unknown")
        bank = result.get("metadata", {}).get("bank", "unknown")
        for section in result.get("sections", []):
            sid = section.get("framework_section_id")
            if sid in SECTION_IDS:
                sections_by_id[sid].append({
                    "source_report": source,
                    "bank": bank,
                    **section,
                })

    print(f"Phase 2: Analyzing patterns across {len(sections_by_id)} section types")

    analyses = {}
    for sid in SECTION_IDS:
        examples = sections_by_id.get(sid, [])
        if not examples:
            print(f"  {SECTION_TITLES[sid]} -- no examples found, skipping")
            continue

        output_file = output_dir / f"{sid}.json"
        if output_file.exists():
            print(f"  {SECTION_TITLES[sid]} -- cached, skipping")
            analyses[sid] = json.loads(output_file.read_text())
            continue

        print(f"  {SECTION_TITLES[sid]} -- {len(examples)} examples, analyzing...")
        prompt = PHASE2_CROSS_REPORT.format(
            section_id=sid,
            section_title=SECTION_TITLES[sid],
            sample_count=len(examples),
            examples_json=json.dumps(examples, indent=2, ensure_ascii=False),
        )

        response = call_llm(client, system=PHASE2_SYSTEM, prompt=prompt, model=model)

        try:
            analysis = parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"    Failed to parse JSON: {e}")
            raw_file = output_dir / f"{sid}.raw.txt"
            raw_file.write_text(response)
            continue

        output_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
        analyses[sid] = analysis

    print(f"Phase 2 complete: {len(analyses)} section types analyzed")
    return analyses


def phase3(
    client: anthropic.Anthropic,
    phase1_results: list[dict],
    phase2_analyses: dict,
    model: str,
) -> dict:
    output_dir = OUTPUT_DIR / "phase3"
    output_dir.mkdir(parents=True, exist_ok=True)

    sections_by_id: dict[str, list[dict]] = defaultdict(list)
    for result in phase1_results:
        source = result.get("_source_file", "unknown")
        bank = result.get("metadata", {}).get("bank", "unknown")
        for section in result.get("sections", []):
            sid = section.get("framework_section_id")
            if sid in SECTION_IDS:
                sections_by_id[sid].append({
                    "source_report": source,
                    "bank": bank,
                    **section,
                })

    print(f"Phase 3: Selecting exemplars for {len(phase2_analyses)} section types")

    exemplars = {}
    for sid, analysis in phase2_analyses.items():
        examples = sections_by_id.get(sid, [])
        if not examples:
            continue

        output_file = output_dir / f"{sid}.json"
        if output_file.exists():
            print(f"  {SECTION_TITLES[sid]} -- cached, skipping")
            exemplars[sid] = json.loads(output_file.read_text())
            continue

        print(f"  {SECTION_TITLES[sid]} -- selecting from {len(examples)} examples...")
        prompt = PHASE3_EXEMPLAR_SELECTION.format(
            section_id=sid,
            section_title=SECTION_TITLES[sid],
            analysis_json=json.dumps(analysis, indent=2, ensure_ascii=False),
            examples_json=json.dumps(examples, indent=2, ensure_ascii=False),
        )

        response = call_llm(client, system=PHASE3_SYSTEM, prompt=prompt, model=model)

        try:
            result = parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"    Failed to parse JSON: {e}")
            raw_file = output_dir / f"{sid}.raw.txt"
            raw_file.write_text(response)
            continue

        output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        exemplars[sid] = result

    print(f"Phase 3 complete: exemplars selected for {len(exemplars)} section types")
    return exemplars


def phase4(
    client: anthropic.Anthropic,
    phase2_analyses: dict,
    phase3_exemplars: dict,
    model: str,
) -> str:
    output_dir = OUTPUT_DIR / "phase4"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "style_guide.md"
    if output_file.exists():
        print("Phase 4: style_guide.md already exists, skipping (delete to regenerate)")
        return output_file.read_text()

    print("Phase 4: Synthesizing style guide...")
    prompt = PHASE4_STYLE_GUIDE.format(
        analyses_json=json.dumps(phase2_analyses, indent=2, ensure_ascii=False),
        exemplars_json=json.dumps(phase3_exemplars, indent=2, ensure_ascii=False),
    )

    response = call_llm(client, system=PHASE4_SYSTEM, prompt=prompt, model=model)

    output_file.write_text(response)
    print(f"Phase 4 complete: style guide written to {output_file}")
    return response


def load_phase_results(phase_num: int) -> list[dict] | dict:
    phase_dir = OUTPUT_DIR / f"phase{phase_num}"
    if not phase_dir.exists():
        print(f"Phase {phase_num} output not found at {phase_dir}. Run phase {phase_num} first.")
        sys.exit(1)

    if phase_num == 1:
        results = []
        for f in sorted(phase_dir.glob("*.json")):
            if f.name.endswith(".raw.txt"):
                continue
            results.append(json.loads(f.read_text()))
        return results
    else:
        results = {}
        for f in sorted(phase_dir.glob("*.json")):
            results[f.stem] = json.loads(f.read_text())
        return results


def main():
    parser = argparse.ArgumentParser(description="Stock Update Report Style Extraction Pipeline")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help=f"Directory containing PDF reports (default: {DEFAULT_REPORTS_DIR})",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4],
        help="Run only a specific phase (default: run all)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete cached output for the specified phase before running",
    )
    args = parser.parse_args()

    client = anthropic.Anthropic()

    if args.clean and args.phase:
        target = OUTPUT_DIR / f"phase{args.phase}"
        if target.exists():
            import shutil
            shutil.rmtree(target)
            print(f"Cleaned {target}")

    if args.phase is None or args.phase == 1:
        p1_results = phase1(client, args.reports_dir, args.model)
    else:
        p1_results = load_phase_results(1)

    if args.phase is not None and args.phase < 2:
        return

    if args.phase is None or args.phase == 2:
        p2_analyses = phase2(client, p1_results, args.model)
    else:
        p2_analyses = load_phase_results(2)

    if args.phase is not None and args.phase < 3:
        return

    if args.phase is None or args.phase == 3:
        p3_exemplars = phase3(client, p1_results, p2_analyses, args.model)
    else:
        p3_exemplars = load_phase_results(3)

    if args.phase is not None and args.phase < 4:
        return

    phase4(client, p2_analyses, p3_exemplars, args.model)

    print("\nPipeline complete.")
    print(f"  Style guide: {OUTPUT_DIR / 'phase4' / 'style_guide.md'}")


if __name__ == "__main__":
    main()
