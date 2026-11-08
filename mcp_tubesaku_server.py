import contextlib
from services.agent_access import public_service_info, data_service_info, track_usage, AgentHTTPMiddleware, configure_mcp_context
from services.agent_markdown import safe_md_path as _safe_md_path, listed_md_paths
from services.agent_preview_client import PreviewClient
from urllib.parse import urljoin

from dotenv import load_dotenv
import httpx
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from services.agent_quota import configuration

load_dotenv()

BASE_URL = "https://tubesaku.com/"
LLMS_URL = urljoin(BASE_URL, "llms.txt")
MAX_TEXT_BYTES = 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MCP_USAGE_LIMITS = configuration()
MAX_MARKDOWN_FILES = 20  # Internal fetch allowlist; public result collections are capped at 10.

mcp = FastMCP(
    "TubeSaku Creator Insights",
    json_response=True,
    max_request_body_size=64 * 1024,
    max_sessions=128,
    session_idle_timeout=900,
    instructions=f"日本の新人VTuber・ゲーム実況者や配信計画を調べるための、TubeSakuが収集・分類・集計した公開データの読み取りサービス。1回の結果は最大10件、MCPセッションあたりツール・リソース取得合計{MCP_USAGE_LIMITS['session_calls']}回、全体の日次上限は{MCP_USAGE_LIMITS['daily_calls']:,}回（日本時間）。上限時は取得を実行せず、事実と説明ページURLを通常応答で返す。配信予告、最終観測時点の配信中ライブ、VTuberデビュー・活動記録、ゲーム需要と供給、歌ってみた候補、公開トレンド資料を提供。YouTube全件の網羅や検索瞬間の配信状態は保証しない。各応答に観測期間・欠損・取得上限を付記。アカウント更新・予約・決済は扱わない。",
)

configure_mcp_context(mcp.get_context)

