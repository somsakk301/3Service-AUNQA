import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptPSResult } from "../api/adapter";
import { SourceReference } from "../components/SourceReference";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

// TEST-ONLY: evidence items shaped as GET /api/monitor sends them (documents of the curriculum).
const COMPLETE = { label: "TEST-1.pdf", reference: "ref-1", storage: "local", path: "test-data/documents/original/TEST-1.pdf" };
const NO_FILE = { label: "TEST-2.pdf", reference: "ref-2", storage: null, path: null };

async function detail(evidence) {
  mockFetch(() => jsonResponse(psResult("PS-01", "PASS", { evidence })));
  renderApp("/monitor/ps/PS-01");
  return within(await screen.findByTestId("section-evidence"));
}

describe("PS detail: หลักฐานที่ใช้ประกอบการตรวจสอบ", () => {
  it("TEST 09: shows each document the API sent, with its storage and path", async () => {
    const box = await detail([COMPLETE, NO_FILE]);
    const [first, second] = box.getAllByTestId("evidence-item");
    expect(within(first).getByText("TEST-1.pdf — ref-1")).toBeInTheDocument();
    expect(within(first).getByTestId("evidence-storage")).toHaveTextContent("ที่เก็บไฟล์ต้นฉบับ: local");
    expect(within(first).getByTestId("evidence-path")).toHaveTextContent("ตำแหน่งไฟล์ต้นฉบับ: test-data/documents/original/TEST-1.pdf");
    expect(within(first).getByTestId("evidence-open")).toHaveAttribute(
      "href",
      "/api/import/documents/ref-1/file",
    );
    // a document without originalFile: said to be missing, no path is made up
    expect(within(second).getByTestId("evidence-storage")).toHaveTextContent("ที่เก็บไฟล์ต้นฉบับ: ไม่พบข้อมูล storage");
    expect(within(second).getByTestId("evidence-path")).toHaveTextContent("ตำแหน่งไฟล์ต้นฉบับ: ไม่พบข้อมูล path");
    expect(within(second).queryByTestId("evidence-open")).not.toBeInTheDocument();
  });

  it("TEST 10: evidence [] shows that there is no evidence and no item", async () => {
    const box = await detail([]);
    expect(box.getByText("ยังไม่มีข้อมูลหลักฐาน")).toBeInTheDocument();
    expect(box.queryByTestId("evidence-item")).not.toBeInTheDocument();
  });
});

describe("PS source document link", () => {
  it("opens the verified PDF at the configured PDF page", () => {
    render(<SourceReference psCode="PS-01" />);
    const link = screen.getByRole("link", { name: /เปิด .* หน้า 10/ });
    expect(link).toHaveAttribute("href", "/references/wuqa-template-2568-page-14.pdf#page=14");
  });
});

describe("/monitor/ps: สถานะหลักฐาน", () => {
  const found = async (body) => {
    mockFetch(() => jsonResponse(body));
    renderApp("/monitor/ps");
    return within(await screen.findByTestId("panel-evidence")).getByText("พบหลักฐาน").nextSibling;
  };

  it("counts each document once although every PS carries it", async () => {
    const body = monitorBody();
    for (const r of body.results) r.evidence = [COMPLETE, NO_FILE];
    expect(await found(body)).toHaveTextContent("2");
  });

  it("counts 0 when the API sent no evidence", async () => {
    expect(await found(monitorBody())).toHaveTextContent("0");
  });
});

describe("adapter: evidence", () => {
  it("keeps storage and path as sent; absent values are null", () => {
    const r = adaptPSResult(psResult("PS-01", "PASS", { evidence: [COMPLETE, { label: "x", reference: "r" }] }));
    expect(r.evidence).toEqual([COMPLETE, { label: "x", reference: "r", storage: null, path: null }]);
  });
});
