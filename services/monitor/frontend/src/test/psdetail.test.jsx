import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

const BACK = "← ภาพรวมเกณฑ์ PS";
const section = (id) => within(screen.getByTestId(`section-${id}`));

describe("/monitor/ps/:psCode", () => {
  it("uses the fixed section order with plain Thai titles", async () => {
    mockFetch(() => jsonResponse(psResult("PS-04", "REVIEW")));
    renderApp("/monitor/ps/PS-04");
    await screen.findByTestId("section-requirement");
    const ids = [...document.querySelectorAll("[data-testid^='section-']")].map((e) => e.getAttribute("data-testid"));
    expect(ids).toEqual([
      "section-header", "section-requirement", "section-status", "section-check", "section-condition",
      "section-data", "section-verification", "section-missing", "section-evidence", "section-traceability",
    ]);
    const titles = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titles).toEqual([
      "สิ่งที่เกณฑ์ต้องการ", "ผลการตรวจสอบ", "เกณฑ์นี้ตรวจสอบอะไร", "เงื่อนไขที่ใช้ตัดสิน",
      "สิ่งที่ระบบตรวจพบ", "การยืนยันข้อมูล", "ยังขาดข้อมูลสำหรับตรวจสอบ", "หลักฐานที่ใช้ประกอบการตรวจสอบ", "แหล่งที่มาของข้อมูล",
    ]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("PS-04");
  });

  it("shows the requirement, the status as text + icon and the Thai result", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "FAIL", { missingInformation: ["g1"] })));
    renderApp("/monitor/ps/PS-01");
    expect(await screen.findByText("req-PS-01")).toBeInTheDocument();
    const status = section("status").getByTestId("status");
    expect(status).toHaveTextContent("ไม่ผ่าน");
    expect(status).toHaveAttribute("data-status", "FAIL");
    expect(status.querySelector("svg")).not.toBeNull();
    expect(section("status").getByText("ไม่ผ่านเกณฑ์")).toBeInTheDocument();
    expect(section("status").getByText("ยังขาดข้อมูล 1 รายการ")).toBeInTheDocument();
  });

  it("never shows the rule expression or the configuration lines", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "PASS", {
      checks: ['targetCollection: "appointments"', 'condition.operator: ">="'],
      dataSummary: [{ label: "Operation", value: "distinct count of personId in appointments; compare >= 5" }],
    })));
    const { container } = renderApp("/monitor/ps/PS-01");
    await screen.findByTestId("section-traceability");
    for (const t of ["targetCollection", "operator", "distinct count", "personId", ">="]) expect(container.textContent).not.toContain(t);
    expect(container.querySelector("details")).toBeNull();
  });

  it("shows empty states when the backend sends nothing", async () => {
    mockFetch(() => jsonResponse(psResult("PS-02", "PASS", { dataSummary: [], dataFound: [], verification: { found: 0, verified: null, approved: null } })));
    renderApp("/monitor/ps/PS-02");
    await screen.findByTestId("section-evidence");
    expect(section("evidence").getByText("ยังไม่มีข้อมูลหลักฐาน")).toBeInTheDocument();
    expect(section("traceability").getByText("ยังไม่มีข้อมูลแหล่งที่มา")).toBeInTheDocument();
    expect(section("missing").getByText("ข้อมูลที่ใช้ตรวจสอบครบถ้วน")).toBeInTheDocument();
    expect(section("data").getByText("ไม่พบข้อมูลที่ใช้ตรวจสอบ")).toBeInTheDocument();
    expect(section("condition").getByText("ข้อมูลไม่เพียงพอสำหรับแสดงเงื่อนไขการตรวจสอบ")).toBeInTheDocument();
    const v = section("verification");
    expect(v.getByText("พบข้อมูล").nextSibling).toHaveTextContent("0");
    expect(v.getByText("ตรวจสอบแล้ว").nextSibling).toHaveTextContent("—");
    expect(v.getByText("อนุมัติแล้ว").nextSibling).toHaveTextContent("—");
  });

  it("no requirement and no locked text: says there is not enough to explain the check", async () => {
    mockFetch(() => jsonResponse(psResult("PS-10", "PASS", { requirement: null })));
    renderApp("/monitor/ps/PS-10");
    await screen.findByTestId("section-check");
    expect(section("requirement").getByText("ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด")).toBeInTheDocument();
    expect(section("check").getByText("ข้อมูลไม่เพียงพอสำหรับอธิบายการตรวจสอบ")).toBeInTheDocument();
  });

  it("shows backend evidence as sent and missing information in plain Thai", async () => {
    mockFetch(() => jsonResponse(psResult("PS-02", "REVIEW", {
      evidence: [{ label: "doc-1", reference: "ref-1" }],
      missingInformation: ["no usable degree value"],
      dataCompleteness: "incomplete",
    })));
    renderApp("/monitor/ps/PS-02");
    expect(await screen.findByText("doc-1 — ref-1")).toBeInTheDocument();
    expect(section("missing").getByText("ไม่พบระดับคุณวุฒิที่ระบบใช้ตรวจสอบได้")).toBeInTheDocument();
    expect(screen.getByText("ข้อมูลยังไม่ครบถ้วน")).toBeInTheDocument();
  });

  it("shows why nothing was decided next to the status", async () => {
    mockFetch(() => jsonResponse(psResult("PS-08", "REVIEW", { issue: "spec_gap" })));
    renderApp("/monitor/ps/PS-08");
    expect((await screen.findByTestId("section-status")).querySelector("[data-testid='issue']")).toHaveTextContent("Spec Gap");
  });

  it.each([["evaluation_error", "Evaluation Error"], ["configuration_error", "Configuration Error"]])(
    "%s is shown as %s", async (issue, text) => {
      mockFetch(() => jsonResponse(psResult("PS-09", "REVIEW", { issue })));
      renderApp("/monitor/ps/PS-09");
      expect((await screen.findByTestId("section-status")).querySelector("[data-testid='issue']")).toHaveTextContent(text);
    });

  it("shows no issue badge when the backend reports none", async () => {
    mockFetch(() => jsonResponse(psResult("PS-03", "REVIEW", { issue: null })));
    renderApp("/monitor/ps/PS-03");
    await screen.findByTestId("section-status");
    expect(screen.queryByTestId("issue")).not.toBeInTheDocument();
  });

  it("links back to the PS overview, keeping ?curriculumCode=", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01")));
    renderApp("/monitor/ps/PS-01?curriculumCode=C-1");
    const back = await screen.findByRole("link", { name: BACK });
    expect(back.getAttribute("href")).toBe("/monitor/ps?curriculumCode=C-1");
  });

  it("404 from backend: still every section; data-dependent ones say they are waiting", async () => {
    mockFetch(() => jsonResponse({ detail: "none" }, 404));
    renderApp("/monitor/ps/PS-09");
    expect(await screen.findByText("ยังไม่มีข้อมูล")).toBeInTheDocument();
    expect(document.querySelectorAll("[data-testid^='section-']")).toHaveLength(10);
    expect(section("status").getByText("กำลังรอข้อมูล")).toBeInTheDocument();
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
  });

  it("backend error -> ไม่สามารถโหลดข้อมูลการตรวจสอบได้, not FAIL; details go to the console", async () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(() => jsonResponse({ detail: "x" }, 503));
    const { container } = renderApp("/monitor/ps/PS-09");
    expect(await screen.findByText("ไม่สามารถโหลดข้อมูลการตรวจสอบได้")).toBeInTheDocument();
    expect(screen.queryByTestId("status")).not.toBeInTheDocument();
    expect(container.textContent).not.toContain("FAIL");
    expect(container.textContent).not.toContain("503");
    expect(log).toHaveBeenCalled();
  });

  it("กำลังโหลดข้อมูล…", () => {
    mockFetch(() => new Promise(() => {}));
    renderApp("/monitor/ps/PS-01");
    expect(screen.getByText("กำลังโหลดข้อมูล…")).toBeInTheDocument();
  });

  it("the overview is re-read on every visit; a detail page does not re-read it", async () => {
    const fetchFn = mockFetch((url) => jsonResponse(url.includes("/ps/") ? psResult("PS-01") : monitorBody()));
    const monitorCalls = () => fetchFn.mock.calls.filter(([u]) => !String(u).includes("/ps/")).length;
    renderApp("/monitor/ps");
    fireEvent.click(within(await screen.findByTestId("card-PS-01")).getByRole("link", { name: "ตรวจสอบรายละเอียด →" }));
    await screen.findByTestId("section-requirement");
    expect(monitorCalls()).toBe(1);
    fireEvent.click(screen.getByRole("link", { name: BACK }));
    await waitFor(() => expect(monitorCalls()).toBe(2));
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();
  });
});

