/**
 * PS-05 presentation (project owner 2026-09-27): the page shows what the backend sent, with its meaning kept apart —
 * subjects judged (dataSummary "Subjects" and the per-subject results in dataFound), source records read
 * (verification.found / traceability) and the condition (checks). Nothing is ranked, compared or decided here.
 * Fixture: ./fixtures/ps05-ordering-sample.json, captured from the backend (see its "_provenance").
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptPSResult } from "../api/adapter";
import { conditionSentence, orderingCondition, rankedResults, recordsBySource } from "../app/explain";
import SAMPLE from "./fixtures/ps05-ordering-sample.json";
import BACKEND from "./fixtures/backend-sample.json";
import { jsonResponse, mockFetch, renderApp } from "./render";

afterEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

const copy = (v) => JSON.parse(JSON.stringify(v));
const section = (id) => within(screen.getByTestId(`section-${id}`));

async function open(body) {
  mockFetch(() => jsonResponse(body));
  renderApp("/monitor/ps/PS-05");
  await screen.findByTestId("section-traceability");
}

const subjects = () => screen.getAllByTestId("subject").map((li) => ({
  name: li.querySelector(".subject-name").textContent,
  status: within(li).getByTestId("status").getAttribute("data-status"),
  highest: within(li).getByTestId("subject-highest").textContent,
  result: within(li).getByTestId("subject-result").textContent,
  values: [...within(li).getByTestId("subject-values").querySelectorAll("li")].map((v) => v.textContent),
}));

describe("CASE 1: one entry per subject the backend judged", () => {
  it("shows the five responsible lecturers of the API, with the backend's highest degree and result", async () => {
    await open(SAMPLE.all_pass);
    expect(subjects()).toEqual([
      { name: "อาจารย์ทดสอบ 1", status: "PASS", highest: "Ph.D.", result: "ผ่านเกณฑ์", values: ["ปร.ด. → Ph.D.", "วท.บ. → bachelor"] },
      { name: "อาจารย์ทดสอบ 2", status: "PASS", highest: "Ph.D.", result: "ผ่านเกณฑ์",
        values: ["Ph.D. → Ph.D.", "วท.บ. → bachelor", "วท.ม. → master"] },
      { name: "อาจารย์ทดสอบ 3", status: "PASS", highest: "master", result: "ผ่านเกณฑ์", values: ["บธ.บ. → bachelor", "วท.ม. → master"] },
      { name: "อาจารย์ทดสอบ 4", status: "PASS", highest: "master", result: "ผ่านเกณฑ์",
        values: ["at → ระบบตีความระดับไม่ได้", "heuristic approach. Journal of Sensor and Actuator → ระบบตีความระดับไม่ได้",
          "วท.บ. → bachelor", "วท.ม. → master"] },
      { name: "อาจารย์ทดสอบ 5", status: "PASS", highest: "Ph.D.", result: "ผ่านเกณฑ์",
        values: ["ปร.ด. → Ph.D.", "วท.บ. → bachelor", "วท.ม. → master", "วบ.บ. → bachelor"] },
    ]);
    expect(section("data").getByText("ผลการตรวจแต่ละราย")).toBeInTheDocument();
    expect(section("data").getAllByText("ระดับคุณวุฒิสูงสุดที่ระบบตีความได้")).toHaveLength(5);
  });

  it("the number of subjects is the backend's (dataSummary Subjects), next to its list", async () => {
    await open(SAMPLE.all_pass);
    expect(section("data").getByText("จำนวนรายการที่ตรวจ").nextSibling).toHaveTextContent("5");
    expect(section("data").getByText("รายการที่ผ่านเกณฑ์").nextSibling).toHaveTextContent("5");
  });
});

describe("CASE 2: source records are not subjects", () => {
  it("25 records read (5 appointments + 20 educations) stay 25 records; 5 subjects stay 5", async () => {
    await open(SAMPLE.all_pass);
    expect(SAMPLE.all_pass.verification.found).toBe(25);
    expect(screen.getAllByTestId("subject")).toHaveLength(5);
    expect(screen.getByTestId("records-read")).toHaveTextContent(
      "ตัวเลขนี้คือจำนวนข้อมูลต้นทางที่ระบบอ่าน (ข้อมูลการแต่งตั้ง 5 รายการ · ข้อมูลคุณวุฒิ 20 รายการ) ไม่ใช่จำนวนรายที่ตรวจ");
    expect(screen.getByTestId("section-data").textContent).not.toMatch(/(20|25) ราย(?!การ)/);
  });

  it("records are counted per source from the traceability the backend sent", () => {
    expect(recordsBySource(adaptPSResult(SAMPLE.all_pass))).toEqual([
      { source: "ข้อมูลการแต่งตั้ง", count: 5 }, { source: "ข้อมูลคุณวุฒิ", count: 20 }]);
  });
});

describe("CASE 3: every subject shows the backend's values and status", () => {
  it("PASS / FAIL / REVIEW and values the backend could not rank, as sent", async () => {
    await open(SAMPLE.mixed);
    const s = subjects();
    expect(s.map((x) => x.status)).toEqual(["PASS", "PASS", "PASS", "FAIL", "REVIEW"]);
    expect(s[1].values).toEqual(["PhD. → Ph.D.", "at → ระบบตีความระดับไม่ได้"]);
    expect(s[3]).toMatchObject({ highest: "bachelor", result: "ไม่ผ่านเกณฑ์" });
    expect(s[4]).toMatchObject({ highest: "—", result: "ต้องตรวจสอบเพิ่มเติม" });          // the backend named no highest
  });

  it("the status is never worked out from the values: the backend's word stands", async () => {
    const body = copy(SAMPLE.all_pass);
    body.dataFound[0].items[0] = body.dataFound[0].items[0].replace("-> PASS", "-> REVIEW");
    await open(body);
    expect(subjects()[0]).toMatchObject({ highest: "Ph.D.", status: "REVIEW", result: "ต้องตรวจสอบเพิ่มเติม" });
    expect(section("status").getByTestId("status")).toHaveAttribute("data-status", "PASS");     // the PS status as sent
  });
});

describe("CASE 4: the condition of an ordering comparison", () => {
  it("is shown from the configuration the backend describes in checks", async () => {
    await open(SAMPLE.all_pass);
    expect(section("condition").getByText(
      "ระดับคุณวุฒิสูงสุดที่ระบบตีความได้ต้องไม่ต่ำกว่า “master” (ลำดับจากต่ำไปสูง: bachelor < master < Ph.D.)")).toBeInTheDocument();
    expect(section("condition").queryByText("ข้อมูลไม่เพียงพอสำหรับแสดงเงื่อนไขการตรวจสอบ")).not.toBeInTheDocument();
  });

  it("follows the checks: another minimum or ordering reads differently", () => {
    const r = adaptPSResult(SAMPLE.all_pass);
    r.checks = r.checks.map((c) => c.replace('minimum: "master"', 'minimum: "Ph.D."'));
    expect(orderingCondition(r)).toEqual({ field: "degree", minimum: "Ph.D.", ordering: ["bachelor", "master", "Ph.D."] });
    expect(conditionSentence(r)).toContain("ต้องไม่ต่ำกว่า “Ph.D.”");
  });

  it.each([
    ["no ordering line", (c) => !c.startsWith("degree.ordering")],
    ["no minimum line", (c) => !c.startsWith("degree.minimum")],
  ])("%s: no condition is made up", (_, keep) => {
    const r = adaptPSResult(SAMPLE.all_pass);
    r.checks = r.checks.filter(keep);
    expect(conditionSentence(r)).toBeNull();
  });

  it("a minimum that is not in the ordering is not shown", () => {
    const r = adaptPSResult(SAMPLE.all_pass);
    r.checks = r.checks.map((c) => c.replace('minimum: "master"', 'minimum: "doctorate"'));
    expect(conditionSentence(r)).toBeNull();
  });
});

describe("CASE 5: the API sends nothing to state the condition with", () => {
  it("says so instead of making a condition up", async () => {
    const body = copy(SAMPLE.all_pass);
    body.checks = [];
    body.requirement = null;
    await open(body);
    expect(section("condition").getByText("ข้อมูลไม่เพียงพอสำหรับแสดงเงื่อนไขการตรวจสอบ")).toBeInTheDocument();
  });
});

describe("CASE 6: incomplete API data does not break the page", () => {
  it.each([
    ["no dataFound", (b) => delete b.dataFound],
    ["no traceability", (b) => delete b.traceability],
    ["no checks and no dataSummary", (b) => { delete b.checks; delete b.dataSummary; }],
  ])("%s", async (_, cut) => {
    const body = copy(SAMPLE.all_pass);
    cut(body);
    await open(body);
    expect(screen.getByTestId("section-data")).toBeInTheDocument();
  });

  it("without dataFound there is no per-subject list and no records note", async () => {
    const body = copy(SAMPLE.all_pass);
    delete body.dataFound;
    await open(body);
    expect(screen.queryByTestId("subject-results")).not.toBeInTheDocument();
    expect(screen.queryByTestId("records-read")).not.toBeInTheDocument();
  });
});

describe("CASE 7: other results keep their own display", () => {
  const others = BACKEND.results.filter((r) => r.psCode !== "PS-05").map(adaptPSResult);

  it("no other PS of the backend sample is read as an ordering comparison", () => {
    expect(others.length).toBe(8);
    for (const r of others) {
      expect(rankedResults(r), r.psCode).toBeNull();
      expect(orderingCondition(r), r.psCode).toBeNull();
    }
  });

  it.each(["PS-02", "PS-06", "PS-07"])("%s shows its names list, not the per-subject block", async (code) => {
    mockFetch(() => jsonResponse(BACKEND.results.find((r) => r.psCode === code)));
    renderApp(`/monitor/ps/${code}`);
    await screen.findByTestId("section-traceability");
    expect(screen.queryByTestId("subject-results")).not.toBeInTheDocument();
    expect(screen.queryByTestId("records-read")).not.toBeInTheDocument();
  });

  it("an item in another form (e.g. 'equal to') is not read as a per-subject result", () => {
    const r = adaptPSResult(SAMPLE.all_pass);
    r.dataFound = [{ label: "อาจารย์ ก", items: ["degree: master (equal to 'master') -> PASS"] }];
    expect(rankedResults(r)).toBeNull();
  });
});

describe("no PS-05 rule, value or person in the frontend source", () => {
  const src = join(process.cwd(), "src");
  const files = readdirSync(src, { recursive: true }).map(String)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.startsWith("test"));
  const config = JSON.parse(readFileSync(join(process.cwd(), "../backend/tests/fixtures/ps_config_v1.json"), "utf8"));
  const degree = config.find((c) => c.psCode === "PS-05").config.degree;
  const values = [...degree.ordering, ...Object.values(degree.aliases).flat()];

  // the two approved PS-code files (the PS list and the locked requirement texts, SCOPE.md) name every PS code
  const PS_CODE_FILES = ["app/psGuideline.js", "app/psTitles.js"];

  it.each(files)("%s", (file) => {
    const text = readFileSync(join(src, file), "utf8");
    for (const v of values) expect(text, v).not.toContain(v);
    expect(text).not.toMatch(/6ab0[0-9a-f]{20}/);                         // no ObjectId
    if (!PS_CODE_FILES.includes(file)) expect(text).not.toMatch(/PS-05/);
  });
});
