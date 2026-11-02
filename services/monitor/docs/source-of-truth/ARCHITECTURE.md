# ARCHITECTURE — Mornitor (AUN-QA PS Monitor)

> **สถานะเอกสาร:** Source of Truth · จัดทำ 2026-09-26 จาก working tree (commit `66ea7f5` + การเปลี่ยนแปลงที่ยังไม่ commit)
> **เอกสารชุดเดียวกัน:** [PS-Config.json](PS-Config.json) · [SRS.md](SRS.md) · [SCOPE.md](SCOPE.md) · [Data-Schema.md](Data-Schema.md) · [API.md](API.md)
> เอกสารนี้อธิบาย architecture ตามที่ code เป็นจริง ไม่ได้เสนอการเปลี่ยนแปลง

## 1. ภาพรวม

```text
┌───────────────────────────── Browser ─────────────────────────────┐
│ React 19 (frontend/src)                                            │
│  pages ─► api/monitorApi ─► api/client (GET; POST verify) ─► /api/.. │
│  display helpers: explain / missingText / fieldLabels / psTitles   │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ HTTP GET (dev/preview: Vite proxy /api → MORNITOR_API_TARGET)
┌──────────────────────────────▼─────────────────────────────────────┐
│ FastAPI (backend/app/main.py, CORS: GET, POST)                      │
│  api/routes/monitor.py ─► api/dependencies.get_service (1 ตัวต่อ process) │
│        │                                                            │
│        ▼                                                            │
│  services/MonitoringService                                         │
│    ├─ ConfigurationRepository ─► MongoConfigurationAdapter ─┐       │
│    ├─ SourceDataRepository   ─► MongoSourceDataAdapter ─────┤ find  │
│    ├─ RuntimeReferences (currentYear)                       │       │
│    ├─ NoManualResults (ผลของผู้ตรวจไม่ override สถานะ)          │       │
│    └─ MonitoringEngine                                      │       │
│         ConfigurationInterpreter + subject_interpreter      │       │
│         → GenericExecutionRequest                           │       │
│         → capabilities / subject_checks / mapping           │       │
│         → EvaluationContext (อ่านข้อมูลผ่าน repository, trace) │       │
└─────────────────────────────────────────────────────────────┼───────┘
                                                              ▼
            MongoDB: ps_requirements (config DB) · curricula, appointments, educations,
                     academic_works, persons, documents (source DB) — อ่านอย่างเดียว
```

## 2. Flow จริงเทียบกับ Flow ที่คาดไว้

Flow ที่คาดไว้คือ `MongoDB → Backend → Configuration / Source Data → Rule Engine → FastAPI → React MONITOR`

ใน code จริง **frontend เป็นฝ่ายเริ่ม** และ **engine ดึงข้อมูลต้นทางเองระหว่างประเมิน** (ไม่โหลดล่วงหน้าทั้งหมด)

```text
ทิศทาง request:  React ─GET─► FastAPI route ─► MonitoringService ─► repositories ─► MongoDB
ทิศทางข้อมูล:    MongoDB ─► repositories ─► MonitoringService
                   ├─ configuration (ps_requirements, active) ────────────┐
                   ├─ curriculum ที่ตรวจ ─► EvaluationContext               │
                   └─ MonitoringEngine: ตีความ config ─► query ข้อมูลต้นทาง ◄┘
                                          ผ่าน EvaluationContext ทีละเกณฑ์
                 ─► PSResult (Pydantic) ─► JSON camelCase ─► React ─► หน้าเว็บ
```

## 3. Backend

### 3.1 Layer และไฟล์

