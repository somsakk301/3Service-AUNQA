/**
 * HTTP client. GET reads; POST is issued only by `saveResults`, `verifyPS` and `reviewPS` (monitorApi.js) to record
 * what the user did in the Monitor-owned store. No other method exists here.
 */
export class ApiError extends Error {
  // kind: "network" | "http"
  constructor(kind, status) {
    super(kind === "http" ? `HTTP ${status}` : "Network error");
    this.kind = kind;
    this.status = status;
  }
}

async function requestJson(url, method, signal, body) {
  const init = body === undefined
    ? { method, headers: { Accept: "application/json" }, signal }
    : { method, headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify(body) };
  let res;
  try {
    res = await fetch(url, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("network");
  }
  if (!res.ok) throw new ApiError("http", res.status);
  try {
    return await res.json();
  } catch {
    throw new ApiError("http", res.status);
  }
}

export const getJson = (url, signal) => requestJson(url, "GET", signal);

export const postJson = (url, body) => requestJson(url, "POST", undefined, body);
