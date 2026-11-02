import { NavLink } from "react-router-dom";
import { PS_GUIDELINE } from "../../app/psGuideline";
import { Status } from "../Status";

// Sidebar entries with no page behind them yet in this app (no route, no backend): shown disabled
// rather than as a dead link or an invented page.
const SOON = [
  { key: "evidence", label: "Evidence" },
  { key: "missing", label: "Missing Information" },
  { key: "import", label: "นำเข้าข้อมูล" },
  { key: "settings", label: "ตั้งค่า" },
];

/**
 * Left navigation for the PS-01 dashboard layout. PS-01…PS-09 are the same codes and the same order
 * as the existing top-bar navigation (app/psGuideline.js); `statusByCode` (psCode -> Status | null) is
 * supplied by the page from a real backend result — a code with no entry shows no badge, never a
 * guessed one.
 */
export function PSSidebar({ psCode, search, statusByCode = {} }) {
  return (
    <nav aria-label="Programme Standards" className="w-64 shrink-0 border-r border-[#DDE8E2] bg-white px-3 py-6">
      <NavLink
        to={`/${search}`}
        className="flex min-h-[44px] items-center rounded-md px-3 text-base font-medium text-[#1F2937] hover:bg-[#EAF5EF]"
      >
        ภาพรวม
      </NavLink>
      <p className="mt-4 px-3 text-sm font-semibold uppercase tracking-wide text-[#667085]">AUN-QA Criteria</p>
      <p className="mt-3 px-3 text-sm font-semibold uppercase tracking-wide text-[#667085]">Programme Standards</p>
      <ul className="mt-1">
        {PS_GUIDELINE.map(({ psCode: code }) => {
          const active = code === psCode;
          const status = statusByCode[code] ?? null;
          return (
            <li key={code}>
              <NavLink
                to={`/monitor/ps/${encodeURIComponent(code)}${search}`}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-[44px] items-center justify-between rounded-md px-3 text-base ${
                  active ? "bg-[#EAF5EF] font-semibold text-[#205B43]" : "text-[#1F2937] hover:bg-[#EAF5EF]"
                }`}
              >
                <span>{code}</span>
                {status && <Status status={status} />}
              </NavLink>
            </li>
          );
        })}
      </ul>
      <ul className="mt-4 border-t border-[#DDE8E2] pt-4">
        {SOON.map((item) => (
          <li key={item.key} className="flex min-h-[44px] items-center justify-between rounded-md px-3 text-base text-[#9CA3AF]">
            <span>{item.label}</span>
            <span className="rounded-full bg-[#F7FAF8] px-2 py-0.5 text-sm text-[#667085]">เร็วๆ นี้</span>
          </li>
        ))}
      </ul>
    </nav>
  );
}
