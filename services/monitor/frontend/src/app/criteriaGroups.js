/**
 * Sections shown on the home page, in display order.
 * โครงสร้างเมนูเท่านั้น ห้ามใส่ PS code, requirement, สถานะ หรือตัวเลข
 * (Menu structure only: never add a PS code, requirement, status or number here.)
 * `inScope: false` sections have no configuration yet and only show a notice.
 */
export const CRITERIA_GROUPS = [
  { key: "p1", label: "P1", title: null, description: null, inScope: false },
  { key: "p2", label: "P2", title: null, description: null, inScope: false },
  { key: "p3", label: "P3", title: null, description: null, inScope: false },
  { key: "p4", label: "P4", title: null, description: null, inScope: false },
  { key: "p8", label: "P8", title: null, description: null, inScope: false },
  { key: "ps", label: "PS", title: "Programme Standards", description: "เกณฑ์มาตรฐานที่ใช้ตรวจสอบข้อมูลของหลักสูตร", inScope: true },
];

export const PS_GROUP = CRITERIA_GROUPS.find((g) => g.key === "ps");
