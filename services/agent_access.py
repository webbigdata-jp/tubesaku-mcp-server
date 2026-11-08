# Extracted from upstream production sources.
"""Shared commercial information and privacy-conscious agent usage events."""


import functools


import hashlib


import hmac


import inspect


import asyncio


from contextvars import ContextVar


import json


import logging


import os


import time


import uuid


from datetime import datetime, timezone


CREATOR_USAGE_TERMS = {
    'summary': 'TubeSakuの規約では、取得した情報をもとにした配信者への一方的な営業・勧誘のリスト作成を禁止しています。',
    'summary_en': "TubeSaku's terms prohibit using results to compile lists for unsolicited commercial outreach to creators.",
    'url': 'https://tubesaku.com/terms',
    'url_en': 'https://tubesaku.com/en/terms',
}


_EVENT_LOG = logging.getLogger('tubesaku.agent_usage')


_REQUEST_FIELDS = ContextVar('agent_request_fields', default=None)


_MCP_CONTEXT = None


_ARGUMENT_FIELDS = {}


def configure_mcp_context(provider):
    global _MCP_CONTEXT
    _MCP_CONTEXT = provider


def _label(value, limit=200):
    return ''.join(c for c in str(value or '') if c.isprintable())[:limit]


def _session_key(value):
    return hashlib.sha256(value.encode()).hexdigest() if value else None


def _usage_context():
    fields = dict(_REQUEST_FIELDS.get() or {})
    if _MCP_CONTEXT is not None:
        try:
            context = _MCP_CONTEXT().request_context
            request = context.request
            if request is not None:
                fields = dict(request.scope.get('agent_usage', fields))
            client = context.session.client_params.clientInfo
            fields.update(client_name=_label(client.name), client_version=_label(client.version),
                          client_info=logged_client({'name': client.name, 'version': client.version}))
        except (LookupError, ValueError, AttributeError):
            pass
    return fields


_DATASETS = {'google_trends.md', 'youtube-keywords_trends.md'}


def known_dataset(path):
    if not isinstance(path, str):
        return None
    return next((name for name in _DATASETS if path in {name, '/llms/' + name, '/static/llms/' + name}), None)


def service_info():
    from services.agent_quota import configuration
    usage_limits = configuration()
    status = os.getenv('TUBESAKU_PAID_STATUS', 'inquiry')
    if status not in {'inquiry', 'available', 'planned'}:
        status = 'inquiry'
    return {
        'public': {'available': True, 'description': '短期トレンド・候補検索の公開データ',
                 'limits': {'live_streams': 10, 'live_date_span_days': 7, 'cover_songs': 5, 'games': 10, 'game_weeks': 4, 'current_live_streams': 10, 'vtubers': 10, **usage_limits},
                 'catalog_url': 'https://tubesaku.com/ai/catalog.json'},
        'mcp_plans': {'public': 'available', 'account': 'coming_soon', 'paid': 'coming_soon',
                      'url': 'https://tubesaku.com/mcp-plans'},
        'future_paid_scope': {'status': 'planned', 'features': ['長期履歴', '一括取得', '継続監視', '個別比較レポート']},
        'paid': {
            'status': status,
            'description': '有料の個別分析・レポートについて相談できます。提供可否・範囲・価格はお問い合わせで確認してください。',
            'pricing': '個別見積もり。公開サンプルの参考価格は確定料金ではありません。',
            'url': 'https://tubesaku.com/ai-data#paid',
            'contact_url': 'https://tubesaku.com/contact',
            'api_subscription_available': False,
        },
    }


def public_service_info():
    """Public access and operational limits, without commercial plan metadata."""
    return {'public': service_info()['public']}


def data_service_info():
    """Operational data for routine results; commercial facts remain in service_info."""
    return {
        'name': 'TubeSaku',
        'public': service_info()['public'],
        'service_info_url': 'https://tubesaku.com/ai/service-info.json',
        'documentation_url': 'https://tubesaku.com/ai-data',
    }


def logged_arguments(arguments, allowed):
    """Only declared tool fields; bounded values, no arbitrary credential fields."""
    if not isinstance(arguments, dict):
        return {}
    def value(item):
        if isinstance(item, str):
            return ''.join(c for c in item if c.isprintable())[:500]
        if item is None or isinstance(item, (bool, int, float)):
            return item
        return '[unsupported value]'
    return {key: value(arguments[key]) for key in sorted(allowed) if key in arguments}


def logged_client(client):
    if not isinstance(client, dict):
        return {}
    return {key: _label(client[key]) for key in ('name','version','title') if key in client}


def record_event(event, **fields):
    # Explicit allowlist: declared search arguments only; no raw IDs, headers or results.
    allowed = {'surface', 'operation', 'status', 'duration_ms', 'method', 'request_id', 'bytes', 'dataset',
               'session_key', 'client_name', 'client_version', 'user_agent', 'source_key',
               'rpc_method', 'rpc_tool', 'path', 'error_type', 'response_reason',
               'client_info', 'tool_arguments', 'quota_reason', 'session_issued'}
    payload = {'timestamp': datetime.now(timezone.utc).isoformat(), 'event': event}
    payload.update({k: v for k, v in fields.items() if k in allowed})
    try:
        line = json.dumps(payload, ensure_ascii=False)
        _EVENT_LOG.info(line)
        # One file per worker avoids competing multiprocess rotation. Rotate externally.
        directory = os.getenv('TUBESAKU_AGENT_LOG_DIR', 'debug_logs/agent_usage')
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, f'events-{os.getpid()}.jsonl'), 'a', encoding='utf-8') as stream:
            stream.write(line + '\n')
    except Exception:
        logging.getLogger(__name__).warning('Agent usage event could not be written')


