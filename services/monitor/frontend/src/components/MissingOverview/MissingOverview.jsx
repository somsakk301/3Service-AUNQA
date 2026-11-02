import { Link } from "react-router-dom";
import { missingText } from "../../app/missingText";

const PREVIEW_LINES = 3;

/** Missing information of every PS, grouped by PS in the backend's order; each line in plain Thai (missingText). */
export function MissingOverview({ results, search }) {
  const groups = results.filter((r) => r.missingInformation.length > 0);
  const total = groups.reduce((n, r) => n + r.missingInformation.length, 0);
  return (
    <section className="box" aria-labelledby="missing-h" data-testid="panel-missing">
      <h2 id="missing-h">ข้อมูลที่ยังขาด</h2>
      {total === 0 ? <p className="muted">ข้อมูลที่ใช้ตรวจสอบครบถ้วน</p> : (
        <>
          <p className="big-number">{total} รายการ</p>
          <ul className="missing-groups">
            {groups.map((r, i) => (
              <li key={`${i}-${r.psCode}`}>
                <span className="missing-groups__code">{r.psCode}</span>
                <ul className="list">
                  {r.missingInformation.slice(0, PREVIEW_LINES).map((m, j) => <li key={j}>{missingText(m)}</li>)}
                </ul>
                {r.missingInformation.length > PREVIEW_LINES && (
                  <Link className="more" to={`/monitor/ps/${encodeURIComponent(r.psCode)}${search}`}>ดูทั้งหมด →</Link>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
