# How configuration is executed, what was interpreted, and what is still open

Source of Truth: the configuration in MongoDB `ps_requirements` (the project's active file is
`backend/tests/fixtures/ps_config_v1.json`; the documentation snapshot is `docs/source-of-truth/PS-Config.json`;
the backend reads neither file at runtime), the Data Dictionary and the Data Schema. The current behaviour,
checked against the code on 2026-09-26, is documented in `docs/source-of-truth/`. None of them is edited by this project. Where they leave something
open, the engine reports `REVIEW` with a `SPEC GAP: …` line under Missing Information (or
`Configuration error: …` for a malformed configuration) and evaluates nothing it cannot justify.

## 1. Pipeline

```
ps_requirements.config ─► ConfigurationInterpreter ─► GenericExecutionRequest ─► MonitoringEngine ─► source data
      + Data Schema        (+ SubjectInterpreter)      (one Measure)             FILTER GROUP JOIN COUNT DISTINCT
                                                                                 COMPARE FORMULA WINDOW NORMALIZE MAP
```

Neither the interpreter nor the engine looks at the PS code or holds a business word: keys are
recognised by **shape** and by the **Data Schema** (`models/source_schema.py`). Anything left
unrecognised is a SPEC GAP; nothing is silently ignored.

Every result carries `issue`: `configuration_error` (the configuration is malformed), `evaluation_error` (the
engine failed unexpectedly on this one result; it is logged and the other results are unaffected — SRS §48),
`spec_gap` (it asks for something the specification leaves undefined) or `null` (the status stands on the data). The status itself is
still the one the configuration provides for what cannot be decided, so `REVIEW` + `issue: null` means
"someone must look at the data", while `REVIEW` + an issue means "the configuration/specification must be fixed".

| Construct in a configuration | Generic meaning |
|---|---|
| `targetCollection(s)` | collections to read (Data Schema collections only) |
| `filter {f: v}` | equality FILTER |
| `<prefix><Field>: v \| [v…]` | FILTER on the declared field named by the key's last word (equality, or membership for a list) |
| `<collection singular>: {f: v}` | FILTER on that collection |
| `count {field, distinct}` + `condition {operator, value}` | (distinct) COUNT compared |
| `calculation.formula` + `year.field` + `comparison {…, reference}` | integer formula over a field and a named reference |
| `requiredFields` (+ nested `required` / `requiredFields` / `<field>Required`) | every selected record has each field |
| `review {required, reviewByUser, allowManualResult}` | review by the user; the configured review status |
| `join` (`{from,to}` or named `collection.field` refs) | JOIN; the collection linked to the curriculum holds the subjects |
| `matching {same<X>: true}` + `condition {EXISTS, field}` | JOIN on `<x>Id` within one collection; the related records are those the condition names |
| `{field, period: previous<N>Years}` + `minimumCount` | COUNT of related records inside a TIME WINDOW, compared with `>=` |
| `{field, minimum}` | related field at least `minimum` (without an ordering only equality is decidable) |
| `{field, minimum, ordering}` | related field at least `minimum` by position in `ordering` (lowest first, exact values); the highest listed value of a subject counts; an unlisted value can block a fail, never a pass (PS-05) |
| `{source, required, condition}` | the information below, **judged** by `condition`: `{operator: EXISTS}` (a value is present; no joined record at all is a fail) or `{operator, value}` (a value of the configured kind compares true); no value, or a value of another kind, is a review (PS-08) |
| `{source, required}` | information the reviewer needs; it has no criterion, so it is **shown, never judged** (`source: null` = no data source). The source is a field of the joined records, or of a record the subjects reference through a Data Schema relationship (`REFERENCES`: `personId → persons._id`), e.g. `persons.hasTeachingExperience` |
| `review` + `join` whose checks are only `{source, required}` | the user decides (review by the user); the join says what the reviewer is shown, subject by subject. A check that would decide (a `condition`, a count, an ordering) is a SPEC GAP (PS-06) |
| `result`, `naEnabled`, prose (`reviewCondition`, `conditions`) | status map; N/A switch; descriptive text |

