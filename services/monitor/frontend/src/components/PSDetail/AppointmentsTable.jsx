/**
 * Per-record field completeness (app/psFindings.js: appointmentRecords — shown whenever the result has
 * this shape, not for a specific psCode): the name, whether the backend found it complete, and which
 * fields it listed as missing when it did not. Nothing here decides completeness; it restates the
 * backend's own "Records" dataFound group.
 */
export function AppointmentsTable({ records }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-base" data-testid="appointments-table">
        <thead>
          <tr className="border-b border-[#DDE8E2] text-left text-[#667085]">
            <th scope="col" className="py-2 pr-3 font-medium">ลำดับ</th>
            <th scope="col" className="py-2 pr-3 font-medium">รายการ</th>
            <th scope="col" className="py-2 pr-3 font-medium">สถานะ</th>
            <th scope="col" className="py-2 font-medium">ข้อมูลที่ขาด</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr key={i} className="border-b border-[#EAF5EF] last:border-0">
              <td className="py-2 pr-3 text-[#1F2937]">{i + 1}</td>
              <td className="py-2 pr-3 text-[#1F2937]">{r.name}</td>
              <td className="py-2 pr-3">
                {r.complete === null ? (
                  <span className="text-[#667085]">—</span>
                ) : r.complete ? (
                  <span className="text-[#2E7D5B]">ครบถ้วน</span>
                ) : (
                  <span className="text-[#C94A4A]">ไม่ครบถ้วน</span>
                )}
              </td>
              <td className="py-2 text-[#667085]">{r.missing ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
