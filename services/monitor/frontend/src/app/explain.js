/**
 * Turns the structured parts of a backend result into plain Thai for the reader.
 * DISPLAY ONLY: nothing here decides, changes or guesses a status. Each sentence restates the
 * fixed meaning of a value the backend sent (status, issue, summary label); when a value has
 * no safe meaning, the caller shows a fallback message instead. Nothing is specific to a PS.
 */
import { fieldLabel, findField } from "./fieldLabels";
import { sourceLabel } from "./sourceLabels";

// dataSummary labels the backend engine uses for placement (see components/DataFound/summaryLabels.js)
const CONDITION = "Condition";
const NOT_APPLICABLE = "Not applicable";

export const RESULT_TEXT = {
  PASS: "ผ่านเกณฑ์",
  FAIL: "ไม่ผ่านเกณฑ์",
  REVIEW: "ต้องตรวจสอบเพิ่มเติม",
  "N/A": "ไม่เข้าข่ายต้องตรวจ",
};

/** Thai names of the sources the backend read, unique, in the order read. */
export function sourcesRead(result) {
  return [...new Set(result.traceability.map((t) => sourceLabel(t.collection)))];
}

/** "ระบบพบข้อมูล N รายการจาก…" from verification.found and the traced sources, or null. */
export function foundSentence(result) {
  const n = result.verification.found;
  if (!(n > 0)) return null;
  const sources = sourcesRead(result);
  return sources.length ? `พบข้อมูล ${n} รายการจาก${sources.join(" และ")}` : `พบข้อมูล ${n} รายการ`;
}

/** What the criterion checks: the configured requirement, framed as a question. */
export function checkSentence(result) {
  if (!result.requirement) return null;
  return `ระบบตรวจสอบว่าข้อมูลของหลักสูตรเป็นไปตามข้อกำหนด “${result.requirement}” หรือไม่`;
}

const COMPARE = { ">=": "ไม่น้อยกว่า", "<=": "ไม่เกิน", ">": "มากกว่า", "<": "น้อยกว่า", "==": "เท่ากับ", "=": "เท่ากับ" };

/**
 * The decision condition: a count condition the backend sent as exactly "<operator> <number>", else an
 * ordering condition the backend describes in `checks`; null when neither is there.
 */
export function conditionSentence(result) {
  const item = result.dataSummary.find((i) => i.label === CONDITION);
  const m = item?.value.trim().match(/^(>=|<=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)$/);
  if (m) return `จำนวนที่ระบบนับได้ต้อง${COMPARE[m[1]]} ${m[2]}`;
  const ordered = orderingCondition(result);
  if (!ordered) return null;
  const what = findField(ordered.field ?? "")?.label ?? "ค่า";
  return `${what}สูงสุดที่ระบบตีความได้ต้องไม่ต่ำกว่า “${ordered.minimum}” (ลำดับจากต่ำไปสูง: ${ordered.ordering.join(" < ")})`;
}

/** The values of one `checks` line "<key>: <JSON values, comma separated>", or null. */
function checkValues(result, key) {
  const line = result.checks.find((c) => c.startsWith(`${key}: `));
  if (!line) return null;
  try {
    return JSON.parse(`[${line.slice(key.length + 2)}]`);
  } catch {
    return null;
  }
}

/**
 * An at-least comparison by an ordering, as the backend describes its configuration in `checks`
 * ("<block>.field", "<block>.minimum", "<block>.ordering"): { field, minimum, ordering } or null.
 * Only restates what the backend sent; nothing is compared here.
 */
export function orderingCondition(result) {
  const blocks = result.checks.map((c) => c.match(/^([^:\s]+)\.minimum: /)?.[1]).filter(Boolean);
  for (const block of blocks) {
    const [minimum] = checkValues(result, `${block}.minimum`) ?? [];
    const ordering = checkValues(result, `${block}.ordering`);
    const [field] = checkValues(result, `${block}.field`) ?? [];
    if (typeof minimum === "string" && Array.isArray(ordering) && ordering.length > 1
        && ordering.every((v) => typeof v === "string") && ordering.includes(minimum)) {
      return { field: typeof field === "string" ? field : null, minimum, ordering };
    }
  }
  return null;
}

