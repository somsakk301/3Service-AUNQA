import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { psResult } from "./fixtures";
import { renderApp } from "./render";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// TEST-ONLY stand-in for the backend: GET answers with what it holds; POST /verification records it.
const EVIDENCE = [{ label: "TEST-1.pdf", reference: "ref-1", storage: "local", path: "test-data/documents/original/TEST-1.pdf" }];
const json = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));

function backend({ verified = false, post = "ok", keepGetUnverified = false } = {}) {
  const state = { verified };
  let release;
  const calls = [];
  const body = () => psResult("PS-01", "FAIL", {
    evidence: EVIDENCE,
    verification: { found: 3, verified: state.verified, approved: null,
      verifiedAt: state.verified === true ? "2026-09-26T05:00:00Z" : null },
  });
  const fetchFn = vi.fn((input, init) => {
    const url = String(input);
    calls.push([init?.method, url]);
    if (init?.method === "POST") {
      if (post === "error") return json({ detail: "Unable to save the verification" }, 503);
      const done = () => { if (!keepGetUnverified) state.verified = true; return json(body()); };
      return post === "hold" ? new Promise((r) => { release = () => r(done()); }) : done();
    }
    return json(body());
  });
  vi.stubGlobal("fetch", fetchFn);
  return { calls, release: () => release() };
}

async function open() {
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderApp("/monitor/ps/PS-01?curriculumCode=C-1");
  return within(await screen.findByTestId("section-verification"));
}

const posts = (calls) => calls.filter(([m]) => m === "POST");

describe("PS detail: การยืนยันข้อมูล", () => {
  it("TEST 01 / 02: shows the verification and the evidence before verifying", async () => {
    backend();
    const box = await open();
    expect(box.getByTestId("verified")).toHaveTextContent("ไม่ใช่");
    expect(box.getByTestId("verify-button")).toHaveTextContent("ยืนยันหลักฐาน / ผลการตรวจ");
    const evidence = within(screen.getByTestId("section-evidence"));
    expect(evidence.getByTestId("evidence-path")).toHaveTextContent("test-data/documents/original/TEST-1.pdf");
  });

  it("TEST 03 / 04: POSTs to the backend, then shows verified only as the backend reads it back", async () => {
    const api = backend({ post: "hold" });
    const box = await open();
    fireEvent.click(box.getByTestId("verify-button"));
    expect(posts(api.calls)).toEqual([["POST", "/api/monitor/ps/PS-01/verification?curriculumCode=C-1"]]);
    // while the request is open nothing says verified
    expect(box.getByTestId("verified")).toHaveTextContent("ไม่ใช่");
    expect(box.getByTestId("verify-button")).toBeDisabled();
    expect(box.getByTestId("verify-button")).toHaveTextContent("กำลังบันทึกการยืนยัน…");
    const getsBefore = api.calls.filter(([m]) => m === "GET").length;
    await act(async () => api.release());
    await waitFor(() => expect(box.getByTestId("verified")).toHaveTextContent("ใช่"));
    expect(api.calls.filter(([m]) => m === "GET").length).toBeGreaterThan(getsBefore);   // read back by GET
    expect(box.getByTestId("verified-at")).not.toHaveTextContent("");
    expect(box.queryByTestId("verify-button")).not.toBeInTheDocument();
  });

  it("TEST 04: a successful POST alone never shows verified; only the backend's GET does", async () => {
    backend({ keepGetUnverified: true });
    const box = await open();
    fireEvent.click(box.getByTestId("verify-button"));
    await waitFor(() => expect(box.getByTestId("verify-button")).toHaveTextContent("บันทึกแล้ว กำลังอ่านสถานะจากระบบ…"));
    expect(box.getByTestId("verified")).toHaveTextContent("ไม่ใช่");
  });

  it("TEST 05: an API error shows the error and not verified; the user may try again", async () => {
    backend({ post: "error" });
    const box = await open();
    fireEvent.click(box.getByTestId("verify-button"));
    expect(await box.findByTestId("verify-error")).toHaveTextContent("บันทึกการยืนยันไม่สำเร็จ กรุณาลองใหม่");
    expect(box.getByTestId("verified")).toHaveTextContent("ไม่ใช่");
    expect(box.getByTestId("verify-button")).toBeEnabled();
  });

  it("TEST 06: clicking again while saving sends one request", async () => {
    const api = backend({ post: "hold" });
    const box = await open();
    const button = box.getByTestId("verify-button");
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(posts(api.calls)).toHaveLength(1);
    await act(async () => api.release());
  });

  it("TEST 07 / 11: status and evidence read the same after verifying", async () => {
    const api = backend();
    const box = await open();
    const before = [screen.getByTestId("section-status").textContent, screen.getByTestId("section-evidence").textContent];
    fireEvent.click(box.getByTestId("verify-button"));
    await waitFor(() => expect(box.getByTestId("verified")).toHaveTextContent("ใช่"));
    expect([screen.getByTestId("section-status").textContent, screen.getByTestId("section-evidence").textContent]).toEqual(before);
    expect(posts(api.calls)).toHaveLength(1);
  });

  it("already verified: shown from the backend, no button, approved stays —", async () => {
    backend({ verified: true });
    const box = await open();
    expect(box.getByTestId("verified")).toHaveTextContent("ใช่");
    expect(box.getByText("อนุมัติแล้ว").nextSibling).toHaveTextContent("—");
    expect(box.queryByTestId("verify-button")).not.toBeInTheDocument();
  });

  it("no verification source (verified null): no button", async () => {
    backend({ verified: null });
    const box = await open();
    expect(box.getByTestId("verified")).toHaveTextContent("—");
    expect(box.queryByTestId("verify-button")).not.toBeInTheDocument();
  });
});

// SET 4, 5, 6: the only non-GET requests are the POSTs to the Monitor-owned store (verification, review, results),
// plus login/logout (project owner, 2026-10-04: Authentication) — the session cookie, not monitoring_results.
describe("the only non-GET requests are the verification, review, results and auth POSTs", () => {
  const src = join(process.cwd(), "src");
  const files = readdirSync(src, { recursive: true }).map(String)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.startsWith("test"));

  it("postJson is used by saveResults, verifyPS, reviewPS, login and logout alone, and no other method is named", () => {
    const callers = files.filter((f) => /postJson\(/.test(readFileSync(join(src, f), "utf8")));
    expect(callers.sort()).toEqual(["api/authApi.js", "api/monitorApi.js"]);
    expect(readFileSync(join(src, "api/client.js"), "utf8"))
      .toMatch(/export const postJson = \(url, body\) => requestJson\(url, "POST", undefined, body\)/);
    const api = readFileSync(join(src, "api/monitorApi.js"), "utf8");
    expect(api.match(/postJson\(/g)).toHaveLength(3);
    expect(api).toMatch(/postJson\(withCurriculum\(endpoints\.results\(\), curriculumCode\)\)/);
    expect(api).toMatch(/postJson\(withCurriculum\(endpoints\.verification\(psCode\)/);
    expect(api).toMatch(/postJson\(withCurriculum\(endpoints\.review\(psCode\)/);
    const auth = readFileSync(join(src, "api/authApi.js"), "utf8");
    expect(auth.match(/postJson\(/g)).toHaveLength(2);
    expect(auth).toMatch(/postJson\(endpoints\.login\(\)/);
    expect(auth).toMatch(/postJson\(endpoints\.logout\(\)\)/);
    for (const f of files) expect(readFileSync(join(src, f), "utf8")).not.toMatch(/["'](PUT|PATCH|DELETE)["']/);
  });
});
