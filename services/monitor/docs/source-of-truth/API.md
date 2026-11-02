# API — Mornitor (AUN-QA PS Monitor)

> **สถานะเอกสาร:** Source of Truth · จัดทำ 2026-09-26 จาก working tree (commit `66ea7f5` + การเปลี่ยนแปลงที่ยังไม่ commit)
> **เอกสารชุดเดียวกัน:** [PS-Config.json](PS-Config.json) · [SRS.md](SRS.md) · [SCOPE.md](SCOPE.md) · [Data-Schema.md](Data-Schema.md) · [ARCHITECTURE.md](ARCHITECTURE.md)
> **ตรวจจาก:**
> - `backend/app/main.py`, `backend/app/api/routes/monitor.py`, `backend/app/models/schemas.py`
> - เรียก `app.openapi()` และ `TestClient` จริงเมื่อ 2026-09-26
> - test `backend/tests/test_engine_and_api.py`
> **Intended Scope:** [SRS-M] §46 ระบุ endpoint และ method เป็น `TBD / SPEC GAP` API ทั้งหมดในเอกสารนี้จึงเป็น **contract ชั่วคราว** ตามที่ code ทำจริง

## 1. ภาพรวม

| หัวข้อ | Current Implementation |
|---|---|
| Framework | FastAPI, `title="Mornitor"`, `version="0.4.0"`, OpenAPI 3.1.0 |
| Base path | `/api` (`APIRouter(prefix="/api/monitor")`) |
| Method | `GET` (อ่าน) · `POST` เฉพาะ `/api/monitor/results`, `/api/monitor/ps/{ps_code}/verification` และ `/api/monitor/ps/{ps_code}/review` (บันทึกใน `monitoring_results`) · method อื่นรวม `HEAD` ตอบ `405` |
| Request body | ไม่มี ยกเว้น `POST …/review` (`{"status": "…"}`) |
| Response | JSON, ชื่อ field แบบ camelCase (`response_model_by_alias=True`) |
| Authentication | ไม่มี |
| CORS | `allow_origins` จาก `MORNITOR_CORS_ORIGINS` (ค่าเริ่มต้น `http://localhost:5173`), `allow_methods=["GET", "POST"]` (route `POST` มีเฉพาะการบันทึกผล การยืนยัน และผลของผู้ตรวจ), `allow_headers=["*"]` · preflight จาก origin อื่นหรือ method อื่นตอบ `400` |
| Caching | ไม่มี อ่าน configuration และข้อมูลใหม่ทุก request |

## 2. Endpoint ทั้งหมด

| METHOD | PATH | PARAMETERS | SOURCE FILE |
|---|---|---|---|
| GET | `/api/monitor` | query `curriculumCode` (string, ไม่บังคับ) | `backend/app/api/routes/monitor.py` (`get_monitor`) |
| GET | `/api/monitor/ps/{ps_code}` | path `ps_code` (string, บังคับ) · query `curriculumCode` (string, ไม่บังคับ) | `backend/app/api/routes/monitor.py` (`get_ps`) |
| POST | `/api/monitor/results` | query `curriculumCode` (string, ไม่บังคับ) | `backend/app/api/routes/monitor.py` (`post_results`) |
| POST | `/api/monitor/ps/{ps_code}/verification` | path `ps_code` (string, บังคับ) · query `curriculumCode` (string, ไม่บังคับ) | `backend/app/api/routes/monitor.py` (`post_verification`) |
| POST | `/api/monitor/ps/{ps_code}/review` | path `ps_code` · query `curriculumCode` (ไม่บังคับ) · body `{"status": string}` | `backend/app/api/routes/monitor.py` (`post_review`) |
| GET | `/openapi.json` | — | FastAPI สร้างอัตโนมัติ (ไม่ได้ปิดใน `main.py`) |
| GET | `/docs`, `/docs/oauth2-redirect` | — | FastAPI สร้างอัตโนมัติ (Swagger UI) |
| GET | `/redoc` | — | FastAPI สร้างอัตโนมัติ (ReDoc) |

ไม่มี endpoint อื่น ไม่มี `PUT` / `PATCH` / `DELETE` และไม่มี endpoint รายชื่อหลักสูตร, configuration หรือ health check

## 3. `GET /api/monitor`

ผลการตรวจทุกเกณฑ์ที่ active ของหนึ่งหลักสูตร

| หัวข้อ | รายละเอียด |
|---|---|
| **PARAMETERS** | `curriculumCode` (query, ไม่บังคับ): เลือกหลักสูตรที่ `curricula.curriculumCode` เท่ากันทุกตัวอักษร |
| **REQUEST** | ไม่มี body |
| **RESPONSE 200** | `MonitorResponse` (§5) |
| **SOURCE FILE** | route `backend/app/api/routes/monitor.py` · logic `backend/app/services/monitoring_service.py` (`monitor`) |

