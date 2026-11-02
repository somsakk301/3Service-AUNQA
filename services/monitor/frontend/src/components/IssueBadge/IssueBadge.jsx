// Shown next to a status when the backend reports why nothing could be decided (SRS §48/§50).
// Display text only: the frontend never sets or changes an issue.
const TEXT = {
  configuration_error: "Configuration Error",
  evaluation_error: "Evaluation Error",
  spec_gap: "Spec Gap",
};

const HINT = {
  configuration_error: "Configuration ของเกณฑ์นี้ผิดรูปแบบหรือไม่ครบ ต้องแก้ config ก่อน สถานะนี้จึงยังไม่ใช่ผลตรวจข้อมูล",
  evaluation_error: "ระบบประมวลผลเกณฑ์นี้ไม่สำเร็จ (เกณฑ์อื่นไม่ได้รับผลกระทบ) แจ้งผู้พัฒนาพร้อมข้อความใน Missing Information",
  spec_gap: "Configuration ขอสิ่งที่ Specification ยังไม่กำหนด ดูรายละเอียดใน Missing Information",
};

export function IssueBadge({ issue }) {
  if (!issue || !TEXT[issue]) return null;
  return (
    <span className={`issue issue--${issue}`} data-testid="issue" title={HINT[issue]}>
      {TEXT[issue]}
    </span>
  );
}
