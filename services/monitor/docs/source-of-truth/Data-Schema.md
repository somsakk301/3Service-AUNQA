# Data-Schema — Mornitor (AUN-QA PS Monitor)

> **สถานะเอกสาร:** Source of Truth · จัดทำ 2026-09-26 จาก working tree (commit `66ea7f5` + การเปลี่ยนแปลงที่ยังไม่ commit)
> **เอกสารชุดเดียวกัน:** [PS-Config.json](PS-Config.json) · [SRS.md](SRS.md) · [SCOPE.md](SCOPE.md) · [API.md](API.md) · [ARCHITECTURE.md](ARCHITECTURE.md)
> รหัสแหล่งอ้างอิง ([SRS-M], [DD], [DS], [IMP]) ใช้ตาม [SRS.md](SRS.md)

## 1. ภาพรวม

| หัวข้อ | Current Implementation |
|---|---|
| Database | MongoDB |
| ตำแหน่ง | ข้อมูลต้นทาง: `MORNITOR_DB_URI` / `MORNITOR_DB_NAME` (ค่าเริ่มต้น `mongodb://localhost:27017` / `mornitor_source`) · configuration: `MORNITOR_CONFIG_DB_URI` / `MORNITOR_CONFIG_DB_NAME` (ค่าเริ่มต้นเท่ากับของข้อมูลต้นทาง) · ผลของ Monitor (`monitoring_results`): `MORNITOR_RESULTS_DB_URI` / `MORNITOR_RESULTS_DB_NAME` (ค่าเริ่มต้นเท่ากับของข้อมูลต้นทาง) — `backend/app/settings.py` |
| การเข้าถึงของระบบ | **Source Data และ Configuration: อ่านอย่างเดียว** ผ่าน `pymongo` `find()` เท่านั้น (`backend/app/adapters/mongo.py`) ไม่มี insert / update / delete · **ผลของ Monitor (`monitoring_results`): เขียนได้** เฉพาะใน `backend/app/adapters/monitoring_results.py` (`update_one` แบบ upsert + unique index; ไม่มี delete / replace) — `test_engine_and_api.py` บังคับ (เจ้าของ project 2026-09-26) |
| รายชื่อ field ที่ระบบรู้จัก | `SOURCE_SCHEMA` ใน `backend/app/models/source_schema.py` (คัดจาก [DD] / [DS] และ `persons.hasTeachingExperience` จาก [IMP] §15) ทุก field ที่ configuration อ้างถึงต้องอยู่ในรายการนี้ มิฉะนั้น engine รายงาน SPEC GAP |
| หลักฐานการอ่านจริง | รัน engine กับข้อมูลทดสอบ (`backend/tests/support/fixtures.py` + อาจารย์พิเศษ 1 คน) แล้วบันทึกทุก query และทุก field ที่ trace (2026-09-26) ผลอยู่ใน §3 |
| ที่เขียนข้อมูลต้นทาง / configuration ได้ (เครื่องมือทดสอบเท่านั้น) | `backend/scripts/seed_test_data.py` เขียนเฉพาะ database ที่ชื่อลงท้าย `_test` · `backend/tests/test_backend_parity.py` เขียนลง `mongod` ชั่วคราวที่ test สร้างเอง |

ณ วันที่จัดทำ MongoDB ของเครื่องนี้ (`localhost:27017`) มีเฉพาะ database `admin`, `aunqa_monitor`, `ps_checker` (ตรวจชื่อ collection เท่านั้น) ไม่มี database ของ Mornitor ข้อมูลจริงของทีมจึงเป็น **ข้อมูลไม่เพียงพอ**

## 2. สรุป Collection