**ลำดับการทำงาน:**
1. อ่านเอกสาร `ps_requirements` ที่ `active: true` แล้วเรียงตาม `psCode` (ไม่รวมเอกสารที่มี `configType`)
2. อ่านเอกสาร `ps_requirements` ที่ `configType: "generationReadiness"` (Data-Schema §4.6)
3. หาหลักสูตร: ถ้ามี `curriculumCode` → หลักสูตรที่รหัสตรง; ถ้าไม่มี → ทุกหลักสูตร
   - มากกว่า 1 หลักสูตร → `409`
   - ไม่พบหลักสูตร → `200` `{"curriculum": null, "overallStatus": null, "dataCompleteness": "complete", "results": [], "generationReadiness": {...}, "programmeReadiness": null}` (ทุก PS ใน `requiredPS` ไม่มีผล จึงเป็น `NOT_READY`; ไม่มีหลักสูตรจึงไม่มี Programme Readiness)
4. ประเมินทุกเกณฑ์ที่ active ด้วย engine ได้ `results` หนึ่งรายการต่อเกณฑ์ ตามลำดับ `psCode`
5. `dataCompleteness` = `incomplete` ถ้ามีผลใดเป็น `incomplete`
6. `overallStatus` = `null` เสมอ (ยังไม่มีกฎรวมผล)
7. `generationReadiness` ตัดสินจากเอกสารในขั้น 2 และ `results` (§5)
8. `programmeReadiness` รวมจาก `results` (§5) คำนวณใน response model
9. อ่าน `monitoring_results` ของหลักสูตร (`verification`, `review`, `persistedResult`) — GET ไม่เขียนข้อมูล

ถ้ามีหลักสูตรแต่ไม่มี configuration ที่ active จะได้ `results: []` และ `curriculum` เป็นข้อมูลหลักสูตรนั้น

**STATUS CODES:**

| Code | เมื่อไร | Body |
|---|---|---|
| 200 | สำเร็จ | `MonitorResponse` |
| 409 | ไม่ระบุ `curriculumCode` และมีมากกว่า 1 หลักสูตร | `{"detail": "SPEC GAP: <n> curricula match and the specification does not define which one to monitor; request one with curriculumCode"}` |
| 503 | อ่าน MongoDB ไม่ได้ (`PyMongoError` → `DataSourceError`) | `{"detail": "Unable to load monitoring data"}` |
| 405 | method อื่นที่ไม่ใช่ `GET` | `{"detail": "Method Not Allowed"}` |
| 422 | ประกาศโดย FastAPI อัตโนมัติ | ไม่พบกรณีที่เกิดได้จาก parameter ชนิด string ในปัจจุบัน |

## 3.1 `POST /api/monitor/results`

Persistent Monitoring Result (เจ้าของ project 2026-09-26): ประเมินตอนนี้ด้วย engine เหมือน §3 แล้วเก็บ `status` ของทุก PS ที่ active

| หัวข้อ | รายละเอียด |
|---|---|
| **PARAMETERS** | `curriculumCode` (query, ไม่บังคับ) เหมือน §3 |
| **REQUEST** | ไม่มี body |
| **RESPONSE 200** | `MonitorResponse` แบบเดียวกับ §3 (อ่านใหม่หลังบันทึก) โดยทุกผลมี `persistedResult` |
| **บันทึก** | `monitoring_results` เอกสาร `curriculumId + psCode` ของทุก PS ใน `results`: `result: {status, evaluatedAt}` (bulk write ครั้งเดียว เวลาของ server เดียวกัน) · current state: บันทึกใหม่แทนค่าเดิม ไม่มีประวัติ ไม่มีเอกสารซ้ำ · ไม่ลบ `verification` / `review` · PS-03 เก็บ `status` ของ engine (REVIEW) ไม่ใช่ `review.status` |
| **ไม่เก็บ** | readiness, evidence, traceability และ field อื่นของ PSResult |
| **ไม่เปลี่ยน** | ผลการประเมินใด ๆ (engine ไม่อ่านค่าที่บันทึก), ข้อมูลต้นทาง / configuration |
| **SOURCE FILE** | route `backend/app/api/routes/monitor.py` (`post_results`) · logic `backend/app/services/monitoring_service.py` (`save_results`) · store `backend/app/repositories/monitoring_results.py`, `backend/app/adapters/monitoring_results.py` |

**STATUS CODES:**

