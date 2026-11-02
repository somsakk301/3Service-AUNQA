/**
 * LOCKED DISPLAY TEXT, decided by the product owner (2026-09-25): what each criterion requires, so
 * PS-01…PS-09 always tell the reader what they are about, even before the backend sends a result.
 * This is a deliberate exception to "the frontend holds no requirement" (SRS §11/§12/§31).
 *
 * The API stays the source of truth: its requirement is always shown when it sends one; this text is
 * used only when it does not. It is never used to evaluate, count or decide anything.
 * src/test/psTitles.test.jsx fails if a text drifts from the configuration's requirement.
 */
export const PS_TITLES = {
  "PS-01": "หลักสูตรต้องมีอาจารย์ผู้รับผิดชอบหลักสูตรอย่างน้อย 5 คน",
  "PS-02": "อาจารย์ผู้รับผิดชอบหลักสูตรต้องมีสถานะอาจารย์ประจำ",
  "PS-03": "อาจารย์ผู้รับผิดชอบหลักสูตรต้องไม่รับผิดชอบเกิน 1 หลักสูตร",
  "PS-04": "หลักสูตรต้องมีคำสั่งแต่งตั้งและระบุบทบาทการบริหารหลักสูตรอย่างชัดเจน",
  "PS-05": "อาจารย์ผู้รับผิดชอบหลักสูตรต้องมีคุณวุฒิสูงสุดอย่างน้อยระดับปริญญาโท",
  "PS-06": "คุณวุฒิของอาจารย์สัมพันธ์กับสาขาของหลักสูตร",
  "PS-07": "อาจารย์ผู้รับผิดชอบหรืออาจารย์ประจำหลักสูตรต้องมีผลงานวิชาการย้อนหลัง 5 ปี",
  "PS-08": "อาจารย์พิเศษต้องมีคุณวุฒิและประสบการณ์ที่เหมาะสม",
  "PS-09": "หลักสูตรต้องมีการปรับปรุงล่าสุดไม่เกิน 5 ปี",
};

/** The requirement to show: the API's text when it sent one, else the locked text, else null (not enough data). */
export function requirementText(psCode, apiRequirement) {
  return apiRequirement || PS_TITLES[psCode] || null;
}

/**
 * LOCKED DISPLAY TEXT for a criterion the user decides (decided by the lecturer, 2026-09-29): the wording of its
 * review. Display only: the statuses offered and saved stay the API's `review.allowManualResult`; an option with no
 * label here is shown by its status. A PS not listed keeps the generic review wording.
 */
export const PS_REVIEW_TEXT = {
  "PS-06": {
    title: "การยืนยันความสัมพันธ์ของคุณวุฒิ",
    instruction: "กรุณาตรวจสอบข้อมูลคุณวุฒิและยืนยันว่ามีความสัมพันธ์กับหลักสูตรหรือไม่",
    question: "คุณวุฒินี้มีความสัมพันธ์กับหลักสูตรหรือไม่?",
    options: { PASS: "มีความสัมพันธ์", FAIL: "ไม่มีความสัมพันธ์" },
    pending: "รอการยืนยันจากผู้ใช้",
    condition: "ผู้ใช้เป็นผู้ยืนยันว่าคุณวุฒิของอาจารย์มีความสัมพันธ์กับหลักสูตรหรือไม่ ระบบไม่ตัดสินความสัมพันธ์เอง",
  },
};

/** The review wording of a PS, or null for the generic wording. */
export function reviewText(psCode) {
  return PS_REVIEW_TEXT[psCode] ?? null;
}