| Layer | ไฟล์ | หน้าที่ |
|---|---|---|
| Entry | `backend/app/main.py` | สร้าง FastAPI app, CORS (`GET` เท่านั้น), รวม router |
| API | `backend/app/api/routes/monitor.py` | 2 endpoint; แปลง exception เป็น `409` / `503`; ไม่มี business logic |
| Composition root | `backend/app/api/dependencies.py` | `get_service()` (`lru_cache`): อ่าน `Settings` และสร้าง adapter, repository, service **ครั้งเดียวต่อ process** |
| Error logging | `backend/app/error_log.py` | `configure_logging()` (handler เดียวบน logger `app`, stderr, WARNING ขึ้นไป, `RedactingFormatter` ซ่อน user:password ใน URL) · หมวด configuration / data source / connection / evaluation / system error · เรียกจาก `main.py` (middleware `system_error`), routes (`503`), service (`configuration_error`), engine (`evaluation_error`) |
| Settings | `backend/app/settings.py` | ตัวแปรสภาพแวดล้อม `MORNITOR_*` (infrastructure เท่านั้น) |
| Service | `backend/app/services/monitoring_service.py` | โหลด configuration ที่ active, เลือกหลักสูตร (`409` เมื่อกำกวม), ส่งให้ engine, ใส่ evidence ให้ทุกผล, รวมผล (`overallStatus = null`) |
| Evidence | `backend/app/services/evidence.py` | อ่าน `documents` ของหลักสูตรผ่าน `SourceDataRepository.find` (`curriculumId`) แปลงเป็น `EvidenceItem` (`fileName`, `_id`, `originalFile.storage/.path`) ไม่ผ่าน engine จึงไม่อยู่ใน traceability |
| Generation Readiness | `backend/app/services/generation_readiness.py` | ตรวจเอกสาร `configType: generationReadiness` และตัดสิน READY / NOT_READY จาก `results` ไม่มีค่าใดของ config อยู่ใน code |
| Engine | `backend/app/monitoring/engine.py` | ตีความ → ประมวลผล → สร้าง `PSResult`; กำหนด `issue`; แยกความล้มเหลวเป็นรายเกณฑ์ |
| Interpreter | `monitoring/interpreter.py`, `subject_interpreter.py`, `interpreter_base.py` | แปลง `config` เป็น `GenericExecutionRequest` หรือรายงาน SPEC GAP / configuration error |
| Execution model | `monitoring/request.py` | Measure และ Check (Count, Formula, FieldsPresent, Review, Subject, Exists, AtLeast, Show, Mapping) |
| Capabilities | `monitoring/capabilities.py`, `subject_checks.py`, `mapping.py` | FILTER, GROUP, JOIN, COUNT, DISTINCT, COMPARE, FORMULA, WINDOW, NORMALIZE, MAP |
| Context | `monitoring/context.py` | อ่านข้อมูลผ่าน repository, บันทึก traceability, หาชื่อที่แสดง (ไม่ trace) |
| References | `backend/app/references/runtime.py`, `monitoring/reference.py` | `currentYear` = ปีของเครื่อง + `MORNITOR_YEAR_OFFSET` |
| Manual results | `monitoring/manual.py` | port `ManualResultSource`; production ใช้ `NoManualResults` (ผลที่ผู้ตรวจบันทึกไม่ถูกส่งเข้า engine — เจ้าของ project 2026-09-26) |
| User review | `backend/app/services/user_review.py` | อ่าน `config.review` ว่า PS ใดให้ผู้ใช้ตรวจและเลือกได้ค่าใด (`allowManualResult`); service บันทึก/อ่าน `review` ผ่าน `MonitoringResultRepository` |
| Monitor-owned persistence | `backend/app/repositories/monitoring_results.py`, `backend/app/adapters/monitoring_results.py` | collection `monitoring_results` (database `MORNITOR_RESULTS_DB_*`) key curriculumId + psCode · เก็บ `verification` (SET 4), `review` (SET 5) และ `result` (SET 6, Persistent Monitoring Result) ด้วย `$set` คนละ sub-document · adapter นี้เป็นที่เดียวที่เขียน database (`update_one` / `bulk_write` แบบ upsert + unique index) · engine ไม่อ่านและไม่เขียน · `test_engine_and_api.py` บังคับ |
| Repositories | `backend/app/repositories/configuration.py`, `source_data.py`, `base.py` | อ่านอย่างเดียว; source repository ยอมรับเฉพาะ collection ใน Data Schema; configuration repository ไม่ส่งเอกสารที่มี `configType` เป็น PS และอ่านเอกสารตาม `configType` ได้ (`load_by_type`) |
| Adapters | `backend/app/adapters/mongo.py` | pymongo `find` เท่านั้น; แปลง `PyMongoError` เป็น `DataSourceError` |
| Adapters (placeholder) | `backend/app/adapters/external_services.py` | `ExternalServiceAAdapter` / `ExternalServiceBAdapter` ว่าง (TBD) ไม่มี code ใดเรียก · Document Generation ไม่ต้องใช้ adapter เพราะเป็นฝ่าย pull (docstring) |
| Models | `backend/app/models/schemas.py`, `source_schema.py`, `status.py` | response model (camelCase), Data Schema ใน code, Status enum · `ProgrammeReadiness` (PASS ÷ 9 × 100) คำนวณเป็น computed field ของ `MonitorResponse` จาก `results` — อยู่ใน models เพราะค่าคงที่ 9 และคำว่า programme เป็นค่าที่เจ้าของ project กำหนดตายตัว ซึ่ง `test_architecture.py` ไม่อนุญาตใน `monitoring/`, `services/`, `api/` |