| Collection | Purpose | Used By | Read/Write | config ACTIVE อ่านหรือไม่ |
|---|---|---|---|---|
| `curricula` | ข้อมูลหลักสูตร | เลือกหลักสูตร, หัวข้อหลักสูตรใน API, PS-09 | Read | ✔ |
| `appointments` | การแต่งตั้งและบทบาทในหลักสูตร | PS-01 ถึง PS-08 | Read | ✔ |
| `educations` | คุณวุฒิ | PS-05, PS-06, PS-08 | Read | ✔ |
| `academic_works` | ผลงานวิชาการ | PS-07 | Read | ✔ |
| `persons` | บุคคล / อาจารย์ | ชื่อที่แสดง (ทุก PS ที่มี `personId`), PS-08 | Read | ✔ |
| `ps_requirements` | configuration ของเกณฑ์ | ทุก PS | Read | (เป็นตัว configuration เอง) |
| `documents` | เอกสารและ path ของไฟล์ | Evidence (`evidence` ของทุก PS) | Read | ✖ (อ่านโดย service ไม่ใช่ configuration) |
| `data_usages` | mapping ว่าข้อมูลใดใช้ตอบ PS / template ใด | test ของ engine เท่านั้น | ไม่ถูกอ่านในระบบจริง | ✖ |
| `generated_documents` | เอกสาร PS ที่ระบบอื่นสร้าง | — | ไม่ถูกอ่าน | ✖ |
| `monitoring_results` | ผลของ Monitor ต่อ curriculumId + psCode: การยืนยัน (SET 4), ผลการตรวจของผู้ตรวจ (SET 5) และผลการตรวจที่บันทึกไว้ (SET 6) (§4.9) | Verification, User Review, Persistent Monitoring Result | **Read + Write** (Monitor เป็นเจ้าของ) | ✖ (ไม่ใช่ข้อมูลต้นทางหรือ configuration) |

ไม่มี collection อื่นที่ code อ้างถึง นอกจาก 10 collection ในตารางนี้ (source 8, `ps_requirements`, `monitoring_results`) · ข้อมูลต้นทางและ configuration อ่านอย่างเดียว · `monitoring_results` เป็นที่เดียวที่ Mornitor เขียน

## 3. Query ที่เกิดจริง (หลักฐาน)

| Collection | เงื่อนไขที่ใช้ค้น | เกิดจาก |
|---|---|---|
| `curricula` | `{}` (ไม่ระบุหลักสูตร) / `{curriculumCode}` / `{_id}` | เลือกหลักสูตร; PS-09 |
| `appointments` | `{curriculumId}`, `{curriculumId, role}`, `{curriculumId, role ∈ […]}`, `{role, curriculumId ∈ […], personId ∈ […]}` | PS-01 ถึง PS-08 |
| `educations` | `{personId ∈ […]}` | PS-05, PS-06, PS-08 |
| `academic_works` | `{personId ∈ […]}` | PS-07 |
| `persons` | `{_id ∈ […]}` | ชื่อที่แสดง, PS-08 |
| `documents` | `{curriculumId}` | Evidence (ทุก request ที่มีหลักสูตร) |
| `monitoring_results` | อ่าน `{curriculumId}` · เขียน `{curriculumId, psCode}` (upsert) | อ่านทุก request ที่มีหลักสูตร; เขียนเฉพาะ `POST …/verification`, `POST …/review` และ `POST /api/monitor/results` (bulk upsert ทุก PS ที่ active) |
| `ps_requirements` | `{active: true}` / `{psCode}` / `{configType: "generationReadiness"}` | ทุก request (`configType` เฉพาะ `GET /api/monitor`) |

Field ที่ถูก trace (ใช้ตัดสินผล) ต่อ PS:

| PS | Field |
|---|---|
| PS-01 | `appointments.role`, `appointments.personId` |
| PS-02 | `appointments.role`, `appointments.curriculumId`, `appointments.personId` |
| PS-03 | `appointments.role` |
| PS-04 | `appointments.personId`, `role`, `roleName`, `appointmentOrder`, `appointmentOrder.orderNumber`, `appointmentOrder.orderDate` |
| PS-05 | `appointments.role`, `appointments.personId`, `educations.personId`, `educations.degree` |
| PS-06 | `appointments.role`, `appointments.personId`, `educations.personId`, `educations.degree`, `educations.field`, `educations.institution` (แสดงให้ผู้ใช้ยืนยัน ไม่ตัดสิน) |
| PS-07 | `appointments.role`, `appointments.personId`, `academic_works.personId`, `academic_works.publicationYear` |
| PS-08 | `appointments.role`, `appointments.personId`, `educations.personId`, `educations.degree`, `persons._id`, `persons.hasTeachingExperience` |
| PS-09 | `curricula.curriculumYear` |

---

## 4. รายละเอียดแต่ละ Collection

ป้ายในคอลัมน์ "การใช้งาน": **ตัดสินผล** = engine อ่านและบันทึกใน traceability · **ขอบเขต** = ใช้จำกัด record ให้อยู่ในหลักสูตรที่ตรวจ · **แสดงผล** = ใช้เป็นชื่อหรือหัวข้อเท่านั้น ไม่ได้ trace และไม่เปลี่ยนผล · **ไม่ถูกอ่าน** = ประกาศไว้แต่ config ACTIVE ไม่ได้ใช้

