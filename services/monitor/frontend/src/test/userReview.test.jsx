import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { psResult } from "./fixtures";
import { renderApp } from "./render";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// TEST-ONLY stand-in for the backend: GET answers with what it holds; POST /review checks the status against
// the options it sent and keeps it. The engine status of PS-03 stays REVIEW throughout.
const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));

const RECORDED_BY = { userId: "u1", name: "ผู้ตรวจทดสอบ" };
// Plain-Thai status words shown to the reader (project owner 2026-10-05); the raw code stays in data-status.
const LABEL = { PASS: "ผ่าน", FAIL: "ไม่ผ่าน", REVIEW: "รอตรวจทาน" };

function backend({ allowed = ["PASS", "FAIL", "REVIEW"], saved = null, post = "ok" } = {}) {
  const state = { saved, by: saved ? RECORDED_BY : null, at: saved ? "2026-09-26T05:00:00Z" : null, n: 0 };
  let release;
  const calls = [];
  const body = (code) => psResult(code, "REVIEW", code === "PS-03"
    ? { review: { allowManualResult: allowed, status: state.saved, recordedBy: state.by, recordedAt: state.at } } : {});
  const fetchFn = vi.fn((input, init) => {
    const url = String(input);
    calls.push([init?.method, url, init?.body ? JSON.parse(init.body) : undefined]);
    const code = url.match(/\/ps\/([^/?]+)/)[1];
    if (init?.method === "POST") {
      const chosen = JSON.parse(init.body).status;
      if (post === "error" || !allowed.includes(chosen)) return json({ detail: "not allowed" }, 422);
      const done = () => {
        state.n += 1; state.saved = chosen; state.by = RECORDED_BY; state.at = `2026-09-26T0${5 + state.n}:00:00Z`;
        return json(body(code));
      };
      return post === "hold" ? new Promise((r) => { release = () => r(done()); }) : done();
    }
    return json(body(code));
  });
  vi.stubGlobal("fetch", fetchFn);
  return { calls, release: () => release() };
}

async function open(code = "PS-03") {
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderApp(`/monitor/ps/${code}?curriculumCode=C-1`);
  await screen.findByTestId("section-status");
}

const review = () => within(screen.getByTestId("section-review"));
const posts = (calls) => calls.filter(([m]) => m === "POST");

describe("PS-03 detail: ผลการตรวจของผู้ตรวจ (User Review)", () => {
  it("TEST 01: shows the review with the options the API sent; nothing saved yet", async () => {
    backend();
    await open();
    expect(review().getByTestId("review-saved")).toHaveTextContent("ยังไม่มีผลการตรวจของผู้ตรวจ");
    expect(review().getAllByRole("radio").map((r) => r.value)).toEqual(["PASS", "FAIL", "REVIEW"]);
    expect(review().getByTestId("review-save")).toBeDisabled();                 // nothing chosen yet
  });

  it("the options are the API's, not a list of the page's own", async () => {
    backend({ allowed: ["PASS", "REVIEW"] });
    await open();
    expect(review().getAllByRole("radio").map((r) => r.value)).toEqual(["PASS", "REVIEW"]);
  });

  it("a PS without a user review has no review section", async () => {
    backend();
    await open("PS-01");
    expect(screen.queryByTestId("section-review")).not.toBeInTheDocument();
  });

  it.each(["PASS", "FAIL", "REVIEW"])("TEST 02-05: %s is POSTed, then shown as the backend reads it back", async (chosen) => {
    const api = backend({ post: "hold" });
    await open();
    fireEvent.click(review().getByTestId(`review-option-${chosen}`));
    // chosen but not saved: only a local selection
    expect(review().getByTestId("review-saved")).toHaveTextContent("ยังไม่มีผลการตรวจของผู้ตรวจ");
    fireEvent.click(review().getByTestId("review-save"));
    expect(posts(api.calls)).toEqual([["POST", "/api/monitor/ps/PS-03/review?curriculumCode=C-1", { status: chosen }]]);
    expect(review().getByTestId("review-save")).toHaveTextContent("กำลังบันทึกผลการตรวจ…");
    expect(review().getByTestId("review-saved")).toHaveTextContent("ยังไม่มีผลการตรวจของผู้ตรวจ");   // not before success
    await act(async () => api.release());
    await waitFor(() => expect(review().getByTestId("review-saved")).toHaveTextContent(LABEL[chosen]));
    expect(review().getByTestId("recorded-by")).toHaveTextContent(RECORDED_BY.name);
    expect(review().getByTestId("recorded-at")).not.toHaveTextContent("");
    await waitFor(() => expect(review().getByTestId("review-save")).toHaveTextContent("บันทึกผลการตรวจ"));
    // the result shown is the reviewer's choice (2026-09-27); the engine's status is still shown next to it
    expect(screen.getByTestId("section-status").querySelector("[data-testid='status']")).toHaveAttribute("data-status", chosen);
    expect(screen.getByTestId("status-sources")).toHaveTextContent(`ระบบประเมินเบื้องต้น: REVIEW · ผู้ตรวจยืนยัน: ${chosen}`);
  });

  it("TEST 06: a refresh shows the saved review from the backend", async () => {
    backend();
    await open();
    fireEvent.click(review().getByTestId("review-option-FAIL"));
    fireEvent.click(review().getByTestId("review-save"));
    await waitFor(() => expect(review().getByTestId("review-saved")).toHaveTextContent(LABEL.FAIL));
    cleanup();
    await open();
    expect(review().getByTestId("review-saved")).toHaveTextContent(LABEL.FAIL);
  });

  it("TEST 09 / 25: an error keeps the saved review and says so", async () => {
    backend({ saved: "PASS", post: "error" });
    await open();
    expect(review().getByTestId("review-saved")).toHaveTextContent(LABEL.PASS);
    fireEvent.click(review().getByTestId("review-option-FAIL"));
    fireEvent.click(review().getByTestId("review-save"));
    expect(await review().findByTestId("review-error")).toHaveTextContent("บันทึกผลการตรวจไม่สำเร็จ กรุณาลองใหม่");
    expect(review().getByTestId("review-saved")).toHaveTextContent(LABEL.PASS);
    expect(review().getByTestId("review-save")).toBeEnabled();
  });

  it("TEST 08: saving again while a save is open sends one request", async () => {
    const api = backend({ post: "hold" });
    await open();
    fireEvent.click(review().getByTestId("review-option-PASS"));
    const save = review().getByTestId("review-save");
    fireEvent.click(save);
    fireEvent.click(save);
    fireEvent.click(save);
    expect(posts(api.calls)).toHaveLength(1);
    await act(async () => api.release());
  });
});
