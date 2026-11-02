# Data Schema — AUN-QA / PS Import Service

**Version:** 1.7  
**Updated:** 3 October 2026  
**Status:** Current implementation reference  
**Source of truth:** `IMPORT_SERVICE_SRS_v1.0.md` version 1.7 and `backend/app/database/schema.py`

> เอกสารนี้เป็นสรุปสำหรับใช้เชื่อมต่อและพัฒนาร่วมกัน ไม่ได้แทนที่ SRS และไม่ได้อนุญาตให้เพิ่มหรือลด Collection, Field หรือ ObjectId relationship

## 1. Database

- Database: MongoDB
- Default database name: `aunqa_ps`
- Validation: `$jsonSchema`, `validationLevel: strict`, `validationAction: error`
- ทุก Collection ที่มี Validator ใช้ `additionalProperties: false`
- `_id` และ Field ความสัมพันธ์ทั้งหมดใช้ BSON `ObjectId` จริง ไม่ใช้ชื่อหรือ String แทน

ระบบกำหนดไว้ทั้งหมด 10 Collections:

1. `curricula`
2. `persons`
3. `educations`
4. `appointments`
5. `academic_works`
6. `documents`
7. `ps_requirements`
8. `data_usages`
9. `generated_documents`
10. `template_ps`

Import Service เขียน Collection ต่อไปนี้:

```text
curricula
persons
educations
appointments
academic_works
documents
data_usages
template_ps
```

`ps_requirements` เป็นข้อมูล Configuration และ `generated_documents` เป็นความรับผิดชอบของ Generate Service

## 2. Shared Objects

### 2.1 SourceReference

ใช้เก็บแหล่งที่มาของข้อมูลแต่ละ Record:

```javascript
{
  "documentId": ObjectId(),
  "pageNumbers": [Integer],
  "fieldPaths": [String]
}
```

| Field | Type | Required | Description |
|---|---|---:|---|
| `documentId` | ObjectId | Yes | อ้างอิง `documents._id` |
| `pageNumbers` | Integer[] | Yes | เลขหน้าที่ตรวจสอบได้จริง; ใช้ `[]` เมื่อระบุหน้าไม่ได้ |
| `fieldPaths` | String[] | Yes | รายชื่อ Field ที่เอกสารนี้รองรับ |

ห้ามสร้าง `documentId`, เลขหน้า หรือ Source ที่ไม่มีอยู่จริง

### 2.2 LocalFileReference

```javascript
{
  "storage": "local",
  "path": String
}
```

`path` ต้องเป็น Relative Path ภายใน `PROJECT_DATA_ROOT`

## 3. MongoDB Collections

### 3.1 `curricula`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Curriculum identifier |
| `curriculumCode` | String | Yes | รหัสหลักสูตร |
| `curriculumName` | String | Yes | ชื่อหลักสูตร |
| `curriculumYear` | Integer | Yes | ปีหลักสูตร |
| `version` | Integer | Yes | เวอร์ชันหลักสูตร |
| `status` | String | Yes | สถานะหลักสูตร เช่น `active` |
| `sources` | SourceReference[] | Yes | แหล่งที่มาของข้อมูล |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

Index:

```text
idx_curricula_code_year_version
(curriculumCode ASC, curriculumYear ASC, version ASC)
```

### 3.2 `persons`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Person identifier |
| `title` | String | Yes | คำนำหน้า |
| `firstName` | String | Yes | ชื่อ |
| `lastName` | String | Yes | นามสกุล |
| `fullName` | String | Yes | ชื่อเต็มแบบ Normalize แล้ว |
| `academicPosition` | String | Yes | ตำแหน่งทางวิชาการ |
| `hasTeachingExperience` | Boolean | No | ผลตรวจจาก CV ว่าพบประสบการณ์สอนหรือไม่ |
| `sources` | SourceReference[] | Yes | แหล่งที่มาของข้อมูล |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

ความหมายของ `hasTeachingExperience`:

```text
ไม่มี Field = ยังไม่ได้ประมวลผล CV
true       = ประมวลผล CV แล้วและพบข้อมูลประสบการณ์สอน
false      = ประมวลผล CV แล้วและไม่พบข้อมูลประสบการณ์สอน
```

ห้ามเก็บ `role` หรือ `roleName` ใน `persons`; ข้อมูลบทบาทต้องอยู่ใน `appointments`

Index:

```text
idx_persons_full_name (fullName ASC)
```

