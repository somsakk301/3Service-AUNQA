ใช่ครับ เอกสารแบบที่คุณต้องการเรียกว่า **SRS — Software Requirements Specification** หรือภาษาไทยว่า **เอกสารข้อกำหนดความต้องการซอฟต์แวร์** เหมาะมากสำหรับใช้ “ล็อกสเปก” ก่อนเขียนโค้ด เพื่อให้ทีมและ AI ทำตามขอบเขตเดียวกัน

ด้านล่างผมจัด **SRS ฉบับใหม่ของ Import Service** ให้ตรงกับที่เราสรุปล่าสุด: มีหน้า Import หน้าเดียว, ไม่มี Login/Dashboard, Backend ทำ Extract → MongoDB → Chunk → BGE-M3 → ChromaDB และทุกอย่างรันบน Docker

# Software Requirements Specification (SRS)
## Import Service — AUN-QA / PS System

**Version:** 1.7  
**Status:** Locked Specification for Implementation

---

# 1. Purpose

Import Service มีหน้าที่นำเอกสารเข้าสู่ระบบ AUN-QA/PS ประมวลผลเอกสาร แปลงข้อมูลจากเอกสารให้เป็น Structured Data บันทึกลง MongoDB และสร้าง Vector Embedding จากเนื้อหาเอกสารเพื่อบันทึกลง ChromaDB สำหรับให้ Generate Service ใช้ค้นคืนข้อมูลภายหลัง

Import Service สิ้นสุดเมื่อข้อมูลทั้งสองประเภทพร้อมใช้งาน:

1. Structured Data พร้อมใน MongoDB
2. Evidence Chunk + Vector พร้อมใน ChromaDB

Import Service ไม่ทำหน้าที่ตรวจผล PS และไม่สร้าง SAR

---

# 2. Scope

Import Service ครอบคลุม:

```text
Upload Document
      ↓
Validate File
      ↓
Store Original File
      ↓
Create Document Record
      ↓
Convert File (ถ้าจำเป็น)
      ↓
Extract Text + Page
      ↓
      ├──────────────────────────┐
      │                          │
      ▼                          ▼
Structured Data             RAG / Vector Data
      │                          │
Parse                        Clean Text
      │                          │
Normalize                     Chunk
      │                          │
Validate                     Metadata
      │                          │
Deduplicate                 Embedding
      │                       BGE-M3
      ▼                          │
MongoDB                        ▼
                           ChromaDB
      │                          │
      └────────────┬─────────────┘
                   ▼
             Final Validation
                   ↓
          status = processed
```

Flow หลักใน OOAD เดิมกำหนดไว้ว่าเริ่มจาก Document → ตรวจสอบไฟล์ → เก็บ Local Storage → Extract ข้อมูล และจากนั้นจึงสร้างข้อมูล Curriculum / Person / Education / AcademicWork / Appointment 

---

# 3. System Boundary

Import Service รับผิดชอบ:

- Upload Document
- File Validation
- File Storage
- Document Conversion
- Text Extraction
- Structured Data Parsing
- Data Normalization
- Data Validation
- Duplicate Detection
- MongoDB Insert/Update
- Relationship Creation
- Data Usage Mapping
- Chunking
- Chunk Metadata
- Embedding
- Vector Storage
- Import Status

Import Service ไม่รับผิดชอบ:

```text
❌ Login
❌ Authentication
❌ User Management
❌ Dashboard
❌ Monitor UI
❌ PS PASS / FAIL / REVIEW
❌ Generate SAR
❌ Generated Document
❌ Reports
❌ Analytics
```

---

# 4. User Interface Requirement

Import Service มีหน้าเว็บเพียง **1 หน้า**

ชื่อหน้า:

```text
Import Document
```

หน้า Import ต้องประกอบด้วย:

### 4.1 Document Type

ผู้ใช้ต้องเลือกประเภทเอกสาร:

```text
Curriculum
CV
Appointment
Template
```

ค่าที่ระบบใช้:

```text
curriculum
cv
appointment
template
```

`template` เป็นประเภทอัปโหลดเฉพาะสำหรับแม่แบบ PS และไม่ถือเป็นเอกสารหลักฐานใน `documents`

---

### 4.2 Curriculum

ผู้ใช้ต้องสามารถเลือกหลักสูตรที่เอกสารนี้เกี่ยวข้อง

ระบบจะใช้ Curriculum Reference เพื่อสร้าง:

```text
documents.curriculumId
```

---

### 4.3 File Upload

รองรับ:

