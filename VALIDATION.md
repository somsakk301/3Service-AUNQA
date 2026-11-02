# ผลตรวจ AUN-QA Portal — 10 ตุลาคม 2026

## ผ่านจากการรันจริง

- `docker compose config --quiet` ผ่าน
- Image ของ Import, Monitor, Generator และ Portal Build สำเร็จ
- Container ทั้ง 7 ตัว Healthy; ชุด aunqa-portal เปิด Host port เฉพาะ 80 ที่ Gateway
- SPA HTML เปิดได้ครบ `/`, `/login`, `/import`, `/monitor`, `/monitor/ps/PS-01`, `/generator`, `/generator/history`, `/generator/reference` และเข้าตรง Route ย่อยได้ HTTP 200
- Login ผ่านบัญชีที่ Bootstrap สร้างจริง ได้ HttpOnly Cookie; Logout แล้วนำ Cookie เก่ามาใช้ไม่ได้
- ผู้ไม่มี Session เข้า API ทั้งสามชุดและ Import workspace ไม่ได้ (401); internal auth URL เข้าจากภายนอกไม่ได้ (404)
- Cross-origin Login ถูกปฏิเสธ (403); same-origin POST ใช้งานได้
- `/api/generator/dev/generate` ไม่มีใน Portal production config (404)
- นำเข้า DOCX หลักสูตรทดสอบ `PORTAL-SMOKE-TEST` ผ่าน Preview และ Confirm จริง ได้ HTTP 201
- BGE-M3 ประมวลผลจริง 1024 มิติและเก็บลง ChromaDB; ข้อมูลหลักสูตรปรากฏใน Monitor พร้อม 9 เกณฑ์และ PS Detail
- Monitor ประเมินข้อมูลทดสอบเป็น NOT_READY; Generator เรียก Monitor จริงแล้วปฏิเสธการ Generate ด้วย HTTP 412 ไม่มีการ bypass
- Restart Container ทั้ง 7 แล้ว Digest ฐานข้อมูล เอกสารต้นฉบับ และจำนวน Vector เหมือนก่อน Restart; HTTP smoke tests หลัง Restart ผ่าน
- `pip check` ภายใน Generator ไม่พบ dependency ที่ขัดกัน
- รัน Production Generator จริงเมื่อ Monitor เป็น `READY` ผ่าน Gateway สำเร็จด้วย Gemini `gemini-3.8-flash`; Slot Marking พบ 3/3 slots, PS ผ่าน Verification หลัง retry และได้ไฟล์ DOCX 32,636 bytes
- งาน `3b66d2c7-ebbc-4106-978b-a4041a9eb489` ยังคงเป็น `completed` หลัง recreate Container, ดาวน์โหลดผ่าน `/api/generator/generate/{job_id}/download` ได้ และปรากฏเป็น Version 1 ใน Document History
- Log ของรอบที่สำเร็จไม่พบ 429/quota error; ปัญหาเดิมเป็น 404 เพราะ `gemini-2.5-flash` ไม่เปิดให้ผู้ใช้ใหม่ ไม่ใช่ AI usage limit

## Regression tests (แยกจากการทดสอบผ่าน Gateway)

- `deploy/test_monitor_adapter.py`: 3 tests ผ่าน ครอบคลุม READY, NOT_READY, null, HTTP error, response ผิดรูปแบบ และหลายหลักสูตร
- `scripts/test_monitor_integration.py` ของ Generator: ผ่าน legacy contract checks
- `scripts/test_generator_gate.py` ของ Generator: 11 checks ผ่าน
- `deploy/test_document_lifecycle.py`: ผ่าน status, HTML preview, DOCX download, immutable History snapshot, restore completed job และตรวจงาน interrupted

Lifecycle test ใช้ DOCX สังเคราะห์, จำลอง LLM/Monitor เฉพาะใน process ทดสอบ และใช้ฐานข้อมูล `portal_lifecycle_test_<uuid>` ที่ลบหลังจบ ส่วนการยืนยัน Gemini ด้วยข้อมูลจริงบันทึกแยกในหัวข้อการรันจริงด้านบน

## ยังไม่ยืนยัน

- Browser interaction, rendering บน Desktop/Mobile และ Browser Console: เครื่องมือ Browser ใน session นี้ไม่มี browser ที่เชื่อมต่อ (`listBrowsers` คืนรายการว่าง) จึงตรวจได้ถึง Production build และ HTTP/asset routes ไม่ได้อ้างว่า UI/Console ผ่านแล้ว
- HTTPS ด้วย Domain/Certificate จริง: มี Compose override พร้อมใช้ แต่ยังไม่มี Domain และ Certificate ให้ทดสอบ
- ไม่ได้ย้ายฐานข้อมูล/เอกสารจริงของระบบเดิมจาก drive D: เข้าสู่ Volume ของ Portal

## ข้อมูลทดสอบและข้อมูลเดิม

