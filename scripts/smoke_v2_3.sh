#!/usr/bin/env bash
# Smoke-test the v2.3 equity-research pipeline against real models.
#
# Usage:
#   1. cp scripts/smoke_v2_3.env.example scripts/smoke_v2_3.env
#   2. Paste your OPENAI_API_KEY (and optionally EODHD_API_KEY) into it.
#   3. ./scripts/smoke_v2_3.sh
#
# Override any value on the CLI:
#   SMOKE_TICKER=AVGO ./scripts/smoke_v2_3.sh
#   SMOKE_OUTPUT="" ./scripts/smoke_v2_3.sh             # skip .docx render
#   ./scripts/smoke_v2_3.sh --language zh-TW            # pass-through flag

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/scripts/smoke_v2_3.env"
EXAMPLE_FILE="$ROOT/scripts/smoke_v2_3.env.example"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE."
  echo "Copy the template and fill in your keys:"
  echo "  cp $EXAMPLE_FILE $ENV_FILE"
  echo "  \$EDITOR $ENV_FILE"
  exit 2
fi

# Load every uncommented KEY=VALUE line from the env file into the shell.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${OPENAI_API_KEY:-}" || "${OPENAI_API_KEY}" == "sk-..." ]]; then
  echo "OPENAI_API_KEY is unset or still the placeholder in $ENV_FILE."
  exit 2
fi

if [[ -z "${OPENLIA_V2_3_CLARIFY_MODEL:-}" ]]; then
  echo "OPENLIA_V2_3_CLARIFY_MODEL is required. Set it in $ENV_FILE."
  exit 2
fi

TICKER="${SMOKE_TICKER:-NVDA}"
REPORT_TYPE="${SMOKE_REPORT_TYPE:-initiation}"
LANGUAGE="${SMOKE_LANGUAGE:-en}"
PROMPT="${SMOKE_PROMPT:-Write a 12-month initiation report on $TICKER for a PM. Include a DCF and competitive overview.}"
OUTPUT="${SMOKE_OUTPUT:-/tmp/v2_3_smoke.docx}"

echo "================================================================="
echo " v2.3 smoke run"
echo "   ticker      : $TICKER"
echo "   report_type : $REPORT_TYPE"
echo "   language    : $LANGUAGE"
echo "   prompt      : $PROMPT"
echo "   output      : ${OUTPUT:-<state only, no .docx>}"
echo "   clarify     : $OPENLIA_V2_3_CLARIFY_MODEL"
for slot in PLAN RESEARCH COMPUTE SYNTHESIZE WRITE VERIFY; do
  var="OPENLIA_V2_3_${slot}_MODEL"
  val="${!var:-<NoOp>}"
  printf "   %-11s : %s\n" "$(echo "$slot" | tr '[:upper:]' '[:lower:]')" "$val"
done
echo "================================================================="

CMD=(
  uv run python -m openlia.scripts.smoke_v2_3
  --ticker "$TICKER"
  --prompt "$PROMPT"
  --report-type "$REPORT_TYPE"
  --language "$LANGUAGE"
  --auto-default
)

if [[ -n "$OUTPUT" ]]; then
  CMD+=(--output "$OUTPUT")
fi

# Any extra args the user passed go through to the CLI.
exec "${CMD[@]}" "$@"
