"""Bounded public MCP work and streamed upstream input, without production traffic."""
import gzip
import unittest
from unittest.mock import AsyncMock, patch

try:
    import mcp
except ImportError:
    mcp = None


@unittest.skipIf(mcp is None, 'MCP SDK is not installed')
class MCPSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_limits_reject_before_fetch(self):
        import mcp_tubesaku_server as server
        with patch.object(server, 'get_allowed_md_paths', new_callable=AsyncMock) as fetch:
            for query in ['x' * 501, 'word ' * 21, '', '\t\n']:
                with self.subTest(query_length=len(query)), self.assertRaises(ValueError):
                    await server.search_tubesaku_context(query)
            fetch.assert_not_awaited()

    async def test_normal_query_and_repeated_terms_have_bounded_score(self):
        import mcp_tubesaku_server as server
        with patch.object(server, 'get_allowed_md_paths', AsyncMock(return_value=['/llms/google_trends.md'])), patch.object(
                server, 'fetch_text', AsyncMock(return_value='VTuber vtuber ゲーム')):
            result = await server.search_tubesaku_context('VTuber\tvtuber ゲーム')
            self.assertEqual(result['results'][0]['score'], 3)
            self.assertEqual(result['query'], 'VTuber\tvtuber ゲーム')
            for query in ['あ' * 500, ' '.join('word' + str(i) for i in range(20))]:
                await server.search_tubesaku_context(query)

    async def test_index_document_count_is_bounded_after_deduplication(self):
        import mcp_tubesaku_server as server
        text = '\n'.join('/llms/file' + str(i) + '.md' for i in range(20))
        with patch.object(server, 'fetch_text', AsyncMock(return_value=text + '\n' + text)):
            self.assertEqual(len(await server.get_allowed_md_paths()), 20)
        with patch.object(server, 'fetch_text', AsyncMock(return_value=text + '\n/llms/extra.md')):
            with self.assertRaises(ValueError):
                await server.get_allowed_md_paths()

    async def test_streamed_limits_include_compression_and_error_json(self):
        import httpx
        import mcp_tubesaku_server as server

        class Chunks(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'abc'
                yield b'def'

        class Compressed(httpx.AsyncByteStream):
            async def __aiter__(self):
                raise AssertionError('Compressed stream must be refused before decoding')
                yield gzip.compress(b'x' * 1024)

        real_client = httpx.AsyncClient
        def factory(response):
            return lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: response), **kwargs)
        with patch.object(server, 'MAX_TEXT_BYTES', 5), patch.object(server.httpx, 'AsyncClient', factory(
                httpx.Response(200, stream=Chunks()))):
            with self.assertRaises(ValueError):
                await server.fetch_text(server.LLMS_URL)
        with patch.object(server, 'MAX_TEXT_BYTES', 5), patch.object(server.httpx, 'AsyncClient', factory(
                httpx.Response(200, stream=Compressed(), headers={'content-encoding': 'gzip'}))):
            with self.assertRaises(ValueError):
                await server.fetch_text(server.LLMS_URL)
        for status in [200, 400]:
            with self.subTest(status=status), patch.object(server, 'MAX_JSON_BYTES', 5), patch.object(
                    server.httpx, 'AsyncClient', factory(httpx.Response(status, stream=Chunks()))):
                with self.assertRaises(ValueError):
                    await server.fetch_json('/ai/catalog.json')
        with patch.object(server, 'MAX_TEXT_BYTES', 5), patch.object(server.httpx, 'AsyncClient', factory(
                httpx.Response(200, content='éabc'.encode('latin1'), headers={'content-type': 'text/plain; charset=iso-8859-1'}))):
            self.assertEqual(await server.fetch_text(server.LLMS_URL), 'éabc')
        with patch.object(server, 'MAX_JSON_BYTES', 8), patch.object(server.httpx, 'AsyncClient', factory(
                httpx.Response(200, content=b'{"ok":1}'))):
            self.assertEqual(await server.fetch_json('/ai/catalog.json'), {'ok': 1})
        with patch.object(server.httpx, 'AsyncClient', factory(httpx.Response(400, json={'message': 'invalid_request'}))):
            with self.assertRaisesRegex(ValueError, 'invalid_request'):
                await server.fetch_json('/ai/catalog.json')
