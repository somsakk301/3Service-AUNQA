"""Isolated integration test of real document APIs + Mongo, using a synthetic DOCX.

LLM and Monitor are test doubles ONLY in this process. Does not prove real SAR generation.
"""
import asyncio
import os
from pathlib import Path
import tempfile
import uuid

test_db = 'portal_lifecycle_test_' + uuid.uuid4().hex
os.environ['MONGODB_DB_NAME'] = test_db
os.environ['MONITOR_CONTRACT'] = 'aunqa-portal'
os.environ['OUTPUT_DIR'] = tempfile.mkdtemp(prefix='portal-lifecycle-')

async def main():
    import docx
    import httpx
    import api_server as api
    from common.mongo import get_db
    from monitor.schemas import MonitorReadinessResult, MonitorReadinessStatus
    from bson import ObjectId
    db=get_db()
    curriculum=ObjectId()
    await db.curricula.insert_one({'_id':curriculum,'curriculumName':'Synthetic API lifecycle test'})
    async def readiness(identifier):
        return MonitorReadinessResult(status=MonitorReadinessStatus.READY,curriculum_id=identifier,detail='test process only')
    async def generate(run_id):
        document=docx.Document()
        document.add_paragraph('Synthetic document lifecycle test')
        path=Path(os.environ['OUTPUT_DIR']) / (run_id+'.docx')
        document.save(path)
        await db.generation_criteria_log.insert_one({'run_id':run_id,'criterion':'TEST','status':'completed','citations':[],'sections':[]})
        return path
    api._monitor_client.check_readiness=readiness
    api.run_master=generate
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app),base_url='http://test') as client:
            response=await client.post('/api/generate',json={'curriculum_id':str(curriculum)})
            assert response.status_code==200,response.text
            job=response.json()['job_id']
            for _ in range(50):
                status=(await client.get(f'/api/generate/{job}/status')).json()
                if status['status']!='running':break
                await asyncio.sleep(.1)
            assert status['status']=='completed',status
            preview=await client.get(f'/api/generate/{job}/preview')
            assert preview.status_code==200 and 'Synthetic document' in preview.json()['html']
            download=await client.get(f'/api/generate/{job}/download')
            assert download.status_code==200 and download.content[:2]==b'PK'
            assert download.headers['x-document-version']=='1'
            history=await client.get('/api/history')
            assert history.status_code==200 and 'Synthetic' not in history.text # filename is server-generated
            snapshot=await client.get('/api/history/1/download')
            assert snapshot.status_code==200 and snapshot.content==download.content
            saved=await db.portal_generation_jobs.find_one({'_id':job})
            assert saved['status']=='completed'
            api._jobs.clear()
            await api.restore_portal_jobs()
            restored=await client.get(f'/api/generate/{job}/preview')
            assert restored.status_code==200
            await db.portal_generation_jobs.insert_one({'_id':'interrupted-test','status':'running','output_path':None,'error':None})
            await api.restore_portal_jobs()
            assert api._jobs['interrupted-test']['status']=='failed'
            print('PASS synthetic lifecycle: status, preview, DOCX download, history snapshot, job restoration, interrupted-job recovery')
    finally:
        assert db.name==test_db and db.name.startswith('portal_lifecycle_test_')
        await db.client.drop_database(test_db)

asyncio.run(main())

