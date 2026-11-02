# Changelog

## Unreleased (ยังไม่ commit และยังไม่กำหนดเลขเวอร์ชัน)

บันทึกจาก `git diff` และ test เมื่อ 2026-09-26 · `backend/app/main.py` และ `frontend/package.json` ยังเป็น `0.4.0` · รายละเอียดพฤติกรรมปัจจุบันอยู่ใน `docs/source-of-truth/`

### Backend / Rule Engine

1. **สถานะเมื่อตัดสินไม่ได้** ใช้ `result.review` ถ้าไม่มีจึงใช้ `result.unknown` ทุกจุด (`engine.py` `_undecided`)
   - PS-06 ไม่ขึ้น Configuration Error อีกเมื่อไม่มีอาจารย์ผู้รับผิดชอบ หรือมี record ไม่มี `personId`
2. **PS-05 ใช้ลำดับปริญญาจาก config**
   - รองรับ construct `{field, minimum, ordering}`
   - config ACTIVE กำหนด `degree.ordering: [bachelor, master, Ph.D.]`
3. **PS-08 ตัดสินอัตโนมัติ** (business rule ของเจ้าของ project 2026-09-25)
   - รองรับ construct `{source, required, condition}`
   - config ACTIVE: `experience.source: persons.hasTeachingExperience`
   - `qualification.condition: {operator: EXISTS}`, `experience.condition: {operator: "==", value: true}`
   - ไม่ใช้ `join.experiencePersonId` เพราะ `persons` ไม่มี field `personId` (บันทึกใน `backend/tests/fixtures/PROVENANCE.md`)
4. **`backend/scripts/seed_test_data.py`** สร้างข้อมูลทดสอบถาวร เขียนได้เฉพาะ database ที่ชื่อลงท้าย `_test`
5. **Test:** backend 613 → 657 passed
6. **Generation Readiness** (ชุดที่ 1, เจ้าของ project 2026-09-26)
   - configuration เป็นเอกสาร `{configType: "generationReadiness", generationReadiness}` ใน `ps_requirements` เดิม (ไม่มี collection ใหม่ ไม่มี `psCode`)
   - `ConfigurationRepository` ไม่โหลดเอกสารที่มี `configType` เป็น PS และมี `load_by_type`; `MongoConfigurationAdapter.read_by_type`
   - `services/generation_readiness.py` ตรวจเอกสารและตัดสิน `READY` / `NOT_READY` + `blockingPS`; ไม่มี / ซ้ำ / ผิดรูปแบบ → `status: null` + `issue`
   - PS ใน `requiredPS` ที่ไม่มี configuration ที่ active → `NOT_READY` + `configuration_error`; ไม่มีผลประเมิน → `NOT_READY` + `detail` (เจ้าของ project ยืนยัน 2026-09-26)
   - ไม่มีกติกาเพิ่มเองสำหรับ `requiredAll: false`, สถานะที่ไม่อยู่ในทั้งสองรายการ หรือ key อื่น: ระบบไม่ตัดสินและรอการตัดสินใจ
   - `GET /api/monitor` มี field ใหม่ `generationReadiness` (field เดิมไม่เปลี่ยน; endpoint รายละเอียด PS ไม่เปลี่ยน)
   - fixture `backend/tests/fixtures/generation_readiness_v1.json`; seed script เพิ่มเอกสารนี้และหยุดเมื่อพบเอกสารซ้ำ
   - **Test:** backend 657 → 722 passed (parity กับ `mongod` 11 → 14)
7. **Programme Readiness** (ชุดที่ 2, เจ้าของ project 2026-09-26)
   - `GET /api/monitor` มี field ใหม่ `programmeReadiness: {percentage, passCount, totalPS}` = จำนวน PS ที่เป็น PASS ÷ 9 × 100 (ทศนิยม 2 ตำแหน่ง)
   - นับเฉพาะ PASS; FAIL, REVIEW, N/A และ PS ที่ไม่มีผลไม่นับ; ตัวหาร 9 เสมอ; ไม่มีหลักสูตร → `null`
   - คำนวณเป็น computed field ใน `models/schemas.py` (`ProgrammeReadiness`); `overallStatus` ยังเป็น `null`; Generation Readiness ไม่เปลี่ยน
   - **Test:** backend 722 → 756 passed
8. **Evidence** (ชุดที่ 3, เจ้าของ project 2026-09-26)
   - `services/evidence.py` อ่าน `documents` ของหลักสูตร (`curriculumId`) แบบอ่านอย่างเดียว; `evidence` ของทุก PS = `{label: fileName, reference: _id, storage, path}` จาก `originalFile` (ค่าที่ไม่มีเป็น `null`)
   - `EvidenceItem` เพิ่ม `storage`, `path` (field เดิมไม่เปลี่ยน); ใช้ได้ทั้ง `GET /api/monitor` และ `GET /api/monitor/ps/{psCode}`
   - ไม่ใช่ traceability, ไม่เปลี่ยนสถานะ / Programme Readiness / Generation Readiness; ยังไม่มี Verification
   - seed script เพิ่มเอกสารทดสอบ 4 รายการ
   - **Test:** backend 756 → 785 passed (parity กับ `mongod` 14 → 16)
