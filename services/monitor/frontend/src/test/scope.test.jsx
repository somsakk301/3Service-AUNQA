import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { monitorBody } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

const GROUPS = ["p1", "p2", "p3", "p4", "p8", "ps"];
const NO_DATA = ["p1", "p2", "p3", "p4", "p8"];

describe("home page (/)", () => {
  it("shows six cards in the order P1 P2 P3 P4 P8 PS and calls no API", () => {
    const fetchFn = mockFetch(() => jsonResponse(monitorBody()));
    const { container } = renderApp("/");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("เลือกส่วนที่ต้องการดู");
    const cards = [...container.querySelectorAll("[data-testid^='home-card-']")];
    expect(cards.map((c) => c.getAttribute("data-testid"))).toEqual(GROUPS.map((k) => `home-card-${k}`));
    expect(cards.map((c) => within(c).getByRole("heading").textContent)).toEqual(["P1", "P2", "P3", "P4", "P8", "PS"]);
    expect(container.querySelectorAll("form, input, textarea, select, button")).toHaveLength(0);
    expect(container.textContent).not.toContain("%");
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it.each(NO_DATA)("the %s card says there is no data yet and opens its page", (key) => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/");
    const card = within(screen.getByTestId(`home-card-${key}`));
    expect(card.getByText("ยังไม่มีข้อมูลสำหรับส่วนนี้")).toBeInTheDocument();
    expect(card.getByRole("link", { name: "เปิดดู →" }).getAttribute("href")).toBe(`/monitor/${key}`);
    expect(card.queryByText("Programme Standards")).not.toBeInTheDocument();
  });

  it("the PS card names Programme Standards and opens /monitor/ps", () => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/");
    const card = within(screen.getByTestId("home-card-ps"));
    expect(card.getByText("Programme Standards")).toBeInTheDocument();
    expect(card.getByText("เกณฑ์มาตรฐานที่ใช้ตรวจสอบข้อมูลของหลักสูตร")).toBeInTheDocument();
    expect(card.getByText("เปิดดูผลการตรวจสอบได้")).toBeInTheDocument();
    expect(card.queryByText("ยังไม่มีข้อมูลสำหรับส่วนนี้")).not.toBeInTheDocument();
    expect(card.getByRole("link", { name: "เปิดดู →" }).getAttribute("href")).toBe("/monitor/ps");
  });

  it("card links keep ?curriculumCode=", () => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/?curriculumCode=C-1");
    for (const k of GROUPS) {
      const link = within(screen.getByTestId(`home-card-${k}`)).getByRole("link", { name: "เปิดดู →" });
      expect(link.getAttribute("href")).toBe(`/monitor/${k}?curriculumCode=C-1`);
    }
  });

  it("the PS card opens the PS overview", async () => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/");
    fireEvent.click(within(screen.getByTestId("home-card-ps")).getByRole("link", { name: "เปิดดู →" }));
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();
  });
});

describe("/monitor/p1 p2 p3 p4 p8 (no data yet)", () => {
  it.each(NO_DATA)("%s shows the notice only and calls no API", (key) => {
    const label = key.toUpperCase();
    const fetchFn = mockFetch(() => jsonResponse(monitorBody()));
    const { container } = renderApp(`/monitor/${key}`);
    const notice = screen.getByTestId("scope-notice");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(label);
    expect(within(notice).getByText("ยังไม่มีข้อมูลสำหรับส่วนนี้")).toBeInTheDocument();
    expect(within(notice).getByText(
      `ส่วนนี้ยังไม่อยู่ในขอบเขตการพัฒนาปัจจุบัน ระบบตรวจเฉพาะเกณฑ์ PS ตาม configuration ใน ps_requirements `
      + `และยังไม่มี configuration ของ ${label} ในฐานข้อมูล จึงไม่แสดงสถานะ ตัวเลข หรือข้อมูลใด ๆ`)).toBeInTheDocument();
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    expect(screen.queryByTestId("issue")).not.toBeInTheDocument();
    expect(container.querySelectorAll("[data-testid^='card-'], [data-testid^='count-']")).toHaveLength(0);
    expect(container.textContent).not.toMatch(/PS-\d/);
    expect(container.textContent).not.toContain("%");
    expect(container.querySelectorAll("form, input, textarea, select, button")).toHaveLength(0);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("links back to the home page, keeping ?curriculumCode=", () => {
    mockFetch(() => jsonResponse(monitorBody()));
    renderApp("/monitor/p3?curriculumCode=C-1");
    const link = within(screen.getByTestId("scope-notice")).getByRole("link", { name: "← กลับหน้าแรก" });
    expect(link.getAttribute("href")).toBe("/?curriculumCode=C-1");
  });
});
