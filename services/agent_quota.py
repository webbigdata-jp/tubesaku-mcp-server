"""Atomic, persistent MCP execution counters. Independent of session SDK workers."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
MAX_RESULTS = 10


def configuration():
    session = int(os.getenv('TUBESAKU_MCP_SESSION_LIMIT', '20'))
    daily = int(os.getenv('TUBESAKU_MCP_DAILY_LIMIT', '20000'))
    if session < 1 or daily < 1:
        raise ValueError('MCP usage limits must be positive integers')
    return {'session_calls': session, 'daily_calls': daily, 'max_results': MAX_RESULTS}


def limited_response(reason, limits, *, reset_at=None):
    messages = {
        'session': 'このMCPセッションの利用上限に達しました。このセッションではこれ以上データ取得を実行しません。',
        'daily': 'TubeSaku MCP全体の本日の利用上限に達しました。日本時間の翌日00:00以降に再度利用できます。',
        'unavailable': '利用回数を確認できないため、現在データ取得を実行していません。時間をおいて再度利用できます。',
        'session_required': '有効なMCPセッションを確認できません。MCPクライアントから接続を初期化してください。',
    }
    data = dict(status='usage_limit_reached' if reason in ('session','daily') else 'usage_temporarily_unavailable',
                limit_scope=reason, message=messages[reason], limits=limits)
    if reset_at:
        data['reset_at'] = reset_at
    url = os.getenv('TUBESAKU_MCP_LIMIT_INFO_URL', 'https://tubesaku.com/mcp-plans')
    if url:
        data['explanation_url'] = url
    return data


def consume(session_key, now=None):
    """Reserve one execution before starting any data access. Denials spend nothing.

    session_key is already hashed; neither raw IDs nor arguments enter this DB.
    Failed/invalid function executions still spend their reservation.
    """
    limits = configuration()
    if not session_key:
        return False, limited_response('session_required', limits)
    now = (now or datetime.now(JST)).astimezone(JST)
    day = now.date().isoformat()
    reset = (now.replace(hour=0, minute=0, second=0, microsecond=0)+timedelta(days=1)).isoformat()
    path = Path(os.getenv('TUBESAKU_MCP_QUOTA_DB', 'run/mcp_usage_limits.sqlite3'))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=5)) as conn:
            conn.execute('PRAGMA busy_timeout=5000')
            conn.execute('CREATE TABLE IF NOT EXISTS sessions (session_key TEXT PRIMARY KEY, calls INTEGER NOT NULL, first_used TEXT NOT NULL, last_used TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS days (day_jst TEXT PRIMARY KEY, calls INTEGER NOT NULL)')
            conn.execute('BEGIN IMMEDIATE')
            try:
                row = conn.execute('SELECT calls FROM sessions WHERE session_key=?', (session_key,)).fetchone()
                session_calls = row[0] if row else 0
                row = conn.execute('SELECT calls FROM days WHERE day_jst=?', (day,)).fetchone()
                daily_calls = row[0] if row else 0
                if session_calls >= limits['session_calls']:
                    conn.rollback()
                    return False, limited_response('session', limits)
                if daily_calls >= limits['daily_calls']:
                    conn.rollback()
                    return False, limited_response('daily', limits, reset_at=reset)
                stamp = now.isoformat()
                conn.execute('INSERT INTO sessions VALUES(?,1,?,?) ON CONFLICT(session_key) DO UPDATE SET calls=calls+1,last_used=excluded.last_used', (session_key,stamp,stamp))
                conn.execute('INSERT INTO days VALUES(?,1) ON CONFLICT(day_jst) DO UPDATE SET calls=calls+1', (day,))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return True, dict(session_used=session_calls+1, session_limit=limits['session_calls'],
            session_remaining=limits['session_calls']-session_calls-1, daily_limit=limits['daily_calls'],
            daily_remaining=limits['daily_calls']-daily_calls-1, daily_reset_at=reset, max_results=MAX_RESULTS)
    except (sqlite3.Error, OSError):
        # Fail closed without exposing filesystem paths or returning a tool error.
        return False, limited_response('unavailable', limits)


def bound_results(payload):
    """Cap primary result collections, not every list in quality/source metadata."""
    if not isinstance(payload, dict):
        return payload
    payload = dict(payload)
    for key in ('streams','creators','songs','games','results','datasets','available_markdown_files'):
        rows = payload.get(key)
        if isinstance(rows, list) and len(rows) > MAX_RESULTS:
            payload[key] = rows[:MAX_RESULTS]
            payload['truncated'] = payload['possibly_truncated'] = True
            if key in ('streams','creators','songs','games'):
                payload['count'] = MAX_RESULTS
    return payload