9. **Verification** (ชุดที่ 4, เจ้าของ project 2026-09-26)
   - `POST /api/monitor/ps/{psCode}/verification` บันทึกการยืนยัน (หลักฐาน + ผล PS) ใน collection ของ Monitor `monitoring_results`: `{curriculumId, psCode, verification: {verified: true, verifiedAt}}`, unique `curriculumId + psCode`, กดซ้ำไม่สร้างรายการใหม่
   - `GET` เดิมส่ง `verification.verified` (`true` / `false`; ไม่มี store → `null`) และ `verification.verifiedAt`; `approved` คง `null`
   - ไม่เปลี่ยนสถานะ PS, evidence, traceability, Programme / Generation Readiness, PS-03
   - `adapters/monitoring_results.py` เป็นที่เดียวที่เขียน database; source / configuration ยัง `find` เท่านั้น; ตัวแปร `MORNITOR_RESULTS_DB_URI` / `MORNITOR_RESULTS_DB_NAME`; CORS `GET`, `POST`
   - architecture test เปลี่ยนจาก "ห้ามเขียนทั้ง backend" เป็น "เขียนได้เฉพาะ Monitor-owned adapter ลง `monitoring_results`" และ "route ที่ไม่ใช่ GET มีเฉพาะการยืนยัน" (เจ้าของ project สั่ง)
   - seed script ไม่หยุดเมื่อ test database มี `monitoring_results`
   - **Test:** backend 785 → 801 passed (parity กับ `mongod` 16 → 17)
10. **PS-03 User Review + การเก็บผล** (ชุดที่ 5, เจ้าของ project 2026-09-26)
   - `POST /api/monitor/ps/{psCode}/review` body `{status}` บันทึกผลที่ผู้ตรวจเลือกใน `monitoring_results` เอกสารเดียวกับ verification (`review: {status, reviewedAt}` เวลาของ server; บันทึกซ้ำแก้เอกสารเดิม; ไม่ลบ `verification` และ verification ไม่ลบ `review`)
   - PS ที่รับ review และค่าที่เลือกได้มาจาก `config.review` (`required`, `reviewByUser`, `allowManualResult`) ไม่มีรหัส PS ใน code (config ACTIVE: PS-03) · ค่าไม่อยู่ในตัวเลือก → `422`; PS อื่น → `400`
   - `PSResult.review = {allowManualResult, status, reviewedAt}` (PS อื่น `null`)
   - **ไม่ override:** `status` ของ PS-03 ยังเป็น REVIEW ของ engine, ไม่ส่งเข้า `ManualResultSource`, Programme / Generation Readiness ไม่เปลี่ยน (เจ้าของ project ตัดสินใจ)
   - architecture test: route ที่ไม่ใช่ GET = verification + review; adapter ของ Monitor มี `set_review` (ยังไม่มี delete / replace)
   - `Data-Schema.md` เพิ่ม `monitoring_results` และแก้ข้อความ "อ่านอย่างเดียว" ให้แยก source / config (อ่านอย่างเดียว) กับ Monitor-owned (เขียนได้)
   - **Test:** backend 801 → 844 passed (parity กับ `mongod` 17 → 18)
11. **Persistent Monitoring Result** (ชุดที่ 6, เจ้าของ project 2026-09-26: current state / POST แยก / เก็บขั้นต่ำ / คงค่าเดิมเมื่อข้อมูลเปลี่ยน)
   - `POST /api/monitor/results` ประเมินด้วย engine แล้วเก็บ `result: {status, evaluatedAt}` ในเอกสาร `curriculumId + psCode` ของทุก PS ที่ active (bulk write; ไม่ลบ `verification` / `review`)
   - `PSResult.persistedResult = {status, evaluatedAt}` อ่านจาก `monitoring_results`; GET ไม่เขียน; engine และ readiness ไม่อ่านค่าที่บันทึก
   - architecture test: route ที่ไม่ใช่ GET เพิ่ม `/api/monitor/results`; adapter ของ Monitor ใช้ได้เฉพาะ `update_one` / `bulk_write` (UpdateOne upsert) / `create_index`
   - **Test:** backend 844 → 867 passed (parity กับ `mongod` 18 → 19)
12. **Document Generation contract (pull, readiness-only)** (ชุดที่ 7, เจ้าของ project 2026-09-26)
   - Generator เรียก `GET /api/monitor?curriculumCode=…` เดิม แล้วอ่านเฉพาะ `generationReadiness.status` (SET 1) · ไม่มี endpoint ใหม่ ไม่มี push / webhook / outbound call ไม่ส่งข้อมูลหลักสูตรให้ Generator
   - `adapters/external_services.py` แก้เฉพาะ docstring (บันทึกว่า Document Generation ใช้ pull) ไม่มี code ใหม่
   - `tests/test_generator_contract.py` ล็อก contract: READY / NOT_READY / null ผ่าน HTTP, ค่าเท่ากับ implementation ของ SET 1, มาจากผลปัจจุบันไม่ใช่ `persistedResult`, แยกตามหลักสูตร, 409 / 503, GET ไม่มี side effect, ไม่มี HTTP client ขาออกใน app
   - **Test:** backend 867 → 888 passed
13. **Error Logging** (ชุดที่ 8, เจ้าของ project: Error เท่านั้น)
   - `app/error_log.py`: `configure_logging()` (handler เดียวบน logger `app`, stderr, `<เวลา> <LEVEL> <module> [<category>] <message>`, ซ่อน user:password ใน URL) และหมวด configuration / data source / connection / evaluation / system error
   - routes log ERROR ทุก `503` (`connection_error` เมื่อ pymongo `ConnectionFailure` → `DataSourceConnectionError`, นอกนั้น `data_source_error`) ครอบคลุมการอ่านและการเขียน `monitoring_results`
   - `main.py` middleware: exception ที่ไม่มี route จัดการ → log ERROR `system_error` + ตอบ `500` "Internal Server Error" เหมือนเดิม
   - engine: log `evaluation_error` เดิมเพิ่ม category · service: WARNING `configuration_error` เมื่อ config ของ PS หรือ Generation Readiness ใช้ไม่ได้
   - ไม่มีการเปลี่ยน HTTP status หรือ response, ไม่ log ผลการตรวจ / request ปกติ / 4xx, ไม่มี log collection, ไม่ส่งออกภายนอก, ไม่มี dependency ใหม่
   - **Test:** backend 888 → 908 passed

