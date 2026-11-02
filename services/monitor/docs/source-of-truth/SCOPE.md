# SCOPE — Mornitor (AUN-QA PS Monitor)

> **สถานะเอกสาร:** Source of Truth · ปรับ 2026-09-26 ให้ตรงกับ implementation หลังชุดที่ 1–8 (commit `66ea7f5` + การเปลี่ยนแปลงที่ยังไม่ commit)
> **เอกสารชุดเดียวกัน:** [PS-Config.json](PS-Config.json) · [SRS.md](SRS.md) · [Data-Schema.md](Data-Schema.md) · [API.md](API.md) · [ARCHITECTURE.md](ARCHITECTURE.md)
> รหัสแหล่งอ้างอิง ([SRS-M], [FE-D] ฯลฯ) ใช้ตาม [SRS.md](SRS.md)

## ความหมายของค่าในตาราง

| คอลัมน์ | ค่า |
|---|---|
| In Scope | ✔ = [SRS-M] กำหนดให้ทำ · TBD = SRS ยังไม่ได้กำหนด ([SRS-M] ระบุเป็น `TBD / SPEC GAP`) · "เจ้าของ project" = ไม่อยู่ใน [SRS-M] แต่เจ้าของ project สั่งเพิ่มหรือตัดสินใจ · — = ไม่ใช่ · ข้อมูลไม่เพียงพอ = ไม่พบหลักฐาน |
| Out of Scope | ✔ = [SRS-M] ระบุว่าไม่ใช่หน้าที่ของ Mornitor · — = ไม่ได้ระบุ |
| Implemented | ✔ Implemented · ✖ Not Implemented · — ไม่ทำโดยเจตนา (Out of Scope) |

## 1. Scope Matrix