### 4.1 `curricula`

- **Purpose:** ข้อมูลหลักสูตรและ version ([DD] §1)
- **Used By:**
  - `MonitoringService._load_curriculum` เลือกหลักสูตร
  - `CurriculumInfo` หัวข้อหลักสูตรใน API
  - PS-09
- **Read/Write:** Read

| Field | ชนิด (code) | การใช้งาน |
|---|---|---|
| `_id` | ObjectId | ขอบเขต: เป็น key ที่ collection อื่นอ้างถึง (`CURRICULUM_KEY`) |
| `curriculumCode` | String | เลือกหลักสูตรด้วย `?curriculumCode=` (เท่ากันทุกตัวอักษร); ชื่อที่แสดงของหลักสูตร (`DISPLAY_FIELD`); หัวข้อใน API |
| `curriculumName` | String | หัวข้อใน API (แสดงในส่วนยืนยันของ PS-06) |
| `curriculumYear` | Integer | ตัดสินผล PS-09; หัวข้อใน API |
| `version` | Integer | หัวข้อใน API เท่านั้น |
| `status` | String | หัวข้อใน API เท่านั้น (ไม่ใช้กรอง) |
| `timestamp` | Date | ไม่ถูกอ่าน |

**Relationships:** `curricula._id` ← `appointments.curriculumId`, `documents.curriculumId`, `data_usages.curriculumId`, `generated_documents.curriculumId`

ถ้าไม่ระบุ `curriculumCode` และมีมากกว่า 1 หลักสูตร API ตอบ `409` ถ้าไม่มีหลักสูตรเลยจะไม่มีผลการตรวจ

### 4.2 `appointments`

- **Purpose:** การแต่งตั้งและบทบาทของบุคคลในหลักสูตร ([DD] §4)
- **Used By:** PS-01 ถึง PS-08
- **Read/Write:** Read

| Field | ชนิด (code) | การใช้งาน |
|---|---|---|
| `_id` | ObjectId | อ้างอิงใน traceability และ missing information |
| `curriculumId` | ObjectId | ขอบเขต (ทุก query); PS-02 จับคู่หลักสูตรเดียวกัน |
| `personId` | ObjectId | ตัดสินผล PS-01 (นับไม่ซ้ำ); key ของบุคคลใน PS-02, PS-05, PS-06, PS-07, PS-08; ต้องมีใน PS-04 |
| `role` | String | กรองบทบาท (`programmeResponsible`, `programmeStaff`, `specialInstructor` ตาม config); ต้องมีใน PS-04 |
| `roleName` | String | ต้องมีใน PS-04 |
| `appointmentOrder` | Object | ต้องมีใน PS-04 |
| `appointmentOrder.orderNumber` | String | ต้องมีใน PS-04 |
| `appointmentOrder.orderDate` | Date/String | ต้องมีใน PS-04 |
| `effectiveDate` | Date/String | ไม่ถูกอ่าน |
| `status` | String | ไม่ถูกอ่าน (config ไม่มีตัวกรองสถานะ appointment ทุกสถานะจึงถูกนับ) |
| `timestamp` | Date | ไม่ถูกอ่าน |

**Relationships:** `curriculumId` → `curricula._id` · `personId` → `persons._id`

### 4.3 `educations`

- **Purpose:** คุณวุฒิของบุคคล หนึ่งคนมีได้หลายรายการ ([DD] §3)
- **Used By:** PS-05, PS-06, PS-08
- **Read/Write:** Read

| Field | ชนิด (code) | การใช้งาน |
|---|---|---|
| `_id` | ObjectId | อ้างอิงใน traceability |
| `personId` | ObjectId | key ที่ใช้ join กับ `appointments.personId` |
| `degree` | String | ตัดสินผล PS-05 (ตรงกับ `ordering` ทุกตัวอักษร); ตัดสินผล PS-08 (มีค่าหรือไม่) |
| `field` | String | แสดงให้ผู้ใช้ยืนยัน PS-06 (ไม่ตัดสิน) |
| `institution` | String | ไม่ถูกอ่าน |
| `graduationYear` | Integer | ไม่ถูกอ่าน |
| `timestamp` | Date | ไม่ถูกอ่าน |

