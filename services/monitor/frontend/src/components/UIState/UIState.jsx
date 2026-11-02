import { RETRY_MS } from "../../api/useRemote";

// kind: "loading" | "empty" | "incomplete" | "error" | "multiple"
const TEXT = {
  loading: "กำลังโหลดข้อมูล…",
  empty: "ยังไม่มีข้อมูล",
  incomplete: "ข้อมูลยังไม่ครบถ้วน",
  error: "ไม่สามารถโหลดข้อมูลการตรวจสอบได้",
  multiple: "พบหลายหลักสูตรในฐานข้อมูล",
};

const EVERY = `ทุก ${RETRY_MS / 1000} วินาที`;
const WAITING = {
  empty: `กำลังรอข้อมูลจากฐานข้อมูล เมื่อฝั่งนำเข้าข้อมูลบันทึกข้อมูลแล้ว หน้านี้จะแสดงผลเองโดยไม่ต้องโหลดหน้าใหม่ (ตรวจสอบ${EVERY})`,
  error: `ระบบจะลองใหม่อัตโนมัติ${EVERY}`,
  // The API answers 409 and does not list the curricula, so none is named here.
  multiple: `กรุณาระบุ curriculumCode ใน URL เช่น /monitor/ps?curriculumCode=<รหัสหลักสูตร> (ระบบตรวจสอบใหม่อัตโนมัติ${EVERY})`,
};

/** When the shown result was last read; the page keeps asking for a newer one. */
export function LastChecked({ checkedAt }) {
  return (
    <p className="last-checked" data-testid="last-checked">
      อัปเดตอัตโนมัติ{EVERY} · ตรวจสอบล่าสุด {checkedAt.toLocaleTimeString("th-TH")}
    </p>
  );
}

/** A page state. With `checkedAt`, the page is waiting and re-checks the database by itself. */
export function UIState({ kind, checkedAt }) {
  const isError = kind === "error";
  const waiting = checkedAt && WAITING[kind];
  return (
    <div className={`state state--${kind}`} role={isError ? "alert" : "status"} data-testid={`state-${kind}`}>
      <p>{TEXT[kind]}</p>
      {waiting && (
        <p className="state__note">
          {waiting} · ตรวจสอบล่าสุด {checkedAt.toLocaleTimeString("th-TH")}
        </p>
      )}
    </div>
  );
}