### Frontend

1. **ลบโหมด mock** (`frontend/mock/`, สคริปต์ `dev:mock*` และส่วนโหลด mock ใน `vite.config.js`)
2. **อ่านผลใหม่อัตโนมัติ** ทุก 10 วินาที (`RETRY_MS`)
   - แสดงเวลาตรวจสอบล่าสุด
   - API `409` แสดง "พบหลายหลักสูตรในฐานข้อมูล"
3. **การ์ด PS-01…PS-09 ครบเสมอ** (`cardList.js`, `GuideCard`)
   - `psGuideline.js` มีแค่ PS code
   - ข้อความ requirement สำรองที่ล็อกไว้อยู่ใน `psTitles.js` (เจ้าของ project ตัดสินใจ 2026-09-25) ใช้เมื่อ API ไม่ส่ง requirement
4. **แถบบน** มีลิงก์ AUN-QA และลิงก์ PS-01…PS-09 เมื่ออยู่ในส่วน PS (0.4.0 มี AUNQA และแท็บ "หน้าแรก")
5. **หน้ารายละเอียด 11 ส่วน** (เพิ่ม "ทำไมจึงได้ผลนี้", "เกณฑ์นี้ตรวจสอบอะไร", "เงื่อนไขที่ใช้ตัดสิน")
   - แหล่งที่มาของข้อมูลเป็นตาราง
6. **Missing Information เป็นภาษาไทย** เฉพาะข้อความที่มีแม่แบบ (`missingText.js`) ที่เหลือแสดง "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด"
7. **Test:** frontend 124 → 230 passed
8. **ความพร้อมของหลักสูตร** (ชุดที่ 2) แสดง `programmeReadiness.percentage` + "%" และ "PASS <passCount> จาก <totalPS> เกณฑ์" จาก API (adapter ส่งต่อค่าเดิม ไม่คำนวณ; ไม่มีค่า → "—")
   - **Test:** frontend 230 → 302 passed
9. **หลักฐานที่ใช้ประกอบการตรวจสอบ** (ชุดที่ 3) แสดงชื่อไฟล์ — รหัสอ้างอิง, ที่เก็บไฟล์ต้นฉบับ และตำแหน่งไฟล์ต้นฉบับ จาก API (`null` → "ไม่พบข้อมูล storage / path")
   - "พบหลักฐาน" บนหน้าภาพรวมนับเอกสารไม่ซ้ำตาม `reference`
   - **Test:** frontend 302 → 307 passed
10. **การยืนยันข้อมูล** (ชุดที่ 4) ปุ่ม "ยืนยันหลักฐาน / ผลการตรวจ" ในหน้ารายละเอียด PS ส่ง `POST` แล้วอ่านสถานะด้วย `GET` (`useRemote.reload`) แสดง "ใช่" และ "ยืนยันเมื่อ" จาก backend เท่านั้น; ผิดพลาดแสดงข้อความและไม่แสดงว่ายืนยันแล้ว; กดซ้ำระหว่างบันทึกส่งครั้งเดียว
   - `api/client.js` มี `postJson` ที่ใช้ได้เฉพาะ `verifyPS`
   - **Test:** frontend 307 → 316 passed
11. **ผลการตรวจของผู้ตรวจ (User Review)** (ชุดที่ 5) ส่วนใหม่ในหน้ารายละเอียดของ PS ที่ API ส่ง `review` (PS-03): ตัวเลือกจาก `review.allowManualResult`, ปุ่ม "บันทึกผลการตรวจ" → `POST` → อ่านซ้ำด้วย `GET`; ผลที่บันทึกแสดงจาก backend เท่านั้น; ผิดพลาดแสดงข้อความและผลเดิมคงอยู่; กดซ้ำระหว่างบันทึกส่งครั้งเดียว; สถานะของเกณฑ์ยังแสดงค่าจาก engine
   - `api/client.js` `postJson(url, body)` ใช้ได้เฉพาะ `verifyPS` / `reviewPS`
   - **Test:** frontend 316 → 327 passed
12. **ผลการตรวจที่บันทึกไว้** (ชุดที่ 6) ส่วนใหม่ท้ายหน้าภาพรวม: ตาราง PS / ผลที่บันทึก / บันทึกเมื่อ จาก `persistedResult` และปุ่ม "บันทึกผลการตรวจของหลักสูตร" → `POST` → อ่านซ้ำด้วย `GET` (หน้าภาพรวมมีปุ่มเดียวนี้ ไม่มีช่องแก้ข้อมูล)
   - **Test:** frontend 327 → 339 passed

### PS-05 รูปแบบวุฒิ และ PS-07 ปี ค.ศ. / พ.ศ. (เจ้าของ project 2026-09-27, จากข้อมูลจริง `aunqa_ps`)

1. **PS-05: เทียบวุฒิหลัง normalization และ alias จาก config**
   - `AtLeastCheck` รับ `aliases` / `normalization` ใช้ `mapping.normalize` เดียวกับ PS-06 โดยไม่แก้ PS-06
   - ตำแหน่งในลำดับหาได้จากค่าใน `ordering` หรือ alias ของมันหลัง normalize
   - interpreter รับ `{field, minimum, ordering, aliases?, normalization?}` และตรวจ alias ที่ไม่อยู่ใน ordering, รูปเขียนที่ชี้ได้ 2 ค่า และรูปเขียนที่ว่าง → `configuration_error`
   - กติกาตัดสินเดิมไม่เปลี่ยน: มีวุฒิ ≥ minimum → PASS; ค่าที่ไม่รู้จักกัน FAIL → REVIEW
