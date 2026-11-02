# คู่มือทดสอบ Mornitor สำหรับทีมอื่น (v0.4.0)

คู่มือนี้ใช้ทดสอบ Mornitor กับข้อมูลจริงของทีม ซึ่งมาจาก Import Service และ configuration `ps_requirements` วิธีติดตั้งและรันระบบอยู่ใน [README.md](../README.md)

> Mornitor **อ่านอย่างเดียว** ทุกขั้นตอนที่ต้องแก้ข้อมูลหรือ configuration ในคู่มือนี้ ให้ผู้ทดสอบทำเองบน **database สำหรับทดสอบ** เท่านั้น ห้ามทำกับ database ที่ใช้งานจริง

## 0. เตรียมระบบ

1. **MongoDB ที่มีข้อมูลต้นทาง**
   - ต้องมี collection ตาม Data Schema: `curricula`, `persons`, `educations`, `appointments`, `academic_works`, `documents`, `data_usages`, `generated_documents`
   - ถ้า Import Service รัน MongoDB ใน Docker Compose ต้องเปิดพอร์ต 27017 ออกมาที่เครื่อง แล้วตั้ง `MORNITOR_DB_URI=mongodb://localhost:27017`
   - ถ้ารัน Mornitor ด้วย Docker (§0.1) ให้ใช้ `mongodb://host.docker.internal:27017` แทน `localhost`
2. **Configuration `ps_requirements`**
   - ต้องมีเอกสาร PS-01 ถึง PS-09 ตามไฟล์ configuration ACTIVE `backend/tests/fixtures/ps_config_v1.json` (ดู `docs/source-of-truth/PS-Config.json`)
   - ถ้ายังไม่มี ให้นำเข้า test DB ด้วยคำสั่งนี้ (ทำเอง ไม่ใช่ Mornitor; ไฟล์เป็น JSON array):
     ```bash
     mongoimport --uri "mongodb://localhost:27017/<test-db>" --collection ps_requirements --jsonArray --file backend/tests/fixtures/ps_config_v1.json
     ```
   - หรือใช้ `backend/scripts/seed_test_data.py` ซึ่งเขียนได้เฉพาะ database ที่ชื่อลงท้าย `_test` และใส่ทั้ง configuration และข้อมูลทดสอบ
3. **Account แบบ read-only (แนะนำ)** ช่วยยืนยันว่า Mornitor ไม่เขียนข้อมูล
   ```javascript
   // mongosh
   use <db>
   db.createUser({ user: "mornitor_ro", pwd: passwordPrompt(), roles: [{ role: "read", db: "<db>" }] })
   ```
   จากนั้นตั้ง `MORNITOR_DB_URI="mongodb://mornitor_ro:<password>@localhost:27017/?authSource=<db>"`
4. **ปฏิทินของปี** ข้อมูลที่เก็บปีเป็น พ.ศ. (เช่น `curriculumYear: 2567`) ต้องใช้ `MORNITOR_YEAR_OFFSET=543` ซึ่งเป็นค่าเริ่มต้น ถ้าเก็บเป็น ค.ศ. ให้ตั้งเป็น `0` **ถ้าตั้งไม่ตรงกับข้อมูล PS-07 และ PS-09 จะคำนวณผิด**

## 0.1 รันด้วย Docker และตรวจ image

```bash
cp .env.example .env              # ตั้ง MORNITOR_DB_URI / MORNITOR_DB_NAME
docker compose up -d --build      # หน้าเว็บ :8080 · API :8000 (เฉพาะ 127.0.0.1)
```

ใน §1 เป็นต้นไป ให้ใช้ `http://localhost:8080/` แทน `:5173` (ส่วน API ใช้ `:8000` เหมือนเดิม หรือเรียกผ่าน `:8080/api/...` ก็ได้) แล้วตรวจเพิ่ม:

| ตรวจ | คำสั่ง | ผลที่ถูกต้อง |
|---|---|---|
| หน้าเว็บและ route ฝั่ง client | `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/monitor/ps/PS-01` | `200` (nginx ส่ง `index.html`) |
| `/api` ผ่าน nginx เท่ากับ API ตรง | เทียบ `curl -s "http://localhost:8080/api/monitor?curriculumCode=<รหัส>"` กับ `:8000` | ผล PS, `programmeReadiness`, `generationReadiness` เหมือนกัน |
| backend ไม่ใช่ root | `docker compose exec backend id -u` | `10001` |
| พอร์ตเปิดเฉพาะเครื่องนี้ | `docker compose ps` | `127.0.0.1:8080->80`, `127.0.0.1:8000->8000` |
| error log | `docker compose logs backend` | ไม่มีบรรทัด `ERROR` / `WARNING` เมื่อ database ใช้ได้ · ถ้าต่อ database ไม่ได้ API ตอบ `503` และมีบรรทัด `[connection_error]` ที่ไม่มีรหัสผ่าน |
| database ต้นทางไม่เปลี่ยน | นับ / hash ทุก collection ก่อนและหลังทดสอบ | เปลี่ยนได้เฉพาะ `monitoring_results` (เมื่อกดยืนยัน / บันทึก) |

