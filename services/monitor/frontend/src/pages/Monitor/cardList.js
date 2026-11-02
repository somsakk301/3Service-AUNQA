import { PS_GUIDELINE } from "../../app/psGuideline";

/**
 * DISPLAY ORDER ONLY. The PS codes of the guideline (PS-01…PS-09) form the base list; each takes
 * the backend's result object as it is when the backend sent one, and `result: null` when it did
 * not (the card then shows an empty state). Results the base list does not name follow in the
 * backend's order, so none is ever dropped. Only psCode is compared: no requirement, status, count
 * or rule is read or derived here.
 */
export function cardList(results, guideline = PS_GUIDELINE) {
  const used = new Set();
  const base = guideline.map(({ psCode }) => {
    const result = results.find((r) => r.psCode === psCode && !used.has(r)) ?? null;
    if (result) used.add(result);
    return { psCode, result };
  });
  const rest = results.filter((r) => !used.has(r)).map((r) => ({ psCode: r.psCode, result: r }));
  return [...base, ...rest];
}
