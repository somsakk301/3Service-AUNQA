import { checkedNames, foundSentence, rankedResults, recordsBySource, reviewedInformation, summaryLabel } from "../../app/explain";
import { NOTE_LABELS, OPERATION } from "../DataFound/summaryLabels";
import { ReviewedInformation } from "../ReviewedInformation";
import { SubjectResults } from "../SubjectResults";

const NOT_ENOUGH = (text) => <p className="muted">{text}</p>;

/**
 * What the system found: a sentence, the counts under Thai labels, and the names checked. For an ordering
 * comparison the backend also sends each subject's values and result: they are shown per subject, and the
 * number of source records read is told apart from the number of subjects judged.
 */
export function FoundData({ result }) {
  const found = foundSentence(result);
  const counts = result.dataSummary
    .filter((i) => i.label !== OPERATION && !NOTE_LABELS.includes(i.label))
    .map((i) => ({ label: summaryLabel(i.label), value: i.value }))
    .filter((i) => i.label !== null);
  const names = checkedNames(result);
  const subjects = rankedResults(result);
  const records = recordsBySource(result);
  const shown = reviewedInformation(result);
  return (
    <>
      {found ? <p className="lead">{found}</p> : NOT_ENOUGH("ไม่พบข้อมูลที่ใช้ตรวจสอบ")}
      {subjects && records.length > 0 && (
        <p className="note" data-testid="records-read">
          {`ตัวเลขนี้คือจำนวนข้อมูลต้นทางที่ระบบอ่าน (${records.map((r) => `${r.source} ${r.count} รายการ`).join(" · ")}) ไม่ใช่จำนวนรายที่ตรวจ`}
        </p>
      )}
      {counts.length > 0 && (
        <dl className="summary">
          {counts.map((c, i) => <div key={i}><dt>{c.label}</dt><dd>{c.value}</dd></div>)}
        </dl>
      )}
      {shown ? (
        <div className="group">
          <h3 className="subhead">ข้อมูลที่ผู้ตรวจใช้พิจารณา</h3>
          <ReviewedInformation subjects={shown} />
        </div>
      ) : subjects ? (
        <div className="group">
          <h3 className="subhead">ผลการตรวจแต่ละราย</h3>
          <SubjectResults subjects={subjects} />
        </div>
      ) : names.length > 0 && (
        <div className="group">
          <h3 className="subhead">รายการที่ระบบตรวจ</h3>
          <ul className="list">{names.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
    </>
  );
}