ผลที่ตรวจแล้ว (2026-09-26, Docker Desktop บน macOS, database ทดสอบจาก `seed_test_data.py` ผ่าน `host.docker.internal`): ผ่านทุกข้อ และ backend test ทั้งชุดใน `python:3.11-slim` ได้ 901 passed, 19 ข้าม (test ที่ต้องมี `mongod`) · `docker compose down` เพื่อหยุด

## 1. Smoke test (ประมาณ 5 นาที)

```bash
curl -s http://localhost:8000/api/monitor | python3 -m json.tool | head -40      # 200 + curriculum + results
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/monitor   # 405 (อ่านอย่างเดียว)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/monitor/ps/PS-99  # 404
```

- ถ้าได้ `409` แปลว่า DB มีหลายหลักสูตร ให้ระบุหลักสูตรด้วย `?curriculumCode=<รหัส>` ทั้งใน API และ URL ของหน้าเว็บ เช่น `http://localhost:5173/?curriculumCode=25500231104894`
- เปิด http://localhost:5173/ แล้วควรเห็นแถบบนสุดมีลิงก์ **AUN-QA** และการ์ด P1 P2 P3 P4 P8 PS (เมื่อเข้าส่วน PS แถบบนจะมีลิงก์ PS-01 … PS-09)
- กด "เปิดดู →" บนการ์ด PS (ไปที่ `/monitor/ps`) แล้วควรเห็น:
  - ข้อมูลหลักสูตร
  - ความพร้อมของหลักสูตร (ความพร้อม "—", ผลรวม "—", จำนวนตามสถานะ)
  - การ์ด PS-01 ถึง PS-09 ครบเสมอ PS ที่ API ไม่ได้ส่งผลมาแสดง "—" และไม่มีสถานะ
  - สถานะหลักฐาน, ข้อมูลที่ยังขาด และความครบถ้วนของข้อมูล

## 2. กรณีทดสอบ

