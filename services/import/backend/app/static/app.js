if (window.self !== window.top) document.documentElement.classList.add("is-embedded");

const importApi = (path) => (window.IMPORT_API_PREFIX || "/api") + path.replace(/^\/api/, "");
const form = document.querySelector("#import-form");
const curriculumSelect = document.querySelector("#curriculum");
const curriculumHelp = document.querySelector("#curriculum-help");
const curriculumGroup = curriculumSelect.closest(".field-group");
const curriculumMetadataGroup = document.querySelector("#curriculum-metadata-group");
const curriculumVersionInput = document.querySelector("#curriculum-version");
const curriculumStatusInput = document.querySelector("#curriculum-status");
const templateVersionGroup = document.querySelector("#template-version-group");
const templateVersionInput = document.querySelector("#template-version");
const dropZone = document.querySelector("#drop-zone");
const fileInput = document.querySelector("#file-input");
const dropCopy = document.querySelector("#drop-copy");
const fileList = document.querySelector("#file-list");
const submitButton = document.querySelector("#submit-button");
const submitLabel = document.querySelector("#submit-label");
const formError = document.querySelector("#form-error");
const statusPill = document.querySelector("#status-pill");
const progressItems = [...document.querySelectorAll("#progress-list li")];
const resultCard = document.querySelector("#result-card");
const resultIcon = document.querySelector(".result-icon");
const resultTitle = document.querySelector("#result-title");
const resultMessage = document.querySelector("#result-message");
const resultMeta = document.querySelector("#result-meta");
const resultDocumentId = document.querySelector("#result-document-id");
const resultIdLabel = document.querySelector("#result-id-label");
const resultChunks = document.querySelector("#result-chunks");
const previewPanel = document.querySelector("#preview-panel");
const previewFiles = document.querySelector("#preview-files");
const previewError = document.querySelector("#preview-error");
const confirmPreviewButton = document.querySelector("#confirm-preview");
const cancelPreviewButton = document.querySelector("#cancel-preview");

class ImportSessionError extends Error {
  constructor() {
    super("Session หมดอายุหรือถูกออกจากระบบ กรุณาเข้าสู่ระบบใหม่ในแท็บใหม่ แล้วกลับมากดปุ่มอีกครั้ง");
  }
}

const sessionNotice = document.createElement("div");
sessionNotice.className = "form-error";
sessionNotice.setAttribute("role", "alert");
sessionNotice.hidden = true;
const sessionText = document.createElement("p");
sessionText.textContent = new ImportSessionError().message;
const sessionLink = document.createElement("a");
sessionLink.href = "/login";
sessionLink.target = "_blank";
sessionLink.rel = "noopener";
sessionLink.textContent = "เข้าสู่ระบบในแท็บใหม่ (เก็บไฟล์และข้อมูลที่แก้ไว้ในหน้านี้)";
sessionNotice.append(sessionText, sessionLink);
const resumePreviewButton = document.createElement("button");
resumePreviewButton.type = "button";
resumePreviewButton.textContent = "สร้าง Preview รายการที่เหลือต่อ";
resumePreviewButton.hidden = true;
resumePreviewButton.addEventListener("click", () => form.requestSubmit());
sessionNotice.append(resumePreviewButton);
form.before(sessionNotice);

async function importFetch(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  if (response.status === 401) {
    sessionNotice.hidden = false;
    throw new ImportSessionError();
  }
  if (response.ok) sessionNotice.hidden = true;
  return response;
}

async function checkImportSession() {
  if (!window.IMPORT_API_PREFIX) return; // Standalone Import has no central login.
  const response = await importFetch("/api/auth/me");
  if (!response.ok) throw new Error("ตรวจสอบ Session ไม่สำเร็จ กรุณาลองใหม่");
}

function pauseForSession() {
  isProcessing = false;
  progressItems.forEach((item) => item.classList.remove("active", "failed"));
  statusPill.className = "status-pill review";
  statusPill.textContent = "Login required";
  resultCard.className = "result-card partial";
  resultIcon.textContent = "!";
  resultTitle.textContent = "หยุดคิวชั่วคราว — กรุณาเข้าสู่ระบบใหม่";
  resultMessage.textContent = "เก็บไฟล์ที่เลือกและข้อมูล Preview ไว้ในหน้านี้แล้ว ยังไม่ส่งรายการที่เหลือ";
  resultMeta.hidden = true;
}

const allowedExtensions = new Set(["pdf", "doc", "docx"]);
const editableCollections = {
  curriculum: ["curricula", "persons", "educations"],
  cv: ["persons", "educations", "academic_works"],
  appointment: ["appointments"],
  template: ["template_ps"],
};

let selectedFiles = [];
let queueStates = [];
let pendingPreviews = [];
let editorErrors = new Set();
let isProcessing = false;
let personOptions = [];
let previewPaused = false;
let activePreviewIndex = 0;
const activeRecordIndexes = new Map();

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function extensionOf(file) {
  return file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
}

function fileKey(file) {
  return `${file.name}\u0000${file.size}\u0000${file.lastModified}`;
}

function setError(message = "") {
  formError.textContent = message;
  formError.hidden = !message;
}

function setPreviewError(message = "") {
  previewError.textContent = message;
  previewError.hidden = !message;
}

function addSelectedFiles(files) {
  setError();
  const existing = new Set(selectedFiles.map(fileKey));
  const rejected = [];
  [...files].forEach((file) => {
    const extension = extensionOf(file);
    const templateMode = form.elements.documentType.value === "template";
    if (!allowedExtensions.has(extension) || (templateMode && !["docx", "pdf"].includes(extension))) {
      rejected.push(`${file.name}: รองรับเฉพาะ PDF, DOC และ DOCX`);
    } else if (file.size === 0) {
      rejected.push(`${file.name}: ไฟล์ต้องมีขนาดมากกว่า 0 bytes`);
    } else if (!existing.has(fileKey(file))) {
      selectedFiles.push(file);
      queueStates.push({ status: "waiting", message: "รอตรวจสอบ" });
      existing.add(fileKey(file));
    }
  });
  fileInput.value = "";
  if (rejected.length) setError(rejected.join(" · "));
  renderFileList();
}

