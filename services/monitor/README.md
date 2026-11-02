# Mornitor

**Version 0.4.0 (2026-09-23)** · ระบบ Monitoring แบบ Plug-in สำหรับตรวจความครบถ้วนของข้อมูลตามเกณฑ์ PS-01 ถึง PS-09

Mornitor ทำงานตามลำดับนี้:

1. อ่าน configuration ของเกณฑ์จาก collection `ps_requirements`
2. อ่านข้อมูลต้นทางที่ Import Service บันทึกไว้ใน MongoDB
3. ตรวจตาม configuration ด้วย engine กลาง (generic)
4. แสดงผลเป็น PASS / FAIL / REVIEW / N/A พร้อม Data Found, Missing Information, Verification และ Traceability
5. ให้ผู้ใช้กดยืนยันหลักฐาน / ผลการตรวจของแต่ละ PS และบันทึกผลที่ผู้ตรวจเลือกของ PS-03 (เก็บใน `monitoring_results` ไม่เปลี่ยนผลการตรวจหรือความพร้อม)

การตรวจทำตาม configuration ทั้งหมด **engine ไม่มีเกณฑ์ ค่า threshold, role หรือรายการ PS เขียนตายตัวไว้เลย** (frontend มีรายการ PS code และข้อความ requirement สำรองไว้แสดงผลเท่านั้น ดู `psGuideline.js` / `psTitles.js`)

- **เอกสาร Source of Truth** (ตรงกับ code ณ 2026-09-26): [docs/source-of-truth/](docs/source-of-truth/) — SRS, SCOPE, Data-Schema, API, ARCHITECTURE, PS-Config
- การตีความ, SPEC GAP และสิ่งที่ยังเปิดอยู่: [docs/SPEC_GAPS.md](docs/SPEC_GAPS.md)
- คู่มือทดสอบสำหรับทีมอื่น: [docs/TESTING.md](docs/TESTING.md)
- สิ่งที่เปลี่ยนในเวอร์ชันนี้: [CHANGELOG.md](CHANGELOG.md)

## ขอบเขต (ตาม SRS Mornitor)

| Mornitor ทำ | Mornitor ไม่ทำ |
|---|---|
| อ่าน configuration จาก DB (`ps_requirements`, เฉพาะ `active: true`) | Import เอกสาร / OCR / Extraction / Parsing |
| อ่านข้อมูลต้นทาง (อ่านอย่างเดียว ใช้แค่ `find`) | สร้าง แก้ไข หรือลบข้อมูลต้นทางหรือ configuration |
| ตรวจตาม configuration และบอกข้อมูลที่พบและข้อมูลที่ขาด | สร้าง business rule ที่ไม่มีใน configuration |
| แสดงผลผ่านเว็บ (GET) และบันทึกการยืนยัน / ผลของผู้ตรวจ / ผลการตรวจ (POST 3 route) | Login / สิทธิ์ผู้ใช้ / Generate SAR (ยังเป็น SPEC GAP หรืออยู่นอกขอบเขต) |

## สิ่งที่ต้องมี

- **Python 3.11 ขึ้นไป** (ทดสอบกับ 3.11)
- **Node.js 20.19 ขึ้นไป หรือ 22.12 ขึ้นไป** (Vite 8 ต้องใช้ ทดสอบกับ Node 22.22)
- **MongoDB** ที่มีข้อมูลจาก Import Service และ collection `ps_requirements` ครบ 9 เกณฑ์
  - ถ้ายังไม่มี ดูวิธีเตรียมใน [docs/TESTING.md](docs/TESTING.md)
  - ควรใช้ account แบบ read-only
- **หรือ Docker** (Docker Desktop / Docker Engine + Compose v2.24 ขึ้นไป) แทน Python และ Node.js ดูข้อ 3

## เริ่มใช้งาน

### 1. Backend (FastAPI, พอร์ต 8000)

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt        # หรือ requirements-dev.lock.txt (เวอร์ชันที่ทดสอบแล้ว)
.venv/bin/python -m pytest                           # ควรผ่านทั้งหมด
MORNITOR_DB_URI="mongodb://localhost:27017" MORNITOR_DB_NAME="<ชื่อ DB ของ Import Service>" \
  .venv/bin/uvicorn app.main:app --port 8000
