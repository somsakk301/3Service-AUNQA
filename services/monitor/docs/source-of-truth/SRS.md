# SRS — Mornitor (AUN-QA PS Monitor)

> **สถานะเอกสาร:** Source of Truth · จัดทำ 2026-09-26 จาก working tree ของ repository (commit `66ea7f5` + การเปลี่ยนแปลงที่ยังไม่ commit) โดยตรวจจาก source code, test และไฟล์ configuration จริง
> **เอกสารชุดเดียวกัน:** [PS-Config.json](PS-Config.json) · [SCOPE.md](SCOPE.md) · [Data-Schema.md](Data-Schema.md) · [API.md](API.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

## ป้ายที่ใช้ในเอกสารนี้

| ป้าย | ความหมาย |
|---|---|
| **Current Implementation** | สิ่งที่ code ทำจริง ณ วันที่จัดทำ (ยืนยันจาก source code และ test) |
| **Intended Scope** | สิ่งที่ SRS ต้นฉบับของโครงการกำหนดให้ Mornitor ทำ |
| **Not Implemented** | อยู่ใน Intended Scope แต่ code ยังไม่มี |
| **Out of Scope** | SRS ต้นฉบับกำหนดว่าไม่ใช่หน้าที่ของ Mornitor |
| **ข้อมูลไม่เพียงพอ** | ไม่พบหลักฐานใน code หรือเอกสาร |

## แหล่งอ้างอิง

| รหัส | ไฟล์ | ใช้เป็น |
|---|---|---|
| [SRS-M] | `~/Mornitor-Data/SRS-Mornitor.md` (นอก repository) | Intended Scope |
| [DD] | `~/Mornitor-Data/Datadict (1).md` | Data Dictionary |
| [DS] | `~/Mornitor-Data/Dataschema (2).md` | ตัวอย่างเอกสาร MongoDB |
| [FE-D] | `~/Mornitor-Data/Forntend.md` | ภาพออกแบบหน้าเว็บ (ตัวเลขและชื่อในภาพเป็นตัวอย่าง ไม่ใช่ข้อมูลจริง) |
| [IMP] | `~/Downloads/IMPORT_SERVICE_SRS_v1.0.md` | SRS ของ Import Service (อีกระบบ) |
| [CFG] | [PS-Config.json](PS-Config.json) → `backend/tests/fixtures/ps_config_v1.json` | Configuration ACTIVE |

---

## 1. Introduction

Mornitor เป็นระบบ Monitoring แบบ Plug-in ที่ตรวจข้อมูลของหลักสูตรตามเกณฑ์ Programme Standards PS-01 ถึง PS-09 โดยอ่านทั้ง configuration ของเกณฑ์และข้อมูลต้นทางจาก MongoDB แล้วแสดงผลผ่านหน้าเว็บ

| ส่วน | Current Implementation |
|---|---|
| Backend | Python + FastAPI (`backend/app`), version `0.4.0` ใน `backend/app/main.py` |
| Frontend | React 19 + Vite 8, JavaScript/JSX (`frontend/src`), version `0.4.0` ใน `frontend/package.json` |
| Database | MongoDB ผ่าน pymongo (source / configuration อ่านอย่างเดียว; เขียนได้เฉพาะ `monitoring_results` ของ Monitor) |
| Test | backend `pytest` 1033 passed (รวม 19 test ที่ต้องมี `mongod`, 12 test ของไฟล์ Docker และ 113 test รูปแบบวุฒิ / ปีของ PS-05 / PS-07) · frontend `vitest` 339 passed (19 ไฟล์) — รัน 2026-09-27 หลังแก้ PS-05 / PS-07 |
| Docker | `compose.yaml` (backend + frontend/nginx) ต่อ MongoDB บนเครื่องผ่าน `host.docker.internal` · ดู `README.md` §3 |

การเปลี่ยนแปลงหลัง 0.4.0 (engine M1, PS-05 ordering, PS-08 condition, หน้าเว็บหลายส่วน) ยังไม่ commit และบันทึกไว้ในหัวข้อ "Unreleased" ของ `CHANGELOG.md`

| Configuration | ตำแหน่ง |
|---|---|
| ACTIVE FILE | `backend/tests/fixtures/ps_config_v1.json` |
| RUNTIME | MongoDB collection `ps_requirements` (backend ไม่อ่านไฟล์ configuration ใด ๆ ตอนทำงาน) |
| DOCUMENTATION SNAPSHOT | `docs/source-of-truth/PS-Config.json` |

## 2. Purpose

**Intended Scope** ([SRS-M] §1): Mornitor มีหน้าที่
1. เชื่อมต่อ Data Source
2. อ่านข้อมูลจาก Database
3. อ่าน Configuration จาก Database
4. ตรวจข้อมูลตาม Configuration
5. ประเมิน PS-01 ถึง PS-09
6. ระบุข้อมูลที่พบ
7. ระบุข้อมูลที่ขาด
8. แสดงผลการตรวจ
9. แสดง Traceability
10. แสดงผลผ่าน Web Interface

Mornitor **ไม่มีหน้าที่สร้างหรือแก้ไขข้อมูลต้นทาง** ([SRS-M] §1, §7)

**เอกสารนี้**ใช้เป็นข้อกำหนดที่ตรงกับ code ปัจจุบัน และแยกให้เห็นว่าข้อใดทำแล้ว ข้อใดยังไม่ทำ ข้อใดอยู่นอกขอบเขต

## 3. Scope

**Intended Scope** ([SRS-M] §2.1):
- Database Connection, Data Reading, Configuration Reading
- Configuration-driven Evaluation, Data Completeness Checking, PS-01 ถึง PS-09 Evaluation
- Evaluation Result, Missing Information, Verification Information, Evidence Reference, Traceability
- Dashboard, PS Detail, Service Integration Boundary

**Current Implementation** โดยย่อ:
- Backend มี API แบบ `GET` 2 endpoint ([API.md](API.md))
- Engine ตรวจตาม configuration แบบ generic ([ARCHITECTURE.md](ARCHITECTURE.md))
- หน้าเว็บมีหน้าแรก หน้าภาพรวมเกณฑ์ PS หน้ารายละเอียด PS และหน้าแจ้งขอบเขตของ P1 P2 P3 P4 P8

ตาราง Feature ทั้งหมดพร้อมหลักฐานอยู่ที่ [SCOPE.md](SCOPE.md)

## 4. System Overview

```text
Import Service (อีกระบบ)          เจ้าของ Configuration
        │ เขียนข้อมูลต้นทาง                 │ เขียน ps_requirements
        ▼                                   ▼
   MongoDB: curricula, persons, appointments, educations, academic_works, … + ps_requirements
        │ อ่านอย่างเดียว (find)
        ▼
   Backend (FastAPI): MonitoringService → MonitoringEngine (generic) → PSResult
        │ GET /api/monitor, GET /api/monitor/ps/{psCode}
        ▼
   Frontend (React): หน้าแรก / ภาพรวมเกณฑ์ PS / รายละเอียด PS   ← ผู้ใช้เปิดดู กดยืนยัน บันทึกผล PS-03 และบันทึกผลการตรวจ (POST verification / review / results → monitoring_results)
```

| หน้าเว็บ (route) | Current Implementation |
|---|---|
| `/` | หน้าแรก "เลือกส่วนที่ต้องการดู" มีการ์ด P1 P2 P3 P4 P8 PS ไม่เรียก API |
| `/monitor/ps` | ภาพรวมเกณฑ์ PS (§16) |
| `/monitor/ps/:psCode` | รายละเอียดเกณฑ์ (§17) |
| `/monitor/p1` `p2` `p3` `p4` `p8` | หน้าแจ้งว่า "ยังไม่มีข้อมูลสำหรับส่วนนี้" ไม่เรียก API |
| URL อื่น (รวม `/monitor`, `/monitor/p5`–`p7`) | redirect ไป `/` โดยคง query เดิม |

ทุกลิงก์คง `?curriculumCode=` ไว้

**Data Ownership** ([SRS-M] §8):
- Data Source เป็นเจ้าของข้อมูลต้นทาง
- Configuration Source เป็นเจ้าของ configuration
- Mornitor เป็นเจ้าของผลการตรวจ **Current Implementation คำนวณผลใหม่ทุก request (engine เป็นผู้ตัดสินเสมอ) และเก็บถาวรใน collection ของ Monitor `monitoring_results`: การยืนยัน, ผลที่ผู้ตรวจเลือก และสถานะที่ผู้ใช้กดบันทึก (current state)** (เจ้าของ project 2026-09-26; [SRS-M] §8 ระบุว่าการจัดเก็บเป็น `TBD / SPEC GAP`)

## 5. Users / Actors

[SRS-M] ไม่ได้กำหนดบทบาทผู้ใช้ และ code ไม่มีระบบยืนยันตัวตน ทุกคนที่เปิดหน้าเว็บเห็นข้อมูลเหมือนกัน

| Actor | ที่มา | Current Implementation |
|---|---|---|
| ผู้ใช้หน้าเว็บ | [SRS-M] §16; [FE-D] เรียกว่า "ผู้จัดทำรายงาน" | เปิดดู และกดยืนยันหลักฐาน / ผลการตรวจของแต่ละ PS ได้ ไม่มี login ไม่มีสิทธิ์แยกระดับ (ไม่รู้ว่าใครยืนยัน) |
| ผู้ตรวจ (reviewer) | config PS-03 `reviewByUser: true` | บันทึกผลที่เลือกได้ในหน้ารายละเอียด PS-03 (§9) ไม่มี login จึงไม่รู้ว่าใครเป็นผู้ตรวจ |
| เจ้าของ Configuration | [SRS-M] §8, §58 | ดูแล `ps_requirements` นอกระบบ (Mornitor ไม่มีหน้าแก้ config) |
| Import Service | [SRS-M] §3.1; [IMP] | ระบบภายนอกที่เขียนข้อมูลต้นทาง Mornitor อ่านอย่างเดียว |
| Document Generation | [SRS-M] §6; เจ้าของ project 2026-09-26 | เรียก `GET /api/monitor?curriculumCode=…` และอ่านเฉพาะ `generationReadiness.status` (pull) แล้วดึงข้อมูลจาก DB ของตัวเอง |
| External Service A / B | [SRS-M] §6 | มีแค่ class ว่าง `ExternalServiceAAdapter` / `ExternalServiceBAdapter` (TBD) ไม่มี service ใดใช้ |

บทบาทผู้ใช้ที่ละเอียดกว่านี้: **ข้อมูลไม่เพียงพอ**

## 6. Functional Requirements

| ID | Requirement | ที่มา | สถานะ | หลักฐาน |
|---|---|---|---|---|
| FR-01 | อ่าน configuration จาก collection `ps_requirements` เฉพาะเอกสาร `active: true` | [SRS-M] §9, §40 | Implemented | `adapters/mongo.py`, `repositories/configuration.py`; `test_engine_and_api.py` |
| FR-02 | อ่านข้อมูลต้นทางแบบอ่านอย่างเดียว (ใช้ `find` เท่านั้น) | [SRS-M] §7 | Implemented | `adapters/mongo.py`; `test_architecture.py`; `test_backend_parity.py` (ยืนยันว่า DB ไม่เปลี่ยน) |
| FR-03 | ตรวจแบบ generic ตาม configuration ไม่มีกฎหรือค่า business ใน code | [SRS-M] §10, §13, §30 | Implemented | `monitoring/*`; `test_architecture.py` (ห้ามคำ business, ค่า config และตัวเลขอื่นนอกจาก 0, 1, -1) |
| FR-04 | construct ที่ engine ไม่รู้จัก → REVIEW + `spec_gap`; config ผิดรูปแบบ → REVIEW + `configuration_error` | [SRS-M] §13, §45, §50 | Implemented | `monitoring/interpreter.py`; `test_issue_reporting.py`, `test_engine_and_api.py` |
| FR-05 | ผลต่อ PS มี status, requirement, checks, dataSummary, dataFound, verification, missingInformation, evidence, traceability, dataCompleteness, issue | [SRS-M] §46 | Implemented (approved เป็น null) | `models/schemas.py`; [API.md](API.md) |
| FR-06 | เลือกหลักสูตรด้วย `?curriculumCode=`; ไม่ระบุแต่มีหลายหลักสูตร → `409` | ไม่มีใน [SRS-M] (SPEC GAP) | Implemented | `services/monitoring_service.py`; `test_engine_and_api.py` |
| FR-07 | N/A เกิดเฉพาะเมื่อ config มี `naEnabled: true` และไม่มีข้อมูลที่ต้องตรวจ | [SRS-M] §24 | Implemented | `engine.py` `_no_subjects`; PS-08 test |
| FR-08 | Missing Information สร้างจาก configuration + ข้อมูลจริง | [SRS-M] §26 | Implemented | `engine.py`, `subject_checks.py` |
| FR-09 | Traceability: record ที่อ่าน, field ที่ใช้ และค่าจริง | [SRS-M] §29, §55 | Implemented | `context.py`; `test_ps_evaluation.py` |
| FR-10 | Verification | [SRS-M] §27; การกดยืนยัน: เจ้าของ project 2026-09-26 | Implemented: `found` = จำนวน record ที่อ่าน · ผู้ใช้กด "ยืนยันหลักฐาน / ผลการตรวจ" ในหน้ารายละเอียด PS → `POST /api/monitor/ps/{psCode}/verification` → บันทึกใน collection ของ Monitor `monitoring_results` (`{curriculumId, psCode, verification: {verified: true, verifiedAt}}`, key ไม่ซ้ำ curriculumId + psCode, กดซ้ำไม่สร้างรายการซ้ำ เวลาครั้งแรกคงเดิม) → `GET` เดิมอ่าน `verification.verified` / `verifiedAt` กลับมา (reload หรือ restart ยังอยู่) · ยืนยันทั้งหลักฐานที่แสดง (SET 3) และผล PS (เจ้าของ project 2026-09-26) · `approved` คงเป็น `null` · ไม่เปลี่ยนสถานะ PS, evidence, traceability, Programme / Generation Readiness และ PS-03 · ไม่มี Monitor store → `verified: null` | `engine.py`, `services/monitoring_service.py`, `repositories/monitoring_results.py`, `adapters/monitoring_results.py`; `test_verification.py`, `test_backend_parity.py`, `verification.test.jsx` |
| FR-11 | Evidence Reference จากข้อมูลจริง | [SRS-M] §28, §39 | Implemented: อ่านจาก `documents` ของหลักสูตรที่ตรวจ (`documents.curriculumId = curricula._id`) แบบอ่านอย่างเดียว · ต่อเอกสาร `{label: fileName, reference: _id, storage: originalFile.storage, path: originalFile.path}` (ค่าที่ไม่มีเป็น `null`) · ทุก PS ของหลักสูตรได้รายการเดียวกัน เพราะไม่มี field ที่เชื่อมเอกสารกับ PS รายตัว (เจ้าของ project ตัดสินใจ 2026-09-26) · ไม่มีเอกสาร → `[]` · อ่าน `documents` ไม่ได้ → `503` · ไม่ใช่ traceability และไม่เปลี่ยนสถานะ | `services/evidence.py`, `services/monitoring_service.py`; `test_evidence.py`, `test_backend_parity.py`, `evidence.test.jsx` |
| FR-12 | Dashboard แสดงรายการ PS จาก configuration | [SRS-M] §11, §17 | Implemented แบบมีข้อยกเว้น: การ์ดใช้ผลจาก API และมีรายการ PS-01..PS-09 ใน frontend เป็นรายการหลัก | `pages/Monitor/cardList.js`, `app/psGuideline.js` |
| FR-13 | ข้อความ requirement มาจาก configuration | [SRS-M] §12, §31 | Implemented แบบมีข้อยกเว้น: ใช้ข้อความจาก API ก่อน ถ้า API ไม่ส่งจึงใช้ข้อความที่ล็อกไว้ | `app/psTitles.js` (เจ้าของ project ตัดสินใจ 2026-09-25) |
| FR-14 | Frontend ไม่ประเมินผลและไม่เปลี่ยนสถานะ | [SRS-M] §16, §20 | Implemented | `api/adapter.js`; frontend tests |
| FR-15 | อ่านผลใหม่อัตโนมัติทุก 10 วินาทีขณะเปิดหน้า | ไม่มีใน [SRS-M] (เจ้าของ project สั่ง) | Implemented | `api/useRemote.js` (`RETRY_MS`) |
| FR-16 | เปลี่ยน configuration หรือข้อมูลแล้ว ผลเปลี่ยนในการตรวจครั้งถัดไป | [SRS-M] §42, §43 | Implemented (ไม่มี cache ของ config/data) | `services/monitoring_service.py`; `test_engine_and_api.py` |
| FR-17 | บันทึกผลที่ผู้ตรวจเลือกสำหรับเกณฑ์ที่ต้องให้ผู้ใช้ตรวจ | config PS-03; การเก็บ / การไม่ override: เจ้าของ project 2026-09-26 | Implemented: ผู้ตรวจเลือก PASS / FAIL / REVIEW (ตัวเลือกจาก `config.review.allowManualResult`) ในหน้ารายละเอียด PS-03 → `POST /api/monitor/ps/{psCode}/review` (body `{status}`) → `monitoring_results` เอกสารเดียวกับ verification (`review: {status, reviewedAt}` เวลาของ server, บันทึกซ้ำแก้เอกสารเดิม) → `GET` อ่าน `review` กลับ (refresh / restart ยังอยู่) · เปิดเฉพาะ PS ที่ config มี `review.required` + `review.reviewByUser` (config ACTIVE: PS-03) · **ไม่ override:** `status` ยังเป็นของ engine (REVIEW) และ Programme / Generation Readiness ไม่อ่านผลนี้ (เจ้าของ project 2026-09-26) · status ไม่อยู่ในตัวเลือก → `422` · PS ที่ไม่ได้ให้ผู้ใช้ตรวจ → `400` | `services/user_review.py`, `services/monitoring_service.py`, `repositories/monitoring_results.py`; `test_user_review.py`, `test_backend_parity.py`, `userReview.test.jsx` |
| FR-18 | Programme Readiness: `programmeReadiness` = จำนวน PS ที่เป็น PASS ÷ 9 × 100 (ทศนิยม 2 ตำแหน่ง) · นับเฉพาะ PASS (FAIL, REVIEW, N/A, ไม่มีผล ไม่นับ) · ตัวหาร 9 เสมอ; ไม่มีหลักสูตร → `null`; แยกจาก Generation Readiness (FR-21) | [FE-D]; สูตรจากเจ้าของ project 2026-09-26 | Implemented (backend คำนวณ, หน้าเว็บแสดงค่าจาก API) · `overallStatus` ยังเป็น `null` เสมอ | `models/schemas.py` (`ProgrammeReadiness`, `MonitorResponse.programme_readiness`); `test_programme_readiness.py`, `programmeReadiness.test.jsx` |
| FR-19 | เชื่อมต่อ External Service (Document Generation) | [SRS-M] §6; เจ้าของ project 2026-09-26 (pull, readiness-only) | Implemented: Document Generation เป็นฝ่าย **pull**: เรียก `GET /api/monitor?curriculumCode=…` แล้วอ่านเฉพาะ `generationReadiness.status` (`READY` / `NOT_READY` จาก SET 1; `null` = configuration ตัดสินไม่ได้) จากนั้นดึงข้อมูลที่ใช้ Generate จาก DB ของตัวเอง · Mornitor ไม่ push ไม่มี webhook / callback / outbound call ไม่ส่ง PS results, evidence, curriculum หรือ documents ให้ Generator และไม่สร้าง SAR (เจ้าของ project 2026-09-26) · ไม่มี endpoint ใหม่ (`GET /api/monitor` เดิมพอ) · adapter A / B ยังว่างเพราะไม่มี service ใดต้องใช้ | `api/routes/monitor.py`, `services/generation_readiness.py`, `adapters/external_services.py` (docstring); `test_generator_contract.py` |
| FR-20 | เก็บผลการตรวจถาวร (Persistent Monitoring Result) | [SRS-M] §8 (TBD); เจ้าของ project 2026-09-26 | Implemented: ผู้ใช้กด "บันทึกผลการตรวจของหลักสูตร" ในหน้าภาพรวม → `POST /api/monitor/results?curriculumCode=` → ประเมินใหม่ด้วย engine (เหมือน GET) แล้วเก็บ `result: {status, evaluatedAt}` ในเอกสาร `curriculumId + psCode` ของทุก PS ที่ active (bulk write ครั้งเดียว เวลาของ server) → `GET` อ่านกลับเป็น `persistedResult` · current state: บันทึกใหม่แทนค่าเดิม ไม่มีประวัติ และคงค่าเดิมเมื่อข้อมูลต้นทางเปลี่ยนจนกว่าจะบันทึกใหม่ · เก็บเฉพาะ status (ไม่เก็บ readiness / evidence / traceability) · ไม่ถูกส่งกลับเข้า engine และไม่มี readiness ใดอ่าน · ไม่ลบ `verification` / `review` (เจ้าของ project 2026-09-26) | `services/monitoring_service.py`, `repositories/monitoring_results.py`, `adapters/monitoring_results.py`; `test_persisted_results.py`, `test_backend_parity.py`, `persistedResults.test.jsx` |
| FR-21 | Generation Readiness: อ่านเอกสาร `configType: "generationReadiness"` จาก `ps_requirements` แล้วตัดสิน (กติกาเมื่อ `requiredAll: true`) `READY` (PS ทุกตัวใน `requiredPS` มี configuration ที่ active มีผล และอยู่ใน `allowedStatus`) / `NOT_READY` (มี PS ที่อยู่ใน `blockedStatus`, ไม่มี configuration ที่ active → `configuration_error`, หรือไม่มีผล → ปัญหาข้อมูล) พร้อม `blockingPS`; ไม่มีเอกสาร มีซ้ำ หรือผิดรูปแบบ → `status: null` + `issue` ไม่มีค่าเริ่มต้นใน code · กรณีที่ยังไม่มีกติกา (`requiredAll: false`, สถานะที่ไม่อยู่ในทั้งสองรายการ, key อื่น) ไม่ถูกตัดสินและรอเจ้าของ project ตัดสินใจ | เจ้าของ project 2026-09-26 (config `PS-Config-with-Generation-Readiness.json`) | Implemented (backend + `GET /api/monitor`; Document Generation อ่าน `status` แบบ pull (FR-19); หน้าเว็บยังไม่แสดง) | `services/generation_readiness.py`, `repositories/configuration.py`; `test_generation_readiness.py`, `test_backend_parity.py` |

### กติกาที่ใช้กับทุก PS (Current Implementation)

- **Status:** `PASS` / `FAIL` / `REVIEW` / `N/A` ตาม map `config.result` ของแต่ละ PS
- **สถานะเมื่อตัดสินไม่ได้:** ใช้ `result.review` ถ้าไม่มีจึงใช้ `result.unknown` (`engine.py` `_undecided`)
- **เกณฑ์ที่ตรวจทีละบุคคล (PS-02, PS-05, PS-06, PS-07, PS-08):**
  - มีคนใด FAIL → FAIL
  - ทุกคน PASS → PASS
  - นอกนั้น → REVIEW
  - เกณฑ์อื่นรวมผลตามตารางของแต่ละ PS (PS-01 นับ, PS-03 ให้ผู้ใช้ตรวจ, PS-04 ทุก record ต้องครบ, PS-09 ใช้ record หลักสูตรเดียว)
- **`issue`:**
  - `configuration_error`: config ผิดรูปแบบ
  - `evaluation_error`: engine ล้มเหลวเฉพาะเกณฑ์นั้น และบันทึก log
  - `spec_gap`: config ขอสิ่งที่ spec ไม่ได้กำหนด
  - `null`: ผลมาจากข้อมูล
  - ถ้ามีหลายชนิด ลำดับที่รายงานคือ `configuration_error` > `evaluation_error` > `spec_gap`
- **`dataCompleteness`:** `incomplete` เมื่อ `missingInformation` ไม่ว่าง
- **ขอบเขตข้อมูล:** ทุก query ที่เลือก record หลักถูกจำกัดด้วยหลักสูตรที่ตรวจ (`appointments.curriculumId = curricula._id`)
- **`currentYear`:** ปีของเครื่อง server + `MORNITOR_YEAR_OFFSET` (ค่าเริ่มต้น 543 จึงได้ พ.ศ.)

---

## 7. PS-01 Requirements

**Requirement (config):** หลักสูตรต้องมีอาจารย์ผู้รับผิดชอบหลักสูตรอย่างน้อย 5 คน

**Configuration:**
- `targetCollection: appointments`
- `filter.role: programmeResponsible`
- `count: {field: personId, distinct: true}`
- `condition: >= 5`
- `naEnabled: false`

**Current Implementation:** นับ `personId` ที่ไม่ซ้ำของ appointments ในหลักสูตรที่ `role = programmeResponsible`

| ข้อมูล | ผล |
|---|---|
| นับได้ ≥ 5 | PASS |
| นับได้ < 5 (รวมกรณีไม่มี record) | FAIL |
| มี record ที่ไม่มี `personId` | REVIEW + `spec_gap` ("N record(s) lack personId; reviewCondition is prose…") |
| N/A | ไม่เกิด (`naEnabled: false`) |

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps01_*`), E2E บน test database

**ข้อจำกัด:**
- นับ appointment ทุก `status` เพราะ config ไม่มีตัวกรองสถานะ
- `reviewCondition` เป็นข้อความสำหรับแสดงเท่านั้น

## 8. PS-02 Requirements

**Requirement (config):** อาจารย์ผู้รับผิดชอบหลักสูตรต้องมีสถานะอาจารย์ประจำ

**Configuration:**
- `targetCollection: appointments`
- `responsibleRole: programmeResponsible`
- `permanentRole: programmeStaff`
- `matching: {sameCurriculum: true, samePerson: true}`
- `condition: {operator: EXISTS, field: programmeStaff}`
- `naEnabled: false`

**Current Implementation:** อาจารย์ผู้รับผิดชอบแต่ละคน (แยกตาม `curriculumId` + `personId`) ต้องมี appointment `role = programmeStaff` ที่ `curriculumId` และ `personId` เดียวกัน

| ข้อมูล | ผล |
|---|---|
| ทุกคนมี programmeStaff คู่กัน | PASS |
| มีคนที่ไม่มี | FAIL |
| มี record ผู้รับผิดชอบที่ไม่มี `personId` และไม่มีคนใด FAIL | REVIEW (missing "N appointments record(s) lack curriculumId, personId") |
| ไม่มีอาจารย์ผู้รับผิดชอบเลย | REVIEW (missing "no appointments record is selected, so nothing can be checked") |

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps02_*`)