**Relationships:** `personId` → `persons._id` (หนึ่งคนมีได้หลายรายการ)

### 4.4 `academic_works`

- **Purpose:** ผลงานวิชาการของบุคคล ([DD] §5)
- **Used By:** PS-07
- **Read/Write:** Read

| Field | ชนิด (code) | การใช้งาน |
|---|---|---|
| `_id` | ObjectId | อ้างอิงใน traceability |
| `personId` | ObjectId | key ที่ใช้ join กับ `appointments.personId` |
| `publicationYear` | Integer | ตัดสินผล PS-07 (ช่วง `currentYear − 5` ถึง `currentYear`; ค่าที่ไม่ใช่จำนวนเต็มถือว่าใช้ไม่ได้) |
| `workType`, `title`, `database`, `quartile` | String | ไม่ถูกอ่าน |
| `timestamp` | Date | ไม่ถูกอ่าน |

**Relationships:** `personId` → `persons._id`

### 4.5 `persons`

- **Purpose:** ข้อมูลบุคคล ไม่เก็บ role เพราะบทบาทอยู่ใน `appointments` ([DD] §2)
- **Used By:**
  - ชื่อที่แสดงแทน ObjectId ของ `personId` ทุก PS
  - PS-08
- **Read/Write:** Read

| Field | ชนิด (code) | การใช้งาน |
|---|---|---|
| `_id` | ObjectId | ปลายทางของ `personId`; PS-08 อ่าน record ผ่าน key นี้ |
| `fullName` | String | แสดงผลเท่านั้น (`DISPLAY_FIELD`) ไม่ trace; ถ้าไม่มีจะแสดง "<id> (ไม่พบ persons.fullName)" |
| `hasTeachingExperience` | Boolean | ตัดสินผล PS-08 (`== true`); ไม่มีค่า = ยังไม่ได้ประมวลผล CV ([IMP] §15) |
| `title`, `firstName`, `lastName`, `academicPosition` | String | ไม่ถูกอ่าน |
| `timestamp` | Date | ไม่ถูกอ่าน |

**Relationships:** `persons._id` ← `appointments.personId`, `educations.personId`, `academic_works.personId`

### 4.6 `ps_requirements` (configuration)

- **Purpose:** เกณฑ์ PS-01 ถึง PS-09 และ configuration ([DD] §7) เนื้อหาปัจจุบันอยู่ใน [PS-Config.json](PS-Config.json)
- **Used By:** `ConfigurationRepository` ทุก request
- **Read/Write:** Read (Mornitor ไม่แก้ configuration)

| Field | ชนิด | การใช้งาน |
|---|---|---|
| `psCode` | String | เรียงผลและค้นในหน้ารายละเอียด (`find({psCode})` ใช้เอกสารแรก) |
| `requirement` | String | ส่งใน API ตามที่เก็บไว้ |
| `config` | Object | ตีความโดย engine ตาม construct ใน [ARCHITECTURE.md](ARCHITECTURE.md) §5 |
| `active` | Boolean | ใช้เฉพาะเอกสารที่เป็น `true` จริง |
| `_id` | ObjectId | ไม่ถูกอ่าน |
| `timestamp` | Date ([DD]) | ไม่ถูกอ่าน |
| `config.minCount`, `config.role` ([DD]) | — | ไม่มีใน config ACTIVE และ engine ไม่รู้จัก config ACTIVE ใช้โครงสร้างอื่นที่ละเอียดกว่า |

**เอกสาร Generation Readiness** (เจ้าของ project กำหนด 2026-09-26): เอกสารชนิดที่สองใน collection เดิม ไม่มี collection ใหม่ เนื้อหาปัจจุบันอยู่ใน `backend/tests/fixtures/generation_readiness_v1.json` (ที่มาอยู่ใน `backend/tests/fixtures/PROVENANCE.md`)

