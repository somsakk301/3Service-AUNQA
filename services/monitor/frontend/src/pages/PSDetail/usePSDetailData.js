import { useEffect, useRef, useState } from "react";
import { adaptPSResult } from "../../api/adapter";
import { ApiError } from "../../api/client";
import { fetchMonitor, fetchPS, reviewPS, verifyPS } from "../../api/monitorApi";
import { useRemote } from "../../api/useRemote";
import { useAuth } from "../../app/AuthContext";
import { checkSentence, conditionSentence, sourcesRead } from "../../app/explain";
import { useCurriculumCode } from "../../app/curriculumParam";
import { requirementText, reviewText } from "../../app/psTitles";

/**
 * Everything a PS Detail page needs: fetching the result, the verify/review requests and their local
 * state, and the plain-Thai derivations (app/explain.js). Used by PSDetailPage for every PS code
 * (route /monitor/ps/:psCode) — this file holds no PS-specific text or rule; `psCode` is only a parameter.
 */
export function usePSDetailData(psCode) {
  const { code, search } = useCurriculumCode();
  const { signOut } = useAuth();
  // The page keeps asking for the newest result while it is open: an import may still be writing.
  const remote = useRemote((signal) => fetchPS(psCode, code, signal), [psCode, code], { retryWhile: () => true });
  // No result for this PS yet: every section is still shown, and everything that needs the database
  // says it is waiting. The requirement is the API's text, else the locked text (psTitles.js).
  const waiting = remote.state === "done" && remote.data === null;
  // The user's verify request. What the page shows as verified is always the backend's answer (GET).
  const [action, setAction] = useState("idle");
  const busy = useRef(false);
  useEffect(() => setAction("idle"), [psCode, code]);
  const onVerify = async () => {
    if (busy.current) return;
    busy.current = true;
    setAction("saving");
    try {
      await verifyPS(psCode, code);
      setAction("saved");
      remote.reload();
    } catch (err) {
      console.error("[Mornitor] could not save the verification:", err); // for developers; the page shows a plain message
      setAction("error");
    } finally {
      busy.current = false;
    }
  };
  // The user review, for a PS the configuration has reviewed by the user: the saved choice shown is the backend's.
  const [reviewAction, setReviewAction] = useState("idle");
  const reviewBusy = useRef(false);
  useEffect(() => setReviewAction("idle"), [psCode, code]);
  const recordedAt = remote.state === "done" ? (remote.data?.review?.recordedAt ?? null) : null;
  useEffect(() => setReviewAction((a) => (a === "saved" ? "idle" : a)), [recordedAt]); // the backend has the new review
  const onReview = async (status) => {
    if (reviewBusy.current) return;
    reviewBusy.current = true;
    setReviewAction("saving");
    try {
      await reviewPS(psCode, status, code);
      setReviewAction("saved");
      remote.reload();
    } catch (err) {
      console.error("[Mornitor] could not save the review:", err); // for developers; the page shows a plain message
      if (err instanceof ApiError && err.status === 401) {
        setReviewAction("unauthenticated");
        signOut();   // the backend just said this session is gone: the displayed signed-in name must go with it
      } else {
        setReviewAction("error");
      }
    } finally {
      reviewBusy.current = false;
    }
  };
  const r = remote.state === "done" ? (remote.data ?? adaptPSResult({ psCode })) : null;
  // A PS the user decides: the reviewer sees the curriculum being decided about (read once, from GET /api/monitor).
  const reviewed = Boolean(r?.review);
  const programme = useRemote((signal) => (reviewed ? fetchMonitor(code, signal) : Promise.resolve(null)), [code, reviewed]);
  const curriculum = programme.state === "done" ? (programme.data?.curriculum ?? null) : null;
  const wording = reviewText(psCode);
  const requirement = r ? requirementText(psCode, r.requirement) : null;
  const check = r ? checkSentence({ requirement }) : null;
  const sources = r ? sourcesRead(r) : [];
  const condition = r ? (conditionSentence(r) ?? (reviewed ? wording?.condition ?? null : null)) : null;

  return {
    search, remote, waiting, action, onVerify, reviewAction, onReview, r, reviewed, curriculum, wording,
    requirement, check, sources, condition,
  };
}
