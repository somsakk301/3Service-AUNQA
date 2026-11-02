/**
 * THE PS status of the frontend (project owner, 2026-09-27). Every badge, text, explanation and count of a PS result
 * goes through `resolveStatus`: the reviewer's choice the backend sent (review.status) where there is a valid one,
 * else the engine's status (`status`). Display only: nothing is decided here, no PS is named, the backend's values are
 * kept as sent, and no readiness is computed from it (the backend sends programmeReadiness / generationReadiness).
 */
import { STATUSES } from "../types/monitoring";

const reviewed = (result) => (STATUSES.includes(result?.review?.status) ? result.review.status : null);

/** The status shown and counted for one PS result: PASS / FAIL / REVIEW / N/A, or null when there is none. */
export function resolveStatus(result) {
  return reviewed(result) ?? result?.status ?? null;
}

/** When a review decides what is shown, both sources for the reader: { engine, reviewer }; otherwise null. */
export function statusSources(result) {
  const reviewer = reviewed(result);
  return reviewer ? { engine: result.status ?? null, reviewer } : null;
}

/** How many results resolve to each status, keyed PASS / FAIL / REVIEW / N/A (display counts only). */
export function countByStatus(results) {
  return Object.fromEntries(STATUSES.map((s) => [s, results.filter((r) => resolveStatus(r) === s).length]));
}
