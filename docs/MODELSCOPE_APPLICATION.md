# ModelScope application — copy-ready fields

Prepared from the contribution guide text supplied by the repository owner. No form has been submitted. Remote transport acceptance and live form options remain unverified.

## 1. MCP service name (English, required)

`tubesaku-creator-insights`

This is the service/plugin identifier, not a published npm or PyPI package. The guide says a package name is typical, not mandatory.

## 2. MCP service name (Chinese, optional)

TubeSaku 日本新人 VTuber 与创作者洞察

## 3. Developer (optional)

GIPU Limited (GitHub: webbigdata-jp)

## 4. MCP Server Configuration (required)

Candidate for an existing remotely hosted Streamable HTTP service. Confirm this transport and configuration schema with ModelScope; the supplied form guide only demonstrates stdio. No local command or API key is required.

```json
{
  "mcpServers": {
    "tubesaku": {
      "type": "streamable_http",
      "url": "https://tubesaku.com/mcp"
    }
  }
}
```

No SSE endpoint or npm/PyPI launcher is provided. Do not replace the remote connection with an unverified local wrapper.

## 5. Service details (English README, required)

# TubeSaku Creator Insights MCP

Read-only research into emerging Japanese VTubers and gaming creators using data collected and classified by TubeSaku.

## Connect

- Endpoint: https://tubesaku.com/mcp
- Transport: Streamable HTTP, session based; JSON responses.
- Authentication: none. No API key, login, local server or package installation is required.
- Source: https://github.com/webbigdata-jp/tubesaku-mcp-server
- Help: https://tubesaku.com/mcp-help
- Contact: https://tubesaku.com/contact

Use a compatible remote MCP client. It initializes the session, sends notifications/initialized, and includes the returned Mcp-Session-Id and negotiated MCP-Protocol-Version on subsequent requests. Accept application/json and text/event-stream. Do not configure this endpoint as legacy SSE.

## Tools

| Tool | Purpose |
| --- | --- |
| get_tubesaku_service_info | Service access conditions and current limits |
| get_tubesaku_data_catalog | Datasets, freshness and missing data |
| search_live_streams | Scheduled streams and debut streams |
| search_current_live_streams | Streams live at the latest observation |
| search_vtubers | VTuber debut and activity research |
| get_game_trends | Weekly game demand and supply observations |
| search_cover_songs | Cover-song research |
| get_tubesaku_index | Index of published trend documents |
| read_tubesaku_markdown | Read an indexed trend document |
| search_tubesaku_context | Keyword search in published documents |

Example requests: find debut streams scheduled in the next seven days; find VTubers who debuted in 2026 and play horror games; compare weekly game trends among creators with 10,000 subscribers or fewer. Dates and times default to Japan Standard Time.

## Limits and data quality

Default limits: 20 tool/resource executions per session, 20,000 per Japan calendar day across the hosted deployment, and up to 10 primary results per call; some tools allow fewer. Current service metadata takes precedence. Do not rotate sessions or repeatedly query to bypass limits or assemble a bulk export.

Results do not cover all YouTube. Live status reflects the latest observation and may have changed. Preserve observation dates, freshness, missing-data notices, truncation and returned usage_terms. Do not compile creator lists for unsolicited commercial outreach. No tool contacts creators or identifies the private person behind an avatar.

## Hosted logging and terms

Read https://tubesaku.com/terms and https://tubesaku.com/privacy before connecting. Queries and client/protocol metadata are sent to tubesaku.com. The service records bounded tool arguments, client metadata and hashed session identifiers. Raw authorization headers and raw session IDs are excluded from the described usage events. Do not send secrets or private personal information in searches. This connection does not disable hosted logging or provide a logging opt-out. Do not connect if you do not agree to these conditions. This disclosure is not a claim of server-enforced consent; clients may contact the service during tool discovery.

## License

Repository software, documentation and bundled assets are licensed under Apache-2.0. This does not license hosted API data, datasets, third-party creator/YouTube content or trademarks. Hosted service/data use is governed separately by TubeSaku Terms, Privacy Policy and returned usage_terms. See DATA_TERMS.md in the repository.

The repository also contains a portable Agent Plugins manifest and research Skill for compatible clients. ModelScope need only connect to the hosted MCP; support for loading those plugin components is not assumed. Included server source is an inspection snapshot and does not certify the deployed revision.

## 6. Service details (Chinese README, optional)

# TubeSaku 创作者洞察 MCP

面向日本新人 VTuber 和游戏创作者的只读研究服务。支持查询直播预告、首次直播、最近观测到的直播、出道与活动记录、每周游戏趋势及翻唱选曲，并可读取已发布的趋势文档。

连接地址：https://tubesaku.com/mcp 。传输方式为 Streamable HTTP，无需 API Key、登录或本地运行服务。请勿将其配置为旧版 SSE。

示例：查询未来七天的首次直播；寻找 2026 年出道且玩恐怖游戏的 VTuber；比较订阅人数一万以下创作者的每周游戏趋势。日期和时间默认使用日本标准时间。

默认每会话最多执行 20 次工具或资源调用，整个托管服务每个日本日历日最多 20,000 次，每次主要结果最多 10 条，部分工具限制更低；以服务返回的当前限制为准。数据不覆盖全部 YouTube，直播状态仅代表最近观测，可能已经变化。展示结果时请保留观测日期、缺失数据及使用条件。禁止整理用于未经请求的商业推广的创作者名单，也不提供虚拟形象背后个人的真实身份。

连接前请阅读并同意 https://tubesaku.com/terms 和 https://tubesaku.com/privacy 。查询及客户端元数据会发送至 tubesaku.com，服务会记录有限的工具参数、客户端信息和哈希化会话标识。所述使用事件不包含原始授权请求头及原始会话 ID。请勿在搜索中发送秘密或私人个人信息。本连接不能关闭托管服务日志；不同意这些条件时请勿连接。工具发现阶段也可能产生请求，不能将本说明视为服务端强制执行的同意机制。

仓库软件、文档和随附素材采用 Apache-2.0 许可；API 数据、数据集、第三方内容和商标不在该许可范围内，另受 TubeSaku 服务条款及工具返回的 usage_terms 约束。

源码：https://github.com/webbigdata-jp/tubesaku-mcp-server 。帮助：https://tubesaku.com/mcp-help 。联系：https://tubesaku.com/contact 。

## 7. GitHub URL (optional, recommended)

https://github.com/webbigdata-jp/tubesaku-mcp-server

## 8. Logo (optional)

Upload `../assets/logo.png` (repository path: `assets/logo.png`). `assets/icon.png` is also available for a smaller icon. These assets are reused from the existing OpenAI submission.

## 9. Suggested category

Choose one closest live form option for search / information retrieval. The actual category list was not supplied, so no exact category label is asserted here.

## Follow-up

Submit through https://alidocs.dingtalk.com/notable/share/form/v01Yvenvep6y6aGVloy_hERWDMS_ycNQeJ0 . The supplied guide says processing generally takes three working days. For progress questions it lists DingTalk group 44837352. Confirm the current form and transport support first. Do not upload the Hermes archive as though it were an npm/PyPI server package.