```

Windows (PowerShell):

```powershell
cd backend
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
$env:MORNITOR_DB_URI = "mongodb://localhost:27017"; $env:MORNITOR_DB_NAME = "<ชื่อ DB ของ Import Service>"
.venv\Scripts\uvicorn app.main:app --port 8000
```

เอกสาร API อัตโนมัติ: http://localhost:8000/docs

### 2. Frontend (React + Vite, พอร์ต 5173)

```bash
cd frontend
npm ci
npm test                 # vitest
npm run dev              # http://localhost:5173/  (proxy /api → http://localhost:8000)
```

- **แบบ production:** `npm run build && npm run preview` จะเปิดที่ http://localhost:4173/ โดยใช้ proxy `/api` แบบเดียวกัน
- **ไม่มีโหมดข้อมูลตัวอย่าง (mock):** หน้าเว็บแสดงเฉพาะข้อมูลจาก backend ถ้า backend ไม่ทำงาน หน้าเว็บจะแสดง "ไม่สามารถโหลดข้อมูลการตรวจสอบได้"

### 3. Docker (ใช้แทนข้อ 1–2)

`compose.yaml` สร้าง 2 container คือ `backend` (FastAPI) และ `frontend` (nginx เสิร์ฟหน้าเว็บที่ build แล้ว และส่ง `/api` ต่อให้ backend) **ไม่มี MongoDB ใน compose**: Mornitor ต่อกับ MongoDB ที่มีข้อมูลของ Import Service อยู่แล้ว

```bash
cp .env.example .env     # แก้ MORNITOR_DB_URI / MORNITOR_DB_NAME ให้ตรงกับ database ของ Import Service
docker compose up -d --build
# หน้าเว็บ http://localhost:8080/  ·  API http://localhost:8000/api/monitor  ·  เอกสาร API http://localhost:8000/docs
docker compose logs -f backend   # error log (stderr)
docker compose down              # หยุดและลบ container (ไม่แตะ database)
```

- **MongoDB บนเครื่องเดียวกัน:** ใน container คำว่า `localhost` คือตัว container เอง ให้ใช้ `mongodb://host.docker.internal:27017` (ค่าเริ่มต้นใน `.env.example`)
  - Docker Desktop (macOS / Windows) ต่อ MongoDB ที่เปิดแค่ `127.0.0.1` ได้เลย
  - Linux: `compose.yaml` ผูก `host.docker.internal` กับ `host-gateway` แล้ว แต่ MongoDB ต้องรับการเชื่อมต่อจาก Docker bridge ด้วย (เช่น `bindIp: 127.0.0.1,172.17.0.1` ใน `mongod.conf`) · ทดสอบแล้วเฉพาะ Docker Desktop บน macOS
  - ถ้า MongoDB ของ Import Service อยู่ใน Docker Compose อื่น ให้เปิดพอร์ต 27017 ของมันออกมาที่เครื่อง แล้วใช้ `host.docker.internal` แบบเดียวกัน
- **พอร์ตเปิดเฉพาะ `127.0.0.1`** (เครื่องนี้เท่านั้น) เพราะ API ยังไม่มี authentication เปลี่ยนพอร์ตได้ด้วย `MORNITOR_WEB_PORT` / `MORNITOR_API_PORT`
- **`.env` ไม่ถูก commit** (อยู่ใน `.gitignore`) และไม่ถูกคัดลอกเข้า image ค่า database ส่งให้ container ตอนรันเท่านั้น
- **การเขียน:** backend เขียนเฉพาะ `monitoring_results` (เมื่อกดยืนยัน / บันทึก User Review / บันทึกผล) ถ้าไม่ต้องการให้เขียนใน database ของ Import Service ให้ตั้ง `MORNITOR_RESULTS_DB_URI` / `MORNITOR_RESULTS_DB_NAME` ใน `.env`
- **Image:** backend = `python:3.11-slim` + แพ็กเกจตาม `requirements.txt` ที่ล็อกเวอร์ชันด้วย `requirements-dev.lock.txt` รันด้วย user ที่ไม่ใช่ root · frontend = build ด้วย `node:22-slim` แล้วเสิร์ฟด้วย `nginx:stable-alpine`

