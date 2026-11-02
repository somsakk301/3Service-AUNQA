"""Real HTTP checks against the running portal. No mocks. No credential output.

python deploy/smoke_test.py [--import-document]
The import option creates one clearly labelled synthetic curriculum via the real UI APIs.
It deliberately remains NOT_READY; it must never start a paid generation request.
"""
import argparse
import io
import json
import os
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--import-document', action='store_true')
parser.add_argument('--base', default='http://localhost')
parser.add_argument('--check-logout', action='store_true', help='Requires a separate PORTAL_TEST_USERNAME/PASSWORD; logout revokes every session of that account')
args = parser.parse_args()
env = dict(line.split('=',1) for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
test_username = os.environ.get('PORTAL_TEST_USERNAME', env['PORTAL_ADMIN_USERNAME'])
test_password = os.environ.get('PORTAL_TEST_PASSWORD', env['PORTAL_ADMIN_PASSWORD'])
if args.check_logout and (not os.environ.get('PORTAL_TEST_PASSWORD') or test_username == env['PORTAL_ADMIN_USERNAME']):
    parser.error('--check-logout requires a separate test account; never revoke the active admin sessions')
jar = CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
results = []

def request(path, data=None, headers=None, method=None, opener=None):
    req = urllib.request.Request(args.base+path, data=data, headers=headers or {}, method=method)
    try:
        with (opener or client).open(req, timeout=600) as r: return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e: return e.code, e.read(), e.headers

def check(name, ok):
    results.append({'check':name, 'passed':bool(ok)})
    print(('PASS ' if ok else 'FAIL ')+name, flush=True)
    if not ok: raise AssertionError(name)

def post(path, body):
    return request(path,json.dumps(body).encode(),{'Content-Type':'application/json','Origin':args.base},'POST')

def multipart(path, fields, filename, content):
    boundary = 'portal'+uuid4().hex
    chunks = []
    for key,value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n'.encode()+content+b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    return request(path,b''.join(chunks),{'Content-Type':f'multipart/form-data; boundary={boundary}','Origin':args.base},'POST')

def document_bytes():
    from xml.sax.saxutils import escape
    lines=['Curriculum Code: PORTAL-SMOKE-TEST','Curriculum Name: Portal Integration Test (Synthetic)', 'Curriculum Year: 2569']
    data=io.BytesIO()
    with ZipFile(data,'w') as doc:
        doc.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        doc.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        doc.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+''.join('<w:p><w:r><w:t>'+escape(line)+'</w:t></w:r></w:p>' for line in lines)+'<w:sectPr/></w:body></w:document>')
    return data.getvalue()

try:
    for route in ['/', '/login', '/import', '/monitor', '/monitor/ps/PS-01', '/generator', '/generator/history', '/generator/reference']:
        status,body,_=request(route)
        check('SPA deep link '+route,status==200 and b'id="root"' in body)
    protected=['/api/import/curricula','/api/monitor','/api/monitor/ps/PS-01','/api/generator/history','/api/generator/health','/import-workspace/']
    for path in protected: check('anonymous rejected '+path,request(path)[0]==401)
    check('internal auth endpoint hidden', request('/_session')[0]==404)
    check('cross-origin login rejected',request('/api/auth/login',b'{}',{'Content-Type':'application/json','Origin':'https://untrusted.example'},'POST')[0]==403)
    status,_,_=post('/api/auth/login',{'username':test_username,'password':test_password})
    check('real login',status==200)
    check('HttpOnly session cookie',any(c.name=='mornitor_session' and c.has_nonstandard_attr('HttpOnly') for c in jar))
    saved_cookies = '; '.join(c.name+'='+c.value for c in jar)
    for path in ['/api/auth/me','/api/import/curricula','/api/import/persons','/api/monitor','/api/generator/health','/api/generator/history','/import-workspace/']:
        check('authenticated '+path,request(path)[0]==200)
    _,body,_=request('/import-workspace/')
    check('Import asset and API prefixes',b'/import-workspace/static/app.js' in body and b'IMPORT_API_PREFIX="/api/import"' in body)
    check('production dev route absent',post('/api/generator/dev/generate',{})[0]==404)
    if args.import_document:
        _,body,_=request('/api/import/curricula')
        existing=next((c for c in json.loads(body) if c['curriculumCode']=='PORTAL-SMOKE-TEST'),None)
        if not existing:
            content=document_bytes()
            status,body,_=multipart('/api/import/import/preview',{'documentType':'curriculum','curriculumVersion':'1','curriculumStatus':'active'},'portal-smoke-test.docx',content)
            check('real DOCX preview',status==200)
            preview=json.loads(body)
            status,body,_=multipart('/api/import/import/confirm',{'documentType':'curriculum','curriculumId':preview['curriculumId'],'previewData':json.dumps(preview)},'portal-smoke-test.docx',content)
            if status!=201: print(body.decode()[:500])
            check('real DOCX confirm and embedding',status==201)
        _,body,_=request('/api/import/curricula')
        current=next(c for c in json.loads(body) if c['curriculumCode']=='PORTAL-SMOKE-TEST')
        status,body,_=request('/api/monitor?curriculumCode=PORTAL-SMOKE-TEST')
        monitor=json.loads(body)
        check('Import data reaches Monitor',status==200 and monitor.get('curriculum') is not None and len(monitor['results'])==9)
        check('incomplete curriculum NOT_READY',monitor['generationReadiness']['status']=='NOT_READY')
        check('PS detail works',request('/api/monitor/ps/PS-01?curriculumCode=PORTAL-SMOKE-TEST')[0]==200)
        status,body,_=post('/api/generator/generate',{'curriculum_id':current['curriculumId']})
        check('Generator enforces real Monitor gate',status==412 and b'NOT_READY' in body)
    if args.check_logout:
        check('logout',post('/api/auth/logout',{})[0]==200)
        check('revoked cookie cannot be reused',request('/api/import/curricula',headers={'Cookie':saved_cookies},opener=urllib.request.build_opener())[0]==401)
    else:
        print('SKIP logout: preserve other active sessions of this account', flush=True)
finally:
    (ROOT/'artifacts').mkdir(exist_ok=True)
    stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime())
    report=json.dumps({'timestamp':time.time(),'results':results},indent=2)
    (ROOT/'artifacts'/'smoke-results.json').write_text(report,encoding='utf-8')
    (ROOT/'artifacts'/f'smoke-{stamp}.json').write_text(report,encoding='utf-8')
