/**
 * PS-06 by user confirmation (decided by the lecturer, 2026-09-29): the page shows the curriculum, each lecturer and
 * the qualifications found, and the reviewer confirms "มีความสัมพันธ์" (PASS) or "ไม่มีความสัมพันธ์" (FAIL) through
 * the existing User Review API. The engine's status stays REVIEW; the page shows the resolved status.
 */
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RESULT_TEXT } from "../app/explain";
import { monitorBody, psResult } from "./fixtures";
import { renderApp } from "./render";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
const CURRICULUM = { curriculumCode: "C-1", curriculumName: "หลักสูตรทดสอบ สาขาทดสอบ", curriculumYear: "2570", version: "1", status: "active" };
const CHECKS = [
  'appointment.role: "programmeResponsible"',
  'qualification.source: "educations.degree"', "qualification.required: true",
  'qualificationField.source: "educations.field"', "qualificationField.required: true",
  'institution.source: "educations.institution"', "institution.required: true",
  "review.required: true", "review.reviewByUser: true", 'review.allowManualResult: "PASS", "FAIL"',
];
const FOUND = [
  { label: "ผศ. ดร. ทดสอบ หนึ่ง", items: ["qualification: ปร.ด., วท.ม. -> REVIEW", "qualificationField: สาขาหนึ่ง, สาขาสอง -> REVIEW",
    "institution: มหาวิทยาลัยหนึ่ง -> REVIEW"] },
  { label: "อ. ทดสอบ สอง", items: ["qualification: วท.ม. -> REVIEW", "qualificationField: no value found -> REVIEW",
    "institution: no value found -> REVIEW"] },
];

// TEST-ONLY stand-in for the backend: the engine's status of PS-06 is REVIEW throughout; POST /review keeps the choice.
function backend({ saved = null } = {}) {
  const state = { saved, at: saved ? "2026-09-29T05:00:00Z" : null };
  const calls = [];
  const ps06 = () => psResult("PS-06", "REVIEW", {
    checks: CHECKS, dataFound: FOUND, dataSummary: [{ label: "Subjects", value: "2" }, { label: "Review", value: "Review by user required by configuration" }],
    missingInformation: ["qualificationField: no value found for review", "institution: no value found for review"],
    review: { allowManualResult: ["PASS", "FAIL"], status: state.saved, reviewedAt: state.at },
  });
  vi.stubGlobal("fetch", vi.fn((input, init) => {
    const url = String(input);
    calls.push([init?.method, url, init?.body ? JSON.parse(init.body) : undefined]);
    if (init?.method === "POST") {
      state.saved = JSON.parse(init.body).status;
      state.at = "2026-09-29T06:00:00Z";
      return json(ps06());
    }
    if (url.includes("/ps/")) return json(ps06());
    const body = monitorBody({ curriculum: CURRICULUM });
    body.results = body.results.map((r) => (r.psCode === "PS-06" ? ps06() : r));
    return json(body);
  }));
  return { calls };
}

async function open() {
  renderApp("/monitor/ps/PS-06?curriculumCode=C-1");
  await screen.findByTestId("section-review");
}

const section = (id) => within(screen.getByTestId(`section-${id}`));
const shownStatus = () => section("status").getByTestId("status").getAttribute("data-status");
const posts = (calls) => calls.filter(([m]) => m === "POST");

