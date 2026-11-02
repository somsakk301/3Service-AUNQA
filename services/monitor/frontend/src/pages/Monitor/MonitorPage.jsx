import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { fetchMonitor, saveResults } from "../../api/monitorApi";
import { useRemote } from "../../api/useRemote";
import { PS_GROUP } from "../../app/criteriaGroups";
import { PS_GUIDELINE } from "../../app/psGuideline";
import { useCurriculumCode } from "../../app/curriculumParam";
import { Completeness } from "../../components/Completeness";
import { CurriculumBox } from "../../components/CurriculumBox";
import { EvidenceStatus } from "../../components/EvidenceStatus";
import { GuideCard } from "../../components/GuideCard";
import { MissingOverview } from "../../components/MissingOverview";
import { PersistedResults } from "../../components/PersistedResults";
import { ProgrammeReadiness } from "../../components/ProgrammeReadiness";
import { PSCard } from "../../components/PSCard";
import { ReadinessTimeline } from "../../components/ReadinessTimeline";
import { LastChecked, UIState } from "../../components/UIState";
import { cardList } from "./cardList";
import { tally } from "./tally";

/**
 * Overview of the PS criteria: what each criterion requires → what the system found → the result.
 * PS-01…PS-09 always have a card: the backend's result when it sent one, an empty state otherwise
 * (see cardList). Counts and panels use the backend's results only.
 */
export function MonitorPage() {
  const { code, search } = useCurriculumCode();
  const { key } = useLocation(); // a new key on every visit, so the data is read fresh each time
  // The page keeps asking for the newest result while it is open: an import may still be writing.
  const remote = useRemote((signal) => fetchMonitor(code, signal), [code, key], { retryWhile: () => true });
  const data = remote.state === "done" ? remote.data : null;
  const counts = data ? tally(data.results) : null;
  const waiting = remote.state === "error" || (data !== null && data.results.length === 0);
  // Saving the monitoring result: what the page shows as saved is always the backend's answer (GET).
  const [action, setAction] = useState("idle");
  const busy = useRef(false);
  useEffect(() => setAction("idle"), [code]);
  const savedAt = data ? JSON.stringify(data.results.map((r) => r.persistedResult?.evaluatedAt ?? null)) : null;
  useEffect(() => setAction((a) => (a === "saved" ? "idle" : a)), [savedAt]); // the backend has the new save
  const onSave = async () => {
    if (busy.current) return;
    busy.current = true;
    setAction("saving");
    try {
      await saveResults(code);
      setAction("saved");
      remote.reload();
    } catch (err) {
      console.error("[Mornitor] could not save the monitoring result:", err); // for developers; the page shows a plain message
      setAction("error");
    } finally {
      busy.current = false;
    }
  };

  return (
    <>
      <header className="page-head">
        <h1>AUNQA</h1>
        <p className="strong">{PS_GROUP.title}</p>
        <p className="muted">{PS_GROUP.description}</p>
      </header>
      {remote.state === "loading" && <UIState kind="loading" />}
      {remote.state === "error" && <UIState kind={remote.status === 409 ? "multiple" : "error"} checkedAt={remote.checkedAt} />}
      {data && data.results.length === 0 && <UIState kind="empty" checkedAt={remote.checkedAt} />}
      {data && data.results.length > 0 && <LastChecked checkedAt={remote.checkedAt} />}
      {waiting && (
        <section className="section" aria-labelledby="guide-h">
          <h2 id="guide-h">ภาพรวมเกณฑ์ PS</h2>
          <p className="note guide-note">ระหว่างรอข้อมูล แสดงข้อกำหนดของแต่ละเกณฑ์ไว้ก่อน ผลการตรวจสอบจะแสดงเมื่อระบบส่งข้อมูลมา</p>
          <div className="ps-grid">
            {PS_GUIDELINE.map((g) => <GuideCard key={g.psCode} psCode={g.psCode} search={search} />)}
          </div>
        </section>
      )}
      {data && data.results.length > 0 && (
        <>
          {data.dataCompleteness === "incomplete" && <UIState kind="incomplete" />}
          {data.curriculum && <CurriculumBox curriculum={data.curriculum} />}
          <ProgrammeReadiness results={data.results} overallStatus={data.overallStatus} readiness={data.programmeReadiness} />
          <section className="section" aria-labelledby="overview-h" data-testid="overview">
            <h2 id="overview-h">ภาพรวมเกณฑ์ PS</h2>
            <div className="overview-layout">
              <ReadinessTimeline cards={cardList(data.results)} />
              <div className="ps-grid">
                {cardList(data.results).map((c, i) => (c.result
                  ? <PSCard key={`${i}-${c.psCode}`} result={c.result} search={search} />
                  : <GuideCard key={`${i}-${c.psCode}`} psCode={c.psCode} search={search} variant="no-result" />))}
              </div>
            </div>
          </section>
          <div className="two-col">
            <EvidenceStatus counts={counts} />
            <MissingOverview results={data.results} search={search} />
          </div>
          <Completeness overall={data.dataCompleteness} counts={counts} />
          <PersistedResults results={data.results} onSave={onSave} action={action} />
        </>
      )}
    </>
  );
}
