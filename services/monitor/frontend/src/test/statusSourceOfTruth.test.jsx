/**
 * One PS status for the whole frontend (project owner, 2026-09-27): every card, detail, badge, text, explanation and
 * count resolves a PS result through app/psStatus.js (a valid review.status from the backend, else `status`).
 * Programme Readiness stays the backend's value.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { countByStatus, resolveStatus, statusSources } from "../app/psStatus";
import { RESULT_TEXT } from "../app/explain";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

const review = (status) => ({ review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status, reviewedAt: status ? "2026-09-27T10:51:19Z" : null } });
const counts = () => Object.fromEntries(["PASS", "FAIL", "REVIEW", "N/A"].map((s) => [s, Number(screen.getByTestId(`count-${s}`).textContent)]));

// CASE 1-7: [engine status, review status or null, the status every presentation must use]
const CASES = [
  ["REVIEW", "PASS", "PASS"], ["REVIEW", "FAIL", "FAIL"], ["REVIEW", "REVIEW", "REVIEW"], ["REVIEW", null, "REVIEW"],
  ["PASS", null, "PASS"], ["FAIL", null, "FAIL"], ["N/A", null, "N/A"],
];

describe("the resolver", () => {
  it.each(CASES)("engine %s + review %s -> %s", (engine, reviewed, expected) => {
    const r = psResult("PS-03", engine, reviewed === null ? {} : review(reviewed));
    expect(resolveStatus(r)).toBe(expected);
    expect(statusSources(r)).toEqual(reviewed ? { engine, reviewer: reviewed } : null);
  });

  it("an unknown review value is not used", () => {
    expect(resolveStatus({ status: "REVIEW", review: { status: "MAYBE" } })).toBe("REVIEW");
    expect(resolveStatus({ status: "REVIEW", review: null })).toBe("REVIEW");
  });

  it("N/A counts as N/A only", () => {
    expect(countByStatus([psResult("PS-08", "N/A")])).toEqual({ PASS: 0, FAIL: 0, REVIEW: 0, "N/A": 1 });
  });

  it("persistedResult.status (the saved snapshot) never overrides a valid review.status", () => {
    const r = psResult("PS-03", "REVIEW", { ...review("PASS"), persistedResult: { status: "REVIEW", evaluatedAt: "2026-09-27T00:00:00Z" } });
    expect(resolveStatus(r)).toBe("PASS");
    expect(statusSources(r)).toEqual({ engine: "REVIEW", reviewer: "PASS" });
    expect(r.persistedResult.status).toBe("REVIEW"); // the snapshot itself is untouched
  });
});

describe("CASE 1-7 / 11: card, count, detail, badge and texts use the same status", () => {
  it.each(CASES)("engine %s + review %s -> %s everywhere", async (engine, reviewed, expected) => {
    const body = monitorBody();                                            // eight PASS + the case under test
    body.results = body.results.map((r) => (r.psCode === "PS-03" ? psResult("PS-03", engine, reviewed === null ? {} : review(reviewed)) : r));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    const card = within(await screen.findByTestId("card-PS-03"));
    expect(card.getByTestId("status")).toHaveAttribute("data-status", expected);
    expect(card.getByText(RESULT_TEXT[expected])).toBeInTheDocument();
    const want = { PASS: 8, FAIL: 0, REVIEW: 0, "N/A": 0 };
    want[expected] += 1;
    expect(counts()).toEqual(want);                                         // the summary counts what the cards show
    if (reviewed) expect(card.getByTestId("card-PS-03-sources")).toHaveTextContent(`ระบบประเมินเบื้องต้น: ${engine} · ผู้ตรวจยืนยัน: ${reviewed}`);
    cleanup();

    mockFetch(() => jsonResponse(psResult("PS-03", engine, reviewed === null ? {} : review(reviewed))));
    renderApp("/monitor/ps/PS-03");
    const status = within(await screen.findByTestId("section-status"));
    expect(status.getByTestId("status")).toHaveAttribute("data-status", expected);
    expect(status.getByText(RESULT_TEXT[expected])).toBeInTheDocument();
    if (expected !== "REVIEW") expect(screen.getByTestId("section-status").textContent).not.toContain(RESULT_TEXT.REVIEW);
  });
});

describe("CASE 8: the same rule for any PS", () => {
  it("a review of PS-06 is resolved the same way on its card and in the counts", async () => {
    const body = monitorBody();
    body.results = body.results.map((r) => (r.psCode === "PS-06" ? psResult("PS-06", "FAIL", review("PASS")) : r));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    expect(within(await screen.findByTestId("card-PS-06")).getByTestId("status")).toHaveAttribute("data-status", "PASS");
    expect(counts()).toEqual({ PASS: 9, FAIL: 0, REVIEW: 0, "N/A": 0 });
  });
});

describe("CASE 10: Programme Readiness is the backend's", () => {
  it("is shown as sent, whatever the counts are", async () => {
    const body = monitorBody();
    body.results = body.results.map((r) => (r.psCode === "PS-03" ? psResult("PS-03", "REVIEW", review("PASS")) : r));
    body.programmeReadiness = { percentage: 77.78, passCount: 7, totalPS: 9 };      // not recomputed to 9 PASS
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    expect(await screen.findByTestId("readiness-value")).toHaveTextContent("77.78%");
    expect(screen.getByTestId("readiness-count")).toHaveTextContent("7 จาก 9 เกณฑ์");
    expect(counts().PASS).toBe(9);
  });
});

describe("CASE 9: one resolver in the source", () => {
  const src = join(process.cwd(), "src");
  const files = readdirSync(src, { recursive: true }).map(String)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.startsWith("test"));
  const read = (f) => readFileSync(join(src, f), "utf8").replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, "");   // code only

  it.each(files)("%s reads no review status or engine status of a PS itself", (file) => {
    if (file === "app/psStatus.js") return;                                   // the resolver
    const code = read(file);
    expect(code).not.toMatch(/review\??\.status/);
    // a PS result is `result` / `r` throughout the source; `s.status` in SubjectResults is one lecturer's status
    // inside dataFound (not a PS status) and `err` / `remote` statuses are HTTP codes
    expect(code).not.toMatch(/\b(result|r)\.status\b/);
    expect(code).not.toMatch(/psCode\s*===?\s*["']PS-/);
  });
});
