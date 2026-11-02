// Thai names of the Data Schema collections. DISPLAY ONLY: never used to evaluate anything.
export const SOURCE_LABELS = {
  curricula: "ข้อมูลหลักสูตร",
  persons: "ข้อมูลอาจารย์",
  educations: "ข้อมูลคุณวุฒิ",
  appointments: "ข้อมูลการแต่งตั้ง",
  academic_works: "ข้อมูลผลงานวิชาการ",
  documents: "ข้อมูลเอกสาร",
  data_usages: "ข้อมูลการใช้งานข้อมูล",
  generated_documents: "เอกสารที่ระบบสร้าง",
};

/** Thai name of a collection, or the collection's own name when it has none. */
export const sourceLabel = (collection) => SOURCE_LABELS[collection] ?? collection;