### 3.2 ลำดับการทำงานของ `GET /api/monitor`

1. `get_monitor()` เรียก `MonitoringService.monitor(curriculumCode)`
2. `ConfigurationRepository.load_active_requirements()` → `find({active: true})` → เก็บเฉพาะ `active is True` ที่ไม่มี `configType` → เรียงตาม `psCode`
   - `ConfigurationRepository.load_by_type("generationReadiness")` → `find({configType: "generationReadiness"})` ใน `ps_requirements` เดียวกัน
3. `_load_curriculum()` → `find(curricula)`
   - มากกว่า 1 หลักสูตร → `CurriculumSelectionUndefined` → `409`
   - ไม่พบ → ผลว่าง
4. สร้าง `EvaluationContext` (หลักสูตร, source repository, references, manual results)
5. `evidence_of()` → `find(documents, {curriculumId})` ครั้งเดียวต่อ request
6. ต่อเอกสาร configuration: `MonitoringEngine.evaluate()` แล้วเติม `evidence` (ผลอื่นไม่เปลี่ยน)
   - `ConfigurationInterpreter.interpret(config)` → ถ้ามี error หรือ gap ได้ REVIEW + `configuration_error` / `spec_gap`
   - `_execute()` ตามชนิด Measure; อ่านข้อมูลผ่าน `EvaluationContext.find()` ซึ่งบันทึก traceability
   - exception ที่ไม่คาดคิด → REVIEW + `evaluation_error` และ log ERROR `[evaluation_error]` เฉพาะเกณฑ์นั้น
   - `DataSourceError` → ส่งต่อขึ้นไปเป็น `503`
7. `generation_readiness.decide()` → `generationReadiness` (ไม่มีหลักสูตรก็ตัดสิน: ทุก PS ไม่มีผล)
   - `MonitorResponse.programme_readiness` (computed) → `programmeReadiness` จาก `results` (ไม่มีหลักสูตร → `null`)
8. Pydantic แปลงเป็น JSON แบบ camelCase

ไม่มี cache ของ configuration หรือข้อมูล การเปลี่ยนใน database มีผลตั้งแต่ request ถัดไป

## 4. Rule Engine

**หลักการที่บังคับด้วย test** (`backend/tests/test_architecture.py`):
- code ของ engine, service และ API ไม่มีคำ business เช่น role, degree, master, experience
- ไม่มีค่าใดจาก configuration ที่ยาว 4 ตัวอักษรขึ้นไป
- ไม่มีตัวเลขอื่นนอกจาก 0, 1, -1
- ไม่มีค่าคงที่ business ระดับ module
- engine ไม่ import adapter หรือ driver ของ database และอ่านข้อมูลผ่าน repository เท่านั้น
- route handler เรียก `MonitoringService` เท่านั้น
- repository ของ configuration แยกจากของข้อมูลต้นทาง
- source repository ปฏิเสธ collection ที่ไม่อยู่ใน Data Schema (รวม `ps_requirements`)

**Status ของผล:**
- มาจาก map `config.result` ของเกณฑ์นั้นเสมอ
- เมื่อตัดสินไม่ได้ใช้ `result.review` ถ้าไม่มีจึงใช้ `result.unknown` ถ้าไม่มีทั้งคู่เป็น `configuration_error`
- เกณฑ์แบบต่อบุคคล: มีคนใด FAIL → FAIL, ทุกคน PASS → PASS, นอกนั้น → REVIEW

