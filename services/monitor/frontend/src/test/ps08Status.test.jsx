/**
 * PS-08 through the same presentation as every other PS (project owner, 2026-09-28): card, detail, badge, text,
 * counts and readiness all use the one resolver (app/psStatus.js).
 * Fixture: ./fixtures/ps08-sample.json, captured from the backend in memory (see its "_provenance"); no database.
 */
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RESULT_TEXT } from "../app/explain";
import SAMPLE from "./fixtures/ps08-sample.json";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

const copy = (v) => JSON.parse(JSON.stringify(v));
const STATUSES = ["PASS", "FAIL", "REVIEW", "N/A"];
const CASES = [["PASS", "PASS"], ["FAIL", "FAIL"], ["REVIEW", "REVIEW"], ["NA", "N/A"]];

/** Card, counts and readiness on /monitor/ps, then badge and text on the detail page. */
async function everywhere(monitor, detail) {
  mockFetch(() => jsonResponse(monitor));
  renderApp("/monitor/ps");
  const card = within(await screen.findByTestId("card-PS-08"));
  const out = {
    card: card.getByTestId("status").dataset.status,
    cardText: card.getByText(/ผ่านเกณฑ์|ไม่ผ่านเกณฑ์|ต้องตรวจสอบเพิ่มเติม|ไม่เข้าข่ายต้องตรวจ/).textContent,
    counts: Object.fromEntries(STATUSES.map((s) => [s, Number(screen.getByTestId(`count-${s}`).textContent)])),
    readiness: screen.getByTestId("readiness-value").textContent,
  };
  cleanup();
  mockFetch(() => jsonResponse(detail));
  renderApp("/monitor/ps/PS-08");
  const status = within(await screen.findByTestId("section-status"));
  out.detail = status.getByTestId("status").dataset.status;
  out.detailText = screen.getByTestId("section-status").textContent;
  cleanup();
  return out;
}

const statusesOf = (monitor) => monitor.results.map((r) => r.review?.status ?? r.status);   // what the backend sent

describe("the four outcomes of PS-08", () => {
  it.each(CASES)("%s: one status in card, detail, text and counts", async (key, expected) => {
    const { monitor, detail } = SAMPLE[key];
    expect(detail.status).toBe(expected);
    const out = await everywhere(monitor, detail);
    expect([out.card, out.detail]).toEqual([expected, expected]);
    expect(out.cardText).toBe(RESULT_TEXT[expected]);
    expect(out.detailText).toContain(RESULT_TEXT[expected]);
    const sent = statusesOf(monitor);
    expect(out.counts).toEqual(Object.fromEntries(STATUSES.map((s) => [s, sent.filter((x) => x === s).length])));
    expect(out.readiness).toBe(`${monitor.programmeReadiness.percentage}%`);   // the backend's value
  });

  it("N/A is counted as N/A only", async () => {
    const out = await everywhere(SAMPLE.NA.monitor, SAMPLE.NA.detail);
    const base = await everywhere(SAMPLE.PASS.monitor, SAMPLE.PASS.detail);
    expect(out.counts["N/A"] - base.counts["N/A"]).toBe(1);
    expect(out.counts.PASS - base.counts.PASS).toBe(-1);
    expect([out.counts.FAIL, out.counts.REVIEW]).toEqual([base.counts.FAIL, base.counts.REVIEW]);
  });
});

describe("a review sent for PS-08 is resolved like any other (test data: the PS-08 config has no review)", () => {
  const withReview = (result, status) => ({ ...result, review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status, reviewedAt: status ? "2026-09-28T01:00:00Z" : null } });

  it("engine REVIEW + review PASS -> PASS in card, detail and counts", async () => {
    const monitor = copy(SAMPLE.REVIEW.monitor);
    monitor.results = monitor.results.map((r) => (r.psCode === "PS-08" ? withReview(r, "PASS") : r));
    const detail = withReview(copy(SAMPLE.REVIEW.detail), "PASS");
    const out = await everywhere(monitor, detail);
    expect([out.card, out.detail, out.cardText]).toEqual(["PASS", "PASS", RESULT_TEXT.PASS]);
    expect(out.detailText).toContain("ระบบประเมินเบื้องต้น: REVIEW · ผู้ตรวจยืนยัน: PASS");
    expect(out.detailText).not.toContain(RESULT_TEXT.REVIEW);
    const base = await everywhere(SAMPLE.REVIEW.monitor, SAMPLE.REVIEW.detail);
    expect([out.counts.PASS - base.counts.PASS, out.counts.REVIEW - base.counts.REVIEW]).toEqual([1, -1]);
    expect(out.readiness).toBe(base.readiness);                                // not recomputed in the frontend
  });

  it("engine REVIEW without a review -> REVIEW everywhere", async () => {
    const out = await everywhere(SAMPLE.REVIEW.monitor, SAMPLE.REVIEW.detail);
    expect([out.card, out.detail]).toEqual(["REVIEW", "REVIEW"]);
    expect(out.detailText).not.toContain("ผู้ตรวจยืนยัน");
  });
});
