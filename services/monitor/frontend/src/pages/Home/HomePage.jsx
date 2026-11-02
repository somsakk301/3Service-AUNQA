import { Link } from "react-router-dom";
import { CRITERIA_GROUPS } from "../../app/criteriaGroups";
import { useCurriculumCode } from "../../app/curriculumParam";

/** Home: choose a section. Calls no API and shows no status or number. */
export function HomePage() {
  const { search } = useCurriculumCode();
  return (
    <>
      <h1 className="page-title">เลือกส่วนที่ต้องการดู</h1>
      <div className="group-grid">
        {CRITERIA_GROUPS.map((g) => (
          <article key={g.key} className="box home-card" data-testid={`home-card-${g.key}`}>
            <h2 id={`home-${g.key}-h`}>{g.label}</h2>
            {g.title && <p className="strong">{g.title}</p>}
            {g.description && <p>{g.description}</p>}
            <p className="muted">{g.inScope ? "เปิดดูผลการตรวจสอบได้" : "ยังไม่มีข้อมูลสำหรับส่วนนี้"}</p>
            <Link className="more" to={`/monitor/${g.key}${search}`} aria-describedby={`home-${g.key}-h`}>เปิดดู →</Link>
          </article>
        ))}
      </div>
    </>
  );
}