```text
PDF
DOC
DOCX
```

ตาม Data Dictionary ของระบบ 

หน้าเว็บควรรองรับ:

```text
Select File / Select Multiple Files
หรือ
Drag & Drop Single/Multiple Files
```

เมื่อเลือกหลายไฟล์ Frontend ต้องสร้าง Import Queue และเรียก Import API เดิมแยกทีละไฟล์ตามลำดับ โดยทุกไฟล์ใน Queue ใช้ `documentType` และ `curriculumId` ที่ผู้ใช้เลือกเดียวกัน แต่ต้องสร้าง `documents` Record แยกกันทุกไฟล์

หากไฟล์ใดประมวลผลล้มเหลว ระบบต้องแสดงสถานะของไฟล์นั้นและประมวลผลไฟล์ถัดไปต่อ โดยไม่เปลี่ยน Collection, Field, ObjectId Relationship หรือ Import Processing Order ของแต่ละไฟล์

กรณี `template` รองรับ DOCX หรือ PDF ครั้งละหนึ่งไฟล์ ผู้ใช้ต้องระบุ `version` เป็นจำนวนเต็มบวก ระบบบันทึกไฟล์ต้นฉบับและ metadata ลง `template_ps` แล้วสิ้นสุด โดยไม่สร้าง `documents` Record และไม่ทำ Extraction, Structured Parser, Chunking, Embedding หรือ ChromaDB

---

### 4.4 Import Button

มีปุ่ม:

```text
Import Document
```

เมื่อกดแล้ว Frontend ส่งไฟล์ไปยัง Import API

---

### 4.5 Processing Status

หน้าเดียวกันต้องแสดงสถานะของ Import เช่น:

```text
✓ File Upload
✓ File Validation
✓ Original File Storage
✓ Text Extraction
✓ Structured Data
✓ MongoDB
✓ Chunking
✓ Embedding
✓ ChromaDB

Import Completed
```

หากเกิดข้อผิดพลาดต้องแสดง:

```text
Import Failed
```

พร้อมข้อความ Error ที่เหมาะสม

กรณีนำเข้าหลายไฟล์ ต้องแสดงสถานะแยกรายไฟล์อย่างน้อย:

```text
Waiting
Processing
Completed
Failed
```

---

### 4.6 Preview / Edit / Confirm Before Database Write

For `curriculum`, `cv`, and `appointment`, the Import page must use a two-step
operation:

```text
Preview Data
    ↓
Review / Add / Edit / Delete parsed records and chunks
    ↓
Confirm Import or Cancel
```

The Preview operation may validate, extract, parse, normalize, and create the
locked 500/100 chunks in temporary processing storage, but it must not create
or update records in MongoDB and must not create or update vectors in ChromaDB.

The Preview page must show the proposed data grouped by its existing MongoDB
collection and must also show the proposed ChromaDB chunks and metadata.
Fields used only to describe a pending relationship in Preview are transport
metadata and must never be written as additional MongoDB fields.

The user may add, edit, or delete proposed parsed records and chunk text before
confirmation. The backend must validate the edited payload against the locked
collection fields, ObjectId relationships, chunk metadata, and maximum
`chunk_size=500` before any database write.

`Confirm Import` must revalidate the uploaded file and the edited Preview
payload before continuing with Original File Storage, MongoDB, Embedding, and
ChromaDB. `Cancel` must leave MongoDB and ChromaDB unchanged.

For `template`, the same page must show the proposed `template_ps` metadata
before the existing template upload API is called. Confirmation then stores
the original file and creates the `template_ps` record; cancellation performs
neither operation.

This requirement does not add a Collection or persistent Field and does not
change any ObjectId Relationship.

---

# 5. Input Requirements

## FR-001 Supported Document Types

ระบบต้องรองรับ:

```text
curriculum
cv
appointment
template
```

ห้ามเพิ่มประเภทเอกสารใหม่โดยไม่แก้ SRS

`template` รองรับ `.docx` และ `.pdf` ส่วน `curriculum`, `cv` และ `appointment` ยังคงรองรับ `.pdf`, `.doc` และ `.docx`

---

## FR-002 Supported File Types

ระบบต้องรองรับ:

```text
.pdf
.doc
.docx
```

ไฟล์อื่นต้อง Reject

---

# 6. File Validation

ก่อนประมวลผล ระบบต้องตรวจ:

- Extension
- File Type
- Document Type
- File Size > 0
- File Readability
- Curriculum Reference
- ไฟล์ไม่เสีย

