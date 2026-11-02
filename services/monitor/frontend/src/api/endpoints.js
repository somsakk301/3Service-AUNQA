// Temporary API contract (TBD / SPEC GAP). Change endpoints here only.
const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const endpoints = {
  monitor: () => `${BASE}/monitor`,
  // POST only: saves the monitoring result (each PS's status now) in the Monitor-owned store.
  results: () => `${BASE}/monitor/results`,
  ps: (psCode) => `${BASE}/monitor/ps/${encodeURIComponent(psCode)}`,
  // POST only: records the user's verification in the Monitor-owned store (never source data).
  verification: (psCode) => `${BASE}/monitor/ps/${encodeURIComponent(psCode)}/verification`,
  // POST only: records the reviewer's choice for a PS the configuration has reviewed by the user.
  review: (psCode) => `${BASE}/monitor/ps/${encodeURIComponent(psCode)}/review`,
  // POST only: { username, password } -> { name }, sets the session cookie.
  login: () => `${BASE}/auth/login`,
  // POST only: clears the session cookie.
  logout: () => `${BASE}/auth/logout`,
};
