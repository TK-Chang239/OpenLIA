import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it, expect } from "vitest";

const RETIRED = /#(7c9cff|94acff|5a9bff|0f1115|12151c|161a22)\b/i;

describe("report themes", () => {
  const dir = resolve(__dirname, "..");
  const files = readdirSync(dir).filter((f) => f.endsWith(".css"));
  for (const f of files) {
    it(`${f} contains no retired blue tokens`, () => {
      const text = readFileSync(resolve(dir, f), "utf-8");
      expect(text).not.toMatch(RETIRED);
    });
  }
});
