// Exercises the real Import event handlers with an in-memory DOM and HTTP stubs.
// No browser, file upload, server request, or database write is performed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../services/import/backend/app/static/app.js'), 'utf8');

function node() {
  return { hidden: true, value: 'curriculum-id', options: [1, 2], handlers: {},
    classList: {add() {}, remove() {}, contains() {return false;}},
    setAttribute() {}, append() {}, before() {}, replaceChildren() {},
    closest() { return node(); }, querySelectorAll() { return []; },
    addEventListener(name, handler) { this.handlers[name] = handler; },
  };
}
async function harness() {
  const nodes = new Map();
  const select = key => { if (!nodes.has(key)) nodes.set(key, node()); return nodes.get(key); };
  const form = select('#import-form');
  form.elements = Object.assign([], {documentType: {value: 'cv'}});
  const calls = [];
  const progressNodes = ['upload','validation','storage','extraction','structured','mongodb','chunking','embedding','chromadb']
    .map(name => Object.assign(node(), {dataset:{progress:name}}));
  let respond = async url => ({ok: true, status: 200, json: async () => url.endsWith('/me') ? {} : []});
  const ctx = vm.createContext({
    window: {IMPORT_API_PREFIX: '/api/import'}, console,
    document: {querySelector: select, querySelectorAll: key => key === '#progress-list li' ? progressNodes : [], createElement: node},
    Option: function () {return node();},
    FormData: class { constructor() {this.values = {};} append(k,v) {this.values[k] = v;} },
    fetch: async (url, init) => {calls.push({url, init}); return respond(url, init);},
  });
  vm.runInContext(source, ctx);
  await new Promise(resolve => setImmediate(resolve));
  vm.runInContext(`
    renderFileList = () => {};
    renderPreviews = () => { previewPanel.hidden = false; };
    setFormLocked = () => {};
    beginPreview = () => {};
    beginConfirm = () => {};
    completeImport = () => {};
    validatePreviewForms = () => true;
  `, ctx);
  calls.length = 0;
  return {ctx, calls, nodes, setResponse: f => {respond=f;},
    run: code => vm.runInContext(code, ctx),
    submit: () => form.handlers.submit({preventDefault() {}}),
    confirm: () => select('#confirm-preview').handlers.click(),
  };
}
const ok = value => ({ok:true, status:200, json:async () => value});
const unauthorized = () => ({ok:false, status:401});

(async () => {
  const h = await harness();
  h.run('selectedFiles = Array.from({length:16}, (_,i) => ({name:`synthetic-${i}.pdf`,size:1}));');
  h.setResponse(async () => unauthorized());
  await h.submit();
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, '/api/auth/me');
  assert.equal(h.run('selectedFiles.length'),16);
  assert.equal(h.run('isProcessing'),false);
  assert.equal(h.run('sessionNotice.hidden'),false);
  console.log('PASS expired session sends zero files and retains all 16 selections');

  let previews = 0;
  h.calls.length = 0;
  h.setResponse(async url => {
    if (url.endsWith('/me')) return ok({});
    previews++;
    return previews === 2 ? unauthorized() : ok({previewId:'test-0', documentType:'cv'});
  });
  await h.submit();
  assert.equal(previews,2);
  assert.equal(h.run('pendingPreviews.length'),1);
  assert.equal(h.run('previewPaused'),true);
  assert.equal(h.run('confirmPreviewButton.disabled'),true);
  console.log('PASS batch stops immediately on 401 and keeps successful previews');

  h.run('pendingPreviews[0].preview.userEdit = "preserve-this";');
  let resumed = 0;
  h.setResponse(async url => url.endsWith('/me') ? ok({}) : ok({previewId:`test-${++resumed}`,documentType:'cv'}));
  await h.submit();
  assert.equal(resumed,15);
  assert.equal(h.run('pendingPreviews.length'),16);
  assert.equal(h.run('pendingPreviews[0].preview.userEdit'),'preserve-this');
  assert.equal(h.run('previewPaused'),false);
  console.log('PASS reauthentication resumes remaining previews without losing edits');

  let confirms = 0;
  h.setResponse(async url => {
    if (url.endsWith('/me')) return ok({});
    confirms++;
    return confirms === 2 ? unauthorized() : ok({documentId:'confirmed-0',chunkCount:1});
  });
  await h.confirm();
  assert.equal(confirms,2);
  assert.equal(h.run('pendingPreviews.length'),15);
  assert.equal(h.run('pendingPreviews[0].queueIndex'),1);
  assert.equal(h.run('previewPanel.hidden'),false);
  assert.equal(h.run('isProcessing'),false);
  let retried = 0;
  h.setResponse(async url => url.endsWith('/me') ? ok({}) : ok({documentId:`confirmed-${++retried}`,chunkCount:1}));
  await h.confirm();
  assert.equal(retried,15);
  assert.equal(h.run('queueStates.filter(s => s.status === "completed").length'),16);
  console.log('PASS confirm retry excludes already saved documents');
})().catch(error => {console.error(error); process.exitCode=1;});