| Feature | In Scope | Out of Scope | Implemented | Evidence |
|---|---|---|---|---|
| MONITOR Dashboard (`/monitor/ps`) | ✔ §2.1, §17–18 | — | ✔ ข้อมูลหลักสูตร, Programme Readiness (ค่า `programmeReadiness` จาก API), ผล PS-01..PS-09, ข้อมูลที่ขาด, Data Completeness, ปุ่มบันทึกผลการตรวจ (Persistent Monitoring Result), เลือกหลักสูตร และอ่านผลอัตโนมัติ · ช่องผลรวม `overallStatus` แสดง "—" เพราะ API ส่ง `null` (ดูแถว Overall Status ซึ่งแยกจาก Programme Readiness) · รายการ PS code และข้อความ requirement สำรองใน frontend เป็นข้อยกเว้นที่อนุมัติแล้ว (ดูแถวท้ายตาราง) | `frontend/src/pages/Monitor/MonitorPage.jsx`; `monitor.test.jsx`, `monitor-panels.test.jsx`, `waiting.test.jsx` |
| ข้อมูลหลักสูตร (Programme Information) | ✔ §2.1 | — | ✔ ชื่อ รหัส ปี เวอร์ชัน และสถานะของหลักสูตรจาก `curriculum` ใน API (field ที่เป็น `null` ไม่แสดง) | `models/schemas.py` (`CurriculumInfo`); `components/CurriculumBox/CurriculumBox.jsx`; `monitor.test.jsx`, `monitor-panels.test.jsx` |
| หน้าแรก `/` (การ์ด P1 P2 P3 P4 P8 PS) | เจ้าของ project (v0.4.0) | — | ✔ | `pages/Home/HomePage.jsx`, `app/criteriaGroups.js`; `scope.test.jsx` |
| เกณฑ์ P1 P2 P3 P4 P8 | ข้อมูลไม่เพียงพอ ([SRS-M] ครอบคลุมเฉพาะ PS-01..PS-09 และไม่มี configuration) | — | ✖ มีแค่หน้าแจ้งขอบเขต ไม่เรียก API | `pages/ScopeNotice/ScopeNoticePage.jsx`; `scope.test.jsx` |
| PS Detail (`/monitor/ps/:psCode`) | ✔ §19 | — | ✔ ส่วนหัว + 10 ส่วน (สิ่งที่เกณฑ์ต้องการ, ผลการตรวจสอบ, เหตุผล, สิ่งที่ตรวจ, เงื่อนไข, สิ่งที่ระบบตรวจพบ, การยืนยันข้อมูล, ข้อมูลที่ขาด, หลักฐาน, แหล่งที่มา) + ส่วน User Review เมื่อ config ของ PS เปิด · หลักฐานแสดงชื่อไฟล์ storage และ path จาก API · ปุ่มยืนยันและปุ่มบันทึก User Review เรียก API | `pages/PSDetail/PSDetailPage.jsx`; `psdetail.test.jsx`, `verification.test.jsx`, `userReview.test.jsx` |
| PS-01 | ✔ §41 | — | ✔ PASS / FAIL / REVIEW | [SRS.md](SRS.md) §7; `test_ps_evaluation.py` |
| PS-02 | ✔ §41 | — | ✔ PASS / FAIL / REVIEW | [SRS.md](SRS.md) §8 |
| PS-03 | ✔ §41 | — | ✔ engine ให้ REVIEW (ต้องให้ผู้ตรวจพิจารณา) และผลที่ผู้ตรวจเลือกเก็บแยกใน `review` ผ่าน User Review (ไม่ override สถานะ) · ไม่ตรวจข้ามหลักสูตร | [SRS.md](SRS.md) §9; `services/user_review.py`; `test_user_review.py` |
| PS-04 | ✔ §41 | — | ✔ PASS / FAIL | [SRS.md](SRS.md) §10 |
| PS-05 | ✔ §41 | — | ✔ PASS / FAIL / REVIEW (degree ordering จาก config) | [SRS.md](SRS.md) §11 |
| PS-06 | ✔ §41; User Confirmation: อาจารย์ยืนยัน 2026-09-29 | — | ✔ engine ให้ REVIEW เท่านั้น (ไม่เทียบชื่อสาขาหรือ Major เอง ไม่มี mapping) · แสดงอาจารย์ผู้รับผิดชอบหลักสูตรแต่ละคนพร้อมระดับคุณวุฒิ สาขาวิชา สถาบัน และหลักสูตร · ผู้ใช้ยืนยัน PASS (มีความสัมพันธ์) / FAIL (ไม่มีความสัมพันธ์) ผ่าน User Review เก็บใน `review` · สถานะที่แสดงและความพร้อมทั้งสองใช้ผลที่ผู้ใช้ยืนยัน (`readiness_status()`) · `status` และ `result` ที่บันทึกยังเป็น REVIEW | [SRS.md](SRS.md) §12; `services/user_review.py`; `test_ps06_user_confirmation.py`, `test_ps_evaluation.py`, `ps06Confirmation.test.jsx` |
| PS-07 | ✔ §41 | — | ✔ PASS / FAIL / REVIEW | [SRS.md](SRS.md) §13 |
| PS-08 | ✔ §41 | — | ✔ N/A / PASS / FAIL / REVIEW (มีคุณวุฒิ + `hasTeachingExperience == true`) | [SRS.md](SRS.md) §14 |
| PS-09 | ✔ §41 | — | ✔ PASS / FAIL / REVIEW | [SRS.md](SRS.md) §15 |
| MongoDB | ✔ §2.1, §7; การเขียน `monitoring_results`: เจ้าของ project 2026-09-26 | — | ✔ ข้อมูลต้นทางและ configuration: **อ่านอย่างเดียว** (`find`) · collection ของ Mornitor `monitoring_results`: **เขียนได้** (verification / review / result) โดย `adapters/monitoring_results.py` ที่เดียว (ดู §4) | `backend/app/adapters/mongo.py`, `backend/app/adapters/monitoring_results.py`; `test_backend_parity.py`, `test_architecture.py` |
| Rule Engine (generic, configuration-driven) | ✔ §13, §15 | — | ✔ | `backend/app/monitoring/`; `test_architecture.py`, `test_generic_capabilities.py`, `test_ps_evaluation.py` |
| FastAPI (Monitoring API) | ✔ §46 (SRS ไม่ได้กำหนด endpoint; ใช้ตาม [API.md](API.md)) | — | ✔ 5 endpoint ภายใต้ `/api/monitor`: `GET` (ผลของหลักสูตร), `GET /ps/{psCode}`, `POST /results`, `POST /ps/{psCode}/verification`, `POST /ps/{psCode}/review` · `GET` ไม่เขียนอะไร · `POST` เขียนเฉพาะ `monitoring_results` | `backend/app/api/routes/monitor.py`; `test_engine_and_api.py`, `test_verification.py`, `test_user_review.py`, `test_persisted_results.py`; [API.md](API.md) |
| React (Web UI) | ✔ §16 | — | ✔ | `frontend/src/`; frontend tests 339 passed |
| Evidence | ✔ §28 | — | ✔ อ่านจาก `documents` ของหลักสูตรที่ตรวจ (`documents.curriculumId = curricula._id`) แบบอ่านอย่างเดียว · ต่อเอกสาร `{label: fileName, reference: _id, storage: originalFile.storage, path: originalFile.path}` (ค่าที่ไม่มีเป็น `null`) · ทุก PS ของหลักสูตรได้รายการเดียวกัน เพราะไม่มี field ที่เชื่อมเอกสารกับ PS รายตัว (เจ้าของ project ตัดสินใจ 2026-09-26) · ไม่เปิดไฟล์ ไม่เปลี่ยนสถานะหรือ readiness · การยืนยันหลักฐานอยู่ในแถว Verification | `services/evidence.py`; `components/Evidence/Evidence.jsx`; `test_evidence.py`, `test_backend_parity.py`, `evidence.test.jsx` |
| Traceability | ✔ §29, §55 | — | ✔ (หน้าเว็บแสดงแหล่งข้อมูล รหัสอ้างอิง และชื่อ field ไม่แสดงค่า) | `monitoring/context.py`; `components/Traceability/Traceability.jsx` |
| Missing Information | ✔ §26 | — | ✔ (หน้าเว็บแปลเป็นไทยเฉพาะข้อความที่มีแม่แบบ ที่เหลือแสดงข้อความสำรอง) | `engine.py`, `subject_checks.py`; `app/missingText.js`; `missing.test.jsx` |
| Verification | ✔ §27; การกดยืนยัน: เจ้าของ project | — | ✔ ผู้ใช้กด "ยืนยันหลักฐาน / ผลการตรวจ" ในหน้ารายละเอียด PS → `POST /api/monitor/ps/{psCode}/verification` → บันทึกใน `monitoring_results` (`{curriculumId, psCode, verification: {verified: true, verifiedAt}}`, key ไม่ซ้ำ curriculumId + psCode, กดซ้ำไม่สร้างรายการซ้ำ เวลาครั้งแรกคงเดิม) → `GET` อ่าน `verification.verified` / `verifiedAt` กลับมา (ค่าคงอยู่หลัง reload หรือ restart) · ยืนยันทั้งหลักฐานที่แสดงและผล PS (เจ้าของ project 2026-09-26) · `approved` เป็น `null` (เจ้าของ project กำหนด) · ไม่เปลี่ยนสถานะ PS, evidence, traceability, Programme / Generation Readiness และ PS-03 | `services/monitoring_service.py`, `repositories/monitoring_results.py`, `adapters/monitoring_results.py`, `api/routes/monitor.py`; `components/Verification/Verification.jsx`; `test_verification.py`, `test_backend_parity.py`, `verification.test.jsx` |
| Generation Readiness (config + การตัดสิน READY / NOT_READY) | เจ้าของ project (2026-09-26) | — | ✔ อ่าน config จาก `ps_requirements` (`configType: "generationReadiness"`) แล้วตัดสินจากผลการประเมินปัจจุบัน → `generationReadiness` ใน `GET /api/monitor` (`READY` / `NOT_READY`; `null` = configuration ตัดสินไม่ได้) · นับสถานะของแต่ละ PS ด้วย `readiness_status()` (ผลที่ผู้ใช้บันทึกใน User Review ถ้ามี มิฉะนั้นผลของ engine; เจ้าของ project 2026-09-27) · config ACTIVE กำหนด PS-03 และ PS-06 เป็น required ทั้งสองเป็น REVIEW จนกว่าผู้ใช้จะบันทึกผล จึงได้ `NOT_READY` จนกว่าผู้ใช้จะยืนยัน · ไม่ใช่ Programme Readiness | `services/generation_readiness.py`; `test_generation_readiness.py`, `test_generator_contract.py`, `test_backend_parity.py` |
| Programme Readiness | เจ้าของ project (2026-09-26) | — | ✔ `programmeReadiness` = จำนวน PS ที่เป็น PASS ÷ 9 × 100 (ทศนิยม 2 ตำแหน่ง) · นับเฉพาะ PASS (FAIL, REVIEW, N/A, ไม่มีผล ไม่นับ) · ตัวหาร 9 เสมอ · คำนวณที่ backend หน้าเว็บแสดงค่าจาก API · ไม่มีหลักสูตร → `null` · ไม่ใช่ Generation Readiness และไม่ใช่ `overallStatus` | `models/schemas.py` (`ProgrammeReadiness`); `components/ProgrammeReadiness/ProgrammeReadiness.jsx`; `test_programme_readiness.py`, `programmeReadiness.test.jsx` |
| Overall Status (`overallStatus`) | SRS ยังไม่ได้กำหนดกฎ | — | ✖ Not Implemented: API ส่ง `null` (คง field ไว้เพื่อ compatibility) · แยกจาก Programme Readiness ซึ่ง Implemented | `services/monitoring_service.py` |
| SAR Generation | — | ✔ §62–63 (หน้าที่จำกัดที่อ่าน-ตรวจ-แสดง); `README.md` | — Out of Scope · การเชื่อมกับ Document Generation เป็นแค่การให้อ่าน readiness (pull) ไม่ใช่การสร้าง SAR | ไม่มี code; `generated_documents` มีแค่การประกาศใน Data Schema |
| OCR | — | ✔ §3.1 | — Out of Scope | ไม่มี code |
| Document Extraction | — | ✔ §3.1, §39 | — Out of Scope | ไม่มี code; Evidence อ่านแค่ reference (`originalFile.storage/.path`) ไม่เปิดไฟล์ |
| Import (นำเข้าข้อมูลต้นทาง) | — | ✔ §3.1 | — Out of Scope | script ข้อมูลทดสอบ `backend/scripts/seed_test_data.py` เขียนได้เฉพาะ database ที่ชื่อลงท้าย `_test` (เครื่องมือทดสอบ ไม่ใช่ความสามารถของระบบ) |
| Authentication | TBD §51 | — | ✖ Not Implemented | ไม่มี code |
| Authorization | TBD §51 | — | ✖ Not Implemented | ไม่มี code (มีแค่ CORS จำกัด origin และ method `GET`, `POST`; route `POST` มีเฉพาะการเขียน `monitoring_results`) |
| Configuration CRUD | — | ✔ §4, §8 | — Out of Scope (configuration อ่านอย่างเดียว) | `adapters/mongo.py` (`find` เท่านั้น) |
| Source Data CRUD | — | ✔ §3.2–3.3, §7 | — Out of Scope (ข้อมูลต้นทางอ่านอย่างเดียว) | `adapters/mongo.py`; `test_backend_parity.py` |
| เลือกหลักสูตร (`?curriculumCode=`, `409`) | ไม่มีใน [SRS-M] (SPEC GAP) | — | ✔ | `services/monitoring_service.py`; `test_engine_and_api.py` |
| อ่านผลใหม่อัตโนมัติทุก 10 วินาที | เจ้าของ project | — | ✔ | `frontend/src/api/useRemote.js`; `waiting.test.jsx` |
| ผลที่ผู้ตรวจเลือก (User Review: PS-03, PS-06) | config `reviewByUser` (PS-03; PS-06 ตั้งแต่ 2026-09-29); การบันทึก: เจ้าของ project | — | ✔ ผู้ตรวจเลือก PASS / FAIL / REVIEW (ตัวเลือกจาก `config.review.allowManualResult`) ในหน้ารายละเอียด PS-03 / PS-06 (PS-06: ปุ่ม "มีความสัมพันธ์" = PASS, "ไม่มีความสัมพันธ์" = FAIL) → `POST /api/monitor/ps/{psCode}/review` (body `{status}`) → `monitoring_results` เอกสารเดียวกับ verification (`review: {status, reviewedAt}` เวลาของ server, บันทึกซ้ำแก้เอกสารเดิม) → `GET` อ่าน `review` กลับ (ค่าคงอยู่หลัง refresh / restart) · เปิดเฉพาะ PS ที่ config มี `review.required` + `review.reviewByUser` (config ACTIVE: PS-03, PS-06) · **ไม่ override:** `status` ยังเป็นของ engine (REVIEW) · สถานะที่แสดงและ Programme / Generation Readiness ใช้ผลนี้ (`resolveStatus` / `readiness_status()`, เจ้าของ project 2026-09-27) | `services/user_review.py`, `services/monitoring_service.py`, `repositories/monitoring_results.py`, `adapters/monitoring_results.py`, `api/routes/monitor.py`; `components/UserReview/UserReview.jsx`; `test_user_review.py`, `test_backend_parity.py`, `userReview.test.jsx` |
| External Service: Document Generation (Generator Pull) | ✔ §6; ทิศทาง pull / readiness-only: เจ้าของ project 2026-09-26 | — | ✔ Document Generation เป็นฝ่าย **pull**: เรียก `GET /api/monitor?curriculumCode=…` แล้วอ่านเฉพาะ `generationReadiness.status` จากนั้นดึงข้อมูลที่ใช้ Generate จาก DB ของตัวเอง · Mornitor ไม่ push ไม่มี webhook / callback / outbound call ไม่ส่ง PS results, evidence, curriculum หรือ documents ให้ Generator · เป็นการให้อ่าน readiness เท่านั้น **ไม่ใช่ SAR Generation** (เจ้าของ project 2026-09-26) | `GET /api/monitor` (`api/routes/monitor.py`); `test_generator_contract.py` |
| External Service A / B (adapter) | ✔ §6 (SRS ไม่ได้ระบุ interface) | — | — ไม่ต้องมี adapter: service ที่รู้จักตัวเดียวคือ Document Generation ซึ่งใช้ pull · class ว่างคงไว้ | `backend/app/adapters/external_services.py`; `test_generator_contract.py` (`test_mornitor_pushes_nothing`) |
| เก็บผลการตรวจถาวร (Persistent Monitoring Result) | SRS §8 ไม่ได้กำหนดรายละเอียด; รูปแบบ / trigger / field / การเปลี่ยนของข้อมูลต้นทาง: เจ้าของ project 2026-09-26 | — | ✔ ผู้ใช้กด "บันทึกผลการตรวจของหลักสูตร" ในหน้าภาพรวม → `POST /api/monitor/results?curriculumCode=` → ประเมินใหม่ด้วย engine (เหมือน GET) แล้วเก็บ `result: {status, evaluatedAt}` ในเอกสาร `curriculumId + psCode` ของทุก PS ที่ active (bulk write ครั้งเดียว เวลาของ server) → `GET` อ่านกลับเป็น `persistedResult` · current state: บันทึกใหม่แทนค่าเดิม ไม่เก็บประวัติ และคงค่าเดิมเมื่อข้อมูลต้นทางเปลี่ยนจนกว่าจะบันทึกใหม่ · เก็บเฉพาะ status (ไม่เก็บ readiness / evidence / traceability) · ไม่ถูกส่งกลับเข้า engine และไม่มี readiness ใดอ่าน · ไม่ลบ `verification` / `review` (เจ้าของ project 2026-09-26) | `services/monitoring_service.py` (`save_results`), `repositories/monitoring_results.py`, `adapters/monitoring_results.py`, `components/PersistedResults/PersistedResults.jsx`; `test_persisted_results.py`, `test_backend_parity.py`, `persistedResults.test.jsx` |
| Logging (Error Logging) | SRS §54 ไม่ได้กำหนดรายละเอียด; ขอบเขต "Error Logging": เจ้าของ project 2026-09-26 | — | ✔ Error Logging (ชุดที่ 8): Python `logging` handler เดียวบน logger `app` (stderr) · รูปแบบ `<เวลา> <LEVEL> <module> [<category>] <message>` + traceback สำหรับ error · ERROR: `data_source_error` / `connection_error` (ทุก `503` พร้อม operation และ `curriculumCode`), `evaluation_error` (engine ล้มเหลวที่ PS หนึ่ง), `system_error` (exception ที่ไม่มี route จัดการ → `500` "Internal Server Error") · WARNING: `configuration_error` (config ของ PS หรือ Generation Readiness ใช้ไม่ได้ request ยังตอบ `200`) · ไม่มีหมวด External Service Error เพราะไม่มี outbound call · ไม่ log ผล PASS / FAIL / REVIEW / N/A, request ปกติ, 4xx, header / cookie / body / query / เอกสาร · ซ่อน user:password ใน URL · log ไม่ถูกเขียนลง database และไม่ส่งออกภายนอก (audit log / metrics อยู่นอกขอบเขตที่เจ้าของ project กำหนด) | `app/error_log.py`, `main.py` (middleware), `api/routes/monitor.py`, `services/monitoring_service.py`, `monitoring/engine.py`; `test_error_logging.py` |
| แยกประเภทข้อผิดพลาด (Error classification: `issue`, `503`, log) | ✔ §48–50 | — | ✔ `issue` ใน API แยก `configuration_error` / `evaluation_error` / `spec_gap` · log แยก 5 หมวด: `configuration_error`, `data_source_error`, `connection_error`, `evaluation_error`, `system_error` (connection = `DataSourceConnectionError` จาก pymongo `ConnectionFailure`) · HTTP: data source และ connection ตอบ `503`, system ตอบ `500` | `engine.py`, `routes/monitor.py`, `adapters/mongo.py`, `app/error_log.py`; `test_issue_reporting.py`, `test_error_logging.py` |
| N/A ตาม configuration | ✔ §24 | — | ✔ | `engine.py` `_no_subjects` |
| Data Completeness | ✔ §2.1 | — | ✔ (`dataCompleteness`) | `models/schemas.py`; `components/Completeness` |
| ป้ายและข้อความภาษาไทย (แสดงผลเท่านั้น) | เจ้าของ project | — | ✔ | `app/fieldLabels.js`, `sourceLabels.js`, `explain.js`, `missingText.js` |
| ข้อความ requirement สำรองใน frontend | ข้อยกเว้นของ §12/§31 (เจ้าของ project 2026-09-25) | — | ✔ | `app/psTitles.js`; `psTitles.test.jsx` |
| รายการ PS code ใน frontend | ข้อยกเว้นของ §11/§32 | — | ✔ | `app/psGuideline.js`; `guideline.test.jsx` |
| Docker (backend + frontend) และการเชื่อมต่อ MongoDB บนเครื่อง | เจ้าของ project (2026-09-26) | — | ✔ `compose.yaml` 2 container: `backend` (`python:3.11-slim`, user ไม่ใช่ root) และ `frontend` (nginx เสิร์ฟหน้าเว็บ + ส่ง `/api/` ต่อให้ backend) · ไม่มี MongoDB ใน compose: ต่อ database บนเครื่องผ่าน `host.docker.internal` (ค่าใน `.env` จาก `.env.example`) · พอร์ตเฉพาะ `127.0.0.1` (หน้าเว็บ 8080, API 8000) · ใช้บนเครื่องเดียว ไม่ใช่การ deploy สำหรับผู้ใช้หลายคน (ไม่มี HTTPS / authentication) · ทดสอบกับ Docker Desktop บน macOS | `compose.yaml`, `.env.example`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`; `test_docker.py`; [TESTING.md](../TESTING.md) §0.1 |
| Performance target | TBD §52 | — | ✖ Not Implemented (SRS ไม่ได้กำหนดเป้าหมาย) | ไม่มีเป้าหมายและไม่มี test |

## 2. สรุปตามกลุ่ม

| กลุ่ม | รายการ |
|---|---|
| **Implemented** | Dashboard, Programme Information, Programme Readiness, หน้าแรก, PS Detail, PS-01..PS-09 (PS-03, PS-06 = REVIEW + User Review), MongoDB (ข้อมูลต้นทางอ่านอย่างเดียว + เขียน `monitoring_results`), Rule Engine, FastAPI, React, Traceability, Missing Information, Data Completeness, N/A, เลือกหลักสูตร, อ่านผลอัตโนมัติ, Evidence (read-only), Verification, PS-03 User Review + การเก็บผล, Persistent Monitoring Result, Generation Readiness, Document Generator Pull (readiness-only), Error Logging, Error classification, Docker + การเชื่อมต่อ MongoDB บนเครื่อง |
| **Partially Implemented** | ไม่มี |
| **Not Implemented / TBD** | Authentication (TBD §51), Authorization (TBD §51), Performance target (TBD §52), การ deploy สำหรับผู้ใช้หลายคน (HTTPS / reverse proxy ภายนอก; ข้อมูลไม่เพียงพอ), Overall Status `overallStatus` (SRS ยังไม่ได้กำหนดกฎ; API ส่ง `null`), เกณฑ์ P1 P2 P3 P4 P8 (ข้อมูลไม่เพียงพอ; มีแค่หน้าแจ้งขอบเขต) |
| **Out of Scope** | SAR Generation, OCR, Document Extraction, Import, Configuration CRUD, Source Data CRUD · Generator integration เป็นแค่การให้อ่าน readiness (pull) ไม่ใช่ SAR Generation |
| **ข้อมูลไม่เพียงพอ** | ระบบที่สร้าง `generated_documents` (Mornitor ไม่เขียน collection นี้) |

## 3. ผลที่เกิดได้จากข้อมูลของแต่ละ PS (config ACTIVE)

| PS | PASS | FAIL | REVIEW | N/A | หมายเหตุ |
|---|:-:|:-:|:-:|:-:|---|
| PS-01 | ✔ | ✔ | ✔ | — | REVIEW + `spec_gap` เมื่อมี record ไม่มี `personId` |
| PS-02 | ✔ | ✔ | ✔ | — | |
| PS-03 | — | — | ✔ | — | engine ให้ REVIEW เท่านั้น · ผลที่ผู้ตรวจเลือก (PASS / FAIL / REVIEW) เก็บแยกใน `review` ไม่เปลี่ยน `status` |
| PS-04 | ✔ | ✔ | — | — | REVIEW เกิดได้จาก config ผิดรูปแบบเท่านั้น |
| PS-05 | ✔ | ✔ | ✔ | — | |
| PS-06 | — | — | ✔ | — | engine ให้ REVIEW เท่านั้น · ผลที่ผู้ใช้ยืนยัน (PASS / FAIL) เก็บแยกใน `review` ไม่เปลี่ยน `status` · config เดิมแบบ mapping (ถ้ายังอยู่ใน database) ได้ REVIEW + `spec_gap` |
| PS-07 | ✔ | ✔ | ✔ | — | |
| PS-08 | ✔ | ✔ | ✔ | ✔ | |
| PS-09 | ✔ | ✔ | ✔ | — | |

รายละเอียดเงื่อนไขของแต่ละช่องอยู่ใน [SRS.md](SRS.md) §7–15 ทุก PS ได้ REVIEW + `configuration_error` เมื่อ config ของ PS นั้นผิดรูปแบบ และได้ REVIEW + `evaluation_error` เมื่อ engine ล้มเหลวที่ PS นั้น

## 4. ความปลอดภัยของข้อมูลใน database

| ข้อมูล | สิทธิ์ของ Mornitor | ที่มา |
|---|---|---|
| ข้อมูลต้นทาง (เช่น `curricula`, `persons`, `appointments`, `documents`) | **อ่านอย่างเดียว** (`find`) ไม่แก้ ไม่ลบ ไม่เพิ่ม | `adapters/mongo.py` (`MongoSourceDataAdapter`); `test_architecture.py`, `test_backend_parity.py` |
| Configuration (`ps_requirements` รวมเอกสาร `generationReadiness`) | **อ่านอย่างเดียว** (`find`) | `adapters/mongo.py` (`MongoConfigurationAdapter`) |
| `monitoring_results` (collection ของ Mornitor) | **เขียนได้**: `update_one` / `bulk_write` แบบ upsert + unique index `curriculumId_psCode` เขียนผ่าน `POST` 3 route เท่านั้น (`/results`, `/ps/{psCode}/verification`, `/ps/{psCode}/review`) · `GET` ไม่เขียน | `adapters/monitoring_results.py` (ที่เดียวที่เขียน database); `test_architecture.py`, `test_persisted_results.py` |
| ตำแหน่งของ `monitoring_results` | ตั้งแยกได้ด้วย `MORNITOR_RESULTS_DB_URI` / `MORNITOR_RESULTS_DB_NAME` (ค่าเริ่มต้น = database เดียวกับข้อมูลต้นทาง) | `app/settings.py` |
| Log | ออก stderr เท่านั้น ไม่เขียนลง database | `app/error_log.py` |

## 5. หลักฐานการทดสอบ (หลังแก้ PS-05 / PS-07, 2026-09-27)

| รายการ | ผล |
|---|---|
| Backend (pytest) | 1033 passed / 0 failed / 0 skipped (908 เดิม + 12 `test_docker.py` + 113 `test_degree_and_year_forms.py`) |
| Frontend (vitest) | 339 passed |
| Frontend build (`npm run build`) | PASS |
| E2E (MongoDB ชั่วคราว + FastAPI + frontend) | PASS |
| Regression ชุดที่ 1–7 | PASS |
| Regression ชุดที่ 8 | PASS |
| Docker build (`docker compose build`) | PASS |
| Backend test ใน image base `python:3.11-slim` | 901 passed / 19 skipped (parity ต้องมี `mongod` ซึ่งไม่มีใน container) |
| Docker E2E (compose → MongoDB บนเครื่องทาง `host.docker.internal`) | PASS: หน้าเว็บ / route ฝั่ง client `200`, ผลผ่าน nginx = API ตรง = backend นอก Docker, `POST` เขียนเฉพาะ `monitoring_results`, user ไม่ใช่ root, พอร์ตเฉพาะ `127.0.0.1`, database ต่อไม่ได้ → `503` + log `[connection_error]` ไม่มีรหัสผ่าน |
