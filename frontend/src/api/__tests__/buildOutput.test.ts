import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const distDir = resolve(HERE, "../../../dist");
const indexPath = join(distDir, "index.html");
const distExists = existsSync(indexPath);

describe.skipIf(!distExists)("frontend dist/ build output", () => {
  it("references hashed bundle and ships SPA mount point", () => {
    const html = readFileSync(indexPath, "utf8");
    expect(html).toMatch(/\/assets\/index-[A-Za-z0-9_-]+\.js/);
    expect(html).toContain('<div id="root">');
  });
});
