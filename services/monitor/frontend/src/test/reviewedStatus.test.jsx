/**
 * PS Detail after a user review (project owner 2026-09-27): "ผลการตรวจสอบ" shows the reviewer's choice the backend
 * sent (review.status) where there is one, else the engine's status; the engine's status stays visible next to it.
 * Nothing is decided here and no PS is named: the review comes from the backend for whichever PS has one.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

const withReview = (status) => ({ review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status, reviewedAt: status ? "2026-09-27T10:51:19Z" : null } });
const section = (id) => within(screen.getByTestId(`section-${id}`));

async function open(code, body) {
  mockFetch(() => jsonResponse(body));
  renderApp(`/monitor/ps/${code}`);
  await screen.findByTestId("section-traceability");
}

const shown = () => section("status").getByTestId("status").getAttribute("data-status");

describe("the result shown after a user review", () => {
  it("1: engine REVIEW + review PASS -> PASS, with both sources named and no 'ต้องตรวจสอบเพิ่มเติม'", async () => {
    await open("PS-03", psResult("PS-03", "REVIEW", withReview("PASS")));
    expect(shown()).toBe("PASS");
    expect(section("status").getByText("ผ่านเกณฑ์")).toBeInTheDocument();
    expect(screen.getByTestId("status-sources")).toHaveTextContent("ระบบประเมินเบื้องต้น: REVIEW · ผู้ตรวจยืนยัน: PASS");
    expect(screen.getByTestId("section-status").textContent).not.toContain("ต้องตรวจสอบเพิ่มเติม");
  });

  it.each([
    ["FAIL", "FAIL", "ไม่ผ่านเกณฑ์"],                // 2
    ["REVIEW", "REVIEW", "ต้องตรวจสอบเพิ่มเติม"],      // 3
  ])("engine REVIEW + review %s -> %s", async (review, expected, text) => {
    await open("PS-03", psResult("PS-03", "REVIEW", withReview(review)));
    expect(shown()).toBe(expected);
    expect(section("status").getByText(text)).toBeInTheDocument();
    expect(screen.getByTestId("status-sources")).toHaveTextContent(`ระบบประเมินเบื้องต้น: REVIEW · ผู้ตรวจยืนยัน: ${review}`);
  });

  it("4: engine REVIEW, the review offered but nothing saved -> REVIEW, no second source line", async () => {
    await open("PS-03", psResult("PS-03", "REVIEW", withReview(null)));
    expect(shown()).toBe("REVIEW");
    expect(section("status").getByText("ต้องตรวจสอบเพิ่มเติม")).toBeInTheDocument();
    expect(screen.queryByTestId("status-sources")).not.toBeInTheDocument();
  });

  it.each([["PS-01", "PASS"], ["PS-06", "FAIL"], ["PS-08", "N/A"], ["PS-02", "REVIEW"]])(
    "6: %s without a review shows the engine's %s as before", async (code, status) => {
      await open(code, psResult(code, status));
      expect(shown()).toBe(status);
      expect(screen.queryByTestId("status-sources")).not.toBeInTheDocument();
    });

  it("follows the backend for any PS with a review, not a PS code", async () => {
    await open("PS-07", psResult("PS-07", "FAIL", withReview("PASS")));
    expect(shown()).toBe("PASS");
  });
});

describe("the PS card on /monitor/ps follows the same rule", () => {
  async function overview(review) {
    const body = monitorBody();
    body.results = body.results.map((r) => (r.psCode === "PS-03" ? psResult("PS-03", "REVIEW", review ? withReview(review) : {}) : r));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    return within(await screen.findByTestId("card-PS-03"));
  }

  it.each([
    ["PASS", "PASS", "ผ่านเกณฑ์"],                  // card 1
    ["FAIL", "FAIL", "ไม่ผ่านเกณฑ์"],               // card 2
    ["REVIEW", "REVIEW", "ต้องตรวจสอบเพิ่มเติม"],     // card 3
  ])("engine REVIEW + review %s -> card shows %s", async (review, expected, text) => {
    const card = await overview(review);
    expect(card.getByTestId("status")).toHaveAttribute("data-status", expected);
    expect(card.getByText(text)).toBeInTheDocument();
    expect(card.getByTestId("card-PS-03-sources")).toHaveTextContent(`ระบบประเมินเบื้องต้น: REVIEW · ผู้ตรวจยืนยัน: ${review}`);
    if (expected === "PASS") expect(card.queryByText("ต้องตรวจสอบเพิ่มเติม")).not.toBeInTheDocument();
  });

  it("card 4: without a review the card shows the engine's status, and other cards are as before", async () => {
    const card = await overview(null);
    expect(card.getByTestId("status")).toHaveAttribute("data-status", "REVIEW");
    expect(card.queryByTestId("card-PS-03-sources")).not.toBeInTheDocument();
    const other = within(screen.getByTestId("card-PS-01"));
    expect(other.getByTestId("status")).toHaveAttribute("data-status", "PASS");
    expect(other.queryByTestId("card-PS-01-sources")).not.toBeInTheDocument();
  });

  it("a review saved for any PS is shown on its card (no PS code in the logic)", async () => {
    const body = monitorBody();
    body.results = body.results.map((r) => (r.psCode === "PS-06" ? psResult("PS-06", "FAIL", withReview("PASS")) : r));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    const card = within(await screen.findByTestId("card-PS-06"));
    expect(card.getByTestId("status")).toHaveAttribute("data-status", "PASS");
  });
});

describe("5: Programme Readiness is the backend's value", () => {
  it("is shown as sent even when it disagrees with the reviews on the page", async () => {
    const body = monitorBody();
    body.results = body.results.map((r) => (r.psCode === "PS-03" ? psResult("PS-03", "REVIEW", withReview("PASS")) : r));
    body.programmeReadiness = { percentage: 12.34, passCount: 1, totalPS: 9 };
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    expect(await screen.findByText(/12\.34/)).toBeInTheDocument();
  });
});

describe("7: no PS rule in the frontend source", () => {
  const src = join(process.cwd(), "src");
  const files = readdirSync(src, { recursive: true }).map(String)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.startsWith("test"));
  const PS_CODE_FILES = ["app/psGuideline.js", "app/psTitles.js"];   // approved PS-code lists (SCOPE.md)
  it.each(files)("%s", (file) => {
    const text = readFileSync(join(src, file), "utf8");
    if (!PS_CODE_FILES.includes(file)) expect(text).not.toMatch(/PS-03/);
  });
});
