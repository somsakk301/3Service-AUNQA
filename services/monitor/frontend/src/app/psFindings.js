/**
 * Which extra, structured display (if any) a PS's result supports, decided from the SHAPE of what the
 * backend sent — never from psCode. Two shapes the active configuration produces are recognised:
 *   - a plain count of named subjects (e.g. PS-01: a dataSummary label ending " count"; CountMeasure)
 *   - a per-record field-presence check (e.g. PS-04: a dataFound group literally labelled "Records";
 *     FieldsPresentMeasure, engine.py _fields_present)
 * Any other shape returns null for both: the page shows no extra table, relying on FoundData alone.
 * DISPLAY ONLY: nothing here decides a status; it only restates text already in the API response.
 */
import { checkedNames, rankedResults, reviewedInformation } from "./explain";
import { fieldLabel } from "./fieldLabels";

const COUNT_LABEL = / count$/;
const RECORD_LINE = /^(.+) \(([^()]+)\): (complete|missing .+)$/;
const RECORD_COLLECTION = "appointments"; // the only collection PS-04-shaped field-presence checks target today

/** A missing-fields list, by Thai label (app/fieldLabels.js) — never the raw field name (e.g. personId). */
function missingLabels(csv) {
  const labels = csv.split(", ").map((f) => fieldLabel(RECORD_COLLECTION, f)).filter((l) => l !== null);
  return labels.length ? labels.join(", ") : "ข้อมูลอ้างอิงภายในระบบ";
}

/** The names of a plain count of subjects (PS-01-shaped), or null when the result is some other shape. */
export function rosterNames(result) {
  if (rankedResults(result) || reviewedInformation(result)) return null;
  if (!result.dataSummary.some((i) => COUNT_LABEL.test(i.label))) return null;
  const names = checkedNames(result);
  return names.length > 0 ? names : null;
}

/**
 * Per-record field completeness (PS-04-shaped), parsed from the "Records" dataFound group exactly as
 * engine.py's FieldsPresentMeasure writes each line ("<name> (<id>): complete" or "<name> (<id>):
 * missing <fields>"): [{ name, id, complete, missing }], missing fields restated by their Thai label
 * (never the raw field name). Null when there is no such group, or when a line does not match the
 * expected shape — never a partial or guessed reading, same as rankedResults.
 */
export function appointmentRecords(result) {
  const group = result.dataFound.find((g) => g.label === "Records");
  if (!group) return null;
  const records = [];
  for (const item of group.items) {
    const m = item.match(RECORD_LINE);
    if (!m) return null;
    const complete = m[3] === "complete";
    records.push({ name: m[1], id: m[2], complete, missing: complete ? null : missingLabels(m[3].replace(/^missing /, "")) });
  }
  return records;
}
