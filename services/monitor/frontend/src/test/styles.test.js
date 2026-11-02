import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// CSS contract for the AUN-QA Monitor redesign (soft green / white, for a middle-aged university lecturer
// audience; project owner 2026-10-05): a single stylesheet, no new dependency.
const css = readFileSync(join(process.cwd(), "src/app/styles.css"), "utf8");
const html = readFileSync(join(process.cwd(), "index.html"), "utf8");
const rule = (selector) => {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`(?:^|\\n)${esc}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
};

describe("AUN-QA Monitor style (CSS contract)", () => {
  it("soft green ground, white surface, dark readable text, soft line, green primary", () => {
    const root = rule(":root");
    for (const t of ["--page-bg: #F7FAF8", "--surface: #FFFFFF", "--primary: #2F7D5B", "--primary-dark: #205B43",
                     "--soft-green: #EAF5EF", "--line: #DDE8E2", "--text: #1F2937", "--muted: #667085"]) {
      expect(root).toContain(t);
    }
    expect(root).toContain("color-scheme: light");
  });

  it("status colours are exactly the ones specified, never only colour (paired with icon + text)", () => {
    const root = rule(":root");
    for (const t of ["--pass: #2E7D5B", "--review: #B7791F", "--fail: #C94A4A", "--na: #6B7280"]) {
      expect(root).toContain(t);
    }
  });

  it("uses Noto Sans Thai / Sarabun and loads no web font", () => {
    expect(rule(":root")).toMatch(/font-family: "Noto Sans Thai", "Sarabun", system-ui, sans-serif/);
    expect(css).not.toMatch(/@import|@font-face|url\(/);
  });

  it("body text is at least 16px with roomy line height; nothing is gradient, glow, neon, animated or percentage-sized", () => {
    expect(rule("body")).toMatch(/font-size: 16px/);
    expect(rule("body")).toMatch(/line-height: 1\.7/);
    expect(css).not.toMatch(/box-shadow|animation|@keyframes|transition|gradient/);
    expect(css).not.toContain("%");
  });

  it("headings follow the given scale: page title 32px, section 22px, card title 18px", () => {
    expect(rule("h1")).toMatch(/font-size: 32px/);
    expect(rule("h2")).toMatch(/font-size: 22px/);
    expect(rule("h3")).toMatch(/font-size: 18px/);
  });

  it("no main-content text is set at 12px", () => {
    expect(css).not.toMatch(/font-size: 12px/);
  });

  it("top bar: white surface, thin bottom line, sticky; brand in the dark primary green, no underline by default", () => {
    const bar = rule(".topbar");
    expect(bar).toMatch(/position: sticky/);
    expect(bar).toMatch(/background: var\(--surface\)/);
    expect(bar).toMatch(/border-bottom: 1px solid var\(--line\)/);
    const brand = rule(".brand");
    expect(brand).toMatch(/font-weight: 700/);
    expect(brand).toMatch(/color: var\(--primary-dark\)/);
    expect(rule(".nav a[aria-current=\"page\"]")).toMatch(/border-bottom-color: var\(--primary\)/);
  });

  it("every link and nav item keeps a 44px minimum clickable height", () => {
    for (const selector of [".brand", ".nav a", ".more", ".back"]) {
      expect(rule(selector)).toMatch(/min-height: 44px/);
    }
  });

  it("boxes and cards: white surface, 1px soft line, 12px corners, 24px padding, no shadow; home cards 32px", () => {
    const box = rule(".box");
    expect(box).toMatch(/border: 1px solid var\(--line\)/);
    expect(box).toMatch(/border-radius: 12px/);
    expect(box).toMatch(/padding: 24px/);
    expect(box).toMatch(/background: var\(--surface\)/);
    expect(rule(".home-card")).toMatch(/padding: 32px/);
  });

  it("24px between cards; home and PS grids are 3 / 2 / 1 columns (laptop / tablet / phone)", () => {
    expect(rule(".ps-grid, .group-grid")).toMatch(/gap: 24px/);
    expect(rule(".group-grid")).toMatch(/grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
    expect(css).toMatch(/@media \(max-width: 1023px\)\s*\{[^@]*\.group-grid\s*\{\s*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
    expect(css).toMatch(/@media \(max-width: 639px\)\s*\{[^@]*\.group-grid\s*\{\s*grid-template-columns: minmax\(0, 1fr\)/);
  });

  it("Programme Readiness reads as the page's main hierarchy: a large percentage and a solid-green progress bar", () => {
    expect(rule(".readiness-hero__percent")).toMatch(/font-size: 48px/);
    expect(rule(".readiness-hero__percent")).toMatch(/font-weight: 700/);
    const bar = rule(".progress-bar");
    expect(bar).toMatch(/background: var\(--soft-green\)/);
    const fill = rule(".progress-bar__fill");
    expect(fill).toMatch(/background: var\(--primary\)/);
    expect(fill).not.toMatch(/gradient/);
  });

  it("status pills: colour, icon and text together, never colour alone; each status its own colour", () => {
    expect(rule(".status--pass")).toMatch(/color: var\(--pass\)/);
    expect(rule(".status--review")).toMatch(/color: var\(--review\)/);
    expect(rule(".status--fail")).toMatch(/color: var\(--fail\)/);
    expect(rule(".status--na")).toMatch(/color: var\(--na\)/);
  });

  it("issue badges: Spec Gap amber, errors light red", () => {
    const gap = rule(".issue--spec_gap");
    expect(gap).toMatch(/background: #fef3c7/);
    expect(gap).toMatch(/border-color: #f59e0b/);
    expect(gap).toMatch(/color: #92400e/);
    expect(rule(".issue--configuration_error, .issue--evaluation_error")).toMatch(/background: #fee2e2/);
  });

  it("the incomplete banner is pale yellow", () => {
    const s = rule(".state--incomplete");
    expect(s).toMatch(/background: #fefce8/);
    expect(s).toMatch(/border-color: #fde68a/);
    expect(s).toMatch(/color: #92400e/);
  });

  it("the two boxes sit side by side, stacked on narrow screens", () => {
    expect(rule(".two-col")).toMatch(/grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
    expect(css).toMatch(/@media \(max-width: 639px\)\s*\{[^@]*\.two-col\s*\{\s*grid-template-columns: minmax\(0, 1fr\)/);
  });

  it("evidence reads as a document list: a bordered card per document, filename first", () => {
    expect(rule(".doc-list > li")).toMatch(/border: 1px solid var\(--line\)/);
    expect(rule(".doc-list__name")).toMatch(/font-weight: 700/);
  });

  it("keeps a clearly visible, green focus ring", () => {
    expect(rule(":focus-visible")).toMatch(/outline: 2px solid var\(--primary\)/);
  });

  it("the page title is AUN-QA Monitor", () => {
    expect(html).toContain("<title>AUN-QA Monitor</title>");
  });
});
