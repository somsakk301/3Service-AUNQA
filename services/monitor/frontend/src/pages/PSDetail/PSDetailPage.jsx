import { Link, useParams } from "react-router-dom";
import { resolveStatus } from "../../app/psStatus";
import { PSDashboardLayout } from "../../components/PSDetail";
import { LastChecked, UIState } from "../../components/UIState";
import { usePSDetailData } from "./usePSDetailData";

/**
 * One PS Detail page for every PS code (PS-01…PS-09, and any other the backend sends — route
 * /monitor/ps/:psCode, App.jsx). The dashboard layout is shared and data-driven (components/PSDetail):
 * nothing here, or in it, branches on which PS this is.
 */
export function PSDetailPage() {
  const { psCode = "" } = useParams();
  const {
    search, remote, waiting, action, onVerify, reviewAction, onReview, r, reviewed, curriculum, wording,
    requirement, check, sources, condition,
  } = usePSDetailData(psCode);
  // The sidebar shows a real status badge only for the PS already loaded on this page (this one): a
  // detail page fetches no other PS's result, same as before this page gained a sidebar.
  const statusByCode = r ? { [psCode]: resolveStatus(r) } : {};

  return (
    <>
      <header className="page-head" data-testid="section-header">
        <Link className="back" to={`/monitor/ps${search}`}>← ภาพรวมเกณฑ์ PS</Link>
        <h1>{psCode}</h1>
      </header>
      {remote.state === "loading" && <UIState kind="loading" />}
      {remote.state === "error" && <UIState kind={remote.status === 409 ? "multiple" : "error"} checkedAt={remote.checkedAt} />}
      {remote.state === "done" && !waiting && <LastChecked checkedAt={remote.checkedAt} />}
      {r && (
        <div className="stack">
          {r.dataCompleteness === "incomplete" && <UIState kind="incomplete" />}
          <PSDashboardLayout
            result={r} psCode={psCode} search={search} waiting={waiting} requirement={requirement} check={check}
            sources={sources} condition={condition} onVerify={onVerify} action={action} statusByCode={statusByCode}
            checkedAt={remote.checkedAt} reviewed={reviewed} curriculum={curriculum} wording={wording}
            reviewAction={reviewAction} onReview={onReview}
          />
        </div>
      )}
    </>
  );
}