| ID | ทำอะไร | ผลที่ควรได้ | อ้างอิง SRS |
|---|---|---|---|
| T-01 | เปิดหน้าแรก `/` แล้วกด "เปิดดู →" บนการ์ด PS | หน้าแรกมีการ์ด P1 P2 P3 P4 P8 PS และไม่เรียก `/api`; หน้า `/monitor/ps` มีการ์ด PS-01 ถึง PS-09 ครบ และการ์ดที่มีสถานะตรงกับ PS ที่ `active: true` ใน `ps_requirements` | §11, §17 |
| T-02 | บน test DB ตั้ง `active: false` ให้ PS หนึ่งข้อ แล้ว reload | การ์ดของ PS นั้นยังอยู่ แต่แสดง "—" และ "ยังไม่มีผลการตรวจสอบ" (ไม่มีสถานะ) และจำนวนตามสถานะไม่นับ PS นั้น โดยไม่ต้องแก้โค้ด | §11, §42 |
| T-03 | บน test DB เปลี่ยน `config.condition.value` ของ PS-01 จาก 5 เป็นจำนวนที่มากกว่าจำนวนอาจารย์ที่มีจริง | PS-01 เปลี่ยนเป็น FAIL โดยไม่ต้องแก้โค้ด | §10 |
| T-04 | เทียบข้อความ Requirement บนการ์ดกับ `requirement` ใน DB | ตรงกันทุกตัวอักษร | §12 |
| T-05 | รันด้วย account read-only แล้วเปิดทุกหน้า | ทำงานได้ปกติ และจำนวนเอกสารใน DB ไม่เปลี่ยน | §7 |
| T-06 | ปิด MongoDB หรือตั้ง URI ผิด แล้วเปิดหน้าเว็บ | ขึ้น "ไม่สามารถโหลดข้อมูลได้" และ API ตอบ 503 **ไม่มี FAIL** | §49 |
| T-07 | เปิด PS-01 และ PS-05 | ส่วน "สิ่งที่ระบบตรวจพบ" ในหน้ารายละเอียดแสดงชื่ออาจารย์ (`persons.fullName`) ไม่ใช่ ObjectId ถ้าไม่มี record ใน `persons` จะขึ้น `<id> (ไม่พบ persons.fullName)` | §25 |
| T-08 | ดูส่วน "แหล่งที่มาของข้อมูล" ของ PS ใดก็ได้ | แต่ละ record ที่อ่านแสดงแหล่งข้อมูล, "รายการที่ N" พร้อมรหัสอ้างอิง และชื่อข้อมูลที่ใช้ตรวจเป็นภาษาไทย (หน้าเว็บไม่แสดงค่า ค่าจริงอยู่ใน `traceability[].values` ของ API) และการ์ดในหน้าภาพรวมไม่แสดง ObjectId | §29 |
| T-09 | เปิด PS-06 แล้วกด "มีความสัมพันธ์" หรือ "ไม่มีความสัมพันธ์" | ก่อนกด: REVIEW + "รอการยืนยันจากผู้ใช้" และเห็นอาจารย์ผู้รับผิดชอบแต่ละคนพร้อมระดับคุณวุฒิ สาขาวิชา สถาบัน · หลังกด: แสดง PASS / FAIL ตามที่เลือก, `status` ใน API ยังเป็น REVIEW และ `review.status` เป็นค่าที่เลือก · ชื่อหลักสูตรไม่มีผลต่อผลเลย (ไม่มี mapping) | SRS §12 |
| T-10 | บน test DB ลบ `config.result` ของ PS หนึ่งข้อ | การ์ดขึ้น REVIEW พร้อมป้าย **Configuration Error** | §48, §50 |
| T-11 | บน test DB เพิ่ม key ที่ไม่รู้จักใน `config` เช่น `"somethingNew": true` | REVIEW พร้อมป้าย **Spec Gap** | §13, §45 |
| T-11b | บน test DB ใส่ค่าผิดชนิด เช่น `config.condition.value: "5"` (ข้อความ) ของ PS-01 | PS-01 เป็น REVIEW + Configuration Error และ **PS อื่นยังแสดงผลตามปกติ** | §48 |
| T-12 | PS-08 เมื่อไม่มี appointment ที่ `role: specialInstructor` | N/A | §24 |
| T-13 | PS-08 เมื่อมีอาจารย์พิเศษที่มี `educations.degree` และ `persons.hasTeachingExperience: true` | PASS; แหล่งที่มาของข้อมูลมี record ของ `appointments`, `educations` และ `persons` | business rule ของเจ้าของ project (2026-09-25) |
| T-14 | PS-08 เมื่ออาจารย์พิเศษมี `hasTeachingExperience: false` หรือไม่มี record ใน `educations` เลย / เมื่อไม่มีค่า `hasTeachingExperience` หรือมี record การศึกษาแต่ `degree` ว่าง | FAIL / REVIEW (ข้อมูลที่ยังขาดบอกว่าขาดอะไร) ไม่ตรวจจำนวนปี ประเภท หรือความเกี่ยวข้องของประสบการณ์ | business rule ของเจ้าของ project (2026-09-25) |
| T-15 | PS-09 ดูส่วน "สิ่งที่ระบบตรวจพบ" | เห็น `currentYear = 2569` (ปี 2026 + 543) และผลลบกับ `curriculumYear` | §27 |
| T-16 | ค้นหา (Ctrl/Cmd+F) คำว่า `[MOCK]` ในทุกหน้า | ไม่พบ หน้าเว็บแสดงเฉพาะข้อมูลจาก backend (ไม่มีโหมด mock แล้ว) | §16 |
| T-17 | ที่หน้าแรก กด "เปิดดู →" บนการ์ด P1 P2 P3 P4 P8 ทีละใบ | เห็นหน้า "ยังไม่มีข้อมูลสำหรับส่วนนี้" ไม่มีสถานะ ตัวเลข หรือการ์ด; เปิด `/monitor/p5`–`p7` ต้องกลับไปหน้าแรก และใน DevTools → Network **ไม่มีการเรียก `/api`** | §11, §31 |
| T-18 | เปิดหน้าแรก `/monitor/ps` และหน้ารายละเอียด PS ใดก็ได้ แล้วค้นหา (Ctrl/Cmd+F) ตัวอักษร `%` | ไม่พบเปอร์เซ็นต์บนหน้า (ยกเว้น `%` ที่อยู่ในข้อความที่ backend ส่งมาเอง เช่น requirement ซึ่งแสดงตามที่ส่งมา) | §16 |
| T-19 | เปิด `/monitor/ps` ตอนที่ database ยังว่าง แล้วให้ฝั่งนำเข้าบันทึกข้อมูล (หรือนำเข้า test DB ตามข้อ 0) โดยไม่ต้อง reload | ระหว่างรอเห็น "ยังไม่มีข้อมูล · กำลังรอข้อมูลจากฐานข้อมูล…" พร้อมเวลาตรวจสอบล่าสุด; ภายใน 10 วินาทีหลังข้อมูลเข้า หน้าแสดงการ์ด PS เอง; ถ้าเขียนข้อมูลเพิ่มภายหลัง (เช่น อาจารย์ครบ 5 คน) ผลบนหน้าเปลี่ยนตาม (FAIL → PASS) ภายใน 10 วินาทีโดยไม่ต้อง reload; ใน DevTools → Network มีแต่ `GET` ทุก 10 วินาทีตลอดที่เปิดหน้าอยู่ | §7, §49 |
| T-20 | ใส่หลักสูตรมากกว่า 1 รายการใน database แล้วเปิด `/monitor/ps` โดยไม่ระบุ `curriculumCode` | API ตอบ `409`; หน้าเว็บขึ้น "พบหลายหลักสูตรในฐานข้อมูล" และ "กรุณาระบุ curriculumCode ใน URL" (ไม่ใช่ "ไม่สามารถโหลดข้อมูลการตรวจสอบได้"); เมื่อเติม `?curriculumCode=<รหัส>` แสดงผลของหลักสูตรนั้น | SPEC_GAPS §4.5 |