**ข้อจำกัด:** ข้อความ "lack curriculumId, personId" ระบุ key ทุกตัวแม้ record จะขาดเพียงบางตัว

## 9. PS-03 Requirements

**Requirement (config):** อาจารย์ผู้รับผิดชอบหลักสูตรต้องไม่รับผิดชอบเกิน 1 หลักสูตร

**Configuration:**
- `targetCollection: appointments`
- `targetRole: programmeResponsible`
- `review: {required: true, reviewByUser: true, allowManualResult: [PASS, FAIL, REVIEW]}`
- `naEnabled: false`

**Current Implementation:** เป็นเกณฑ์ **User Review**

| ข้อมูล | ผล (`status`) |
|---|---|
| ทุกกรณี (รวมเมื่อผู้ตรวจบันทึกผลแล้ว) | REVIEW |

**ผลที่ผู้ตรวจเลือก (SET 5, เจ้าของ project 2026-09-26):**
- หน้ารายละเอียด PS-03 มีส่วน "ผลการตรวจของผู้ตรวจ (User Review)" ให้เลือก PASS / FAIL / REVIEW ตาม `allowManualResult` แล้วกด "บันทึกผลการตรวจ"
- `POST /api/monitor/ps/PS-03/review` → `monitoring_results` (`review: {status, reviewedAt}`) → `GET` ส่ง `review: {allowManualResult, status, reviewedAt}`
- **เก็บแยกจากผลการตรวจ:** `status` ยังเป็น REVIEW ของ engine, ผลที่เลือกไม่ถูกส่งเข้า `ManualResultSource` และ Programme / Generation Readiness ไม่อ่านผลนี้ (Generation Readiness จึงเป็น NOT_READY เพราะ PS-03 เป็น REVIEW เสมอ)