def track_usage(operation):
    def decorate(function):
        signature = inspect.signature(function)
        _ARGUMENT_FIELDS[operation] = set(signature.parameters)
        @functools.wraps(function)
        async def wrapped(*args, **kwargs):
            from services.agent_quota import consume, bound_results
            started = time.monotonic()
            status = 'success'
            error_type = None
            fields = _usage_context()
            quota_reason = None
            arguments = {}
            try:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                arguments = logged_arguments(bound.arguments, signature.parameters)
                # Public HTTP requests have request_id; direct internal calls are not
                # public MCP requests. SDK request.scope covers session worker tasks.
                usage = None
                if fields.get('request_id'):
                    allowed, usage = await asyncio.to_thread(consume, fields.get('session_key'))
                    if not allowed:
                        status = 'limited'
                        quota_reason = usage['limit_scope']
                        return json.dumps(usage, ensure_ascii=False) if signature.return_annotation is str else usage
                result = bound_results(await function(*args, **kwargs))
                if usage is not None and isinstance(result, dict):
                    result['usage'] = usage
                return result
            except Exception as exc:
                error_type = type(exc).__name__
                status = 'error'
                raise
            finally:
                request_id = fields.pop('request_id', str(uuid.uuid4()))
                fields.pop('tool_arguments', None)
                record_event('mcp_usage', **fields, surface='mcp', operation=operation, error_type=error_type,
                             dataset=known_dataset(kwargs.get('path', args[0] if args else None)) if 'markdown' in operation else None,
                             request_id=request_id, status=status, tool_arguments=arguments, quota_reason=quota_reason,
                             duration_ms=round((time.monotonic() - started) * 1000, 2))
        return wrapped
    return decorate


class AgentHTTPMiddleware:
    """Passively inspect bounded MCP metadata and declared tool arguments."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        started = time.monotonic()
        status = 500
        headers = dict(scope.get('headers', []))
        fields = {'request_id': str(uuid.uuid4()),
                  'session_key': _session_key(headers.get(b'mcp-session-id', b'').decode('latin1')),
                  'user_agent': _label(headers.get(b'user-agent', b'').decode('latin1')),
                  'path': scope.get('path') if scope.get('path') in {'/mcp', '/mcp/'} else 'other'}
        # HMAC permits correlation without storing raw IP. Never trust forwarded headers here.
        secret = os.getenv('TUBESAKU_AGENT_IP_HASH_KEY')
        if secret and scope.get('client'):
            fields['source_key'] = hmac.new(secret.encode(), scope['client'][0].encode(), hashlib.sha256).hexdigest()
        scope['agent_usage'] = fields
        token = _REQUEST_FIELDS.set(fields)
        body = bytearray()
        too_large = False
        response_body = bytearray()

        async def tracked_receive():
            nonlocal too_large
            message = await receive()
            if message['type'] == 'http.disconnect':
                fields['response_reason'] = 'client_disconnect'
            if message['type'] == 'http.request':
                chunk = message.get('body', b'')
                if len(body) + len(chunk) > 65536:
                    too_large = True
                    body.clear()
                if not too_large:
                    body.extend(chunk)
                if not message.get('more_body', False) and not too_large:
                    try:
                        rpc = json.loads(body)
                        method = rpc.get('method')
                        if method in {'initialize', 'notifications/initialized', 'tools/list', 'tools/call',
                                      'resources/list', 'resources/templates/list', 'resources/read', 'prompts/list', 'ping'}:
                            fields['rpc_method'] = method
                        if method == 'initialize':
                            client = rpc.get('params', {}).get('clientInfo', {})
                            fields.update(client_name=_label(client.get('name')), client_version=_label(client.get('version')),
                                          client_info=logged_client(client))
                        if method == 'tools/call':
                            fields['rpc_tool'] = _label(rpc.get('params', {}).get('name'), 120)
                            fields['tool_arguments'] = logged_arguments(
                                rpc.get('params', {}).get('arguments', {}),
                                _ARGUMENT_FIELDS.get(fields['rpc_tool'], set()))
                    except (ValueError, AttributeError, TypeError, RecursionError):
                        pass
            return message

        async def tracked_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                session = dict(message.get('headers', [])).get(b'mcp-session-id')
                if session:
                    fields['session_key'] = _session_key(session.decode('latin1'))
                    if fields.get('rpc_method') == 'initialize':
                        fields['session_issued'] = True
            elif message['type'] == 'http.response.body' and status >= 400:
                response_body.extend(message.get('body', b'')[:max(0, 4096 - len(response_body))])
            await send(message)

        try:
            # Both public paths reach the SDK's canonical endpoint without a redirect.
            if scope.get('path') == '/mcp/':
                scope = dict(scope, path='/mcp', raw_path=b'/mcp')
            await self.app(scope, tracked_receive, tracked_send)
        except Exception as exc:
            fields['error_type'] = type(exc).__name__
            raise
        finally:
            # Classify known transport failures without saving arbitrary error text.
            lower = bytes(response_body).lower()
            for needle, reason in [(b'session', 'session'), (b'accept', 'accept'),
                                   (b'content-type', 'content_type'), (b'json', 'json'),
                                   (b'origin', 'origin'), (b'host', 'host')]:
                if needle in lower and 'response_reason' not in fields:
                    fields['response_reason'] = reason
                    break
            record_event('mcp_http_access', **fields, surface='mcp', method=scope['method'],
                         status=status, duration_ms=round((time.monotonic() - started) * 1000, 2))
            _REQUEST_FIELDS.reset(token)
