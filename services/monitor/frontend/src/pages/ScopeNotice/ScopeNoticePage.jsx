import { Link } from "react-router-dom";
import { useCurriculumCode } from "../../app/curriculumParam";

/**
 * A section with no configuration yet. It calls no API and shows no status,
 * number or criterion content: only that there is no data for it.
 */
export function ScopeNoticePage({ label }) {
  const { search } = useCurriculumCode();
  return (
    <section className="box scope-notice" data-testid="scope-notice" aria-labelledby="scope-h">
      <h1 id="scope-h">{label}</h1>
      <p className="strong">ยังไม่มีข้อมูลสำหรับส่วนนี้</p>
      <p className="muted">
        ส่วนนี้ยังไม่อยู่ในขอบเขตการพัฒนาปัจจุบัน ระบบตรวจเฉพาะเกณฑ์ PS ตาม configuration ใน ps_requirements
        {" "}และยังไม่มี configuration ของ {label} ในฐานข้อมูล จึงไม่แสดงสถานะ ตัวเลข หรือข้อมูลใด ๆ
      </p>
      <Link className="more" to={`/${search}`}>← กลับหน้าแรก</Link>
    </section>
  );
}
