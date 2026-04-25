import { execSync } from "node:child_process";
import { describe, it, expect } from "vitest";

describe("frontend source", () => {
  it("contains no hex color literals outside tokens.css", () => {
    const out = execSync(
      "grep -rnE '#[0-9A-Fa-f]{3,8}\\b' src --include='*.tsx' --include='*.ts' | grep -v tokens.css | grep -v '&#' || true",
      { cwd: process.cwd(), encoding: "utf-8" },
    );
    expect(out.trim()).toBe("");
  });
});
