import { readFileSync } from "node:fs";
import { join } from "node:path";
import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PS_GUIDELINE } from "../app/psGuideline";
import { PS_TITLES, requirementText } from "../app/psTitles";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// The locked texts the product owner asked for (2026-09-25), word for word.
const ASKED = {
  "PS-01": "หลักสูตรต้องมีอาจารย์ผู้รับผิดชอบหลักสูตรอย่างน้อย 5 คน",
  "PS-02": "อาจารย์ผู้รับผิดชอบหลักสูตรต้องมีสถานะอาจารย์ประจำ",
  "PS-03": "อาจารย์ผู้รับผิดชอบหลักสูตรต้องไม่รับผิดชอบเกิน 1 หลักสูตร",
  "PS-04": "หลักสูตรต้องมีคำสั่งแต่งตั้งและระบุบทบาทการบริหารหลักสูตรอย่างชัดเจน",
  "PS-05": "อาจารย์ผู้รับผิดชอบหลักสูตรต้องมีคุณวุฒิสูงสุดอย่างน้อยระดับปริญญาโท",
  "PS-06": "คุณวุฒิของอาจารย์สัมพันธ์กับสาขาของหลักสูตร",
  "PS-07": "อาจารย์ผู้รับผิดชอบหรืออาจารย์ประจำหลักสูตรต้องมีผลงานวิชาการย้อนหลัง 5 ปี",
  "PS-08": "อาจารย์พิเศษต้องมีคุณวุฒิและประสบการณ์ที่เหมาะสม",
  "PS-09": "หลักสูตรต้องมีการปรับปรุงล่าสุดไม่เกิน 5 ปี",
};
// The backend's verbatim copy of the configuration (ps_requirements).
const CONFIG = JSON.parse(readFileSync(join(process.cwd(), "../backend/tests/fixtures/ps_config_v1.json"), "utf8"));
const CODES = Object.keys(ASKED);
const NOT_ENOUGH = "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด";
const EMPTY = { curriculum: null, overallStatus: null, dataCompleteness: "complete", results: [] };

describe("locked requirement texts", () => {
  it("are exactly the nine texts asked for", () => {
    expect(PS_TITLES).toEqual(ASKED);
  });

  it("match the configuration's requirement texts (fails if the configuration changes)", () => {
    expect(PS_TITLES).toEqual(Object.fromEntries(CONFIG.map((c) => [c.psCode, c.requirement])));
  });

  it("psGuideline.js still holds PS codes only", () => {
    for (const g of PS_GUIDELINE) expect(Object.keys(g)).toEqual(["psCode"]);
  });

  it("the API's requirement always wins; the locked text only fills a missing one", () => {
    expect(requirementText("PS-01", "requirement as sent by the API")).toBe("requirement as sent by the API");
    expect(requirementText("PS-01", null)).toBe(ASKED["PS-01"]);
    expect(requirementText("PS-01", "")).toBe(ASKED["PS-01"]);
    expect(requirementText("PS-10", null)).toBeNull(); // no locked text: nothing is made up
  });
});

describe("สิ่งที่เกณฑ์ต้องการ on the MONITOR cards", () => {
  const requirementOf = (card) => within(card).getByText("สิ่งที่เกณฑ์ต้องการ").nextElementSibling.textContent;

  it("A. every PS shows the API's requirement when the API sends it (and its status as sent)", async () => {
    const body = monitorBody({}, ["PASS", "FAIL", "REVIEW", "N/A", "PASS", "FAIL", "REVIEW", "N/A", "PASS"]);
    body.results.forEach((r) => { r.requirement = `API: ${r.psCode}`; });
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    for (const [i, code] of CODES.entries()) {
      const card = screen.getByTestId(`card-${code}`);
      expect(requirementOf(card)).toBe(`API: ${code}`);
      expect(within(card).getByTestId("status")).toHaveAttribute("data-status", body.results[i].status);
    }
  });

  it("B. no result for a PS: its requirement is still shown, with no status of its own", async () => {
    const body = monitorBody();
    body.results = body.results.filter((r) => !["PS-05", "PS-08"].includes(r.psCode));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    for (const code of ["PS-05", "PS-08"]) {
      const card = screen.getByTestId(`guide-${code}`);
      expect(requirementOf(card)).toBe(ASKED[code]);
      expect(within(card).getByText("ยังไม่มีผลการตรวจสอบ")).toBeInTheDocument();
      expect(within(card).queryByTestId("status")).not.toBeInTheDocument();
    }
    // readiness still counts the backend's results only
    const counted = ["PASS", "FAIL", "REVIEW", "N/A"].reduce((n, s) => n + Number(screen.getByTestId(`count-${s}`).textContent), 0);
    expect(counted).toBe(7);
  });

  it("C. a result without a requirement: the locked text, and the status stays the backend's", async () => {
    const body = monitorBody({}, ["FAIL"]);
    body.results[0].requirement = null;
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    const card = await screen.findByTestId("card-PS-01");
    expect(requirementOf(card)).toBe(ASKED["PS-01"]);
    expect(within(card).getByTestId("status")).toHaveAttribute("data-status", "FAIL");
  });

  it("D. the database is empty: all nine requirements, and no result made up", async () => {
    mockFetch(() => jsonResponse(EMPTY));
    const { container } = renderApp("/monitor/ps");
    await screen.findByTestId("state-empty");
    for (const code of CODES) expect(requirementOf(screen.getByTestId(`guide-${code}`))).toBe(ASKED[code]);
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    for (const s of ["PASS", "FAIL", "REVIEW", "N/A"]) expect(container.textContent).not.toContain(s);
  });

  it("a PS without a locked text and without a requirement says there is not enough data", async () => {
    const body = monitorBody();
    body.results.push(psResult("PS-10", "REVIEW", { requirement: null }));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    expect(requirementOf(await screen.findByTestId("card-PS-10"))).toBe(NOT_ENOUGH);
  });
});

describe("สิ่งที่เกณฑ์ต้องการ on the PS detail pages", () => {
  const requirement = () => within(screen.getByTestId("section-requirement")).getByRole("heading").nextElementSibling.textContent;

  it.each(CODES)("%s with a result: the API's requirement and status", async (code) => {
    mockFetch(() => jsonResponse(psResult(code, "REVIEW", { requirement: `API: ${code}` })));
    renderApp(`/monitor/ps/${code}`);
    await screen.findByTestId("section-requirement");
    expect(requirement()).toBe(`API: ${code}`);
    expect(within(screen.getByTestId("section-status")).getByTestId("status")).toHaveAttribute("data-status", "REVIEW");
  });

  it.each(CODES)("%s without a result: the locked requirement, waiting for data", async (code) => {
    mockFetch(() => jsonResponse({ detail: "none" }, 404));
    renderApp(`/monitor/ps/${code}`);
    await screen.findByTestId("section-requirement");
    expect(requirement()).toBe(ASKED[code]);
    expect(screen.getByTestId("section-check")).toHaveTextContent(`ข้อกำหนด “${ASKED[code]}”`);
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
  });

  it("a PS without a locked text and without a result says there is not enough data", async () => {
    mockFetch(() => jsonResponse({ detail: "none" }, 404));
    renderApp("/monitor/ps/PS-99");
    await screen.findByTestId("section-requirement");
    expect(requirement()).toBe(NOT_ENOUGH);
  });
});
