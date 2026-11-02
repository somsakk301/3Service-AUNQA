import { RESULT_TEXT } from "../../app/explain";

// Thai wording of the status the backend sent. Display only: the status itself is never derived here.
export function ResultText({ status, missing }) {
  return (
    <>
      <p className="strong">{RESULT_TEXT[status] ?? "ยังไม่มีผลการตรวจสอบ"}</p>
      {missing > 0 && <p className="muted">ยังขาดข้อมูล {missing} รายการ</p>}
    </>
  );
}
