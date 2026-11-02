const show = (v) => (v === null ? "—" : typeof v === "boolean" ? (v ? "ใช่" : "ไม่ใช่") : String(v));
const when = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("th-TH");
};
const LABEL = {
  idle: "ยืนยันหลักฐาน / ผลการตรวจ",
  error: "ยืนยันหลักฐาน / ผลการตรวจ",
  saving: "กำลังบันทึกการยืนยัน…",
  saved: "บันทึกแล้ว กำลังอ่านสถานะจากระบบ…",
};

/**
 * The verification exactly as the backend sent it. "ตรวจสอบแล้ว" is shown only when the backend says so;
 * the button is offered only when the backend reports the PS as not verified yet (verified === false).
 * `action`: the state of the user's request ("idle" | "saving" | "saved" | "error"), never the verification itself.
 */
export function Verification({ value, onVerify, action = "idle" }) {
  return (
    <>
      <dl className="summary">
        <div><dt>พบข้อมูล</dt><dd>{show(value.found)}</dd></div>
        <div><dt>ตรวจสอบแล้ว</dt><dd data-testid="verified">{show(value.verified)}</dd></div>
        {value.verified === true && value.verifiedAt && (
          <div><dt>ยืนยันเมื่อ</dt><dd data-testid="verified-at">{when(value.verifiedAt)}</dd></div>
        )}
        <div><dt>อนุมัติแล้ว</dt><dd>{show(value.approved)}</dd></div>
      </dl>
      {onVerify && value.verified === false && (
        <div className="group">
          <button type="button" data-testid="verify-button" onClick={onVerify}
            disabled={action === "saving" || action === "saved"}>
            {LABEL[action]}
          </button>
          <p className="note">การยืนยันไม่เปลี่ยนผลการตรวจสอบ หลักฐาน หรือความพร้อมของหลักสูตร</p>
          {action === "error" && (
            <p className="note" role="alert" data-testid="verify-error">บันทึกการยืนยันไม่สำเร็จ กรุณาลองใหม่</p>
          )}
        </div>
      )}
    </>
  );
}