| Code | เมื่อไร | Body |
|---|---|---|
| 200 | บันทึกแล้ว | `MonitorResponse` |
| 404 | ไม่พบหลักสูตร (ไม่บันทึก) | `{"detail": "No monitoring result"}` |
| 409 | ไม่ระบุ `curriculumCode` และมีมากกว่า 1 หลักสูตร (ไม่บันทึก) | เหมือน §3 |
| 503 | อ่านข้อมูลไม่ได้ระหว่างประเมิน (ไม่บันทึก) / เขียนไม่ได้ / ไม่มี Monitor store | `{"detail": "Unable to save the monitoring result"}` |
| 405 | `GET` / method อื่นที่ path นี้ | `{"detail": "Method Not Allowed"}` |

## 3.2 Contract สำหรับ Document Generation (pull, readiness-only)

เจ้าของ project ยืนยัน 2026-09-26: ฝั่ง Document Generation เป็นผู้เรียก Mornitor ไม่มีการ push จาก Mornitor

| หัวข้อ | รายละเอียด |
|---|---|
| **Endpoint** | `GET /api/monitor?curriculumCode=<curricula.curriculumCode>` (§3 เดิม ไม่มี endpoint ใหม่) |
| **Field ที่ Generator อ่าน** | `generationReadiness.status` เท่านั้น · field อื่นใน response มีไว้สำหรับหน้าเว็บ Generator ไม่ต้องใช้ |
| **ค่า** | `"READY"` → Generator ดึงข้อมูลจาก DB ของตัวเองแล้ว Generate ต่อ · `"NOT_READY"` → ไม่ Generate · `null` → configuration Generation Readiness ตัดสินไม่ได้ (ดู `generationReadiness.issue`) ซึ่งไม่ใช่ `READY` · ค่าคำนวณจากผลปัจจุบันของ engine ตาม SET 1 ทุก request (ไม่ใช่ `persistedResult`) |
| **Status code** | `200` · `409` เมื่อไม่ส่ง `curriculumCode` และมีหลายหลักสูตร (ส่ง `curriculumCode` เสมอ) · `503` เมื่ออ่าน MongoDB ไม่ได้ (ไม่มีค่า readiness) · `curriculumCode` ที่ไม่มีอยู่ → `200` `curriculum: null` และ `NOT_READY` |
| **Side effect** | ไม่มี: GET ไม่เขียน `monitoring_results` ข้อมูลต้นทางหรือ configuration |
| **Authentication** | ไม่มี (Mornitor ยังไม่มี authentication — [SRS-M] §51 TBD) · CORS ใช้เฉพาะเมื่อเรียกจาก browser (`MORNITOR_CORS_ORIGINS`) |
| **Timeout / retry** | กำหนดโดยฝั่ง Generator (Mornitor ไม่มี contract เรื่องนี้) · ทุก request ประเมินใหม่ ไม่มี cache |
| **Mornitor ไม่ทำ** | push / webhook / callback / outbound call, ส่ง PS results / evidence / curriculum / documents ให้ Generator, เข้าถึง DB ของ Generator, สร้าง SAR |
| **Test** | `backend/tests/test_generator_contract.py` |

## 4. `GET /api/monitor/ps/{ps_code}`

ผลการตรวจของเกณฑ์เดียว

| หัวข้อ | รายละเอียด |
|---|---|
| **PARAMETERS** | `ps_code` (path, บังคับ) เช่น `PS-01` · `curriculumCode` (query, ไม่บังคับ) |
| **REQUEST** | ไม่มี body |
| **RESPONSE 200** | `PSResult` (§5) เหมือนรายการใน `results` ของ `GET /api/monitor` ทุก field |
| **SOURCE FILE** | route `backend/app/api/routes/monitor.py` · logic `backend/app/services/monitoring_service.py` (`ps_detail`) |

**ลำดับการทำงาน:**
1. `find({psCode: ps_code})` แล้วใช้เอกสารแรก เอกสารนั้นต้องมี `active: true`
2. หาหลักสูตรแบบเดียวกับ §3 ขั้นนี้ทำเสมอ จึงได้ `409` เมื่อมีหลายหลักสูตรแม้ `ps_code` จะไม่มีอยู่
3. ไม่มีเกณฑ์ที่ active หรือไม่มีหลักสูตร → `404`

**STATUS CODES:**

| Code | เมื่อไร | Body |
|---|---|---|
| 200 | สำเร็จ | `PSResult` |
| 404 | ไม่มีเกณฑ์นี้, เกณฑ์ไม่ active หรือไม่พบหลักสูตร | `{"detail": "No monitoring result"}` |
| 409 | ไม่ระบุ `curriculumCode` และมีมากกว่า 1 หลักสูตร | เหมือน §3 |
| 503 | อ่าน MongoDB ไม่ได้ | `{"detail": "Unable to load monitoring data"}` |
| 405 | method อื่น | `{"detail": "Method Not Allowed"}` |