| Field | ชนิด | การใช้งาน |
|---|---|---|
| `configType` | String | ต้องเป็น `"generationReadiness"` ใช้แยกชนิดเอกสาร เอกสารที่มี field นี้จะไม่ถูกโหลดเป็น PS (`ConfigurationRepository`) |
| `generationReadiness.requiredPS` | Array[String] | PS ที่ต้องตรวจ ต้องไม่ว่าง · ทุกตัวต้องมี PS configuration ที่ active และมีผลประเมิน มิฉะนั้นไม่ READY (ไม่มี configuration → `configuration_error`; ไม่มีผล → ปัญหาข้อมูลใน `detail`) |
| `generationReadiness.readyWhen.allowedStatus` | Array[String] | สถานะที่ไม่ block (ค่าใน Status) |
| `generationReadiness.readyWhen.blockedStatus` | Array[String] | สถานะที่ block (ค่าใน Status) ห้ามซ้ำกับ `allowedStatus` · ไม่บังคับให้สองรายการครอบคลุมทุก Status |
| `generationReadiness.requiredAll` | Boolean | ต้องเป็น boolean · กติกาที่กำหนดแล้วมีเฉพาะ `true` · `false` ยังไม่มีกติกา ระบบไม่ตัดสิน (รอเจ้าของ project ตัดสินใจ) |
| key อื่น | — | ไม่ถูกอ่าน (ยังไม่มีข้อกำหนด) |
| `psCode`, `active` | — | ไม่มี (ไม่ใช่ Programme Standard) |

ต้องมีเอกสารนี้ **1 เอกสาร** ถ้าไม่มีหรือมีมากกว่า 1 เอกสาร `generationReadiness.status` เป็น `null` + `configuration_error` ([API.md](API.md) §5) ณ วันที่จัดทำ `ps_requirements` จริงยังไม่มีเอกสารนี้ เจ้าของ configuration ต้องนำเข้าเอง

### 4.7 Collection ที่ประกาศแต่ config ACTIVE ไม่อ่าน

| Collection | Field ที่ประกาศใน `SOURCE_SCHEMA` | หมายเหตุ |
|---|---|---|
| `documents` | `_id`, `documentType`, `fileType`, `fileName`, `curriculumId`, `originalFile(.storage/.path)`, `convertedFile(.storage/.path)`, `extractedText(.storage/.path)`, `status`, `timestamp` | configuration ไม่อ่าน แต่ Evidence อ่าน `_id`, `fileName`, `curriculumId` (ขอบเขต), `originalFile.storage`, `originalFile.path` (ดู §4.8) · ไม่อ่าน `convertedFile`, `extractedText`, `documentType`, `fileType`, `status` · frontend มีป้ายไทยของ `documentType` และ `fileName` ไว้แสดงผลเท่านั้น |
| `data_usages` | `_id`, `dataType`, `dataId`, `curriculumId`, `psCodes` (Array), `roles` (Array), `templateFields` (Array), `timestamp` | engine อ่านค่าใน Array ไม่ได้ (SPEC GAP) · ใช้ใน `test_generic_capabilities.py` เพื่อยืนยันว่า engine ไม่ผูกกับ PS |
| `generated_documents` | `_id`, `curriculumId`, `fileName`, `fileType`, `generatedFiles` (Array[Object]), `generatedFiles.path`, `generatedFiles.timestamp`, `timestamp` | เก็บเอกสาร PS ที่ระบบอื่นสร้าง ([DD] §9) · ระบบที่สร้าง: ข้อมูลไม่เพียงพอ |

### 4.8 `documents` สำหรับ Evidence

- **Relationship:** `documents.curriculumId → curricula._id` ([DD] §6) เท่านั้น ไม่มี field ที่เชื่อมเอกสารกับ PS รายตัว (`data_usages` มีตัวอย่าง `dataType` แค่ `education`, `academicWork`) จึงให้เอกสารของหลักสูตรเป็น evidence ของทุก PS (เจ้าของ project ตัดสินใจ 2026-09-26; [Datacat] Source Document → PS-01–PS-09)
- **Read/Write:** Read (`find` เท่านั้น) ไม่เปิดหรืออ่านไฟล์ตาม path และไม่ทำ Document Extraction ([SRS-M] §39)
- **ข้อมูลทดสอบ:** `backend/scripts/seed_test_data.py` เพิ่ม 4 เอกสาร (`_id` `7e57da7a07…`) ของ `TEST-IS-001` (ครบ / ไม่มี `originalFile` / ไม่มี `path`) และ `TEST-IS-002`

### 4.9 `monitoring_results` (ผลของ Monitor)