## 5. Construct ของ Configuration ที่ engine รู้จัก

| Construct | ความหมาย | ใช้ใน config ACTIVE |
|---|---|---|
| `targetCollection` / `targetCollections` | collection ที่อ่าน (ต้องอยู่ใน Data Schema) | ทุก PS |
| `filter {field: value}` | กรองแบบเท่ากับ | PS-01 |
| `<prefix><Field>: value \| [values]` | กรองด้วย field ที่เป็นคำสุดท้ายของชื่อ key (เช่น `targetRole` → `role`) | PS-02, 03, 07, 08 |
| `<collection เอกพจน์>: {field: value}` | กรองใน collection นั้น (เช่น `appointment: {role: …}`) | PS-05, 06 |
| `count {field, distinct}` + `condition {operator, value}` | นับ (ไม่ซ้ำ) แล้วเปรียบเทียบ | PS-01 |
| `calculation.formula` + `year.field` + `comparison {operator, value, reference}` | สูตรจำนวนเต็ม (ชื่อ, จำนวนเต็ม, `+`, `-`) กับค่าอ้างอิง | PS-09 |
| `requiredFields` (+ `<field>: {required, requiredFields, <x>Required}`) | ทุก record ต้องมี field ครบ | PS-04 |
| `review {required, reviewByUser, allowManualResult}` | ให้ผู้ใช้ตรวจ (engine ให้ `result.review`) | PS-03, 06 |
| `review` + `join` ที่มีแต่ `{source, required}` | ผู้ใช้ตัดสิน; join บอกว่าผู้ตรวจเห็นอะไร (ทีละบุคคล) · check ที่ตัดสินได้ในนั้นเป็น SPEC GAP | PS-06 |
| `join` (`{from, to}` หรือหลาย `collection.field`) | JOIN; collection ที่เชื่อมกับหลักสูตรเป็นเจ้าของบุคคลที่ตรวจ | PS-05, 06, 07, 08 |
| `matching {same<X>: true}` + `condition {operator: EXISTS, field}` | จับคู่ใน collection เดียวกันด้วย `<x>Id` | PS-02 |
| `{field, period: previous<N>Years}` + `minimumCount` | นับ record ในช่วงปีแล้วเทียบ `>=` | PS-07 |
| `{field, minimum}` | เท่ากับ minimum เท่านั้น (ไม่มีลำดับ) | — |
| `{field, minimum, ordering}` | เปรียบเทียบตามตำแหน่งใน `ordering` | PS-05 |
| `{source, required}` | แสดงให้ผู้ตรวจดู ไม่ตัดสิน | PS-06 |
| `{source, required, condition}` | ตัดสินด้วย `EXISTS` หรือ `{operator, value}` | PS-08 |
| `result`, `naEnabled`, `reviewCondition`, `conditions` | map ของ status, สวิตช์ N/A, ข้อความประกอบ (ไม่ถูกประเมิน) | ทุก PS |

operator ที่รองรับ: `>=`, `>`, `<=`, `<`, `==`, `!=` และ `EXISTS` (ใน `matching` และ `condition`)

key ที่ไม่รู้จักเป็น SPEC GAP ค่าที่ผิดชนิดเป็น configuration error ของเกณฑ์นั้นเท่านั้น

## 6. Frontend

