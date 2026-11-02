import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../app/App";

export function jsonResponse(body, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

/** Routes fake backend responses by URL substring; anything else is an unexpected call. */
export function mockFetch(handler) {
  const fn = vi.fn((input, _init) => handler(String(input)));
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function renderApp(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
