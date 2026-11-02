import { describe, expect, it } from "vitest";
import { adaptMonitor, adaptPSResult } from "../api/adapter";
import { psResult } from "./fixtures";

describe("adapter", () => {
  it("keeps traceability values as sent (strings only)", () => {
    const r = adaptPSResult(psResult("PS-01", "PASS", {
      traceability: [{ collection: "c", recordId: "r", fields: ["a", "b"], values: { a: "1", b: 2 } }],
    }));
    expect(r.traceability[0]).toEqual({ collection: "c", recordId: "r", fields: ["a", "b"], values: { a: "1", b: "2" } });
  });

  it("missing traceability values become an empty object", () => {
    const r = adaptPSResult(psResult("PS-01", "PASS", { traceability: [{ collection: "c", recordId: "r", fields: ["a"] }] }));
    expect(r.traceability[0].values).toEqual({});
  });

  it.each([
    ["configuration_error", "configuration_error"],
    ["spec_gap", "spec_gap"],
    ["evaluation_error", "evaluation_error"],
    ["something-else", null],
    [undefined, null],
  ])("issue %s -> %s (never invented)", (sent, expected) => {
    expect(adaptPSResult(psResult("PS-01", "REVIEW", { issue: sent })).issue).toBe(expected);
  });

  it("keeps the order of the results the backend sends", () => {
    const body = { curriculum: null, overallStatus: null, dataCompleteness: "complete",
      results: ["PS-09", "PS-10", "PS-01"].map((c) => psResult(c)) };
    expect(adaptMonitor(body).results.map((r) => r.psCode)).toEqual(["PS-09", "PS-10", "PS-01"]);
  });
});