T-13 และ T-14 ต้องใช้ PS-08 ตามไฟล์ configuration ACTIVE (มี `experience.source` และ `condition` ของ qualification / experience แล้ว) ถ้า `ps_requirements` ในฐานข้อมูลยังเป็นรุ่นเก่า ให้เจ้าของ config นำ PS-08 จากไฟล์ ACTIVE เข้าไปแทนก่อน

## 3. พฤติกรรมที่ตั้งใจไว้ (ไม่ใช่บั๊ก)

ข้อเหล่านี้เกิดจาก configuration หรือ specification ปัจจุบัน ถ้าต้องการให้เปลี่ยน ต้องแก้ที่ config หรือ spec ไม่ใช่ที่โค้ด:

- **นับการแต่งตั้งทุกสถานะ** PS-01, 02, 04, 05, 06 และ 07 นับรวม appointment ที่ `status` ไม่ใช่ `active` ด้วย เพราะ config ไม่มีตัวกรองสถานะ
- **PS-03 เป็น REVIEW เสมอ** config กำหนดให้ผู้ใช้เป็นคนตรวจ และยังไม่มีที่เก็บผลที่ผู้ใช้ตัดสิน
- **PS-05 ใช้ลำดับปริญญาจาก config** (`bachelor` < `master` < `Ph.D.`, minimum `master`): `master` และ `Ph.D.` ได้ PASS, `bachelor` ได้ FAIL, ค่าที่ไม่อยู่ในลำดับแบบตรงตัวอักษร (เช่น `Master`, `PhD`, `ปริญญาโท`) หรือไม่มีค่า ได้ REVIEW
- **PS-06 ผู้ใช้เป็นผู้ยืนยัน 100%** ระบบไม่เทียบชื่อสาขาเอง engine ให้ REVIEW จนกว่าผู้ใช้จะยืนยัน PASS / FAIL (config ใน database ต้องเป็นแบบใหม่ ถ้ายังเป็นแบบ mapping เดิมจะได้ REVIEW + Spec Gap)
- **PS-08 ตรวจแค่มีคุณวุฒิและมีประสบการณ์สอนหรือไม่** (`educations.degree` มีค่า และ `persons.hasTeachingExperience` เป็น `true`) ไม่ตรวจจำนวนปี ประเภท หรือความเกี่ยวข้องของประสบการณ์
- **ช่องที่ยังไม่มีแหล่งข้อมูล** หลักฐานว่าง, ตรวจสอบแล้ว/อนุมัติแล้วเป็น "—", ความพร้อมและผลรวมเป็น "—"

รายละเอียดทั้งหมดอยู่ใน [SPEC_GAPS.md](SPEC_GAPS.md) §3–§5

## 4. แจ้งผล / แจ้งปัญหา

ถ้าเจอป้าย **Evaluation Error** ให้แนบ log ของ backend จากช่วงเวลานั้นมาด้วย ใน log จะมี traceback ของข้อผิดพลาด

ส่งข้อมูลต่อไปนี้กลับมา:

1. PS code และ `curriculumCode`
2. ภาพหน้าจอ
3. JSON จาก `GET /api/monitor/ps/<PS>?curriculumCode=<รหัส>`
4. ผลที่คาดหวังเทียบกับผลที่ได้
5. เอกสาร `ps_requirements` ของ PS นั้นในขณะทดสอบ

ข้อมูลส่วนตัวในภาพหรือ JSON ให้ปิดทับก่อนส่งตามนโยบายของหน่วยงาน
