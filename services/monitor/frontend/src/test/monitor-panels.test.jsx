import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

/**
 * Nine results with known values:
 * evidence items: 2 (PS-01) + 1 (PS-05) = 3 · verified true: 2 · verified false: 1
 * incomplete: 2 · missing information: 4 (PS-01) + 1 (PS-05) = 5
 */
function countedBody() {
  const body = monitorBody({}, ["PASS", "FAIL", "REVIEW", "PASS", "PASS", "REVIEW", "PASS", "N/A", "PASS"]);
  const r = body.results;
  r[0].evidence = [{ label: "e1", reference: null }, { label: "e2", reference: null }];
  r[4].evidence = [{ label: "e3", reference: null }];
  r[0].verification = { found: 3, verified: true, approved: true };
  r[3].verification = { found: 3, verified: false, approved: false };
  r[4].verification = { found: 3, verified: true, approved: null };
  r[1].dataCompleteness = "incomplete";
  r[2].dataCompleteness = "incomplete";
  r[0].missingInformation = ["ขาดข้อมูลส่วนที่ 1", "ขาดข้อมูลส่วนที่ 2", "ขาดข้อมูลส่วนที่ 3", "ขาดข้อมูลส่วนที่ 4"];
  r[4].missingInformation = ["ขาดข้อมูลส่วนที่ ก"];
  return body;
}

async function openMonitor(body) {
  mockFetch(() => jsonResponse(body));
  const view = renderApp("/monitor/ps");
  await screen.findByTestId("panel-readiness");
  return view;
}

const value = (box, label) => within(box).getByText(label).nextSibling;