## หน้าเว็บ (routes)

แถบบนสุดมีลิงก์ **AUN-QA** (ไปหน้าแรก) และเมื่ออยู่ในส่วน PS (`/monitor/ps…`) มีลิงก์ **PS-01 … PS-09** ไปหน้ารายละเอียด ทุกลิงก์คง `?curriculumCode=` เดิมไว้ หน้าเว็บเป็นภาษาไทย

| URL | หน้า |
|---|---|
| `/` | หน้าแรก "เลือกส่วนที่ต้องการดู": การ์ด P1 P2 P3 P4 P8 PS (ไม่เรียก API) |
| `/monitor` | redirect ไป `/` (คง query เดิม) |
| `/monitor/ps` | ภาพรวมเกณฑ์ PS: หัวหน้า · แถบ "ข้อมูลยังไม่ครบถ้วน" (เมื่อ backend บอก) · ข้อมูลหลักสูตร · ความพร้อมของหลักสูตร · การ์ดเกณฑ์ PS · สถานะหลักฐาน คู่กับ ข้อมูลที่ยังขาด · ความครบถ้วนของข้อมูล |
| `/monitor/ps/:psCode` | รายละเอียด PS 11 ส่วน: หัว · สิ่งที่เกณฑ์ต้องการ · ผลการตรวจสอบ · ทำไมจึงได้ผลนี้ · เกณฑ์นี้ตรวจสอบอะไร · เงื่อนไขที่ใช้ตัดสิน · สิ่งที่ระบบตรวจพบ · การยืนยันข้อมูล · ยังขาดข้อมูลสำหรับตรวจสอบ · หลักฐานที่ใช้ประกอบการตรวจสอบ · แหล่งที่มาของข้อมูล (API ตอบ `404` → ทุกส่วนแสดง "กำลังรอข้อมูล") |
| `/monitor/p1` `p2` `p3` `p4` `p8` | แจ้งว่ายังไม่มีข้อมูลสำหรับส่วนนี้ (ไม่เรียก API ไม่มีสถานะหรือตัวเลข) |
| URL อื่น (รวม `/monitor/p5`–`p7`) | redirect ไป `/` |

- ตัวเลขบนหน้าเป็น**การนับ**ค่าที่ backend ส่งมาเท่านั้น และ frontend ไม่ประเมินสถานะเอง "ความพร้อม" แสดง `programmeReadiness` ที่ backend คำนวณ (จำนวน PS ที่เป็น PASS ÷ 9 × 100; N/A, FAIL, REVIEW และ PS ที่ไม่มีผลไม่นับ) ไม่มีค่าจาก backend จะแสดง "—"
- "สิ่งที่ระบบตรวจพบ" บนการ์ดสร้างจาก `verification.found` และ `traceability` เท่านั้น โดยใช้ชื่อภาษาไทยจาก `frontend/src/app/sourceLabels.js` และ `fieldLabels.js` (ใช้แสดงผลเท่านั้น) field ที่ไม่อยู่ในตาราง เช่น ObjectId จะไม่แสดงบนการ์ด
- รายการส่วนบนหน้าแรกอยู่ที่ `frontend/src/app/criteriaGroups.js` (โครงสร้างเมนูเท่านั้น ไม่มี PS code)
- **การ์ด PS-01…PS-09 แสดงครบเสมอ:**
  - รายการ PS code อยู่ที่ `frontend/src/app/psGuideline.js` (PS code เท่านั้น)
  - PS ที่ backend ส่งผลมาแสดงผลจาก backend
  - PS ที่ backend ไม่ได้ส่งผลมาแสดง "—" และ "ยังไม่มีผลการตรวจสอบ" ไม่มีสถานะ
  - ถ้า database ยังว่าง ทุกการ์ดเขียนว่า "กำลังรอข้อมูล" / "รอผู้ใช้อัปโหลดข้อมูล"
