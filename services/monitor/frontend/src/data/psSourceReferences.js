import data from "./psSourceReferences.json";

/**
 * Verified source-document references for PS requirements (UI display only; never read by the Rule
 * Engine, never changes a result). Each entry is checked against the real PDF before being added here —
 * no page number or quote is guessed. A PS with no entry has not been checked (or was checked and the
 * document has no text that supports it): the UI must show "ข้อมูลไม่เพียงพอ" for it
 * (components/SourceReference), never a placeholder page or made-up text.
 *
 * The data itself lives in the sibling psSourceReferences.json, a config file, like the backend's own
 * ps_requirements, naming a PS code per entry — this loader (a plain .js/.jsx file, scanned by the
 * "no PS code in the frontend source" architecture tests) carries no PS code literal of its own.
 *
 * Shape: { documentName, file, section, printedPage, pdfPage, quote }
 *   file:        path under frontend/public/ the PDF must be placed at
 *   printedPage: the page number printed in the document's own footer (shown to the reader)
 *   pdfPage:     the PDF's own page number, i.e. the Nth page of the file (used for `file#page=`,
 *                since a PDF reader's #page= jumps by file page, not by the number printed on the page)
 *   quote:       the source text verbatim; no wording is added, removed or rephrased
 *
 * The PDF is in the repo at frontend/public/references/wuqa-template-2568.pdf (verified byte-for-byte
 * against the file supplied for review, sha256 1b030a58af92ea8f0f67118811f444c0537a63759097be68856da680
 * 9f6e6514; 65 pages, extracted with pypdf to check every entry's printedPage/pdfPage/quote directly
 * against the real file rather than against any paraphrase of it).
 */
export const psSourceReferences = data;
