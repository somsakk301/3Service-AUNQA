import { Link } from "react-router-dom";
import { foundSentence } from "../../app/explain";
import { resolveStatus } from "../../app/psStatus";
import { requirementText } from "../../app/psTitles";
import { IssueBadge } from "../IssueBadge";
import { ResultText } from "../ResultText";
import { Status } from "../Status";
import { StatusSources } from "../StatusSources";

/**
 * One PS result in plain words: requirement → what the system found → result. No rule expression. The result shown
 * is the reviewer's choice the backend sent where there is one, with the engine's status beside it (as PS Detail).
 */
export function PSCard({ result, search }) {
  const { psCode } = result;
  const found = foundSentence(result);
  const requirement = requirementText(psCode, result.requirement);
  const headId = `card-${psCode}-h`;
  return (
    <article className="box card" data-testid={`card-${psCode}`}>
      <header className="card__head">
        <h3 id={headId}>{psCode}</h3>
        <span className="card__badges">
          <IssueBadge issue={result.issue} />
          <Status status={resolveStatus(result)} large />
        </span>
      </header>
      <div>
        <h4>สิ่งที่เกณฑ์ต้องการ</h4>
        {requirement ? <p>{requirement}</p> : <p className="muted">ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด</p>}
      </div>
      <div>
        <h4>สิ่งที่ระบบตรวจพบ</h4>
        {found ? <p>{found}</p> : <p className="muted">ยังไม่พบข้อมูลที่ใช้ตรวจสอบ</p>}
      </div>
      <div>
        <h4>ผลการตรวจสอบ</h4>
        <ResultText status={resolveStatus(result)} missing={result.missingInformation.length} />
        <StatusSources result={result} testId={`card-${psCode}-sources`} />
      </div>
      <Link className="more" to={`/monitor/ps/${encodeURIComponent(psCode)}${search}`} aria-describedby={headId}>ตรวจสอบรายละเอียด →</Link>
    </article>
  );
}
