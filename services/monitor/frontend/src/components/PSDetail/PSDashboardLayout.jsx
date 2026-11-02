import { resolveStatus, statusSources } from "../../app/psStatus";
import { appointmentRecords, rosterNames } from "../../app/psFindings";
import { CurriculumBox } from "../CurriculumBox";
import { Evidence } from "../Evidence";
import { FoundData } from "../FoundData";
import { IssueBadge } from "../IssueBadge";
import { MissingInformation } from "../MissingInformation";
import { PSSidebar } from "../PSSidebar";
import { ResultText } from "../ResultText";
import { Section } from "../Section";
import { SourceReference } from "../SourceReference";
import { Status } from "../Status";
import { StatusSources } from "../StatusSources";
import { Traceability } from "../Traceability";
import { UIState } from "../UIState";
import { UserReview } from "../UserReview";
import { Verification } from "../Verification";
import { AppointmentsTable } from "./AppointmentsTable";
import { RosterTable } from "./RosterTable";

const NOT_ENOUGH = (text) => <p className="muted">{text}</p>;
const WAITING = (upload = false) => <p className="muted">กำลังรอข้อมูล{upload ? " · รอผู้ใช้อัปโหลดข้อมูล" : ""}</p>;

const TABS = [
  { href: "#overview", label: "ภาพรวม" },
  { href: "#data", label: "ข้อมูลที่ใช้ตรวจสอบ" },
  { href: "#source-reference", label: "เกณฑ์จากเอกสารต้นทาง" },
  { href: "#status", label: "ผลการตรวจสอบ" },
  { href: "#evidence", label: "หลักฐาน" },
  { href: "#traceability", label: "แหล่งอ้างอิง" },
];

/** The one extra, data-shape-driven display under "ข้อมูลที่พบ" (app/psFindings.js) — not a psCode branch. */
function SpecificTable({ result }) {
  const roster = rosterNames(result);
  if (roster) {
    return (
      <div className="rounded-lg border border-[#DDE8E2] bg-white p-4">
        <h3 className="text-sm font-semibold text-[#1F2937]">รายชื่อที่เกี่ยวข้อง</h3>
        <div className="mt-3"><RosterTable names={roster} /></div>
      </div>
    );
  }
  const records = appointmentRecords(result);
  if (records) {
    return (
      <div className="rounded-lg border border-[#DDE8E2] bg-white p-4">
        <h3 className="text-sm font-semibold text-[#1F2937]">ความครบถ้วนของข้อมูลการแต่งตั้ง</h3>
        <div className="mt-3"><AppointmentsTable records={records} /></div>
      </div>
    );
  }
  return null;
}

/**
 * Shared dashboard layout for every PS Detail page (project owner's UI reference, 2026-10-03; originally
 * built for PS-01 alone, then generalised so PS-01…PS-09 share one layout, not nine copies). It reuses
 * the same `resolveStatus`/`checkSentence`/etc. derivations and the very same Section/Evidence/
 * Traceability/Verification/MissingInformation/UserReview/FoundData components every PS already used —
 * nothing here decides a status, a count or a readiness value, and nothing branches on which PS this is:
 * the one extra table (if any) is chosen from the shape of `result` (psFindings.js), not from `psCode`.
 *
 * Layout note: this renders inside the shared `.page` container (Layout.jsx, max-width 1120px), which
 * this file does not touch, so the sidebar + 2-column body sit within that width rather than the full
 * browser width a standalone dashboard shell would use.
 */
