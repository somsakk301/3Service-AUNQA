import assert from 'node:assert/strict';
import { endpoints } from '@monitor/api/endpoints';
import { login, logout } from '@monitor/api/authApi';
import { getJson, postJson, getBlob } from '@generator/services/httpClient';

const originalFetch = globalThis.fetch;
const calls = [];
globalThis.fetch = async (url, init) => {
  calls.push({url, init});
  return new Response(JSON.stringify({name: 'Routing test'}), {
    status: 200, headers: {'Content-Type': 'application/json'},
  });
};
try {
  await login('test-user', 'test-password');
  await logout();
  assert.equal(calls[0].url, '/api/auth/login');
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[1].url, '/api/auth/logout');
  assert.equal(endpoints.monitor(), '/api/monitor');
  assert.equal(endpoints.ps('PS-01'), '/api/monitor/ps/PS-01');
  assert.equal(endpoints.results(), '/api/monitor/results');
  assert.equal(endpoints.verification('PS-01'), '/api/monitor/ps/PS-01/verification');
  assert.equal(endpoints.review('PS-01'), '/api/monitor/ps/PS-01/review');
  await getJson('/api/history');
  await postJson('/api/generate', {});
  await getBlob('/api/documents/test/download');
  assert.deepEqual(calls.slice(2).map(c => c.url), [
    '/api/generator/history', '/api/generator/generate', '/api/generator/documents/test/download',
  ]);
  assert.ok(calls.slice(2).every(c => c.init.credentials === 'same-origin'));
  console.log('PASS: production frontend auth, Monitor and Generator API routing');
} finally {
  globalThis.fetch = originalFetch;
}
