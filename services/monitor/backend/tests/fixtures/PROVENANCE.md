`ps_config_v1.json` is the project's copy of the authoritative PS Config (the Data Import
team's `ps_requirements` content). It is TEST-ONLY for the application: it stands in for the
`ps_requirements` collection in tests, and `scripts/seed_test_data.py` copies it into test
databases. Application code never reads it. Do not edit it except to follow the authoritative
config; record every difference from the authoritative file here.

Base: `Mornitor-Data/PS-Config-v1(3)-PS08-updated(3)-degree-ordering.json` (2026-09-25, the project owner's
config: `PS-Config-v1.json` plus PS-08 `experience.source` and PS-05 `degree.ordering`).

Differences from the base, each required by the Data Schema (`app/models/source_schema.py`):

- PS-08 `config.join.experiencePersonId: "persons.personId"` is not included. `persons` has no
  field `personId` (its key is `persons._id`), so the engine reported the whole PS-08 join as a
  SPEC GAP. The engine reaches the person record through the Data Schema reference
  `appointments.personId -> persons._id`, so `experience.source` needs no join key.

- PS-08 `config.qualification.condition: {operator: EXISTS}` and
  `config.experience.condition: {operator: "==", value: true}` are added: the project owner's PS-08
  rule (2026-09-25). A special instructor passes with a qualification (some `educations.degree`) and
  `persons.hasTeachingExperience == true`; no `educations` record, or `false`, fails; an education
  record without a degree, or no `hasTeachingExperience`, is a review. Nothing else about experience
  (years, kind, relevance) is judged.

- PS-05 `config.degree.aliases` and `config.degree.normalization` are added (project owner
  2026-09-27, from the degree forms found in the real data `aunqa_ps`). `ordering` and `minimum` are
  unchanged. Before: `{field: degree, minimum: master, ordering: [bachelor, master, Ph.D.]}`. Added:
  `aliases: {bachelor: [วท.บ., บธ.บ., วบ.บ.], master: [วท.ม.], Ph.D.: [ปร.ด.]}` (exactly the owner's lists;
  `วบ.บ.` added 2026-09-27 in the owner's second PS-05 request) and
  `normalization: {enabled: true, remove: [" ", "."], caseInsensitive: true}` (blanks, dots and letter
  case do not count: `ปร. ด.`, `วท.บ`, `PhD.` rank as written above). Any other form (e.g. `วศ.ม.`,
  `วศ.บ.`, `สท.บ`) is not given by the owner and stays unlisted.

- PS-06 `config` is replaced (the lecturer's decision, 2026-09-29: user confirmation 100%). The system no
  longer decides whether a qualification relates to the curriculum, so every automatic-comparison key is
  removed: `programmeField`, `normalization`, `comparison`, `fieldMappings` (with its aliases and related
  fields), `reviewCondition`, and the `exact / related / unrelated / unknown` result map. The new config keeps
  the same `targetCollection`, `appointment` and `join` (who the reviewer sees: each programmeResponsible
  lecturer of the curriculum), shows `qualification` (`educations.degree`), `qualificationField`
  (`educations.field`) and `institution` (`educations.institution`) as information only (no condition), and
  adds `review: {required: true, reviewByUser: true, allowManualResult: [PASS, FAIL]}` with
  `result: {pass, fail, review, na}`. `requirement` and `active` are unchanged.

Kept from the base: PS-08 `config.experience.source: "persons.hasTeachingExperience"` (Import
Service SRS §15; docs/TESTING.md T-14). The same changes (PS-08, PS-05 and PS-06) must be applied to the real
`ps_requirements` by its owner. Until PS-06 is, the engine reports the old PS-06 config as REVIEW + spec_gap
(it has no automatic comparison any more), never PASS or FAIL.

---

`generation_readiness_v1.json` is the generation readiness configuration document, one more
document of the same `ps_requirements` collection (TEST-ONLY for the application in the same way;
`scripts/seed_test_data.py` copies it into test databases).

Source: `~/Downloads/PS-Config-with-Generation-Readiness.json` (2026-09-26 12:05, sha1
`8d94adfc00bb3f155ec0b4fc1ffc2ba32a125ae8`, the project owner's config). Its `generationReadiness`
object is copied verbatim. Its `psConfigurations` equal `ps_config_v1.json` exactly (checked
2026-09-26), so `ps_config_v1.json` is unchanged.

Document shape set by the project owner (2026-09-26): `{"configType": "generationReadiness",
"generationReadiness": {...}}`. `configType` tells it apart from the PS configurations; it has no
`psCode` (it is not a Programme Standard) and no `active`. The real `ps_requirements` needs the same
document, added by its owner.
