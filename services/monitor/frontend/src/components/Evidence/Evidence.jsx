const originalFileUrl = (reference) =>
  reference ? `/api/import/documents/${encodeURIComponent(reference)}/file` : null;

/** Source documents exactly as the backend sent them. The URL uses only the document id; the Import
 * Service resolves and validates the stored path server-side before serving the original file. */
export function Evidence({ items }) {
  if (items.length === 0) return <p className="muted">ยังไม่มีข้อมูลหลักฐาน</p>;
  return (
    <ul className="doc-list">
      {items.map((e, i) => {
        const url = originalFileUrl(e.reference);
        return (
          <li key={i} data-testid="evidence-item">
            <span className="doc-list__name">{e.label}{e.reference ? ` — ${e.reference}` : ""}</span>
            <span className="doc-list__detail label" data-testid="evidence-storage">ที่เก็บไฟล์ต้นฉบับ: {e.storage ?? "ไม่พบข้อมูล storage"}</span>
            <span className="doc-list__detail label" data-testid="evidence-path">ตำแหน่งไฟล์ต้นฉบับ: {e.path ?? "ไม่พบข้อมูล path"}</span>
            {url && e.storage === "local" && e.path ? (
              <a
                className="doc-list__open"
                href={url}
                target="_blank"
                rel="noreferrer"
                data-testid="evidence-open"
              >
                เปิดไฟล์ต้นฉบับ ↗
              </a>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