รายละเอียดของผล:
- `issue: null`, `dataCompleteness: complete`
- `reviewRequired: true`, `reviewByUser: true`
- `dataSummary` มี "Review by user required by configuration"
- `dataFound` แสดงชื่ออาจารย์ผู้รับผิดชอบ **ของหลักสูตรที่ตรวจเท่านั้น**
- engine มี port `ManualResultSource` ที่จะใช้ผลที่ผู้ตรวจเลือกเป็น `status` แต่ production ใช้ `NoManualResults` ตามการตัดสินใจ "ไม่ override" (ผลที่เลือกอยู่ใน `review` แทน)

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps03_*`), `test_issue_reporting.py`, `test_user_review.py`

**ข้อจำกัด:**
- ไม่ตรวจข้ามหลักสูตร เพราะ query จำกัดเฉพาะหลักสูตรที่ตรวจ (`capabilities.select_records`) และ config ไม่มี construct สำหรับนับข้ามหลักสูตร
- ถ้าจะตรวจอัตโนมัติ ต้องเปลี่ยน business rule ใน config (การตัดสินใจของเจ้าของ config)

## 10. PS-04 Requirements

**Requirement (config):** หลักสูตรต้องมีคำสั่งแต่งตั้งและระบุบทบาทการบริหารหลักสูตรอย่างชัดเจน

**Configuration:**
- `targetCollection: appointments`
- `requiredFields: [personId, role, roleName, appointmentOrder]`
- `appointmentOrder: {required: true, requiredFields: [orderNumber, orderDate]}`
- `role: {required: true, roleNameRequired: true}`
- `conditions` เป็นข้อความ
- `naEnabled: false`

**Current Implementation:** appointment **ทุก record** ของหลักสูตร (ทุก role) ต้องมีค่าไม่ว่างครบใน `personId`, `role`, `roleName`, `appointmentOrder`, `appointmentOrder.orderNumber` และ `appointmentOrder.orderDate`

| ข้อมูล | ผล |
|---|---|
| ครบทุก record | PASS |
| record ใดขาด field ใด | FAIL + missing "<ชื่อ (id)>: <field>" หนึ่งบรรทัดต่อ field |
| ไม่มี appointment เลย | FAIL + missing "no appointments records were found" |
| REVIEW จากข้อมูล | ไม่เกิด (`conditions.review` เป็นข้อความเท่านั้น) |

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps04_*`)