describe("/monitor/ps/:psCode explanations", () => {
  it("เกณฑ์นี้ตรวจสอบอะไร frames the requirement and names the sources read", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "PASS", {
      requirement: "ต้องมีอย่างน้อย 5 คน",
      traceability: [{ collection: "appointments", recordId: "a1", fields: ["role"], values: { role: "r" } }],
    })));
    renderApp("/monitor/ps/PS-01");
    const check = within(await screen.findByTestId("section-check"));
    expect(check.getByText("ระบบตรวจสอบว่าข้อมูลของหลักสูตรเป็นไปตามข้อกำหนด “ต้องมีอย่างน้อย 5 คน” หรือไม่")).toBeInTheDocument();
    expect(check.getByText("ข้อมูลที่ใช้ตรวจ: ข้อมูลการแต่งตั้ง")).toBeInTheDocument();
  });

  it("เงื่อนไขที่ใช้ตัดสิน: plain words only for an exact '<operator> <number>' condition", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "PASS", { dataSummary: [{ label: "Condition", value: ">= 5" }] })));
    renderApp("/monitor/ps/PS-01");
    expect(within(await screen.findByTestId("section-condition")).getByText("จำนวนที่ระบบนับได้ต้องไม่น้อยกว่า 5")).toBeInTheDocument();
    expect(section("data").queryByText(">= 5")).not.toBeInTheDocument();
  });

  it("a condition in any other form is not shown", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "PASS", { dataSummary: [{ label: "Condition", value: "EXISTS programmeStaff" }] })));
    const { container } = renderApp("/monitor/ps/PS-01");
    expect(within(await screen.findByTestId("section-condition")).getByText("ข้อมูลไม่เพียงพอสำหรับแสดงเงื่อนไขการตรวจสอบ")).toBeInTheDocument();
    expect(container.textContent).not.toContain("programmeStaff");
  });

  it("สิ่งที่ระบบตรวจพบ: a sentence, counts under Thai labels, and the names checked", async () => {
    mockFetch(() => jsonResponse(psResult("PS-05", "PASS", {
      verification: { found: 4, verified: null, approved: null },
      dataSummary: [
        { label: "Operation", value: "op" },
        { label: "Subjects", value: "2" },
        { label: "Subjects PASS", value: "2" },
        { label: "Distinct personId count", value: "2" },
        { label: "curriculumYear", value: "2567" },
        { label: "somethingNew", value: "9" },
      ],
      dataFound: [
        { label: "อาจารย์ ก", items: ["degree: master (equal to 'master') -> PASS"] },
        { label: "personId", items: ["อาจารย์ ข"] },
      ],
      traceability: [{ collection: "educations", recordId: "e1", fields: ["degree", "personId"], values: { degree: "master", personId: "p1" } }],
    })));
    renderApp("/monitor/ps/PS-05");
    const data = within(await screen.findByTestId("section-data"));
    expect(data.getByText("พบข้อมูล 4 รายการจากข้อมูลคุณวุฒิ")).toBeInTheDocument();
    expect(data.getByText("จำนวนรายการที่ตรวจ").nextSibling).toHaveTextContent("2");
    expect(data.getByText("รายการที่ผ่านเกณฑ์").nextSibling).toHaveTextContent("2");
    expect(data.getByText("จำนวนที่ระบบนับได้").nextSibling).toHaveTextContent("2");
    expect(data.getByText("ปีหลักสูตร").nextSibling).toHaveTextContent("2567");
    expect(data.getByText("ข้อมูลเพิ่มเติม").nextSibling).toHaveTextContent("9");
    expect(data.getByText("อาจารย์ ก")).toBeInTheDocument();
    expect(data.getByText("อาจารย์ ข")).toBeInTheDocument();
    for (const t of ["Subjects", "personId", "somethingNew", "->", "equal to", "op"]) {
      expect(screen.getByTestId("section-data").textContent).not.toContain(t);
    }
  });
});