- **ข้อความ "สิ่งที่เกณฑ์ต้องการ":**
  - ใช้ `requirement` จาก API ก่อนเสมอ
  - ถ้า API ไม่ได้ส่งมา ใช้ข้อความที่ล็อกไว้ใน `frontend/src/app/psTitles.js` (เจ้าของ project ตัดสินใจ 2026-09-25)
  - ถ้า configuration เปลี่ยน test (`guideline.test.jsx`, `psTitles.test.jsx`) จะ fail จนกว่าจะแก้สองไฟล์นี้ให้ตรง
- **อ่านข้อมูลใหม่อัตโนมัติ:** ระหว่างที่เปิดหน้าภาพรวม PS หรือหน้ารายละเอียดอยู่ หน้าเว็บส่ง `GET` ใหม่ทุก 10 วินาที (`RETRY_MS` ใน `frontend/src/api/useRemote.js`) **ตลอดเวลา ไม่หยุดเมื่อได้ผลครั้งแรก** เพราะฝั่งนำเข้าอาจเขียนข้อมูลทีละส่วน ผลบนหน้าจึงตามผลล่าสุดของ backend เอง (เช่น FAIL → PASS) โดยไม่ต้อง reload และไม่กระพริบกลับไปหน้าโหลด ใต้หัวหน้ามีบรรทัด "อัปเดตอัตโนมัติทุก 10 วินาที · ตรวจสอบล่าสุด …"
- **หลายหลักสูตร (API `409`):** หน้าเว็บแสดง "พบหลายหลักสูตรในฐานข้อมูล · กรุณาระบุ curriculumCode ใน URL" ไม่ใช่ข้อความโหลดไม่ได้ และไม่แสดงรายชื่อหลักสูตร เพราะ API ไม่ได้ส่งรายชื่อมา

## ตัวแปรสภาพแวดล้อม

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `MORNITOR_DB_URI` | `mongodb://localhost:27017` | MongoDB ของข้อมูลต้นทาง (Import Service) |
| `MORNITOR_DB_NAME` | `mornitor_source` | ชื่อ database ของข้อมูลต้นทาง |
| `MORNITOR_CONFIG_DB_URI` / `MORNITOR_CONFIG_DB_NAME` | ใช้ค่าเดียวกับ source | ตำแหน่งของ `ps_requirements` ถ้าเก็บแยก database |
| `MORNITOR_RESULTS_DB_URI` / `MORNITOR_RESULTS_DB_NAME` | ใช้ค่าเดียวกับ source | ตำแหน่งของ `monitoring_results` (ที่เดียวที่ backend เขียน) ถ้าเก็บแยก database |
| `MORNITOR_YEAR_OFFSET` | `543` | ค่าที่บวกกับปีของเครื่อง เพื่อได้ `currentYear` ในปฏิทินเดียวกับข้อมูล (ข้อมูลเป็น พ.ศ. จึงใช้ 543; ถ้าข้อมูลเป็น ค.ศ. ให้ตั้งเป็น `0`) |
| `MORNITOR_CORS_ORIGINS` | `http://localhost:5173` | ใช้เฉพาะเมื่อ frontend เรียก backend ข้าม origin |
| `MORNITOR_WEB_PORT` / `MORNITOR_API_PORT` (Docker) | `8080` / `8000` | พอร์ตบนเครื่องของหน้าเว็บและ API เมื่อใช้ `docker compose` (เปิดเฉพาะ `127.0.0.1`) |
| `MORNITOR_API_TARGET` (frontend) | `http://localhost:8000` | ปลายทาง proxy `/api` ของ `npm run dev` และ `npm run preview` |
| `VITE_API_BASE_URL` (frontend, ตอน build) | `/api` | ใช้เมื่อ backend อยู่คนละ host |

## Error Logging

backend log **เฉพาะ error** ลง stderr (logger `app`): `<เวลา> <LEVEL> <module> [<category>] <message>` + traceback · ERROR = `data_source_error`, `connection_error` (ทุก `503`), `evaluation_error`, `system_error` (`500`) · WARNING = `configuration_error` · ไม่ log request ปกติ, ผล PASS / FAIL / REVIEW / N/A, header, body หรือข้อมูลเอกสาร และซ่อน user:password ใน URL · ไม่เก็บ log ใน database และไม่ส่งออกภายนอก (`backend/app/error_log.py`)

