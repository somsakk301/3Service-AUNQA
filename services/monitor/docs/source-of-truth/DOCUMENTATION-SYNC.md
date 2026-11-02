# DOCUMENTATION-SYNC — เอกสารเดิมเทียบกับ Source of Truth

> **สถานะเอกสาร:** จัดทำ 2026-09-26 · เทียบเอกสารเดิมกับ source code, test และ [SRS.md](SRS.md) / [API.md](API.md) / [PS-Config.json](PS-Config.json)
> เลขบรรทัดอ้างอิงเนื้อหา **ก่อน** แก้ในรอบนี้ · แถวที่มี "✔ แก้แล้ว" ได้แก้ในไฟล์นั้นแล้วเมื่อ 2026-09-26
> ไม่มีไฟล์ `docs/CHANGELOG.md` · CHANGELOG ของโครงการอยู่ที่ `CHANGELOG.md` (root)

ค่าในคอลัมน์ Action:
- **แก้เอกสาร** = ข้อความผิดจากพฤติกรรมจริงที่ยืนยันแล้ว
- **คงไว้ (ประวัติ)** = บันทึกของเวอร์ชันเก่าที่ถูกต้องในเวลานั้น ไม่แก้ย้อนหลัง
- **รายงาน (code)** = อยู่ในไฟล์ code หรือ test ไม่แก้ในรอบเอกสาร

## README.md

| File | Outdated Content | Current Truth | Action |
|---|---|---|---|
| README.md:12 | "โค้ดไม่มีเกณฑ์ ค่า threshold, role หรือรายการ PS เขียนตายตัวไว้เลย" | engine ไม่มี; frontend มีรายการ PS code (`psGuideline.js`) และข้อความ requirement สำรอง (`psTitles.js`) สำหรับแสดงผล | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md:77 | แถบบนสุดมี **AUNQA** และแท็บ **หน้าแรก** | แถบบนมีลิงก์ **AUN-QA** (ไปหน้าแรก) และลิงก์ PS-01…PS-09 เมื่ออยู่ในส่วน PS (`frontend/src/app/Layout.jsx`) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md:84 | รายละเอียด PS **9 ส่วน** | **11 ส่วน**: หัว · สิ่งที่เกณฑ์ต้องการ · ผลการตรวจสอบ · ทำไมจึงได้ผลนี้ · เกณฑ์นี้ตรวจสอบอะไร · เงื่อนไขที่ใช้ตัดสิน · สิ่งที่ระบบตรวจพบ · การยืนยันข้อมูล · ยังขาดข้อมูล · หลักฐาน · แหล่งที่มาของข้อมูล (`PSDetailPage.jsx`) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md:91 | ข้อกำหนดของแต่ละเกณฑ์ "คัดจาก `PS-Config-v1.json`" อยู่ใน `psGuideline.js`; การ์ดจาก backend "แทนที่ทั้งหมด" | `psGuideline.js` มีแค่ PS code; ข้อความ requirement สำรองอยู่ใน `psTitles.js` (เจ้าของ project ตัดสินใจ 2026-09-25) ใช้เฉพาะเมื่อ API ไม่ส่ง requirement; การ์ด PS-01…PS-09 แสดงครบเสมอ PS ที่ไม่มีผลแสดง "—" (`cardList.js`) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md:137–138 | backend 602 passed / 11 skipped (613 เมื่อมี `mongod`); frontend 124 passed (2026-09-23) | backend **657 passed** (รวม 11 test ที่ต้องมี `mongod`); frontend **230 passed** (2026-09-26) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md:142 | `ps_config_v1.json` "เป็นสำเนาของ PS-Config-v1.json ... ห้ามแก้" | เป็นไฟล์ configuration **ACTIVE** ของ project; ต่างจากไฟล์ต้นฉบับเฉพาะ PS-08 ตามที่บันทึกใน `backend/tests/fixtures/PROVENANCE.md`; runtime อ่าน `MongoDB.ps_requirements` ไม่อ่านไฟล์นี้ | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md:158 | components: "PSCard, Status, IssueBadge, **DataFound**, Traceability" | `DataFound.jsx` ถูกลบแล้ว เหลือ `components/DataFound/summaryLabels.js`; มี `GuideCard` เพิ่ม | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| README.md (ต้นไฟล์) | ไม่มีลิงก์ไปเอกสาร Source of Truth | `docs/source-of-truth/` | แก้เอกสาร (เพิ่มลิงก์) · ✔ แก้แล้ว 2026-09-26 |

