/** Data completeness: the response's own flag, then PS counted by their dataCompleteness. */
export function Completeness({ overall, counts }) {
  return (
    <section className="box" aria-labelledby="completeness-h" data-testid="panel-completeness">
      <h2 id="completeness-h">ความครบถ้วนของข้อมูล</h2>
      <dl className="stat-bar">
        <div><dt>ภาพรวม</dt><dd>{overall === "incomplete" ? "ยังไม่ครบถ้วน" : "ครบถ้วน"}</dd></div>
        <div><dt>ข้อมูลครบ</dt><dd>{counts.complete} เกณฑ์</dd></div>
        <div><dt>ข้อมูลไม่ครบ</dt><dd>{counts.incomplete} เกณฑ์</dd></div>
      </dl>
    </section>
  );
}