## API (contract ชั่วคราว)

**Document Generation (pull):** เรียก `GET /api/monitor?curriculumCode=…` แล้วอ่านเฉพาะ `generationReadiness.status` (`READY` → ดึงข้อมูลจาก DB ของตัวเองแล้ว Generate · `NOT_READY` → ไม่ Generate) Mornitor ไม่ส่งข้อมูลไปหา Generator (รายละเอียด `docs/source-of-truth/API.md` §3.2)

| Method + Path | ผลลัพธ์ |
|---|---|
| `GET /api/monitor[?curriculumCode=…]` | `{ curriculum, overallStatus, dataCompleteness, results[], generationReadiness, programmeReadiness }` โดย `results` เรียงตาม PS ที่ active ใน configuration |
| `GET /api/monitor/ps/{psCode}[?curriculumCode=…]` | ผลของ PS นั้น; ไม่มีเกณฑ์นี้หรือไม่มีหลักสูตร ได้ `404` |
| `POST /api/monitor/results[?curriculumCode=…]` | ประเมินตอนนี้แล้วบันทึก `status` ของทุก PS ใน `monitoring_results` (`result: {status, evaluatedAt}`, ครั้งล่าสุดเท่านั้น) · `GET` อ่านกลับเป็น `persistedResult` · ไม่มีผลต่อการตรวจหรือ readiness · `404` / `409` / `503` |
| `POST /api/monitor/ps/{psCode}/review[?curriculumCode=…]` body `{"status": …}` | บันทึกผลที่ผู้ตรวจเลือก (เฉพาะ PS ที่ config ให้ผู้ใช้ตรวจ: PS-03; ค่าต้องอยู่ใน `allowManualResult`) ใน `monitoring_results` · `status` ของ PS และ readiness ไม่เปลี่ยน · `400` / `422` / `503` |
| `POST /api/monitor/ps/{psCode}/verification[?curriculumCode=…]` | บันทึกการยืนยันของผู้ใช้ใน `monitoring_results` (กดซ้ำไม่สร้างรายการใหม่) แล้วตอบผลของ PS นั้น · ไม่เปลี่ยนสถานะ, evidence หรือ readiness · บันทึกไม่ได้ `503` |
| DB ติดต่อไม่ได้ | `503` "Unable to load monitoring data" (**ไม่ใช่ FAIL**) |
| มีหลายหลักสูตรแต่ไม่ได้ระบุ `curriculumCode` | `409` (SPEC GAP: ยังไม่ได้กำหนดว่าต้องเลือกหลักสูตรไหน) |

field ในผลของแต่ละ PS:

`psCode, status, requirement, checks, dataSummary, dataFound, verification, missingInformation, evidence, traceability, dataCompleteness, issue, reviewRequired, reviewByUser, review, persistedResult`

`evidence` คือเอกสารของหลักสูตรจาก collection `documents` (`{label: fileName, reference: _id, storage, path}` จาก `originalFile`) อ่านอย่างเดียว ทุก PS ได้รายการเดียวกัน · `verification.verified` มาจากการกดยืนยัน (`approved` เป็น `null` เสมอ)

### อ่าน status และ issue อย่างไร

| status | issue | ความหมาย |
|---|---|---|
| PASS / FAIL | `null` | ข้อมูลผ่าน / ไม่ผ่านเงื่อนไขใน configuration |
| REVIEW | `null` | ต้องมีคนดูข้อมูล เช่น เกณฑ์กำหนดให้ผู้ใช้ตรวจ หรือข้อมูลไม่พอให้ตัดสิน |
| REVIEW | `spec_gap` | configuration ขอสิ่งที่ specification ยังไม่ได้กำหนด ต้องแก้ spec/config ก่อน |
| REVIEW | `configuration_error` | configuration ผิดรูปแบบหรือไม่ครบ ต้องแก้ config ก่อน |
| REVIEW | `evaluation_error` | ระบบประมวลผลเกณฑ์นี้ไม่สำเร็จ แต่เกณฑ์อื่นยังแสดงผลตามปกติ ให้ส่ง log ของ backend และข้อความใน Missing Information ให้ผู้พัฒนา |
| N/A | `null` | configuration อนุญาตให้เป็น N/A และไม่มีข้อมูลที่ต้องตรวจ (เช่น ไม่มีอาจารย์พิเศษ) |

