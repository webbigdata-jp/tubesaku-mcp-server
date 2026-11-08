"""Protocol integration checks; run with requirements-mcp.txt installed."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import mcp
except ImportError:
    mcp = None


@unittest.skipIf(mcp is None, 'MCP SDK is not installed')
class MCPSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_paths_session_correlation_errors_and_client_report(self):
        from httpx import AsyncClient, ASGITransport
        from mcp_tubesaku_server import app, mcp as server
        from services.agent_usage_report import get_agent_usage_report

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'TUBESAKU_AGENT_LOG_DIR': directory, 'TUBESAKU_MCP_QUOTA_DB': directory + '/quota.sqlite3', 'TUBESAKU_AGENT_IP_HASH_KEY': 'test-key'}):
            async with app.app.router.lifespan_context(app.app), AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost:8000') as client:
                headers = {'accept': 'application/json, text/event-stream', 'user-agent': 'test-agent'}
                response = await client.post('/mcp/', headers=headers, json={'jsonrpc': '2.0', 'id': 1,
                    'method': 'initialize', 'params': {'protocolVersion': '2025-03-26',
                    'capabilities': {}, 'clientInfo': {'name': 'Test Client', 'version': '1.2'}}}, follow_redirects=False)
                self.assertEqual(response.status_code, 200, response.text)
                session_id = response.headers['mcp-session-id']
                headers['mcp-session-id'] = session_id
                headers['mcp-protocol-version'] = '2025-03-26'
                response = await client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                self.assertEqual(response.status_code, 202)
                for index, method, params in [(2, 'tools/list', {}), (3, 'tools/call',
                        {'name': 'get_tubesaku_service_info', 'arguments': {}}),
                        (4, 'tools/call', {'name': 'read_tubesaku_markdown', 'arguments': {'path': '../private'}})]:
                    response = await client.post('/mcp/', headers=headers, json={'jsonrpc': '2.0', 'id': index,
                        'method': method, 'params': params}, follow_redirects=False)
                    self.assertEqual(response.status_code, 200, response.text)
                    if method == 'tools/list':
                        self.assertEqual(len(response.json()['result']['tools']), 10)
                for index, method, field in [(6, 'resources/list', 'resources'),
                                              (7, 'resources/templates/list', 'resourceTemplates')]:
                    response = await client.post('/mcp', headers=headers, json={
                        'jsonrpc': '2.0', 'id': index, 'method': method})
                    self.assertEqual(len(response.json()['result'][field]), 1)
                headers['mcp-session-id'] = 'expired-session'
                response = await client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 5, 'method': 'tools/list'})
                self.assertEqual(response.status_code, 404)
                headers['mcp-session-id'] = session_id
                for endpoint in ['/mcp', '/mcp/']:
                    response = await client.post(endpoint, headers=headers,
                        content=b'x' * (64 * 1024 + 1), follow_redirects=False)
                    self.assertEqual(response.status_code, 413)
                # Exercise the configured cap at a small size without allocating 128 sessions.
                with patch.object(server.session_manager, 'max_sessions', 1):
                    response = await client.post('/mcp', headers={
                        'accept': 'application/json, text/event-stream'}, json={
                        'jsonrpc': '2.0', 'id': 8, 'method': 'initialize', 'params': {
                            'protocolVersion': '2025-03-26', 'capabilities': {},
                            'clientInfo': {'name': 'Another Client', 'version': '1'}}})
                    self.assertEqual(response.status_code, 503)
            events = [json.loads(line) for path in Path(directory).glob('*.jsonl') for line in path.read_text().splitlines()]
            usage = [event for event in events if event['event'] == 'mcp_usage']
            self.assertEqual(len(usage), 2)
            self.assertEqual(usage[0]['client_name'], 'Test Client')
            self.assertEqual(usage[0]['session_key'], events[0]['session_key'])
            self.assertEqual(usage[1]['error_type'], 'ValueError')
            transports = [e for e in events if e['event'] == 'mcp_http_access']
            self.assertTrue(any(e['request_id'] == usage[0]['request_id'] for e in transports))
            self.assertNotIn(session_id, json.dumps(events))
            self.assertEqual(usage[1]['tool_arguments']['path'], '../private')
            self.assertTrue(any(e.get('response_reason') == 'session' and e['status'] == 404 for e in transports))
            report = get_agent_usage_report()
            row = next(row for row in report['clients'] if row['client_name'] == 'Test Client')
            self.assertEqual((row['sessions'], row['initialized'], row['listed'], row['tool_called'], row['tool_success']), (1, 1, 1, 1, 1))
