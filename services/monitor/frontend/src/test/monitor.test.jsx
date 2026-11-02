import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cardList } from "../pages/Monitor/cardList";
import { ALL_CODES, monitorBody, psResult } from "./fixtures";
// TEST-ONLY: GET /api/monitor as produced by the real backend engine (see humanreadable.test.jsx).
import sample from "./fixtures/backend-sample.json";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

const loaded = () => screen.findByTestId("panel-readiness");

describe("/monitor/ps", () => {
  it("shows the header, curriculum, readiness and nine PS cards", async () => {
    mockFetch(() => jsonResponse(monitorBody({}, ["PASS", "FAIL", "REVIEW", "N/A"])));
    renderApp("/monitor/ps");
    expect(screen.getByRole("heading", { level: 1, name: "AUNQA" })).toBeInTheDocument();
    expect(within(document.querySelector(".page-head")).getByText("Programme Standards")).toBeInTheDocument();
    expect(screen.getByText("เกณฑ์มาตรฐานที่ใช้ตรวจสอบข้อมูลของหลักสูตร")).toBeInTheDocument();
    await loaded();
    for (const c of ALL_CODES) expect(screen.getByTestId(`card-${c}`)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ภาพรวมเกณฑ์ PS" })).toBeInTheDocument();
  });

  it("curriculum box shows only the fields the backend sent", async () => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/monitor/ps");
    const box = within(await screen.findByTestId("panel-curriculum"));
    expect(box.getByText("ชื่อหลักสูตร").nextSibling).toHaveTextContent("Name-1");
    expect(box.getByText("รหัสหลักสูตร").nextSibling).toHaveTextContent("C-1");
    expect(box.getByText("เวอร์ชัน").nextSibling).toHaveTextContent("v1");
    expect(box.queryByText("ปีหลักสูตร")).not.toBeInTheDocument(); // null
    expect(box.queryByText("สถานะ")).not.toBeInTheDocument();      // null
  });

  it("counts statuses from backend results; readiness and overall are —", async () => {
    mockFetch(() => jsonResponse(monitorBody({}, ["PASS", "FAIL", "REVIEW", "N/A"])));
    renderApp("/monitor/ps");
    const box = within(await loaded());
    expect(box.getByText("ความพร้อมของหลักสูตร")).toBeInTheDocument();
    expect(box.getByTestId("readiness-none")).toHaveTextContent("—");
    expect(box.getByTestId("overall-none")).toHaveTextContent("—");
    expect(box.getByText("ระบบยังไม่ได้ส่งค่าความพร้อมมา จึงยังแสดงเป็นค่าว่าง")).toBeInTheDocument();
    expect(box.getByTestId("count-PASS")).toHaveTextContent("6");
    expect(box.getByTestId("count-FAIL")).toHaveTextContent("1");
    expect(box.getByTestId("count-REVIEW")).toHaveTextContent("1");
    expect(box.getByTestId("count-N/A")).toHaveTextContent("1");
  });

  it("shows the overall status when the backend supplies it; readiness stays —", async () => {
    mockFetch(() => jsonResponse(monitorBody({ overallStatus: "REVIEW" })));
    renderApp("/monitor/ps");
    const box = within(await loaded());
    expect(box.queryByTestId("overall-none")).not.toBeInTheDocument();
    expect(box.getByText("ผลรวม").parentElement.querySelector("[data-testid='status']")).toHaveAttribute("data-status", "REVIEW");
    expect(box.getByTestId("readiness-none")).toHaveTextContent("—");
    expect(box.queryByText("ระบบยังไม่ได้ส่งค่าความพร้อมมา จึงยังแสดงเป็นค่าว่าง")).not.toBeInTheDocument();
  });

  it("cards: PS-01…PS-09 first in order, each from the backend when it has a result; other PS the backend sends follow", async () => {
    const body = monitorBody();
    body.results = body.results.filter((r) => r.psCode !== "PS-05");
    body.results.push(psResult("PS-10", "REVIEW"));
    body.results.reverse();
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-10");
    expect(screen.queryByTestId("card-PS-05")).not.toBeInTheDocument(); // no result: never shown as a result card
    const order = [...document.querySelectorAll("[data-testid^='card-'], [data-testid^='guide-']")].map((e) => e.getAttribute("data-testid"));
    expect(order).toEqual([...ALL_CODES.map((c) => (c === "PS-05" ? "guide-PS-05" : `card-${c}`)), "card-PS-10"]);
  });

  it("a card shows why nothing was decided when the backend reports an issue", async () => {
    const body = monitorBody({}, ["REVIEW", "REVIEW", "REVIEW", "REVIEW"]);
    body.results[0].issue = "configuration_error";
    body.results[1].issue = "spec_gap";
    body.results[2].issue = "evaluation_error";
    body.results[3].issue = "something-else";
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    expect(within(await screen.findByTestId("card-PS-01")).getByTestId("issue")).toHaveTextContent("Configuration Error");
    expect(within(screen.getByTestId("card-PS-02")).getByTestId("issue")).toHaveTextContent("Spec Gap");
    expect(within(screen.getByTestId("card-PS-03")).getByTestId("issue")).toHaveTextContent("Evaluation Error");
    expect(within(screen.getByTestId("card-PS-04")).queryByTestId("issue")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("card-PS-05")).queryByTestId("issue")).not.toBeInTheDocument();
  });
});