2. **config ACTIVE (`ps_config_v1.json`) PS-05 `degree`:** เพิ่ม `aliases: {bachelor: [วท.บ., บธ.บ.], master: [วท.ม.], Ph.D.: [ปร.ด.]}` และ `normalization: {enabled: true, remove: [" ", "."], caseInsensitive: true}`
   - `ordering` และ `minimum` เดิม
   - บันทึกใน `PROVENANCE.md` และ `docs/source-of-truth/PS-Config.json`
   - **`ps_requirements` ของ database จริงต้องเพิ่มเอง** เพราะ Mornitor ไม่เขียน configuration
3. **PS-07: ปีของช่วงเวลา**
   - รับจำนวนเต็มหรือข้อความตัวเลขล้วน (`helpers.whole_number`)
   - แปลงเป็นปฏิทินของ `currentYear` ด้วย `ReferenceSource.in_anchor_calendar`: `RuntimeReferences` บวก `MORNITOR_YEAR_OFFSET` ให้ปีที่ไม่เกินปี ค.ศ. ปัจจุบัน (2022–2026 → 2565–2569)
   - ปีอื่นคงเดิม ไม่มีตัวเลขปีใน engine
   - ค่าที่ไม่ใช่ปี (`null`, ข้อความอื่น, ทศนิยม, boolean) ยังเป็นปีที่ใช้ไม่ได้
   - `FixedReferences` ของ test ไม่แปลง (ค่าคงที่ไม่มีปฏิทิน)
4. **ข้อมูลจริง `aunqa_ps` (อ่านอย่างเดียว):**
   - PS-05 PASS 5/5 คน เมื่อใช้ config ACTIVE
   - PS-07 PASS 13/13 คน
   - Rule Engine = API = DB oracle
   - PS อื่นให้ผลเหมือนเดิมทุก field
   - ระบบที่รันอยู่ (อ่าน config จาก database): PS-07 PASS, PS-05 ยัง REVIEW จนกว่า config ใน database จะมี aliases → Programme Readiness 44.44% → 55.56% (66.67% เมื่อ config ใน database ถูกอัปเดต)
   - **Test ใหม่:** `tests/test_degree_and_year_forms.py` 99 รายการ
   - **Test ที่ปรับ setup (ค่าที่คาดหวังเดิม):** `test_ps05_degree_is_compared_by_the_configured_ordering` ถอด `aliases` / `normalization` ออกก่อน เพื่อยังตรวจการเทียบตรงตัวเมื่อ config ไม่มี normalization; `test_ps05_without_an_ordering_…` ลบ `aliases` / `normalization` พร้อม `ordering`
   - **Test support:** `FixedReferences.in_anchor_calendar` คืนปีเดิม
   - backend 920 → 1019 passed
5. **PS-05 รอบที่ 2 (เจ้าของ project 2026-09-27)**
   - config ACTIVE เพิ่ม `วบ.บ.` ใน `aliases.bachelor`
   - ข้อความผลใน `dataFound` บอกทุกค่าที่อ่าน และค่าในลำดับที่มันแทน (`ปร.ด. → Ph.D.; วท.บ. → bachelor`, `at → not in the ordering`) ก่อน `(highest … is at least / below …)`
   - รูปแบบ API ไม่เปลี่ยน และหน้าเว็บไม่แสดงข้อความนี้ (แสดงแค่ชื่อ)
   - ข้อมูลจริง: อาจารย์ผู้รับผิดชอบ 5/5 คน PASS (Rule Engine = API = DB oracle เมื่อใช้ config ACTIVE)
   - `ps_requirements` ของ `aunqa_ps` ยังไม่มี `aliases` / `normalization` ระบบที่รันอยู่จึงยังเป็น REVIEW จนกว่าเจ้าของ config จะนำเข้า
   - **Test:** เพิ่ม 14 รายการใน `test_degree_and_year_forms.py`
     - รูปแบบวุฒิของผู้รับผิดชอบจริงทั้ง 5 แบบ, `วบ.บ.`, ข้อความของ FAIL
     - ตรวจเฉพาะ programmeResponsible และ role มาจาก config
     - integration กับข้อมูลจริงใน `DB-DATA/` (ข้ามเมื่อไม่มีโฟลเดอร์นี้)
   - แก้ test ข้อความผลของรอบก่อนให้ตรงรูปแบบใหม่
   - backend 1019 → 1033 passed

### Docker / การเชื่อมต่อ MongoDB บนเครื่อง (เจ้าของ project 2026-09-26)

1. **`compose.yaml`** รวม 2 container: `backend` (FastAPI) และ `frontend` (nginx) ไม่มี MongoDB เพราะ Mornitor ต่อกับ database ของ Import Service
   - ค่าเริ่มต้น `MORNITOR_DB_URI=mongodb://host.docker.internal:27017` (MongoDB บนเครื่องเดียวกัน) และ `extra_hosts: host.docker.internal:host-gateway` สำหรับ Linux
   - ตั้งค่าใน `.env` (คัดลอกจาก `.env.example` ใหม่) ตัวแปรที่ไม่บังคับส่งเข้า container เฉพาะเมื่อมีใน `.env` เพื่อไม่ส่งค่าว่างไปแทนค่า fallback ของ `Settings.from_env`
   - พอร์ตเปิดเฉพาะ `127.0.0.1` (หน้าเว็บ `8080`, API `8000`; เปลี่ยนด้วย `MORNITOR_WEB_PORT` / `MORNITOR_API_PORT`) เพราะ API ยังไม่มี authentication
