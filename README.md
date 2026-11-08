# TubeSaku Creator Insights

A portable Agent Plugins v1 package connecting Hermes and compatible clients to TubeSaku's hosted, read-only Japanese YouTube research MCP. Discover emerging VTubers, debut and scheduled streams, observed live streams, weekly game trends and cover-song ideas.

## Install in Hermes

Before enabling, read [Data terms and logging disclosure](DATA_TERMS.md), [Terms](https://tubesaku.com/terms) and [Privacy](https://tubesaku.com/privacy). Enabling may contact the remote endpoint for tool discovery. Do not enable if you do not agree to sending requests to the logged hosted service.

```bash
hermes plugins install https://github.com/webbigdata-jp/tubesaku-mcp-server --no-enable
hermes plugins enable tubesaku-creator-insights
hermes plugins list
```

Restart Hermes. The bundled skill is `tubesaku-creator-insights:tubesaku-creator-research`. Ask: “Using TubeSaku, find debut streams scheduled over the next seven days.” The skill asks for explicit agreement to hosted logging before its first tool call. This is an instruction-level safeguard, not a server-enforced opt-in.

After catalog acceptance, installation by name will be available. Until then use the Git URL or a local checkout. No Python, Node, API key, login or local MCP process is required by this package. Requires Hermes >=0.23.0. The package was validated using the official v0.23.0 validator (portable manifest passes; security scan safe; no warnings). Remote MCP initialization, discovery of ten tools and get_tubesaku_service_info were checked with curl; a full interactive Hermes chat remains untested.

## Package

- `plugin.json`: portable manifest, identity/presentation/assets adapted from the pending OpenAI submission; package version 1.0.2.
- `mcp.json`: Streamable HTTP connection to `https://tubesaku.com/mcp`, server name `tubesaku`; no credentials or custom headers.
- `skills/tubesaku-creator-research/SKILL.md`: research workflow, consent disclosure and result handling.
- `server.json`: separate MCP directory metadata; its 0.2.0 version describes that server metadata, not this plugin release.
- [SOURCE_SNAPSHOT.md](SOURCE_SNAPSHOT.md): tool inventory and reference server source instructions. Included Python files are an inspection snapshot, never launched by the plugin and not guaranteed to match production.
- [docs/SUBMISSION.md](docs/SUBMISSION.md): Hermes and ModelScope submission checklist.

## Limits and disclosure

Queries and protocol metadata go over HTTPS to tubesaku.com. The hosted service records usage as described in [DATA_TERMS.md](DATA_TERMS.md). This package has no local telemetry, shell commands, local file reads, background processes, stored credentials or self-updater. Hosted logging is not disabled by installing this package. The remote service can change independently of the pinned plugin commit.

Default limits are 20 executions per session, 20,000 per Japan calendar day across the hosted deployment, and up to 10 primary results (some tools use lower limits). Check service metadata for current limits. Observed data is incomplete and may be stale. Preserve observation dates, missing-data notices and returned usage_terms. Do not assemble lists for unsolicited commercial outreach.

## License and data

Software, documentation and bundled assets: [Apache License 2.0](LICENSE). Hosted API data and third-party content are covered separately by [DATA_TERMS.md](DATA_TERMS.md); Apache-2.0 grants no rights to them or to trademarks.

[Help](https://tubesaku.com/mcp-help) · [Contact](https://tubesaku.com/contact)
