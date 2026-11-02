/**
 * Authentication (project owner, 2026-10-04): the login page, the signed-in name shown on every page, sign-out,
 * and a Manual Review save that is rejected (401) because no session covers it. AuthContext reads no network
 * (it only remembers what a login response already sent), so these are the only tests in the suite that exercise
 * it — no other test's fetch-call-count assertions are affected by its presence on every page.
 */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

const NAME = "ผู้ตรวจทดสอบ";

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function backend({ loginOk = true } = {}) {
  return mockFetch((url) => {
    if (url.includes("/api/auth/login")) {
      return loginOk ? jsonResponse({ name: NAME }) : jsonResponse({ detail: "Invalid username or password" }, 401);
    }
    if (url.includes("/api/auth/logout")) return jsonResponse({ ok: true });
    if (url.includes("/api/monitor/ps/")) return jsonResponse(psResult("PS-03", "REVIEW"));
    return jsonResponse(monitorBody());
  });
}

async function login() {
  renderApp("/login");
  fireEvent.change(screen.getByTestId("login-username"), { target: { value: "reviewer1" } });
  fireEvent.change(screen.getByTestId("login-password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByTestId("login-submit"));
}

describe("signed out", () => {
  it("shows a login link and no sign-out control", async () => {
    backend();
    renderApp("/");
    expect(await screen.findByTestId("login-link")).toBeInTheDocument();
    expect(screen.queryByTestId("logout")).not.toBeInTheDocument();
  });
});

describe("the login page", () => {
  it("on success, shows the signed-in name and returns to the PS overview", async () => {
    backend();
    await login();
    await waitFor(() => expect(screen.getByText(new RegExp(NAME))).toBeInTheDocument());
    expect(screen.getByTestId("logout")).toBeInTheDocument();
    expect(screen.queryByTestId("login-link")).not.toBeInTheDocument();
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();   // navigated to /monitor/ps
  });

  it("on a wrong username/password, shows an error and stays signed out", async () => {
    backend({ loginOk: false });
    await login();
    expect(await screen.findByTestId("login-error")).toBeInTheDocument();
    expect(screen.getByTestId("login-link")).toBeInTheDocument();
    expect(screen.queryByTestId("logout")).not.toBeInTheDocument();
  });
});

describe("signing out", () => {
  it("clears the signed-in name and shows the login link again", async () => {
    backend();
    await login();
    await waitFor(() => expect(screen.getByTestId("logout")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("logout"));
    await waitFor(() => expect(screen.getByTestId("login-link")).toBeInTheDocument());
    expect(screen.queryByTestId("logout")).not.toBeInTheDocument();
  });
});

describe("recording a review without a session", () => {
  it("shows a sign-in prompt instead of the generic save error", async () => {
    mockFetch((url) => {
      if (String(url).includes("/review")) return jsonResponse({ detail: "Login required" }, 401);
      return jsonResponse(psResult("PS-03", "REVIEW",
        { review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status: null, recordedBy: null, recordedAt: null } }));
    });
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderApp("/monitor/ps/PS-03");
    await screen.findByTestId("section-review");
    fireEvent.click(screen.getByTestId("review-option-PASS"));
    fireEvent.click(screen.getByTestId("review-save"));
    expect(await screen.findByTestId("review-unauthenticated")).toHaveTextContent("กรุณาเข้าสู่ระบบก่อนบันทึกผลการตรวจ");
    expect(screen.queryByTestId("review-error")).not.toBeInTheDocument();
  });
});

describe("Finding #3: a 401 from a protected API clears the displayed signed-in state", () => {
  it("a 401 on review save removes the signed-in name/sign-out and shows the login link again", async () => {
    // Signed in locally (AuthContext/localStorage) from an earlier, now-expired session — the backend is the
    // one source of truth, so this display state must not survive the backend's own 401.
    localStorage.setItem("mornitor:user", JSON.stringify({ name: NAME }));
    mockFetch((url) => {
      if (String(url).includes("/review")) return jsonResponse({ detail: "Login required" }, 401);
      return jsonResponse(psResult("PS-03", "REVIEW",
        { review: { allowManualResult: ["PASS", "FAIL", "REVIEW"], status: null, recordedBy: null, recordedAt: null } }));
    });
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderApp("/monitor/ps/PS-03");
    await screen.findByTestId("section-review");
    expect(screen.getByTestId("logout")).toBeInTheDocument();          // stale local state, shown before the save
    expect(screen.queryByTestId("login-link")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("review-option-PASS"));
    fireEvent.click(screen.getByTestId("review-save"));
    await screen.findByTestId("review-unauthenticated");

    expect(screen.queryByTestId("logout")).not.toBeInTheDocument();    // cleared by the 401, not by a manual logout
    expect(screen.getByTestId("login-link")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("mornitor:user") ?? "null")).toBeNull();
  });
});
