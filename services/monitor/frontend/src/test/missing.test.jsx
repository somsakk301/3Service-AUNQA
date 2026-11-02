import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptPSResult } from "../api/adapter";
import { missingText, NOT_ENOUGH } from "../app/missingText";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

// Lines exactly as the backend engine produced them during the E2E run (mornitor_e2e_test).
const E2E = {
  specGapJoin: "SPEC GAP: join is not a set of 'collection.field' references declared by the Data Schema: join.experiencePersonId",
  specGapNa: "SPEC GAP: naEnabled is true, but this operation defines no not-applicable condition",
  specGapDegree: "SPEC GAP: the specification defines no ordering of degree values, so bachelor cannot be compared with the minimum 'master' (only equality with it is decidable)",
  roleName: "ผู้ทดสอบ E2E-C2-1 (0a10a9dc91c5c70000000001): roleName",
  orderDate: "ผู้ทดสอบ E2E-C2-1 (0a10a9dc91c5c70000000001): appointmentOrder.orderDate",
  order: "ผู้ทดสอบ E2E-C3-1 (30abd13bcc6a470000000001): appointmentOrder",
  orderNumber: "ผู้ทดสอบ E2E-C3-1 (30abd13bcc6a470000000001): appointmentOrder.orderNumber",
  degree: "no usable degree value",
  publicationYear: "1 record(s) lack a usable publicationYear",
  curriculumYear: "E2E-C3: curriculumYear is missing or not an integer",
  noSubjects: "no appointments record is selected, so nothing can be checked",
  configError: "Configuration error: result.review is missing or is not a status",
};
// Rule-engine and configuration vocabulary that must not reach the reader.
const TECHNICAL = /SPEC GAP|Configuration error|collection\.field|join|naEnabled|appointmentOrder|roleName|publicationYear|curriculumYear|record\(s\)|\bdegree\b|mapping|extraction|[0-9a-f]{24}/;

describe("missingText: backend lines in plain Thai (presentation only)", () => {
  it.each([
    [E2E.curriculumYear, "E2E-C3: ไม่พบข้อมูลปีหลักสูตร หรือข้อมูลปีหลักสูตรไม่อยู่ในรูปแบบที่ระบบตรวจสอบได้"],
    [E2E.publicationYear, "พบข้อมูลผลงานวิชาการ 1 รายการที่ไม่มีปีที่เผยแพร่ที่ระบบใช้ตรวจสอบได้"],
    [E2E.degree, "ไม่พบระดับคุณวุฒิที่ระบบใช้ตรวจสอบได้"],
    [E2E.noSubjects, "ไม่พบข้อมูลการแต่งตั้งที่ตรงกับเงื่อนไขของเกณฑ์นี้ จึงยังตรวจสอบไม่ได้"],
    [E2E.roleName, "ผู้ทดสอบ E2E-C2-1: ไม่มีข้อมูลชื่อบทบาท"],
    [E2E.orderDate, "ผู้ทดสอบ E2E-C2-1: ไม่มีข้อมูลวันที่ออกคำสั่ง"],
    [E2E.orderNumber, "ผู้ทดสอบ E2E-C3-1: ไม่มีข้อมูลเลขที่คำสั่งแต่งตั้ง"],
    [E2E.order, "ผู้ทดสอบ E2E-C3-1: ไม่มีข้อมูลคำสั่งแต่งตั้ง"],
    ["no appointments records were found", "ไม่พบข้อมูลการแต่งตั้ง"],
  ])("%s", (line, thai) => {
    expect(missingText(line)).toBe(thai);
  });

  it.each([
    E2E.specGapJoin, E2E.specGapNa, E2E.specGapDegree, E2E.configError,
    "Evaluation error: KeyError: 'x'",
    "2 appointments record(s) lack curriculumId, personId",       // internal keys only
    "experience: no value found for review",                        // a configuration key, not data
    "no things records were found",                                 // collection without a Thai name
    "3 record(s) lack a usable somethingNew",                       // field without a Thai label
    "somebody (0a10a9dc91c5c70000000001): personId",                // field without a Thai label
    "an English sentence the engine may add later",
  ])("not safely translatable → %s", (line) => {
    expect(missingText(line)).toBe(NOT_ENOUGH);
  });

  it("a record known only by its id is not named", () => {
    expect(missingText("0a10a9dc91c5c70000000001: roleName")).toBe("มีรายการที่ไม่มีข้อมูลชื่อบทบาท");
    expect(missingText("0a10a9dc91c5c70000000001 (ไม่พบ persons.fullName) (0a10a9dc91c5c70000000002): roleName"))
      .toBe("มีรายการที่ไม่มีข้อมูลชื่อบทบาท");
  });

  it("a line written without Latin script is shown as sent", () => {
    expect(missingText("ยังไม่มีคำสั่งแต่งตั้งของอาจารย์ 2 คน")).toBe("ยังไม่มีคำสั่งแต่งตั้งของอาจารย์ 2 คน");
  });

  it("no line becomes technical text", () => {
    for (const line of Object.values(E2E)) expect(missingText(line)).not.toMatch(TECHNICAL);
  });
});

describe("missing information on the pages", () => {
  const lines = [E2E.roleName, E2E.orderDate, E2E.specGapJoin, E2E.degree];

  it("detail: one plain line per backend line, none hidden, nothing technical", async () => {
    const raw = psResult("PS-04", "FAIL", { missingInformation: [...lines], dataCompleteness: "incomplete" });
    mockFetch(() => jsonResponse(raw));
    renderApp("/monitor/ps/PS-04");
    const section = await screen.findByTestId("section-missing");
    const shown = within(section).getAllByRole("listitem").map((li) => li.textContent);
    expect(shown).toEqual(lines.map(missingText));
    expect(shown).toHaveLength(lines.length);
    expect(section.textContent).not.toMatch(TECHNICAL);
    // the result the backend sent is unchanged: status and the card count still come from it
    expect(within(screen.getByTestId("section-status")).getByTestId("status")).toHaveAttribute("data-status", "FAIL");
    expect(screen.getByTestId("section-status")).toHaveTextContent(`ยังขาดข้อมูล ${lines.length} รายการ`);
  });

  it("overview: the panel total is the backend's count; lines are shown in plain Thai", async () => {
    const body = monitorBody();
    body.results[3] = psResult("PS-04", "FAIL", { missingInformation: [...lines] });
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    const panel = await screen.findByTestId("panel-missing");
    expect(within(panel).getByText(`${lines.length} รายการ`)).toBeInTheDocument();
    const group = within(panel).getByText("PS-04").closest("li");
    expect(within(group).getAllByRole("listitem").map((li) => li.textContent)).toEqual(lines.slice(0, 3).map(missingText));
    expect(panel.textContent).not.toMatch(TECHNICAL);
    expect(within(screen.getByTestId("card-PS-04")).getByText(`ยังขาดข้อมูล ${lines.length} รายการ`)).toBeInTheDocument();
  });

  it("the data the page received is not changed (presentation only)", () => {
    const raw = psResult("PS-04", "FAIL", { missingInformation: [...lines] });
    const adapted = adaptPSResult(raw);
    lines.forEach(missingText);
    expect(adapted.missingInformation).toEqual(lines);
    expect(raw.missingInformation).toEqual(lines);
  });
});