## 4.1 `POST /api/monitor/ps/{ps_code}/verification`

ผู้ใช้ยืนยันหลักฐานที่แสดงประกอบกับผลของ PS นี้ (เจ้าของ project 2026-09-26) ไม่เปลี่ยนผลการตรวจ

| หัวข้อ | รายละเอียด |
|---|---|
| **PARAMETERS** | เหมือน §4 |
| **REQUEST** | ไม่มี body |
| **RESPONSE 200** | `PSResult` แบบเดียวกับ §4 (อ่านใหม่หลังบันทึก) โดย `verification.verified = true` |
| **บันทึก** | collection `monitoring_results` (database: `MORNITOR_RESULTS_DB_URI` / `MORNITOR_RESULTS_DB_NAME`, ค่าเริ่มต้นเท่ากับ source) เอกสาร `{curriculumId: curricula._id, psCode, verification: {verified: true, verifiedAt}}` · unique index `curriculumId + psCode` · กดซ้ำ → ไม่มีรายการใหม่ `verifiedAt` ครั้งแรกคงเดิม (idempotent) |
| **ไม่เปลี่ยน** | `status`, `evidence`, `traceability`, `approved` (คง `null`), `programmeReadiness`, `generationReadiness`, ผล PS-03 และข้อมูลต้นทาง / configuration ทุก collection |
| **SOURCE FILE** | route `backend/app/api/routes/monitor.py` · logic `backend/app/services/monitoring_service.py` (`verify`) · store `backend/app/repositories/monitoring_results.py`, `backend/app/adapters/monitoring_results.py` |

**STATUS CODES:**

| Code | เมื่อไร | Body |
|---|---|---|
| 200 | บันทึกแล้ว (หรือยืนยันไว้แล้ว) | `PSResult` |
| 404 | ไม่มีเกณฑ์นี้, เกณฑ์ไม่ active หรือไม่พบหลักสูตร (ไม่บันทึก) | `{"detail": "No monitoring result"}` |
| 409 | ไม่ระบุ `curriculumCode` และมีมากกว่า 1 หลักสูตร (ไม่บันทึก) | เหมือน §3 |
| 503 | อ่าน/เขียน MongoDB ไม่ได้ หรือไม่มี Monitor store | `{"detail": "Unable to save the verification"}` |
| 405 | `GET` / method อื่นที่ path นี้ | `{"detail": "Method Not Allowed"}` |

## 4.2 `POST /api/monitor/ps/{ps_code}/review`

ผลที่ผู้ตรวจเลือกสำหรับ PS ที่ configuration ให้ผู้ใช้ตรวจ (`review.required: true`, `review.reviewByUser: true`; config ACTIVE: PS-03, PS-06) เจ้าของ project 2026-09-26

| หัวข้อ | รายละเอียด |
|---|---|
| **PARAMETERS** | เหมือน §4 |
| **REQUEST** | JSON `{"status": "PASS" \| "FAIL" \| "REVIEW"}` — ต้องเป็นค่าใน `config.review.allowManualResult` ของ PS นั้น (ตรงตัวอักษร) · key อื่น (เช่น `reviewedAt`) ไม่ถูกใช้ |
| **RESPONSE 200** | `PSResult` แบบเดียวกับ §4 (อ่านใหม่หลังบันทึก) โดย `review.status` เป็นค่าที่บันทึก และ `status` ยังเป็นของ engine |
| **บันทึก** | `monitoring_results` เอกสาร `curriculumId + psCode` (เอกสารเดียวกับ verification) ตั้ง `review: {status, reviewedAt}` ด้วยเวลาของ server · บันทึกซ้ำแก้เอกสารเดิม ไม่สร้างเอกสารใหม่ ไม่ลบ `verification` · ไม่เก็บประวัติ ไม่มี `reviewedBy` |
| **ไม่เปลี่ยน** | `status` (REVIEW ของ engine), `evidence`, `traceability`, `verification`, `programmeReadiness`, `generationReadiness` และข้อมูลต้นทาง / configuration ทุก collection |
| **SOURCE FILE** | route `backend/app/api/routes/monitor.py` · logic `backend/app/services/monitoring_service.py` (`review`), `backend/app/services/user_review.py` · store `backend/app/repositories/monitoring_results.py`, `backend/app/adapters/monitoring_results.py` |

**STATUS CODES:**

