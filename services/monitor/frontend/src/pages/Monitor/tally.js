/**
 * Counts over the results the backend returned. Counting only: no formula, threshold,
 * percentage or status is derived here. A verification count is null when every value it
 * counts is null, i.e. the backend has no source for it.
 */
const count = (results, pred) => results.filter(pred).length;
const noVerification = (results) => results.every((r) => r.verification.verified === null);

// A curriculum document is evidence of every PS, so an item with a reference is counted once;
// an item without a reference cannot be matched and counts on its own.
function evidenceCount(results) {
  const items = results.flatMap((r) => r.evidence);
  const referenced = new Set(items.filter((e) => e.reference !== null).map((e) => e.reference));
  return referenced.size + items.filter((e) => e.reference === null).length;
}

export function tally(results) {
  const unverifiable = noVerification(results);
  return {
    evidence: evidenceCount(results),
    verified: unverifiable ? null : count(results, (r) => r.verification.verified === true),
    pending: unverifiable ? null : count(results, (r) => r.verification.verified === false),
    complete: count(results, (r) => r.dataCompleteness === "complete"),
    incomplete: count(results, (r) => r.dataCompleteness === "incomplete"),
  };
}
