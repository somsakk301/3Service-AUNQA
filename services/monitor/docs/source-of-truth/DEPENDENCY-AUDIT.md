# DEPENDENCY-AUDIT — ตรวจการอ้างอิงก่อนลบหรือย้ายไฟล์

> **สถานะเอกสาร:** จัดทำ 2026-09-26 · **ไม่มีการลบหรือย้ายไฟล์ในขั้นตอนนี้**
> **วิธีตรวจ:** ค้นชื่อไฟล์และชื่อ symbol ทั้ง repository (ยกเว้น `node_modules`, `.venv`, `dist`, `.git`) แล้วแยกตามชนิดการอ้างอิง

| ชนิดการอ้างอิง | ผลการค้นทั้ง repository |
|---|---|
| dynamic import | ไม่พบ `import(` ใน `frontend/src` / `vite.config.js` และไม่พบ `importlib` / `__import__` ใน `backend/app` / `backend/scripts` |
| build reference | `frontend/vite.config.js` (plugin `react`, `tailwindcss`) และ `frontend/index.html` (`/src/main.jsx`) |

## 1. คำเตือน: ไฟล์หลักที่ยังไม่ได้ commit

ไฟล์ต่อไปนี้**ไม่อยู่ใน git** (untracked) แต่ app หรือ test ใช้งานอยู่ ถ้ารัน `git clean` หรือลบโดยไม่ตั้งใจ ระบบจะเสีย:

| ไฟล์ | ถูกใช้โดย |
|---|---|
| `frontend/src/app/explain.js` | `PSCard.jsx`, `PSDetailPage.jsx` |
| `frontend/src/app/missingText.js` | `MissingInformation.jsx`, `MissingOverview.jsx` |
| `frontend/src/app/psGuideline.js` | `Layout.jsx`, `GuideCard.jsx`, `MonitorPage.jsx`, `cardList.js`, `PSDetailPage.jsx` |
| `frontend/src/app/psTitles.js` | `PSCard.jsx`, `GuideCard.jsx`, `PSDetailPage.jsx` |
| `frontend/src/components/GuideCard/*` | `MonitorPage.jsx` |
| `frontend/src/pages/Monitor/cardList.js` | `MonitorPage.jsx` |
| `backend/scripts/seed_test_data.py` | เครื่องมือสร้างข้อมูลทดสอบ (`PROVENANCE.md`, เอกสาร source-of-truth) |
| test 5 ไฟล์ + `test/fixtures/backend-sample.json` | ชุด test ของ frontend |

## 2. ผลตรวจรายไฟล์

| ไฟล์ / สิ่งที่ตรวจ | import | test | script | config / build | documentation | สรุป |
|---|---|---|---|---|---|---|
| `backend/tests/fixtures/ps_config_v1.json` (config ACTIVE) | — | `tests/support/fixtures.py`:18, `guideline.test.jsx`:15, `psTitles.test.jsx`:28 | `seed_test_data.py`:42 | — | README, SPEC_GAPS, PROVENANCE, source-of-truth | **ห้ามลบ** |
| `backend/tests/fixtures/PROVENANCE.md` | — | อ้างใน `fixtures.py` (docstring) | — | — | source-of-truth | **ห้ามลบ** |
| `docs/source-of-truth/PS-Config.json` | ไม่มี code อ่าน | — | — | — | เอกสาร source-of-truth | **ห้ามลบ** (snapshot สำหรับเอกสาร) |
| `frontend/src/app/psGuideline.js` | 5 ไฟล์ | `guideline.test.jsx` | — | — | README, SPEC_GAPS | **ห้ามลบ** |
| `frontend/src/app/psTitles.js` | 3 ไฟล์ | `psTitles.test.jsx` | — | — | source-of-truth | **ห้ามลบ** (ข้อความสำรองที่ตั้งใจออกแบบ) |
| `frontend/src/components/DataFound/summaryLabels.js` | `PSDetailPage.jsx`:9 (`NOTE_LABELS`, `OPERATION`); อ้างใน comment ของ `explain.js`:10 | — | — | — | README:158 | **ห้ามลบ** ถ้าจะย้ายต้องแก้ import ใน `PSDetailPage.jsx` |
| `frontend/src/types/monitoring.js` | `adapter.js`, `ProgrammeReadiness.jsx` | `status.test.jsx` | — | — | — | **ห้ามลบ** |
| `backend/app/monitoring/manual.py` | `monitoring_service.py`, `context.py` | ใช้ผ่าน `ManualResults` ใน test | — | — | SPEC_GAPS §4.3 | **ห้ามลบ** (port ของผลผู้ตรวจ แม้ production ไม่มีที่เก็บ) |
| `backend/app/monitoring/reference.py` | `monitoring_service.py`, `context.py` | `test_generic_capabilities.py` | — | — | — | **ห้ามลบ** |
| `backend/app/adapters/external_services.py` | **ไม่มี** | ไม่มี | ไม่มี | ไม่มี | README (โครงสร้าง), [SRS-M] §6 | **ต้องตรวจเพิ่ม:** ไม่มีใครเรียก แต่เป็นจุดเชื่อมที่ SRS §6 กำหนด (TBD) ให้เจ้าของ project ตัดสิน |
| `frontend/src/test/fixtures/backend-sample.json` | — | `humanreadable.test.jsx`:5, `monitor.test.jsx`:6 | — | — | — | **ห้ามลบ** (ควรสร้างใหม่จาก config ACTIVE ในรอบแก้ test) |
| `backend/scripts/seed_test_data.py` | ไม่มี code ของ app import | — | เป็น script เอง | — | PROVENANCE, source-of-truth | **ห้ามลบ** |
| `frontend/src/app/tailwind.css` | `main.jsx`:5 | — | — | Tailwind v4 (`@import "tailwindcss/…"`) | — | **ต้องตรวจเพิ่ม:** ไม่มี component ใช้ class ของ Tailwind (ใน build มีแค่ `.visible` / `.fixed` จากคำใน comment) ถ้าจะลบต้องลบ import ใน `main.jsx` ด้วย |
| package `tailwindcss`, `@tailwindcss/vite` | — | — | — | `package.json`, `package-lock.json`, `vite.config.js` (plugin) | README (ไม่ได้กล่าวถึง) | **ต้องตรวจเพิ่ม** พร้อม `tailwind.css` แล้ว build และ test ใหม่ |
| CSS class `.mono` (`styles.css`:20) | ไม่มี component ใช้ | `styles.test.js` อ่านทั้งไฟล์ `styles.css` แต่ไม่ตรวจ `.mono` | — | — | — | **ปลอดภัยที่จะลบ** เมื่อเปิดรอบแก้ CSS (ต้องรัน `styles.test.js` ใหม่) |
| แม่แบบ "the extraction source … is blank" ใน `missingText.js` | ส่วนหนึ่งของ `missingText.js` ที่ใช้อยู่ | `missing.test.jsx` (ตรวจข้อความ backend ที่รู้จัก) | — | — | API.md §7 | **ต้องตรวจเพิ่ม:** ไม่เคยตรงข้อความจริงของ backend การแก้เป็นการเปลี่ยนพฤติกรรมหน้าเว็บ ต้องให้เจ้าของ project สั่ง |
| field `checks`, `traceability[].values` ใน `adapter.js` | `adapter.js` | `values`: `adapter.test.js`:6–10 · `checks`: ไม่มี test | — | — | API.md §9 | **ห้ามลบ:** เป็นส่วนของ API contract (`values` มี test ตรวจ) |
| `docs/SPEC_GAPS.md` | `backend/app/models/schemas.py`:1 (docstring) | — | — | — | README, CHANGELOG | **ห้ามลบ** |
| `docs/TESTING.md` | — | อ้างใน `PROVENANCE.md` | — | — | README, CHANGELOG | **ห้ามลบ** |