| Code | เมื่อไร | Body |
|---|---|---|
| 200 | บันทึกแล้ว | `PSResult` |
| 400 | configuration ของ PS นี้ไม่ได้ให้ผู้ใช้ตรวจ | `{"detail": "<psCode> takes no review by the user in its configuration"}` |
| 404 | ไม่มีเกณฑ์นี้, เกณฑ์ไม่ active หรือไม่พบหลักสูตร | `{"detail": "No monitoring result"}` |
| 409 | ไม่ระบุ `curriculumCode` และมีมากกว่า 1 หลักสูตร | เหมือน §3 |
| 422 | `status` ไม่อยู่ใน `allowManualResult` (เช่น `N/A`, `APPROVED`), ไม่มี body หรือ `status` ไม่ใช่ข้อความ | `{"detail": …}` |
| 503 | อ่าน/เขียน MongoDB ไม่ได้ หรือไม่มี Monitor store | `{"detail": "Unable to save the review"}` |
| 405 | `GET` / method อื่นที่ path นี้ | `{"detail": "Method Not Allowed"}` |

ทุกกรณีที่ไม่ใช่ 200 ไม่บันทึกอะไร

## 5. Response Schema

**`MonitorResponse`**

| Field | Type | หมายเหตุ |
|---|---|---|
| `curriculum` | `CurriculumInfo` \| null | null เมื่อไม่พบหลักสูตร |
| `overallStatus` | Status \| null | null เสมอ (ผลรวมยังไม่มีนิยาม; Programme Readiness อยู่ใน `programmeReadiness`) |
| `dataCompleteness` | `"complete"` \| `"incomplete"` | |
| `results` | `PSResult[]` | เรียงตาม `psCode` |
| `generationReadiness` | `GenerationReadiness` | ความพร้อมสำหรับระบบสร้างเอกสารภายนอก (เพิ่ม 2026-09-26) ไม่ใช่ `overallStatus` และไม่ใช่ Programme Readiness |
| `programmeReadiness` | `ProgrammeReadiness` \| null | ความพร้อมของหลักสูตรเป็น % (เพิ่ม 2026-09-26) · `null` เมื่อไม่พบหลักสูตร |

**`GenerationReadiness`** (`backend/app/services/generation_readiness.py`)

| Field | Type | ความหมาย |
|---|---|---|
| `status` | `"READY"` \| `"NOT_READY"` \| null | `READY` เมื่อ PS ทุกตัวใน `requiredPS` มี configuration ที่ active มีผล และสถานะอยู่ใน `allowedStatus` · `NOT_READY` เมื่อมี PS ที่ block · `null` เมื่อตัดสินไม่ได้ (ดู `issue`) |
| `blockingPS` | `{psCode, status}[]` | PS ใน `requiredPS` ที่สถานะอยู่ใน `blockedStatus` หรือไม่มี configuration ที่ active / ไม่มีผล (`status: null`) เรียงตาม `requiredPS` · ว่างเมื่อ `READY` หรือ `status` เป็น null |
| `issue` | `"configuration_error"` \| `"spec_gap"` \| null | `configuration_error`: ไม่พบเอกสาร, มีมากกว่า 1 เอกสาร, เอกสารผิดรูปแบบ (`status: null`) หรือ `requiredPS` มี PS ที่ไม่มี configuration ที่ active (`NOT_READY`) · `spec_gap`: กรณีที่เจ้าของ project ยังไม่ได้กำหนดกติกา ระบบจึงไม่ตัดสินและรอการตัดสินใจ (`requiredAll: false` หรือมีผลที่สถานะไม่อยู่ในทั้งสองรายการและไม่มี PS ที่ block) |
| `detail` | string \| null | ข้อความอธิบาย (ภาษาอังกฤษ) รวมถึงกรณี PS ใน `requiredPS` ไม่มีผลการประเมิน เช่น ไม่พบหลักสูตร (ปัญหาข้อมูล `issue` เป็น null เพราะ contract ยังไม่มีรหัสสำหรับปัญหาข้อมูล) |

ไม่มีค่าเริ่มต้นใน code: ถ้าไม่มีเอกสาร `status` เป็น `null` เสมอ ไม่มีการอ่าน key อื่นนอกจาก `requiredPS`, `readyWhen.allowedStatus`, `readyWhen.blockedStatus`, `requiredAll` สถานะของแต่ละ PS อยู่ใน `results[].status` ส่วน endpoint รายละเอียด PS ไม่มี field นี้

**`ProgrammeReadiness`** (`backend/app/models/schemas.py`)