## 11. PS-05 Requirements

**Requirement (config):** อาจารย์ผู้รับผิดชอบหลักสูตรต้องมีคุณวุฒิสูงสุดอย่างน้อยระดับปริญญาโท

**Configuration:**
- `targetCollection: educations`
- `appointment.role: programmeResponsible`
- `join: appointments.personId → educations.personId`
- `degree: {field: degree, minimum: master, ordering: [bachelor, master, Ph.D.], aliases, normalization}`
  - `aliases: {bachelor: [วท.บ., บธ.บ., วบ.บ.], master: [วท.ม.], Ph.D.: [ปร.ด.]}` (เจ้าของ project 2026-09-27 จากข้อมูลจริง)
  - `normalization: {enabled: true, remove: [" ", "."], caseInsensitive: true}`
- `naEnabled: false`

**Current Implementation:**
- ต่ออาจารย์ผู้รับผิดชอบแต่ละคน อ่าน `educations.degree` ทุกรายการของคนนั้น
- ค่าหนึ่งมีตำแหน่งในลำดับเมื่อ**หลัง normalization** ตรงกับค่าใน `ordering` หรือกับ alias ของค่านั้น แล้วใช้ตำแหน่งที่สูงสุด
- ตัวอย่างที่ได้ตำแหน่ง: `ปร. ด.`, `วท.บ`, `PhD.`, `Master` เพราะไม่นับช่องว่าง จุด และตัวพิมพ์
- ค่าที่ config ไม่ได้ให้ไว้ ระบบไม่เดา
- ข้อความผลใน `dataFound` บอกทุกค่าที่อ่านและค่าในลำดับที่มันแทน เช่น `degree: ปร.ด. → Ph.D.; วท.บ. → bachelor (highest 'Ph.D.' is at least 'master') -> PASS` หรือ `at → not in the ordering`

| ข้อมูลของอาจารย์หนึ่งคน | ผล |
|---|---|
| มีค่าที่ได้ตำแหน่ง ≥ master (`master` / `วท.ม.` / `Ph.D.` / `ปร.ด.` …) แม้จะมีค่าอื่นที่อ่านไม่ได้ปนอยู่ | PASS |
| ทุกค่าได้ตำแหน่งและต่ำกว่า master (`bachelor` / `วท.บ.` / `บธ.บ.` / `วบ.บ.`) | FAIL |
| มีค่าที่ไม่ได้ตำแหน่ง (เช่น `Diploma`, `วศ.ม.`, `at`) และไม่มีค่าที่ ≥ master | REVIEW + missing "degree value(s) not in the configured ordering: …" (ค่าที่อ่านไม่ได้อาจสูงกว่า จึงไม่ตัดสินเป็น FAIL) |
| ไม่มี education หรือ degree ว่าง | REVIEW + missing "no usable degree value" |
| ไม่มีอาจารย์ผู้รับผิดชอบ | REVIEW + missing |

- **ผลของหลักสูตร:** รวมตามกติกาใน §6 และ `issue` เป็น `null` ในทุกกรณีข้างต้น
- **config ที่ผิด → REVIEW + `configuration_error`:**
  - `minimum` ไม่อยู่ใน `ordering`
  - `ordering` ไม่ใช่ list ของข้อความที่ไม่ซ้ำ
  - alias ชี้ค่าที่ไม่อยู่ใน `ordering`
  - รูปเขียนหนึ่งชี้ได้มากกว่า 1 ค่าหลัง normalization
  - รูปเขียนว่างหลัง normalization
  - `aliases` / `normalization` ผิดรูปแบบ
- **config ที่ใช้ไม่ได้ → REVIEW + SPEC GAP:** มี `aliases` / `normalization` แต่ไม่มี `ordering`

**หลักฐาน:**
- `test_ps_evaluation.py` (`test_ps05_*`)
- `test_degree_and_year_forms.py` (กรณีของเจ้าของ project, รูปเขียนต่าง ๆ, config ผิด)
- ตรวจกับข้อมูลจริงของ `aunqa_ps` (2026-09-27): Rule Engine = API = DB oracle → PASS 5/5 คนเมื่อใช้ config ACTIVE (`test_ps05_on_the_real_data_of_the_curriculum` อ่าน export ใน `DB-DATA/`)