2. **`backend/Dockerfile`** `python:3.11-slim` ติดตั้งเฉพาะ `requirements.txt` โดยล็อกเวอร์ชันด้วย `requirements-dev.lock.txt` รันด้วย user `mornitor` (uid 10001) ไม่มีค่า database อยู่ใน image
3. **`frontend/Dockerfile` + `frontend/nginx.conf`** build ด้วย `node:22-slim` แล้วเสิร์ฟด้วย `nginx:stable-alpine` · nginx ส่ง `/api/` ต่อให้ `backend:8000` (origin เดียวกัน ไม่ต้องใช้ CORS) และส่ง `index.html` ให้ route ฝั่ง client
4. **`.gitignore`** ไม่ commit `.env` (ยกเว้น `.env.example`) · `.dockerignore` ทั้งสองฝั่งไม่คัดลอก `.env`, `.venv`, `node_modules`
5. ไม่แก้ code ของแอป, API และ Data Schema
   - **Test:** `tests/test_docker.py` 12 รายการ (ค่าใน `.env.example` ตรงกับตัวแปรที่ `Settings` อ่าน, ไม่มีรหัสผ่านในไฟล์, `.env` ไม่ถูก commit หรือคัดลอกเข้า image, ค่าเริ่มต้นชี้ `host.docker.internal`, ไม่ส่งตัวแปรว่าง, พอร์ตเฉพาะ `127.0.0.1`, พอร์ตของ uvicorn / compose / nginx ตรงกัน, image ไม่ใช้ root, ทุก route อยู่ใต้ `/api/`) · backend 908 → 920 passed · `requirements-dev.txt` เพิ่ม `PyYAML>=6` (มีใน lock อยู่แล้ว)
   - **ตรวจด้วย Docker จริง** (Docker Desktop บน macOS): build ผ่าน · backend test ใน `python:3.11-slim` 901 passed, 19 ข้าม (ไม่มี `mongod` ใน container) · E2E ผ่าน database ทดสอบบนเครื่องทาง `host.docker.internal` ([docs/TESTING.md](docs/TESTING.md) §0.1)

### เอกสาร

- เพิ่ม `docs/source-of-truth/` (SRS, SCOPE, Data-Schema, API, ARCHITECTURE, PS-Config, DOCUMENTATION-SYNC, DEPENDENCY-AUDIT)
- ปรับ `README.md`, `docs/SPEC_GAPS.md`, `docs/TESTING.md` ให้ตรงกับ code

## 0.4.0 — 2026-09-23

**เปลี่ยนเฉพาะ frontend** backend และ API contract เหมือน 0.3.0 ทุกอย่าง (แก้แค่เลขเวอร์ชันใน `backend/app/main.py`)

### แก้ไข / เปลี่ยนแปลง

1. **หน้าแรก `/`** "เลือกส่วนที่ต้องการดู"
   - การ์ด P1 P2 P3 P4 P8 PS จาก `criteriaGroups.js`
   - ไม่เรียก API
2. **Routes ใหม่**
   - `/monitor` และ URL อื่น (รวม `/monitor/p5`–`p7`) redirect ไป `/` โดยคง query
   - `/monitor/p1` `p2` `p3` `p4` `p8` แจ้งว่า "ยังไม่มีข้อมูลสำหรับส่วนนี้"
3. **แถบบนสุด** มีแค่ **AUNQA** และ **หน้าแรก** (ลบแถบ P1–P8 / PS ของ 0.3.0)
4. **หน้าภาพรวมเกณฑ์ PS** เป็นภาษาไทยตามภาพตัวอย่าง
   - แถบ "ข้อมูลยังไม่ครบถ้วน", ข้อมูลหลักสูตร, ความพร้อมของหลักสูตร (ความพร้อม "—")
   - การ์ด 5 ส่วน, สถานะหลักฐาน, ข้อมูลที่ยังขาด, ความครบถ้วนของข้อมูล
   - ลบกล่อง DATA STATUS และความหมายของสถานะ
5. **"สิ่งที่ระบบตรวจพบ" บนการ์ด** สร้างจาก `verification.found` และ `traceability` เท่านั้น
   - ใช้ป้ายไทยจาก `sourceLabels.js` / `fieldLabels.js` (ใช้แสดงผลเท่านั้น)
   - ไม่แสดง ObjectId หรือ field ที่ไม่อยู่ในตาราง
6. **หน้ารายละเอียด** หัวข้อภาษาไทย 9 ส่วน (ลำดับและ `section-*` เดิม)
   - การตรวจย้อนกลับแสดงชื่อ collection / field ภาษาไทย
   - ลบบรรทัดอธิบายใต้หัวข้อของ 0.3.0 เพราะไม่มีในภาพตัวอย่าง
7. **ข้อความสถานะของหน้าเป็นภาษาไทย** กำลังโหลดข้อมูล… / ไม่สามารถโหลดข้อมูลได้ / ไม่มีข้อมูล / ข้อมูลยังไม่ครบถ้วน
8. **สไตล์ใหม่**
   - สีลิงก์ `#2563eb`, มุมโค้ง 12px, padding 24px (การ์ดหน้าแรก 32px), ระยะห่าง 24px
   - ป้าย Spec Gap สีเหลืองอำพัน และป้าย error สีแดงอ่อน
   - `<title>` = AUNQA
   - **โหมดสว่างอย่างเดียว** (ลบ dark mode ของ 0.3.0 ตามภาพตัวอย่าง)