| Field | Type | ความหมาย |
|---|---|---|
| `percentage` | number | `passCount` × 100 ÷ `totalPS` ปัดทศนิยม 2 ตำแหน่ง (เช่น 77.78; 100 และ 0 ส่งเป็น `100.0` / `0.0`) |
| `passCount` | integer | จำนวน PS (ไม่ซ้ำ `psCode`) ใน `results` ที่ `status` เป็น `PASS` เท่านั้น — FAIL, REVIEW, N/A และ PS ที่ไม่มีผลไม่นับ |
| `totalPS` | integer | 9 เสมอ (PS-01 ถึง PS-09 ตามที่เจ้าของ project กำหนด) ไม่ใช่จำนวน `results`, จำนวน configuration ที่ active หรือ `generationReadiness.requiredPS` |

Programme Readiness ≠ Generation Readiness: เช่น PASS 7 + N/A 2 → `programmeReadiness.percentage` 77.78 แต่ `generationReadiness.status` `READY` (N/A อยู่ใน `allowedStatus`) ทั้งสองเป็นคนละ object และไม่มีตัวใดใส่ใน `overallStatus` · PS-03 ที่ยังไม่มีผลจากผู้ตรวจเป็น REVIEW จึงไม่นับ

**`CurriculumInfo`:** ทุก field เป็น string หรือ null (แปลงจาก `curricula` ด้วย `str()`)

| Field | มาจาก |
|---|---|
| `curriculumCode` | `curricula.curriculumCode` |
| `curriculumName` | `curricula.curriculumName` |
| `curriculumYear` | `curricula.curriculumYear` |
| `version` | `curricula.version` |
| `status` | `curricula.status` |

**`PSResult`**

| Field | Type | ความหมาย |
|---|---|---|
| `psCode` | string | จาก `ps_requirements.psCode` |
| `status` | `"PASS"` \| `"FAIL"` \| `"REVIEW"` \| `"N/A"` | จาก map `config.result` |
| `requirement` | string \| null | จาก `ps_requirements.requirement` |
| `checks` | string[] | ทุกบรรทัดของ `config` ในรูป `path: value` |
| `dataSummary` | `SummaryItem[]` (`{label, value}`) | ตัวเลขและบันทึกของการตรวจ (§6) |
| `dataFound` | `DataGroup[]` (`{label, items[]}`) | สิ่งที่พบ แสดงชื่อแทน ObjectId |
| `verification` | `{found, verified, approved, verifiedAt}` | `found` = จำนวน record ที่อ่าน (เท่ากับ `traceability.length`) · `verified` = `true` เมื่อมีการยืนยันใน `monitoring_results` (curriculumId + psCode), `false` เมื่อยังไม่ยืนยัน, `null` เมื่อ backend ไม่มี Monitor store · `verifiedAt` = เวลายืนยันครั้งแรก (ISO 8601 UTC) หรือ `null` · `approved` = `null` เสมอ (การยืนยันไม่ใช่การอนุมัติ) |
| `missingInformation` | string[] | ข้อมูลที่ขาดหรือปัญหาของ configuration (§7) |
| `evidence` | `EvidenceItem[]` (`{label, reference, storage, path}`) | เอกสารของหลักสูตรที่ตรวจ (`documents.curriculumId = curricula._id`) อ่านอย่างเดียว เรียงตามที่ MongoDB ส่ง ไม่ซ้ำ `_id` · ทุก PS ได้รายการเดียวกัน · ไม่มีเอกสาร → `[]` · ไม่เปลี่ยน `status`, `traceability` หรือ readiness |
| `traceability` | `TraceItem[]` | `{collection, recordId, fields[], values{field: string}}` ต่อ record ที่อ่าน |
| `dataCompleteness` | `"complete"` \| `"incomplete"` | `incomplete` เมื่อ `missingInformation` ไม่ว่าง |
| `issue` | `"configuration_error"` \| `"evaluation_error"` \| `"spec_gap"` \| null | เหตุที่ตัดสินไม่ได้; null = ผลมาจากข้อมูล |
| `reviewRequired` | boolean \| null | `config.review.required` เมื่อเป็น boolean (config ACTIVE: PS-03, PS-06) |
| `reviewByUser` | boolean \| null | `config.review.reviewByUser` เมื่อเป็น boolean (config ACTIVE: PS-03, PS-06) |
| `persistedResult` | `{status, evaluatedAt}` \| null | สถานะที่ engine ให้ PS นี้ตอนบันทึกผลครั้งล่าสุด (§3.1) และเวลาของ server · `null` เมื่อยังไม่เคยบันทึก หรือไม่มี Monitor store · อาจต่างจาก `status` เมื่อข้อมูลเปลี่ยนหลังบันทึก · ไม่มี readiness ใดอ่าน |
| `review` | `UserReview` \| null | เฉพาะ PS ที่ configuration ให้ผู้ใช้ตรวจ (PS-03, PS-06): `{allowManualResult: Status[], status: Status \| null, reviewedAt: string \| null}` · `allowManualResult` จาก config · `status` / `reviewedAt` จาก `monitoring_results` (`null` เมื่อยังไม่บันทึก) · **ไม่ใช่ `status` ของ PS** และไม่มี readiness ใดอ่าน · PS อื่นเป็น `null` |