## 3. ไฟล์ที่ถูกลบแล้ว (อยู่ใน working tree ยังไม่ commit)

| ไฟล์ที่ลบ | การอ้างอิงที่เหลือ | สรุป |
|---|---|---|
| `frontend/mock/mockBackend.js` | `CHANGELOG.md`:90 เท่านั้น (บันทึกของ 0.3.0) | ไม่มี code, test, config หรือ script ใดอ้างถึง ลบได้ถูกต้อง |
| `frontend/src/components/Requirement/*` | ไม่มี | ลบได้ถูกต้อง |
| `frontend/src/components/PSCard/detected.js`, `test/detected.test.jsx` | ไม่มี | ลบได้ถูกต้อง |
| `frontend/src/components/DataFound/DataFound.jsx`, `index.js` | README:158 (ชื่อ component ในโครงสร้าง) | code ไม่อ้างถึง แต่ README ต้องแก้ (DOCUMENTATION-SYNC) |

## 4. ไฟล์นอก repository

| ไฟล์ | สรุป |
|---|---|
| `~/Mornitor-Data/*.md` (SRS, Data Dictionary, Data Schema, OOAD, Forntend) | **ห้ามลบ:** เป็นแหล่ง Intended Scope |
| `~/Mornitor-Data/PS-Config-v1(3)-PS08-updated(3)-degree-ordering.json` | **ห้ามลบ:** ต้นฉบับจากเจ้าของ project |
| config รุ่นเก่าใน `~/Downloads` (ดู [PS-Config.json](PS-Config.json) `configurationFiles`) | **ต้องตรวจเพิ่ม:** ไม่มี code ใดอ้างถึง ความสัมพันธ์กับ version ปัจจุบัน: ข้อมูลไม่เพียงพอ |

## 5. สรุป

| กลุ่ม | ไฟล์ |
|---|---|
| **ห้ามลบ** | config ACTIVE, PROVENANCE, PS-Config.json, psGuideline.js, psTitles.js, summaryLabels.js, types/monitoring.js, manual.py, reference.py, backend-sample.json, seed_test_data.py, SPEC_GAPS.md, TESTING.md, ไฟล์ untracked ทั้งหมดในข้อ 1, เอกสารใน `Mornitor-Data` |
| **ปลอดภัยที่จะลบ (เมื่อเปิดรอบแก้ code)** | CSS class `.mono` |
| **ต้องตรวจเพิ่ม / ให้เจ้าของ project ตัดสิน** | `external_services.py`, Tailwind (`tailwind.css` + 2 package), แม่แบบ extraction ใน `missingText.js`, config เก่าใน `~/Downloads` |
