# Agent 可觀測性：OpenTelemetry GenAI 慣例與自架工具

本篇整理 OpenTelemetry GenAI semantic conventions（span、content 擷取、metrics、MCP）、可自架的 Langfuse 與 Phoenix 如何接 OTel，以及 Claude Code 自身的 OTel 遙測；資料取得日期 2026-10-14，內文的 `[簡稱]` 對應文末來源表。

## 為什麼用標準慣例，以及目前穩定度

- 用 OTel 標準屬性名稱打點，換後端時不用改 instrumentation：Langfuse 與 Phoenix 都能收 OTel trace，Phoenix 的 README 明說同一套 OpenTelemetry/OpenInference instrumentation 也能送到 Arize AX。[Langfuse-OTel] [Phoenix]
- GenAI semantic conventions 已搬到獨立 repo `open-telemetry/semantic-conventions-genai`（本篇 OTel 快取網址皆在此 repo 的 `docs/gen-ai/`）；文件內仍引用 `open-telemetry/semantic-conventions` 的通用慣例（如 `error.type`、`server.address`）。[OTel-GenAI] [OTel-Spans]
- 穩定度：總覽、client inference、spans、agent spans、events、metrics、token metrics、MCP 共八份文件的 Status 都是 Development；屬性多數標 Development，只有借自通用慣例的 `error.type`、`server.*`、`network.*` 標 Stable（表格中所見）。[OTel-GenAI] [OTel-Inference] [OTel-Spans] [OTel-Agent] [OTel-Events] [OTel-Metrics] [OTel-TokenMetrics] [OTel-MCP]
- 因為還在演進，後端會自行做屬性對照：Langfuse 說 GenAI 屬性仍在演進，所以把收到的 OTel trace 對應到自己的資料模型，並額外支援 OTel GenAI 生態常見的屬性。[Langfuse-OTel]

## Span 結構

- GenAI span 代表呼叫端觀察到的邏輯操作，涵蓋從發起到收到完整回應（或錯誤、取消）；自動重試要算在同一個 span 內。[OTel-Spans]
- 操作類型由 `gen_ai.operation.name` 決定，已定義值包括 `chat`、`generate_content`、`text_completion`、`embeddings`、`retrieval`、`execute_tool`、`create_agent`、`invoke_agent`、`invoke_workflow`、`plan`，以及一組 memory 相關操作（`create_memory`、`search_memory` 等）。[OTel-Spans]
- Inference span（`gen_ai.client.inference`，Status Development）代表對模型或服務的一次呼叫，產生回應或要求 tool call。Span name 為 `{gen_ai.operation.name} {gen_ai.request.model}`，kind 為 `CLIENT`；呼叫同進程內的模型時可用 `INTERNAL`。必填屬性是 `gen_ai.operation.name`（如 `chat`）與 `gen_ai.provider.name`；`gen_ai.request.model`、`gen_ai.conversation.id`、`gen_ai.output.type`、`gen_ai.request.stream` 等為條件必填；建議屬性包括 `gen_ai.request.{max_tokens,temperature,top_p}`、`gen_ai.response.{id,model,finish_reasons}`、`gen_ai.usage.{input_tokens,output_tokens}`（另有 cache_read、cache_write、reasoning 與各 modality 的細分）。`gen_ai.input.messages`、`gen_ai.output.messages`、`gen_ai.system_instructions`、`gen_ai.tool.definitions` 為 Opt-In。[OTel-Inference]
- 命名與 kind 規則：

| Span | operation.name | Span name | Span kind |
| --- | --- | --- | --- |
| Inference | `chat`、`generate_content`、`text_completion` 等 | `{gen_ai.operation.name} {gen_ai.request.model}` | `CLIENT`（同進程可 `INTERNAL`） |
| Embeddings | `embeddings` | `{gen_ai.operation.name} {gen_ai.request.model}` | `CLIENT` |
| Create agent | `create_agent` | `create_agent {gen_ai.agent.name}` | `CLIENT` |
| Invoke agent（遠端服務，如 OpenAI Assistants、Bedrock Agents） | `invoke_agent` | `invoke_agent {gen_ai.agent.name}`，無名稱時 `invoke_agent` | `CLIENT` |
| Invoke agent（同進程，如 LangChain、CrewAI） | `invoke_agent` | 同上 | `INTERNAL` |
| Invoke workflow | `invoke_workflow` | `invoke_workflow {gen_ai.workflow.name}` | `INTERNAL` |
| Plan | `plan` | `plan {gen_ai.agent.name}`，無名稱時 `plan` | `INTERNAL` |
| Execute tool | `execute_tool` | `execute_tool {gen_ai.tool.name}` | `INTERNAL` |

  [OTel-Inference] [OTel-Spans] [OTel-Agent]
