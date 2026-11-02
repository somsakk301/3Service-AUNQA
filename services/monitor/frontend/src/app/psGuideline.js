/**
 * IDENTIFIERS ONLY: the PS codes of the active criteria in the configuration (PS-Config-v1.json,
 * `ps_requirements`), in order. Used as the base list for the navigation and for the MONITOR cards,
 * so PS-01…PS-09 always have a place even before the backend returns a result.
 *
 * It is NOT a source of truth for anything about a PS: no requirement, operation, status,
 * verification, evidence, missing information or traceability lives here. Those come from the
 * backend only; without a backend result the page says there is not enough data.
 * src/test/guideline.test.jsx fails if this list drifts from the configuration's PS codes.
 */
export const PS_GUIDELINE = [
  { psCode: "PS-01" },
  { psCode: "PS-02" },
  { psCode: "PS-03" },
  { psCode: "PS-04" },
  { psCode: "PS-05" },
  { psCode: "PS-06" },
  { psCode: "PS-07" },
  { psCode: "PS-08" },
  { psCode: "PS-09" },
];

/** What every data-dependent part says while there is no result yet. */
export const WAITING_TEXT = "กำลังรอข้อมูล";
export const UPLOAD_TEXT = "รอผู้ใช้อัปโหลดข้อมูล";
