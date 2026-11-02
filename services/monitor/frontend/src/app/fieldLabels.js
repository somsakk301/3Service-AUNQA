/**
 * Thai labels of Data Schema fields ("collection.field"), used to name fields on the page (the source
 * table, summary labels, missing information). DISPLAY ONLY: never used to evaluate anything.
 * A field not listed here (e.g. _id, personId, curriculumId) is never named on the page.
 */
export const FIELD_LABELS = [
  ["educations.degree", "ระดับคุณวุฒิ"],
  ["educations.field", "สาขาวิชา"],
  ["academic_works.publicationYear", "ปีที่เผยแพร่"],
  ["curricula.curriculumYear", "ปีหลักสูตร"],
  ["appointments.appointmentOrder.orderNumber", "เลขที่คำสั่งแต่งตั้ง"],
  ["appointments.appointmentOrder.orderDate", "วันที่ออกคำสั่ง"],
  ["appointments.appointmentOrder", "คำสั่งแต่งตั้ง"],
  ["persons.hasTeachingExperience", "ประสบการณ์สอน"],
  ["appointments.roleName", "ชื่อบทบาท"],
  ["appointments.role", "บทบาท"],
  ["educations.institution", "สถาบันการศึกษา"],
  ["educations.graduationYear", "ปีที่สำเร็จการศึกษา"],
  ["academic_works.workType", "ประเภทผลงาน"],
  ["academic_works.database", "ฐานข้อมูลที่เผยแพร่"],
  ["academic_works.quartile", "Quartile"],
  ["appointments.effectiveDate", "วันที่เริ่มมีผล"],
  ["appointments.status", "สถานะการแต่งตั้ง"],
  ["curricula.curriculumCode", "รหัสหลักสูตร"],
  ["curricula.curriculumName", "ชื่อหลักสูตร"],
  ["persons.academicPosition", "ตำแหน่งทางวิชาการ"],
  ["documents.documentType", "ประเภทเอกสาร"],
  ["documents.fileName", "ชื่อไฟล์"],
];

const BY_KEY = new Map(FIELD_LABELS);

/** Thai label of a traced field, or null when it has none. */
export const fieldLabel = (collection, field) => BY_KEY.get(`${collection}.${field}`) ?? null;

/** A field named without its collection: its collection and Thai label, when exactly one entry has that field. */
export function findField(field) {
  const hits = FIELD_LABELS.filter(([key]) => key.slice(key.indexOf(".") + 1) === field);
  if (hits.length !== 1) return null;
  const [key, label] = hits[0];
  return { collection: key.slice(0, key.indexOf(".")), label };
}
