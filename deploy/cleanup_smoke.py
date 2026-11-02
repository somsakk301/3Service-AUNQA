"""Remove only this run's synthetic curriculum after verification; archive it first.

Run inside import-backend: python /tmp/cleanup_smoke.py <exact-document-id>
Refuses when the test curriculum has acquired other documents/linked data.
"""
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from bson import ObjectId
from bson.json_util import dumps
from pymongo import MongoClient
import chromadb

document_id=ObjectId(sys.argv[1])
db=MongoClient('mongodb://mongodb:27017').aunqa_ps
record=db.documents.find_one({'_id':document_id,'fileName':'portal-smoke-test.docx','documentType':'curriculum'})
if not record: raise SystemExit('Exact synthetic document not found; no changes')
curriculum_id=record['curriculumId']
curriculum=db.curricula.find_one({'_id':curriculum_id,'curriculumCode':'PORTAL-SMOKE-TEST','curriculumName':'Portal Integration Test (Synthetic)'})
if not curriculum:raise SystemExit('Synthetic identity mismatch; no changes')
if db.documents.count_documents({'curriculumId':curriculum_id})!=1:raise SystemExit('Additional documents exist; no changes')
for name in ['appointments','generated_documents']:
    if db[name].count_documents({'curriculumId':curriculum_id}):raise SystemExit('Additional linked data exists; no changes')
usages=list(db.data_usages.find({'curriculumId':curriculum_id}))
if any(u.get('dataId')!=curriculum_id for u in usages):raise SystemExit('Unexpected linked usage; no changes')
base=Path('/app/project-data').resolve()
paths=[]
for key in ['originalFile','convertedFile','extractedText']:
    ref=record.get(key)
    if isinstance(ref,dict) and ref.get('path'):
        path=(base/Path(*PurePosixPath(ref['path']).relative_to('project-data').parts)).resolve()
        if not path.is_relative_to(base) or path.stem!=str(document_id):raise SystemExit('Unexpected file path; no changes')
        if path.is_file():paths.append(path)
collection=chromadb.HttpClient(host='chromadb',port=8000).get_collection('document_chunks')
vectors=collection.get(where={'documentId':str(document_id)},include=['documents','metadatas','embeddings'])
if vectors.get('embeddings') is not None:vectors['embeddings']=vectors['embeddings'].tolist()
archive=base/'test-backups'/f'{document_id}.zip'
archive.parent.mkdir(exist_ok=True)
with ZipFile(archive,'x') as output:
    output.writestr('database.json',dumps({'curricula':[curriculum],'documents':[record],'data_usages':usages}))
    output.writestr('vectors.json',dumps(vectors))
    for path in paths:output.write(path,str(path.relative_to(base)))
collection.delete(where={'documentId':str(document_id)})
db.data_usages.delete_many({'_id':{'$in':[u['_id'] for u in usages]}})
db.documents.delete_one({'_id':document_id})
db.curricula.delete_one({'_id':curriculum_id})
for path in paths:path.unlink()
print(f'Removed synthetic curriculum/document/vectors only. Recoverable archive: {archive}')
