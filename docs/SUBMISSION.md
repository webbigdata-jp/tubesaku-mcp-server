# Submission preparation

## Hermes

Source: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission

1. Commit this package in the public repository and choose its full 40-character SHA.
2. Verify a released Hermes version supporting portable Streamable HTTP. Run `hermes plugins validate /path/to/checkout --install-deps`, then install, enable, discover all ten tools and exercise the skill with consent accepted and declined. The official v0.23.0 validate_plugin_dir entry point passed locally: portable manifest, manifest fields, config schema and security scan (safe), no warnings. Portable packages declare no local dependencies. Discovery of ten hosted tools and get_tubesaku_service_info passed through curl using protocol 2025-03-26. A full interactive Hermes chat and the CI command remain pending.
3. Add `plugin-catalog/tubesaku-creator-insights.yaml` to NousResearch/hermes-agent through an owner-submitted PR. Use the catalog template beside this document, replacing SHA and minimum-version placeholders. Do not submit placeholders.
4. Disclose HTTPS calls, hosted argument/client logging, independent hosted-service changes, quotas and consent limitations in the PR. Rule 13 requires telemetry/usage reporting to be opt-in. README acceptance alone is not demonstrated compliance. Ask reviewers whether required operational/quota logs are exempt; if analytics are included, obtain acceptance of the consent approach or implement a real optional logging path before claiming compliance. No backend behavior was changed here.
5. Remote MCP tool names are discovered dynamically, not Python register_tool declarations. Confirm capabilities against Hermes validation output; do not guess the catalog registry names.

## ModelScope MCP plaza

The operator supplied the text of https://www.modelscope.cn/headlines/article/1189 . It describes manual form submission, normally processed within three working days (guidance, not a guaranteed SLA). Follow up in DingTalk group 44837352 if needed. The current live form has not been verified.

Form: https://alidocs.dingtalk.com/notable/share/form/v01Yvenvep6y6aGVloy_hERWDMS_ycNQeJ0

Copy-ready field values and README text: [MODELSCOPE_APPLICATION.md](MODELSCOPE_APPLICATION.md).

Use the existing externally hosted service at https://tubesaku.com/mcp, with no authentication. Do not deploy the reference Python snapshot. The supplied guide demonstrates stdio (`command`/`args`), but does not establish which remote configuration fields this form accepts. The official cookbook uses `streamable_http`: https://github.com/modelscope/ms-cookbook/blob/main/content/chapters/chapter-30.md . The separate modelscope-mcp.json follows that spelling; confirm remote Streamable HTTP acceptance with the platform before submitting. Do not substitute `streamable-http` without checking the receiving schema, claim SSE support, or invent an npm/PyPI package.

plugin.json and the bundled Skill are for compatible Agent Plugins clients. They are not required form fields, and ModelScope is not assumed to load them or enforce the skill's consent step. Before enabling a connection, users must see the hosted logging disclosure. Verify tool discovery and a permitted read-only query from ModelScope before claiming compatibility.