- 最常用屬性：`gen_ai.operation.name` 與 `gen_ai.provider.name` 為 Required；`gen_ai.request.model`、`gen_ai.agent.name` / `gen_ai.agent.id` / `gen_ai.agent.version`、`gen_ai.conversation.id`、`gen_ai.tool.name`（execute_tool 為 Required）、`gen_ai.tool.call.id`、`gen_ai.tool.type`、`gen_ai.usage.input_tokens`、`error.type`（出錯時必填）。[OTel-Spans] [OTel-Agent]
- `gen_ai.provider.name` 是 discriminator：用來標示該 span 採用哪家的 GenAI telemetry 格式（例如 `aws.bedrock` 就搭配 `aws.bedrock.*` 屬性、不該有 `openai.*`），值依 instrumentation 所知設定，可能與實際上游不同（例如經過 proxy）。[OTel-Spans]
- `gen_ai.usage.input_tokens` 要包含 cached tokens；細分屬性（如 `gen_ai.usage.cache_read.input_tokens`）是總數的子集。[OTel-Spans]
- `gen_ai.conversation.id` 只在有現成識別碼時填；沒有就不要填，也不要用新 UUID、trace id 或內容 hash 充數。[OTel-Spans]
- 取樣會用到的屬性（operation.name、provider.name、request.model、tool.name 等）應在 span 建立時就給，不要事後補。[OTel-Spans]
- execute_tool：instrumentation 能追蹤工具執行就該追蹤；應用程式自己的工具鼓勵照此慣例手動打點；Agent Skills 等特化工具要用 refinement（如 `execute_tool {gen_ai.tool.name} {gen_ai.skill.name}`），一次呼叫不要記兩個 span。[OTel-Spans] [OTel-Agent]

## 內容擷取與隱私