**ข้อจำกัด:**
- รูปเขียนอื่นที่เจ้าของ config ไม่ได้ให้ (เช่น `วศ.ม.`, `วศ.บ.`, `สท.บ`, "ปริญญาโท", "M.Sc.") ไม่ได้ตำแหน่งจนกว่าจะเพิ่มใน `aliases`
- `ps_requirements` ใน database จริงต้องมี `aliases` / `normalization` ก่อน ผลจริงจึงจะเปลี่ยน (Mornitor ไม่เขียน configuration)

## 12. PS-06 Requirements

**Requirement (config):** คุณวุฒิของอาจารย์สัมพันธ์กับสาขาของหลักสูตร

**การตัดสิน:** User Confirmation 100% (อาจารย์ยืนยัน 2026-09-29) — ระบบ**ไม่**ตัดสินเองว่าคุณวุฒิสัมพันธ์กับหลักสูตรหรือไม่ ไม่เทียบชื่อสาขา ไม่มี mapping ของ Major ผู้ใช้เป็นผู้ยืนยัน

**Configuration:**
- `targetCollection: educations`
- `appointment.role: programmeResponsible`
- `join` ด้วย `personId` (+ `curriculumId`)
- ข้อมูลที่ผู้ตรวจเห็น (ไม่มี `condition` จึงไม่ตัดสิน): `qualification.source: educations.degree`, `qualificationField.source: educations.field`, `institution.source: educations.institution` (ทั้งสาม `required: true`)
- `review: {required: true, reviewByUser: true, allowManualResult: [PASS, FAIL]}`
- `result: {pass: PASS, fail: FAIL, review: REVIEW, na: N/A}` · `naEnabled: false`

**Current Implementation:**
1. engine เลือกอาจารย์ `programmeResponsible` ของหลักสูตร join `educations` ด้วย `personId` แล้วส่งให้ผู้ตรวจเห็นทีละคน: ระดับคุณวุฒิ สาขาวิชา สถาบัน (`dataFound`) — ไม่มีการเปรียบเทียบใด
2. `status` ของ engine เป็น `result.review` (REVIEW) เสมอ — `review` + `join` ที่มี check ตัดสินได้ (มี `condition`, นับ, ordering) เป็น `spec_gap`
3. ผู้ใช้ยืนยันในหน้ารายละเอียด ("มีความสัมพันธ์" = PASS / "ไม่มีความสัมพันธ์" = FAIL) → `POST /api/monitor/ps/PS-06/review` → `monitoring_results.review`
4. สถานะที่แสดง (`resolveStatus`) และ Programme / Generation Readiness (`readiness_status()`) ใช้ผลที่ผู้ใช้ยืนยัน ส่วน `status` และ `result` ที่บันทึก (Persistent Monitoring Result) ยังเป็น REVIEW

| ข้อมูล | ผล engine (`status`) | สถานะที่แสดง / readiness |
|---|---|---|
| ยังไม่ยืนยัน | REVIEW | REVIEW (block Generation Readiness) |
| ผู้ใช้ยืนยัน "มีความสัมพันธ์" | REVIEW | PASS |
| ผู้ใช้ยืนยัน "ไม่มีความสัมพันธ์" | REVIEW | FAIL (block Generation Readiness) |
| อาจารย์ไม่มี education / ไม่มีสาขาวิชา / ไม่มีสถาบัน | REVIEW + missing ("<ชื่อ>: no value found for review"), `issue: null` | ตามที่ผู้ใช้ยืนยัน |
| ไม่มีอาจารย์ผู้รับผิดชอบ | REVIEW + missing, `issue: null` | ตามที่ผู้ใช้ยืนยัน |
| config เดิมแบบ mapping ยังอยู่ใน database | REVIEW + `spec_gap` (engine ไม่มี mapping แล้ว) | REVIEW |

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps06_*`), `test_ps06_user_confirmation.py`, `frontend/src/test/ps06Confirmation.test.jsx`

**ข้อจำกัด:** อาจารย์ที่มีหลายวุฒิแสดงระดับคุณวุฒิ สาขา และสถาบันเป็นรายการของแต่ละ field (ไม่จับคู่ทีละวุฒิ) · ผู้ใช้ยืนยันหนึ่งครั้งต่อหลักสูตร ไม่ใช่รายบุคคล

## 13. PS-07 Requirements

**Requirement (config):** อาจารย์ผู้รับผิดชอบหรืออาจารย์ประจำหลักสูตรต้องมีผลงานวิชาการย้อนหลัง 5 ปี

**Configuration:**
- `targetCollections: [academic_works, appointments]`
- `targetRoles: [programmeResponsible, programmeStaff]`
- `join: appointments.personId → academic_works.personId`
- `publicationYear: {field: publicationYear, period: previous5Years}`
- `minimumCount: 1`
- `naEnabled: false`

**Current Implementation:** ต่อ `personId` ที่ไม่ซ้ำของผู้รับผิดชอบหรืออาจารย์ประจำ นับผลงานที่ `publicationYear` อยู่ในช่วง `currentYear − 5` ถึง `currentYear` (รวมทั้งสองปลาย เช่น 2564–2569 เมื่อ currentYear = 2569)

**ปีที่ใช้ได้** (เจ้าของ project 2026-09-27 จากข้อมูลจริงที่มีทั้ง ค.ศ. และ พ.ศ.):
1. ค่าต้องเป็นจำนวนเต็ม หรือข้อความที่เป็นตัวเลขล้วน ไม่นับช่องว่างหัวท้าย (เช่น `"2567"`, `" 2025 "`)
   - ค่าอื่นเป็นปีที่ใช้ไม่ได้และไม่ถูกนับ: `null`, ไม่มี field, ข้อความอื่น, ทศนิยม, boolean
2. แปลงเป็นปฏิทินของ `currentYear` ก่อนเทียบช่วง ตามค่า `MORNITOR_YEAR_OFFSET` (ค่าเริ่มต้น 543)
   - ปีที่ไม่เกินปี ค.ศ. ปัจจุบันของเครื่อง ถือเป็น ค.ศ. และบวก offset (2022–2026 → 2565–2569)
   - ปีอื่นใช้ตามเดิม (2564–2569 คงเดิม; 2027 และ 2570 อยู่นอกช่วง)
   - ถ้า offset = 0 (ข้อมูลเป็น ค.ศ.) ไม่แปลง
   - ตัวเลข 543 หรือช่วงปีไม่ได้ฝังใน code ของ engine (`app/references/runtime.py` `in_anchor_calendar`)

| ข้อมูล | ผล |
|---|---|
| ≥ 1 ผลงานในช่วง (หลังแปลงปี) | PASS |
| 0 ในช่วง และทุกผลงานมีปีที่ใช้ได้ (หรือไม่มีผลงาน) | FAIL |
| 0 ในช่วง และมีผลงานที่ไม่มีปีที่ใช้ได้ | REVIEW + missing "N record(s) lack a usable publicationYear" |
| ไม่มีอาจารย์เลย | REVIEW + missing |

**หลักฐาน:**
- `test_ps_evaluation.py` (`test_ps07_*`)
- `test_degree_and_year_forms.py` (ปี พ.ศ. / ค.ศ. / ข้อความ / ค่าที่ไม่ใช่ปี)
- `test_generic_capabilities.py` (time window)
- ตรวจกับข้อมูลจริงของ `aunqa_ps` (2026-09-27): Rule Engine = API = DB oracle → PASS 13/13 คน

**ข้อจำกัด:**
- `workType`, `database`, `quartile` ไม่ถูกใช้ เพราะ config ไม่ได้กำหนด
- การแปลงปฏิทินใช้เฉพาะช่วงเวลาของ PS-07 (ไม่ใช้กับ `curriculumYear` ของ PS-09)

## 14. PS-08 Requirements

**Requirement (config):** อาจารย์พิเศษต้องมีคุณวุฒิและประสบการณ์ที่เหมาะสม

**Configuration:**
- `targetRole: specialInstructor`
- `join` ด้วย `personId`
- `qualification: {source: educations.degree, required: true, condition: {operator: EXISTS}}`
- `experience: {source: persons.hasTeachingExperience, required: true, condition: {operator: "==", value: true}}`
- `naEnabled: true`
- `conditions` เป็นข้อความ

**Current Implementation (business rule ของเจ้าของ project 2026-09-25):** ตรวจแค่ "มีคุณวุฒิ" และ "มีประสบการณ์สอนหรือไม่" ไม่ตรวจจำนวนปี ประเภท หรือความเกี่ยวข้องของประสบการณ์

| ข้อมูลของอาจารย์พิเศษหนึ่งคน | qualification | experience |
|---|---|---|
| ไม่มี record `educations` เลย | FAIL | — |
| มี record แต่ `degree` ว่าง | REVIEW (missing "qualification: no value found for review") | — |
| มี `degree` ค่าใดก็ได้ | PASS (ไม่ประเมินระดับ) | — |
| `hasTeachingExperience = true` | — | PASS |
| `hasTeachingExperience = false` | — | FAIL |
| ไม่มีค่า / `null` | — | REVIEW (missing "experience: no value found for review") |
| ไม่ใช่ Boolean | — | REVIEW (missing "… cannot be compared with true") |

- ผลของคนหนึ่งและผลรวมทุกคนใช้กติกาใน §6
- ไม่มีอาจารย์พิเศษ → **N/A**
- `persons` เข้าถึงผ่าน `appointments.personId → persons._id` ไม่มี field `persons.personId`

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps08_*`), `test_generic_capabilities.py`, API verification 6 กรณีบน test database

