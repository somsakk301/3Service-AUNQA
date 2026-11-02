const FIELDS = [
  ["curriculumName", "ชื่อหลักสูตร"],
  ["curriculumCode", "รหัสหลักสูตร"],
  ["curriculumYear", "ปีหลักสูตร"],
  ["version", "เวอร์ชัน"],
  ["status", "สถานะ"],
];

/** Curriculum fields from the backend; a null field is not shown. */
export function CurriculumBox({ curriculum }) {
  const present = FIELDS.filter(([key]) => curriculum[key] !== null);
  return (
    <section className="box" aria-label="ข้อมูลหลักสูตร" data-testid="panel-curriculum">
      <dl className="meta">
        {present.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{curriculum[key]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