function renderFileList() {
  fileList.replaceChildren();
  selectedFiles.forEach((file, index) => {
    const state = queueStates[index] || { status: "waiting", message: "รอตรวจสอบ" };
    const item = document.createElement("li");
    item.className = `file-card ${state.status}`;
    const badge = document.createElement("span");
    badge.className = "file-badge";
    badge.textContent = extensionOf(file).toUpperCase();
    const details = document.createElement("span");
    details.className = "file-details";
    const name = document.createElement("strong");
    name.textContent = file.name;
    const meta = document.createElement("small");
    meta.textContent = state.documentId
      ? `${formatBytes(file.size)} · ID ${state.documentId}`
      : formatBytes(file.size);
    details.append(name, meta);
    const status = document.createElement("span");
    status.className = "file-status";
    status.textContent = state.message;
    item.append(badge, details, status);
    if (!isProcessing && previewPanel.hidden) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.dataset.removeIndex = String(index);
      remove.setAttribute("aria-label", `นำ ${file.name} ออกจากคิว`);
      remove.textContent = "×";
      item.append(remove);
    }
    fileList.append(item);
  });
  const hasFiles = selectedFiles.length > 0;
  fileList.hidden = !hasFiles;
  dropCopy.hidden = hasFiles;
  submitLabel.textContent = hasFiles && selectedFiles.length > 1
    ? `Preview ${selectedFiles.length} Documents`
    : "Preview Data";
}

function resetProgress() {
  progressItems.forEach((item) => item.classList.remove("done", "active", "failed"));
  statusPill.className = "status-pill idle";
  statusPill.textContent = "Ready";
  resultCard.className = "result-card";
  resultIcon.textContent = "→";
  resultTitle.textContent = "พร้อมตรวจสอบเอกสาร";
  resultMessage.textContent = "ระบบจะแสดงข้อมูลให้ยืนยันก่อนบันทึกฐานข้อมูล";
  resultMeta.hidden = true;
  resultIdLabel.textContent = "Document ID";
}

function progress(name) {
  return progressItems.find((item) => item.dataset.progress === name);
}

function beginPreview(file, index, total) {
  resetProgress();
  ["upload", "validation", "extraction", "structured", "chunking"].forEach((name) => progress(name).classList.add("active"));
  statusPill.className = "status-pill processing";
  statusPill.textContent = `${index + 1}/${total}`;
  resultTitle.textContent = `กำลังสร้าง Preview: ${file.name}`;
  resultMessage.textContent = "ขั้นตอนนี้ยังไม่เขียน MongoDB หรือ ChromaDB";
}

function previewReady() {
  progressItems.forEach((item) => item.classList.remove("active", "failed", "done"));
  ["upload", "validation", "extraction", "structured", "chunking"].forEach((name) => progress(name).classList.add("done"));
  statusPill.className = "status-pill review";
  statusPill.textContent = "Review";
  resultCard.className = "result-card partial";
  resultIcon.textContent = "!";
  resultTitle.textContent = "รอการยืนยัน";
  resultMessage.textContent = "ตรวจข้อมูลด้านล่าง แล้วกด Confirm Import เพื่อบันทึกจริง";
}

function beginConfirm() {
  progressItems.forEach((item) => item.classList.remove("failed"));
  ["storage", "mongodb", "embedding", "chromadb"].forEach((name) => progress(name).classList.add("active"));
  statusPill.className = "status-pill processing";
  statusPill.textContent = "Saving";
  resultTitle.textContent = "กำลังบันทึกข้อมูลที่ยืนยันแล้ว";
  resultMessage.textContent = "กำลังเขียน MongoDB, สร้าง BGE-M3 Embedding และเขียน ChromaDB";
}

function completeImport(result) {
  progressItems.forEach((item) => {
    item.classList.remove("active", "failed");
    item.classList.add("done");
  });
  statusPill.className = "status-pill completed";
  statusPill.textContent = "Completed";
  resultCard.className = "result-card success";
  resultIcon.textContent = "✓";
  resultTitle.textContent = "Import Completed";
  resultMessage.textContent = "บันทึกข้อมูลแบบมีโครงสร้างและเวกเตอร์เรียบร้อยแล้ว";
  resultDocumentId.textContent = result.documentId;
  resultChunks.textContent = String(result.chunkCount);
  resultMeta.hidden = false;
}

function completeTemplate(result) {
  progressItems.slice(0, 3).forEach((item) => item.classList.add("done"));
  statusPill.className = "status-pill completed";
  statusPill.textContent = "Completed";
  resultCard.className = "result-card success";
  resultIcon.textContent = "✓";
  resultTitle.textContent = "Template Upload Completed";
  resultMessage.textContent = `บันทึก Template version ${result.version} เรียบร้อยแล้ว`;
  resultIdLabel.textContent = "Template ID";
  resultDocumentId.textContent = result.templateId;
  resultChunks.textContent = "Not applicable";
  resultMeta.hidden = false;
}

function failImport(message) {
  progressItems.filter((item) => item.classList.contains("active")).forEach((item) => {
    item.classList.remove("active");
    item.classList.add("failed");
  });
  statusPill.className = "status-pill failed";
  statusPill.textContent = "Failed";
  resultCard.className = "result-card failure";
  resultIcon.textContent = "!";
  resultTitle.textContent = "Import Failed";
  resultMessage.textContent = message;
  resultMeta.hidden = true;
}

