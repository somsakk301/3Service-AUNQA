const DASH = "—";

/**
 * The named subjects a plain-count PS result counted (app/psFindings.js: rosterNames — shown whenever
 * the result has that shape, not for a specific psCode). Such a count criterion traces only the field
 * it counts, never an academic position, a per-person status or a date, so those columns stay "—"
 * rather than a guessed value; which columns apply is the same for any PS of this shape.
 */
export function RosterTable({ names }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-base" data-testid="roster-table">
        <thead>
          <tr className="border-b border-[#DDE8E2] text-left text-[#667085]">
            <th scope="col" className="py-2 pr-3 font-medium">ลำดับ</th>
            <th scope="col" className="py-2 pr-3 font-medium">ชื่อ-สกุล</th>
            <th scope="col" className="py-2 pr-3 font-medium">ตำแหน่งทางวิชาการ</th>
            <th scope="col" className="py-2 pr-3 font-medium">สถานะ</th>
            <th scope="col" className="py-2 font-medium">วันที่เริ่มรับผิดชอบ</th>
          </tr>
        </thead>
        <tbody>
          {names.map((name, i) => (
            <tr key={i} className="border-b border-[#EAF5EF] last:border-0">
              <td className="py-2 pr-3 text-[#1F2937]">{i + 1}</td>
              <td className="py-2 pr-3 text-[#1F2937]">{name}</td>
              <td className="py-2 pr-3 text-[#667085]">{DASH}</td>
              <td className="py-2 pr-3 text-[#667085]">{DASH}</td>
              <td className="py-2 text-[#667085]">{DASH}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-sm text-[#667085]">
        ตำแหน่งทางวิชาการ สถานะรายบุคคล และวันที่เริ่มรับผิดชอบ: ข้อมูลไม่เพียงพอ (เกณฑ์นี้ไม่ได้อ่านหรือบันทึกค่าเหล่านี้)
      </p>
    </div>
  );
}