## docs/SPEC_GAPS.md

| File | Outdated Content | Current Truth | Action |
|---|---|---|---|
| SPEC_GAPS.md:3 | Source of Truth: `PS-Config-v1.json` | config ACTIVE: `backend/tests/fixtures/ps_config_v1.json`; runtime: `MongoDB.ps_requirements`; snapshot: `docs/source-of-truth/PS-Config.json` | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:40 (§1) | `{source, required}` "shown, never judged" เป็น construct เดียวของ PS-08; ไม่มี `{field, minimum, ordering}` | มี construct `{source, required, condition}` (ตัดสินด้วย EXISTS หรือ operator + value) และ `{field, minimum, ordering}` (`subject_interpreter.py`) | แก้เอกสาร (เพิ่มแถว) · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:59 (§2) | PS-05: PASS / REVIEW | PASS / FAIL / REVIEW ตาม `degree.ordering` (bachelor < master < Ph.D.) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:62 (§2) | PS-08: N/A / REVIEW / (user's choice) | N/A / PASS / FAIL / REVIEW: มีคุณวุฒิ (`educations.degree` EXISTS) และ `persons.hasTeachingExperience == true` | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:80 (§3.10) | at-least ตัดสินได้เฉพาะความเท่ากัน | เมื่อ config มี `ordering` ใช้ตำแหน่งใน ordering; ไม่มี ordering จึงเท่ากับ minimum เท่านั้น | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:82 (§3.12) | "Manual review required…" (PS-08) | PS-08 ไม่เป็น manual review แล้ว เหลือเฉพาะ PS-03 | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:88 (§4.1) | Degree ordering ยังเปิดอยู่ | ปิดแล้ว: config กำหนด `ordering: [bachelor, master, Ph.D.]` (จับคู่ตรงตัวอักษร ระดับละ 1 คำสะกด) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:89 (§4.2) | PS-08 ไม่มีเกณฑ์ ผู้ใช้ตัดสิน | ปิดแล้วตาม business rule ของเจ้าของ project 2026-09-25: ตรวจว่ามีคุณวุฒิจาก `educations.degree` และ `hasTeachingExperience` เป็น true ไม่ตรวจจำนวนปี ประเภท หรือความเกี่ยวข้อง | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:90 (§4.3) | Manual review results (PS-03, **PS-08**) | เหลือเฉพาะ PS-03 | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:96 (§4.8) | "The frontend holds no PS list … the top bar lists criteria groups only" | frontend มีรายการ PS code (`psGuideline.js`) และแถบบนแสดงลิงก์ PS-01…PS-09 ในส่วน PS | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:100 (§4.9) | "`Forntend.md` itself was not in the delivered files" | ปัจจุบันไฟล์อยู่ที่ `~/Mornitor-Data/Forntend.md` | แก้เอกสาร (หมายเหตุ) · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:130–136 (§4.11) | ข้อความ requirement คัดจาก `PS-Config-v1.json` ไว้ใน `psGuideline.js` | `psGuideline.js` มีแค่ PS code; ข้อความสำรองอยู่ใน `psTitles.js`; ข้อความจาก API ใช้ก่อนเสมอ; `psTitles.test.jsx` ตรวจว่าตรงกับ config ACTIVE | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| SPEC_GAPS.md:142 (§5) | ไฟล์ test เป็น "byte-for-byte copy … Do not edit it" | เป็นไฟล์ ACTIVE ของ project ความต่างจากต้นฉบับบันทึกใน `PROVENANCE.md` | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |

## docs/TESTING.md

| File | Outdated Content | Current Truth | Action |
|---|---|---|---|
| TESTING.md:13, 16 | นำเข้า `PS-Config-v1.json` | ไฟล์นี้ไม่มีแล้ว ใช้ `backend/tests/fixtures/ps_config_v1.json` (เป็น JSON array นำเข้าด้วย `--jsonArray` ได้) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:36 | แถบบนสุด **AUNQA · หน้าแรก** | แถบบนมีลิงก์ **AUN-QA** | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:40 | การ์ดหนึ่งใบต่อ PS ที่ active | การ์ด PS-01…PS-09 ครบเสมอ PS ที่ไม่มีผลจาก API แสดง "—" | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:47 (T-01) | หน้า `/monitor/ps` มีการ์ดตรงกับ PS ที่ `active: true` | การ์ด PS-01…PS-09 ครบเสมอ การ์ดที่มีสถานะตรงกับ PS ที่ active | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:48 (T-02) | ตั้ง `active: false` แล้ว "การ์ดของ PS นั้นหายไป" | การ์ดยังอยู่ แสดง "—" และ "ยังไม่มีผลการตรวจสอบ"; จำนวนตามสถานะไม่นับ PS นั้น (`cardList.js`, `GuideCard.jsx`) | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:54 (T-08) | การตรวจย้อนกลับแสดง "`ป้ายไทย (หรือชื่อ field) = ค่าจริง`" | ตารางแสดงแหล่งข้อมูล, "รายการที่ N" + รหัสอ้างอิง และชื่อข้อมูลที่ใช้ตรวจ **ไม่แสดงค่า** (`Traceability.jsx`: "Raw stored values … are not shown") | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:60–61, 70–73 (T-13, T-14) | PS-08 เมื่อ `experience.source: null` → Spec Gap; คำสั่ง `updateOne` ให้ตั้ง source | config ACTIVE มี source และ `condition` แล้ว: มีคุณวุฒิ + true → PASS; false หรือไม่มี record การศึกษา → FAIL; ไม่มีค่าประสบการณ์หรือ degree ว่าง → REVIEW | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:81 (§3) | PS-05 ผ่านเฉพาะ `master`; `Ph.D.` ได้ REVIEW + Spec Gap | `master`, `Ph.D.` → PASS; `bachelor` → FAIL; ค่าที่ไม่อยู่ใน ordering หรือไม่มีค่า → REVIEW | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |
| TESTING.md:83 (§3) | PS-08 ไม่ตัดสิน PASS/FAIL อัตโนมัติ | ตัดสินอัตโนมัติตาม `condition` ของ qualification และ experience | แก้เอกสาร · ✔ แก้แล้ว 2026-09-26 |

## CHANGELOG.md

| File | Outdated Content | Current Truth | Action |
|---|---|---|---|
| CHANGELOG.md (ต้นไฟล์) | รายการล่าสุดคือ 0.4.0 | มีการเปลี่ยนแปลงที่ยังไม่ commit (ยืนยันจาก `git diff`): ลบโหมด mock, อ่านใหม่ทุก 10 วินาที, การ์ด PS ครบเสมอ, `psTitles.js`, แถบบนใหม่, หน้ารายละเอียด 11 ส่วน, engine `_undecided`, PS-05 ordering, PS-08 condition, seed script, เอกสาร source-of-truth | แก้เอกสาร (เพิ่มหัวข้อ "Unreleased" ไม่กำหนดเลขเวอร์ชัน) · ✔ แก้แล้ว 2026-09-26 |
| CHANGELOG.md:15, 23, 32, 38, 83, 90 | แถบ AUNQA + หน้าแรก, 9 ส่วน, โหมด `[MOCK]` / `dev:mock` | ถูกต้องสำหรับ 0.3.0 / 0.4.0 ในเวลานั้น | คงไว้ (ประวัติ) |
| CHANGELOG.md:165–171 | คำขอแก้ configuration (PS-05 ordering, PS-08 source) | คำขอเหล่านี้เจ้าของ project ตอบแล้วใน config ACTIVE | คงไว้ (ประวัติ) และบันทึกใน Unreleased |

## Code / test (ไม่แก้ในรอบเอกสาร)

| File | Outdated Content | Current Truth | Action |
|---|---|---|---|
| `frontend/src/app/psGuideline.js`:2 (comment) | อ้าง `PS-Config-v1.json` | ไฟล์ ACTIVE คือ `backend/tests/fixtures/ps_config_v1.json` | รายงาน (code) |
| `frontend/src/test/guideline.test.jsx`:14 (comment) | "byte-for-byte copy … (PS-Config-v1.json)" | ไฟล์ ACTIVE ต่างจากต้นฉบับที่ PS-08 | รายงาน (code) |
| `backend/tests/test_ps_evaluation.py` (comment "as PS-Config-v1 had it") | อ้างชื่อไฟล์เก่า | ความหมายยังถูก (config ที่ไม่มี source) | รายงาน (code) |
| `frontend/src/test/fixtures/backend-sample.json` | สร้างจาก config รุ่นเก่า (PS-08 `experience.source: null`, ไม่มี ordering / condition) | ไม่ตรงกับ config ACTIVE | รายงาน (test fixture) |
| `backend/app/models/schemas.py`:1 | "Temporary API contract (TBD / SPEC GAP), see docs/SPEC_GAPS.md" | ยังถูกต้อง | ไม่ต้องแก้ |