9. **Mock** ใช้ชื่อ collection / field จริงของ Data Schema เพื่อให้เห็นป้ายไทย โดยค่าทุกค่ายังขึ้นต้นด้วย `[MOCK]`

### Test ที่ปรับ (พฤติกรรมเปลี่ยนโดยตั้งใจ)

| Test เดิม (0.3.0) | เปลี่ยนเป็น | เหตุผล |
|---|---|---|
| แถบเลือกกลุ่ม P1–P8 / PS (`navigation.test.jsx`) | แถบ AUNQA + หน้าแรก, `aria-current` เฉพาะหน้าแรก | ลบแถบเลือกกลุ่มออกตามภาพตัวอย่าง |
| `/monitor` และ URL อื่น redirect ไป `/monitor/ps` | redirect ไป `/` (รวม `/monitor/p5`–`p7`) | มีหน้าแรกแล้ว และ P5–P7 ไม่อยู่ในรายการ |
| หน้า P1–P8 ข้อความ "ยังไม่อยู่ในขอบเขตการพัฒนาปัจจุบัน" + ลิงก์ "ไปที่ PS →" | หน้า P1 P2 P3 P4 P8 ข้อความ "ยังไม่มีข้อมูลสำหรับส่วนนี้" + "← กลับหน้าแรก" | ข้อความใหม่ตาม prompt ข้อ 5 |
| หัวข้อ MONITOR, Programme Readiness, PS Overview, Evidence Status, Missing Information, Data Status | หัวข้อภาษาไทยใหม่ และตัวเลขตามกล่องใหม่ | หน้าภาพรวมเปลี่ยนตามภาพตัวอย่าง |
| Evidence Status "Found x / n" | "พบหลักฐาน" = ผลรวม evidence, "รอการตรวจสอบ" = verified false | นิยามใหม่ตาม prompt ข้อ 6.6 |
| DATA STATUS และความหมายของสถานะ | ความครบถ้วนของข้อมูล / ตรวจว่าไม่มีสองกล่องเดิม | ถูกลบออกตาม prompt |
| การ์ด 3 ชั้น (ไม่แสดง Operation, "ขาด N รายการ") | การ์ด 5 ส่วน, ข้อความผลการตรวจสอบภาษาไทย, "ยังขาดข้อมูล N รายการ", ลิงก์ "ดูรายละเอียด →" | โครงการ์ดใหม่ตาม prompt ข้อ 6.5 |
| Missing Information มีลิงก์ PS | ชื่อ PS ตัวเล็ก (ไม่เป็นลิงก์) + "ดูทั้งหมด →" | ตาม prompt ข้อ 6.6 |
| ข้อความ Loading data... / Unable to load monitoring data / No Data / Incomplete Data | ข้อความภาษาไทย | ตาม prompt ข้อ 9 |
| หน้ารายละเอียด: หัวข้อ h2 ภาษาอังกฤษ, บรรทัดอธิบายใต้หัวข้อ, "← MONITOR", "configuration ที่ใช้ตรวจ (N บรรทัด)" | หัวข้อภาษาไทย ไม่มีบรรทัดอธิบาย, "← ภาพรวมเกณฑ์ PS", "ดู configuration ที่ใช้ตรวจ" | ตาม prompt ข้อ 8 |
| Traceability `collection / recordId` และ `field = value` | `ชื่อไทย (collection) / recordId` และ `ป้ายไทย = value` | ตาม prompt ข้อ 8 |
| Verification Found / Verified / Approved, Evidence "รอการอ้างอิงข้อมูลจริงจาก DB ของทีม" | พบข้อมูล / ตรวจสอบแล้ว / อนุมัติแล้ว, "ยังไม่มีข้อมูลหลักฐาน" | ตาม prompt ข้อ 8 |
| CSS contract ของ 0.3.0 (สี accent `#1f4fa3`, dark mode, มุม 8px) | CSS contract ของ 0.4.0 | สไตล์ใหม่ตาม prompt ข้อ 10 |

test ที่คงไว้และยังผ่าน: ส่งแค่ GET, ไม่มี form control, error ไม่แสดง FAIL, ป้าย issue ครบ 3 แบบ, adapter, status และ responsive (`.ps-grid` 3 / 2 / 1)

จำนวน test frontend: 104 → 124

### SPEC GAP ที่เพิ่ม

- `SPEC_GAPS.md` §4.10:
  - "ความพร้อม" ยังไม่มีแหล่งข้อมูล
  - ป้ายไทยใน `sourceLabels.js` / `fieldLabels.js` และข้อความสถานะภาษาไทยใช้แสดงผลเท่านั้น

## 0.3.0 — 2026-09-23

**เปลี่ยนเฉพาะ frontend** backend และ API contract เหมือน 0.2.0 ทุกอย่าง (แก้แค่เลขเวอร์ชันใน `backend/app/main.py`)

### แก้ไข / เปลี่ยนแปลง

1. **แถบเลือกกลุ่มเกณฑ์ `P1 … P8 PS`** แทนเมนู PS-01…PS-09 เดิม
   - เปิดมาที่ PS, ตัวที่เลือกมี `aria-current="page"` และเส้นใต้สี accent
   - P1–P8 แสดงสีจาง และมี `aria-label` "Pn – ยังไม่อยู่ในขอบเขต"
   - รายการอยู่ที่ `src/app/criteriaGroups.js` (โครงสร้างเมนูเท่านั้น ไม่มี PS code)
