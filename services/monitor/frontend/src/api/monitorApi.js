import { adaptMonitor, adaptPSResult } from "./adapter";
import { ApiError, getJson, postJson } from "./client";
import { endpoints } from "./endpoints";

function withCurriculum(url, curriculumCode) {
  return curriculumCode ? `${url}?curriculumCode=${encodeURIComponent(curriculumCode)}` : url;
}

export async function fetchMonitor(curriculumCode, signal) {
  return adaptMonitor(await getJson(withCurriculum(endpoints.monitor(), curriculumCode), signal));
}

/** Saves the monitoring result of the curriculum (the backend evaluates now and keeps each PS's status). */
export async function saveResults(curriculumCode) {
  return adaptMonitor(await postJson(withCurriculum(endpoints.results(), curriculumCode)));
}

/** Resolves to null when the backend has no result for this PS (renders as No Data). */
export async function fetchPS(psCode, curriculumCode, signal) {
  try {
    return adaptPSResult(await getJson(withCurriculum(endpoints.ps(psCode), curriculumCode), signal));
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** The user verified the evidence and result of this PS. The backend keeps it; the page reads it back by GET. */
export async function verifyPS(psCode, curriculumCode) {
  return adaptPSResult(await postJson(withCurriculum(endpoints.verification(psCode), curriculumCode)));
}

/** The reviewer's choice (one of the statuses the API listed). The backend keeps it; the page reads it back by GET. */
export async function reviewPS(psCode, status, curriculumCode) {
  return adaptPSResult(await postJson(withCurriculum(endpoints.review(psCode), curriculumCode), { status }));
}