### 3.3 `educations`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Education identifier |
| `personId` | ObjectId | Yes | อ้างอิง `persons._id` |
| `degree` | String | Yes | ระดับวุฒิ |
| `field` | String | Yes | สาขาวิชา |
| `institution` | String | Yes | สถาบันการศึกษา |
| `graduationYear` | Integer | Yes | ปีที่สำเร็จการศึกษา |
| `sources` | SourceReference[] | Yes | แหล่งที่มาของข้อมูล |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

Index:

```text
idx_educations_person_id (personId ASC)
```

### 3.4 `appointments`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Appointment identifier |
| `curriculumId` | ObjectId | Yes | อ้างอิง `curricula._id` |
| `personId` | ObjectId | Yes | อ้างอิง `persons._id` |
| `role` | Enum | Yes | `programmeResponsible` หรือ `programmeStaff` |
| `roleName` | String | Yes | ชื่อบทบาทตามเอกสาร |
| `effectiveDate` | Date/String | Yes | วันที่มีผล |
| `appointmentOrder.orderNumber` | String | Yes | เลขที่คำสั่ง |
| `appointmentOrder.orderDate` | Date/String | Yes | วันที่คำสั่ง |
| `status` | String | Yes | สถานะรายการแต่งตั้ง |
| `sources` | SourceReference[] | Yes | แหล่งที่มาของข้อมูล |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

Indexes:

```text
idx_appointments_curriculum_person (curriculumId ASC, personId ASC)
idx_appointments_role (role ASC)
```

### 3.5 `academic_works`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Academic work identifier |
| `personId` | ObjectId | Yes | อ้างอิง `persons._id` |
| `workType` | String | Yes | ประเภทผลงาน |
| `title` | String | Yes | ชื่อผลงาน |
| `publicationYear` | Integer | Yes | ปีเผยแพร่ |
| `database` | String | Yes | ฐานข้อมูลผลงาน |
| `quartile` | String | Yes | Quartile |
| `sources` | SourceReference[] | Yes | แหล่งที่มาของข้อมูล |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

Indexes:

```text
idx_academic_works_person_id (personId ASC)
idx_academic_works_publication_year (publicationYear ASC)
```

### 3.6 `documents`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Document identifier |
| `documentType` | Enum | Yes | `curriculum`, `cv`, `appointment` |
| `fileType` | Enum | Yes | `pdf`, `doc`, `docx` |
| `fileName` | String | Yes | ชื่อไฟล์ต้นฉบับ |
| `curriculumId` | ObjectId | Yes | อ้างอิง `curricula._id` |
| `originalFile` | LocalFileReference | Yes | ตำแหน่งไฟล์ต้นฉบับ |
| `convertedFile` | LocalFileReference | Yes | ตำแหน่งไฟล์ที่แปลงแล้ว |
| `extractedText` | LocalFileReference | Yes | ตำแหน่งข้อความที่ Extract แล้ว |
| `status` | Enum | Yes | `uploaded`, `processing`, `processed`, `failed` |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

Indexes:

```text
idx_documents_curriculum_type (curriculumId ASC, documentType ASC)
idx_documents_status (status ASC)
```

### 3.7 `ps_requirements`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Requirement identifier |
| `psCode` | String | Yes | `PS-01` ถึง `PS-09` |
| `requirement` | String | Yes | ข้อกำหนด PS |
| `config` | Object | Yes | Configuration ของ Requirement |
| `active` | Boolean | Yes | สถานะเปิดใช้งาน |
| `timestamp` | Date | Yes | เวลาบันทึก |

Index:

```text
idx_ps_requirements_code (psCode ASC)
```

### 3.8 `data_usages`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Mapping identifier |
| `dataType` | String | Yes | ประเภทข้อมูล |
| `dataId` | ObjectId | Yes | ID ของข้อมูลที่ถูกใช้งาน |
| `curriculumId` | ObjectId | Yes | อ้างอิง `curricula._id` |
| `psCodes` | String[] | Yes | PS ที่ใช้ข้อมูลนี้ |
| `roles` | String[] | Yes | บทบาทที่ใช้ข้อมูลนี้ |
| `templateFields` | String[] | Yes | Field ใน Template ที่ใช้ข้อมูลนี้ |
| `timestamp` | Date | Yes | เวลาบันทึกล่าสุด |

Indexes:

