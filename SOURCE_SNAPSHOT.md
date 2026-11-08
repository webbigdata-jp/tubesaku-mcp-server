# TubeSaku Creator Insights MCP

Public source snapshot for MCP directory reviewers and developers inspecting [TubeSaku](https://tubesaku.com/ai-data), a Japanese YouTube and creator research service.

**Hosted endpoint:** `https://tubesaku.com/mcp`

**Transport:** Streamable HTTP, JSON responses, session based

**Authentication:** No API key or user login required

This repository exposes the MCP interface and public HTTP data access. Production development and deployment remain in the upstream application. This snapshot does not certify which revision is currently deployed. Collectors, databases, website implementation, credentials and production data are excluded.

## Request flow

```text
MCP client
  → MCP tool/resource definition
  → input validation and session quota
  → TubeSaku public JSON APIs / published Markdown over HTTPS
  → bounded results with observation dates, quality and usage terms
```

The server reads collected and processed data through TubeSaku's public endpoints. It does not search all of YouTube or contact creators when a tool is called. Database queries and collection run on the data provider side.

## Tools

| Tool | Purpose | Upstream |
| --- | --- | --- |
| `get_tubesaku_service_info` | Public access conditions and limits | Local metadata |
| `get_tubesaku_index` | Published trend document index | `/llms.txt` |
| `read_tubesaku_markdown` | Read an indexed document | Indexed Markdown URL |
| `search_tubesaku_context` | Keyword search in published documents | Index and Markdown |
| `get_tubesaku_data_catalog` | Datasets, freshness and missing data | `/ai/catalog.json` |
| `search_live_streams` | Scheduled broadcasts | `/api/stream-schedule/search` |
| `search_current_live_streams` | Live at the last observation | `/api/live-now/search` |
| `search_vtubers` | VTuber debut/activity search | `/api/vtubers/search` |
| `get_game_trends` | Weekly game demand/supply observations | `/ai/games-preview.json` |
| `search_cover_songs` | Cover song research | `/api/utattemita-ranking/search` |

Resources: `tubesaku://llms` and `tubesaku://markdown/{path}`. Tools are read only. Argument definitions and annotations are in [mcp_tubesaku_server.py](mcp_tubesaku_server.py).

## Connect or run locally

Add `https://tubesaku.com/mcp` in a client's remote Streamable HTTP connector settings. A local checkout is not required to use the hosted service.

Protocol clients initialize, send `notifications/initialized`, then send the returned `Mcp-Session-Id` and negotiated `MCP-Protocol-Version` with subsequent requests. Use `Content-Type: application/json` and `Accept: application/json, text/event-stream`.

For local inspection, Python 3.10+:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m uvicorn mcp_tubesaku_server:app --host 127.0.0.1 --port 7010
```

Local endpoint: `http://127.0.0.1:7010/mcp`. Tool calls still read TubeSaku's public service. Tests use local ASGI and mocked upstream responses.

## Limits and data use

Snapshot defaults: 20 tool/resource executions per session, 20,000 executions per Japan calendar day across the deployment, and at most 10 primary results (some tools use lower limits). Check current hosted metadata for effective limits. Local runs have their own counters and do not reproduce the hosted deployment's global quota.

Results reflect observations of collected data, not exhaustive coverage or guaranteed real time status. Check observation periods, freshness, missing data and truncation. Creator responses preserve the prohibition on compiling lists for unsolicited commercial outreach.

Usage events contain bounded client metadata, declared tool arguments and hashed session identifiers. Raw authorization headers and raw session IDs are excluded from these events. Optional IP hashing uses a private deployment key. Runtime quota SQLite files and logs are created locally and excluded from Git.

[Terms](https://tubesaku.com/terms) · [Privacy](https://tubesaku.com/privacy) · [Help](https://tubesaku.com/mcp-help) · [Contact](https://tubesaku.com/contact)

## Code and maintenance

- `mcp_tubesaku_server.py`: tools, resources and bounded HTTP fetching.
- `services/agent_preview_client.py`: public API requests and result bounds.
- `services/agent_access.py`: MCP middleware, logging and metadata; website routes are omitted.
- `services/agent_data.py`: only constants and the validation adapter required by the client.
- `services/agent_quota.py`: persistent execution counters.
- `services/agent_usage_report.py`: usage event aggregation, exercised by session tests.
- `tests/`: offline protocol, input bounds and creator usage condition checks.
- `server.json`: hosted service directory metadata.
- `SOURCE_MANIFEST.json`: SHA-256 hashes of exported files.

The upstream application's `scripts/export_public_mcp.py` refreshes this snapshot from an explicit allowlist. Changes to this repository are not automatically deployed. Software is licensed under Apache-2.0; hosted data is governed separately by DATA_TERMS.md.

## 日本語

MCP登録先や外部の方に、実際のツール定義とデータ取得の流れを示す公開用スナップショットです。開発・本番配備の管理場所は移しません。Webと共有するコードは公開出力側だけで必要部分を抽出し、収集処理・DB・内部運用設定・秘密情報は含めません。