หากไม่ผ่าน Validation ระบบต้องหยุด Import

---

# 7. Docker Requirement

ระบบทั้งหมดต้องทำงานบน Docker

อย่างน้อยต้องมี:

```text
Docker Compose
│
├── Backend / Import Service
├── MongoDB
└── ChromaDB
```

Backend ต้องเรียก Service ผ่าน Docker Network

ตัวอย่าง:

```text
mongodb:27017
chromadb:8000
```

ห้าม Hard-code `localhost` สำหรับการสื่อสารระหว่าง Container ใน Deployment

---

# 8. Original File Storage

Original File ต้องถูก Copy จากเครื่องผู้ใช้เข้ามาเก็บใน Storage ของระบบ

ตัวอย่าง:

```text
User Computer

C:\Downloads\teacher.pdf
       ↓
HTTP Upload
       ↓
FastAPI
       ↓
System Storage
```

ห้ามเก็บ Path ของเครื่องผู้ใช้ เช่น:

```text
C:\Users\xxx\Downloads\...
```

ลง Database

---

# 9. Host Storage

ไฟล์ต้อง Persist บน Host

ตัวอย่าง Development:

```text
D:\AUN\
└── project-data\
```

Docker Mount:

```text
HOST
D:\AUN\project-data

        ↕

CONTAINER
/app/project-data
```

Host Path ต้องกำหนดผ่าน Docker Configuration

ห้าม Hard-code Drive `D:` ใน Application Code

---

# 10. Storage Folder Structure

โครงสร้างต้องเป็น:

```text
project-data/
│
├── documents/
│   │
│   ├── original/
│   │   ├── curriculum/
│   │   ├── cv/
│   │   ├── appointment/
│   │   └── template/
│   │
│   ├── converted/
│   │   ├── curriculum/
│   │   ├── cv/
│   │   └── appointment/
│   │
│   ├── extracted/
│   │   ├── curriculum/
│   │   ├── cv/
│   │   └── appointment/
│   │
│   └── generated/
│
├── mongodb/
│
└── chromadb/
```

โครงสร้าง Original / Converted / Extracted / Generated สอดคล้องกับ Data Schema 

---

# 11. Relative Path Requirement

MongoDB เก็บเฉพาะ Relative Path

ถูก:

```text
project-data/documents/original/cv/teacher.pdf
```

ผิด:

```text
D:\AUN\project-data\documents\...
```

ผิด:

```text
/app/project-data/documents/...
```

Data Schema กำหนด Local Storage และ Relative Path ไว้แล้ว 

---

# 12. Document Processing

## FR-003 PDF

ใช้:

```text
PyMuPDF (fitz)
```

ต้อง Extract:

```text
pageNumber
text
```

ระบบต้องรักษาข้อมูล Page

---

## FR-004 DOCX

ใช้:

```text
python-docx
```

ต้องสามารถอ่าน:

```text
Paragraph
Table
```

---

## FR-005 DOC

ใช้:

```text
LibreOffice Headless
```

Flow:

```text
DOC
 ↓
LibreOffice
 ↓
DOCX / supported format
 ↓
Extraction
```

---

# 13. MongoDB Database Design

ระบบมี 10 Collections ตาม Data Schema ล่าสุด:

```text
1. curricula
2. persons
3. educations
4. appointments
5. academic_works
6. documents
7. ps_requirements
8. data_usages
9. generated_documents
10. template_ps
```



Import Service เขียนหลัก ๆ:

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

Import ไม่เขียน:

```text
generated_documents
```

---

# 14. curricula

Schema:

```javascript
{
  "_id": ObjectId(),

  "curriculumCode": String,
  "curriculumName": String,
  "curriculumYear": Integer,
  "version": Integer,
  "status": String,

  "sources": [SourceReference],

  "timestamp": Date
}
```

ตรงกับ Data Schema 

---

# 15. persons

Schema:

```javascript
{
  "_id": ObjectId(),

  "title": String,
  "firstName": String,
  "lastName": String,
  "fullName": String,
  "academicPosition": String,
  "hasTeachingExperience": Boolean, // Optional until a CV is processed

  "sources": [SourceReference],

  "timestamp": Date
}
```

`hasTeachingExperience` ระบุว่าพบข้อมูลประสบการณ์สอนใน CV ของอาจารย์หรือไม่:

```text
true  = ประมวลผล CV แล้วพบข้อมูลประสบการณ์สอน
false = ประมวลผล CV แล้วไม่พบข้อมูลประสบการณ์สอน
```

