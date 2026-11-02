import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
// TEST-ONLY: GET /api/monitor as produced by the real backend engine over the backend's own test
// data (backend/tests/support/fixtures.py base_data) for PS-01 … PS-09. Not used by the app.
import sample from "./fixtures/backend-sample.json";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

// Rule-engine and configuration vocabulary that must never reach the reader.
const TECHNICAL = [
  "distinct count", "targetCollection", "operator", "compare", "previous5Years", ">=", "<=", "->",
  "checks:", "ExistsCheck", "AtLeastCheck", "MappingCheck", "CountCheck", "ShowCheck", "join ", "where role",
  "personId", "curriculumId", "publicationYear", "Subjects", "Operation", "equal to", "matching record",
  "programmeResponsible", "programmeStaff", "specialInstructor",
];
const CODES = sample.results.map((r) => r.psCode);

describe("human-readable pages with real backend output", () => {
  it("the overview shows every PS card without rule logic", async () => {
    mockFetch(() => jsonResponse(sample));
    const { container } = renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(CODES).toEqual(["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06", "PS-07", "PS-08", "PS-09"]);
    for (const c of CODES) expect(screen.getByTestId(`card-${c}`)).toBeInTheDocument();
    for (const t of TECHNICAL) expect(container.textContent, t).not.toContain(t);
    expect(screen.getByTestId("card-PS-01")).toHaveTextContent("หลักสูตรต้องมีอาจารย์ผู้รับผิดชอบหลักสูตรอย่างน้อย 5 คน");
    expect(screen.getByTestId("card-PS-01")).toHaveTextContent("พบข้อมูล 5 รายการจากข้อมูลการแต่งตั้ง");
  });

  it.each(CODES)("%s detail explains the result without rule logic", async (code) => {
    const result = sample.results.find((r) => r.psCode === code);
    mockFetch(() => jsonResponse(result));
    const { container } = renderApp(`/monitor/ps/${code}`);
    await screen.findByTestId("section-traceability");
    const text = container.textContent;
    for (const t of TECHNICAL) expect(text, `${code}: ${t}`).not.toContain(t);
    expect(screen.getByTestId("section-requirement")).toHaveTextContent(result.requirement);
    expect(screen.queryByTestId("section-why")).not.toBeInTheDocument();
    expect(text).not.toContain("ทำไมจึงได้ผลนี้");
    expect(container.querySelectorAll("form, input, textarea, select, button")).toHaveLength(0);
  });

  it("PS-01 states its condition in plain words", async () => {
    mockFetch(() => jsonResponse(sample.results[0]));
    renderApp("/monitor/ps/PS-01");
    expect(await screen.findByText("จำนวนที่ระบบนับได้ต้องไม่น้อยกว่า 5")).toBeInTheDocument();
    expect(screen.getByText("จำนวนที่ระบบนับได้").nextSibling).toHaveTextContent("5");
  });

  it("PS-08 (N/A) shows that no source was traced", async () => {
    mockFetch(() => jsonResponse(sample.results[7]));
    renderApp("/monitor/ps/PS-08");
    expect(await screen.findByText("ยังไม่มีข้อมูลแหล่งที่มา")).toBeInTheDocument();
  });
});
