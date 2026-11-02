const show = (n) => (n === null ? "—" : n);

/** Evidence and verification counts, from `tally` (counts of backend values only). */
export function EvidenceStatus({ counts }) {
  return (
    <section className="box" aria-labelledby="evidence-h" data-testid="panel-evidence">
      <h2 id="evidence-h">สถานะหลักฐาน</h2>
      <dl className="stat-lines">
        <div><dt>พบหลักฐาน</dt><dd>{counts.evidence}</dd></div>
        <div><dt>ตรวจสอบแล้ว</dt><dd>{show(counts.verified)}</dd></div>
        <div><dt>รอการตรวจสอบ</dt><dd>{show(counts.pending)}</dd></div>
      </dl>
      {counts.evidence === 0 && <p className="note">ยังไม่มีข้อมูลหลักฐาน</p>}
      {counts.verified === null && <p className="note">ระบบยังไม่ได้ส่งสถานะการตรวจสอบหลักฐานมา</p>}
    </section>
  );
}
