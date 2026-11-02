/**
 * Shapes used by the frontend (documentation only; JavaScript has no types).
 *
 * Status: "PASS" | "FAIL" | "REVIEW" | "N/A"
 * DataCompleteness: "complete" | "incomplete"
 * SummaryItem: { label: string, value: string }
 * DataGroup: { label: string, items: string[] }
 * Verification: { found: number | null, verified: boolean | null, approved: boolean | null, verifiedAt: string | null }
 *   verified: the user verified this PS's evidence and result (read from the backend); approved is never set by it
 * EvidenceItem: { label: string, reference: string | null, storage: string | null, path: string | null }
 *   a source document of the curriculum (documents.originalFile), as the backend sent it
 * TraceItem: { collection: string, recordId: string, fields: string[], values: { [field]: string } }
 * Issue: "configuration_error" | "evaluation_error" | "spec_gap" (why nothing could be decided; null when the status stands on the data)
 * PSResult: Result exactly as produced by the backend. The frontend never derives it.
 *   { psCode, status, requirement, checks, dataSummary, dataFound, verification,
 *     missingInformation, evidence, traceability, dataCompleteness, issue, review, persistedResult }
 * PersistedResult: { status: Status, evaluatedAt: string | null } | null
 *   the status the backend kept when the monitoring result was last saved; may differ from `status` (current)
 * UserReview: { allowManualResult: Status[], status: Status | null, recordedBy: RecordedBy | null,
 *                recordedAt: string | null } | null
 *   only for a PS the configuration has reviewed by the user; the reviewer's saved choice, kept apart from `status`
 * RecordedBy: { userId: string, name: string } | null
 *   the signed-in identity that recorded the review (the backend's session, never a name the frontend sends)
 * CurriculumInfo: { curriculumCode, curriculumName, curriculumYear, version, status } (each string | null)
 * ProgrammeReadiness: { percentage: number, passCount: number, totalPS: number } exactly as the backend
 *   computed it (docs/source-of-truth/API.md). The frontend never derives it.
 * MonitorData: { curriculum: CurriculumInfo | null, overallStatus: Status | null,
 *                programmeReadiness: ProgrammeReadiness | null,
 *                dataCompleteness: DataCompleteness, results: PSResult[] }
 */
export const STATUSES = ["PASS", "FAIL", "REVIEW", "N/A"];
export const ISSUES = ["configuration_error", "evaluation_error", "spec_gap"];