`overallStatus` จะเป็น `null` เสมอ เพราะยังไม่มีการกำหนดกฎรวมผลทั้งหลักสูตร (SPEC GAP) ส่วน Programme Readiness อยู่ใน `programmeReadiness` และความพร้อมสำหรับระบบสร้างเอกสารอยู่ใน `generationReadiness` (คนละค่ากัน)

## การทดสอบอัตโนมัติ

| ส่วน | คำสั่ง | ผลล่าสุด (2026-09-26) |
|---|---|---|
| Backend | `cd backend && .venv/bin/python -m pytest` | 1033 passed (รวม 19 test ที่ต้องมี `mongod`, 300 กรณีสุ่มค่าผิดรูปแบบ, 12 test ของไฟล์ Docker และ 113 test รูปแบบวุฒิ / ปีของ PS-05 / PS-07 ซึ่งมี 1 test ที่อ่าน `DB-DATA/`) |
| Frontend | `cd frontend && npm test` | 339 passed (19 ไฟล์) |
| Build | `cd frontend && npm run build` | ผ่าน |
| Docker | `docker compose build` แล้วตรวจตาม [docs/TESTING.md](docs/TESTING.md) §0.1 | ผ่าน (backend test ใน `python:3.11-slim`: 901 passed, 19 ข้ามเพราะ container ไม่มี `mongod`) |

- **11 test ใน `tests/test_backend_parity.py`** เทียบผลกับ MongoDB จริง ชุดนี้จะรันเองเมื่อเครื่องมี `mongod` ถ้าไม่มีจะถูกข้าม
- **`tests/fixtures/ps_config_v1.json`** เป็นไฟล์ configuration **ACTIVE** ของ project
  - ใช้โดย test, `scripts/seed_test_data.py` และ test ของ frontend
  - ต่างจากไฟล์ต้นฉบับของเจ้าของ project เฉพาะ PS-08 ตามที่บันทึกใน `tests/fixtures/PROVENANCE.md`
  - แอป**ไม่ได้อ่านไฟล์นี้ตอนทำงาน**: runtime อ่าน collection `ps_requirements` ใน MongoDB
  - snapshot สำหรับเอกสารอยู่ที่ `docs/source-of-truth/PS-Config.json`

## โครงสร้าง

```text
backend/app/
  api/            routes (GET + POST results / verification / review) + composition root
  services/       load configuration + data → engine; evidence, readiness, user review
  monitoring/     generic engine (ไม่มี business vocabulary; ตรวจโดย tests/test_architecture.py)
  repositories/   อ่านอย่างเดียว: ConfigurationRepository, SourceDataRepository · MonitoringResultRepository (monitoring_results)
  adapters/       MongoDB (source/config: find เท่านั้น; monitoring_results: ที่เดียวที่เขียน), External Service A/B (TBD; Document Generation ใช้ pull)
  models/         API schema, Data Schema (source_schema.py)
frontend/src/
  api/            client (GET; POST เฉพาะ saveResults / verifyPS / reviewPS) + adapter
  app/            routing, layout, criteriaGroups.js, sourceLabels.js / fieldLabels.js (ป้ายไทย ใช้แสดงผลเท่านั้น)
  pages/          Home, MONITOR (ภาพรวม PS), PS Detail, ScopeNotice (P1 P2 P3 P4 P8)
  components/     PSCard, GuideCard, Status, IssueBadge, Traceability, ... (DataFound/ เหลือแค่ summaryLabels.js)
docs/             SPEC_GAPS.md, TESTING.md, source-of-truth/ (SRS, SCOPE, Data-Schema, API, ARCHITECTURE, PS-Config)
compose.yaml      backend + frontend (ไม่มี MongoDB) · .env.example = ค่าที่ต้องตั้ง
backend/Dockerfile, frontend/Dockerfile, frontend/nginx.conf
```
