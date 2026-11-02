import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptPSResult } from "../api/adapter";
import { ALL_CODES, monitorBody, psResult } from "./fixtures";
import { renderApp } from "./render";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// TEST-ONLY stand-in for the backend: GET answers with the current statuses and whatever it has saved; POST
// /results saves the current statuses (as the real backend does) with one time.
const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
const CURRENT = ["PASS", "PASS", "REVIEW", "PASS", "FAIL", "FAIL", "FAIL", "PASS", "PASS"];

function backend({ saved = null, post = "ok", reviews = {} } = {}) {
  const state = { saved, at: saved ? "2026-09-26T05:00:00Z" : null };
  let release;
  const calls = [];
  const body = () => monitorBody({ results: ALL_CODES.map((c, i) => psResult(c, CURRENT[i], {
    persistedResult: state.saved ? { status: state.saved[i], evaluatedAt: state.at } : null,
    ...(reviews[c] ? { review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status: reviews[c], reviewedAt: "2026-09-27T16:20:33Z" } } : {}),
  })) });
  vi.stubGlobal("fetch", vi.fn((input, init) => {
    calls.push([init?.method, String(input)]);
    if (init?.method === "POST") {
      if (post === "error") return json({ detail: "Unable to save the monitoring result" }, 503);
      const done = () => { state.saved = [...CURRENT]; state.at = "2026-09-26T06:00:00Z"; return json(body()); };
      return post === "hold" ? new Promise((r) => { release = () => r(done()); }) : done();
    }
    return json(body());
  }));
  return { calls, release: () => release() };
}

async function open() {
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderApp("/monitor/ps?curriculumCode=C-1");
  return within(await screen.findByTestId("section-persisted"));
}

const row = (box, code) => within(box.getByTestId(`persisted-${code}`));
const posts = (calls) => calls.filter(([m]) => m === "POST");
const when = (iso) => new Date(iso).toLocaleString("th-TH");   // matches components/PersistedResults/PersistedResults.jsx

