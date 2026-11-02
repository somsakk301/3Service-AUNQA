// TEST-ONLY fixtures shaped like the backend response. Placeholder values only.
export function psResult(code, status = "PASS", extra = {}) {
  return {
    psCode: code,
    status,
    requirement: `req-${code}`,
    checks: [`check-${code}`],
    dataSummary: [{ label: "Records", value: "3" }],
    dataFound: [{ label: "Group", items: ["item-1", "item-2"] }],
    verification: { found: 3, verified: null, approved: null },
    missingInformation: [],
    evidence: [],
    traceability: [],
    dataCompleteness: "complete",
    ...extra,
  };
}

export const ALL_CODES = Array.from({ length: 9 }, (_, i) => `PS-0${i + 1}`);

export function monitorBody(overrides = {}, statuses = []) {
  return {
    curriculum: { curriculumCode: "C-1", curriculumName: "Name-1", curriculumYear: null, version: "v1", status: null },
    overallStatus: null,
    dataCompleteness: "complete",
    results: ALL_CODES.map((c, i) => psResult(c, statuses[i] ?? "PASS")),
    ...overrides,
  };
}