async function responseError(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

function setFormLocked(locked) {
  [...form.elements].forEach((element) => { element.disabled = locked; });
  submitButton.disabled = locked;
  if (!locked) updateDocumentTypeMode();
}

function updateDocumentTypeMode() {
  const documentType = form.elements.documentType.value;
  const templateMode = documentType === "template";
  const curriculumMode = documentType === "curriculum";
  curriculumGroup.hidden = templateMode || curriculumMode;
  curriculumSelect.required = !templateMode && !curriculumMode;
  curriculumSelect.disabled = templateMode || curriculumMode || curriculumSelect.options.length <= 1;
  curriculumMetadataGroup.hidden = !curriculumMode;
  curriculumVersionInput.required = curriculumMode;
  curriculumVersionInput.disabled = !curriculumMode;
  curriculumStatusInput.required = curriculumMode;
  curriculumStatusInput.disabled = !curriculumMode;
  templateVersionGroup.hidden = !templateMode;
  templateVersionInput.required = templateMode;
  templateVersionInput.disabled = !templateMode;
  fileInput.accept = templateMode ? ".docx,.pdf" : ".pdf,.doc,.docx";
  setError();
  if (templateMode && selectedFiles.some((file) => !["docx", "pdf"].includes(extensionOf(file)))) {
    selectedFiles = [];
    queueStates = [];
    renderFileList();
  }
}

function templatePreview(file) {
  const version = Number(templateVersionInput.value);
  return {
    previewId: null,
    documentType: "template",
    fileType: extensionOf(file),
    fileName: file.name,
    curriculumId: null,
    collections: { template_ps: [{ version, fileName: file.name, fileType: extensionOf(file) }] },
    systemPreview: { template_ps: [{ originalFile: { storage: "local", path: "assigned after confirmation" }, timestamp: "assigned after confirmation" }] },
    chunks: [],
  };
}

function defaultRecord(collection, item) {
  const curriculumId = item.preview.curriculumId;
  const sourceFields = {
    curricula: ["curriculumCode", "curriculumName", "curriculumYear", "version", "status"],
    persons: ["title", "firstName", "lastName", "fullName", "academicPosition", "hasTeachingExperience"],
    educations: ["personId", "degree", "field", "institution", "graduationYear"],
    academic_works: ["personId", "workType", "title", "publicationYear", "database", "quartile"],
    appointments: ["curriculumId", "personId", "role", "roleName", "effectiveDate", "appointmentOrder.orderNumber", "appointmentOrder.orderDate", "status"],
  };
  const sources = sourceFields[collection]
    ? [{ documentId: item.preview.previewId, pageNumbers: [], fieldPaths: sourceFields[collection] }]
    : undefined;
  const defaults = {
    curricula: { curriculumCode: "", curriculumName: "", curriculumYear: 0, version: 1, status: "active", sources },
    persons: { title: "", firstName: "", lastName: "", fullName: "", academicPosition: "", hasTeachingExperience: false, sources },
    educations: { degree: "", field: "", institution: "", graduationYear: 0, sources, _personIndex: 0 },
    academic_works: { workType: "", title: "", publicationYear: 0, database: "", quartile: "", sources, _personIndex: 0 },
    appointments: { curriculumId, personId: "", role: "programmeStaff", roleName: "", effectiveDate: "", appointmentOrder: { orderNumber: "", orderDate: "" }, status: "active", sources },
    template_ps: { version: 1, fileName: item.file.name, fileType: extensionOf(item.file) },
  };
  if (collection === "persons" && item.preview.documentType === "curriculum") {
    delete defaults.persons.hasTeachingExperience;
    defaults.persons.sources[0].fieldPaths = defaults.persons.sources[0].fieldPaths.filter((field) => field !== "hasTeachingExperience");
  }
  return structuredClone(defaults[collection]);
}

const collectionLabels = {
  curricula: "ข้อมูลหลักสูตร",
  persons: "ข้อมูลบุคลากร",
  educations: "วุฒิการศึกษา",
  academic_works: "ผลงานทางวิชาการ",
  appointments: "ข้อมูลการแต่งตั้ง",
  template_ps: "ข้อมูลแม่แบบเอกสาร",
};

const collectionFormSchemas = {
  curricula: [
    { path: "curriculumCode", label: "รหัสหลักสูตร", required: true },
    { path: "curriculumName", label: "ชื่อหลักสูตร", type: "textarea", required: true, wide: true },
    { path: "curriculumYear", label: "ปีหลักสูตร", type: "number", required: true },
    { path: "version", label: "เวอร์ชัน", type: "number", min: 1, required: true },
    { path: "status", label: "สถานะหลักสูตร", type: "select", required: true, options: [["active", "กำลังใช้งาน"], ["inactive", "ไม่ได้ใช้งาน"]] },
  ],
  persons: [
    { path: "title", label: "คำนำหน้า" },
    { path: "firstName", label: "ชื่อ", required: true },
    { path: "lastName", label: "นามสกุล", required: true },
    { path: "fullName", label: "ชื่อเต็ม", required: true, wide: true },
    { path: "academicPosition", label: "ตำแหน่งทางวิชาการ", wide: true },
    { path: "hasTeachingExperience", label: "มีประสบการณ์สอน", type: "boolean", wide: true, optional: true },
  ],
  educations: [
    { path: "_personIndex", label: "บุคลากรเจ้าของวุฒิ", type: "personIndex", required: true, wide: true },
    { path: "degree", label: "ระดับวุฒิ", required: true },
    { path: "field", label: "สาขาวิชา", required: true },
    { path: "institution", label: "สถาบันการศึกษา", required: true, wide: true },
    { path: "graduationYear", label: "ปีที่สำเร็จการศึกษา", type: "number", required: true },
  ],
  academic_works: [
    { path: "_personIndex", label: "เจ้าของผลงาน", type: "personIndex", required: true, wide: true },
    { path: "workType", label: "ประเภทผลงาน", required: true },
    { path: "title", label: "ชื่อผลงาน", type: "textarea", required: true, wide: true },
    { path: "publicationYear", label: "ปีเผยแพร่", type: "number", required: true },
    { path: "database", label: "ฐานข้อมูล" },
    { path: "quartile", label: "Quartile" },
  ],
  appointments: [
    { path: "curriculumId", label: "หลักสูตร", type: "curriculumReference", readOnly: true, wide: true },
    { path: "personId", label: "บุคลากร", type: "personId", required: true, wide: true },
    { path: "role", label: "บทบาท", type: "select", required: true, options: [["programmeResponsible", "อาจารย์ผู้รับผิดชอบหลักสูตร"], ["programmeStaff", "อาจารย์ประจำหลักสูตร"]] },
    { path: "roleName", label: "ชื่อตำแหน่ง/บทบาท", required: true },
    { path: "effectiveDate", label: "วันที่มีผล", required: true },
    { path: "appointmentOrder.orderNumber", label: "เลขที่คำสั่ง", required: true },
    { path: "appointmentOrder.orderDate", label: "วันที่คำสั่ง", required: true },
    { path: "status", label: "สถานะ", type: "select", required: true, options: [["active", "กำลังใช้งาน"], ["inactive", "ไม่ได้ใช้งาน"]] },
  ],
  template_ps: [
    { path: "version", label: "เวอร์ชัน Template", type: "number", min: 1, required: true },
    { path: "fileName", label: "ชื่อไฟล์", readOnly: true, wide: true },
    { path: "fileType", label: "ชนิดไฟล์", readOnly: true },
  ],
};

function valueAtPath(record, path) {
  return path.split(".").reduce((value, key) => value?.[key], record);
}

function setValueAtPath(record, path, value, optional = false) {
  const keys = path.split(".");
  const finalKey = keys.pop();
  let target = record;
  keys.forEach((key) => {
    if (!target[key] || typeof target[key] !== "object") target[key] = {};
    target = target[key];
  });
  if (optional && value === "") delete target[finalKey];
  else target[finalKey] = value;
}

function personOptionLabel(person, index) {
  const name = person.fullName || [person.title, person.firstName, person.lastName].filter(Boolean).join(" ");
  return name || `บุคลากรคนที่ ${index + 1}`;
}

function createFieldControl(item, collection, record, field, pendingIndex, recordIndex) {
  const wrapper = document.createElement("label");
  wrapper.className = `preview-form-field${field.wide ? " wide" : ""}`;
  const label = document.createElement("span");
  label.textContent = field.label;
  if (field.required) label.dataset.required = "true";
  const id = `preview-${pendingIndex}-${collection}-${recordIndex}-${field.path.replaceAll(".", "-")}`;
  let control;
  if (field.type === "textarea") control = document.createElement("textarea");
  else if (["select", "boolean", "personIndex", "personId", "curriculumReference"].includes(field.type)) control = document.createElement("select");
  else {
    control = document.createElement("input");
    control.type = field.type === "number" ? "number" : "text";
  }
  control.id = id;
  control.className = "preview-field-control";
  control.required = Boolean(field.required);
  if (field.min !== undefined) control.min = String(field.min);
  if (field.maxLength !== undefined) control.maxLength = field.maxLength;

  const currentValue = valueAtPath(record, field.path);
  if (field.type === "select") {
    field.options.forEach(([value, text]) => control.add(new Option(`${text} (${value})`, value)));
    control.value = currentValue ?? "";
  } else if (field.type === "boolean") {
    control.add(new Option("ยังไม่ระบุ", ""));
    control.add(new Option("มี", "true"));
    control.add(new Option("ไม่มี", "false"));
    control.value = currentValue === undefined || currentValue === null ? "" : String(currentValue);
  } else if (field.type === "personIndex") {
    const people = item.preview.collections.persons || [];
    people.forEach((person, index) => control.add(new Option(personOptionLabel(person, index), String(index))));
    control.value = String(Number.isInteger(currentValue) ? currentValue : 0);
    if (!people.length) {
      control.add(new Option("ไม่พบบุคลากรใน Preview", ""));
      control.value = "";
    }
  } else if (field.type === "personId") {
    personOptions.forEach((person) => control.add(new Option(person.fullName, person.personId)));
    if (!personOptions.some((person) => person.personId === currentValue) && currentValue) {
      control.add(new Option(`บุคลากรปัจจุบัน · ${currentValue}`, currentValue));
    }
    control.value = currentValue ?? "";
  } else if (field.type === "curriculumReference") {
    const selected = [...curriculumSelect.options].find((option) => option.value === currentValue);
    control.add(new Option(selected?.textContent || currentValue || "ไม่พบหลักสูตร", currentValue || ""));
    control.value = currentValue ?? "";
  } else {
    control.value = currentValue ?? "";
  }

  if (field.readOnly) {
    control.readOnly = true;
    control.classList.add("system-controlled");
    const hint = document.createElement("small");
    hint.textContent = "ระบบเชื่อมโยงให้อัตโนมัติ";
    wrapper.append(label, control, hint);
    return wrapper;
  }

  const updateRecord = () => {
    let value = control.value;
    if (field.type === "number" || field.type === "personIndex") value = value === "" ? "" : Number(value);
    if (field.type === "boolean") value = value === "" ? "" : value === "true";
    setValueAtPath(record, field.path, value, field.optional);
    editorErrors.delete(`${pendingIndex}:${collection}:${recordIndex}:${field.path}`);
    setPreviewError();
  };
  control.addEventListener("input", updateRecord);
  control.addEventListener("change", updateRecord);
  wrapper.append(label, control);
  return wrapper;
}

function sourceSummary(item, record) {
  const section = document.createElement("div");
  section.className = "preview-source";
  const heading = document.createElement("strong");
  heading.textContent = "แหล่งที่มาของข้อมูล · ระบบกำหนด แก้ไขไม่ได้";
  section.append(heading);
  const sources = Array.isArray(record.sources) ? record.sources : [];
  if (!sources.length) {
    const empty = document.createElement("p");
    empty.textContent = "ไม่มีแหล่งอ้างอิงที่ตรวจสอบได้";
    section.append(empty);
    return section;
  }
  sources.forEach((source) => {
    const details = document.createElement("dl");
    const values = [
      ["ไฟล์", item.file.name],
      ["Document ID", source.documentId || "—"],
      ["หน้า", source.pageNumbers?.length ? source.pageNumbers.join(", ") : "ยังไม่ได้ระบุเลขหน้า"],
      ["ฟิลด์จากเอกสาร", source.fieldPaths?.join(", ") || "—"],
    ];
    values.forEach(([term, description]) => {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = description;
      row.append(dt, dd);
      details.append(row);
    });
    section.append(details);
  });
  return section;
}

function canRemoveRecord(item, collection, records) {
  if (collection === "curricula" || collection === "template_ps") return false;
  if (collection === "persons" && item.preview.documentType === "cv") return false;
  if (collection === "appointments" && records.length <= 1) return false;
  return true;
}

function canAddRecord(item, collection) {
  if (collection === "curricula" || collection === "template_ps") return false;
  if (collection === "persons" && item.preview.documentType === "cv") return false;
  return true;
}

function removePreviewRecord(item, collection, records, recordIndex) {
  records.splice(recordIndex, 1);
  if (collection === "persons") {
    ["educations", "academic_works"].forEach((dependentCollection) => {
      const dependents = item.preview.collections[dependentCollection] || [];
      for (let index = dependents.length - 1; index >= 0; index -= 1) {
        const personIndex = dependents[index]._personIndex;
        if (personIndex === recordIndex) dependents.splice(index, 1);
        else if (personIndex > recordIndex) dependents[index]._personIndex -= 1;
      }
    });
  }
}

function previewRecordLabel(collection, record, recordIndex, item) {
  const ownerIndex = Number(record._personIndex);
  const owner = Number.isInteger(ownerIndex) ? item?.preview?.collections?.persons?.[ownerIndex] : null;
  const ownerName = owner ? personOptionLabel(owner, ownerIndex) : "";
  if (collection === "persons") return personOptionLabel(record, recordIndex);
  if (collection === "educations") {
    const degree = record.degree || record.field || `วุฒิ ${recordIndex + 1}`;
    return ownerName ? `${ownerName} · ${degree}` : degree;
  }
  if (collection === "academic_works") {
    const work = record.title || `ผลงาน ${recordIndex + 1}`;
    return ownerName ? `${ownerName} · ${work}` : work;
  }
  if (collection === "appointments") return record.roleName || `รายการแต่งตั้ง ${recordIndex + 1}`;
  return `รายการ ${recordIndex + 1}`;
}

function editableGroup(item, pendingIndex, collection, records = item.preview.collections[collection], initiallyOpen = false) {
  const details = document.createElement("details");
  details.className = "preview-group";
  details.open = initiallyOpen;
  const summary = document.createElement("summary");
  summary.textContent = `${collectionLabels[collection] || collection} · ${collection} (${records.length})`;
  const body = document.createElement("div");
  body.className = "preview-group-body";
  const recordKey = `${item.queueIndex}:${collection}`;
  details.dataset.groupKey = recordKey;
  const requestedIndex = activeRecordIndexes.get(recordKey) ?? 0;
  const activeIndex = Math.max(0, Math.min(requestedIndex, Math.max(0, records.length - 1)));
  activeRecordIndexes.set(recordKey, activeIndex);
  const switcher = document.createElement("div");
  switcher.className = "preview-record-switcher";
  records.forEach((record, recordIndex) => {
    const select = document.createElement("button");
    select.type = "button";
    select.className = `preview-record-tab${recordIndex === activeIndex ? " active" : ""}`;
    select.textContent = previewRecordLabel(collection, record, recordIndex, item);
    select.title = select.textContent;
    select.setAttribute("aria-pressed", String(recordIndex === activeIndex));
    select.addEventListener("click", () => {
      activeRecordIndexes.set(recordKey, recordIndex);
      [...body.querySelectorAll(".preview-record")].forEach((recordElement, index) => { recordElement.hidden = index !== recordIndex; });
      [...switcher.querySelectorAll(".preview-record-tab")].forEach((tab, index) => {
        tab.classList.toggle("active", index === recordIndex);
        tab.setAttribute("aria-pressed", String(index === recordIndex));
      });
    });
    switcher.append(select);
    const wrapper = document.createElement("div");
    wrapper.className = "preview-record";
    wrapper.dataset.recordIndex = String(recordIndex);
    wrapper.hidden = recordIndex !== activeIndex;
    const toolbar = document.createElement("div");
    toolbar.className = "preview-record-toolbar";
    const label = document.createElement("span");
    label.textContent = `${collectionLabels[collection] || "รายการ"} ${recordIndex + 1}`;
    toolbar.append(label);
    if (canRemoveRecord(item, collection, records)) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "ลบรายการ";
      remove.addEventListener("click", () => {
        removePreviewRecord(item, collection, records, recordIndex);
        activeRecordIndexes.set(recordKey, Math.max(0, recordIndex - 1));
        editorErrors.clear();
        renderPreviews();
      });
      toolbar.append(remove);
    }
    const fields = document.createElement("div");
    fields.className = "preview-form-grid";
    collectionFormSchemas[collection].forEach((field) => {
      fields.append(createFieldControl(item, collection, record, field, pendingIndex, recordIndex));
    });
    wrapper.append(toolbar, fields);
    if (record.sources !== undefined) wrapper.append(sourceSummary(item, record));
    body.append(wrapper);
  });
  if (records.length || canAddRecord(item, collection)) body.prepend(switcher);
  if (canAddRecord(item, collection)) {
    const add = document.createElement("button");
    add.type = "button";
    add.className = "add-record-button";
    add.textContent = `+ เพิ่ม${collectionLabels[collection] || "รายการ"}`;
    add.addEventListener("click", () => {
      records.push(defaultRecord(collection, item));
      activeRecordIndexes.set(recordKey, records.length - 1);
      editorErrors.clear();
      renderPreviews();
      const refreshedGroup = previewPanel.querySelector(`[data-group-key="${recordKey}"]`);
      if (refreshedGroup) {
        refreshedGroup.open = true;
        refreshedGroup.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
    switcher.append(add);
  }
  details.append(summary, body);
  return details;
}

function chunksGroup(item, pendingIndex) {
  const records = item.preview.chunks;
  const details = document.createElement("details");
  details.className = "preview-group";
  const summary = document.createElement("summary");
  summary.textContent = `ข้อความสำหรับค้นหา · ChromaDB chunks (${records.length})`;
  const body = document.createElement("div");
  body.className = "preview-group-body";
  records.forEach((record, recordIndex) => {
    const wrapper = document.createElement("div");
    wrapper.className = "preview-record";
    const toolbar = document.createElement("div");
    toolbar.className = "preview-record-toolbar";
    const label = document.createElement("span");
    label.textContent = `ข้อความส่วนที่ ${recordIndex + 1}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "ลบ Chunk";
    remove.addEventListener("click", () => { records.splice(recordIndex, 1); renderPreviews(); });
    toolbar.append(label, remove);
    const fields = document.createElement("div");
    fields.className = "preview-form-grid";
    [
      { path: "text", label: "ข้อความ", type: "textarea", required: true, maxLength: 500, wide: true },
      { path: "metadata.page", label: "หน้า", type: "number", min: 1, required: true },
      { path: "metadata.chunkIndex", label: "ลำดับ Chunk", type: "number", min: 1, required: true },
      { path: "metadata.section", label: "หัวข้อ/ส่วน", optional: true, wide: true },
      { path: "metadata.documentId", label: "Document ID", readOnly: true, wide: true },
      { path: "metadata.curriculumId", label: "Curriculum ID", readOnly: true, wide: true },
    ].forEach((field) => fields.append(createFieldControl(item, "chunks", record, field, pendingIndex, recordIndex)));
    wrapper.append(toolbar, fields);
    body.append(wrapper);
  });
  const add = document.createElement("button");
  add.type = "button";
  add.className = "add-record-button";
  add.textContent = "+ เพิ่ม Chunk";
  add.addEventListener("click", () => {
    const page = records.at(-1)?.metadata?.page || 1;
    const chunkIndex = Math.max(0, ...records.filter((chunk) => chunk.metadata?.page === page).map((chunk) => chunk.metadata?.chunkIndex || 0)) + 1;
    records.push({ id: "assigned after confirmation", text: "", metadata: { documentId: item.preview.previewId, curriculumId: item.preview.curriculumId, documentType: item.preview.documentType, page, chunkIndex } });
    editorErrors.clear();
    renderPreviews();
  });
  body.append(add);
  details.append(summary, body);
  return details;
}

function flattenSystemValue(value, prefix = "") {
  if (Array.isArray(value)) return value.flatMap((item, index) => flattenSystemValue(item, `${prefix}${prefix ? " · " : ""}รายการ ${index + 1}`));
  if (value && typeof value === "object") return Object.entries(value).flatMap(([key, nested]) => flattenSystemValue(nested, `${prefix}${prefix ? " · " : ""}${key}`));
  return [[prefix, value === null || value === "" ? "—" : String(value)]];
}

function readOnlyGroup(title, value) {
  const details = document.createElement("details");
  details.className = "preview-group";
  const summary = document.createElement("summary");
  summary.textContent = `${title} (ระบบจัดการอัตโนมัติ)`;
  const body = document.createElement("div");
  body.className = "preview-group-body";
  const list = document.createElement("dl");
  list.className = "system-preview-list";
  flattenSystemValue(value).forEach(([term, description]) => {
    const row = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = description;
    row.append(dt, dd);
    list.append(row);
  });
  body.append(list);
  details.append(summary, body);
  return details;
}

function renderPreviews() {
  previewFiles.replaceChildren();
  activePreviewIndex = Math.max(0, Math.min(activePreviewIndex, Math.max(0, pendingPreviews.length - 1)));
  const fileSwitcher = document.createElement("div");
  fileSwitcher.className = "preview-file-switcher";
  fileSwitcher.setAttribute("role", "tablist");
  pendingPreviews.forEach((item, pendingIndex) => {
    const fileTab = document.createElement("button");
    fileTab.type = "button";
    fileTab.className = `preview-file-tab${pendingIndex === activePreviewIndex ? " active" : ""}`;
    fileTab.setAttribute("role", "tab");
    fileTab.setAttribute("aria-selected", String(pendingIndex === activePreviewIndex));
    const person = item.preview.collections.persons?.[0];
    fileTab.textContent = person ? personOptionLabel(person, pendingIndex) : item.file.name;
    fileTab.title = item.file.name;
    fileTab.addEventListener("click", () => {
      activePreviewIndex = pendingIndex;
      [...previewFiles.querySelectorAll(".preview-file")].forEach((file, index) => { file.hidden = index !== pendingIndex; });
      [...fileSwitcher.querySelectorAll(".preview-file-tab")].forEach((tab, index) => {
        tab.classList.toggle("active", index === pendingIndex);
        tab.setAttribute("aria-selected", String(index === pendingIndex));
      });
    });
    fileSwitcher.append(fileTab);
    const article = document.createElement("article");
    article.className = "preview-file";
    article.hidden = pendingIndex !== activePreviewIndex;
    article.dataset.previewIndex = String(pendingIndex);
    const header = document.createElement("div");
    header.className = "preview-file-header";
    const heading = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = item.file.name;
    const meta = document.createElement("small");
    meta.textContent = `${item.preview.documentType} · ${formatBytes(item.file.size)} · ยังไม่บันทึกฐานข้อมูล`;
    heading.append(title, meta);
    header.append(heading);
    const groups = document.createElement("div");
    groups.className = "preview-groups";
    editableCollections[item.preview.documentType].forEach((collection, groupIndex) => groups.append(editableGroup(item, pendingIndex, collection, item.preview.collections[collection], groupIndex === 0)));
    if (item.preview.documentType !== "template") groups.append(chunksGroup(item, pendingIndex));
    groups.append(readOnlyGroup("System records", item.preview.systemPreview));
    article.append(header, groups);
    previewFiles.append(article);
  });
  if (pendingPreviews.length > 1) previewFiles.prepend(fileSwitcher);
  previewPanel.hidden = pendingPreviews.length === 0;
  if (!previewPanel.hidden) previewPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function validatePreviewForms() {
  const controls = [...previewPanel.querySelectorAll(".preview-field-control")];
  const invalid = controls.find((control) => !control.checkValidity());
  if (invalid) {
    const article = invalid.closest(".preview-file");
    if (article?.hidden) {
      activePreviewIndex = Number(article.dataset.previewIndex);
      [...previewPanel.querySelectorAll(".preview-file")].forEach((file) => { file.hidden = file !== article; });
      [...previewPanel.querySelectorAll(".preview-file-tab")].forEach((tab, index) => {
        tab.classList.toggle("active", index === activePreviewIndex);
        tab.setAttribute("aria-selected", String(index === activePreviewIndex));
      });
    }
    const record = invalid.closest(".preview-record");
    const group = invalid.closest(".preview-group");
    if (group) group.open = true;
    if (record?.hidden) {
      const recordIndex = Number(record.dataset.recordIndex);
      [...group.querySelectorAll(".preview-record")].forEach((element, index) => { element.hidden = index !== recordIndex; });
      [...group.querySelectorAll(".preview-record-tab")].forEach((tab, index) => {
        tab.classList.toggle("active", index === recordIndex);
        tab.setAttribute("aria-pressed", String(index === recordIndex));
      });
    }
    invalid.reportValidity();
    invalid.focus();
    setPreviewError("กรุณากรอกข้อมูลในฟอร์มให้ครบและถูกต้องก่อนยืนยัน");
    return false;
  }
  return true;
}

async function loadCurricula() {
  try {
    const response = await importFetch(importApi("/api/curricula"), { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(await responseError(response));
    const curricula = await response.json();
    curriculumSelect.replaceChildren(new Option(curricula.length ? "เลือกหลักสูตร" : "ไม่พบหลักสูตรในระบบ", ""));
    curricula.forEach((curriculum) => {
      const option = document.createElement("option");
      option.value = curriculum.curriculumId;
      option.textContent = `${curriculum.curriculumCode} — ${curriculum.curriculumName} (${curriculum.curriculumYear}, v${curriculum.version})`;
      curriculumSelect.append(option);
    });
    curriculumSelect.disabled = curricula.length === 0;
    curriculumHelp.textContent = curricula.length ? `พบ ${curricula.length} หลักสูตร — ใช้ ObjectId เชื่อมโยงเอกสาร` : "ต้องมีข้อมูลหลักสูตรก่อนจึงจะนำเข้าเอกสารได้";
  } catch (error) {
    curriculumSelect.replaceChildren(new Option("โหลดหลักสูตรไม่สำเร็จ", ""));
    curriculumSelect.disabled = true;
    curriculumHelp.textContent = error.message;
    setError(`ไม่สามารถโหลดหลักสูตร: ${error.message}`);
  }
}

async function loadPersons() {
  try {
    const response = await importFetch(importApi("/api/persons"), { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(await responseError(response));
    personOptions = await response.json();
  } catch {
    personOptions = [];
  }
}

dropZone.addEventListener("click", (event) => {
  if (!event.target.closest("[data-remove-index]") && !isProcessing) fileInput.click();
});
dropZone.addEventListener("keydown", (event) => {
  if ((event.key === "Enter" || event.key === " ") && !isProcessing) {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => addSelectedFiles(fileInput.files));
form.querySelectorAll('input[name="documentType"]').forEach((input) => input.addEventListener("change", updateDocumentTypeMode));
fileList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-index]");
  if (!button || isProcessing) return;
  event.stopPropagation();
  const index = Number(button.dataset.removeIndex);
  selectedFiles.splice(index, 1);
  queueStates.splice(index, 1);
  renderFileList();
});
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", (event) => {
  if (!isProcessing) addSelectedFiles(event.dataTransfer.files);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isProcessing) return;
  setError();
  const documentType = form.elements.documentType.value;
  const templateMode = documentType === "template";
  const curriculumMode = documentType === "curriculum";
  if (!templateMode && !curriculumMode && !curriculumSelect.value) return setError("กรุณาเลือกหลักสูตร");
  if (curriculumMode && Number(curriculumVersionInput.value) < 1) return setError("Curriculum version ต้องเป็นจำนวนเต็มบวก");
  if (curriculumMode && !curriculumStatusInput.value) return setError("กรุณาเลือก Curriculum status");
  if (!selectedFiles.length) return setError("กรุณาเลือกไฟล์อย่างน้อย 1 ไฟล์");
  if (templateMode && selectedFiles.length !== 1) return setError("Template ต้องอัปโหลดครั้งละ 1 ไฟล์");
  if (templateMode && Number(templateVersionInput.value) < 1) return setError("Template version ต้องเป็นจำนวนเต็มบวก");
  isProcessing = true;
  try { await checkImportSession(); }
  catch (error) {
    isProcessing = false;
    if (error instanceof ImportSessionError) pauseForSession();
    return setError(error.message);
  }
  isProcessing = true;
  setFormLocked(true);
  if (!previewPaused) {
    pendingPreviews = [];
    activePreviewIndex = 0;
    activeRecordIndexes.clear();
    editorErrors.clear();
    queueStates = selectedFiles.map(() => ({ status: "waiting", message: "รอตรวจสอบ" }));
  }
  renderFileList();
  for (let index = 0; index < selectedFiles.length; index += 1) {
    if (pendingPreviews.some(item => item.queueIndex === index)) continue;
    const file = selectedFiles[index];
    queueStates[index] = { status: "processing", message: "กำลังสร้าง Preview" };
    renderFileList();
    beginPreview(file, index, selectedFiles.length);
    try {
      let preview;
      if (templateMode) {
        preview = templatePreview(file);
      } else {
        const payload = new FormData();
        payload.append("documentType", documentType);
        if (curriculumMode) {
          payload.append("curriculumVersion", curriculumVersionInput.value);
          payload.append("curriculumStatus", curriculumStatusInput.value);
        } else {
          payload.append("curriculumId", curriculumSelect.value);
        }
        payload.append("file", file, file.name);
        const response = await importFetch(importApi("/api/import/preview"), { method: "POST", body: payload });
        if (!response.ok) throw new Error(await responseError(response));
        preview = await response.json();
      }
      pendingPreviews.push({ file, preview, queueIndex: index });
      queueStates[index] = { status: "waiting", message: "รอยืนยัน", documentId: preview.previewId };
    } catch (error) {
      if (error instanceof ImportSessionError) {
        queueStates[index] = { status: "waiting", message: "รอเข้าสู่ระบบใหม่" };
        renderFileList();
        if (pendingPreviews.length) renderPreviews();
        previewPaused = true;
        resumePreviewButton.hidden = false;
        confirmPreviewButton.disabled = true;
        pauseForSession();
        return;
      }
      queueStates[index] = { status: "failed", message: `Preview ล้มเหลว · ${error.message}` };
    }
    renderFileList();
  }
  previewPaused = false;
  resumePreviewButton.hidden = true;
  confirmPreviewButton.disabled = false;
  isProcessing = false;
  if (pendingPreviews.length) {
    previewReady();
    renderPreviews();
  } else {
    setFormLocked(false);
    failImport("ไม่สามารถสร้าง Preview ได้");
  }
});

cancelPreviewButton.addEventListener("click", () => {
  previewPaused = false;
  resumePreviewButton.hidden = true;
  confirmPreviewButton.disabled = false;
  pendingPreviews = [];
  editorErrors.clear();
  previewPanel.hidden = true;
  setPreviewError();
  setFormLocked(false);
  queueStates = selectedFiles.map(() => ({ status: "waiting", message: "รอตรวจสอบ" }));
  renderFileList();
  resetProgress();
});

confirmPreviewButton.addEventListener("click", async () => {
  if (isProcessing || previewPaused) return;
  setPreviewError();
  if (editorErrors.size) return setPreviewError("กรุณาแก้ข้อมูลในฟอร์มให้ถูกต้องก่อนยืนยัน");
  if (!validatePreviewForms()) return;
  isProcessing = true;
  try { await checkImportSession(); }
  catch (error) {
    isProcessing = false;
    if (error instanceof ImportSessionError) pauseForSession();
    return setPreviewError(error.message);
  }
  isProcessing = true;
  confirmPreviewButton.disabled = true;
  cancelPreviewButton.disabled = true;
  beginConfirm();
  let completed = 0;
  for (const item of pendingPreviews) {
    const index = item.queueIndex;
    queueStates[index] = { status: "processing", message: "กำลังบันทึกข้อมูลที่ยืนยันแล้ว", documentId: item.preview.previewId };
    renderFileList();
    try {
      if (item.preview.documentType === "template") {
        const record = item.preview.collections.template_ps[0];
        if (!record || !Number.isInteger(Number(record.version)) || Number(record.version) < 1) throw new Error("template_ps ต้องมี version เป็นจำนวนเต็มบวก");
        if (!record.fileName || record.fileType !== extensionOf(item.file)) throw new Error("template_ps fileName หรือ fileType ไม่ถูกต้อง");
        const payload = new FormData();
        payload.append("version", String(record.version));
        payload.append("file", item.file, record.fileName);
        const response = await importFetch(importApi("/api/templates"), { method: "POST", body: payload });
        if (!response.ok) throw new Error(await responseError(response));
        const result = await response.json();
        queueStates[index] = { status: "completed", message: `สำเร็จ · Template v${result.version}`, documentId: result.templateId };
        completeTemplate(result);
      } else {
        const payload = new FormData();
        payload.append("documentType", item.preview.documentType);
        payload.append("curriculumId", item.preview.curriculumId);
        payload.append("previewData", JSON.stringify(item.preview));
        payload.append("file", item.file, item.file.name);
        const response = await importFetch(importApi("/api/import/confirm"), { method: "POST", body: payload });
        if (!response.ok) throw new Error(await responseError(response));
        const result = await response.json();
        queueStates[index] = { status: "completed", message: `สำเร็จ · ${result.chunkCount} chunks`, documentId: result.documentId };
        completeImport(result);
      }
      completed += 1;
    } catch (error) {
      if (error instanceof ImportSessionError) {
        queueStates[index] = { ...queueStates[index], status: "waiting", message: "รอเข้าสู่ระบบใหม่" };
        pendingPreviews = pendingPreviews.filter(p => queueStates[p.queueIndex].status !== "completed");
        confirmPreviewButton.disabled = false;
        cancelPreviewButton.disabled = false;
        renderFileList();
        renderPreviews();
        setPreviewError(error.message);
        pauseForSession();
        return;
      }
      queueStates[index] = { ...queueStates[index], status: "failed", message: `ล้มเหลว · ${error.message}` };
      failImport(error.message || "Import processing failed");
    }
    renderFileList();
  }
  isProcessing = false;
  confirmPreviewButton.disabled = false;
  cancelPreviewButton.disabled = false;
  previewPanel.hidden = true;
  pendingPreviews = [];
  setFormLocked(false);
  if (completed > 1) {
    resultTitle.textContent = "Import Queue Completed";
    resultMessage.textContent = `บันทึกสำเร็จ ${completed} จาก ${queueStates.length} ไฟล์`;
  }
});

resetProgress();
loadCurricula();
loadPersons();
updateDocumentTypeMode();
