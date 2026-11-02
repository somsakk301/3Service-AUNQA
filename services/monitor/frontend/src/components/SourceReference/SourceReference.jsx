import { psSourceReferences } from "../../data/psSourceReferences";

/**
 * "ข้อความจากเอกสารต้นทาง": the verbatim source text this PS's requirement was checked against, from
 * data/psSourceReferences.js (verified per entry against the real PDF — never guessed here). Separate
 * from the requirement the system uses (Section "สิ่งที่เกณฑ์ต้องการ"): this card is the original
 * document text, not the configured rule. A PS with no verified entry says so plainly.
 */
export function SourceReference({ psCode }) {
  const ref = psSourceReferences[psCode];
  const pageFile = ref ? ref.file.replace(/\.pdf$/i, `-page-${ref.pdfPage}.pdf`) : '';
  return (
    <div className="rounded-lg border border-[#DDE8E2] bg-white p-4" id="source-reference" data-testid="source-reference">
      <h3 className="text-lg font-semibold text-[#1F2937]">ข้อความจากเอกสารต้นทาง</h3>
      {ref ? (
        <>
          <blockquote className="mt-3 border-l-2 border-[#2F7D5B] pl-3 text-base leading-relaxed text-[#1F2937]">
            {ref.quote}
          </blockquote>
          <dl className="mt-4 space-y-2 text-base">
            <div>
              <dt className="text-sm text-[#667085]">เอกสาร</dt>
              <dd className="text-[#1F2937]">{ref.documentName}</dd>
            </div>
            <div>
              <dt className="text-sm text-[#667085]">หัวข้อ</dt>
              <dd className="text-[#1F2937]">{ref.section}</dd>
            </div>
            <div>
              <dt className="text-sm text-[#667085]">หน้าเอกสาร</dt>
              <dd className="text-[#1F2937]">{ref.printedPage}</dd>
            </div>
          </dl>
          <a
            className="mt-4 inline-flex min-h-[44px] items-center gap-1 text-base font-medium text-[#205B43] hover:underline"
            href={`${pageFile}#page=${ref.pdfPage}`}
            target="_blank"
            rel="noreferrer"
            aria-label={`เปิด ${ref.documentName} หน้า ${ref.printedPage}`}
          >
            เปิดเอกสารหน้า {ref.printedPage} ↗
          </a>
        </>
      ) : (
        <p className="mt-2 text-base text-[#667085]">ยังไม่มีข้อมูลแหล่งอ้างอิงสำหรับ PS นี้</p>
      )}
    </div>
  );
}
