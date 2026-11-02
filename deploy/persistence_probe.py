"""Read-only digest to compare before/after restart; run inside import-backend."""
import hashlib
import json
from pathlib import Path
import chromadb
from pymongo import MongoClient
from bson.json_util import dumps

client=MongoClient('mongodb://mongodb:27017')
snapshot={}
for name in ['aunqa_ps','aunqa_config','aunqa_monitor']:
    db=client[name]
    snapshot[name]={}
    for collection in sorted(db.list_collection_names()):
        if collection.startswith('generation_') or collection=='portal_generation_jobs':continue
        documents=list(db[collection].find({}).sort('_id',1))
        snapshot[name][collection]={'count':len(documents),'sha256':hashlib.sha256(dumps(documents,sort_keys=True).encode()).hexdigest()}
snapshot['files']={str(p.relative_to('/app/project-data')):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in Path('/app/project-data/documents').rglob('*') if p.is_file()}
chroma=chromadb.HttpClient(host='chromadb',port=8000)
snapshot['vectors']={c.name:c.count() for c in chroma.list_collections()}
print(json.dumps(snapshot,sort_keys=True))