// One judged subject of an ordering comparison, as the backend writes it in dataFound:
// "<field>: <value> → <ordering value>; <value> → not in the ordering (highest '<v>' is at least|below '<min>') -> STATUS"
const RANKED = /^([^:]+): (.+?)(?: \(highest '(.+)' is (?:at least|below) '(.+)'\))? -> (PASS|FAIL|REVIEW|N\/A)$/;
const READ_AS = /^(.+) → (.+)$/;
const NOT_RANKED = "not in the ordering";

/**
 * The per-subject results of an ordering comparison, read from dataFound exactly as the backend sent them:
 * [{ name, field, values: [{ value, level }], highest, status }] with `level`/`highest` null when the backend
 * gave none. Null when dataFound is not in that form (every other kind of result keeps its own display).
 * The status of each subject is the backend's; nothing here ranks, compares or decides.
 */
export function rankedResults(result) {
  const out = [];
  for (const g of result.dataFound) {
    const m = g.items.length === 1 ? g.items[0].match(RANKED) : null;
    const pairs = m ? m[2].split("; ").map((p) => p.match(READ_AS)) : [];
    if (!m || pairs.some((p) => !p)) return null;
    out.push({
      name: g.label,
      field: m[1],
      values: pairs.map((p) => ({ value: p[1], level: p[2] === NOT_RANKED ? null : p[2] })),
      highest: m[3] ?? null,
      status: m[5],
    });
  }
  return out.length ? out : null;
}

// One piece of information shown to a reviewer, as the backend writes it in dataFound: "<name>: <values> -> STATUS",
// where <name> is a configuration key whose `<name>.source` is listed in checks; "no value found" when there is none.
const SHOWN = /^([A-Za-z][A-Za-z0-9]*): (.+) -> (?:PASS|FAIL|REVIEW|N\/A)$/;
const NO_VALUE = "no value found";

/**
 * What the reviewer is shown when the user decides the result (the backend sent a review): each subject with
 * [{ label, value }] rows, labelled by the Thai name of the field the configuration names as the source; a value the
 * source lacks is null. Null when dataFound is not in that form. DISPLAY ONLY: nothing is judged or compared here.
 */
export function reviewedInformation(result) {
  if (!result.review || result.dataFound.length === 0) return null;
  const subjects = [];
  for (const g of result.dataFound) {
    const rows = [];
    for (const item of g.items) {
      const m = item.match(SHOWN);
      const [source] = (m && checkValues(result, `${m[1]}.source`)) || [];
      const dot = typeof source === "string" ? source.indexOf(".") : -1;
      if (dot < 1) return null;
      const field = source.slice(dot + 1);
      rows.push({ label: fieldLabel(source.slice(0, dot), field) ?? field, value: m[2] === NO_VALUE ? null : m[2] });
    }
    subjects.push({ name: g.label, rows });
  }
  return subjects;
}

/** How many source records the backend traced, per source (Thai name), in the order read. Display counts only. */
export function recordsBySource(result) {
  const counts = new Map();
  for (const t of result.traceability) {
    const name = sourceLabel(t.collection);
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts].map(([source, count]) => ({ source, count }));
}

/** A backend summary label in Thai, or null when it is not shown in the data section. */
export function summaryLabel(label) {
  if (label === CONDITION || label === NOT_APPLICABLE) return null;
  if (label === "Subjects" || label === "Records checked") return "จำนวนรายการที่ตรวจ";
  if (label === "Records with missing fields") return "รายการที่ข้อมูลไม่ครบ";
  const subjects = label.match(/^Subjects (PASS|FAIL|REVIEW|N\/A)$/);
  if (subjects) return `รายการที่${RESULT_TEXT[subjects[1]]}`;
  if (/ count$/.test(label)) return "จำนวนที่ระบบนับได้";
  return findField(label)?.label ?? "ข้อมูลเพิ่มเติม";
}

/**
 * Names of what the backend checked, from dataFound: a group labelled with a traced field or
 * collection lists the records themselves; any other group is labelled with one checked item.
 * The group items that describe how an item was judged are never shown.
 */
export function checkedNames(result) {
  const fields = new Set(result.traceability.flatMap((t) => t.fields));
  const collections = new Set(result.traceability.map((t) => t.collection));
  const names = result.dataFound.flatMap((g) => {
    if (g.items.length === 0) return []; // e.g. a counted field with no record: its label is not a name
    if (fields.has(g.label) || collections.has(g.label)) return g.items;
    return g.label === "Records" ? [] : [g.label];
  });
  return [...new Set(names)];
}