```text
idx_data_usages_curriculum_id (curriculumId ASC)
idx_data_usages_type_data_id (dataType ASC, dataId ASC)
```

### 3.9 `generated_documents`

- Collection นี้มีไว้สำหรับ Generate Service
- Import Service ห้าม `CREATE`, `UPDATE` หรือ `DELETE` ข้อมูลใน Collection นี้
- ปัจจุบันระบบมีไว้เป็น Collection เปล่า; Import Service ไม่สร้าง Validator และไม่กำหนด Field ให้แทนทีม Generate
- Field ของ Collection นี้ต้องให้ทีม Generate กำหนดตาม SRS ของบริการตนเอง

### 3.10 `template_ps`

| Field | Type | Required | Description |
|---|---|---:|---|
| `_id` | ObjectId | Yes | Template identifier |
| `version` | Integer | Yes | เวอร์ชันจำนวนเต็มบวกและห้ามซ้ำ |
| `fileName` | String | Yes | ชื่อไฟล์ Template |
| `fileType` | Enum | Yes | `docx` หรือ `pdf` |
| `originalFile` | LocalFileReference | Yes | Relative Path ของไฟล์จริง |
| `timestamp` | Date | Yes | เวลาบันทึก |

Index:

```text
idx_template_ps_version (version ASC, UNIQUE)
```

Template ไม่สร้าง `documents` Record และไม่เข้า Extraction, Parser, Chunking, Embedding หรือ ChromaDB

## 4. ObjectId Relationships

```text
appointments.curriculumId       -> curricula._id
appointments.personId           -> persons._id
educations.personId             -> persons._id
academic_works.personId         -> persons._id
documents.curriculumId          -> curricula._id
data_usages.curriculumId        -> curricula._id
generated_documents.curriculumId -> curricula._id  (Generate Service responsibility)

curricula.sources[].documentId      -> documents._id
persons.sources[].documentId        -> documents._id
educations.sources[].documentId     -> documents._id
academic_works.sources[].documentId -> documents._id
appointments.sources[].documentId   -> documents._id
```

## 5. ChromaDB Schema

Collection ที่ Import Service เขียน:

```text
document_chunks
```

Record structure:

```javascript
{
  "id": String,
  "document": String,
  "embedding": [Float], // 1024 dimensions from BAAI/bge-m3
  "metadata": {
    "documentId": String,
    "curriculumId": String,
    "documentType": "curriculum" | "cv" | "appointment",
    "page": Integer,
    "chunkIndex": Integer,
    "section": String,  // Optional
    "personId": String  // Optional
  }
}
```

Locked settings:

```text
embedding model = BAAI/bge-m3
embedding dimension = 1024
chunk_size = 500
chunk_overlap = 100
```

`documentId` ใน ChromaDB ต้องตรงกับ `documents._id` ใน MongoDB ในรูป String

## 6. Data Ownership

| Collection | Import Service | Generate Service | Monitor |
|---|---|---|---|
| `curricula` | Write | Read | Read |
| `persons` | Write | Read | Read |
| `educations` | Write | Read | Read |
| `appointments` | Write | Read | Read |
| `academic_works` | Write | Read | Read |
| `documents` | Write | Read | Read |
| `ps_requirements` | Configuration only | Read | Read |
| `data_usages` | Write | Read | Read |
| `generated_documents` | No write | Write | Read |
| `template_ps` | Write | Read/Download | Read |

## 7. Connection Examples

เมื่อเชื่อมจากเครื่องอื่นในเครือข่ายเดียวกัน ให้แทน `<IMPORT_HOST_IP>` ด้วย IP ของเครื่องที่รัน Docker:

```text
MongoDB:  mongodb://<IMPORT_HOST_IP>:27017/aunqa_ps
ChromaDB: http://<IMPORT_HOST_IP>:8000
Backend:  http://<IMPORT_HOST_IP>:8080
```

การเข้าถึงจากเครื่องอื่นขึ้นอยู่กับ Firewall และนโยบายของเครือข่าย

## 8. Implementation Files

```text
Locked specification:       IMPORT_SERVICE_SRS_v1.0.md
MongoDB schema/validators:  backend/app/database/schema.py
Database bootstrap:         backend/app/database/bootstrap.py
API schemas:                backend/app/schemas/document.py
Preview form schema:        backend/app/static/app.js
ChromaDB metadata model:    backend/app/chunking/models.py
ChromaDB storage:           backend/app/vectorization/store.py
```