A subject-based operation is: FILTER subjects → GROUP by the join keys → JOIN related records →
run every check per subject → the requirement holds when every subject satisfies every check.
When the only checks are `{source, required}` information (no criterion at all), nothing can be decided
automatically: the result is the review status and the user's manual choice, if given, replaces it.
Every field a configuration names must be declared by the Data Schema; a field inside an array, or
a distinct count over an Object/Array, is a SPEC GAP.

## 2. What the authoritative configuration yields (test data with a defined reference)

| PS | Outcome | Operation the configuration selects |
|---|---|---|
| PS-01 | PASS / FAIL | distinct count of the filtered records, compared |
| PS-02 | PASS / FAIL | each subject has a related record (same curriculum, same person) |
| PS-03 | REVIEW | review by the user is required; the records to review are shown |
| PS-04 | PASS / FAIL | every appointment has the required (nested) fields |
| PS-05 | PASS / FAIL / REVIEW | subjects joined to their educations, highest degree at least `master` by `degree.ordering` (`bachelor` < `master` < `Ph.D.`); an unlisted or missing degree is REVIEW |
| PS-06 | REVIEW | user confirmation (2026-09-29): each responsible lecturer is shown with degree, field and institution; the user confirms PASS / FAIL through the User Review, nothing is decided automatically |
| PS-07 | PASS / FAIL / REVIEW | per subject, works inside the time window, at least `minimumCount` |
| PS-08 | N/A / PASS / FAIL / REVIEW | none selected → N/A; otherwise each special instructor needs a qualification (`educations.degree` EXISTS: no education record → FAIL, a record without a degree → REVIEW) and `persons.hasTeachingExperience == true` (`false` → FAIL, absent / null / not a Boolean → REVIEW). Years, kind or relevance of experience are not judged |
| PS-09 | PASS / FAIL | `currentYear - curriculumYear` compared |

## 3. Interpretations applied where the configuration is silent

These are the only places the engine chose a meaning. Each is generic (not tied to a PS) and each
should be confirmed by the owner of the configuration.

1. **Quantifier.** A requirement over several subjects holds only if every subject satisfies it: any `fail` → FAIL, else any `review` → REVIEW, else PASS.
2. **No subject.** With `naEnabled: true` → `result.na`; otherwise REVIEW ("nothing can be checked"). `naEnabled: true` without `result.na` is a configuration error.
3. **Several related records per subject.** One satisfying record is enough (a person's best education counts).
4. **Required fields.** A missing/blank field, or no records at all, is the configured `fail` (`conditions.fail` says "no order or incomplete data").
5. **Time window.** `previous<N>Years` = reference − N … reference, both ends included, the same convention as `currentYear - curriculumYear <= N`. A year after the reference is outside.
6. **`minimumCount`** is `>=`, counted per subject.
7. **`currentYear`** = the runtime clock's year + `MORNITOR_YEAR_OFFSET` (default `543`, the calendar of the Data Schema's example data: `curriculumYear 2567`, `publicationYear 2569` beside 2026 timestamps). Set `0` for Gregorian years. A relative window counts back from `currentYear`.
8. **(removed 2026-09-29)** The automatic comparison of the curriculum name with the field of study (`extract` / mapping) no longer exists: PS-06 is decided by the user. A configuration that still asks for it is a SPEC GAP (REVIEW), never PASS or FAIL.
9. **`EXISTS`.** The subject filter is the one whose value differs from `condition.field`; the related filter is the one it equals.
10. **At-least.** Equality with `minimum` is the only comparison decidable without an ordering. With `ordering` (PS-05) values compare by position, matched exactly (`Master`, `PhD` or `ปริญญาโท` are not listed values, so they are REVIEW).
11. **Manual choices (information-only operations, i.e. `{source, required}` without `condition`; none in the active configuration).** The statuses the configuration's `conditions` name, except N/A. The user's choice replaces the review status; any other value is rejected with a SPEC GAP. No subject → N/A whatever the choice.
12. **A required review is not missing data.** "Review by user required by configuration" (PS-03) and "Manual review required…" (an information-only operation; PS-08 is no longer one) are shown in the summary under `Review`, not under Missing Information, so they do not by themselves make `dataCompleteness` `incomplete`. **To confirm:** if the criterion owners count "waiting for the reviewer" as incomplete data, this is reversed in one place (`engine.py`).
13. **Issue precedence.** When a result has both a configuration error and a SPEC GAP, `issue` is `configuration_error`, because the configuration must be fixed before anything else can be judged.
14. **Malformed values never stop the monitor.** A configuration value of the wrong type (a list where a collection name is expected, text where a number is compared, …) is a configuration error of that result only. A record whose key value is a list or an object is unusable, like a blank one. Anything unexpected is an `evaluation_error` of that result only (logged with its traceback). Only a data-source failure stops the whole run (API `503`). A randomized test (`tests/test_robustness.py`) checks this on 300 malformed variants.