**ข้อจำกัด:**
- ไฟล์ของเจ้าของ config ยังมี `join.experiencePersonId: "persons.personId"` และไม่มี `condition` ดู [PS-Config.json](PS-Config.json) `differencesFromOwnerFile`
- ถ้าใช้ config ที่ไม่มี `condition` เกณฑ์นี้จะกลับเป็นแบบให้ผู้ตรวจตัดสิน (REVIEW)

## 15. PS-09 Requirements

**Requirement (config):** หลักสูตรต้องมีการปรับปรุงล่าสุดไม่เกิน 5 ปี

**Configuration:**
- `targetCollection: curricula`
- `year.field: curriculumYear`
- `calculation.formula: currentYear - curriculumYear`
- `comparison: <= 5, reference currentYear`
- `naEnabled: false`

**Current Implementation:**

| ข้อมูล | ผล |
|---|---|
| `curriculumYear` เป็นจำนวนเต็ม และ `currentYear − curriculumYear ≤ 5` | PASS |
| มากกว่า 5 | FAIL |
| ไม่มีค่า หรือไม่ใช่จำนวนเต็ม (เช่น `"2567"`) | REVIEW + missing "<รหัสหลักสูตร>: curriculumYear is missing or not an integer" |

**หลักฐาน:** `test_ps_evaluation.py` (`test_ps09_*`)

**ข้อจำกัด:** ถ้าตั้ง `MORNITOR_YEAR_OFFSET` ไม่ตรงกับปฏิทินของข้อมูล ผลจะผิด

---

## 16. Monitoring Dashboard Requirements

**Intended Scope** ([SRS-M] §17–18): Dashboard แสดงรายการ PS ที่ active จาก configuration การ์ดแต่ละใบมี PS Code, Requirement, Status, Data Summary และ Missing Information

**Current Implementation** (`/monitor/ps`, `pages/Monitor/MonitorPage.jsx`):

1. **หัวหน้า:**
   - "AUNQA", "Programme Standards" และคำอธิบาย (จาก `criteriaGroups.js`)
   - บรรทัด "อัปเดตอัตโนมัติทุก 10 วินาที · ตรวจสอบล่าสุด …"
2. **สถานะของหน้า:**
   - กำลังโหลด
   - ไม่สามารถโหลดได้ (ลองใหม่ทุก 10 วินาที)
   - `409` แสดง "พบหลายหลักสูตรในฐานข้อมูล" และ "กรุณาระบุ curriculumCode ใน URL"
   - ไม่มีข้อมูล (รอข้อมูลอัตโนมัติ)
   - "ข้อมูลยังไม่ครบถ้วน" เมื่อ API ส่ง `dataCompleteness: incomplete`
3. **ข้อมูลหลักสูตร:** `curriculum` จาก API
4. **ความพร้อมของหลักสูตร:**
   - ความพร้อมแสดง `programmeReadiness.percentage` + "%" และ "PASS <passCount> จาก <totalPS> เกณฑ์" จาก API (ไม่มีค่า → "—"; frontend ไม่คำนวณ)
   - ผลรวมแสดง `overallStatus` เมื่อ API ส่งมา (ปัจจุบันเป็น `null` จึงแสดง "—")
   - จำนวนต่อสถานะนับจาก `results`
5. **การ์ด PS-01 ถึง PS-09 ครบเสมอ:**
   - ถ้า API ส่งผลมา แสดงสถานะ ป้าย issue ข้อความผล "สิ่งที่ระบบตรวจพบ" และลิงก์รายละเอียด
   - ถ้า API ไม่มีผลของ PS นั้น แสดง "—" และไม่มีสถานะ
   - ถ้า database ว่าง แสดง "กำลังรอข้อมูล" / "รอผู้ใช้อัปโหลดข้อมูล"
6. **สถานะหลักฐาน:** "พบหลักฐาน" นับเอกสารไม่ซ้ำตาม `reference` (เอกสารเดียวกันอยู่ในทุก PS) ส่วน ตรวจสอบแล้ว / รอการตรวจสอบ นับจำนวน PS ที่ `verified` เป็น `true` / `false` (ไม่มี Monitor store → "—")
7. **ข้อมูลที่ยังขาด:** แยกตาม PS แสดงสูงสุด 3 บรรทัดต่อ PS แปลงเป็นภาษาไทยด้วย `missingText.js` ข้อความที่ไม่มีแม่แบบจะแสดง "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด"
8. **ความครบถ้วนของข้อมูล:** ภาพรวมและจำนวนเกณฑ์ที่ข้อมูลครบ / ไม่ครบ
9. **ผลการตรวจที่บันทึกไว้ (SET 6):** ตาราง PS · ผลที่บันทึก (`persistedResult.status`, "ยังไม่ได้บันทึก" เมื่อ `null`) · บันทึกเมื่อ (`evaluatedAt`) และปุ่ม "บันทึกผลการตรวจของหลักสูตร" → `POST /api/monitor/results` → อ่านซ้ำด้วย `GET` · ผิดพลาด → "บันทึกผลการตรวจไม่สำเร็จ กรุณาลองใหม่" · ไม่คำนวณอะไรจากค่าที่บันทึก

**ข้อยกเว้นต่อ [SRS-M] §11, §12, §31, §32** (เจ้าของ project ตัดสินใจ):
- `psGuideline.js` มีรายการ PS code
- `psTitles.js` มีข้อความ requirement สำรอง ใช้เฉพาะเมื่อ API ไม่ส่ง requirement

**Not Implemented จาก [FE-D]:**
- ชื่อเกณฑ์ภาษาไทยที่ไม่มีใน config
- หมวดของ Missing Information
- ปุ่มกำหนด N/A

**หน้าอื่น:**
- หน้าแรก `/` มีการ์ด P1 P2 P3 P4 P8 PS
- P1 P2 P3 P4 P8 ยังไม่มี configuration จึงแสดงหน้าแจ้งขอบเขต
- แถบบนมี "AUN-QA" และลิงก์ PS-01..PS-09 (แสดงเมื่ออยู่ในส่วน PS)

## 17. PS Detail Requirements

**Intended Scope** ([SRS-M] §19): Requirement, Status, สิ่งที่ต้องตรวจสอบ, Data Found, Verification, Missing Information, Evidence, Traceability

**Current Implementation** (`/monitor/ps/:psCode`, `pages/PSDetail/PSDetailPage.jsx`) มี 11 ส่วน:

| ส่วน | ที่มาของข้อมูล |
|---|---|
| หัว (PS code, ลิงก์กลับ) | URL |
| สิ่งที่เกณฑ์ต้องการ | `requirement` จาก API หรือข้อความสำรอง |
| ผลการตรวจสอบ | `status`, `issue`, จำนวนข้อมูลที่ขาด |
| ทำไมจึงได้ผลนี้ | ข้อความคงที่ตาม `status` / `issue` / label ของ `dataSummary` |
| เกณฑ์นี้ตรวจสอบอะไร | ข้อความจาก requirement และชื่อแหล่งข้อมูลจาก `traceability` |
| เงื่อนไขที่ใช้ตัดสิน | `dataSummary` label `Condition` (เฉพาะรูปแบบ "<operator> <ตัวเลข>") |
| สิ่งที่ระบบตรวจพบ | `verification.found`, `dataSummary`, ชื่อจาก `dataFound` |
| ผลการตรวจของผู้ตรวจ (User Review) — เฉพาะ PS ที่ API ส่ง `review` (PS-03) | `review.allowManualResult` เป็นตัวเลือก, `review.status` / `reviewedAt` เป็นผลที่บันทึก ("ยังไม่มีผลการตรวจของผู้ตรวจ" เมื่อ `null`) · ปุ่ม "บันทึกผลการตรวจ" → `POST` → อ่านซ้ำด้วย `GET` · ผลที่เลือกแต่ยังไม่บันทึกอยู่ในหน้าเท่านั้น · ผิดพลาด → "บันทึกผลการตรวจไม่สำเร็จ กรุณาลองใหม่" และผลเดิมคงอยู่ |
| การยืนยันข้อมูล | `verification.found` / `verified` / `verifiedAt` ("ยืนยันเมื่อ") / `approved` (`null` → "—") · ปุ่ม "ยืนยันหลักฐาน / ผลการตรวจ" เมื่อ API ส่ง `verified: false` → `POST` → อ่านซ้ำด้วย `GET` · "ใช่" แสดงเมื่อ `GET` ตอบ `true` เท่านั้น · ผิดพลาด → "บันทึกการยืนยันไม่สำเร็จ กรุณาลองใหม่" · กดซ้ำระหว่างบันทึกส่งครั้งเดียว |
| ยังขาดข้อมูลสำหรับตรวจสอบ | `missingInformation` ทุกบรรทัดผ่าน `missingText.js` |
| หลักฐานที่ใช้ประกอบการตรวจสอบ | `evidence`: ชื่อไฟล์ — รหัสอ้างอิง, "ที่เก็บไฟล์ต้นฉบับ" (`storage`) และ "ตำแหน่งไฟล์ต้นฉบับ" (`path`); ค่า `null` → "ไม่พบข้อมูล storage / path"; ว่าง → "ยังไม่มีข้อมูลหลักฐาน" |
| แหล่งที่มาของข้อมูล | `traceability`: แหล่งข้อมูล, รหัสอ้างอิง (ObjectId), ชื่อ field ภาษาไทย (10 แถวแรก ที่เหลืออยู่ใน "แสดงทั้งหมด") |

