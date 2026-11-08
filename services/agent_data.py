from datetime import timedelta, timezone
# Extracted from upstream production sources.
JST = timezone(timedelta(hours=9))


BASE_URL = 'https://tubesaku.com'


RETIRED_MARKDOWN = 'youtube-live-stream_stats.md'


TREND_FILES = {
    'google_trends': 'google_trends.md',
    'youtube_keywords': 'youtube-keywords_trends.md',
}


FREE_LIMITS = {'live_streams': 10, 'live_date_span_days': 7, 'cover_songs': 5,
               'game_weeks': 4, 'games': 10, 'current_live_streams': 10, 'vtubers': 10}


def positive_integer(value, name, maximum):
    from services.agent_validation import integer
    return integer(value, name, maximum=maximum)
