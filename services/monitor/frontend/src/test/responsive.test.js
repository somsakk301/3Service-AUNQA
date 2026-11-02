import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "src/app/styles.css"), "utf8");
const columns = (block) => (block.match(/grid-template-columns:\s*([^;]+);/)?.[1] ?? "").trim();

describe("responsive PS grid (CSS contract)", () => {
  it("desktop is 3 columns", () => {
    expect(columns(css.match(/\.ps-grid\s*\{[^}]*\}/)[0])).toMatch(/repeat\(3,/);
  });
  it("tablet (<=1023px) is 2 columns", () => {
    const m = css.match(/@media \(max-width: 1023px\)\s*\{\s*\.ps-grid\s*\{([^}]*)\}/);
    expect(columns(m[1])).toMatch(/repeat\(2,/);
  });
  it("mobile (<=639px, includes 390px) is 1 column", () => {
    const m = css.match(/@media \(max-width: 639px\)\s*\{\s*\.ps-grid\s*\{([^}]*)\}/);
    expect(columns(m[1])).toMatch(/^minmax\(0, 1fr\)$/);
  });
});
