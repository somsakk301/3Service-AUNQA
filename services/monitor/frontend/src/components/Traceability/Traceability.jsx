import { fieldLabel } from "../../app/fieldLabels";
import { sourceLabel } from "../../app/sourceLabels";

const VISIBLE_RECORDS = 10;

/**
 * Which data was used from one record, by Thai label. Raw stored values (often codes such as role
 * keys) are not shown to the reader; fields without a label are internal references.
 */
function usedData(t) {
  const labels = [...new Set(t.fields.map((f) => fieldLabel(t.collection, f)).filter((l) => l !== null))];
  return labels.length ? labels.join(", ") : "ข้อมูลอ้างอิงภายในระบบ";
}

function Rows({ items, offset }) {
  return items.map((t, i) => (
    <tr key={offset + i}>
      <td>{sourceLabel(t.collection)}</td>
      <td>รายการที่ {offset + i + 1}<span className="ref">รหัสอ้างอิง {t.recordId}</span></td>
      <td>{usedData(t)}</td>
    </tr>
  ));
}

function Table({ items, offset }) {
  return (
    <table className="trace-table">
      <thead><tr><th scope="col">แหล่งข้อมูล</th><th scope="col">รายการ</th><th scope="col">ข้อมูลที่ใช้ตรวจสอบ</th></tr></thead>
      <tbody><Rows items={items} offset={offset} /></tbody>
    </table>
  );
}

/** Each source record the backend read and which of its data was used, in plain words. */
export function Traceability({ items }) {
  if (items.length === 0) return <p className="muted">ยังไม่มีข้อมูลแหล่งที่มา</p>;
  const rest = items.slice(VISIBLE_RECORDS);
  return (
    <>
      <Table items={items.slice(0, VISIBLE_RECORDS)} offset={0} />
      {rest.length > 0 && (
        <details className="more-details">
          <summary>แสดงทั้งหมด ({items.length})</summary>
          <Table items={rest} offset={VISIBLE_RECORDS} />
        </details>
      )}
    </>
  );
}
