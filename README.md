# AUN-QA Portal

เว็บกลาง React 19 + Vite สำหรับ Import, Monitor และ Generator เปิดที่ **http://localhost** ผ่าน Nginx จุดเดียว Backend ทั้งสามเป็น FastAPI และใช้ MongoDB Container เดียวกัน พร้อม ChromaDB สำหรับ Embedding

## เริ่มใช้งานบน Windows

ต้องมี Docker Desktop ที่เปิด Linux containers และ Docker Compose ใช้งานได้ รันจากโฟลเดอร์นี้:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/setup.ps1
docker compose up -d --build
docker compose ps
```

`setup.ps1` สร้าง `.env` ครั้งแรกด้วย Session Secret และรหัสผ่านสุ่ม ไม่เขียนทับ `.env` ที่มีอยู่ หากพบ `GEMINI_API_KEY` ใน `.env` ของ Generator เดิม จะคัดลอกเฉพาะค่านี้มาใช้โดยไม่พิมพ์ออก Log

เข้าสู่ระบบด้วย `PORTAL_ADMIN_USERNAME` (เริ่มต้น `admin`) และ `PORTAL_ADMIN_PASSWORD` ใน `.env` อ่านรหัสผ่านจากไฟล์บนเครื่องโดยตรง อย่าใส่ `.env` ใน Git หากใช้ Linux/macOS ให้คัดลอก `.env.example` เป็น `.env` แล้วตั้ง Session Secret แบบสุ่มอย่างน้อย 32 ตัวอักษร และรหัสผ่านอย่างน้อย 12 ตัวอักษรก่อนรัน Compose

การ Build ครั้งแรกต้องดาวน์โหลด Python/Node packages และ Image; Import ครั้งแรกต้องดาวน์โหลด BGE-M3 หลาย GB หากยังไม่มี cache ให้เตรียม RAM และพื้นที่ดิสก์เพียงพอสำหรับโมเดล ไม่มีการใช้ GPU ใน Compose นี้

ระบบรวมนี้ใช้ Volume ใหม่ชื่อขึ้นต้น `aunqa-portal_` **ไม่ได้ย้ายหรือแก้ข้อมูลของชุด `aunqa-import-service` เดิม** จึงต้องนำเข้าข้อมูลผ่าน Portal หรือย้ายสำเนาข้อมูลตามขั้นตอนสำรองด้านล่าง การรวมโค้ดไม่ได้ทำให้ฐานข้อมูลเดิมปรากฏอัตโนมัติ

## การใช้งาน

1. Login แล้วเปิด Import Document เลือก Curriculum เพื่อสร้างหลักสูตรจากเอกสาร ตรวจและแก้ Preview ก่อนยืนยัน
2. นำเข้า CV, Appointment และ Template ที่เกี่ยวข้อง หน้า Generate ใช้แม่แบบ DOCX เท่านั้น แม้ Import เดิมรับ Template PDF ได้
3. เปิด Monitor/PS Detail เพื่อตรวจหลักฐาน ข้อมูลที่ขาด และยืนยันผลตามสิทธิ์เดิม
4. Generate SAR จะตรวจ Monitor จริงก่อนเริ่ม เฉพาะสถานะ `READY` จึงเริ่มได้; ไม่มี Mock หรือ Dev bypass ใน Portal
5. บันทึก Draft, ดาวน์โหลด DOCX, เปิด History และ Reference ตามวงจรเดิมของ Generator

Generator ใน Docker รับค่า MongoDB, ChromaDB, Template และ Gemini จาก Environment ของ Compose และส่งต่อไปยัง MCP subprocess อัตโนมัติ ค่าเริ่มต้นปัจจุบันคือ `GEMINI_CRITERIA_MODEL=gemini-3.8-flash`; หากเปลี่ยนรุ่นให้กำหนดใน `.env` แล้วรัน `docker compose up -d --build generator-backend` ใหม่ การเรียก Gemini ทำใน worker thread เพื่อให้หน้าเว็บติดตามสถานะได้ระหว่างประมวลผล และ Verification gate ยังทำงานตามเดิม

| URL | การใช้งาน |
|---|---|
| `/` | Dashboard และรายชื่อหลักสูตร |
| `/login` | Session Login กลาง |
| `/import` | ฟอร์ม Import เดิมในพื้นที่แยกภายใต้ Portal |
| `/monitor` | Monitor Overview |
| `/monitor/ps/:psCode` | รายละเอียด PS |
| `/generator` | สร้าง/ดู/แก้ Draft SAR |
| `/generator/history` | ประวัติ Version |
| `/generator/reference` | แหล่งอ้างอิง |
| `/api/import/*` | แปลงเป็น `/api/*` ของ Import เช่น `/api/import/import/preview` |
| `/api/monitor/*` | API Monitor เดิม |
| `/api/generator/*` | แปลงเป็น `/api/*` ของ Generator |
| `/api/auth/*` | Login, Me, Logout |

หน้า React ของ Monitor และ Generator อยู่ใน Router เดียวและใช้ Source เดิมผ่าน Vite aliases ไม่ได้คัดลอกโค้ดเป็นอีกชุด หน้า Import เดิมใช้ DOM scripting และ CSS ของตัวเอง จึงแยกด้วย same-origin iframe เพื่อรักษาฟอร์ม Preview/แก้ข้อมูลหลาย Collection; Gateway ป้องกันทั้งหน้าและ API ด้วย Session เดียวกัน

## สถาปัตยกรรมและข้อมูล

```text
Browser → Gateway :80 → portal-frontend :8080
                     → import-backend :8000
                     → monitor-backend :8000 (เจ้าของ Session)
                     → generator-backend :8010
ทุก Backend → mongodb :27017
Import และ Generator → chromadb :8000
Generator → Monitor API + Import Template API ภายใน Docker network
```

| Service | ข้อมูลถาวร |
|---|---|
| mongodb | `mongodb-data` |
| chromadb | `chroma-data` |
| import-backend | `uploaded-documents` ที่ `/app/project-data` รวมเอกสารและ cache |
| generator-backend | `generated-documents` ที่ `/app/output`, `generator-models` และเอกสารต้นทางแบบอ่านอย่างเดียว |

MongoDB ตัวเดียวมีฐานข้อมูล `aunqa_ps` สำหรับข้อมูลต้นทาง/Generator, `aunqa_config` สำหรับ configuration ของ Monitor และ `aunqa_monitor` สำหรับผลตรวจ/ผู้ใช้ การแยกสองฐานข้อมูลหลังจำเป็นเพราะ Import ล็อก validator ของ `ps_requirements` ขณะที่ Monitor มีเอกสาร `configType: generationReadiness` อีกโครงสร้างหนึ่ง จึงใช้ความสามารถแยก configuration/results database ที่ Monitor มีอยู่แล้วแทนการเปลี่ยน Schema

Bootstrap ใช้ configuration snapshot ที่เอกสาร Monitor ระบุว่า ACTIVE (`backend/tests/fixtures/ps_config_v1.json` และ `generation_readiness_v1.json`; ดู PROVENANCE.md ข้างไฟล์) คัดลอกลงฐานข้อมูลใหม่ครั้งแรกเท่านั้น ไม่มีการนำเข้าข้อมูลบุคคลหรือผล PASS ปลอม ไม่เขียนทับ configuration และบัญชีที่มีอยู่ ภายหลัง runtime อ่าน MongoDB ตามเดิม

Gateway ตรวจ `/api/auth/me` ทุกคำขอที่เข้า Import/Monitor/Generator แล้วส่ง Cookie เดิมไป Backend; logout เพิกถอน session ฝั่ง server จริง ไม่มี Backend/Database port เปิดออก Host และมีการปฏิเสธคำขอเปลี่ยนข้อมูลจาก Origin อื่น บริการภายใน Docker network ใช้ service name; network นี้ถือเป็นขอบเขตที่เชื่อถือได้ อย่านำ Container ที่ไม่เชื่อถือมาเชื่อม

## Environment

| ตัวแปร | ความหมาย |
|---|---|
| `MORNITOR_SESSION_SECRET` | จำเป็น; สุ่มอย่างน้อย 32 ตัวอักษร |
| `PORTAL_ADMIN_USERNAME`, `PORTAL_ADMIN_NAME`, `PORTAL_ADMIN_PASSWORD` | บัญชีเริ่มต้น สร้างเมื่อยังไม่มี username เท่านั้น |
| `GEMINI_API_KEY` | คีย์สำหรับสร้างเอกสาร; หากไม่มี API Generate ตอบ 503 |
| `GEMINI_CRITERIA_MODEL` | โมเดลที่บัญชี Gemini ใช้ได้ ค่าเริ่มต้น `gemini-2.5-flash` |
| `MORNITOR_COOKIE_SECURE` | false สำหรับ local HTTP; HTTPS override ตั้ง true |
| `APP_DOMAIN` | ใช้บันทึก Domain เป้าหมาย; ต้องตั้ง DNS/Certificate ภายนอกเอง Nginx รองรับ Host ที่ชี้มาที่เครื่อง |

การสร้างผู้ใช้เพิ่มใช้ script เดิม โดยไม่ส่งรหัสผ่านผ่าน command line:

```powershell
docker compose exec monitor-backend python scripts/seed_user.py --username reviewer --name "Reviewer"
```

เปลี่ยนรหัสผ่านบัญชีที่มีอยู่เพิ่ม `--update-password`; การแก้ `PORTAL_ADMIN_PASSWORD` ใน `.env` อย่างเดียวไม่เปลี่ยนบัญชีเดิม

## ข้อขัดแย้งและข้อจำกัดที่ตรวจพบ

- README หลักของ Generator อ้างว่า Verification ถูก bypass แต่โค้ด `master_agent/master.py` ปัจจุบันตรวจ `verify()` และ retry ก่อนฉีดเนื้อหาแล้ว Portal เพิ่มการตรวจผลว่าไม่มี `failed_*` และมีส่วนที่ completed ก่อนรายงานว่างานสำเร็จ
- Monitor Source of Truth ส่ง `GET /api/monitor?curriculumCode=...` และ `generationReadiness.status`; Generator เดิมรออีก endpoint และ `generatedReady` ตัวเชื่อม Portal ใช้ contract ของ Monitor พร้อมแปลง ObjectId เป็น curriculumCode ไม่คำนวณกฎ PS ใหม่
- Generator core ปัจจุบันเลือกข้อมูลแบบหลักสูตรเดียว Portal จึงบล็อกการ Generate เมื่อมีหลายหลักสูตรเพื่อไม่ใช้หลักฐานผิดหลักสูตร Import/Monitor ยังรองรับการเลือกหลักสูตรได้
- Master Config มี guideline ว่างใน PS/P2/P3/P4/P8 และการตรวจด้วยคนของ Monitor บางเกณฑ์ยังไม่เปลี่ยนสถานะ engine/readiness ตาม Source of Truth เดิม จึงอาจทำให้ข้อมูลยัง NOT_READY แม้กดยืนยัน ต้องให้เจ้าของเกณฑ์ตัดสินข้อกำหนดก่อนแก้ business rule
- ไม่รับรองการสร้าง SAR พร้อมใช้ส่งจริงจนมีข้อมูล/แม่แบบ/เกณฑ์ครบและทดสอบ Gemini → Verification → DOCX ผ่านจริง การผ่าน Build หรือ API smoke test ไม่ใช่การผ่านการตรวจเนื้อหารายงาน
- งาน Generator เก็บสถานะลง MongoDB และกู้คืนงาน completed หลัง Restart งานที่กำลังทำจะถูกทำเครื่องหมาย failed พร้อมเหตุผลให้ผู้ใช้กดเริ่มใหม่ ไม่มีการเรียก LLM ซ้ำอัตโนมัติ
- รายละเอียดผลทดสอบและข้อจำกัด Browser อยู่ใน `VALIDATION.md`

## HTTPS

วาง Certificate ที่เชื่อถือได้ใน `deploy/certs/fullchain.pem` และ private key ใน `deploy/certs/privkey.pem` (โฟลเดอร์นี้ถูก ignore) ตั้ง DNS ของ Domain ให้ชี้ไปเครื่อง แล้วรัน:

```powershell
docker compose -f docker-compose.yml -f docker-compose.https.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
```

Override เปิด 443 เพิ่ม และให้ 80 redirect ไป HTTPS; Cookie Secure เปิดพร้อมกัน ใช้ไฟล์ Compose ทั้งสองในการจัดการชุด HTTPS ต่อไป Certificate และ Domain จริงยังไม่ได้ติดตั้งในงานนี้

## ดูแลระบบ

```powershell
docker compose ps
docker compose logs --tail 100 -f
docker compose up -d --build
docker compose stop
docker compose start
docker compose down
```

`down` เก็บ named volumes ไว้ อย่าใช้ `down -v` หากต้องการรักษาข้อมูล

## Backup และ Restore

เก็บ MongoDB, ChromaDB, เอกสารต้นฉบับ และ output เป็นชุดเดียวกัน เพราะอ้างอิงกัน หยุดรับคำขอและหยุดบริการที่เขียนข้อมูลก่อน Backup:

```powershell
New-Item -ItemType Directory -Force backups
docker compose stop gateway import-backend monitor-backend generator-backend
docker compose exec -T mongodb mongodump --archive=/tmp/portal.archive --gzip
docker compose cp mongodb:/tmp/portal.archive ./backups/portal.archive
docker compose stop chromadb
```

สำรอง volume ที่หยุดเขียนแล้วด้วย `tar` ผ่าน helper container โดย mount ต้นทาง read-only ทำกับ `aunqa-portal_chroma-data`, `aunqa-portal_uploaded-documents`, `aunqa-portal_generated-documents` (model cache สำรองได้แต่โหลดใหม่ได้) ตัวอย่าง PowerShell:

```powershell
$backupPath = (Resolve-Path backups).Path
docker run --rm --mount type=volume,source=aunqa-portal_chroma-data,target=/data,readonly --mount "type=bind,source=$backupPath,target=/backup" nginx:1.28-alpine tar czf /backup/chroma-data.tgz -C /data .
docker run --rm --mount type=volume,source=aunqa-portal_uploaded-documents,target=/data,readonly --mount "type=bind,source=$backupPath,target=/backup" nginx:1.28-alpine tar czf /backup/uploaded-documents.tgz -C /data .
docker run --rm --mount type=volume,source=aunqa-portal_generated-documents,target=/data,readonly --mount "type=bind,source=$backupPath,target=/backup" nginx:1.28-alpine tar czf /backup/generated-documents.tgz -C /data .
docker compose up -d
```

Restore ไปยังเครื่อง/Volume ใหม่ที่ว่างก่อน เริ่ม MongoDB แล้ว `docker compose cp ./backups/portal.archive mongodb:/tmp/portal.archive` และ `docker compose exec -T mongodb mongorestore --archive=/tmp/portal.archive --gzip --stopOnError` คืนไฟล์ tar ไป volume คู่กันขณะหยุดบริการ โดยเปลี่ยน tar เป็น `tar xzf /backup/<ชื่อ>.tgz -C /data` และเอา `readonly` ของ volume เป้าหมายออก ตรวจ owner ให้ Import UID 999 และ Generator UID 10001 เขียนได้ แล้วค่อย `up -d` ห้าม Restore ทับชุดใช้งานโดยไม่มี Backup และไม่ต้องใช้ `--drop` สำหรับฐานข้อมูลว่าง

การย้ายจากระบบเดิมใช้หลักเดียวกัน: snapshot MongoDB/ChromaDB/เอกสารจากชุดเดิมแบบสอดคล้องกัน แล้วคืนลงชุดว่าง เส้นทางเอกสารต้องยังตรงกับ metadata; หากมี schema legacy ของ `generated_documents` ต้องใช้ migration script เดิมของ Generator หลังสำรองข้อมูล

## ตรวจสอบซ้ำ

```powershell
docker compose config --quiet
python deploy/smoke_test.py
# ตัวเลือกนี้สร้างหลักสูตรทดสอบชื่อ PORTAL-SMOKE-TEST ผ่าน Import จริง
python deploy/smoke_test.py --import-document
```

ผลล่าสุดอยู่ `artifacts/smoke-results.json` ใช้ `deploy/test_monitor_adapter.py` และ `deploy/test_document_lifecycle.py` ภายใน Generator image โดยตั้ง `PYTHONPATH=/app` สำหรับ regression tests แยกกระบวนการ; lifecycle test ใช้ฐานข้อมูลชั่วคราวของตัวเองและไม่เรียก Gemini จริง
## MongoDB Compass บนเครื่องพัฒนา

ไฟล์ `docker-compose.override.yml` เปิด MongoDB ของ Portal เฉพาะ `127.0.0.1:27018` และถูกโหลดอัตโนมัติเมื่อใช้ `docker compose up -d --build` เพื่อให้ Compass บนเครื่องนี้เชื่อมได้

ใน Compass เลือก Add new connection ใส่ URI `mongodb://127.0.0.1:27018` ตั้งชื่อ `AUN-QA Portal` แล้วกด Connect เลือกฐานข้อมูล `aunqa_ps` และ Collection `documents` เพื่อดูเอกสารนำเข้า หรือ `curricula` เพื่อดูหลักสูตร ไม่ใช้พอร์ต 27017 ซึ่งเป็น MongoDB ของระบบเดิม

Production ใช้ `docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build` ซึ่งไม่โหลด override สำหรับ Compass นี้

การตรวจด้วย `python deploy/smoke_test.py` ไม่เรียก Logout โดยปริยาย เพราะกติกาเดิมของ Monitor จะยกเลิกทุก Session ของบัญชีเดียวกัน หากต้องทดสอบ Logout ให้ใช้บัญชีทดสอบแยกผ่าน environment `PORTAL_TEST_USERNAME` และ `PORTAL_TEST_PASSWORD` แล้วระบุ `--check-logout` ห้ามใช้บัญชี admin ที่ทีมกำลังใช้งาน

หากหน้า Import แจ้งว่าต้องเข้าสู่ระบบใหม่ ให้เปิดลิงก์ Login ในแท็บใหม่ แล้วกลับมาทำต่อในหน้าเดิมเพื่อรักษาไฟล์ที่เลือกและ Preview ที่แก้ไขไว้ ทดสอบการหยุด/ทำต่อของคิวโดยไม่อัปโหลดจริงด้วย `node deploy/test_import_session.cjs`

