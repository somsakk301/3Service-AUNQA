import { resolveStatus } from "../../app/psStatus";
import { Status } from "../Status";

const when = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("th-TH");
};
const LABEL = {
  idle: "บันทึกผลการตรวจของหลักสูตร",
  error: "บันทึกผลการตรวจของหลักสูตร",
  saving: "กำลังบันทึกผลการตรวจ…",
  saved: "บันทึกแล้ว กำลังอ่านผลจากระบบ…",
};

/**
 * Persistent Monitoring Result: which PS have a saved snapshot, and when (`persistedResult.evaluatedAt`), as the
 * API sends it. The status column shows the same resolved status as everywhere else (app/psStatus.js) so a PS
 * with a user review is not shown by its engine snapshot alone; `persistedResult.status` itself is never read or
 * changed here. `action`: the state of the save request.
 */
export function PersistedResults({ results, onSave, action = "idle" }) {
  return (
    <section className="box" aria-labelledby="persisted-h" data-testid="section-persisted">
      <h2 id="persisted-h">ผลการตรวจที่บันทึกไว้</h2>
      <table className="trace-table">
        <thead><tr><th>เกณฑ์</th><th>ผลที่บันทึก</th><th>บันทึกเมื่อ</th></tr></thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={`${i}-${r.psCode}`} data-testid={`persisted-${r.psCode}`}>
              <td>{r.psCode}</td>
              <td>{r.persistedResult ? <Status status={resolveStatus(r)} /> : "ยังไม่ได้บันทึก"}</td>
              <td>{r.persistedResult?.evaluatedAt ? when(r.persistedResult.evaluatedAt) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="group">
        <button type="button" data-testid="persist-save" onClick={onSave} disabled={action === "saving" || action === "saved"}>
          {LABEL[action]}
        </button>
        <p className="note">
          ผลที่บันทึกคือสถานะที่ระบบตรวจได้ ณ เวลาที่บันทึก และจะไม่เปลี่ยนเมื่อข้อมูลต้นทางเปลี่ยน จนกว่าจะบันทึกใหม่ (บันทึกใหม่จะแทนผลเดิม)
          · ผลปัจจุบันอยู่ในภาพรวมเกณฑ์ด้านบน
        </p>
        {action === "error" && (
          <p className="note" role="alert" data-testid="persist-error">บันทึกผลการตรวจไม่สำเร็จ กรุณาลองใหม่</p>
        )}
      </div>
    </section>
  );
}