**พฤติกรรมเพิ่มเติม:**
- API ตอบ `404` → แสดงทุกส่วนเป็น "กำลังรอข้อมูล" และไม่มีสถานะ
- `409` → ข้อความหลายหลักสูตร
- อ่านใหม่ทุก 10 วินาที

**ข้อมูลที่ API ส่งแต่หน้าเว็บไม่แสดง:**
- `checks`
- `reviewRequired`, `reviewByUser`
- `traceability[].values`

## 18. API Requirements

**Intended Scope** ([SRS-M] §46–47): API ส่ง configuration-derived information, evaluation result, data summary, missing information, verification, evidence และ traceability โดย endpoint และ method เป็น `TBD / SPEC GAP` และ controller ห้ามมี business configuration

**Current Implementation:** ดูรายละเอียดใน [API.md](API.md)
- `GET /api/monitor[?curriculumCode=]` และ `GET /api/monitor/ps/{ps_code}[?curriculumCode=]`
- `POST /api/monitor/ps/{ps_code}/verification[?curriculumCode=]` บันทึกการยืนยันใน `monitoring_results` เท่านั้น
- `POST /api/monitor/ps/{ps_code}/review[?curriculumCode=]` (body `{status}`) บันทึกผลที่ผู้ตรวจเลือกใน `monitoring_results` เท่านั้น
- `POST /api/monitor/results[?curriculumCode=]` บันทึกสถานะปัจจุบันของทุก PS ใน `monitoring_results` เท่านั้น
- ทุก endpoint ส่ง JSON แบบ camelCase; endpoint `GET` อ่านอย่างเดียว
- FastAPI เปิด `/docs`, `/redoc`, `/openapi.json` โดยอัตโนมัติ
- route handler เรียก `MonitoringService` เท่านั้น (`test_architecture.py`)

**Not Implemented:**
- endpoint รายชื่อหลักสูตร
- endpoint configuration
- endpoint สุขภาพระบบ (health)

## 19. Data Requirements

ดูรายละเอียดใน [Data-Schema.md](Data-Schema.md) สรุป:
- **collection ที่ config ACTIVE อ่านจริง:** `curricula`, `appointments`, `educations`, `academic_works`, `persons` และ `ps_requirements`
- **ประกาศใน Data Schema แต่ config ACTIVE ไม่อ่าน:** `documents`, `data_usages`, `generated_documents`
- **ทุก field ที่ config อ้างถึงต้องประกาศใน `backend/app/models/source_schema.py`** มิฉะนั้นเป็น SPEC GAP
- **ปีเก็บเป็น พ.ศ. แบบจำนวนเต็ม** ตามตัวอย่างใน [DS]
- **ความสัมพันธ์:** `personId → persons._id`, `curriculumId → curricula._id`

## 20. Error Handling

**Intended Scope** ([SRS-M] §48–50): แยก Configuration Error, Data Source Error, Connection Error, Evaluation Error, System Error โดย code และข้อความเป็น `TBD` ถ้าเชื่อมต่อไม่ได้ต้องไม่เป็น FAIL

| สถานการณ์ | Current Implementation |
|---|---|
| อ่าน MongoDB ไม่ได้ (`PyMongoError`) | API `503` `{"detail": "Unable to load monitoring data"}` ไม่ใช่ FAIL · หน้าเว็บแสดง "ไม่สามารถโหลดข้อมูลการตรวจสอบได้" และลองใหม่ทุก 10 วินาที |
| config ของ PS หนึ่งผิดรูปแบบ | เฉพาะ PS นั้นเป็น REVIEW + `configuration_error` และบรรทัด "Configuration error: …" · PS อื่นทำงานปกติ |
| config ขอสิ่งที่ spec ไม่กำหนด | REVIEW + `spec_gap` และบรรทัด "SPEC GAP: …" |
| engine ล้มเหลวที่ PS หนึ่ง (exception ที่ไม่คาดคิด) | เฉพาะ PS นั้นเป็น REVIEW + `evaluation_error` · log ERROR `[evaluation_error]` พร้อม traceback |
| หลายหลักสูตรแต่ไม่ระบุ `curriculumCode` | `409` พร้อม `detail` ที่ขึ้นต้นด้วย "SPEC GAP: …" |
| PS ไม่มีหรือไม่ active หรือไม่มีหลักสูตร (endpoint รายละเอียด) | `404` `{"detail": "No monitoring result"}` |
| เอกสาร Generation Readiness ไม่มี / มีซ้ำ / ผิดรูปแบบ | `generationReadiness.status: null` + `issue` (`configuration_error` / `spec_gap`) + `detail` · ผล PS ไม่เปลี่ยน · API ยังตอบ `200` |
| บันทึกการยืนยันไม่ได้ (`monitoring_results` อ่าน/เขียนไม่ได้ หรือไม่มี Monitor store) | `POST` ตอบ `503` `{"detail": "Unable to save the verification"}` ไม่บันทึกอะไร ผล PS ไม่เปลี่ยน · หน้าเว็บแสดง "บันทึกการยืนยันไม่สำเร็จ กรุณาลองใหม่" |
| บันทึกผลของผู้ตรวจ: status ไม่อยู่ใน `allowManualResult` / ไม่มี body / ไม่ใช่ข้อความ · PS ที่ไม่ได้ให้ผู้ใช้ตรวจ · บันทึกไม่ได้ | `422` · `400` · `503` `{"detail": "Unable to save the review"}` — ไม่บันทึกอะไรและผลเดิมคงอยู่ |
| บันทึกผลการตรวจ: อ่านข้อมูลไม่ได้ระหว่างประเมิน / เขียน `monitoring_results` ไม่ได้ | `503` `{"detail": "Unable to save the monitoring result"}` · ประเมินครบก่อนเขียน จึงไม่เขียนเลยเมื่ออ่านไม่ได้ · MongoDB แบบ standalone ไม่มี transaction ถ้าการเชื่อมต่อหลุดระหว่าง bulk write อาจเขียนได้บางส่วน |
| exception อื่นที่ไม่มี route จัดการ | `500` "Internal Server Error" (plain text เหมือน default เดิม ไม่มี traceback ใน response) · log ERROR `[system_error]` พร้อม method + path และ traceback (`main.py` middleware) |
| อ่าน / เขียน MongoDB ไม่ได้ | `503` เหมือนเดิม · log ERROR `[connection_error]` (ติดต่อ database ไม่ได้: pymongo `ConnectionFailure`) หรือ `[data_source_error]` (error อื่นของ driver) พร้อม operation, `curriculumCode` และ traceback |
| configuration ใช้ไม่ได้ (PS หรือ Generation Readiness) | ผลเหมือนเดิม (`200`) · log WARNING `[configuration_error]` |

## 21. Non-Functional Requirements