export function PSDashboardLayout({
  result, psCode, search, waiting, requirement, check, sources, condition, onVerify, action, statusByCode, checkedAt,
  reviewed, curriculum, wording, reviewAction, onReview,
}) {
  const status = resolveStatus(result);
  return (
    <div className="-mx-4 flex flex-col gap-6 border border-[#DDE8E2] bg-white lg:-mx-6 lg:flex-row lg:gap-0">
      <PSSidebar psCode={psCode} search={search} statusByCode={statusByCode} />
      <div id="overview" className="min-w-0 flex-1 px-4 py-6 lg:px-8">
        <nav aria-label="Breadcrumb" className="text-base text-[#667085]">
          <span>Programme Standards</span> <span aria-hidden="true">›</span> <span className="text-[#1F2937]">{psCode}</span>
        </nav>
        <div className="mt-2 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 lg:max-w-xl">
            <p className="text-[28px] font-bold text-[#1F2937]">{psCode}</p>
            <div className="mt-2">
              <Section id="requirement" testId="section-requirement" title="สิ่งที่เกณฑ์ต้องการ">
                {requirement ? <p>{requirement}</p> : NOT_ENOUGH("ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด")}
              </Section>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-lg border border-[#DDE8E2] bg-white px-4 py-3">
              <p className="text-sm text-[#667085]">สถานะ</p>
              <div className="mt-1 flex items-center gap-2">
                {status ? <Status status={status} large /> : <span className="text-lg text-[#667085]">—</span>}
                <IssueBadge issue={result.issue} />
              </div>
            </div>
            <div className="rounded-lg border border-[#DDE8E2] bg-white px-4 py-3">
              <p className="text-sm text-[#667085]">ความพร้อมของเกณฑ์นี้</p>
              <p className="mt-1 text-lg font-semibold text-[#1F2937]">—</p>
              <p className="max-w-xs text-sm text-[#667085]">ระบบมีค่าความพร้อมเฉพาะระดับหลักสูตรทั้งหมด ไม่มีค่าความพร้อมรายเกณฑ์</p>
            </div>
          </div>
        </div>

        <nav aria-label="Section" className="mt-6 flex flex-wrap gap-x-6 gap-y-2 border-b border-[#DDE8E2] pb-2 text-base">
          {TABS.map((t) => (
            <a key={t.href} href={t.href} className="text-[#667085] hover:text-[#205B43]">{t.label}</a>
          ))}
        </nav>

        {waiting && <div className="mt-6"><UIState kind="empty" checkedAt={checkedAt} /></div>}

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="flex flex-col gap-6">
            <Section id="status" testId="section-status" title="ผลการตรวจสอบ">
              {waiting ? WAITING() : (
                <>
                  {status && (
                    <div className="status-row">
                      <Status status={status} large />
                      <IssueBadge issue={result.issue} />
                    </div>
                  )}
                  <ResultText status={status} missing={result.missingInformation.length} />
                  {reviewed && !statusSources(result) && wording?.pending && (
                    <p className="note" data-testid="review-pending">{wording.pending}</p>
                  )}
                  <StatusSources result={result} testId="status-sources" />
                </>
              )}
            </Section>
            {!waiting && reviewed && (
              <Section id="review" testId="section-review" title={wording?.title ?? "ผลการตรวจของผู้ตรวจ (User Review)"}>
                {wording?.instruction && <p data-testid="review-instruction">{wording.instruction}</p>}
                {curriculum && <CurriculumBox curriculum={curriculum} />}
                <UserReview value={result.review} onSave={onReview} action={reviewAction} wording={wording} />
              </Section>
            )}
            <Section id="check" testId="section-check" title="เกณฑ์นี้ตรวจสอบอะไร">
              {check ? <p>{check}</p> : NOT_ENOUGH("ข้อมูลไม่เพียงพอสำหรับอธิบายการตรวจสอบ")}
              {check && sources.length > 0 && <p className="note">ข้อมูลที่ใช้ตรวจ: {sources.join(" และ")}</p>}
            </Section>
            <Section id="condition" testId="section-condition" title="เงื่อนไขที่ใช้ตัดสิน">
              {waiting ? WAITING() : condition ? <p>{condition}</p> : NOT_ENOUGH("ข้อมูลไม่เพียงพอสำหรับแสดงเงื่อนไขการตรวจสอบ")}
            </Section>
            <Section id="data" testId="section-data" title="สิ่งที่ระบบตรวจพบ">
              {waiting ? WAITING(true) : <FoundData result={result} />}
            </Section>
            {!waiting && <SpecificTable result={result} />}
            <Section id="verification" testId="section-verification" title="การยืนยันข้อมูล">
              {waiting ? WAITING() : <Verification value={result.verification} onVerify={onVerify} action={action} />}
            </Section>
            <Section id="missing" testId="section-missing" title="ยังขาดข้อมูลสำหรับตรวจสอบ">
              {waiting ? WAITING() : <MissingInformation items={result.missingInformation} />}
            </Section>
          </div>
          <div className="flex flex-col gap-6">
            <SourceReference psCode={psCode} />
            <Section id="evidence" testId="section-evidence" title="หลักฐานที่ใช้ประกอบการตรวจสอบ">
              {waiting ? WAITING() : <Evidence items={result.evidence} />}
            </Section>
            <Section id="traceability" testId="section-traceability" title="แหล่งที่มาของข้อมูล">
              {waiting ? WAITING() : <Traceability items={result.traceability} />}
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}
