import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptMonitor } from "../api/adapter";
import { monitorBody } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

// TEST-ONLY: the programmeReadiness object as GET /api/monitor sends it (the backend computes it).
const readiness = (percentage, passCount, totalPS = 9) => ({ percentage, passCount, totalPS });

async function panel(body) {
  mockFetch(() => jsonResponse(body));
  renderApp("/monitor/ps");
  return within(await screen.findByTestId("panel-readiness"));
}

describe("Programme Readiness on /monitor/ps", () => {
  it.each([
    [readiness(77.78, 7), "77.78%", "7 จาก 9 เกณฑ์"],
    [readiness(100, 9), "100%", "9 จาก 9 เกณฑ์"],
    [readiness(66.67, 6), "66.67%", "6 จาก 9 เกณฑ์"],
    [readiness(0, 0), "0%", "0 จาก 9 เกณฑ์"],
  ])("TEST 13: shows the value the API sent (%o)", async (sent, percent, count) => {
    const box = await panel(monitorBody({ programmeReadiness: sent }));
    expect(box.getByTestId("readiness-value")).toHaveTextContent(percent);
    expect(box.getByTestId("readiness-count")).toHaveTextContent(count);
    expect(box.queryByTestId("readiness-none")).not.toBeInTheDocument();
    expect(box.queryByText("ระบบยังไม่ได้ส่งค่าความพร้อมมา จึงยังแสดงเป็นค่าว่าง")).not.toBeInTheDocument();
  });

  it("TEST 14: shows the API value even when the results would give another one", async () => {
    // nine PASS results, but the API says 44.44 / 4: the page shows what the API sent
    const box = await panel(monitorBody({ programmeReadiness: readiness(44.44, 4) }));
    expect(box.getByTestId("count-PASS")).toHaveTextContent("9");
    expect(box.getByTestId("readiness-value")).toHaveTextContent("44.44%");
    expect(box.getByTestId("readiness-count")).toHaveTextContent("4 จาก 9 เกณฑ์");
  });

  it("TEST 14: without programmeReadiness from the API nothing is derived from the results", async () => {
    const box = await panel(monitorBody());                  // nine PASS results, no programmeReadiness
    expect(box.getByTestId("readiness-none")).toHaveTextContent("—");
    expect(box.queryByTestId("readiness-value")).not.toBeInTheDocument();
    expect(box.getByText("ระบบยังไม่ได้ส่งค่าความพร้อมมา จึงยังแสดงเป็นค่าว่าง")).toBeInTheDocument();
  });

  it("the overall status stays independent of the readiness", async () => {
    const box = await panel(monitorBody({ programmeReadiness: readiness(77.78, 7) }));
    expect(box.getByTestId("overall-none")).toHaveTextContent("—");   // overallStatus is null, as the API sends
  });
});

describe("adapter: programmeReadiness", () => {
  it("passes the backend values through unchanged", () => {
    expect(adaptMonitor(monitorBody({ programmeReadiness: readiness(88.89, 8) })).programmeReadiness)
      .toEqual({ percentage: 88.89, passCount: 8, totalPS: 9 });
  });

  it.each([
    ["missing", undefined],
    ["null", null],
    ["percentage not a number", { percentage: "77.78", passCount: 7, totalPS: 9 }],
    ["totalPS missing", { percentage: 77.78, passCount: 7 }],
  ])("%s -> null (never recomputed)", (_, sent) => {
    expect(adaptMonitor(monitorBody({ programmeReadiness: sent })).programmeReadiness).toBeNull();
  });
});

describe("TEST 14: no readiness arithmetic in the frontend source", () => {
  const src = join(process.cwd(), "src");
  const files = readdirSync(src, { recursive: true })
    .map(String)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.startsWith("test"));

  it.each(files)("%s", (file) => {
    const text = readFileSync(join(src, file), "utf8");
    expect(text).not.toMatch(/passCount\s*[/*]|[/*]\s*(totalPS|passCount)|\/\s*9\b|\*\s*100\b/);
  });
});