- **Purpose:** สิ่งที่ Monitor เก็บไว้ต่อ PS หนึ่งในหลักสูตรหนึ่ง (เจ้าของ project 2026-09-26): การยืนยัน, ผลที่ผู้ตรวจเลือก และสถานะที่บันทึกไว้ครั้งล่าสุด ไม่ใช่ข้อมูลต้นทางและไม่ใช่ configuration
- **Used By:** `MonitoringResultRepository` (`backend/app/repositories/monitoring_results.py`) ผ่าน `MongoMonitoringResultAdapter` (`backend/app/adapters/monitoring_results.py`) · engine ไม่อ่านและไม่เขียน
- **Read/Write:** Read + Write (Monitor-owned) · ไม่มี delete

| Field | ชนิด | การใช้งาน |
|---|---|---|
| `_id` | ObjectId | สร้างโดย MongoDB ไม่ถูกอ่าน |
| `curriculumId` | ObjectId | `curricula._id` ของหลักสูตรที่ตรวจ · ส่วนหนึ่งของ key |
| `psCode` | String | รหัส PS · ส่วนหนึ่งของ key |
| `verification.verified` | Boolean | `true` เมื่อผู้ใช้ยืนยันหลักฐาน / ผลการตรวจ (SET 4) |
| `verification.verifiedAt` | Date | เวลาของ server ตอนยืนยันครั้งแรก (ยืนยันซ้ำไม่เปลี่ยน) |
| `review.status` | String | ผลที่ผู้ตรวจเลือก (SET 5) ต้องอยู่ใน `config.review.allowManualResult` ของ PS นั้น และ PS นั้นต้องมี `review.required: true`, `review.reviewByUser: true` (config ACTIVE: PS-03 เท่านั้น) |
| `review.reviewedAt` | Date | เวลาของ server ตอนบันทึกล่าสุด (ไม่รับเวลาจาก client) |
| `result.status` | String | Persistent Monitoring Result (SET 6): `status` ที่ engine ให้ PS นี้ตอนผู้ใช้กดบันทึกผล (PS-03 = REVIEW ของ engine ไม่ใช่ `review.status`) |
| `result.evaluatedAt` | Date | เวลาของ server ตอนบันทึก (ทุก PS ในการบันทึกครั้งเดียวกันมีค่าเดียวกัน) |

- **Key:** `curriculumId + psCode` ไม่ซ้ำ (unique index `curriculumId_psCode` สร้างโดย adapter ก่อนเขียน) · บันทึกซ้ำแก้เอกสารเดิม · `verification`, `review`, `result` เขียนด้วย `$set` คนละ sub-document จึงไม่ลบกัน
- **`result` เป็น current state:** บันทึกใหม่แทนค่าเดิม ไม่มีประวัติ · เมื่อข้อมูลต้นทางเปลี่ยน ค่าที่เก็บไว้คงเดิมจนกว่าจะบันทึกใหม่ (ไม่มี invalidation) · PS ที่ไม่ active ตอนบันทึกไม่ถูกเขียน
- **ไม่มี:** `verifiedBy` / `reviewedBy` (ยังไม่มี authentication), `approved`, ประวัติการแก้ไข, ส่วนอื่นของ PSResult, readiness, evidence, traceability (เจ้าของ project เลือกเก็บขั้นต่ำ 2026-09-26)
- **ผลต่อการตรวจ:** ไม่มี — engine ไม่อ่าน collection นี้ `status` ของ PS ยังมาจาก engine (`review.status` / `result.status` ไม่ถูกส่งเข้า `ManualResultSource`) และ Programme / Generation Readiness ไม่อ่าน collection นี้ (เจ้าของ project 2026-09-26)
- **ข้อมูลทดสอบ:** `seed_test_data.py` ไม่เขียนและไม่ตรวจ collection นี้ (ถ้ามีอยู่ใน test database จากการทดสอบ ไม่ทำให้ script หยุด)

## 5. ความสัมพันธ์

```text
                              curricula (_id, curriculumCode)
             ┌──────────────────────┼──────────────────────┬───────────────────────┐
             │ curriculumId         │ curriculumId         │ curriculumId          │ curriculumId
             ▼                      ▼                      ▼                       ▼
        appointments            documents              data_usages          generated_documents
             │ personId
             ▼
          persons (_id) ◄──── personId ──── educations
                        ◄──── personId ──── academic_works

monitoring_results (curriculumId → curricula._id, psCode)  — ผลของ Monitor อาจอยู่คนละ database; psCode ตรงกับ ps_requirements.psCode

ps_requirements (psCode, requirement, config, active)  — configuration อาจอยู่คนละ database
                + 1 เอกสาร {configType: "generationReadiness", generationReadiness}
```

