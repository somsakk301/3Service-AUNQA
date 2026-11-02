/**
 * One line of the backend's missingInformation, in plain Thai. PRESENTATION ONLY: called at render
 * time on a copy of the text; the data the page received is never changed, and every backend line
 * is still shown as exactly one line (the count stays the backend's).
 *
 * A line is rewritten only when it matches, from start to end, one of the fixed messages the backend
 * engine writes (backend/app/monitoring/engine.py, subject_checks.py) and every collection or field in
 * it has a Thai label; the Thai sentence restates that message and nothing more. A line with no Latin
 * script is already in the reader's language and is shown as sent. Anything else (SPEC GAP,
 * configuration or evaluation errors, configuration keys, unknown messages) is not safe to rephrase,
 * so it says there is not enough data to show the detail. No status, count or rule is derived here.
 */
import { findField } from "./fieldLabels";
import { SOURCE_LABELS } from "./sourceLabels";

export const NOT_ENOUGH = "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด";

const source = (collection) => SOURCE_LABELS[collection] ?? null;
const OBJECT_ID = /^[0-9a-f]{24}$/;

/** A record's display name without its database ids; null when only an id or a technical note is left. */
function recordName(shown) {
  const name = shown.replace(/\s*\([0-9a-f]{24}\)/g, "").trim();
  return name === "" || OBJECT_ID.test(name) || /[A-Za-z]\.[A-Za-z]/.test(name) ? null : name;
}

/** "<record>: <sentence>" when the record has a name, otherwise a sentence about "a record". */
function aboutRecord(shown, sentence, unnamed) {
  const name = recordName(shown);
  return name ? `${name}: ${sentence}` : unnamed;
}

// [backend message, Thai sentence | null when a name in it has no Thai label]
const MESSAGES = [
  [/^no (\w+) records were found$/, ([c]) => source(c) && `ไม่พบ${source(c)}`],
  [/^no (\w+) record is selected, so nothing can be checked$/,
    ([c]) => source(c) && `ไม่พบ${source(c)}ที่ตรงกับเงื่อนไขของเกณฑ์นี้ จึงยังตรวจสอบไม่ได้`],
  [/^(\d+) record\(s\) lack a usable ([\w.]+)$/, ([n, f]) => {
    const field = findField(f);
    return field && source(field.collection) && `พบ${source(field.collection)} ${n} รายการที่ไม่มี${field.label}ที่ระบบใช้ตรวจสอบได้`;
  }],
  [/^no usable ([\w.]+) value$/, ([f]) => findField(f) && `ไม่พบ${findField(f).label}ที่ระบบใช้ตรวจสอบได้`],
  [/^(.+): ([\w.]+) is missing or not an integer$/, ([who, f]) => {
    const label = findField(f)?.label;
    const sentence = label && `ไม่พบข้อมูล${label} หรือข้อมูล${label}ไม่อยู่ในรูปแบบที่ระบบตรวจสอบได้`;
    return sentence && aboutRecord(who, sentence, sentence);
  }],
  // a required field is absent from a record (the backend names the record, then the field)
  [/^(.+): ([\w.]+)$/, ([who, f]) => {
    const label = findField(f)?.label;
    return label && aboutRecord(who, `ไม่มีข้อมูล${label}`, `มีรายการที่ไม่มีข้อมูล${label}`);
  }],
];

// Lines that report what the configuration or the engine must fix: not data a reader can act on.
const NOT_DATA = ["SPEC GAP: ", "Configuration error: ", "Evaluation error: "];

export function missingText(line) {
  if (NOT_DATA.some((prefix) => line.startsWith(prefix))) return NOT_ENOUGH;
  for (const [pattern, toThai] of MESSAGES) {
    const m = line.match(pattern);
    if (m) return toThai(m.slice(1)) || NOT_ENOUGH;
  }
  return /[A-Za-z]/.test(line) ? NOT_ENOUGH : line;
}