Field นี้ต้องไม่มีค่าใน Record ที่ยังไม่ได้ประมวลผล CV และต้องกำหนดเป็น Boolean หลังจากประมวลผล CV สำเร็จเท่านั้น



### Critical Rule

`persons` ห้ามมี:

```text
role
roleName
```

Role ต้องอยู่ใน `appointments`

เนื่องจากอาจารย์หนึ่งคนสามารถมีหลาย Role ได้ 

---

# 16. educations

Schema:

```javascript
{
  "_id": ObjectId(),

  "personId": ObjectId(),

  "degree": String,
  "field": String,
  "institution": String,
  "graduationYear": Integer,

  "sources": [SourceReference],

  "timestamp": Date
}
```

Relationship:

```text
persons._id
     ↓
educations.personId
```

หนึ่ง Person สามารถมี Education ได้หลายรายการ 

---

# 17. appointments

Schema:

```javascript
{
  "_id": ObjectId(),

  "curriculumId": ObjectId(),
  "personId": ObjectId(),

  "role": String,
  "roleName": String,

  "effectiveDate": Date/String,

  "appointmentOrder": {
    "orderNumber": String,
    "orderDate": Date/String
  },

  "status": String,

  "sources": [SourceReference],

  "timestamp": Date
}
```

Role ปัจจุบัน:

```text
programmeResponsible
programmeStaff
```



---

# 18. academic_works

Schema:

```javascript
{
  "_id": ObjectId(),

  "personId": ObjectId(),

  "workType": String,
  "title": String,
  "publicationYear": Integer,
  "database": String,
  "quartile": String,

  "sources": [SourceReference],

  "timestamp": Date
}
```

หนึ่ง Person สามารถมี Academic Work ได้หลายรายการ 

---

# 19. documents

Schema:

```javascript
{
  "_id": ObjectId(),

  "documentType": String,
  "fileType": String,
  "fileName": String,

  "curriculumId": ObjectId(),

  "originalFile": {
    "storage": "local",
    "path": String
  },

  "convertedFile": {
    "storage": "local",
    "path": String
  },

  "extractedText": {
    "storage": "local",
    "path": String
  },

  "status": String,

  "timestamp": Date
}
```

ตรงกับ Data Schema 

`documents._id` ต้องใช้เป็น Reference สำหรับ Vector Chunk

---

# 20. ps_requirements

เก็บ:

```text
PS-01
PS-02
PS-03
PS-04
PS-05
PS-06
PS-07
PS-08
PS-09
```

Schema:

```javascript
{
  "_id": ObjectId(),

  "psCode": String,
  "requirement": String,
  "config": Object,
  "active": Boolean,

  "timestamp": Date
}
```



Import Service ไม่ประเมินผล PS

---

# 21. data_usages

Schema:

```javascript
{
  "_id": ObjectId(),

  "dataType": String,
  "dataId": ObjectId(),

  "curriculumId": ObjectId(),

  "psCodes": [String],

  "roles": [String],

  "templateFields": [String],

  "timestamp": Date
}
```



ใช้ Mapping:

```text
Data Record
    ↓
PS
Role
Template Field
```

---

# 22. generated_documents

Import Service ห้าม:

```text
CREATE
UPDATE
DELETE
```

Collection นี้

Collection นี้เป็น Responsibility ของ Generate Service 

---

## 22.1 template_ps

Collection นี้เก็บ metadata ของแม่แบบ PS โดยไฟล์จริงต้องอยู่ใน Host Storage ผ่าน Docker bind mount และ MongoDB เก็บเฉพาะ Relative Path

Schema:

```javascript
{
  "_id": ObjectId(),
  "version": Integer,
  "fileName": String,
  "fileType": "docx" | "pdf",
  "originalFile": {
    "storage": "local",
    "path": String
  },
  "timestamp": Date
}
```

ข้อกำหนด:

```text
version ต้องเป็นจำนวนเต็มบวกและห้ามซ้ำ
รองรับ DOCX และ PDF
ไม่สร้าง documents Record
ไม่ทำ Extraction / Parser / Chunking / Embedding / ChromaDB
Generate Service ดาวน์โหลดไฟล์ตาม version ผ่าน GET /api/templates/{version}/download
Download API ต้อง resolve เฉพาะ Relative Path ภายใน PROJECT_DATA_ROOT
```

---

# 23. ObjectId Relationships

Relationship ต้องเป็น:

```text
appointments.curriculumId
→ curricula._id

appointments.personId
→ persons._id

educations.personId
→ persons._id

academic_works.personId
→ persons._id

documents.curriculumId
→ curricula._id

data_usages.curriculumId
→ curricula._id

generated_documents.curriculumId
→ curricula._id

curricula.sources[].documentId
→ documents._id

persons.sources[].documentId
→ documents._id

educations.sources[].documentId
→ documents._id

academic_works.sources[].documentId
→ documents._id

appointments.sources[].documentId
→ documents._id
```



ห้ามใช้ชื่อแทน ObjectId Relationship

## 23.1 SourceReference and Field-Level Provenance

Structured records used by Monitor must carry their verified provenance in a
`sources` array directly on the related record:

```javascript
{
  "documentId": ObjectId(),
  "pageNumbers": [Integer],
  "fieldPaths": [String]
}
```

Rules:

```text
sources applies to curricula, persons, educations, academic_works, appointments
documentId must reference an existing documents._id
fieldPaths lists only fields actually supported by that source document
pageNumbers lists only pages that can be identified without guessing
use pageNumbers = [] when the exact page cannot be identified reliably
use sources = [] only when no verifiable source exists
never fabricate a documentId, page number, file name, or source
when an existing record is supported by another document, merge the new source
without deleting its previous sources
Monitor resolves documents.fileName and originalFile.path through documentId
```

Preview must show the proposed `sources` with each editable record. During
Confirm, the backend must reject a source whose `documentId` differs from the
confirmed Preview document or does not reference the resulting documents
record. Source identity is system-controlled even when other record values are
editable.

---

# 24. Structured Data Parser

ต้องมี Parser แยก:

```text
curriculum_parser
cv_parser
appointment_parser
```

Output:

### Curriculum Parser

```text
Curriculum
```

### CV Parser

```text
Person (รวม hasTeachingExperience)
Education[]
AcademicWork[]
```

### Appointment Parser

```text
Appointment
Person Reference
Curriculum Reference
```

---

# 25. Normalization

ต้อง Normalize ก่อน Duplicate Detection

ตัวอย่าง:

```text
"ผศ. ดร."
"ผศ.ดร."
"ผศ. ดร"
```

ให้ได้ Standard Format เดียว

Role ต้อง Normalize เป็น:

```text
programmeResponsible
programmeStaff
```

---

# 26. Duplicate Detection

ห้าม Insert ทุกครั้งโดยไม่ตรวจข้อมูลเดิม

Flow:

```text
Normalized Data
       ↓
Find Existing
       ↓
 ┌─────┴─────┐
 ▼           ▼
Found     Not Found
 │            │
Update      Insert
```

ต้องใช้ MongoDB Query / Index / Upsert ตามความเหมาะสม

---

# 27. Timestamp

ทุก MongoDB Record ต้องมี:

```text
timestamp
```

และ Update ทุกครั้งที่ Record เปลี่ยน

Timestamp ไม่ใช่ Collection หรือ Data Category ใหม่ 

---

# 28. Chunking Requirement

หลัง Extract Text ต้องทำ Chunking

Project Configuration:

```text
CHUNK_SIZE = 500 characters
CHUNK_OVERLAP = 100 characters
```

ห้าม:

```text
Whole Document
→ One Vector
```

ต้องเป็น:

```text
Document
 ↓
Page
 ↓
Chunk 1
Chunk 2
Chunk 3
...
```

ต้องรักษา Page Source

---

# 29. Chunk ID

รูปแบบ:

```text
{documentId}-p{page}-c{chunkIndex}
```

ตัวอย่าง:

```text
68ffabc123-p12-c03
```

Chunk ID ต้อง Unique

---

# 30. Chunk Metadata

ทุก Chunk ต้องมีขั้นต่ำ:

```text
documentId
curriculumId
documentType
page
chunkIndex
```

ควรมีเมื่อสามารถระบุได้:

```text
section
personId
```

ตัวอย่าง:

```json
{
  "documentId": "...",
  "curriculumId": "...",
  "documentType": "cv",
  "page": 12,
  "chunkIndex": 3,
  "section": "education",
  "personId": "..."
}
```

---

# 31. Embedding Requirement

Embedding Model:

```text
BAAI/bge-m3
```

Library:

```text
FlagEmbedding
```

Dense Vector Dimension:

```text
1024
```

Input:

```text
chunk.text
```

Output:

```text
1024-dimensional vector
```

---

# 32. Embedding Compatibility

Import:

```text
Chunk
 ↓
BAAI/bge-m3
 ↓
Vector
```

Generate:

```text
Query
 ↓
BAAI/bge-m3
 ↓
Query Vector
```

Import และ Generate ต้องใช้ Embedding Model เดียวกัน

หากเปลี่ยน Embedding Model ต้อง Re-index Vector ทั้งหมด

---

# 33. Vector Database

ใช้:

```text
ChromaDB
```

ChromaDB ต้องรันผ่าน Docker

เก็บ:

```text
Chunk ID
Chunk Text
Embedding
Metadata
```

Concept:

```text
Vector Record
│
├── id
├── text
├── embedding
└── metadata
     ├── documentId
     ├── curriculumId
     ├── documentType
     ├── page
     ├── chunkIndex
     ├── section
     └── personId
```

---

# 34. ChromaDB Persistence

ChromaDB ต้อง Persist บน Host

```text
project-data/chromadb
      ↕
ChromaDB Container
```

ข้อมูล Vector ต้องไม่หายเมื่อ Rebuild Container

---

# 35. MongoDB Persistence

MongoDB ต้อง Persist บน Host เช่น:

```text
project-data/mongodb
      ↕
/data/db
```

ข้อมูลต้องไม่หายเมื่อ Rebuild Container

---

# 36. Import Status

Status ที่ใช้:

```text
uploaded
processing
processed
failed
```

ความหมาย:

```text
uploaded
= รับและเก็บไฟล์แล้ว

processing
= Pipeline กำลังประมวลผล

processed
= MongoDB และ ChromaDB สำเร็จ

failed
= Pipeline ล้มเหลว
```

ห้ามตั้ง:

```text
processed
```

ก่อน Vector ถูกเก็บลง ChromaDB สำเร็จ

---

# 37. Import Processing Order

ลำดับต้องเป็น:

```text
01 Select File
02 Validate for Preview
03 Temporary Convert (when required)
04 Extract Text + Page for Preview
05 Clean Text
06 Parse Structured Data
07 Normalize
08 Create 500/100 Chunk Preview + Metadata
09 Show Preview grouped by Collection and ChromaDB
10 User Add / Edit / Delete
11 Confirm Import
12 Revalidate File + Edited Preview
13 Store Original
14 Create Document Record
15 Store Extracted Text
16 Duplicate Check
17 MongoDB Insert / Update
18 Relationship Validation
19 Data Usage Mapping
20 BGE-M3 Embedding
21 ChromaDB Insert
22 Final Validation
23 status = processed
```

No MongoDB or ChromaDB write is permitted before step 11. If the user cancels
at step 9 or 10, processing ends without a database change.

---

# 38. Monitor Handoff

Monitor ใช้ Structured Data จาก MongoDB:

```text
curricula
persons
educations
appointments
academic_works
data_usages
ps_requirements
```

OOAD ระบุว่าการตรวจ PS ใช้ข้อมูลจริงจาก Curriculum / Appointment / Education / AcademicWork 

Import Service ไม่สร้าง PASS / FAIL

---

# 39. Generate Handoff

Generate ใช้:

```text
MongoDB
+
ChromaDB
```

Flow:

```text
Generate Query
      ↓
BAAI/bge-m3
      ↓
Query Vector
      ↓
ChromaDB Search
      ↓
Top-K Chunks
      ↓
Document ID + Page
      ↓
Evidence
      ↓
Generate SAR
```

Import รับผิดชอบ Document Embedding

Generate รับผิดชอบ Query Embedding

---

# 40. Traceability

ระบบต้องสามารถย้อนกลับ:

```text
Generated Content
      ↓
Retrieved Chunk
      ↓
Chunk ID
      ↓
documentId
      ↓
documents._id
      ↓
originalFile.path
      ↓
Original File
      ↓
Page
```

Chunk ที่ไม่มี `documentId` หรือ Page Source ถือว่าไม่สมบูรณ์

---

# 41. Non-Functional Requirements

## NFR-001 Persistence

การ Rebuild Container ต้องไม่ทำให้:

```text
Original Document
MongoDB Data
ChromaDB Data
```

หาย

---

## NFR-002 Maintainability

ค่าต่อไปนี้ต้องอยู่ใน Environment / Configuration:

```text
MONGODB_URI

CHROMADB_HOST
CHROMADB_PORT

PROJECT_DATA_ROOT

EMBEDDING_MODEL
EMBEDDING_DIMENSION

CHUNK_SIZE
CHUNK_OVERLAP
```

---

## NFR-003 Logging

Import Pipeline ต้อง Log อย่างน้อย:

```text
Upload
Validation
Extraction
Parsing
MongoDB Write
Chunking
Embedding
ChromaDB Write
Error
```

---

## NFR-004 Testing

ใช้:

```text
pytest
```

ต้องมี Unit / Integration Test สำหรับส่วนสำคัญ เช่น:

```text
Upload
Validation
PDF Extraction
DOCX Extraction
Parsing
Normalization
MongoDB
Chunking
Embedding
ChromaDB
```

---

# 42. Technology Stack

```text
Backend
├── Python
├── FastAPI
└── Pydantic

Document Processing
├── PyMuPDF
├── python-docx
└── LibreOffice Headless

Data Processing
├── Python
└── Regex

Structured Database
├── MongoDB
└── PyMongo / Async MongoDB Driver

RAG / Vector
├── Chunking
├── BAAI/bge-m3
├── FlagEmbedding
└── ChromaDB

Infrastructure
├── Docker
└── Docker Compose

Storage
└── Host Local Storage + Docker Bind Mount

Testing
└── pytest
```

---

# 43. Forbidden Changes

Developer หรือ AI ห้ามเปลี่ยนสิ่งเหล่านี้เอง:

```text
❌ เพิ่ม Login

❌ เพิ่ม Dashboard

❌ เพิ่ม User Management

❌ เปลี่ยนชื่อ Collection

❌ เปลี่ยนชื่อ Field

❌ เพิ่ม role ใน persons

❌ ลบ appointments

❌ เปลี่ยน ObjectId Relationship

❌ ใช้ชื่ออาจารย์แทน personId

❌ ใช้ชื่อหลักสูตรแทน curriculumId

❌ เก็บไฟล์เฉพาะใน Docker Container

❌ เก็บ Absolute Path

❌ ใช้ Path จากเครื่องผู้ใช้

❌ เก็บ Binary PDF ใน MongoDB

❌ Insert Duplicate โดยไม่ตรวจ

❌ ทำ Page Source หาย

❌ Embedding ทั้งเอกสารเป็น Vector เดียว

❌ สร้าง Chunk โดยไม่มี documentId

❌ เปลี่ยน BAAI/bge-m3

❌ เปลี่ยน Dimension 1024

❌ เปลี่ยน ChromaDB

❌ ใช้ Embedding Model คนละตัวกับ Generate

❌ ให้ Import ตรวจ PASS / FAIL

❌ ให้ Import Generate SAR

❌ ให้ Import เขียน generated_documents

❌ ส่ง template เข้า Structured Parser, Chunking, Embedding หรือ ChromaDB

❌ ตั้ง processed ก่อน MongoDB + ChromaDB สำเร็จ
```

---

# 44. Acceptance Criteria

Import Service ถือว่าสำเร็จเมื่อสามารถทำได้ครบ:

```text
AC-01
Upload PDF/DOC/DOCX ได้

AC-02
เลือก documentType ได้

AC-03
เลือก Curriculum ได้

AC-04
ตรวจสอบไฟล์ได้

AC-05
Copy Original File เข้า System Storage ได้

AC-06
Original File Persist ผ่าน Docker Bind Mount

AC-07
สร้าง documents Record ได้

AC-08
Extract PDF พร้อม Page ได้

AC-09
Extract DOCX Paragraph/Table ได้

AC-10
Convert DOC ได้

AC-11
Parse Curriculum ได้

AC-12
Parse Person ได้

AC-13
Parse Education หลายรายการได้

AC-14
Parse AcademicWork หลายรายการได้

AC-15
Parse Appointment ได้

AC-16
Normalize Data ได้

AC-17
ป้องกันข้อมูลซ้ำได้

AC-18
บันทึก MongoDB ตาม Schema ได้

AC-19
ObjectId Relationship ถูกต้อง

AC-20
สร้าง DataUsage ได้

AC-21
Chunk Text ได้

AC-22
Chunk มี Source Page

AC-23
Chunk มี documentId

AC-24
สร้าง Embedding ด้วย BAAI/bge-m3 ได้

AC-25
Vector Dimension = 1024

AC-26
บันทึก Vector ใน ChromaDB ได้

AC-27
ChromaDB Persist ผ่าน Docker ได้

AC-28
Trace Chunk กลับ Original File + Page ได้

AC-29
status = processed เฉพาะเมื่อ Pipeline สำเร็จทั้งหมด

AC-30
Monitor อ่าน Structured Data ได้

AC-31
Generate Retrieve Chunk จาก ChromaDB ได้

AC-32
CV Import บันทึก persons.hasTeachingExperience เป็น Boolean ได้

AC-33
เลือกและนำเข้าเอกสารหลายไฟล์เป็น Queue ได้ โดยแต่ละไฟล์มีสถานะและ documents Record แยกกัน และไฟล์ที่ล้มเหลวไม่หยุดไฟล์ถัดไป

AC-34
อัปโหลด Template DOCX หรือ PDF พร้อม version ได้จากหน้า Import Document เดิม

AC-35
ไฟล์ Template Persist ที่ project-data/documents/original/template ผ่าน Docker bind mount

AC-36
สร้าง template_ps Record พร้อม version, Relative Path และ timestamp ได้ และปฏิเสธ version ซ้ำ

AC-37
Template ไม่สร้าง documents Record และไม่เข้าสู่ Extraction, Parser, Chunking, Embedding หรือ ChromaDB

AC-38
ดาวน์โหลด Template DOCX หรือ PDF ตาม version ผ่าน GET /api/templates/{version}/download ได้ โดยไม่เปิดเผย Absolute Path และไม่อนุญาต Path ออกนอก PROJECT_DATA_ROOT
```