describe("/monitor/ps: ผลการตรวจที่บันทึกไว้", () => {
  it("shows every PS as not saved before any save", async () => {
    backend();
    const box = await open();
    for (const c of ALL_CODES) expect(row(box, c).getByText("ยังไม่ได้บันทึก")).toBeInTheDocument();
  });

  it("TEST 01 / 02: POSTs to the backend, then shows what the backend saved", async () => {
    const api = backend({ post: "hold" });
    const box = await open();
    fireEvent.click(box.getByTestId("persist-save"));
    expect(posts(api.calls)).toEqual([["POST", "/api/monitor/results?curriculumCode=C-1"]]);
    expect(box.getByTestId("persist-save")).toBeDisabled();
    expect(row(box, "PS-01").getByText("ยังไม่ได้บันทึก")).toBeInTheDocument();          // not before success
    await act(async () => api.release());
    await waitFor(() => expect(row(box, "PS-05").getByTestId("status")).toHaveAttribute("data-status", "FAIL"));
    ALL_CODES.forEach((c, i) => expect(row(box, c).getByTestId("status")).toHaveAttribute("data-status", CURRENT[i]));
    await waitFor(() => expect(box.getByTestId("persist-save")).toHaveTextContent("บันทึกผลการตรวจของหลักสูตร"));
  });

  it("shows the current resolved status, not the raw saved snapshot, when they differ (app/psStatus.js)", async () => {
    backend({ saved: ["FAIL", ...CURRENT.slice(1)] });   // persistedResult.status: FAIL, but the current status is PASS
    const box = await open();
    expect(row(box, "PS-01").getByTestId("status")).toHaveAttribute("data-status", "PASS");
    expect(screen.getByTestId("card-PS-01").querySelector("[data-testid='status']")).toHaveAttribute("data-status", "PASS");
  });

  it("a review decides the status shown here exactly as it does on the card, even though persistedResult.status is the engine's REVIEW", async () => {
    // persistedResult.status stays REVIEW (the Rule Engine's snapshot); PS-03 has a saved review of PASS.
    const persisted = { status: "REVIEW", evaluatedAt: "2026-09-26T05:00:00Z" };
    const body = monitorBody({
      results: ALL_CODES.map((c, i) => psResult(c, CURRENT[i], {
        persistedResult: c === "PS-03" ? persisted : { status: CURRENT[i], evaluatedAt: persisted.evaluatedAt },
        ...(c === "PS-03" ? { review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status: "PASS", reviewedAt: "2026-09-27T16:20:33Z" } } : {}),
      })),
    });
    vi.stubGlobal("fetch", vi.fn(() => json(body)));
    const box = await open();
    expect(row(box, "PS-03").getByTestId("status")).toHaveAttribute("data-status", "PASS");   // resolved, not persistedResult.status (REVIEW)
    expect(screen.getByTestId("card-PS-03").querySelector("[data-testid='status']")).toHaveAttribute("data-status", "PASS");
    // the saved snapshot itself, and its saved time, are unchanged (not overwritten to match the resolved status)
    const ps03 = body.results.find((r) => r.psCode === "PS-03");
    expect(ps03.persistedResult).toEqual(persisted);
    expect(row(box, "PS-03").getByText(when(persisted.evaluatedAt))).toBeInTheDocument();
  });

  it("TEST 03: a refresh shows the saved result from the backend", async () => {
    backend();
    const box = await open();
    fireEvent.click(box.getByTestId("persist-save"));
    await waitFor(() => expect(row(box, "PS-03").getByTestId("status")).toHaveAttribute("data-status", "REVIEW"));
    cleanup();
    const again = await open();
    expect(row(again, "PS-03").getByTestId("status")).toHaveAttribute("data-status", "REVIEW");
  });

  it("TEST 14: an error shows the error and keeps the resolved status shown before (not persistedResult.status)", async () => {
    backend({ saved: ["FAIL", ...CURRENT.slice(1)], post: "error" });   // saved snapshot FAIL; current status PASS
    const box = await open();
    fireEvent.click(box.getByTestId("persist-save"));
    expect(await box.findByTestId("persist-error")).toHaveTextContent("บันทึกผลการตรวจไม่สำเร็จ กรุณาลองใหม่");
    expect(row(box, "PS-01").getByTestId("status")).toHaveAttribute("data-status", "PASS");
    expect(box.getByTestId("persist-save")).toBeEnabled();
  });

  it("TEST 11: clicking again while saving sends one request", async () => {
    const api = backend({ post: "hold" });
    const box = await open();
    const button = box.getByTestId("persist-save");
    fireEvent.click(button);
    fireEvent.click(button);
    expect(posts(api.calls)).toHaveLength(1);
    await act(async () => api.release());
  });

  // engine status, review.status (or none), persistedResult.status (the saved snapshot) -> expected status shown
  it.each([
    ["REVIEW", "PASS", "REVIEW", "PASS"],
    ["REVIEW", "FAIL", "REVIEW", "FAIL"],
    ["REVIEW", "REVIEW", "REVIEW", "REVIEW"],
    ["REVIEW", null, "REVIEW", "REVIEW"],
    ["PASS", null, "PASS", "PASS"],
    ["FAIL", null, "FAIL", "FAIL"],
    ["N/A", null, "N/A", "N/A"],
  ])("Case engine=%s review=%s persisted=%s -> %s", async (engine, review, persistedStatus, expected) => {
    const persisted = { status: persistedStatus, evaluatedAt: "2026-09-26T05:00:00Z" };
    const body = monitorBody({
      results: ALL_CODES.map((c, i) => psResult(c, i === 2 ? engine : CURRENT[i], {
        persistedResult: i === 2 ? persisted : { status: CURRENT[i], evaluatedAt: persisted.evaluatedAt },
        ...(i === 2 && review ? { review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status: review, reviewedAt: "2026-09-27T16:20:33Z" } } : {}),
      })),
    });
    vi.stubGlobal("fetch", vi.fn(() => json(body)));
    const box = await open();
    expect(row(box, "PS-03").getByTestId("status")).toHaveAttribute("data-status", expected);
    expect(body.results[2].persistedResult.status).toBe(persistedStatus);   // the snapshot itself is never mutated
  });

  it("after a successful save, a live review still decides the status shown (not the freshly-saved snapshot)", async () => {
    const api = backend({ post: "hold", reviews: { "PS-03": "PASS" } });   // engine REVIEW, review PASS throughout
    const box = await open();
    expect(row(box, "PS-03").getByText("ยังไม่ได้บันทึก")).toBeInTheDocument();
    fireEvent.click(box.getByTestId("persist-save"));
    await act(async () => api.release());   // the save succeeds; the backend's snapshot for PS-03 becomes REVIEW (CURRENT[2])
    await waitFor(() => expect(row(box, "PS-01").getByTestId("status")).toHaveAttribute("data-status", "PASS"));
    expect(row(box, "PS-03").getByTestId("status")).toHaveAttribute("data-status", "PASS");   // review, not the REVIEW snapshot just saved
    expect(screen.getByTestId("card-PS-03").querySelector("[data-testid='status']")).toHaveAttribute("data-status", "PASS");
  });
});

describe("adapter: persistedResult", () => {
  it.each([
    [{ status: "PASS", evaluatedAt: "2026-09-26T05:00:00Z" }, { status: "PASS", evaluatedAt: "2026-09-26T05:00:00Z" }],
    [null, null],
    [undefined, null],
    [{ status: "SAVED" }, null],
  ])("%o -> %o (never derived)", (sent, expected) => {
    expect(adaptPSResult(psResult("PS-01", "PASS", { persistedResult: sent })).persistedResult).toEqual(expected);
  });
});