describe("names checked", () => {
  it("an empty group is not shown as a name (e.g. a counted field with no record)", async () => {
    mockFetch(() => jsonResponse(psResult("PS-01", "FAIL", {
      verification: { found: 0, verified: null, approved: null },
      dataFound: [{ label: "personId", items: [] }],
      traceability: [],
    })));
    const { container } = renderApp("/monitor/ps/PS-01");
    await screen.findByTestId("section-data");
    expect(section("data").queryByText("รายการที่ระบบตรวจ")).not.toBeInTheDocument();
    expect(container.textContent).not.toContain("personId");
  });
});

describe("แหล่งที่มาของข้อมูล", () => {
  it("is a table of source, record and the data used, with Thai labels", async () => {
    mockFetch(() => jsonResponse(psResult("PS-05", "PASS", {
      traceability: [
        { collection: "educations", recordId: "e1", fields: ["degree", "personId"], values: { degree: "master", personId: "p1" } },
        { collection: "appointments", recordId: "a9", fields: ["personId"], values: { personId: "p1" } },
      ],
    })));
    renderApp("/monitor/ps/PS-05");
    const table = within(await screen.findByTestId("section-traceability")).getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["แหล่งข้อมูล", "รายการ", "ข้อมูลที่ใช้ตรวจสอบ"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("ข้อมูลคุณวุฒิ")).toBeInTheDocument();
    expect(within(rows[0]).getByText("ระดับคุณวุฒิ")).toBeInTheDocument();
    expect(rows[0].textContent).not.toContain("master");
    expect(rows[0].textContent).toContain("รหัสอ้างอิง e1");
    expect(rows[0].textContent).not.toContain("personId");
    expect(within(rows[1]).getByText("ข้อมูลอ้างอิงภายในระบบ")).toBeInTheDocument();
  });

  it("shows ten records, the rest in a closed <details>", async () => {
    const traceability = Array.from({ length: 12 }, (_, i) => (
      { collection: "educations", recordId: `r${i + 1}`, fields: ["degree"], values: { degree: `v${i + 1}` } }));
    mockFetch(() => jsonResponse(psResult("PS-03", "PASS", { traceability })));
    renderApp("/monitor/ps/PS-03");
    const el = await screen.findByTestId("section-traceability");
    const details = within(el).getByText("แสดงทั้งหมด (12)").closest("details");
    expect(details).not.toHaveAttribute("open");
    for (let i = 1; i <= 10; i++) expect(details.contains(within(el).getByText(`รหัสอ้างอิง r${i}`))).toBe(false);
    for (const i of [11, 12]) expect(details.contains(within(el).getByText(`รหัสอ้างอิง r${i}`))).toBe(true);
  });

  it("ten records or fewer need no <details>", async () => {
    mockFetch(() => jsonResponse(psResult("PS-03", "PASS", { traceability: [{ collection: "c", recordId: "r1", fields: [], values: {} }] })));
    renderApp("/monitor/ps/PS-03");
    expect(within(await screen.findByTestId("section-traceability")).queryByText(/แสดงทั้งหมด/)).not.toBeInTheDocument();
  });

  it("shows no percentage and no form controls", async () => {
    mockFetch(() => jsonResponse(psResult("PS-03", "REVIEW")));
    const { container } = renderApp("/monitor/ps/PS-03");
    await screen.findByTestId("section-traceability");
    expect(container.textContent).not.toContain("%");
    expect(container.querySelectorAll("form, input, textarea, select, button")).toHaveLength(0);
  });
});
