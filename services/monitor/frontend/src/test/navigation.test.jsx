import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { monitorBody, psResult } from "./fixtures";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.unstubAllGlobals());

const PS = ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06", "PS-07", "PS-08", "PS-09"];
const topbar = () => within(document.querySelector(".topbar"));
const psList = () => topbar().queryByRole("list", { name: "Programme Standards" });
/** Answers the overview and each PS detail with a result for that PS. */
const backend = () => mockFetch((url) => {
  const code = url.match(/\/ps\/([^?]+)/)?.[1];
  return jsonResponse(code ? psResult(decodeURIComponent(code)) : monitorBody());
});

describe("navigation hierarchy: AUN-QA › Programme Standards › PS-01…PS-09", () => {
  it("AUN-QA is the top level and opens the home page", () => {
    backend();
    renderApp("/");
    const brand = topbar().getByRole("link", { name: "AUN-QA Monitor" });
    expect(brand.getAttribute("href")).toBe("/");
    expect(brand).toHaveAttribute("aria-current", "page");
  });

  it("the top bar has no MONITOR item", async () => {
    backend();
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(topbar().queryByRole("link", { name: "MONITOR" })).not.toBeInTheDocument();
    expect(document.querySelector(".topbar").textContent).not.toContain("MONITOR");
  });

  it("the PS overview (/monitor/ps) still opens, from the home page's PS card", async () => {
    backend();
    renderApp("/");
    fireEvent.click(within(screen.getByTestId("home-card-ps")).getByRole("link", { name: "เปิดดู →" }));
    expect(await screen.findByTestId("card-PS-01")).toBeInTheDocument();
    expect(topbar().getByRole("link", { name: "AUN-QA Monitor" })).not.toHaveAttribute("aria-current");
  });

  it("the top bar shows no 'Programme Standards' text; the PS list keeps it as its accessible name", async () => {
    backend();
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(document.querySelector(".topbar").textContent).not.toContain("Programme Standards");
    expect(psList()).not.toBeNull(); // named "Programme Standards" for assistive technology only
    expect(topbar().queryByRole("link", { name: "Programme Standards" })).not.toBeInTheDocument();
  });

  it("inside Programme Standards, PS-01…PS-09 are listed under it, in order, linking to their detail pages", async () => {
    backend();
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    const list = psList();
    expect(list).not.toBeNull();
    const links = within(list).getAllByRole("link");
    expect(links.map((a) => a.textContent)).toEqual(PS);
    expect(links.map((a) => a.getAttribute("href"))).toEqual(PS.map((c) => `/monitor/ps/${c}`));
  });

  it("each PS link opens its existing detail page (PS-01…PS-09)", async () => {
    const fetchFn = backend();
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    for (const code of PS) {
      fireEvent.click(within(psList()).getByRole("link", { name: code }));
      expect(await screen.findByRole("heading", { level: 1, name: code })).toBeInTheDocument();
      expect(await screen.findByTestId("section-requirement")).toHaveTextContent(`req-${code}`);
      const link = within(psList()).getByRole("link", { name: code });
      expect(link).toHaveAttribute("aria-current", "page");
    }
    const urls = fetchFn.mock.calls.map(([u]) => String(u));
    for (const code of PS) expect(urls).toContain(`/api/monitor/ps/${code}`);
  });

  it.each(["/", "/monitor/p1"])("outside Programme Standards (%s) the top bar shows AUN-QA only", (path) => {
    backend();
    renderApp(path);
    expect(psList()).toBeNull();
    expect(topbar().getAllByRole("link").map((a) => a.textContent)).toEqual(["AUN-QA Monitor"]);
    expect(document.querySelector(".topbar").textContent).toBe("AUN-QA Monitorระบบติดตามความพร้อมหลักสูตร");
  });

  it("keeps ?curriculumCode= on every navigation link", async () => {
    backend();
    renderApp("/monitor/ps/PS-02?curriculumCode=C-1");
    await screen.findByTestId("section-requirement");
    const links = topbar().getAllByRole("link");
    expect(links.length).toBe(1 + PS.length); // AUN-QA + PS-01…PS-09
    for (const a of links) expect(a.getAttribute("href")).toMatch(/\?curriculumCode=C-1$/);
  });

  it("the menu needs no data: a detail page calls only its own endpoint", async () => {
    const fetchFn = mockFetch(() => jsonResponse(psResult("PS-02")));
    renderApp("/monitor/ps/PS-02");
    await screen.findByTestId("section-requirement");
    expect(fetchFn.mock.calls.map(([u]) => String(u))).toEqual(["/api/monitor/ps/PS-02"]);
  });

  it("uses links only (no buttons or form controls)", async () => {
    backend();
    renderApp("/monitor/ps");
    await screen.findByTestId("card-PS-01");
    expect(document.querySelector(".topbar").querySelectorAll("button, input, select, textarea, form, details")).toHaveLength(0);
  });
});

describe("routes (unchanged)", () => {
  const onHome = () => expect(topbar().getByRole("link", { name: "AUN-QA Monitor" })).toHaveAttribute("aria-current", "page");

  it("/monitor redirects to / and keeps the query", () => {
    backend();
    renderApp("/monitor?curriculumCode=C-1");
    onHome();
    expect(topbar().getByRole("link", { name: "AUN-QA Monitor" }).getAttribute("href")).toBe("/?curriculumCode=C-1");
  });

  it.each(["/monitor/p5", "/monitor/p6", "/monitor/p7", "/monitor/p9", "/somewhere-else"])("%s redirects to /", (path) => {
    backend();
    renderApp(path);
    onHome();
  });

  it.each(["/monitor/p1", "/monitor/p2", "/monitor/p3", "/monitor/p4", "/monitor/p8"])("%s still opens its notice page", (path) => {
    backend();
    renderApp(path);
    expect(screen.getByTestId("scope-notice")).toBeInTheDocument();
  });
});