2. **Routes ใหม่**
   - `/monitor` → redirect ไป `/monitor/ps` (คง query)
   - `/monitor/p1` … `/monitor/p8` → หน้าแจ้งขอบเขต ไม่เรียก API
   - URL อื่น → `/monitor/ps`
   - ทุกลิงก์คง `?curriculumCode=`
3. **หน้า MONITOR ครบตามไฟล์ออกแบบ**
   - Header, Programme Readiness, PS Overview, Evidence Status, Missing Information, Data Status และความหมายของสถานะ
   - หน้าโหลดข้อมูลเอง (ย้ายออกจาก Layout) และอ่านใหม่ทุกครั้งที่เข้ามา
   - ตัวเลขทั้งหมดเป็นการนับค่าที่ backend ส่งมา ไม่มีเปอร์เซ็นต์
   - Overall แสดง "—" พร้อมหมายเหตุ SPEC GAP
4. **การ์ด PS 3 ชั้น:** PS + สถานะ / สิ่งที่ต้องการ (ตัดที่ 3 บรรทัด) / สถานะปัจจุบัน (dataSummary 2 รายการ ไม่รวม `Operation` + จำนวนที่ขาด)
5. **หน้ารายละเอียด PS** (ลำดับ 9 ส่วนและหัวข้อเดิม)
   - ลิงก์ `← MONITOR` ไป `/monitor/ps`
   - มีบรรทัดอธิบายใต้หัวข้อทุกส่วน
   - `Operation` อยู่ในส่วนสิ่งที่ต้องตรวจสอบ และ `checks` อยู่ใน `<details>`
   - หมายเหตุ `Review` / `Manual result` อยู่ในส่วน Status
   - Traceability เกิน 10 record ที่เหลือจะอยู่ใน `<details>`
6. **สไตล์มินิมอล** พื้นขาว เส้นบาง สี accent เดียว ไม่มีเงา/animation รองรับ dark mode, grid การ์ด 3 / 2 / 1 คอลัมน์เหมือนเดิม
7. **Mock (`npm run dev:mock`)** มีข้อมูล `[MOCK]` ครบทุก panel

### Test ที่ปรับ (พฤติกรรมเปลี่ยนโดยตั้งใจ)

| Test เดิม | เปลี่ยนเป็น | เหตุผล |
|---|---|---|
| "navigation lists MONITOR and the PS the backend returns" | test ของแถบเลือกกลุ่ม (`navigation.test.jsx`) | เมนูไม่แสดง PS code แล้ว |
| "navigation on a detail page lists the PS the backend returns" | "PS stays current on a PS detail page" และ "a detail page does not call /api/monitor" | เมนูไม่ต้องใช้ข้อมูล PS แล้ว |
| "loads the monitoring data once for the page and its navigation" | "the MONITOR page loads its data once" | การโหลดย้ายจาก Layout ไปที่หน้า MONITOR |
| test ที่เปิด `/monitor` | เปิด `/monitor/ps` และเพิ่ม test ว่า redirect ทำงาน | route ใหม่ |
| "has a Back to MONITOR link" (`href="/monitor"`) | ลิงก์ `← MONITOR` ไป `/monitor/ps` | route ใหม่และข้อความตามไฟล์ออกแบบ |
| "card shows … missing information" (ข้อความในการ์ด) | การ์ดแสดง "ขาด N รายการ" | ข้อความเต็มย้ายไปที่ panel Missing Information |

จำนวน test frontend: 48 → 104

### SPEC GAP ที่เพิ่ม

- `SPEC_GAPS.md` §4.9 **Frontend design:** รายการจากไฟล์ออกแบบที่ไม่ได้ทำ เพราะไม่มีข้อมูลใน configuration/API หรือขัดกับ SRS (เปอร์เซ็นต์, ชื่อเกณฑ์, ปุ่มเลือก N/A, หมวด Missing Information, ตาราง, P1–P8)

## 0.2.0 — 2026-09-23

เวอร์ชันนี้พัฒนาต่อจากโค้ดชุดที่ได้รับเมื่อ **2026-09-21** (ไฟล์ล่าสุด 21:23 น.) ต้องใช้แทนชุดเดิมทั้งหมด

> **ห้ามนำไปรวม (merge) กับงานที่ Claude Code แก้ไว้ในเครื่อง**
> งานชุดนั้นไม่ได้อยู่ในไฟล์ที่ได้รับ เวอร์ชันนี้ทำข้อ 1–5 ใหม่ทั้งหมด ถ้ารวมกันจะเกิด conflict

### แก้ไข / เปลี่ยนแปลง

1. **Frontend ไม่มีรายการ PS ตายตัวแล้ว** (SRS §11, §31)
   - ลบ `src/app/psCodes.js`
   - การ์ดและเมนูสร้างจาก `results` ที่ backend ส่งมา และเรียงตามลำดับของ backend
   - โหลดข้อมูลครั้งเดียวที่ Layout แล้วส่งต่อให้หน้า MONITOR
   - ทุกครั้งที่กลับมาหน้า MONITOR จะอ่านข้อมูลใหม่
2. **PS-06: alias ภาษาอังกฤษต้องตรงทั้งคำ**
   - `IT` ไม่ถูกจับในคำ `Nutrition` อีก และ `ICT` ไม่ถูกจับในคำ `Predictive`
   - ภาษาไทยยังค้นหาแบบ substring เหมือนเดิม
   - รายละเอียดอยู่ใน `SPEC_GAPS.md` §3.8
