import { countByStatus } from "../../app/psStatus";
import { STATUSES } from "../../types/monitoring";
import { Status } from "../Status";

/**
 * Status counts tallied from the results the backend returned, by the status each PS card shows (app/psStatus.js).
 * Readiness (percentage, PASS count, total) and the overall status are shown only as the backend supplies them:
 * none is derived here.
 */
export function ProgrammeReadiness({ results, overallStatus, readiness }) {
  const counts = countByStatus(results);
  return (
    <section className="box readiness-hero" aria-labelledby="readiness-h" data-testid="panel-readiness">
      <h2 id="readiness-h">ความพร้อมของหลักสูตร</h2>
      <div className="readiness-hero__top">
        <div className="readiness-hero__figure">
          <span className="label">ความพร้อมโดยรวม</span>
          {readiness ? (
            <>
              <span className="readiness-hero__percent" data-testid="readiness-value">{readiness.percentage}%</span>
              <span className="readiness-hero__count" data-testid="readiness-count">
                {readiness.passCount} จาก {readiness.totalPS} เกณฑ์
              </span>
            </>
          ) : <span className="big-number" data-testid="readiness-none">—</span>}
        </div>
        <div>
          <span className="label">ผลรวม</span>
          {overallStatus ? <Status status={overallStatus} large /> : <span className="big-number" data-testid="overall-none">—</span>}
        </div>
      </div>
      {readiness && (
        <div className="progress-bar" role="presentation">
          <div className="progress-bar__fill" style={{ width: `${Math.min(100, Math.max(0, readiness.percentage))}%` }} />
        </div>
      )}
      <div className="readiness">
        <ul className="counts">
          {STATUSES.map((s) => (
            <li key={s}>
              <Status status={s} />
              <strong data-testid={`count-${s}`}>{counts[s]}</strong>
            </li>
          ))}
        </ul>
      </div>
      {!readiness && !overallStatus && <p className="note">ระบบยังไม่ได้ส่งค่าความพร้อมมา จึงยังแสดงเป็นค่าว่าง</p>}
    </section>
  );
}