| ส่วน | ไฟล์ | หน้าที่ |
|---|---|---|
| Entry | `frontend/src/main.jsx`, `index.html` | `BrowserRouter`, โหลด `tailwind.css` และ `styles.css` |
| Routing | `frontend/src/app/App.jsx`, `Layout.jsx` | route ตาม [SRS.md](SRS.md) §4; แถบบน (AUN-QA + PS-01..PS-09 ในส่วน PS) |
| API layer | `frontend/src/api/*` | `GET` เท่านั้น, adapter, อ่านซ้ำทุก 10 วินาที ([API.md](API.md) §9) |
| Pages | `frontend/src/pages/Home`, `Monitor`, `PSDetail`, `ScopeNotice` | หน้าเว็บ 4 แบบ |
| Components | `frontend/src/components/*` | PSCard, GuideCard, Status, IssueBadge, Traceability, Evidence, Verification, MissingInformation, MissingOverview, ProgrammeReadiness, EvidenceStatus, Completeness, CurriculumBox, UIState, Section, ResultText |
| Display helpers | `app/explain.js`, `missingText.js`, `fieldLabels.js`, `sourceLabels.js` | แปลงค่าที่ backend ส่งเป็นข้อความไทย ไม่ตัดสินผล |
| รายการคงที่ | `app/psGuideline.js` (PS code), `app/psTitles.js` (requirement สำรอง), `app/criteriaGroups.js` (เมนูหน้าแรก) | ข้อยกเว้นที่เจ้าของ project อนุมัติ ([SRS.md](SRS.md) §16) |
| Style | `app/styles.css` | CSS ของหน้าเว็บทั้งหมด (โหมดสว่าง, grid 3 / 2 / 1 คอลัมน์) |

- **State:** แต่ละหน้าใช้ `useRemote` ของตัวเอง ไม่มี global store
- **หน้าภาพรวม:** อ่านใหม่ทุกครั้งที่เข้าหน้า (`useLocation().key`) และทุก 10 วินาที
- **Tailwind CSS v4:** ตั้งค่าไว้ใน `vite.config.js` และ `tailwind.css` แต่ไม่มี component ใช้ class ของ Tailwind ใน build มีแค่ utility `.visible` และ `.fixed` ซึ่งมาจากคำใน comment

## 7. Configuration และ Runtime

