import { findField } from "../../app/fieldLabels";
import { RESULT_TEXT } from "../../app/explain";
import { Status } from "../Status";

/**
 * The result of each judged subject of an ordering comparison, exactly as the backend sent it (see
 * `rankedResults`): the values it read and the ordering value each stands for, the highest one the backend named,
 * and the backend's status. DISPLAY ONLY: nothing is ranked, compared or decided here; a missing value is "—".
 */
export function SubjectResults({ subjects }) {
  return (
    <ul className="subjects" data-testid="subject-results">
      {subjects.map((s, i) => {
        const what = findField(s.field)?.label ?? "ค่า";
        return (
          <li key={i} data-testid="subject">
            <div className="subject-head">
              <span className="subject-name">{s.name}</span>
              <Status status={s.status} />
            </div>
            <dl className="meta">
              <div><dt>{what}สูงสุดที่ระบบตีความได้</dt><dd data-testid="subject-highest">{s.highest ?? "—"}</dd></div>
              <div><dt>ผลการตรวจสอบ</dt><dd data-testid="subject-result">{RESULT_TEXT[s.status] ?? "—"}</dd></div>
            </dl>
            <h4>{what}ที่พบ</h4>
            <ul className="list" data-testid="subject-values">
              {s.values.map((v, j) => (
                <li key={j}>{v.value} → {v.level ?? "ระบบตีความระดับไม่ได้"}</li>
              ))}
            </ul>
          </li>
        );
      })}
    </ul>
  );
}