describe("UI states", () => {
  it("กำลังโหลดข้อมูล…", () => {
    mockFetch(() => new Promise(() => {}));
    renderApp("/monitor/ps");
    expect(screen.getByText("กำลังโหลดข้อมูล…")).toBeInTheDocument();
  });

  it("ยังไม่มีข้อมูล when the backend returns nothing", async () => {
    mockFetch(() => jsonResponse({ curriculum: null, overallStatus: null, dataCompleteness: "complete", results: [] }));
    renderApp("/monitor/ps");
    expect(await screen.findByText("ยังไม่มีข้อมูล")).toBeInTheDocument();
  });

  it("ข้อมูลยังไม่ครบถ้วน is shown only when the backend says so", async () => {
    mockFetch(() => jsonResponse(monitorBody({ dataCompleteness: "incomplete" })));
    renderApp("/monitor/ps");
    expect(await screen.findByTestId("state-incomplete")).toHaveTextContent("ข้อมูลยังไม่ครบถ้วน");
    expect(screen.getByTestId("card-PS-01")).toBeInTheDocument();
  });

  it("does not infer incomplete data from raw contents", async () => {
    const body = monitorBody();
    body.results[0].missingInformation = ["gap"]; // backend flag still says complete
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    await loaded();
    expect(screen.queryByTestId("state-incomplete")).not.toBeInTheDocument();
  });

  it.each([
    ["network failure", () => Promise.reject(new TypeError("offline"))],
    ["HTTP 503", () => jsonResponse({ detail: "x" }, 503)],
  ])("%s -> ไม่สามารถโหลดข้อมูลการตรวจสอบได้, never FAIL", async (_n, handler) => {
    mockFetch(handler);
    const { container } = renderApp("/monitor/ps");
    expect(await screen.findByText("ไม่สามารถโหลดข้อมูลการตรวจสอบได้")).toBeInTheDocument();
    expect(container.textContent).not.toContain("FAIL");
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    expect(document.querySelectorAll("[data-testid^='panel-']")).toHaveLength(0);
  });
});

