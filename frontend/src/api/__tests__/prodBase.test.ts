import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Walk a directory and yield every regular file path matching `extensions`.
function walk(root: string, extensions: ReadonlyArray<string>): string[] {
  const out: string[] = [];
  const stack: string[] = [root];
  while (stack.length > 0) {
    const dir = stack.pop()!;
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      const info = statSync(path);
      if (info.isDirectory()) {
        if (entry === "__tests__" || entry === "node_modules") continue;
        stack.push(path);
        continue;
      }
      // Skip test files — they intentionally use absolute mock URLs.
      if (entry.endsWith(".test.ts") || entry.endsWith(".test.tsx")) continue;
      if (extensions.some((ext) => entry.endsWith(ext))) {
        out.push(path);
      }
    }
  }
  return out;
}

const HERE = dirname(fileURLToPath(import.meta.url));

describe("frontend production base URL", () => {
  it("never embeds an absolute https?://host/api literal", () => {
    const apiDir = resolve(HERE, "..");
    const files = walk(apiDir, [".ts", ".tsx"]);
    expect(files.length).toBeGreaterThan(0);

    // Match any string literal of the form "http(s)://<host>/api...".
    const offenders: { file: string; match: string }[] = [];
    const pattern = /["'`]https?:\/\/[^"'`/\s]+\/api[^"'`]*["'`]/g;
    for (const file of files) {
      const text = readFileSync(file, "utf8");
      // Strip block comments — JSDoc snippets reference example URLs.
      const stripped = text.replace(/\/\*[\s\S]*?\*\//g, "");
      const matches = stripped.match(pattern);
      if (matches) {
        for (const m of matches) {
          offenders.push({ file, match: m });
        }
      }
    }

    expect(offenders, JSON.stringify(offenders, null, 2)).toEqual([]);
  });
});
