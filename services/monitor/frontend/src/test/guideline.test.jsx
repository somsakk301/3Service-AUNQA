import { readFileSync } from "node:fs";
import { join } from "node:path";
import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PS_GUIDELINE } from "../app/psGuideline";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// The backend's byte-for-byte copy of the authoritative configuration (PS-Config-v1.json).
const CONFIG = JSON.parse(readFileSync(join(process.cwd(), "../backend/tests/fixtures/ps_config_v1.json"), "utf8"));
const EMPTY = { curriculum: null, overallStatus: null, dataCompleteness: "complete", results: [] };
const WAIT = "กำลังรอข้อมูล";
const UPLOAD = "รอผู้ใช้อัปโหลดข้อมูล";

const REQUIREMENTS = CONFIG.map((c) => c.requirement);
const NOT_ENOUGH = "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด";

describe("PS guideline (identifiers only: menu and card base list)", () => {
  it("is exactly the active configuration's PS codes, in order, and nothing else", () => {
    expect(PS_GUIDELINE.map((g) => g.psCode)).toEqual(CONFIG.filter((c) => c.active === true).map((c) => c.psCode));
    for (const g of PS_GUIDELINE) expect(Object.keys(g)).toEqual(["psCode"]); // no requirement, status or rule
  });

  it("the overview shows a card per PS while waiting, with its locked requirement and no status", async () => {
    mockFetch(() => jsonResponse(EMPTY));
    const { container } = renderApp("/monitor/ps");
    await screen.findByTestId("state-empty");
    const cards = [...container.querySelectorAll("[data-testid^='guide-']")];
    expect(cards.map((c) => c.getAttribute("data-testid"))).toEqual(PS_GUIDELINE.map((g) => `guide-${g.psCode}`));
    for (const g of PS_GUIDELINE) {
      const card = within(screen.getByTestId(`guide-${g.psCode}`));
      expect(card.getByRole("heading", { name: g.psCode })).toBeInTheDocument();
      expect(card.getByText(REQUIREMENTS[PS_GUIDELINE.indexOf(g)])).toBeInTheDocument();
      expect(card.getByText(UPLOAD)).toBeInTheDocument();
      expect(card.getAllByText(WAIT).length).toBeGreaterThan(0);
      expect(card.getByRole("link", { name: "ตรวจสอบรายละเอียด →" }).getAttribute("href")).toBe(`/monitor/ps/${g.psCode}`);
    }
    // nothing data-dependent is shown or invented while waiting
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    expect(container.querySelectorAll("[data-testid^='card-'], [data-testid^='panel-'], [data-testid^='count-']")).toHaveLength(0);
    for (const t of ["PASS", "FAIL", "REVIEW", "N/A", "%"]) expect(container.textContent).not.toContain(t);
  });

  it("guideline links keep ?curriculumCode=", async () => {
    mockFetch(() => jsonResponse(EMPTY));
    renderApp("/monitor/ps?curriculumCode=C-1");
    const card = within(await screen.findByTestId("guide-PS-03"));
    expect(card.getByRole("link", { name: "ตรวจสอบรายละเอียด →" }).getAttribute("href")).toBe("/monitor/ps/PS-03?curriculumCode=C-1");
  });

  it("also shows the cards when the API cannot be reached, with their locked requirement and no status", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(() => jsonResponse({ detail: "x" }, 503));
    const { container } = renderApp("/monitor/ps");
    await screen.findByTestId("state-error");
    expect(screen.getByTestId("guide-PS-01")).toHaveTextContent(REQUIREMENTS[0]);
    expect(screen.getByTestId("guide-PS-01")).not.toHaveTextContent(NOT_ENOUGH);
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    expect(container.textContent).not.toContain("FAIL");
  });

  it("once the backend has results, it only fills the PS the backend did not send", async () => {
    const body = monitorBody();
    body.results = [psResult("PS-01", "PASS")];
    mockFetch(() => jsonResponse(body));
    const { container } = renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(container.querySelectorAll("[data-testid^='card-']")).toHaveLength(1);
    expect([...container.querySelectorAll("[data-testid^='guide-']")].map((g) => g.dataset.testid))
      .toEqual(PS_GUIDELINE.slice(1).map((g) => `guide-${g.psCode}`));
    expect(screen.queryByTestId("state-empty")).not.toBeInTheDocument(); // not "waiting": the database has data
    expect(container.textContent).not.toContain(UPLOAD);
  });
});

describe("PS detail while waiting for data", () => {
  it("no result from the API: the locked requirement is shown, everything data-dependent waits", async () => {
    mockFetch(() => jsonResponse({ detail: "none" }, 404));
    const { container } = renderApp("/monitor/ps/PS-01");
    const req = within(await screen.findByTestId("section-requirement"));
    expect(req.getByText(REQUIREMENTS[0])).toBeInTheDocument();
    expect(req.queryByText(NOT_ENOUGH)).not.toBeInTheDocument();
    for (const id of ["status", "condition", "data", "verification", "missing", "evidence", "traceability"]) {
      expect(screen.getByTestId(`section-${id}`), id).toHaveTextContent(WAIT);
    }
    expect(screen.getByTestId("section-data")).toHaveTextContent(UPLOAD);
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    for (const t of ["PASS", "FAIL", "ไม่พบข้อมูลที่ใช้ตรวจสอบ", "ข้อมูลที่ใช้ตรวจสอบครบถ้วน"]) expect(container.textContent).not.toContain(t);
  });

  it("with a result, the requirement is the API's text, whatever the configuration copy says", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "PASS", { requirement: "requirement as sent by the API" })));
    const { container } = renderApp("/monitor/ps/PS-01");
    expect(within(await screen.findByTestId("section-requirement")).getByText("requirement as sent by the API")).toBeInTheDocument();
    expect(container.textContent).not.toContain(REQUIREMENTS[0]);
  });

  it("a PS outside the guideline says there is not enough to show its rule", async () => {
    mockFetch(() => jsonResponse({ detail: "none" }, 404));
    renderApp("/monitor/ps/PS-99");
    expect(within(await screen.findByTestId("section-requirement")).getByText("ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด")).toBeInTheDocument();
    expect(screen.getByTestId("section-data")).toHaveTextContent(WAIT);
  });
});