## 4. Still open (Specification does not define; the engine says so instead of guessing)

1. **Degree ordering (PS-05) — closed (2026-09-25).** The project owner's configuration sets `degree.ordering: ["bachelor", "master", "Ph.D."]` with `minimum: "master"`: `bachelor` → FAIL, `master` / `Ph.D.` → PASS, a missing degree or a value not in the ordering → REVIEW. Still open: the ordering holds one spelling per level; other spellings (e.g. `M.Sc.`, `ปริญญาโท`) stay REVIEW until the owner lists them.
2. **Qualification and experience (PS-08) — closed (2026-09-25).** The project owner's rule: PS-08 checks that a qualification exists in `educations.degree` and that `persons.hasTeachingExperience` is `true` (reached through `appointments.personId → persons._id`; `persons` has no `personId` field, so the owner file's `join.experiencePersonId` is not used). The number of years, the kind and the relevance of experience are not judged. The configuration expresses this with `condition` blocks (see §1).
3. **Manual review results (PS-03).** The user's result is entered by the user; the Data Schema has no place to store it and Mornitor never writes. It is read through a port (`ManualResultSource`); production supplies none, so PS-03 stays REVIEW until a store is defined.
4. **Prose conditions.** `reviewCondition` / `conditions` are sentences; they are displayed, not evaluated. A record lacking the counted field (PS-01) is REVIEW.
5. **Curriculum selection / overall status.** With several curricula and no `?curriculumCode=` the API answers `409`. The overall-status rule is undefined → `null`.
6. **Verification, Evidence.** `Verified`/`Approved` have no source (`null`); Evidence source undefined (empty). Traceability lists each record read with the fields used and their actual values (`field = value`); the per-subject line shows check → result.
   *Names are display only:* Data Found shows records by name (`persons.fullName`, `curricula.curriculumCode`, via the Data Schema `REFERENCES`/`DISPLAY_FIELD` tables) instead of ObjectIds. These lookups are not evidence, are not traced and never change a result; a reference without a named record is shown as `<id> (ไม่พบ persons.fullName)`.
