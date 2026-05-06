import type { SourceKind } from "./SourceChip";

export interface ToolCallSourceLabel {
  label: string;
  kind: SourceKind;
}

/** Heuristic mapping from a tool call's `(name, argsPreview, structured)`
 *  triple → a friendly user-facing label + icon kind for `SourceChip`.
 *
 *  This is intentionally pattern-based rather than typed against every
 *  backend tool registration: backends evolve their tool surface and we
 *  don't want every new tool name to require a frontend change. The
 *  fallback always renders a sensible, technical-but-not-cryptic label. */
export function mapToolCallToSource(
  toolName: string,
  argsPreview: string,
  structured: Record<string, unknown> | null | undefined,
): ToolCallSourceLabel {
  const name = toolName.toLowerCase();
  const args = argsPreview ?? "";
  const struct = structured ?? {};

  // 1. Read-a-file family. Filename usually appears in argsPreview as a
  //    quoted path or `filename=foo.pdf`. Try structured fields first, fall
  //    back to a parenthesized argsPreview.
  if (
    name.includes("read_repo") ||
    name.includes("read_file") ||
    name === "open_file"
  ) {
    const filename = pickFilename(struct, args);
    return { label: filename, kind: kindFromFilename(filename) };
  }

  // 2. News.
  if (name.includes("news") || name.includes("article")) {
    const headline = pickString(struct, ["headline", "title"]) ?? "News article";
    return { label: headline, kind: "news" };
  }

  // 3. Web search / lookup.
  if (name.includes("search") || name.includes("lookup") || name.includes("query")) {
    const q = pickString(struct, ["query", "q"]) ?? args;
    return { label: q ? `Search: ${truncate(q, 40)}` : "Search", kind: "search" };
  }

  // 4. Market quotes / prices / fundamentals.
  if (name.includes("quote") || name.includes("price") || name.includes("fundamental")) {
    const ticker = pickString(struct, ["ticker", "symbol"]) ?? args;
    return {
      label: ticker ? `Market data — ${ticker}` : "Market data",
      kind: "data",
    };
  }

  // 5. SEC / filings.
  if (name.includes("filing") || name.includes("sec") || name.includes("10q") || name.includes("10k")) {
    const filing = pickString(struct, ["filing", "form_type", "accession"]) ?? args;
    return { label: filing || "SEC filing", kind: "pdf" };
  }

  // 6. Repository / list.
  if (name.includes("list_repo") || name.includes("list_chat") || name.includes("list_session")) {
    return { label: "Repository", kind: "table" };
  }

  // 7. Earnings transcript.
  if (name.includes("transcript") || name.includes("earnings_call")) {
    return { label: "Earnings call transcript", kind: "doc" };
  }

  // 8. Consensus / analysts.
  if (name.includes("consensus") || name.includes("analyst")) {
    const n = pickNumber(struct, ["count", "n_analysts"]);
    return {
      label: n ? `Consensus — ${n} analysts` : "Analyst consensus",
      kind: "data",
    };
  }

  // 9. Suggest-redirect — already rendered as RedirectCard, so the chip
  //    here is supplemental context. Keep it minimal.
  if (name === "suggest_redirect") {
    return { label: "Department redirect", kind: "search" };
  }

  // 10. Fallback: render `tool_name(arg)` truncated.
  const fallback = args ? `${toolName}(${truncate(args, 24)})` : toolName;
  return { label: fallback, kind: "search" };
}

function pickString(
  struct: Record<string, unknown>,
  keys: string[],
): string | null {
  for (const k of keys) {
    const v = struct[k];
    if (typeof v === "string" && v.trim().length > 0) return v.trim();
  }
  return null;
}

function pickNumber(
  struct: Record<string, unknown>,
  keys: string[],
): number | null {
  for (const k of keys) {
    const v = struct[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

function pickFilename(
  struct: Record<string, unknown>,
  argsPreview: string,
): string {
  const fromStruct = pickString(struct, ["filename", "path", "name", "title"]);
  if (fromStruct) return fromStruct;
  // Try to extract `filename=foo.pdf` or `"foo.pdf"` or just `foo.pdf` from the args.
  const named = /(?:filename|path|name)\s*[=:]\s*["']?([^"'\s,]+)["']?/.exec(argsPreview);
  if (named) return named[1];
  const quoted = /["']([^"']+\.[a-zA-Z0-9]{1,6})["']/.exec(argsPreview);
  if (quoted) return quoted[1];
  const bare = /([\w./-]+\.[a-zA-Z0-9]{1,6})\b/.exec(argsPreview);
  if (bare) return bare[1];
  return "Document";
}

function kindFromFilename(filename: string): SourceKind {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "csv" || ext === "tsv") return "csv";
  if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext)) return "image";
  if (["py", "js", "ts", "tsx", "json", "yaml", "yml", "toml"].includes(ext)) return "code";
  return "doc";
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1).trimEnd() + "…";
}