การทดสอบ Import สร้างหลักสูตรที่ระบุชัดว่า `Portal Integration Test (Synthetic)` และเอกสาร `portal-smoke-test.docx` ใน Volume ของ Portal หลังตรวจ Restart สำเร็จ ได้สำรองและนำเฉพาะข้อมูลทดสอบนี้ออก เพื่อไม่ให้ชนกับข้อจำกัดหลักสูตรเดียวของ Generator เมื่อผู้ใช้นำเข้าข้อมูลจริง สำเนาอยู่ใน `artifacts/smoke-data-backup.zip` และ `uploaded-documents/test-backups/` ข้อมูลชุดเดิมและ Container ชื่อ `aunqa-import-service-*` ไม่ถูกแก้ไข ใช้สำเนา cache โมเดลเดิมเพื่อหลีกเลี่ยงดาวน์โหลดโมเดลหลาย GB ซ้ำ

## ไฟล์ที่เกี่ยวข้อง

- `docker-compose.yml`, `docker-compose.https.yml`: ระบบรวมและ HTTPS override
- `deploy/`: Gateway, Monitor image/bootstrap, setup และชุดทดสอบ
- `portal/`: React Portal, Router กลาง, CSS ที่แยกขอบเขต Generator และ Docker build
- Import `backend/app/static/app.js`: เพิ่ม API prefix สำหรับ Portal โดย standalone ยังใช้ `/api` เดิม
- Monitor `backend/app/main.py`: เพิ่ม Healthcheck
- Generator `backend/monitor/client.py`, `common/config.py`: เพิ่ม contract adapter สำหรับ Monitor จริง
- Generator `backend/api_server.py`: เก็บและกู้คืนงาน ตรวจ API key และไม่รายงาน completed หากไม่มีส่วนที่ผ่านหรือมี failed criterion
- Generator `backend/api/routes.py`: ปฏิเสธการเลือกหลักสูตรแบบกำกวม
- Generator Frontend `httpClient.ts`, `VersionActions.tsx`, `GeneratePage.tsx`: API relative URL, Reference route ใน Portal และตรวจว่ามีแม่แบบ DOCX

Working tree ของทั้งสามโครงการมีไฟล์แก้ไข/เพิ่ม/ลบอยู่ก่อนเริ่มงานแล้ว ไม่ reset และไม่ commit งานของทีม Root เดิมไม่มี Git repository แยกต่างหาก
# Login routing fix (2026-10-10)

- The browser screenshot exposed a frontend integration bug missed by direct HTTP checks: the shared Vite `VITE_API_BASE_URL=/api/generator` redirected Monitor login/logout and Monitor requests to Generator.
- Portal now defines the shared base as `/api`; Generator's client selects `/api/generator` locally when `VITE_PORTAL=true`. Standalone Generator behavior is preserved.
- Added `portal/tests/api-routing.mjs` and its entry module. These compile the real frontend clients using production Vite definitions and assert auth, Monitor, Generator JSON and download request paths. This regression test now runs during the Portal image build; it passed.
- Rebuilt and started `portal-frontend`; `python deploy/smoke_test.py` passed, including real login with the configured password, HttpOnly cookie, protected API access, logout and session revocation. These checks do not claim a browser-driven login test.

# Import session incident (2026-10-10)

- Gateway logs show the smoke test's admin logout at 14:24:09 UTC followed by 16 browser Preview requests rejected with 401 at 14:29:30–31 UTC. Monitor's existing account-wide logout revocation invalidated the user's earlier browser session. This is not evidence of a PDF parsing or batch-size failure.
- Normal `deploy/smoke_test.py` now skips logout. `--check-logout` requires a separate `PORTAL_TEST_USERNAME` and `PORTAL_TEST_PASSWORD` and refuses the configured admin account. The backend logout policy is unchanged.
- Import checks the central session before Preview/Confirm, stops a batch on 401, shows a Login link in a new tab, and retains selections/edited previews. Resuming previews skips those already prepared; retrying Confirm excludes already saved records.
- `node deploy/test_import_session.cjs` passed all four in-memory scenarios: 16 selected files with an expired session send no files; a mid-batch 401 stops the queue; reauthentication resumes remaining previews while retaining edits; confirmation retries exclude successful records. These tests use synthetic objects and stub HTTP only, not the user's PDFs or database.
- Rebuilt Import and reran HTTP smoke checks without logout. A session established before the smoke checks remained valid afterwards, and Gateway served the updated Import script. No user CV was uploaded or confirmed during this fix.

# Generator integration fix (2026-10-10)

- MCP stdio now receives the Generator process environment explicitly. Compose-injected `MONGODB_URI`, `CHROMA_*`, Template URL and Gemini settings therefore reach MCP without copying secrets into `/app/.env`.
- The criteria model default is `gemini-3.8-flash`. Client errors such as 401/403/404 fail immediately with the real root error; retry remains enabled only for 429 and server-side 5xx errors.
- Synchronous Gemini calls run through `asyncio.to_thread`, keeping FastAPI health/status endpoints responsive during generation. The verification gate remains enabled and no development bypass is enabled.
- `scripts/test_mcp_runtime_config.py`, Generator gate checks, dev-route checks, `deploy/smoke_test.py`, and `deploy/verify_completed_generation.py` passed after rebuilding the container.
- The current Template has three PS slots only. P1/P2/P3/P4/P8 were correctly recorded as `skipped_no_slots`; this is a Template/configuration scope limitation rather than a runtime failure.