- 系統指示、使用者訊息、模型輸出被視為敏感且體積大；instrumentation 預設不應擷取，但應提供 opt-in。[OTel-Spans]
- 三種用法：(1) 預設不記錄；(2) 記在 span 屬性 `gen_ai.system_instructions`、`gen_ai.input.messages`、`gen_ai.output.messages`，適合量小且無隱私法規或儲存合規的情境（如 pre-production）；(3) 內容存外部儲存、span 只放參照，建議用於 production，可另設存取控制。[OTel-Spans]
- 結構化內容在 events（logs）支援較好，span 上若不支援就序列化成 JSON 字串；可提供截斷選項（保留 JSON 結構）。[OTel-Spans]
- 外部儲存透過 in-process hook：hook 獨立於 opt-in 旗標，不論取樣結果都應被呼叫，可修改內容再讓屬性記錄；「如何在 span 上記錄外部內容的參照」原文仍是 TODO，streaming chunks 一節也是 TODO。[OTel-Spans]
- `gen_ai.tool.call.arguments`、`gen_ai.tool.call.result` 為 Opt-In，`gen_ai.tool.description` 也標註可能含敏感資訊。[OTel-Spans]
- Memory 的 `gen_ai.memory.query.text`、`gen_ai.memory.records` 同樣預設不擷取，要由明確 opt-in 控制（原文舉例 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`），並警告可能含 PII。[OTel-Spans]

## Metrics 與 events

- `gen_ai.client.operation.duration`（Histogram，單位 `s`）記錄 GenAI 操作耗時；但不該用於 inference 操作，改用 `gen_ai.client.inference.duration`（Histogram，`s`，Development），另有 `gen_ai.client.inference.time_to_first_chunk` 與 `time_per_output_chunk`。[OTel-Metrics] [OTel-Inference]
- Token 用量分兩族（Status Development）：`gen_ai.client.inference.usage.{input_tokens,output_tokens,cache_read.input_tokens,cache_write.input_tokens,reasoning.output_tokens}` 是 Counter、單位 `{token}`，用於總量與成本估算；`cache_read`、`cache_write`、`reasoning` 是 input / output 的子集。主要屬性：`gen_ai.operation.name`、`gen_ai.provider.name`、`gen_ai.token.modality`（text / image / audio）為 Required，`gen_ai.request.model` 為條件必填。[OTel-TokenMetrics]
- 每次操作的分布用 `gen_ai.client.inference.operation.input_tokens` / `output_tokens`（Histogram，`{token}`）：只拿來看 p95 / p99 與離群值，不可用來算總量或成本；刻意不按 modality 拆分，因為跨 modality 的百分位數不能相加。[OTel-TokenMetrics]
- Agent 層 metrics：`gen_ai.invoke_agent.duration`、`gen_ai.invoke_agent.inference_calls`、`gen_ai.invoke_agent.tool_calls`（後兩者為 Histogram，建議 bucket `[1, 2, 4, 8, 16, 32, 64, 128]`，只計該 agent 自己發出的呼叫，sub-agent 的算在其自己的 invocation），以及 `gen_ai.execute_tool.duration`、`gen_ai.invoke_workflow.duration`。[OTel-Metrics]
- 模型服務端 metrics：`gen_ai.server.request.duration`、`gen_ai.server.time_per_output_token`、`gen_ai.server.time_to_first_token`。[OTel-Metrics]
- Events：events 文件定義 `gen_ai.evaluation.result`（Development），記錄對 GenAI 輸出的評估結果，屬性含 `gen_ai.evaluation.name`（Required）、`gen_ai.evaluation.score.value`、`gen_ai.evaluation.score.label`、`gen_ai.evaluation.explanation`；應盡量掛在被評估的 GenAI span 底下，否則用 `gen_ai.response.id` 關聯。這讓線上評估分數可以回貼到 trace（本筆記推論）。[OTel-Events]
- Events 在部分語言尚未可用，需查 spec-compliance matrix。[OTel-Events]

## MCP 慣例

- 建議 MCP 用專屬慣例而不是 RPC 或 HTTP 慣例，因為後兩者不涵蓋串流內的訊息交換，且一個 HTTP 請求可能承載多個 MCP 請求。[OTel-MCP]
- Context propagation：把 OTel propagator 的 context 注入 MCP 請求的 `params._meta`，接收端從中取出當作 remote parent，因為 HTTP trace context 只涵蓋 HTTP 請求本身。[OTel-MCP]
- Span name 格式 `{mcp.method.name} {target}`，target 對應 `gen_ai.tool.name` 或 `gen_ai.prompt.name`，沒有低基數 target 就只用 method；`mcp.resource.uri` 預設不進 span name（避免高基數），可 opt-in。範例：`tools/call get-weather`。client 為 `CLIENT`、server 為 `SERVER`。[OTel-MCP]
- MCP tool call 與 GenAI `execute_tool` span 相容：若能確定外層 GenAI instrumentation 已追蹤該次工具執行，就不要另開 span，而是把 MCP 屬性加到既有 span 上。[OTel-MCP]
- Metrics：`mcp.client.operation.duration`、`mcp.server.operation.duration`、`mcp.client.session.duration`、`mcp.server.session.duration`。[OTel-MCP]
- 傳輸方式靠屬性辨識：stdio 為 `network.transport=pipe`；Streamable HTTP 與舊的 HTTP+SSE 以 `mcp.protocol.version` 區分（`2025-06-18` 或更新為 Streamable HTTP，`2024-11-05` 或更舊為 SSE）。[OTel-MCP]

## 自架後端：Langfuse 與 Phoenix

| 項目 | Langfuse | Phoenix |
| --- | --- | --- |
| 接 OTel 的方式 | 在 `/api/public/otel` 收 OTLP（HTTP/JSON 與 HTTP/protobuf，尚不支援 gRPC）；Basic Auth（`pk-lf-…:sk-lf-…` 的 base64）；本機部署需 >= v3.22.0 [Langfuse-OTel] | 以 OpenTelemetry 為基礎，用 OpenInference instrumentation；提供 `arize-phoenix-otel`（Python）與 `@arizeai/phoenix-otel`（JS）；`px setup` 可自動偵測框架並接好 trace export [Phoenix] |
| 專屬注意事項 | 直送 OTel 要加 header `x-langfuse-ingestion-version=4`，否則資料最多延遲約 10 分鐘出現；userId、sessionId、tags 等 trace 層屬性要傳到每個 span（建議用 OTel Baggage + `BaggageSpanProcessor`，但 baggage 會跨服務傳遞，勿放敏感資料）[Langfuse-OTel] | 另有 Remote MCP Server（`/mcp`），可讓 Claude Code、Cursor 等 MCP client 直接查 traces、datasets、experiments [Phoenix] |
| GenAI 慣例（本筆記歸納） | 預設聚焦 LLM 相關 span（Langfuse SDK span、帶 `gen_ai.*` 屬性的 span、已知 LLM instrumentor）；屬性會對應到 Langfuse 資料模型 [Langfuse-OTel] | 來源未特別說明 |
| 授權 | README：MIT，`ee` 資料夾除外 [Langfuse] | README：Elastic License 2.0 (ELv2) [Phoenix] |
| 自架部署 | Docker Compose（本機／單 VM，無高可用、擴充或備份）；production 用 Kubernetes (Helm)，另有 AWS、Azure、GCP（Terraform 範本）；Render、Railway 為社群維護 [Langfuse] [Langfuse-Self] | Docker Hub 映像（`arizephoenix/phoenix`，建議 production 釘版本）、Helm chart、CLI（`uvx arize-phoenix serve`）、AWS CloudFormation、Railway／Render／Cloud Run／Azure 一鍵部署 [Phoenix] [Phoenix-Self] |
| 架構相依 | Web + Worker 兩個容器，加 Postgres、ClickHouse、Redis/Valkey、S3/Blob；事件先寫 S3 再入庫，資料庫暫時掛掉不會遺失 [Langfuse-Self] | 來源未列 |
| 自架功能限制 | 部分附加功能需 license key（EE）[Langfuse-Self] | 官方文件稱自架免費、無功能限制，可完全離線（air-gapped）；企業版支援另見 Arize AX [Phoenix-Self] |
| 其他 | 預設會回報基本使用統計到 PostHog（不含 traces、prompts 等內容），README 有說明 [Langfuse] | 提供 tracing、evals、datasets、experiments、prompt management [Phoenix] [Phoenix-Self] |

## Coding agent 自身的遙測：Claude Code

- 開啟方式：`CLAUDE_CODE_ENABLE_TELEMETRY=1`，再以 `OTEL_METRICS_EXPORTER`（otlp / prometheus / console / none）與 `OTEL_LOGS_EXPORTER`（otlp / console / none）選匯出器，並設 `OTEL_EXPORTER_OTLP_PROTOCOL`（Claude Code 沒有預設協定，必須設）、`OTEL_EXPORTER_OTLP_ENDPOINT`、`OTEL_EXPORTER_OTLP_HEADERS`。預設匯出間隔 metrics 60000 ms、logs 5000 ms。[CC-OTel]
- 管理員用 managed settings 的 `env` 統一下發；repo 內 `.claude/settings.json` 的 OTel 匯出變數會被忽略，避免專案自行開啟遙測或指定目的地。設了 `OTEL_EXPORTER_OTLP_ENDPOINT` 後，開發者自設的 per-signal endpoint 會被移除，等於鎖定 collector。[CC-OTel]
- Claude Code 不會把 `OTEL_*` 傳給它啟動的子程序（Bash、hooks、MCP servers），所以在 Bash 裡跑的 OTel 應用要自己設 exporter。[CC-OTel]
- Metrics：`claude_code.session.count`、`lines_of_code.count`、`pull_request.count`、`commit.count`、`cost.usage`（USD）、`token.usage`、`code_edit_tool.decision`、`active_time.total`。可用 `OTEL_METRICS_INCLUDE_*` 控制基數。[CC-OTel]
- Events（經 logs 匯出）：`claude_code.user_prompt`、`assistant_response`、`tool_result`、`tool_decision`、`api_request`、`api_error`、`api_refusal`、`mcp_server_connection`、`skill_activated`、`compaction`、`subagent_completed`、hook 相關事件等；用 `prompt.id` 可串起單一 prompt 觸發的所有事件。[CC-OTel]
- 內容預設遮蔽：prompt 文字顯示為 `<REDACTED>`，要 `OTEL_LOG_USER_PROMPTS=1` 才記錄；`OTEL_LOG_TOOL_DETAILS=1` 記錄 Bash 指令、MCP/skill 名稱等工具參數；`OTEL_LOG_TOOL_CONTENT=1` 記錄工具內容（需開 tracing，預設截斷於 60 KB）；`OTEL_LOG_RAW_API_BODIES` 會輸出完整 API request / response，含整段對話歷史，等同同意前述所有內容記錄。[CC-OTel]
- Traces（beta，預設關）：需 `CLAUDE_CODE_ENABLE_TELEMETRY=1` 加 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`，並設 `OTEL_TRACES_EXPORTER`。Span 階層為 `claude_code.interaction`（每個 prompt 一個 root）底下有 `llm_request`、`tool`（其下 `tool.blocked_on_user`、`tool.execution`）與 hook；subagent 的 span 巢在父 tool 之下。注意這是 Claude Code 自己的 span 名稱，原文列的是 `claude_code.*`，而非 OTel GenAI 慣例的 span 命名（本筆記比較）。[CC-OTel]
- 跨程序關聯：tracing 開啟時，Bash 子程序會繼承 `TRACEPARENT`；直連 Anthropic API 時每個模型請求帶 `traceparent` header；Agent SDK 與 `-p` 模式會讀入呼叫端的 `TRACEPARENT`，讓 Claude Code 的 span 成為呼叫端 trace 的子節點。[CC-OTel]
- 團隊視角：能回答用量、成本、被拒絕或被使用者擋下的工具、commit / PR 數等問題；是否記錄 prompt 與工具內容是隱私與合規決策，預設都是關的。[CC-OTel]

