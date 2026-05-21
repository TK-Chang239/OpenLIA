"""Copy-pastable conversion prompt builder.

Users with source documents in formats other than JSON/YAML (Markdown, .docx)
run this prompt in their own Claude/ChatGPT/Gemini and paste the result back.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.capability_manifest import load_manifest

_TEMPLATE = """
You are converting a free-form report framework into a structured OpenLIA template.

Engine version: {engine_version}

OUTPUT FORMAT: JSON or YAML, validating the following schema (paste either).

Required top-level keys: template_id, template_name, department, report_type,
engine_version_compat, sections.
Optional: composer_inputs, required_artifacts, verifier_severity_overrides.

Allowed composer_inputs[].type values: ticker, ticker_list, sector, string,
enum, int, bool, date_range.

Each section has: id (lowercase, underscore-separated), name, directive.
Optional per section: depends_on (list of section ids), trigger_when (free
text condition; only set when section is conditional).

DO NOT include any of these reserved keys: {reserved_keys}.
Engine v{engine_version} does not support extra LLM passes, review loops,
or custom subagents. If the source document mentions them, ignore those
parts when emitting the template.

For directives that contain conditional language (e.g., 'if applicable',
'where relevant', 'include only when material'), set the section's
trigger_when field with a plain-English condition.

Source document follows below. Convert it to a single JSON object or YAML
mapping. Return only the converted template, no surrounding prose.

--- SOURCE DOCUMENT ---
[Paste your source document here]
""".strip()


def build_conversion_prompt() -> str:
    m = load_manifest()
    reserved = sorted({k for u in m.unsupported for k in u.detect_in_template_keys})
    return _TEMPLATE.format(
        engine_version=m.engine_version,
        reserved_keys=", ".join(reserved) if reserved else "(none)",
    )