3. **แสดงชื่อแทน ObjectId** (ใช้แสดงผลเท่านั้น)
   - Data Found แสดง `persons.fullName` และ `curricula.curriculumCode` ผ่านตาราง `REFERENCES` / `DISPLAY_FIELD` ใน `models/source_schema.py`
   - การค้นชื่อไม่บันทึกลง Traceability และไม่เปลี่ยนผลตรวจ
4. **Traceability แสดง `field = value`** ตาม SRS §29 (adapter เดิมตัด `values` ทิ้ง)
5. **เพิ่ม field `issue` ในผลของแต่ละ PS** (SRS §48, §50)
   - ค่าที่เป็นไปได้: `configuration_error`, `evaluation_error`, `spec_gap` หรือ `null`
   - หน้าเว็บแสดงเป็นป้าย Configuration Error / Evaluation Error / Spec Gap ข้างสถานะ
6. **PS-08 อ่าน `persons.hasTeachingExperience` ได้** (Import Service SRS §15)
   - `{source, required}` อ้างถึง field ของ record ที่ subject อ้างอิงได้แล้ว (`personId → persons._id`)
   - ค่าที่อ่านได้แสดงให้คนตัดสินเท่านั้น ระบบไม่ตัดสินจากค่านี้
   - ค่า Boolean แสดงเป็น `true` / `false`
7. **ติดตั้ง dependency ของ test ได้ครบ**
   - `requirements-dev.txt` เพิ่ม `httpx2` ซึ่ง Starlette รุ่นใหม่ใช้กับ TestClient
   - เพิ่ม `requirements-dev.lock.txt` (เวอร์ชันที่ทดสอบผ่านแล้ว)
8. **ค่าที่ผิดรูปแบบไม่ทำให้ทั้งหน้าล่ม** (SRS §48)
   - เดิมถ้า config หรือข้อมูลมีค่าผิดชนิด เช่น list แทนชื่อ collection หรือข้อความแทนตัวเลข ระบบทั้งหมดจะตอบ 500
   - ตอนนี้แยกรายงานเฉพาะเกณฑ์นั้น เป็น `configuration_error` หรือเป็น `evaluation_error` สำหรับกรณีที่ไม่คาดคิด (บันทึก log ไว้ด้วย)
   - เกณฑ์อื่นยังแสดงผลตามปกติ
   - มี test สุ่มค่าผิดรูปแบบ 300 แบบ ยืนยันว่าไม่ล่ม
9. **เอกสาร**
   - README เขียนใหม่ให้ตรงกับของจริง (JavaScript, React 19, Vite 8, ไม่มีคำสั่ง `typecheck`)
   - เพิ่ม `docs/TESTING.md`
   - ปรับ `SPEC_GAPS.md`

### พฤติกรรมที่เปลี่ยน (สำหรับทีมที่เรียก API)

- **มี field ใหม่** `issue` ใน PSResult
- **ข้อความ Review ย้ายที่** "Review by user required by configuration" (PS-03) และ "Manual review required…" (PS-08) ย้ายจาก `missingInformation` ไปอยู่ที่ `dataSummary` (label `Review`) ผลคือ PS-03 ได้ `dataCompleteness: complete`
- **รายการใน Data Found เปลี่ยนเป็นชื่อ** ทั้งรายการและ label ของกลุ่มแสดงชื่อแทน id (id ยังดูได้ใน Traceability) โดย PS-03 แสดงชื่ออาจารย์แทน id ของ appointment

### ต้องให้เจ้าของ config / เจ้าของเกณฑ์ยืนยัน

1. alias ภาษาอังกฤษสั้น ๆ ไม่มีตัวไหนตั้งใจให้จับกลางคำ (§3.8)
2. "รอผู้ตรวจ" ไม่นับเป็นข้อมูลไม่ครบ (§3.12) ถ้าไม่ใช่ แก้กลับได้ที่จุดเดียว
3. เมื่อมีทั้ง configuration error และ SPEC GAP ให้รายงานเป็น configuration error ก่อน (§3.13)
4. ค่าผิดชนิดใน config ถือเป็น configuration error ของเกณฑ์นั้นเท่านั้น (§3.14)
5. ใช้ `persons.fullName` / `curricula.curriculumCode` เป็นชื่อที่แสดง

### คำขอแก้ configuration (เจ้าของ `ps_requirements`)

- **เพิ่มตัวกรอง `status: active`** ให้ PS ที่อ่าน `appointments`
- **PS-05:** กำหนดลำดับระดับปริญญาและคำเทียบ เช่น Ph.D., ปริญญาเอก, M.Sc., Master
- **PS-06:** เพิ่ม entry สำหรับ "เทคโนโลยีสารสนเทศอัจฉริยะ" หรือยืนยันว่าใช้ entry "เทคโนโลยีสารสนเทศ" และตัดสินว่า `Informatics` สัมพันธ์กับสาขาหรือไม่
- **PS-03:** กำหนดข้อมูลที่ผู้ตรวจต้องเห็น และที่เก็บผลที่ผู้ตรวจตัดสิน
- **PS-08:** ตั้ง `experience.source` เป็น `"persons.hasTeachingExperience"` และยืนยันว่า "ประสบการณ์สอน" ตรงกับ "ประสบการณ์ที่เหมาะสม"

### ยังไม่ทำ (อยู่นอกขอบเขตหรือยังเป็น SPEC GAP)

- **Docker image / compose** ยังไม่ได้ทำ เพราะทดสอบ build ในสภาพแวดล้อมนี้ไม่ได้ จึงไม่ส่งไฟล์ที่ยังไม่ผ่านการทดสอบ
- **ยังไม่ได้กำหนด** กฎ overall status, แหล่ง Evidence, Verified/Approved, security, External Service A/B และ error code