| หัวข้อ | ค่า |
|---|---|
| ตัวแปรฝั่ง backend | `MORNITOR_DB_URI`, `MORNITOR_DB_NAME`, `MORNITOR_CONFIG_DB_URI`, `MORNITOR_CONFIG_DB_NAME`, `MORNITOR_RESULTS_DB_URI`, `MORNITOR_RESULTS_DB_NAME`, `MORNITOR_CORS_ORIGINS`, `MORNITOR_YEAR_OFFSET` |
| ตัวแปรฝั่ง frontend | `MORNITOR_API_TARGET` (proxy), `VITE_API_BASE_URL` (ตอน build) |
| พอร์ตตาม `README.md` | backend `8000` (uvicorn), frontend dev `5173`, preview `4173` · Docker: หน้าเว็บ `8080`, API `8000` (เฉพาะ `127.0.0.1`) |
| Docker | `compose.yaml`: `backend` (`python:3.11-slim`, uvicorn, user ไม่ใช่ root) + `frontend` (build ด้วย `node:22-slim`, เสิร์ฟด้วย nginx ซึ่งส่ง `/api/` ต่อให้ `backend:8000`) · ไม่มี MongoDB ใน compose: ต่อ database บนเครื่องผ่าน `host.docker.internal` · ค่าใน `.env` (แม่แบบ `.env.example`) ส่งตอนรัน ไม่อยู่ใน image |
| Configuration: ACTIVE FILE | `backend/tests/fixtures/ps_config_v1.json` (test, seed script และ test ของ frontend ใช้ไฟล์นี้) |
| Configuration: RUNTIME | MongoDB collection `ps_requirements` backend อ่านที่นี่เท่านั้น ไม่อ่านไฟล์ configuration ใด ๆ ตอนทำงาน ต้องนำเนื้อหาของ ACTIVE FILE เข้า collection นี้ก่อน |
| Configuration: DOCUMENTATION SNAPSHOT | `docs/source-of-truth/PS-Config.json` ไม่มี code ใดอ่าน |
| Dependency backend | `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `pymongo>=4.8`, `pydantic>=2.8` (+ dev: `pytest`, `httpx2`, `httpx`, `PyYAML`) |
| Dependency frontend | `react ^19.3.0`, `react-dom`, `react-router-dom ^7.18.4` (+ dev: vite 8, vitest 5, testing-library, jsdom, tailwindcss 4) |

## 8. Test Architecture

| ชุด | เครื่องมือ | จำนวน (2026-09-27, หลังแก้ PS-05 / PS-07) | หมายเหตุ |
|---|---|---|---|
| Backend unit / integration | pytest + in-memory adapter (`tests/support/memory_store.py`) + FastAPI `TestClient` | 1033 passed | ใช้ config ACTIVE เป็น fixture (`tests/support/fixtures.py`) |
| Backend parity | pytest + `mongod` ชั่วคราว | 19 (รวมใน 1033) | ข้ามเมื่อเครื่องไม่มี `mongod` · ยืนยันว่า adapter ของ source / config ไม่เขียน database และการยืนยัน / ผลของผู้ตรวจ / ผลที่บันทึกเขียนเฉพาะ `monitoring_results` |
| Backend robustness | สุ่ม config / ข้อมูลผิดรูปแบบ 300 แบบ | 311 (รวมใน 1033) | `tests/test_robustness.py` |
| Docker files | pytest อ่าน `compose.yaml`, `.env.example`, Dockerfile, `nginx.conf` | 12 (รวมใน 1033) | `tests/test_docker.py` · build / run ตรวจตาม `docs/TESTING.md` §0.1 |
| รูปแบบวุฒิ / ปี (PS-05 / PS-07) | pytest + config ACTIVE + `RuntimeReferences` ที่กำหนดวันที่ | 113 (รวมใน 1033) | `tests/test_degree_and_year_forms.py` · กรณีของเจ้าของ project 2026-09-27, config ผิด, API, ข้อมูลจริงจาก `DB-DATA/` (ข้ามเมื่อไม่มีโฟลเดอร์นี้) |
| Frontend | vitest + jsdom + Testing Library | 339 passed (19 ไฟล์) | อ่าน config ACTIVE เพื่อตรวจ `psGuideline.js` / `psTitles.js`; ใช้ `test/fixtures/backend-sample.json` |
| ข้อมูลทดสอบถาวร | `backend/scripts/seed_test_data.py` | — | เขียนได้เฉพาะ database ที่ชื่อลงท้าย `_test` |

## 9. เทียบกับ Architecture ใน [SRS-M] §5 และ §59

| Component ใน [SRS-M] | ใน code |
|---|---|
| Configuration DB | collection `ps_requirements` (database แยกได้ด้วย `MORNITOR_CONFIG_DB_*`) |
| Configuration Loader | `ConfigurationRepository` + `MongoConfigurationAdapter` |
| Data Access Layer | `SourceDataRepository` + `MongoSourceDataAdapter` + `EvaluationContext` |
| Configuration-driven Evaluation Engine | `MonitoringEngine` + interpreters + capabilities |
| Verification Result | `PSResult.verification` (คำนวณใหม่ทุก request; การยืนยันของผู้ใช้เก็บใน `monitoring_results`) |
| Monitoring API | FastAPI `api/routes/monitor.py` |
| Web UI | React `frontend/` |
| Traceability | `EvaluationContext` → `PSResult.traceability` |
| External Service: Document Generation | pull: Generator → `GET /api/monitor?curriculumCode=` → `generationReadiness.status` → Generator ดึงข้อมูลจาก DB ของตัวเอง · Mornitor ไม่มี outbound call ([API.md](API.md) §3.2) |
| External Service A / B | class ว่างใน `adapters/external_services.py` (ไม่มี service ใดใช้) |

## 10. สิ่งที่ยังไม่มีใน Architecture

- ประวัติของผลการตรวจที่บันทึก (เก็บเฉพาะครั้งล่าสุด ตามที่เจ้าของ project เลือก)
- Authentication / Authorization ([SRS-M] §51 TBD)
- External Service อื่นนอกจาก Document Generation ([SRS-M] §6 TBD)
- Logging นอกเหนือจาก Error Logging (audit, activity, request, metrics) และการเก็บ / หมุนไฟล์ log ([SRS-M] §54 TBD)
- Cache หรือ performance target ([SRS-M] §52 TBD)
- การ deploy สำหรับผู้ใช้หลายคน (reverse proxy ภายนอก, HTTPS, orchestration) · Docker ที่มีอยู่ตั้งใจให้ใช้บนเครื่องเดียว (พอร์ตเฉพาะ `127.0.0.1`)