async def _bounded_response(url: str, *, maximum: int, timeout: float, params=None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream('GET', url, params=params,
                                 headers={'Accept-Encoding': 'identity'}) as response:
            if response.status_code != 400:
                response.raise_for_status()
            # HTTPX decompresses a whole raw chunk before yielding decoded bytes.
            # Require identity so a compressed expansion cannot bypass our memory cap.
            if response.headers.get('content-encoding', 'identity').strip().lower() not in {'', 'identity'}:
                raise ValueError('Compressed upstream responses are not supported')
            content = bytearray()
            # Bound accumulation even when Content-Length is absent or incorrect.
            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                if len(content) + len(chunk) > maximum:
                    raise ValueError('Upstream response exceeds the public data size limit')
                content.extend(chunk)
            # Preserve httpx text charset/JSON behavior without retaining streaming state.
            headers = {'content-type': response.headers.get('content-type', '')}
            return httpx.Response(response.status_code, content=bytes(content),
                                  headers=headers, request=response.request)


async def fetch_text(url: str) -> str:
    response = await _bounded_response(url, maximum=MAX_TEXT_BYTES, timeout=15.0)
    response.raise_for_status()
    return response.text


async def get_allowed_md_paths() -> list[str]:
    llms = await fetch_text(LLMS_URL)
    paths = listed_md_paths(llms)
    if len(paths) > MAX_MARKDOWN_FILES:
        raise ValueError('Published Markdown index exceeds the document limit')
    return paths


@mcp.tool(title="TubeSakuの提供範囲・利用条件", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("get_tubesaku_service_info")
async def get_tubesaku_service_info() -> dict:
    """MCPの利用条件・取得上限・提供状況を返す。"""
    return public_service_info()


@mcp.tool(title="公開トレンド資料の一覧", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("get_tubesaku_index")
async def get_tubesaku_index() -> dict:
    """
    TubeSakuのllms.txtを読み、利用可能な公開Markdown一覧を最大10件返す。
    """
    paths = await get_allowed_md_paths()
    return {
        "source": LLMS_URL,
        "available_markdown_files": paths,
        "service": data_service_info(),
        "catalog_url": urljoin(BASE_URL, "ai/catalog.json"),
    }


@mcp.tool(title="公開トレンド資料の読出し", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("read_tubesaku_markdown")
async def read_tubesaku_markdown(path: str) -> dict:
    """
    llms.txtで公開されているTubeSakuのMarkdownファイルを読む。
    path例: /llms/google_trends.md
    """
    safe_path = _safe_md_path(path)
    allowed = await get_allowed_md_paths()

    if safe_path not in allowed:
        raise ValueError(f"Not listed in llms.txt: {safe_path}")

    url = urljoin(BASE_URL, safe_path.lstrip("/"))
    text = await fetch_text(url)

    return {
        "source": url,
        "path": safe_path,
        "content": text[:50000],
        "truncated": len(text) > 50000,
        "service": data_service_info(),
    }


@mcp.tool(title="公開トレンド資料のキーワード検索", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("search_tubesaku_context")
async def search_tubesaku_context(query: str) -> dict:
    """
    TubeSakuの公開Markdownを横断的に読み、queryに関係しそうな本文を返す。
    空白区切りの単純検索。queryは1〜500文字・1〜20語、同じ語の重複は除く。
    """
    if len(query) > 500:
        raise ValueError('query must be at most 500 characters')
    terms = query.split()
    if not 1 <= len(terms) <= 20:
        raise ValueError('query must contain 1-20 whitespace-separated terms')
    query_terms = list(dict.fromkeys(term.lower() for term in terms))
    paths = await get_allowed_md_paths()

    results = []

    for path in paths:
        url = urljoin(BASE_URL, path.lstrip("/"))
        text = await fetch_text(url)
        lower = text.lower()

        score = sum(lower.count(term) for term in query_terms)

        if score > 0:
            results.append({
                "path": path,
                "source": url,
                "score": score,
                "excerpt": text[:8000],
            })

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "query": query,
        "results": results[:3],
        "total_matching_count": len(results),
        "possibly_truncated": len(results) > 3,
        "service": data_service_info(),
    }


async def fetch_json(path: str, params: dict | None = None) -> dict:
    response = await _bounded_response(urljoin(BASE_URL, path.lstrip('/')),
                                       maximum=MAX_JSON_BYTES, timeout=20.0, params=params)
    if response.status_code == 400:
        raise ValueError(response.json().get('message', 'Invalid request'))
    return response.json()


_preview_client = PreviewClient(fetch_json)


@mcp.tool(title="データカタログと鮮度・欠損", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("get_tubesaku_data_catalog")
async def get_tubesaku_data_catalog() -> dict:
    """公開データの一覧、更新日時、観測範囲、欠損・古さ・利用条件を確認する。観測日時と欠損情報を含む。"""
    return await _preview_client.catalog()


@mcp.tool(title="配信予告の条件検索", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("search_live_streams")
async def search_live_streams(date_from: str = '', date_to: str = '',
                              start_time: str = '', end_time: str = '',
                              keyword: str = '', debut_only: bool = False,
                              category: str = '', limit: int = 5) -> dict:
    """配信予定をJSTの日付・時間帯・初配信候補・ジャンルで検索。公開アクセスでは最大7日間・10件。通常・デビューとも現行予告のみ。開始予定時刻を過ぎた予告は猶予期間後に対象外。過去のデビュー予告・終了済み配信の履歴は取得不可。総一致件数も返す。"""
    return await _preview_client.live_streams(date_from=date_from, date_to=date_to,
        start_time=start_time, end_time=end_time, keyword=keyword,
        debut_only=debut_only, category=category, limit=limit)


@mcp.tool(title="最終確認時点で配信中のライブ検索", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("search_current_live_streams")
async def search_current_live_streams(keyword: str = '', category: str = '', limit: int = 5) -> dict:
    """最終確認時点で配信中のライブを検索。keywordはタイトル・チャンネル名・説明の部分一致（最大200文字）。categoryはYouTubeカテゴリID（例20=ゲーム）。limitは1〜10、既定5。2時間以内の観測のみ。検索直前の終了は未確認。"""
    return await _preview_client.current_live(keyword=keyword, category=category, limit=limit)


@mcp.tool(title="VTuberのデビュー・活動条件検索", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("search_vtubers")
async def search_vtubers(debut_year: str = '', date_from: str = '', date_to: str = '',
                         game: str = '', keyword: str = '', limit: int = 5) -> dict:
    """収録VTuberをデビュー年・日付範囲(YYYY-MM-DD、両端含む)・活動ゲーム・名前/紹介文等でAND検索。debut_yearは2000〜2100の年。gameはゲームID・日本語名・英語名のあいまい部分一致（大文字小文字・全半角・空白・記号・かな表記を正規化。英字名は4文字以上の語の1文字の追加・削除・置換にも対応）、keywordは名前・紹介文等の部分一致（各200文字まで）。limitは1〜10。紹介文のない人物もあり、ゲーム未収録は未プレイを意味しない。"""
    return await _preview_client.vtubers(debut_year=debut_year, date_from=date_from,
        date_to=date_to, game=game, keyword=keyword, limit=limit)


@mcp.tool(title="ゲーム需要・供給の週次比較", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("get_game_trends")
async def get_game_trends(game: str = '', segment: str = 'u10k', weeks: int = 4,
                           limit: int = 5) -> dict:
    """ゲーム別の需要順位・供給順位の週次比較。最大4週までさかのぼり、トップ10ランキングを取得。返却は最新週優先で最大10行。gameは日本語名・英語名のあいまい部分一致（大文字小文字・全半角・空白・記号・かな表記を正規化。英字名は4文字以上の語の1文字の追加・削除・置換にも対応）。既定は登録者1万人以下。集計値は取得できる数値のみ返し、欠損は省略。指標や順位の欠損理由はquality.missing_fieldsに集約し、series_indexesで対象行を示す。latest_available_periodが保存済み最新週、is_latest_periodで各行を識別。period_label_onlyは正確な観測日時不明。Steam人数とYouTube再生数は別指標。"""
    return await _preview_client.games(game=game, segment=segment, weeks=weeks, limit=limit)


@mcp.tool(title="歌ってみた候補の検索", annotations=ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
@track_usage("search_cover_songs")
async def search_cover_songs(keyword: str = '', scope: str = 'low_supply',
                              require_playlist_video: bool = False, limit: int = 3) -> dict:
    """歌ってみた候補を原曲人気・最近の競合数・公開後6時間相当の反応で探す。最大5曲。scope: all,low_supply,no_recent_covers,shorts_growth,popular_covers。楽曲の利用許諾は別途確認。"""
    return await _preview_client.covers(keyword=keyword, scope=scope,
        require_playlist_video=require_playlist_video, limit=limit)


@mcp.resource("tubesaku://llms")
@track_usage("tubesaku_llms_txt")
async def tubesaku_llms_txt() -> str:
    """
    TubeSakuのllms.txt本文。
    """
    return await fetch_text(LLMS_URL)


@mcp.resource("tubesaku://markdown/{path}")
@track_usage("tubesaku_markdown_resource")
async def tubesaku_markdown_resource(path: str) -> str:
    """
    TubeSakuの公開Markdown本文。
    例: tubesaku://markdown/google_trends.md
    """
    safe_path = _safe_md_path(path)
    allowed = await get_allowed_md_paths()

    if safe_path not in allowed:
        raise ValueError(f"Not listed in llms.txt: {safe_path}")

    return await fetch_text(urljoin(BASE_URL, safe_path.lstrip("/")))


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


app = AgentHTTPMiddleware(app)
