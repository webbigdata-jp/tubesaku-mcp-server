# Data and hosted service terms

The Apache-2.0 license in LICENSE covers the software, documentation and bundled assets in this repository. It does not license API responses, TubeSaku datasets, creator content, YouTube content, names, trademarks or linked media. Rights in third-party content remain with their owners.

Use of the hosted endpoint and returned data is subject to [TubeSaku Terms](https://tubesaku.com/terms) and [Privacy Policy](https://tubesaku.com/privacy), and the usage_terms returned by tools. Preserve those notices when presenting results. Do not compile lists for unsolicited commercial outreach. Public access is not a grant of bulk redistribution rights or a guarantee of continued availability.

The hosted service records bounded client metadata, declared tool arguments and hashed session identifiers. Raw authorization headers and raw session IDs are excluded from the described usage events; optional IP hashing uses a private deployment key. Do not send secrets or private personal information in searches. No retention period or opt-out mechanism is promised by this package; consult the service policies and contact the operator for details.

This package adds no local telemetry. Hosting-side logging remains active; declining consent means the bundled skill must not contact TubeSaku. This instruction is not a transport-level consent gate: a client may discover tools when the plugin is enabled, and direct tool calls bypass skill instructions. Read this disclosure before enabling the plugin. The package cannot disable or delete hosted logs.