**`EvidenceItem`** (`backend/app/services/evidence.py`)

| Field | Type | มาจาก |
|---|---|---|
| `label` | string | `documents.fileName` (ไม่มีหรือว่าง → ใช้ `reference`) |
| `reference` | string \| null | `documents._id` |
| `storage` | string \| null | `documents.originalFile.storage` · `null` เมื่อไม่มี `originalFile`, ไม่มี field นี้, ว่าง หรือไม่ใช่ข้อความ |
| `path` | string \| null | `documents.originalFile.path` · `null` ในกรณีเดียวกัน (ไม่มีการสร้าง path) |

กรณีที่แยกได้: มีเอกสารครบ · มีเอกสารแต่ไม่มี `originalFile` (`storage`, `path` เป็น `null`) · ขาด `storage` · ขาด `path` · ไม่มีเอกสารของหลักสูตร (`evidence: []`) · อ่าน `documents` ไม่ได้ (`503`) ไม่มี issue code ใหม่ และไม่เพิ่มบรรทัดใน `missingInformation` (ส่วนนั้นมาจาก configuration)

field ที่บังคับใน OpenAPI ของ `PSResult`:
- `psCode`, `status`, `checks`, `dataSummary`, `dataFound`, `verification`
- `missingInformation`, `evidence`, `traceability`, `dataCompleteness`

ไม่มี field `foundCount` จำนวนที่พบอยู่ที่ `verification.found`

## 6. Label ใน `dataSummary`

engine ใช้ label เหล่านี้เท่านั้น (`backend/app/monitoring/engine.py`) frontend ใช้ label เพื่อเลือกตำแหน่งแสดงผล (`components/DataFound/summaryLabels.js`, `app/explain.js`)

| Label | เกิดจาก |
|---|---|
| `Operation` | ทุกผลที่ engine ประมวลผลได้: คำอธิบาย operation |
| `Distinct <field> count` / `<field> count` | การนับ (PS-01) |
| `Condition` | เงื่อนไขการนับ เช่น `>= 5` |
| `<field>` (เช่น `curriculumYear`) | ค่าที่ใช้ในสูตร (PS-09) |
| `Records checked`, `Records with missing fields` | การตรวจ field ที่ต้องมี (PS-04) |
| `Subjects`, `Subjects PASS` / `FAIL` / `REVIEW` / `N/A` | การตรวจต่อบุคคล (PS-02, PS-05 ถึง PS-08) |
| `Review` | บันทึกว่าเกณฑ์ต้องให้ผู้ตรวจพิจารณา (PS-03, PS-06; หรือเกณฑ์ที่ไม่มีเงื่อนไขตัดสิน) |
| `Manual result` | ผลที่ผู้ตรวจเลือกเมื่อถูกส่งเข้า `ManualResultSource` ของ engine (ไม่เกิดใน production: ผลที่ผู้ตรวจบันทึกอยู่ใน `review` และไม่ override สถานะ) |
| `Not applicable` | เหตุผลของ N/A |

## 7. ข้อความใน `missingInformation`

ข้อความเป็นภาษาอังกฤษจาก engine หน้าเว็บแปลเป็นไทยด้วย `frontend/src/app/missingText.js` เฉพาะข้อความที่ตรงแม่แบบ ข้อความอื่นแสดงเป็น "ข้อมูลไม่เพียงพอสำหรับแสดงรายละเอียด" (จำนวนบรรทัดเท่าเดิม)

| ข้อความ (รูปแบบ) | แหล่ง | หน้าเว็บ |
|---|---|---|
| `SPEC GAP: …` | engine / interpreter | ข้อความสำรอง |
| `Configuration error: …` | engine / interpreter | ข้อความสำรอง |
| `Evaluation error: <Type>: <message>` | engine | ข้อความสำรอง |
| `no <collection> records were found` | PS-04 | แปลไทย |
| `no <collection> record is selected, so nothing can be checked` | ทุกเกณฑ์แบบต่อบุคคล | แปลไทย |
| `<n> <collection> record(s) lack <keys>` | ทุกเกณฑ์แบบต่อบุคคล (record ไม่มี key) | ข้อความสำรอง |
| `<record>: <field> is missing or not an integer` | PS-09 | แปลไทย |
| `<record>: <field>` | PS-04 | แปลไทย (เมื่อ field มีป้ายไทย) |
| `<n> record(s) lack a usable <field>` | PS-07 | แปลไทย |
| `no usable <field> value` | PS-05 | แปลไทย |
| `<field> value(s) not in the configured ordering: <values>` | PS-05 | ข้อความสำรอง |
| `<name>: no value found for review` | PS-06, PS-08 | ข้อความสำรอง (หน้า PS-06 แสดง "—" ในข้อมูลของอาจารย์คนนั้น) |
| `<name>: <values> cannot be compared with <value>` | PS-08 | ข้อความสำรอง |

