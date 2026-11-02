import { useState } from "react";
import { Status } from "../Status";

const when = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("th-TH");
};
const LABEL = {
  idle: "บันทึกผลการตรวจ",
  error: "บันทึกผลการตรวจ",
  unauthenticated: "บันทึกผลการตรวจ",
  saving: "กำลังบันทึกผลการตรวจ…",
  saved: "บันทึกแล้ว กำลังอ่านผลจากระบบ…",
};

/**
 * The user review of a PS the configuration has reviewed by the user. The options are the API's
 * (allowManualResult); the saved choice, who recorded it and when are shown only as the backend returns them
 * (`recordedBy`/`recordedAt`: the signed-in identity its own session verified, never a name this page could
 * send). The engine's status is kept apart; the page shows and counts the saved choice (app/psStatus.js, and
 * the backend's readiness).
 * `wording` (app/psTitles.js): a question with one button per option, each saving its status at once; without it,
 * the options are chosen, then saved. `action`: the state of the save request
 * ("idle" | "saving" | "saved" | "error" | "unauthenticated" — no session when the save was attempted).
 */
export function UserReview({ value, onSave, action = "idle", wording = null }) {
  const [choice, setChoice] = useState(null);
  const busy = action === "saving" || action === "saved";
  const label = (s) => wording?.options?.[s] ?? s;
  return (
    <>
      <dl className="summary">
        <div>
          <dt>ผลที่ผู้ตรวจบันทึก</dt>
          <dd data-testid="review-saved">
            {value.status ? <><Status status={value.status} />{label(value.status) !== value.status && ` ${label(value.status)}`}</>
              : "ยังไม่มีผลการตรวจของผู้ตรวจ"}
          </dd>
        </div>
        <div><dt>ผู้บันทึก</dt><dd data-testid="recorded-by">{value.recordedBy?.name ?? "—"}</dd></div>
        <div><dt>บันทึกเมื่อ</dt><dd data-testid="recorded-at">{value.recordedAt ? when(value.recordedAt) : "—"}</dd></div>
      </dl>
      {wording?.question ? (
        <div className="group">
          <p className="strong" data-testid="review-question">{wording.question}</p>
          {value.allowManualResult.map((s) => (
            <button key={s} type="button" data-testid={`review-choose-${s}`} disabled={busy} onClick={() => onSave(s)}>
              {label(s)}
            </button>
          ))}
          {busy && <p className="note" data-testid="review-progress">{LABEL[action]}</p>}
        </div>
      ) : (
        <>
          <fieldset className="group" disabled={busy}>
            <legend className="label">เลือกผลการตรวจ</legend>
            {value.allowManualResult.map((s) => (
              <label key={s}>
                <input type="radio" name="user-review" value={s} checked={choice === s} onChange={() => setChoice(s)}
                  data-testid={`review-option-${s}`} /> {s}{" "}
              </label>
            ))}
          </fieldset>
          <button type="button" data-testid="review-save" disabled={!choice || busy} onClick={() => onSave(choice)}>
            {LABEL[action]}
          </button>
        </>
      )}
      <p className="note">ผลนี้เก็บแยกจากผลการประเมินของระบบ (ผลของระบบไม่เปลี่ยน) และใช้เป็นผลของเกณฑ์นี้ในการแสดงผลและการคำนวณความพร้อมของหลักสูตร</p>
      {action === "error" && (
        <p className="note" role="alert" data-testid="review-error">บันทึกผลการตรวจไม่สำเร็จ กรุณาลองใหม่</p>
      )}
      {action === "unauthenticated" && (
        <p className="note" role="alert" data-testid="review-unauthenticated">กรุณาเข้าสู่ระบบก่อนบันทึกผลการตรวจ</p>
      )}
    </>
  );
}
