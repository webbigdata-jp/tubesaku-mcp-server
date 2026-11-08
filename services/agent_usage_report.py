"""Read-only, bounded reporting of agent JSONL logs (including gzip rotations)."""
from collections import Counter
import heapq
from datetime import datetime, timedelta, timezone
import gzip
import os
from pathlib import Path

# A malformed or unexpectedly large log must not make the admin page unbounded.
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 100
MAX_LINE_BYTES = 16 * 1024


def get_agent_usage_report(days=7):
    days = max(1, min(int(days), 30))
    directory = Path(os.getenv('TUBESAKU_AGENT_LOG_DIR', 'debug_logs/agent_usage'))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    report = {'days': days, 'directory': str(directory.resolve()), 'rows': [], 'recent': [],
              'totals': {'http_access': 0, 'mcp_http_access': 0, 'mcp_usage': 0},
              'argument_rows': [], 'clients': [], 'sessions': [], 'uncorrelated_usage': 0, 'files_read': 0, 'malformed_lines': 0, 'unreadable_files': 0,
              'truncated': False, 'missing_directory': not directory.exists()}
    sessions = {}
    argument_counts = Counter()
    counts = Counter()
    durations = Counter()
    measured = Counter()
    recent = []
    used_bytes = 0
    try:
        files = sorted(directory.glob('events-*.jsonl*'), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        report['error'] = 'ログ保存先を読み取れません。保存先と権限を確認してください。'
        return report
    report['truncated'] = len(files) > MAX_FILES
    for path in files[:MAX_FILES]:
        if used_bytes >= MAX_BYTES:
            report['truncated'] = True
            break
        try:
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rb') as stream:
                report['files_read'] += 1
                while True:
                    line = stream.readline(MAX_LINE_BYTES + 1)
                    if not line:
                        break
                    used_bytes += len(line)
                    if used_bytes > MAX_BYTES:
                        report['truncated'] = True
                        break
                    if len(line) > MAX_LINE_BYTES:
                        # Stop this malformed file rather than rendering a partial event.
                        report['malformed_lines'] += 1
                        report['truncated'] = True
                        break
                    try:
                        row = json_parse_event(line, cutoff)
                    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
                        report['malformed_lines'] += 1
                        continue
                    if row is None:
                        continue
                    if row['event'] == 'mcp_usage':
                        import json
                        for field, value in row.get('tool_arguments', {}).items():
                            argument_counts[(row['operation'],field,json.dumps(value,ensure_ascii=False))] += 1
                    session_key = row.get('session_key')
                    if session_key:
                        session = sessions.setdefault(session_key, {'session_key': session_key, 'client_name': '不明',
                            'client_version': '', 'initialized': False, 'listed': False, 'tool_called': False,
                            'tool_success': False, 'last_seen': row['timestamp'], 'http_errors': 0})
                        if row.get('client_name'):
                            session['client_name'] = row['client_name']
                            session['client_version'] = row.get('client_version', '')
                        method = row.get('rpc_method')
                        session['initialized'] |= method == 'initialize' and row['status'] == '200'
                        session['listed'] |= method in {'tools/list', 'resources/list', 'resources/templates/list'} and row['status'] == '200'
                        session['tool_called'] |= (method == 'tools/call' or (row['event'] == 'mcp_usage' and not row['operation'].startswith('tubesaku_')))
                        session['tool_success'] |= row['event'] == 'mcp_usage' and row['status'] == 'success' and not row['operation'].startswith('tubesaku_')
                        session['http_errors'] += int(row['event'] == 'mcp_http_access' and row['status'].isdigit() and int(row['status']) >= 400)
                        session['last_seen'] = max(session['last_seen'], row['timestamp'])
                    elif row['event'] == 'mcp_usage':
                        report['uncorrelated_usage'] += 1
                    key = (row['event'], row['operation'], row['dataset'], row['status'])
                    counts[key] += 1
                    report['totals'][row['event']] += 1
                    if row['duration_ms'] is not None:
                        durations[key] += row['duration_ms']
                        measured[key] += 1
                    heapq.heappush(recent, (row['timestamp'], used_bytes, row))
                    if len(recent) > 100:
                        heapq.heappop(recent)
        except (OSError, EOFError):
            report['unreadable_files'] += 1
    report['argument_rows'] = [dict(operation=k[0], field=k[1], value=k[2], count=n) for k,n in argument_counts.most_common(20)]
    report['rows'] = [dict(event=key[0], operation=key[1], dataset=key[2], status=key[3],
                           count=count, average_ms=round(durations[key] / measured[key], 1) if measured[key] else None)
                      for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    clients = {}
    for session in sessions.values():
        client = clients.setdefault(session['client_name'], dict(client_name=session['client_name'], sessions=0,
            initialized=0, listed=0, tool_called=0, tool_success=0))
        client['sessions'] += 1
        for stage in ('initialized', 'listed', 'tool_called', 'tool_success'):
            client[stage] += int(session[stage])
    report['clients'] = sorted(clients.values(), key=lambda row: (-row['tool_called'], row['client_name']))
    report['sessions'] = sorted(sessions.values(), key=lambda row: row['last_seen'], reverse=True)[:100]
    report['recent'] = [entry[2] for entry in sorted(recent, reverse=True)]
    return report


def json_parse_event(line, cutoff):
    import json
    import math
    row = json.loads(line)
    if not isinstance(row, dict):
        raise ValueError('Event must be a JSON object')
    timestamp = datetime.fromisoformat(row['timestamp'])
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp must contain timezone')
    if row['event'] not in {'http_access', 'mcp_http_access', 'mcp_usage'} or timestamp < cutoff:
        return None
    duration = row.get('duration_ms')
    if not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration < 0:
        duration = None
    from services.agent_access import logged_arguments, logged_client
    argument_fields = {'query','path','date_from','date_to','start_time','end_time','keyword','debut_only','category','limit','debut_year','game','segment','weeks','scope','require_playlist_video'}
    # Read an allowlist only, even if a log has extra fields.
    return {'tool_arguments': logged_arguments(row.get('tool_arguments'), argument_fields),
            'client_info': logged_client(row.get('client_info')),
            'quota_reason': str(row.get('quota_reason') or '')[:40],
            'timestamp': timestamp.astimezone(timezone.utc).isoformat(),
            'timestamp_jst': timestamp.astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S'),
            **{key: str(row.get(key) or '')[:256] for key in ('session_key', 'client_name', 'client_version',
                'request_id', 'rpc_method', 'rpc_tool', 'user_agent', 'source_key', 'path', 'error_type', 'response_reason')},
            'event': row['event'], 'operation': str(row.get('operation') or '-')[:120],
            'dataset': str(row.get('dataset') or '-')[:120],
            'status': str(row.get('status') or '-')[:40], 'duration_ms': duration}
