"""Contract tests for the Portal adapter. Test doubles only; not production data."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from monitor.client import MonitorClient
from monitor.schemas import MonitorReadinessStatus

ID = '507f1f77bcf86cd799439011'

class MonitorAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def check(self, payload, status=200, count=1):
        db = MagicMock()
        db.curricula.count_documents = AsyncMock(return_value=count)
        db.curricula.find_one = AsyncMock(return_value={'curriculumCode':'CS & QA'})
        settings = MagicMock(monitor_service_url='http://monitor-backend:8000', monitor_timeout_seconds=5,
                             monitor_readiness_path='/legacy/{curriculum_id}', monitor_contract='aunqa-portal')
        response = httpx.Response(status, json=payload, request=httpx.Request('GET','http://monitor-backend:8000/api/monitor'))
        client = AsyncMock()
        client.__aenter__.return_value.get.return_value = response
        with patch('monitor.client.get_settings',return_value=settings), patch('common.mongo.get_db',return_value=db), patch('monitor.client.httpx.AsyncClient',return_value=client):
            result = await MonitorClient().check_readiness(ID)
        if count==1:
            client.__aenter__.return_value.get.assert_awaited_once_with('http://monitor-backend:8000/api/monitor',params={'curriculumCode':'CS & QA'})
        return result.status

    async def test_only_exact_ready_allows_generation(self):
        self.assertEqual(await self.check({'generationReadiness':{'status':'READY'}}),MonitorReadinessStatus.READY)
        for value in ['NOT_READY',None]:
            self.assertEqual(await self.check({'generationReadiness':{'status':value}}),MonitorReadinessStatus.NOT_READY)

    async def test_invalid_responses_fail_closed(self):
        for payload in [{},[],{'generatedReady':True},{'generationReadiness':{}},{'generationReadiness':{'status':True}}, {'generationReadiness':{'status':'ready'}}]:
            self.assertEqual(await self.check(payload),MonitorReadinessStatus.INVALID_RESPONSE)

    async def test_failure_and_ambiguous_curricula_block(self):
        self.assertEqual(await self.check({},503),MonitorReadinessStatus.MONITOR_UNAVAILABLE)
        self.assertEqual(await self.check({},count=2),MonitorReadinessStatus.NOT_READY)

if __name__=='__main__': unittest.main(verbosity=2)
