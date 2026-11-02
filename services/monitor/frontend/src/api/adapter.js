/**
 * Adapter Layer: maps the temporary backend contract into the frontend types.
 * It only normalises shape (missing arrays, nulls). It never computes a status,
 * completeness or any business value.
 */
import { ISSUES, STATUSES } from "../types/monitoring";

const str = (v) => (v === null || v === undefined ? null : String(v));
const arr = (v) => (Array.isArray(v) ? v : []);
const bool = (v) => (typeof v === "boolean" ? v : null);
const status = (v) => (STATUSES.includes(v) ? v : null);
const completeness = (v) => (v === "incomplete" ? "incomplete" : "complete");
// An unrecognised issue stays null; it is never mapped to another issue.
const issue = (v) => (ISSUES.includes(v) ? v : null);
const values = (v) =>
  v && typeof v === "object" && !Array.isArray(v)
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [String(k), x === null || x === undefined ? "—" : String(x)]))
    : {};
// Who recorded a review: the backend's session identity, as sent; anything else (missing, partial) -> null,
// never a partial or guessed identity.
const recordedBy = (v) =>
  v && typeof v === "object" && typeof v.userId === "string" && typeof v.name === "string"
    ? { userId: v.userId, name: v.name }
    : null;
// The user review of a PS the configuration has reviewed by the user, as sent; absent -> null. The options are
// the API's list (config allowManualResult), never a list of our own; an unknown status is dropped, not mapped.
const review = (v) =>
  v && typeof v === "object" && !Array.isArray(v)
    ? { allowManualResult: arr(v.allowManualResult).filter((s) => STATUSES.includes(s)), status: status(v.status),
        recordedBy: recordedBy(v.recordedBy), recordedAt: str(v.recordedAt) }
    : null;
// The status saved for this PS (Persistent Monitoring Result), as sent; absent or unknown -> null.
const persisted = (v) =>
  v && typeof v === "object" && status(v.status) ? { status: status(v.status), evaluatedAt: str(v.evaluatedAt) } : null;
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
// Programme Readiness exactly as the backend computed it; anything incomplete is null, never recomputed.
const programmeReadiness = (v) => {
  if (!v || typeof v !== "object") return null;
  const r = { percentage: num(v.percentage), passCount: num(v.passCount), totalPS: num(v.totalPS) };
  return Object.values(r).includes(null) ? null : r;
};

export function adaptPSResult(raw) {
  const verification = raw.verification ?? {};
  return {
    psCode: String(raw.psCode ?? ""),
    // An unrecognised status stays null; it is never mapped to another status.
    status: status(raw.status),
    requirement: str(raw.requirement),
    checks: Array.isArray(raw.checks) ? raw.checks.map(String) : [],
    dataSummary: arr(raw.dataSummary).map((i) => ({ label: String(i.label), value: String(i.value) })),
    dataFound: arr(raw.dataFound).map((g) => ({
      label: String(g.label),
      items: Array.isArray(g.items) ? g.items.map(String) : [],
    })),
    verification: {
      found: typeof verification.found === "number" ? verification.found : null,
      verified: bool(verification.verified),
      approved: bool(verification.approved),
      verifiedAt: str(verification.verifiedAt),
    },
    missingInformation: Array.isArray(raw.missingInformation) ? raw.missingInformation.map(String) : [],
    evidence: arr(raw.evidence).map((e) => ({
      label: String(e.label),
      reference: str(e.reference),
      storage: str(e.storage),
      path: str(e.path),
    })),
    traceability: arr(raw.traceability).map((t) => ({
      collection: String(t.collection),
      recordId: String(t.recordId),
      fields: Array.isArray(t.fields) ? t.fields.map(String) : [],
      values: values(t.values),
    })),
    dataCompleteness: completeness(raw.dataCompleteness),
    issue: issue(raw.issue),
    review: review(raw.review),
    persistedResult: persisted(raw.persistedResult),
  };
}

export function adaptMonitor(raw) {
  const c = raw.curriculum;
  const curriculum = c
    ? {
        curriculumCode: str(c.curriculumCode),
        curriculumName: str(c.curriculumName),
        curriculumYear: str(c.curriculumYear),
        version: str(c.version),
        status: str(c.status),
      }
    : null;
  return {
    curriculum,
    overallStatus: status(raw.overallStatus),
    programmeReadiness: programmeReadiness(raw.programmeReadiness),
    dataCompleteness: completeness(raw.dataCompleteness),
    results: arr(raw.results).map(adaptPSResult),
  };
}
