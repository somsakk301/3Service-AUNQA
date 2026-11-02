import { Link } from "react-router-dom";
import { UPLOAD_TEXT, WAITING_TEXT } from "../../app/psGuideline";
import { requirementText } from "../../app/psTitles";

// "waiting": the database has no data yet. "no-result": the backend sent results, but none for this
// PS; why is not known here, so the card only says there is no result (never a status of its own).
const TEXT = {
  waiting: { tag: WAITING_TEXT, found: UPLOAD_TEXT, result: WAITING_TEXT },
  "no-result": { tag: "—", found: "ยังไม่มีข้อมูลจากระบบสำหรับเกณฑ์นี้", result: "ยังไม่มีผลการตรวจสอบ" },
};

/**
 * A PS card without a result from the backend: its code, its locked requirement text (see psTitles.js)
 * and an empty state for everything the backend decides.
 */
export function GuideCard({ psCode, search, variant = "waiting" }) {
  const headId = `guide-${psCode}-h`;
  const text = TEXT[variant];
  const requirement = requirementText(psCode, null);
  return (
    <article className="box card card--waiting" data-testid={`guide-${psCode}`}>
      <header className="card__head">
        <h3 id={headId}>{psCode}</h3>
        <span className="wait-tag" title={text.result}>{text.tag}</span>
      </header>
      <div>
        <h4>สิ่งที่เกณฑ์ต้องการ</h4>
        {requirement ? <p>{requirement}</p> : <p className="muted">ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด</p>}
      </div>
      <div>
        <h4>สิ่งที่ระบบตรวจพบ</h4>
        <p className="muted">{text.found}</p>
      </div>
      <div>
        <h4>ผลการตรวจสอบ</h4>
        <p className="muted">{text.result}</p>
      </div>
      <Link className="more" to={`/monitor/ps/${encodeURIComponent(psCode)}${search}`} aria-describedby={headId}>ตรวจสอบรายละเอียด →</Link>
    </article>
  );
}