## 相關筆記

- [agent-evals.md](agent-evals.md)：trace 是 eval 的原料；`gen_ai.evaluation.result` 可把評分回貼到 trace。
- [harness-engineering.md](harness-engineering.md#狀態可靠性與可觀測)：harness 層的狀態、可靠性與可觀測做法。
- [agent-security.md](agent-security.md)：prompt / 工具內容進入遙測時的敏感資料與憑證邊界。

## 來源

| 簡稱 | 來源 | 讀取程度 |
| --- | --- | --- |
| OTel-GenAI | [Semantic conventions for generative AI systems（OpenTelemetry, semantic-conventions-genai）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/README.md) | 全文（索引頁） |
| OTel-Inference | [Semantic conventions for generative AI client inference（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md) | 部分（Status、inference span 的 name / kind / 屬性表、metrics 標題；events 段落未讀） |
| OTel-Spans | [Semantic conventions for generative client AI spans（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md) | 部分（Embeddings、Execute tool、內容擷取段落；Memory 僅看 opt-in 註解） |
| OTel-Agent | [Semantic Conventions for GenAI agent and framework spans（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) | 部分（開頭、各 span 的 name / kind、Invoke agent 屬性表前段、Agent skills） |
| OTel-Events | [Semantic conventions for Generative AI events（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md) | 全文 |
| OTel-Metrics | [Semantic conventions for generative AI metrics（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md) | 部分（目錄、client / agent metrics 段落） |
| OTel-TokenMetrics | [Semantic conventions for generative AI inference token metrics（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-token-metrics.md) | 部分（開頭說明、各 metric 的名稱 / 單位 / 屬性表） |
| OTel-MCP | [Semantic conventions for Model Context Protocol (MCP)（OpenTelemetry）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md) | 部分（目錄、context propagation、client span、metrics 標題、transport 表；範例未讀） |
| Langfuse | [langfuse/langfuse README（Langfuse）](https://github.com/langfuse/langfuse/blob/main/README.md) | 部分（部署、授權、telemetry 段落；廠商性質） |
| Langfuse-OTel | [OpenTelemetry (OTEL) for LLM Observability（Langfuse）](https://langfuse.com/integrations/native/opentelemetry) | 部分（endpoint、v4 header、屬性傳遞、ingestion 選項；attribute mapping 細節未讀；廠商性質） |
| Langfuse-Self | [Self-host Langfuse（Langfuse）](https://langfuse.com/self-hosting) | 全文（廠商性質） |
| Phoenix | [Arize-ai/phoenix README（Arize）](https://github.com/Arize-ai/phoenix/blob/main/README.md) | 部分（功能、tracing、部署、授權段落；廠商性質） |
| Phoenix-Self | [Self-Hosting - Phoenix（Arize）](https://arize.com/docs/phoenix/self-hosting) | 全文（廠商性質） |
| CC-OTel | [Monitoring（Anthropic, Claude Code Docs）](https://code.claude.com/docs/en/monitoring-usage) | 部分（設定、管理員鎖定、traces、events 列表、metrics 列表；各 event 屬性細節未讀；廠商性質） |
