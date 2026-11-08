"""Remote preview operations, kept separate from MCP transport registration."""
from datetime import datetime, timedelta
from services.agent_data import FREE_LIMITS, JST, positive_integer
from services.agent_access import data_service_info
from services.agent_validation import (SearchValidationError, integer, search_text,
    date_range, debut_year as validate_year, current_category, search_time)


class PreviewClient:
    def __init__(self, fetch_json):
        self.fetch_json = fetch_json

    async def catalog(self):
        result = await self.fetch_json('/ai/catalog.json')
        result['service'] = data_service_info()
        return result

    async def live_streams(self, *, date_from='', date_to='', start_time='', end_time='',
                           keyword='', debut_only=False, category='', limit=5):
        limit = positive_integer(limit, 'limit', FREE_LIMITS['live_streams'])
        today = datetime.now(JST).date()
        start, end = date_range(date_from, date_to)
        start = start or today
        end = end or start + timedelta(days=6)
        keyword = search_text(keyword, 'keyword')
        category = search_text(category, 'category', 50)
        start_clock = search_time(start_time, 'start_time')
        end_clock = search_time(end_time, 'end_time')
        if start_clock is not None and end_clock is not None and end_clock < start_clock:
            raise SearchValidationError('end_time must be on or after start_time within one JST day')
        if not 1 <= (end - start).days + 1 <= FREE_LIMITS['live_date_span_days']:
            raise ValueError('Public access date range must be 1-7 days in JST')
        params = {'date_from': start.isoformat(), 'date_to': end.isoformat(),
                  'start_time': start_time, 'end_time': end_time, 'keyword': keyword,
                  'debut_only': str(debut_only).lower(), 'category': category, 'limit': limit + 1}
        result = await self.fetch_json('/api/stream-schedule/search', params)
        return self._bounded(result, 'streams', limit)

    async def current_live(self, *, keyword='', category='', limit=5):
        limit = integer(limit, 'limit')
        keyword, category = search_text(keyword, 'keyword'), current_category(category)
        result = await self.fetch_json('/api/live-now/search', {'keyword': keyword, 'category': category, 'limit': limit})
        result['service'] = data_service_info()
        return result

    async def vtubers(self, *, debut_year='', date_from='', date_to='', game='', keyword='', limit=5):
        limit = integer(limit, 'limit')
        validate_year(debut_year)
        date_range(date_from, date_to)
        game, keyword = search_text(game, 'game'), search_text(keyword, 'keyword')
        result = await self.fetch_json('/api/vtubers/search', dict(debut_year=debut_year,
            date_from=date_from, date_to=date_to, game=game, keyword=keyword, limit=limit))
        result['service'] = data_service_info()
        return result

    async def games(self, *, game='', segment='u10k', weeks=4, limit=5):
        weeks = positive_integer(weeks, 'weeks', FREE_LIMITS['game_weeks'])
        game = search_text(game, 'game')
        if segment not in {'all', 'u100k', 'u10k'}:
            raise SearchValidationError('segment must be all, u100k, or u10k')
        limit = positive_integer(limit, 'limit', FREE_LIMITS['games'])
        result = await self.fetch_json('/ai/games-preview.json', {
            'game': game, 'segment': segment, 'weeks': weeks, 'limit': limit})
        result['service'] = data_service_info()
        return result

    async def covers(self, *, keyword='', scope='low_supply', require_playlist_video=False, limit=3):
        limit = positive_integer(limit, 'limit', FREE_LIMITS['cover_songs'])
        keyword = search_text(keyword, 'keyword')
        if scope not in {'all', 'low_supply', 'no_recent_covers', 'shorts_growth', 'popular_covers'}:
            raise SearchValidationError('scope must be all, low_supply, no_recent_covers, shorts_growth, or popular_covers')
        result = await self.fetch_json('/api/utattemita-ranking/search', {
            'keyword': keyword, 'scope': scope,
            'require_playlist_video': str(require_playlist_video).lower(), 'limit': limit + 1})
        return self._bounded(result, 'songs', limit)

    @staticmethod
    def _bounded(result, field, limit):
        rows = result.get(field) or []
        total = result.get('total_matching_count')
        has_more = (total > limit if isinstance(total, int) else len(rows) > limit) or bool(result.get('possibly_truncated'))
        result.update({field: rows[:limit], 'count': len(rows[:limit]),
                       'truncated': has_more,
                       'possibly_truncated': has_more,
                       'tier': 'public', 'limits': FREE_LIMITS, 'service': data_service_info()})
        result.setdefault('query', {})['limit'] = limit
        return result
