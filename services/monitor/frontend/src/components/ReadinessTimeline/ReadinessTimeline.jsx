import { resolveStatus } from "../../app/psStatus";

const CLASS = { PASS: "pass", FAIL: "fail", REVIEW: "review", "N/A": "na" };

/**
 * Vertical visual index of the overview grid: the same `cardList` entries the grid renders (PS-01…PS-09,
 * in the same order), each shown by its psCode and the same resolved status every PS card already shows
 * (app/psStatus.js: the reviewer's choice where there is one, else the engine's status). Display only —
 * no status, count or readiness is computed here, and a PS without a result yet (cardList: `result: null`,
 * as GuideCard shows it) gets no status of its own.
 */
export function ReadinessTimeline({ cards }) {
  return (
    <ol className="readiness-timeline" aria-label="สถานะความพร้อมของข้อมูลราย PS" data-testid="readiness-timeline">
      {cards.map(({ psCode, result }, i) => {
        const status = result ? resolveStatus(result) : null;
        const cls = status ? CLASS[status] : "none";
        return (
          <li key={`${i}-${psCode}`} className={`readiness-timeline__item readiness-timeline--${cls}`}
              data-testid={`timeline-${psCode}`}>
            <span className="readiness-timeline__rail" aria-hidden="true">
              <span className="readiness-timeline__dot" />
              <span className="readiness-timeline__line" />
            </span>
            <span className="readiness-timeline__body">
              <span className="readiness-timeline__code">{psCode}</span>
              <span className="readiness-timeline__status">{status ?? "—"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