| หัวข้อ | Intended ([SRS-M]) | Current Implementation | หลักฐาน |
|---|---|---|---|
| อ่านอย่างเดียว | §7 | source / configuration ใช้แค่ `find`; เขียนได้เฉพาะ `adapters/monitoring_results.py` ลง `monitoring_results` (`test_engine_and_api.py`); CORS `GET`, `POST`; frontend ส่ง `POST` เฉพาะ `verifyPS` และ `reviewPS` | `adapters/mongo.py`, `main.py`, `api/client.js`; tests |
| ไม่ hard-code business | §30–32 | engine ไม่มีคำ business, ค่าจาก config หรือตัวเลขอื่นนอกจาก 0, 1, -1 (มีข้อยกเว้นฝั่ง frontend ตาม §16) | `test_architecture.py` |
| ทนต่อ config ผิดรูปแบบ | §48 | test สุ่ม 300 แบบยืนยันว่าไม่ล่ม | `test_robustness.py` |
| Performance | §52 (TBD) | ข้อมูลไม่เพียงพอ ไม่มีเป้าหมาย ไม่มี cache ทุก request อ่าน config และข้อมูลใหม่ | — |
| Scalability | §53 (TBD) | ข้อมูลไม่เพียงพอ | — |
| Security | §51 (TBD) | ไม่มี authentication / authorization; มีแค่ CORS | `main.py` |
| Logging | §54 (TBD); Error เท่านั้น: เจ้าของ project | Error Logging เท่านั้น (SET 8, เจ้าของ project 2026-09-26): Python `logging` handler เดียวบน logger `app` (stderr) · รูปแบบ `<เวลา> <LEVEL> <module> [<category>] <message>` + traceback สำหรับ error · ERROR: `data_source_error` / `connection_error` (ทุก `503` พร้อม operation และ `curriculumCode`), `evaluation_error` (engine ล้มเหลวที่ PS หนึ่ง), `system_error` (exception ที่ไม่มี route จัดการ → `500` "Internal Server Error" เหมือนเดิม) · WARNING: `configuration_error` (config ของ PS หรือ Generation Readiness ใช้ไม่ได้ request ยังตอบ `200`) · ไม่มี External Service Error เพราะไม่มี outbound call (SET 7) · ไม่ log ผล PASS / FAIL / REVIEW / N/A, request ปกติ, 4xx, header / cookie / body / query / เอกสาร · ซ่อน user:password ใน URL · ไม่มี collection ของ log และไม่ส่งออกภายนอก | `app/error_log.py`; `test_error_logging.py` |
| Audit / Traceability | §55 | ทุกผลมี `traceability` | `context.py` |
| ภาษาและการแสดงผล | — | หน้าเว็บภาษาไทย, สถานะมีทั้งข้อความและไอคอน, grid 3 / 2 / 1 คอลัมน์ | `styles.css`; `responsive.test.js` |

## 22. Constraints

- **Runtime:**
  - Python 3.11 ขึ้นไป และ Node.js 20.19+ หรือ 22.12+ (ตาม `README.md`)
  - เครื่องที่จัดทำเอกสารใช้ Python 3.14.7 และ Node 26.8.1
  - ต้องมี MongoDB
- **ตัวแปรสภาพแวดล้อมฝั่ง backend** (`backend/app/settings.py`):
  - `MORNITOR_DB_URI`, `MORNITOR_DB_NAME`
  - `MORNITOR_CONFIG_DB_URI`, `MORNITOR_CONFIG_DB_NAME`
  - `MORNITOR_CORS_ORIGINS`
  - `MORNITOR_YEAR_OFFSET`
  - อ่านครั้งเดียวเมื่อสร้าง service (ต้อง restart จึงเปลี่ยน)
- **ตัวแปรฝั่ง frontend:**
  - `MORNITOR_API_TARGET` (proxy ของ dev / preview)
  - `VITE_API_BASE_URL` (ตอน build)
- **ข้อมูล:**
  - ตรวจได้ครั้งละ 1 หลักสูตร
  - ปีต้องอยู่ในปฏิทินเดียวกับ `MORNITOR_YEAR_OFFSET`
- **ภาษาและเครื่องมือ:** Frontend ต้องเป็น JavaScript/JSX (ไม่ใช้ TypeScript ตามคำสั่งเจ้าของ project)

## 23. Out of Scope

| รายการ | ที่มา |
|---|---|
| Import ข้อมูลจากเอกสารหรือไฟล์, OCR, Data Extraction, Document Parsing, Data Entry | [SRS-M] §3.1, §39 |
| สร้าง แก้ไข ลบ หรือแปลงข้อมูลต้นทาง (Source Data CRUD) | [SRS-M] §3.2–3.3, §7 |
| สร้าง แก้ไข หรือลบ configuration ผ่าน Mornitor (Configuration CRUD) | [SRS-M] §4 (Mornitor เป็น Configuration Consumer), §8 |
| สร้าง business rule ที่ไม่อยู่ใน configuration และ hard-code configuration | [SRS-M] §3.4–3.5 |
| สร้างเอกสาร (เช่น SAR / เอกสาร PS ใน `generated_documents`) | [SRS-M] §62–63 จำกัดหน้าที่ไว้ที่ "อ่าน Configuration + อ่าน Data + ตรวจ + แสดงผล"; SRS ไม่ได้พูดถึง SAR โดยตรง และระบบใดเป็นผู้สร้าง: **ข้อมูลไม่เพียงพอ** |

หัวข้อที่ [SRS-M] ระบุเป็น `TBD / SPEC GAP` (ยังไม่ได้ตัดสินว่าอยู่ในขอบเขตหรือไม่):
- Security (§51)
- Performance (§52)
- Scaling (§53)
- Logging นอกเหนือจาก Error Logging เช่น audit, activity, request, retention / rotation (§54)
- API endpoint (§46)
- Error code (§48)
- External Service A / B นอกจาก Document Generation (§6)
- การเก็บผลการตรวจ (§8)

## 24. Current Limitations

1. `overallStatus` เป็น `null` เสมอ (Programme Readiness อยู่ใน field `programmeReadiness` แยกต่างหาก)
2. `evidence` เป็นเอกสารของหลักสูตร (ไม่ใช่รายเกณฑ์ เพราะไม่มี field เชื่อมเอกสารกับ PS) และ `verification.approved` เป็น `null` เสมอ (`verified` มาจากการกดยืนยันของผู้ใช้เท่านั้น ไม่มีการยกเลิกหรือยืนยันใหม่เมื่อข้อมูลเปลี่ยน; เก็บ `verifiedAt` ไว้)
3. PS-03 มี `status` เป็น REVIEW เสมอ (รวมใน `result.status` ที่บันทึก) แม้ผู้ตรวจบันทึกผลแล้ว (ผลที่เลือกอยู่ใน `review` ไม่ override) Generation Readiness จึงเป็น NOT_READY เสมอ และ Programme Readiness ไม่เกิน 88.89% จนกว่าจะมีการตัดสินใจเรื่อง override
4. PS-03 ไม่ตรวจข้ามหลักสูตร
5. ไม่ระบุ `curriculumCode` แต่มีหลายหลักสูตรจะได้ `409` และไม่มี endpoint รายชื่อหลักสูตร
6. นับ appointment ทุก `status` (PS-01, 02, 04, 05, 06, 07)
7. PS-05 จับคู่ degree ตรงตัวอักษรและรับระดับละ 1 คำสะกด
8. PS-08 ตรวจว่ามีข้อมูลคุณวุฒิจาก `educations.degree` และตรวจ `hasTeachingExperience` ว่าเป็น true โดยไม่ตรวจจำนวนปี ประเภท หรือความเกี่ยวข้องของประสบการณ์ (business rule ของเจ้าของ project)
9. ถ้ามีเอกสาร `ps_requirements` ที่ `psCode` ซ้ำ:
   - endpoint ภาพรวมจะแสดงทุกเอกสารที่ active
   - endpoint รายละเอียดใช้เอกสารแรกที่ `find` คืนมา
10. บรรทัด missing ที่ไม่มีแม่แบบภาษาไทยแสดงเป็น "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด" รวมถึง SPEC GAP, configuration error และข้อความของ PS-06 เรื่องชื่อหลักสูตร
11. ไม่มี authentication, authorization (ไม่รู้ว่าใครยืนยัน) และเก็บถาวรเฉพาะการยืนยัน
12. Document Generation อ่าน readiness แบบ pull ผ่าน `GET /api/monitor` ซึ่งไม่มี authentication (SRS-M §51 TBD) · adapter External Service A / B ยังเป็น class ว่าง
13. ไฟล์ configuration ACTIVE เป็นไฟล์ใน `backend/tests/fixtures/` และต้องนำเข้า `ps_requirements` ก่อนระบบจึงใช้ได้จริง ณ วันที่จัดทำ database ของเครื่องนี้ยังไม่มี `ps_requirements`
14. frontend มีข้อความ requirement และรายการ PS code ซ้ำกับ configuration (`psTitles.js`, `psGuideline.js`) ซึ่ง test ตรวจว่าตรงกัน
15. เอกสารเดิม (`README.md`, `docs/SPEC_GAPS.md`, `docs/TESTING.md`, `CHANGELOG.md`) ถูกปรับให้ตรงกับ code แล้วเมื่อ 2026-09-26 ส่วน comment ใน code และ test fixture ที่ยังอ้างของเก่าอยู่ใน [DOCUMENTATION-SYNC.md](DOCUMENTATION-SYNC.md)
16. เมื่อหลายคนมี `fullName` ซ้ำกัน บรรทัด missing ของ PS-04 จะแสดงรหัสอ้างอิงซ้ำสองครั้ง เช่น `x (id) (id): roleName` (แสดงผลเท่านั้น ไม่เปลี่ยนผล)