7. **Data Dictionary vs configuration.** The Data Dictionary lists only `minCount`/`role` under `ps_requirements.config`; the authoritative configuration is richer and is what runs.
8. **Infrastructure.** Database engine, API contract, error codes, security, External Services 1/2. (The frontend holds the PS codes PS-01…PS-09 in `psGuideline.js` as the base list for the cards and the top bar's PS links, and locked requirement texts in `psTitles.js`; both are display only, see 4.11.)

9. **Frontend design (`Forntend.md`) — what is not built, and why** (v0.3.0). The design asks for things the
   configuration or the API does not provide, or that the SRS forbids the frontend to do. The frontend shows `—` or a
   fixed explanatory text instead and never guesses. `Forntend.md` itself was not in the delivered files at the time; this list
   follows the v0.3.0 UI brief (`PROMPT_UI_v0.3.0.md` §9). (The file is now available at `~/Mornitor-Data/Forntend.md`.)

   | In `Forntend.md` | Built instead | Reason |
   |---|---|---|
   | Readiness "82%" | Counts per status; Overall `—` with "ยังไม่มีกฎรวมผลทั้งหลักสูตร (SPEC GAP)" | No formula in the configuration; the frontend may not compute a condition (SRS §16) |
   | Thai criterion names, e.g. "จำนวนอาจารย์ผู้รับผิดชอบหลักสูตร" | `psCode` + `requirement` | The configuration has no name field; hard-coding is forbidden (SRS §12, §31) |
   | Per-criterion "สิ่งที่ต้องตรวจสอบ" text | `Operation` (dataSummary) + `checks` from the backend | The configuration has no such text |
   | PS-08 "การกำหนด N/A โดยเจ้าหน้าที่" (a choice control) | Not built | Mornitor is read-only; N/A comes from the configuration (SRS §24) |
   | Example numbers and names ("อาจารย์ A", "5 คน", "XX คน") | Real API data | `Forntend.md` marks them as examples only |
   | Missing Information categories ("คุณวุฒิอาจารย์", "ผลงานวิชาการ") | Grouped by `psCode`, lines as sent | The backend does not categorise |
   | ✓ / ⚠ symbols | The existing `Status` icons | Text plus icon shape, never colour alone |
   | Table "อาจารย์ \| สถานะ \| ผลตรวจสอบ" | A list per `dataFound` group, items as sent | Backend text may not be split into columns |
   | Content for P1–P8 | A scope notice page (no API call, no status or number) | Not in scope; no configuration exists |

   Counts on the PS overview are tallies of values the backend sent. `Verified` / `Approved` have no source yet (4.6),
   so they show `—` while every value is `null`.

10. **PS overview and labels (v0.4.0).**
    * **Readiness (ความพร้อม) has no source.** Neither the configuration nor the API provides a programme readiness
      value or a rule to compute one, so the page shows `—` with "ระบบยังไม่ได้ส่งค่าความพร้อมมา จึงยังแสดงเป็นค่าว่าง".
      No percentage is derived. The same holds for the overall status (4.5).
    * **Thai labels are display only.** `frontend/src/app/sourceLabels.js` (collection names) and `fieldLabels.js`
      (field names, in priority order) only name what the backend traced. They never select, filter or evaluate data,
      and a field outside `fieldLabels.js` (e.g. `_id`, `personId`, `curriculumId`, `appointmentOrder` as an object) is
      not shown on a card. The labels are not defined by the Data Dictionary; its owner should confirm the wording.
    * **Status wording is display only.** PASS / FAIL / REVIEW / N/A are shown as ผ่านเกณฑ์ / ไม่ผ่านเกณฑ์ /
      ต้องตรวจสอบเพิ่มเติม / ไม่เข้าข่ายต้องตรวจ; the status itself always comes from the backend.

11. **PS cards and requirement texts in the frontend (decided by the product owner).** PS-01…PS-09 always have a
    card: the backend's result when it sent one, otherwise an empty state ("—", no status, number or evidence; while
    the database is empty, "กำลังรอข้อมูล"). The API cannot supply the list or the texts without a curriculum: with no
    curriculum in the database it returns no results even when `ps_requirements` exists, and a new endpoint was out of
    scope. Therefore:
    * `frontend/src/app/psGuideline.js` holds the **PS codes only** (the base list; `src/test/guideline.test.jsx`
      fails if it differs from the active configuration `backend/tests/fixtures/ps_config_v1.json`).
    * `frontend/src/app/psTitles.js` holds the **locked requirement texts** (product owner, 2026-09-25). The API's
      `requirement` is always shown when it is sent; the locked text is used only when it is not.
      `src/test/psTitles.test.jsx` fails if a text differs from the active configuration.

    This is an **exception to SRS §11/§12/§31/§32**, limited to display; it is never used to evaluate. **To remove the
    exception:** add a read-only endpoint that returns the active configuration's `psCode` + `requirement`, and read it
    instead.

## 5. Observations on the configuration's own content

* `backend/tests/fixtures/ps_config_v1.json` is the project's **active** configuration file (used by the tests, the
  seed script and the frontend tests; the application reads `ps_requirements` in MongoDB at runtime, never this file).
  It follows the project owner's file and differs from it in PS-08, PS-05 and PS-06, as recorded in
  `backend/tests/fixtures/PROVENANCE.md`.
