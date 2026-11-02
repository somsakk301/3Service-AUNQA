import { act, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RETRY_MS } from "../api/useRemote";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const EMPTY = { curriculum: null, overallStatus: null, dataCompleteness: "complete", results: [] };
/** Moves past one retry interval inside act(), so React finishes the resulting render and effects. */
const later = () => act(() => vi.advanceTimersByTimeAsync(RETRY_MS));

/** Answers each call with the next response; the last one repeats. */
function responses(...list) {
  let i = 0;
  return () => {
    const next = list[Math.min(i, list.length - 1)];
    i += 1;
    return typeof next === "function" ? next() : next;
  };
}

describe("the PS overview waits for data from the database", () => {
  it("re-checks every 10 seconds while the database has no data, then shows it", async () => {
    const fetchFn = mockFetch(responses(() => jsonResponse(EMPTY), () => jsonResponse(EMPTY), () => jsonResponse(monitorBody())));
    renderApp("/monitor/ps");
    const state = await screen.findByTestId("state-empty");
    expect(within(state).getByText("ยังไม่มีข้อมูล")).toBeInTheDocument();
    expect(state).toHaveTextContent("กำลังรอข้อมูลจากฐานข้อมูล");
    expect(state).toHaveTextContent("ตรวจสอบล่าสุด");
    expect(fetchFn).toHaveBeenCalledTimes(1);

    await later();
    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("state-empty")).toBeInTheDocument(); // still waiting, no loading flash

    await later();
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();
    expect(screen.queryByTestId("state-empty")).not.toBeInTheDocument();

    await later();
    expect(fetchFn).toHaveBeenCalledTimes(4); // data arrived: it keeps checking for newer results
  });

  it("retries after an error until the database answers", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchFn = mockFetch(responses(() => jsonResponse({ detail: "x" }, 503), () => jsonResponse(monitorBody())));
    const { container } = renderApp("/monitor/ps");
    const state = await screen.findByTestId("state-error");
    expect(within(state).getByText("ไม่สามารถโหลดข้อมูลการตรวจสอบได้")).toBeInTheDocument();
    expect(state).toHaveTextContent("ระบบจะลองใหม่อัตโนมัติ");
    expect(container.textContent).not.toContain("FAIL");

    await later();
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("keeps checking after the first result and shows the newest one (FAIL → PASS), no reload", async () => {
    const fetchFn = mockFetch(responses(() => jsonResponse(monitorBody({}, ["FAIL"])), () => jsonResponse(monitorBody({}, ["PASS"]))));
    renderApp("/monitor/ps");
    const card = await screen.findByTestId("card-PS-01");
    expect(within(card).getByTestId("status")).toHaveAttribute("data-status", "FAIL");
    await later();
    await waitFor(() => expect(within(screen.getByTestId("card-PS-01")).getByTestId("status")).toHaveAttribute("data-status", "PASS"));
    expect(screen.queryByTestId("state-loading")).not.toBeInTheDocument(); // no loading flash while refreshing
    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("last-checked")).toHaveTextContent("อัปเดตอัตโนมัติทุก 10 วินาที");
  });

  it("stops checking after leaving the page", async () => {
    const fetchFn = mockFetch(() => jsonResponse(EMPTY));
    const { unmount } = renderApp("/monitor/ps");
    await screen.findByTestId("state-empty");
    unmount();
    await later();
    await later();
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("only ever sends GET", async () => {
    const fetchFn = mockFetch(responses(() => jsonResponse(EMPTY), () => jsonResponse(monitorBody())));
    renderApp("/monitor/ps");
    await screen.findByTestId("state-empty");
    await later();
    await screen.findByTestId("card-PS-01");
    for (const [, init] of fetchFn.mock.calls) expect(init?.method).toBe("GET");
  });
});

describe("a PS detail page waits for its result", () => {
  it("re-checks while the backend has no result for the PS, then shows it", async () => {
    const fetchFn = mockFetch(responses(() => jsonResponse({ detail: "none" }, 404), () => jsonResponse(psResult("PS-01", "PASS"))));
    renderApp("/monitor/ps/PS-01");
    expect(await screen.findByTestId("state-empty")).toHaveTextContent("กำลังรอข้อมูลจากฐานข้อมูล");
    expect(document.querySelectorAll("[data-testid^='section-']")).toHaveLength(10); // sections stay, with empty states

    await later();
    expect(await screen.findByText("ผ่านเกณฑ์")).toBeInTheDocument();
    expect(screen.queryByTestId("state-empty")).not.toBeInTheDocument();
    await later();
    expect(fetchFn).toHaveBeenCalledTimes(3); // keeps checking for newer results
  });

  it("keeps checking after the result and shows the newest one", async () => {
    mockFetch(responses(() => jsonResponse(psResult("PS-01", "FAIL")), () => jsonResponse(psResult("PS-01", "PASS"))));
    renderApp("/monitor/ps/PS-01");
    expect(await screen.findByText("ไม่ผ่านเกณฑ์")).toBeInTheDocument();
    await later();
    expect(await screen.findByText("ผ่านเกณฑ์")).toBeInTheDocument();
  });

  it("retries after an error", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchFn = mockFetch(responses(() => jsonResponse({ detail: "x" }, 503), () => jsonResponse(psResult("PS-01", "PASS"))));
    renderApp("/monitor/ps/PS-01");
    expect(await screen.findByTestId("state-error")).toHaveTextContent("ระบบจะลองใหม่อัตโนมัติ");
    await later();
    expect(await screen.findByText("ผ่านเกณฑ์")).toBeInTheDocument();
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });
});

describe("several curricula (API 409)", () => {
  const MULTI = () => jsonResponse({ detail: "SPEC GAP: 2 curricula match …; request one with curriculumCode" }, 409);

  it("the overview says there are several curricula and how to choose one — not a load failure", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { container } = (mockFetch(MULTI), renderApp("/monitor/ps"));
    const state = await screen.findByTestId("state-multiple");
    expect(within(state).getByText("พบหลายหลักสูตรในฐานข้อมูล")).toBeInTheDocument();
    expect(state).toHaveTextContent("กรุณาระบุ curriculumCode ใน URL");
    expect(container.textContent).not.toContain("ไม่สามารถโหลดข้อมูลการตรวจสอบได้");
    expect(screen.queryByTestId("state-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    expect(screen.getByTestId("guide-PS-01")).toBeInTheDocument(); // the rules stay visible
  });

  it("the detail page says the same", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(MULTI);
    renderApp("/monitor/ps/PS-01");
    const state = await screen.findByTestId("state-multiple");
    expect(state).toHaveTextContent("พบหลายหลักสูตรในฐานข้อมูล");
    expect(state).toHaveTextContent("กรุณาระบุ curriculumCode ใน URL");
  });

  it("recovers by itself once a single curriculum remains", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(responses(MULTI, () => jsonResponse(monitorBody())));
    renderApp("/monitor/ps");
    await screen.findByTestId("state-multiple");
    await later();
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();
    expect(screen.queryByTestId("state-multiple")).not.toBeInTheDocument();
  });
});