```text
AC-39
Preview แสดงข้อมูลที่กำลังจะบันทึกแยกตาม Collection และ ChromaDB ได้ โดยยังไม่เขียน MongoDB หรือ ChromaDB

AC-40
ผู้ใช้เพิ่ม แก้ไข หรือลบข้อมูลใน Preview แล้วระบบตรวจ Schema และ ObjectId Relationship เดิมก่อนบันทึกได้

AC-41
Confirm Import เท่านั้นที่เริ่มเขียน MongoDB, สร้าง BGE-M3 Embedding และเขียน ChromaDB

AC-42
Cancel Preview แล้วจำนวนข้อมูลใน MongoDB และ ChromaDB ไม่เปลี่ยนแปลง

AC-43
ข้อมูลใน curricula, persons, educations, academic_works และ appointments มี sources Array ที่อ้างอิง documents._id จริง

AC-44
Monitor สามารถ Lookup sources.documentId เพื่อแสดง fileName, originalFile.path และหน้าที่เป็นแหล่งอ้างอิงได้

AC-45
เมื่อข้อมูลเดิมได้รับการยืนยันจากเอกสารใหม่ ระบบรวม Source ใหม่โดยไม่ลบ Source เดิม และไม่สร้าง Source ที่ไม่มีอยู่จริง

```

---

# 45. Definition of Done

Import Service ถือว่าเสร็จเมื่อ:

```text
Document
   ↓
Upload
   ↓
Validate
   ↓
Original Stored
   ↓
Extracted
   ↓
Structured Data → MongoDB
   +
Chunks → BGE-M3 → ChromaDB
   ↓
Traceability Valid
   ↓
status = processed
```

และข้อมูลพร้อมส่งต่อให้:

```text
Monitor
+
Generate
```

---

# 46. Final Scope

```text
IMPORT SERVICE
=
หน้า Import Document เพียงหน้าเดียว

+

Backend Import Pipeline

+

MongoDB Structured Data

+

Chunking

+

BAAI/bge-m3 Embedding

+

ChromaDB Vector Index

+

Docker Storage / Persistence
```

ขอบเขตจบที่:

```text
Structured Data Ready
+
Vector Evidence Ready
```

หลังจากนั้นเป็นหน้าที่ของ:

```text
Monitor → ตรวจ PS

Generate → Retrieve Evidence และสร้างเอกสาร
```

---

# MASTER IMPLEMENTATION RULE

**Code ต้องทำตาม SRS ฉบับนี้**

หาก Code, AI Prompt, Database Model หรือ Docker Configuration ขัดกับเอกสารนี้ ให้แก้ Code ให้ตรง SRS

หากต้องการเปลี่ยน:

- Collection
- Field
- Relationship
- File Storage
- Chunk Size
- Embedding Model
- Vector Database
- Docker Architecture
- Service Responsibility

ต้องแก้ SRS และเพิ่ม Version ก่อน จึงอนุญาตให้แก้ Code

ชื่อที่คุณเอาไปตั้งไฟล์ได้เลยคือ **`IMPORT_SERVICE_SRS_v1.0.md`** และแนะนำให้ใช้ไฟล์นี้เป็นตัวหลักในการสั่ง AI ว่า *“อ่าน SRS นี้ก่อนเขียนหรือแก้โค้ดทุกครั้ง และห้ามเปลี่ยนสเปกเอง”* ครับ