describe("PS-06 before the user confirms", () => {
  it("is REVIEW, waiting for the user's confirmation", async () => {
    backend();
    await open();
    expect(shownStatus()).toBe("REVIEW");
    expect(section("status").getByTestId("review-pending")).toHaveTextContent("รอการยืนยันจากผู้ใช้");
    expect(screen.queryByTestId("status-sources")).not.toBeInTheDocument();
  });

  it("asks the question with one button per choice, worded for PS-06", async () => {
    backend();
    await open();
    const review = section("review");
    expect(screen.getByTestId("section-review")).toHaveTextContent("การยืนยันความสัมพันธ์ของคุณวุฒิ");
    expect(review.getByTestId("review-instruction")).toHaveTextContent("กรุณาตรวจสอบข้อมูลคุณวุฒิและยืนยันว่ามีความสัมพันธ์กับหลักสูตรหรือไม่");
    expect(review.getByTestId("review-question")).toHaveTextContent("คุณวุฒินี้มีความสัมพันธ์กับหลักสูตรหรือไม่?");
    expect(review.getByTestId("review-choose-PASS")).toHaveTextContent("มีความสัมพันธ์");
    expect(review.getByTestId("review-choose-FAIL")).toHaveTextContent("ไม่มีความสัมพันธ์");
    expect(review.queryByTestId("review-option-PASS")).not.toBeInTheDocument();   // no separate choose-then-save
  });

  it("shows the curriculum, each lecturer and the qualifications found; a missing value is —", async () => {
    backend();
    await open();
    expect(await section("review").findByText("หลักสูตรทดสอบ สาขาทดสอบ")).toBeInTheDocument();
    const lecturers = within(screen.getByTestId("reviewed-information")).getAllByTestId("reviewed-subject");
    expect(lecturers.map((l) => l.querySelector(".subject-name").textContent)).toEqual(["ผศ. ดร. ทดสอบ หนึ่ง", "อ. ทดสอบ สอง"]);
    const rows = (l) => [...l.querySelectorAll("dl > div")].map((d) => [d.querySelector("dt").textContent, d.querySelector("dd").textContent]);
    expect(rows(lecturers[0])).toEqual([["ระดับคุณวุฒิ", "ปร.ด., วท.ม."], ["สาขาวิชา", "สาขาหนึ่ง, สาขาสอง"], ["สถาบันการศึกษา", "มหาวิทยาลัยหนึ่ง"]]);
    expect(rows(lecturers[1])).toEqual([["ระดับคุณวุฒิ", "วท.ม."], ["สาขาวิชา", "—"], ["สถาบันการศึกษา", "—"]]);
  });

  it("says who decides, and never names a mapping", async () => {
    backend();
    await open();
    expect(screen.getByTestId("section-condition")).toHaveTextContent("ระบบไม่ตัดสินความสัมพันธ์เอง");
    const text = document.body.textContent;
    for (const word of ["Mapping", "mapping", "Related Major", "Approved Major", "Matching Rule"]) expect(text).not.toContain(word);
  });
});

describe("the user confirms through the existing User Review API", () => {
  it.each([
    ["PASS", "มีความสัมพันธ์"],
    ["FAIL", "ไม่มีความสัมพันธ์"],
  ])("%s: the button saves the choice, and the page shows it as the result", async (status, label) => {
    const api = backend();
    await open();
    await act(async () => fireEvent.click(section("review").getByTestId(`review-choose-${status}`)));
    expect(posts(api.calls)).toEqual([["POST", "/api/monitor/ps/PS-06/review?curriculumCode=C-1", { status }]]);
    await waitFor(() => expect(shownStatus()).toBe(status));
    expect(section("status").getByText(RESULT_TEXT[status])).toBeInTheDocument();
    expect(screen.getByTestId("status-sources")).toHaveTextContent(`ระบบประเมินเบื้องต้น: REVIEW · ผู้ตรวจยืนยัน: ${status}`);
    expect(section("review").getByTestId("review-saved")).toHaveTextContent(label);
    expect(screen.queryByTestId("review-pending")).not.toBeInTheDocument();
  });

  it("the overview card shows the confirmed result, and readiness stays the backend's", async () => {
    backend({ saved: "PASS" });
    renderApp("/monitor/ps?curriculumCode=C-1");
    const card = within(await screen.findByTestId("card-PS-06"));
    expect(card.getByTestId("status")).toHaveAttribute("data-status", "PASS");
    expect(screen.queryByTestId("readiness-value")).not.toBeInTheDocument();   // this stand-in sends none: not computed here
  });
});

describe("PS-03 keeps its own review wording", () => {
  it("choose, then save", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json(psResult("PS-03", "REVIEW", {
      review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status: null, reviewedAt: null } }))));
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderApp("/monitor/ps/PS-03");
    const review = within(await screen.findByTestId("section-review"));
    expect(screen.getByTestId("section-review")).toHaveTextContent("ผลการตรวจของผู้ตรวจ (User Review)");
    expect(review.getByTestId("review-option-PASS")).toBeInTheDocument();
    expect(review.getByTestId("review-save")).toBeDisabled();
    expect(review.queryByTestId("review-question")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-pending")).not.toBeInTheDocument();
  });
});
