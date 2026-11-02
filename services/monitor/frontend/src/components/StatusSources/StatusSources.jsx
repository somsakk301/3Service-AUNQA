import { statusSources } from "../../app/psStatus";

/** Where the status shown comes from, when a user review decides it: the engine's first status and the reviewer's. */
export function StatusSources({ result, testId }) {
  const sources = statusSources(result);
  if (!sources) return null;
  return (
    <p className="note" data-testid={testId}>
      {`ระบบประเมินเบื้องต้น: ${sources.engine ?? "—"} · ผู้ตรวจยืนยัน: ${sources.reviewer}`}
    </p>
  );
}