describe("read-only", () => {
  it("only issues GET requests", async () => {
    const fetchFn = mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/monitor/ps");
    await loaded();
    for (const [, init] of fetchFn.mock.calls) expect(init?.method).toBe("GET");
  });

  it("renders no form controls for editing data; its one button saves the monitoring result (SET 6)", async () => {
    mockFetch(() => jsonResponse(monitorBody()));
    const { container } = renderApp("/monitor/ps");
    await loaded();
    expect(container.querySelectorAll("form, input, textarea, select")).toHaveLength(0);
    expect([...container.querySelectorAll("button")].map((b) => b.dataset.testid)).toEqual(["persist-save"]);
  });

  it("passes the optional curriculumCode selector to the backend", async () => {
    const fetchFn = mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/monitor/ps?curriculumCode=C-1");
    await waitFor(() => expect(fetchFn).toHaveBeenCalled());
    expect(String(fetchFn.mock.calls[0][0])).toContain("curriculumCode=C-1");
  });

  it("loads its data once per visit", async () => {
    const fetchFn = mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/monitor/ps");
    await loaded();
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
});

describe("PS-01…PS-09 always have a card", () => {
  const cardsOrder = () => [...document.querySelectorAll("[data-testid^='card-'], [data-testid^='guide-']")].map((e) => e.getAttribute("data-testid"));

  it("API has all nine: nine result cards, statuses exactly as sent", async () => {
    mockFetch(() => jsonResponse(monitorBody({}, ["PASS", "FAIL", "REVIEW", "N/A", "PASS", "FAIL", "REVIEW", "N/A", "PASS"])));
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(cardsOrder()).toEqual(ALL_CODES.map((c) => `card-${c}`));
    const statuses = ALL_CODES.map((c) => within(screen.getByTestId(`card-${c}`)).getByTestId("status").dataset.status);
    expect(statuses).toEqual(["PASS", "FAIL", "REVIEW", "N/A", "PASS", "FAIL", "REVIEW", "N/A", "PASS"]);
  });

  it("API misses some PS: their cards stay, with an empty state and no invented result", async () => {
    const body = monitorBody({}, ["PASS", "FAIL", "REVIEW", "N/A", "PASS", "FAIL", "REVIEW", "N/A", "PASS"]);
    body.results = body.results.filter((r) => !["PS-05", "PS-08"].includes(r.psCode));
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(cardsOrder()).toEqual(ALL_CODES.map((c) => (["PS-05", "PS-08"].includes(c) ? `guide-${c}` : `card-${c}`)));
    for (const code of ["PS-05", "PS-08"]) {
      const card = screen.getByTestId(`guide-${code}`);
      expect(within(card).getByRole("heading", { name: code })).toBeInTheDocument();
      expect(within(card).getByText("—")).toBeInTheDocument();
      expect(within(card).getByText("ยังไม่มีผลการตรวจสอบ")).toBeInTheDocument();
      expect(within(card).getByText("ยังไม่มีข้อมูลจากระบบสำหรับเกณฑ์นี้")).toBeInTheDocument();
      expect(within(card).getByRole("link", { name: "ตรวจสอบรายละเอียด →" }).getAttribute("href")).toBe(`/monitor/ps/${code}`);
      expect(within(card).queryByTestId("status")).not.toBeInTheDocument();
      for (const s of ["PASS", "FAIL", "REVIEW", "N/A", "รอผู้ใช้อัปโหลดข้อมูล"]) expect(card.textContent).not.toContain(s);
    }
    // the backend's results are untouched, and nothing is counted for the missing PS
    expect(within(screen.getByTestId("card-PS-04")).getByTestId("status")).toHaveAttribute("data-status", "N/A");
    expect(["PASS", "FAIL", "REVIEW", "N/A"].map((s) => Number(screen.getByTestId(`count-${s}`).textContent))).toEqual([2, 2, 2, 1]);
  });

  it("a missing PS still shows its locked requirement (no status of its own)", async () => {
    const body = monitorBody();
    body.results = body.results.filter((r) => r.psCode !== "PS-09");
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    const card = await screen.findByTestId("guide-PS-09");
    expect(card).toHaveTextContent("หลักสูตรต้องมีการปรับปรุงล่าสุดไม่เกิน 5 ปี");
    expect(card).not.toHaveTextContent("ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด");
    expect(within(card).queryByTestId("status")).not.toBeInTheDocument();
  });

  it("API empty: all nine cards stay, waiting for data", async () => {
    mockFetch(() => jsonResponse({ curriculum: null, overallStatus: null, dataCompleteness: "complete", results: [] }));
    renderApp("/monitor/ps");
    await screen.findByTestId("state-empty");
    expect(cardsOrder()).toEqual(ALL_CODES.map((c) => `guide-${c}`));
  });

  it("with real backend output missing one PS, every other card matches the backend exactly", async () => {
    const body = structuredClone(sample);
    body.results = body.results.filter((r) => r.psCode !== "PS-03");
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(screen.getByTestId("guide-PS-03")).toBeInTheDocument();
    for (const r of body.results) {
      const card = screen.getByTestId(`card-${r.psCode}`);
      expect(within(card).getByTestId("status")).toHaveAttribute("data-status", r.status);
      expect(card).toHaveTextContent(r.requirement);
      if (r.issue) expect(within(card).getByTestId("issue")).toBeInTheDocument();
      else expect(within(card).queryByTestId("issue")).not.toBeInTheDocument();
    }
  });
});

describe("cardList (display order only)", () => {
  const guideline = [{ psCode: "A" }, { psCode: "B" }];

  it("uses the backend's result objects as they are; a gap is only a PS code without a result", () => {
    const a = { psCode: "A", status: "WHATEVER", requirement: "from backend" };
    const x = { psCode: "X", status: "FAIL" };
    expect(cardList([x, a], guideline)).toEqual([
      { psCode: "A", result: a },
      { psCode: "B", result: null },
      { psCode: "X", result: x },
    ]);
    expect(cardList([x, a], guideline)[0].result).toBe(a); // same object: nothing re-derived
  });

  it("never drops a backend result, even a repeated code", () => {
    const a1 = { psCode: "A" };
    const a2 = { psCode: "A" };
    expect(cardList([a1, a2], guideline).map((c) => c.result)).toEqual([a1, null, a2]);
  });
});
