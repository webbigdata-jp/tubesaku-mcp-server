"""Real MCP protocol responses preserve creator-list terms through both bounding layers."""
from copy import deepcopy
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from services.agent_access import CREATOR_USAGE_TERMS

try:
    import mcp
except ImportError:
    mcp = None


@unittest.skipIf(mcp is None, 'MCP SDK is not installed')
class MCPCreatorUsageTermsTests(unittest.IsolatedAsyncioTestCase):
    async def test_creator_tools_preserve_terms_and_other_tools_omit_them(self):
        from httpx import ASGITransport, AsyncClient
        import mcp_tubesaku_server as server
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from services.agent_access import AgentHTTPMiddleware

        async def upstream(path, params=None):
            field = {
                '/api/vtubers/search': 'creators',
                '/api/live-now/search': 'streams',
                '/api/stream-schedule/search': 'streams',
                '/ai/games-preview.json': 'series',
                '/api/utattemita-ranking/search': 'songs',
            }[path]
            # Over-limit collections exercise PreviewClient and track_usage/bound_results.
            payload = {field: [{'id': i} for i in range(12)], 'total_matching_count': 12}
            if path in {'/api/vtubers/search', '/api/live-now/search', '/api/stream-schedule/search'}:
                payload['usage_terms'] = deepcopy(CREATOR_USAGE_TERMS)
            return payload

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'TUBESAKU_AGENT_LOG_DIR': directory,
            'TUBESAKU_MCP_QUOTA_DB': directory + '/quota.sqlite3',
        }), patch.object(server._preview_client, 'fetch_json', AsyncMock(side_effect=upstream)), \
                patch.object(server.mcp, '_session_manager', None):
            # Each SDK session manager can start only once; keep other tests' manager intact.
            app = AgentHTTPMiddleware(Starlette(
                routes=[Mount('/', app=server.mcp.streamable_http_app())], lifespan=server.lifespan))
            async with app.app.router.lifespan_context(app.app), AsyncClient(
                transport=ASGITransport(app=app), base_url='http://localhost:8000'
            ) as client:
                headers = {'accept': 'application/json, text/event-stream'}
                counter = 0

                async def rpc(method, params):
                    nonlocal counter
                    counter += 1
                    response = await client.post('/mcp', headers=headers, json={
                        'jsonrpc': '2.0', 'id': counter, 'method': method, 'params': params})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertNotIn('error', response.json())
                    return response

                response = await rpc('initialize', {'protocolVersion': '2025-03-26',
                    'capabilities': {}, 'clientInfo': {'name': 'creator-terms-test', 'version': '1'}})
                headers['mcp-session-id'] = response.headers['mcp-session-id']
                headers['mcp-protocol-version'] = response.json()['result']['protocolVersion']
                response = await client.post('/mcp', headers=headers, json={
                    'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                self.assertEqual(response.status_code, 202)
                for name, arguments, expected_field, maximum in (
                    ('search_vtubers', {}, 'creators', 10),
                    ('search_current_live_streams', {}, 'streams', 10),
                    ('search_live_streams', {}, 'streams', 5),
                    ('search_live_streams', {'debut_only': True}, 'streams', 5),
                    ('get_game_trends', {}, 'series', 12),
                    ('search_cover_songs', {}, 'songs', 3),
                ):
                    with self.subTest(tool=name, arguments=arguments):
                        response = await rpc('tools/call', {'name': name, 'arguments': arguments})
                        result = response.json()['result']
                        self.assertFalse(result.get('isError'), result)
                        text_payload = json.loads(result['content'][0]['text'])
                        payload = result.get('structuredContent', text_payload)
                        self.assertLessEqual(len(payload[expected_field]), maximum)
                        if name.startswith('search_') and name != 'search_cover_songs':
                            self.assertEqual(payload['usage_terms'], CREATOR_USAGE_TERMS)
                            self.assertEqual(text_payload['usage_terms'], CREATOR_USAGE_TERMS)
                        else:
                            self.assertNotIn('usage_terms', payload)
                            self.assertNotIn('usage_terms', text_payload)
