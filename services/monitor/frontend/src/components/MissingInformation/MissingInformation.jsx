import { missingText } from "../../app/missingText";

/** The backend's missing information, one line per item, each shown in plain Thai (see missingText). */
export function MissingInformation({ items }) {
  if (items.length === 0) return <p className="muted">ข้อมูลที่ใช้ตรวจสอบครบถ้วน</p>;
  return <ul className="list">{items.map((m, i) => <li key={i}>{missingText(m)}</li>)}</ul>;
}