ใน code ความสัมพันธ์เหล่านี้กำหนดไว้ใน `backend/app/models/source_schema.py`:

| ค่าคงที่ | ความหมาย |
|---|---|
| `CURRICULUM_LINK` | field ที่ใช้จำกัด record ให้อยู่ในหลักสูตรที่ตรวจ: `curricula._id`, `appointments.curriculumId`, `documents.curriculumId`, `data_usages.curriculumId`, `generated_documents.curriculumId` |
| `REFERENCES` | `personId` → `persons._id`, `curriculumId` → `curricula._id` |
| `DISPLAY_FIELD` | `persons.fullName`, `curricula.curriculumCode` (ใช้แสดงผลเท่านั้น) |

collection ที่ไม่มีใน `CURRICULUM_LINK` (`persons`, `educations`, `academic_works`) อ่านได้เฉพาะผ่าน join หรือ reference จาก `appointments` เท่านั้น

## 6. รูปแบบข้อมูลที่ engine คาดหวัง

- **ปี** เป็นจำนวนเต็มแบบ พ.ศ. (เช่น `curriculumYear: 2567`) ตามตัวอย่างใน [DS] ถ้าข้อมูลเป็น ค.ศ. ต้องตั้ง `MORNITOR_YEAR_OFFSET=0`
- **ค่าว่าง** คือ `null`, ข้อความว่าง หรือมีแต่ช่องว่าง, list หรือ object ว่าง ถือว่าไม่มีข้อมูล (`helpers.is_blank`)
- **key ที่เป็น list หรือ object** ใช้จับคู่ไม่ได้
- **field ซ้อน** ใช้ชื่อแบบจุด (`appointmentOrder.orderDate`) แต่ค่าภายใน Array อ่านไม่ได้
- **ค่าที่ต้องตรงตัวอักษร:**
  - `role` (เช่น `programmeResponsible`)
  - `degree` ของ PS-05 (`bachelor`, `master`, `Ph.D.`)
  - `hasTeachingExperience` ต้องเป็น Boolean

## 7. ความต่างระหว่าง Schema ใน code กับเอกสารข้อมูล

| หัวข้อ | [DD] / [DS] | Code / config ACTIVE |
|---|---|---|
| `persons.hasTeachingExperience` | ไม่มี | ประกาศใน `SOURCE_SCHEMA` ตาม [IMP] §15 และ PS-08 ใช้ |
| `ps_requirements.config` | มีแค่ `minCount`, `role` | config จริงใช้โครงสร้างที่ละเอียดกว่า (ดู [PS-Config.json](PS-Config.json)) |
| ตัวอย่าง `educations.degree` | `"Ph.D."` | PS-05 รู้จักเฉพาะ `bachelor`, `master`, `Ph.D.` แบบตรงตัวอักษร |
| `timestamp` | ทุก collection | ประกาศไว้แต่ไม่ถูกอ่าน |
| `appointments.status` | ตัวอย่าง `active` | ไม่ถูกใช้กรอง |

## 8. ข้อมูลทดสอบ (ไม่ใช่ข้อมูลจริง)

- **`backend/scripts/seed_test_data.py`** สร้างชุดข้อมูลทดสอบถาวร
  - หลักสูตร `TEST-…` และบุคคล P001–P008
  - `_id` ขึ้นต้นด้วย `7e57da7a`
  - เขียนได้เฉพาะ database ที่ชื่อลงท้าย `_test` และตรวจทุก field กับ `SOURCE_SCHEMA` ก่อนเขียน
  - `ps_requirements` = PS 9 เอกสาร + เอกสาร Generation Readiness 1 เอกสาร (`_id` `7e57da7a0600000000000010`) ตรวจด้วยกติกาเดียวกับ backend ก่อนเขียน และหยุดถ้ามีเอกสาร `configType` เดียวกันที่ `_id` อื่น
- **`backend/tests/support/fixtures.py`** สร้างข้อมูลในหน่วยความจำสำหรับ unit test
- **`frontend/src/test/fixtures/backend-sample.json`** เป็นภาพถ่าย response ของ API สำหรับ test ของ frontend

ข้อมูลทั้งสามชุดนี้ใช้ทดสอบเท่านั้น ไม่ใช่ข้อมูลของหลักสูตรจริง