describe("PS overview layout", () => {
  it("shows the boxes in the fixed order", async () => {
    await openMonitor(countedBody());
    const order = [...document.querySelectorAll("[data-testid^='panel-'], [data-testid='overview']")]
      .map((e) => e.getAttribute("data-testid"));
    expect(order).toEqual(["panel-curriculum", "panel-readiness", "overview", "panel-evidence", "panel-missing", "panel-completeness"]);
  });

  it("the incomplete banner comes before the curriculum box", async () => {
    await openMonitor(monitorBody({ dataCompleteness: "incomplete" }));
    const banner = screen.getByTestId("state-incomplete");
    const box = screen.getByTestId("panel-curriculum");
    expect(banner.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows no percentage anywhere", async () => {
    const { container } = await openMonitor(countedBody());
    expect(container.textContent).not.toContain("%");
  });

  it("has no DATA STATUS box or status legend any more", async () => {
    await openMonitor(countedBody());
    expect(screen.queryByTestId("panel-data-status")).not.toBeInTheDocument();
    expect(screen.queryByText("ความหมายของสถานะ")).not.toBeInTheDocument();
  });
});

describe("สถานะหลักฐาน", () => {
  it("sums evidence and counts verified true / false", async () => {
    await openMonitor(countedBody());
    const box = screen.getByTestId("panel-evidence");
    expect(within(box).getByText("สถานะหลักฐาน")).toBeInTheDocument();
    expect(value(box, "พบหลักฐาน")).toHaveTextContent("3");
    expect(value(box, "ตรวจสอบแล้ว")).toHaveTextContent("2");
    expect(value(box, "รอการตรวจสอบ")).toHaveTextContent("1");
    expect(within(box).queryByText("ยังไม่มีข้อมูลหลักฐาน")).not.toBeInTheDocument();
    expect(within(box).queryByText("ระบบยังไม่ได้ส่งสถานะการตรวจสอบหลักฐานมา")).not.toBeInTheDocument();
  });

  it("no evidence and no verification source: — with both notes", async () => {
    await openMonitor(monitorBody());
    const box = screen.getByTestId("panel-evidence");
    expect(value(box, "พบหลักฐาน")).toHaveTextContent("0");
    expect(value(box, "ตรวจสอบแล้ว")).toHaveTextContent("—");
    expect(value(box, "รอการตรวจสอบ")).toHaveTextContent("—");
    expect(within(box).getByText("ยังไม่มีข้อมูลหลักฐาน")).toBeInTheDocument();
    expect(within(box).getByText("ระบบยังไม่ได้ส่งสถานะการตรวจสอบหลักฐานมา")).toBeInTheDocument();
  });
});

describe("ข้อมูลที่ยังขาด", () => {
  it("totals the items and groups them by PS in the backend's order", async () => {
    await openMonitor(countedBody());
    const box = within(screen.getByTestId("panel-missing"));
    expect(box.getByText("ข้อมูลที่ยังขาด")).toBeInTheDocument();
    expect(box.getByText("5 รายการ")).toBeInTheDocument();
    expect([...screen.getByTestId("panel-missing").querySelectorAll(".missing-groups__code")].map((e) => e.textContent))
      .toEqual(["PS-01", "PS-05"]);
  });

  it("shows at most three lines per PS, as sent, then ดูทั้งหมด →", async () => {
    await openMonitor(countedBody());
    const box = within(screen.getByTestId("panel-missing"));
    const group = box.getByText("PS-01").closest("li");
    for (const m of ["ขาดข้อมูลส่วนที่ 1", "ขาดข้อมูลส่วนที่ 2", "ขาดข้อมูลส่วนที่ 3"]) expect(within(group).getByText(m)).toBeInTheDocument();
    expect(within(group).queryByText("ขาดข้อมูลส่วนที่ 4")).not.toBeInTheDocument();
    expect(within(group).getByRole("link", { name: "ดูทั้งหมด →" }).getAttribute("href")).toBe("/monitor/ps/PS-01");
    const small = box.getByText("PS-05").closest("li");
    expect(within(small).getByText("ขาดข้อมูลส่วนที่ ก")).toBeInTheDocument();
    expect(within(small).queryByRole("link", { name: "ดูทั้งหมด →" })).not.toBeInTheDocument();
  });

  it("keeps ?curriculumCode= on its links", async () => {
    mockFetch(() => jsonResponse(countedBody()));
    renderApp("/monitor/ps?curriculumCode=C-1");
    const box = within(await screen.findByTestId("panel-missing"));
    expect(box.getByRole("link", { name: "ดูทั้งหมด →" }).getAttribute("href")).toBe("/monitor/ps/PS-01?curriculumCode=C-1");
  });

  it("says nothing is missing when every list is empty", async () => {
    await openMonitor(monitorBody());
    expect(within(screen.getByTestId("panel-missing")).getByText("ข้อมูลที่ใช้ตรวจสอบครบถ้วน")).toBeInTheDocument();
  });
});

describe("ความครบถ้วนของข้อมูล", () => {
  it("overall from the response; complete / incomplete counted per PS", async () => {
    await openMonitor(countedBody());
    const box = screen.getByTestId("panel-completeness");
    expect(within(box).getByText("ความครบถ้วนของข้อมูล")).toBeInTheDocument();
    expect(value(box, "ภาพรวม")).toHaveTextContent("ครบถ้วน");
    expect(value(box, "ข้อมูลครบ")).toHaveTextContent("7 เกณฑ์");
    expect(value(box, "ข้อมูลไม่ครบ")).toHaveTextContent("2 เกณฑ์");
  });

  it("overall says ยังไม่ครบถ้วน when the response is incomplete", async () => {
    await openMonitor(monitorBody({ dataCompleteness: "incomplete" }));
    expect(value(screen.getByTestId("panel-completeness"), "ภาพรวม")).toHaveTextContent("ยังไม่ครบถ้วน");
  });
});

describe("PS card", () => {
  it.each([
    ["PASS", "ผ่านเกณฑ์"],
    ["FAIL", "ไม่ผ่านเกณฑ์"],
    ["REVIEW", "ต้องตรวจสอบเพิ่มเติม"],
    ["N/A", "ไม่เข้าข่ายต้องตรวจ"],
    ["UNKNOWN", "ยังไม่มีผลการตรวจสอบ"],
  ])("result text for %s is %s", async (status, text) => {
    const body = monitorBody();
    body.results[0] = psResult("PS-01", status);
    await openMonitor(body);
    const result = within(screen.getByTestId("card-PS-01")).getByText("ผลการตรวจสอบ").parentElement;
    expect(within(result).getByText(text)).toBeInTheDocument();
  });

  it("has code, badges, requirement, detection, result and a details link", async () => {
    const body = monitorBody();
    body.results[0] = psResult("PS-01", "REVIEW", { requirement: "full requirement text", issue: "spec_gap", missingInformation: ["g1", "g2"] });
    await openMonitor(body);
    const card = within(screen.getByTestId("card-PS-01"));
    expect(card.getByRole("heading", { name: "PS-01" })).toBeInTheDocument();
    expect(card.getByTestId("status")).toHaveAttribute("data-status", "REVIEW");
    expect(card.getByTestId("issue")).toHaveTextContent("Spec Gap");
    expect(card.getByText("สิ่งที่เกณฑ์ต้องการ")).toBeInTheDocument();
    expect(card.getByText("full requirement text")).toBeInTheDocument();
    expect(card.getByText("สิ่งที่ระบบตรวจพบ")).toBeInTheDocument();
    expect(card.getByText("ยังขาดข้อมูล 2 รายการ")).toBeInTheDocument();
    expect(card.queryByText("g1")).not.toBeInTheDocument();
    expect(card.getByRole("link", { name: "ตรวจสอบรายละเอียด →" }).getAttribute("href")).toBe("/monitor/ps/PS-01");
  });

  it("no missing line when nothing is missing", async () => {
    await openMonitor(monitorBody());
    expect(within(screen.getByTestId("card-PS-02")).queryByText(/ยังขาดข้อมูล/)).not.toBeInTheDocument();
  });

  it("the details link keeps ?curriculumCode=", async () => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/monitor/ps?curriculumCode=C-1");
    const card = within(await screen.findByTestId("card-PS-03"));
    expect(card.getByRole("link", { name: "ตรวจสอบรายละเอียด →" }).getAttribute("href")).toBe("/monitor/ps/PS-03?curriculumCode=C-1");
  });
});
