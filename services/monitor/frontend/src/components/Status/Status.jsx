const CLASS = { PASS: "pass", FAIL: "fail", REVIEW: "review", "N/A": "na" };
// Plain-Thai status words for a non-technical reader (project owner 2026-10-05); the raw code the backend
// sent stays in `data-status` for anything that needs it (tests, other code) — only the visible label changes.
const LABEL = { PASS: "ผ่าน", FAIL: "ไม่ผ่าน", REVIEW: "รอตรวจทาน", "N/A": "ไม่เกี่ยวข้อง" };

// Each status has its own icon shape, so colour is never the only signal.
function Icon({ status }) {
  const common = { width: 16, height: 16, viewBox: "0 0 16 16", "aria-hidden": true, focusable: false };
  switch (status) {
    case "PASS":
      return <svg {...common}><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M4.5 8.2l2.4 2.4 4.6-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
    case "FAIL":
      return <svg {...common}><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
    case "REVIEW":
      return <svg {...common}><path d="M8 1.5L15 14H1z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="M8 6.2v3.6M8 11.6v.1" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
    case "N/A":
      return <svg {...common}><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2.5 2" /><path d="M5 8h6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
    default:
      return null;
  }
}

export function Status({ status, large = false }) {
  const cls = status ? CLASS[status] : "none";
  return (
    <span className={`status status--${cls}${large ? " status--large" : ""}`} data-testid="status" data-status={status ?? ""}>
      <Icon status={status} />
      <span>{status ? LABEL[status] : "—"}</span>
    </span>
  );
}