## 8. ตัวอย่าง response (ข้อมูลทดสอบ ไม่ใช่ข้อมูลจริง)

ผลจริงของ code ปัจจุบัน สำหรับหลักสูตรทดสอบ `TEST-IS-001` บน test database: `GET /api/monitor/ps/PS-09?curriculumCode=TEST-IS-001` (ตัด `checks` ให้สั้นลง)

```json
{
  "psCode": "PS-09",
  "status": "PASS",
  "requirement": "หลักสูตรต้องมีการปรับปรุงล่าสุดไม่เกิน 5 ปี",
  "checks": ["targetCollection: \"curricula\"", "year.field: \"curriculumYear\"", "…"],
  "dataSummary": [
    {"label": "Operation", "value": "currentYear - curriculumYear over curricula; compare <= 5"},
    {"label": "curriculumYear", "value": "2567"}
  ],
  "dataFound": [{"label": "TEST-IS-001", "items": ["currentYear = 2569", "currentYear - curriculumYear = 2"]}],
  "verification": {"found": 1, "verified": false, "approved": null, "verifiedAt": null},
  "missingInformation": [],
  "evidence": [],
  "traceability": [
    {"collection": "curricula", "recordId": "7e57da7a0100000000000001",
     "fields": ["curriculumYear"], "values": {"curriculumYear": "2567"}}
  ],
  "dataCompleteness": "complete",
  "issue": null,
  "reviewRequired": null,
  "reviewByUser": null
}
```

## 9. การใช้งานฝั่ง Frontend

| ไฟล์ | หน้าที่ |
|---|---|
| `frontend/src/api/endpoints.js` | `${VITE_API_BASE_URL ?? "/api"}/monitor` และ `/monitor/ps/{psCode}` |
| `frontend/src/api/client.js` | ส่ง `GET` เท่านั้น แยก error แบบ network / http |
| `frontend/src/api/monitorApi.js` | เติม `?curriculumCode=`; ถ้าหน้ารายละเอียดได้ `404` จะคืน `null` (แสดงสถานะรอข้อมูล) |
| `frontend/src/api/adapter.js` | ปรับรูปข้อมูลเท่านั้น (array ว่าง / null) ไม่คำนวณสถานะ; status หรือ issue ที่ไม่รู้จักกลายเป็น null |
| `frontend/src/api/useRemote.js` | ส่ง `GET` เดิมซ้ำทุก 10 วินาทีตลอดเวลาที่เปิดหน้า |

- **ระหว่างพัฒนา / preview:** Vite proxy `/api` ไปที่ `MORNITOR_API_TARGET` (ค่าเริ่มต้น `http://localhost:8000`)
- **field ที่ API ส่งแต่หน้าเว็บไม่ใช้:**
  - `reviewRequired`, `reviewByUser` (adapter ไม่อ่าน; หน้าเว็บใช้ `review` แทน)
  - `generationReadiness` (adapter ไม่อ่าน หน้าเว็บยังไม่แสดง)
- **`programmeReadiness`:** adapter ส่งต่อค่าเดิม (ไม่ครบหรือไม่ใช่ตัวเลข → `null`) และหน้า `/monitor/ps` แสดง `percentage` + "%" กับ `passCount` / `totalPS` ในกล่อง "ความพร้อมของหลักสูตร"
  - `checks`, `traceability[].values` (adapter อ่านแต่ไม่แสดง)

## 10. Not Implemented

| รายการ | ที่มา |
|---|---|
| endpoint รายชื่อหลักสูตร (หน้าเว็บจึงแสดงได้แค่ข้อความเมื่อได้ `409`) | SPEC GAP |
| endpoint ที่ส่ง configuration ที่ active (รายการ PS + requirement) โดยไม่ต้องมีหลักสูตร | `docs/SPEC_GAPS.md` §4.11 |
| error code มาตรฐาน | [SRS-M] §48 (TBD) |
| authentication / authorization | [SRS-M] §51 (TBD) |
| versioning ของ API | ข้อมูลไม่เพียงพอ |
