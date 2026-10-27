# Agent 工具：寫給 agent 用的工具與 MCP server 設計

本篇整理設計給 agent 使用的工具與 MCP server 的做法（工具切分、回傳內容、錯誤、評估迭代、工具過多時的處理、MCP spec 2026-07-28 版的實作重點、官方 servers repo），資料取得日期 2026-10-14。內文的 `[簡稱]` 對應文末「來源」表。

## 工具切分與命名

- 工具不是 API 的一對一包裝：agent 的 context 有限，應針對少數高影響的工作流程設計工具，再逐步擴充；例如用 `search_contacts` 或 `message_contact`，而不是 `list_contacts`。[Anthropic-Tools]
- 把經常串在一起的多步操作合併成一個工具：`schedule_event`（找空檔並排程）取代 `list_users` + `list_events` + `create_event`；`search_logs`（只回相關行與前後文）取代 `read_logs`；`get_customer_context` 取代 `get_customer_by_id` + `list_transactions` + `list_notes`。[Anthropic-Tools]
- 每個工具要有清楚且不重疊的用途；工具太多或功能重疊，會讓 agent 選錯或走低效率的策略。[Anthropic-Tools]
- 用共同前綴做 namespacing（依服務如 `asana_search`、`jira_search`，或依資源如 `asana_projects_search`）；前綴或後綴式命名對評估結果有不小的影響，且因模型而異，要用自己的 eval 決定。[Anthropic-Tools]
- MCP 的名稱規則：長度建議 1 到 128 字元、區分大小寫，只用 A-Z a-z 0-9 `_` `-` `.`，同一 server 內唯一；跨 server 聚合時可能撞名，client 或 proxy 應自行加前綴消歧，不要依賴 serverInfo 的 server 名稱（不保證唯一）。[MCP-Tools]
- 需要跨呼叫狀態時（購物車、瀏覽器 context、資料庫 transaction），由建立工具回傳明確的 handle，後續工具把它當一般參數；handle 的保存期限寫進建立工具的描述，過期或不存在時回傳工具執行錯誤讓模型重建。（non-normative 指引）[MCP-Tools]

## 回傳內容與 token 量

- 只回高訊號資訊，優先考慮上下文相關性而非彈性；避開 `uuid`、`256px_image_url`、`mime_type` 這類低階技術識別碼，改回 `name`、`image_url`、`file_type`。[Anthropic-Tools]
- 把不透明的英數 UUID 解析成有語意的名稱（甚至 0 起算的流水號）能降低幻覺、提高檢索準確度。[Anthropic-Tools]
- 需要兩種粒度時提供 `response_format` enum（`concise` / `detailed`）：detailed 帶後續呼叫要用的 ID（如 Slack 的 `thread_ts`），concise 只回內容；原文範例 206 對 72 tokens，約省三分之二。[Anthropic-Tools]
- 回應格式（XML、JSON、Markdown）會影響 eval 表現，沒有通用最佳解，用自己的 eval 選。[Anthropic-Tools]
- 對可能很大的回應，組合使用 pagination、range selection、filtering、truncation，並設合理預設值；Claude Code 預設把工具回應限制在 25,000 tokens。[Anthropic-Tools]
- 截斷時要附上引導文字，鼓勵 agent 改用多次小而準的搜尋，而不是一次大範圍搜尋。[Anthropic-Tools]
- 要給程式讀的回傳，在描述裡寫清楚回傳欄位與型別（如 `id (str)`、`status` 的可能值），因為模型會寫程式解析輸出。[Anthropic-AdvTools]
- MCP 的 `structuredContent` 可放任何 JSON 值，有 `outputSchema` 時 server 必須符合；為了向後相容，同時回傳結構化內容的工具仍應把序列化 JSON 放進一個 TextContent。[MCP-Tools]

## 錯誤訊息

- 參數驗證失敗等錯誤，要寫成具體且可執行的改正建議，而不是不透明的錯誤碼或 traceback；也可以在錯誤裡示範正確的輸入格式。[Anthropic-Tools]
- MCP 把錯誤分兩種：protocol error（未知工具、請求格式錯誤、server 錯誤，用 JSON-RPC error，模型通常難以自行修復）與 tool execution error（API 失敗、輸入驗證、商業邏輯，放在結果裡設 `isError: true`，client 應交給模型自我修正）。[MCP-Tools]
- 範例：`Invalid departure date: must be in the future. Current date is 08/08/2025.`，錯誤文字直接帶出判斷依據。[MCP-Tools]
- 看 eval 指標：大量因參數無效的錯誤，代表描述或範例不夠清楚；大量重複呼叫，代表分頁或 token 上限參數需要調整。[Anthropic-Tools]

## 工具描述與用 eval 迭代

- 把工具描述當成寫給新進同事的說明：把原本隱含的查詢格式、專有名詞、資源之間的關係都寫明；參數名稱要無歧義（`user_id` 而非 `user`），並用嚴格的資料模型約束輸入輸出。[Anthropic-Tools]
- 小幅修改描述就可能有顯著影響：web search 工具上線時發現 Claude 會在 query 多加 2025，改描述後修正；Sonnet 3.5 在 SWE-bench Verified 的成績也來自精修工具描述。[Anthropic-Tools]
- 流程：先做原型（包成本機 MCP server 或 DXT，用 `claude mcp add` 連到 Claude Code 自己試）→ 產生以真實情境為本的評估任務 → 程式化跑 eval → 分析 → 讓 agent 協助改工具 → 重複。[Anthropic-Tools]
- 評估任務要貼近真實、需要多次（甚至數十次）工具呼叫，避免過於簡單的 sandbox 任務；每題配可驗證的答案，verifier 不要嚴格到因格式或標點誤判。[Anthropic-Tools]
- 用簡單的 while loop 配合 LLM API 跑每個任務；請 agent 在工具呼叫前先輸出 reasoning 與 feedback 區塊，或開 interleaved thinking，以便找出描述的缺陷。[Anthropic-Tools]
- 除準確率外，也記錄單次與整體執行時間、工具呼叫次數、token 消耗、工具錯誤；呼叫軌跡能看出常見工作流，提示哪些工具可以合併。[Anthropic-Tools]
- 分析時要讀原始 transcript，不只讀 agent 的自述（agent 沒說的往往更重要）；可把多份 transcript 貼給 Claude Code 讓它一次重構多個工具，並用 held-out 測試集避免對訓練用 eval 過擬合。[Anthropic-Tools]
- 描述難以表達用法慣例時，可加 `input_examples`（1 到 5 個、用真實資料、涵蓋最小／部分／完整填寫）；原文內部測試複雜參數處理的準確率從 72% 升到 90%。只在用法不明顯處加。[Anthropic-AdvTools]

## 工具太多時

- 五個 server、58 個工具約佔 55K tokens，加上 Jira 一個就約 17K；Anthropic 內部看過工具定義吃掉 134K tokens；除了成本，常見失敗是選錯工具與參數錯誤（如名稱相近的 `notification-send-user` 與 `notification-send-channel`）。[Anthropic-AdvTools]
- Tool Search Tool：把工具標 `defer_loading: true`，一開始只載入搜尋工具，需要時才展開 3 到 5 個相關工具；內部測試 token 約降 85%，MCP eval 準確率 Opus 4 由 49% 升到 74%、Opus 4.5 由 79.5% 升到 88.1%。不破壞 prompt caching。[Anthropic-AdvTools]
- 適用情境：工具定義超過 10K tokens、有選錯工具的問題、多 server、10 個以上工具；工具少於 10 個或每個 session 都常用則效益小。常用的 3 到 5 個工具維持載入，其餘延遲。搜尋比對名稱與描述，所以描述要清楚。[Anthropic-AdvTools]
- 對 MCP server 可整個延遲載入（`mcp_toolset` 搭配 `default_config.defer_loading`），個別高頻工具再設 `defer_loading: false`。[Anthropic-AdvTools]
- Programmatic Tool Calling：工具設 `allowed_callers`，由 Claude 寫程式在 code execution 中協調多個工具，中間結果不進 context，只回最終輸出；原文數字為複雜研究任務平均 token 由 43,588 降到 27,297（37%）。適合大量資料只需彙總、三個以上相依呼叫、平行處理；單次簡單查詢不划算。可平行或可安全重試（idempotent）的工具適合開放。[Anthropic-AdvTools]
- Code execution with MCP：把 MCP server 呈現為檔案系統上的程式碼 API（每個工具一個檔），agent 逐檔讀取需要的定義；原文範例 token 由 150,000 降到 2,000（98.7%）。也可改在 server 上加 `search_tools`，並用 detail level 參數控制回傳細節。[Anthropic-CodeExec]
- 其他好處：在執行環境內過濾 10,000 列只回 5 列、用程式寫迴圈與條件、中間結果預設不進模型（client 還可把 PII 先 tokenize）、可存檔續跑並把程式存成 skill。[Anthropic-CodeExec]
- 代價：需要安全的執行環境、sandbox、資源限制與監控，這些營運成本是直接呼叫工具不需要的。[Anthropic-CodeExec]

## MCP spec 重點（2026-07-28 版）

- 相對前版 2025-11-25 的重大變更：移除 protocol-level session 與 `Mcp-Session-Id`，移除 initialize 握手，每個請求在 `_meta` 帶 protocol version 與 client capabilities；server 必須實作 `server/discover`；所有結果帶必填的 `resultType`；server 發起的請求改為 Multi Round-Trip Requests（`input_required`）。[MCP-Changelog]
- 其他影響 server 實作者的變更：`tools/list` 等 list 結果須帶 `ttlMs` 與 `cacheScope`；Streamable HTTP POST 須帶 `Mcp-Method`、`Mcp-Name` header；移除 SSE 串流續傳（斷線後 client 須用新 request ID 重發）；tasks 移到 extension。[MCP-Changelog]
- 已標為 Deprecated 的有 Roots、Sampling、Logging、HTTP+SSE transport，以及 Dynamic Client Registration（改推 Client ID Metadata Documents）；新實作不應採用。[MCP-Changelog]
- `tools/list`：結果不得隨連線或其他請求的副作用而變，但可依請求帶的授權（例如 scope）而不同；順序應固定，以利 client 快取與 prompt cache 命中。[MCP-Tools] [MCP-Changelog]
- `inputSchema` 必須是有效的 JSON Schema 物件（預設 2020-12）；無參數工具建議用 `{"type":"object","additionalProperties":false}`；`outputSchema` 與 `inputSchema` 現已允許任意 JSON Schema 2020-12 關鍵字。[MCP-Tools] [MCP-Changelog]
- `annotations` 描述工具行為，但 client 必須把它視為不可信，除非來自受信任的 server；Anthropic 文章提到它可揭露工具是否需 open-world 存取或有破壞性變更。[MCP-Tools] [Anthropic-Tools]
- `x-mcp-header` 可把基本型別參數鏡射成 `Mcp-Param-{name}` header 給中間設備路由；不要標在密碼、API key、PII 等敏感參數上，因為 header 對中間設備可見。[MCP-Tools]
- Server 的安全義務：驗證所有輸入、實作存取控制、對工具呼叫限速、清理輸出；client 應在敏感操作前徵求使用者確認。[MCP-Tools]
- Authorization 為選用；使用 HTTP transport 時才應依此 spec，stdio 應改從環境取得憑證。[MCP-Auth]
- 角色：受保護的 MCP server 是 OAuth 2.1 resource server，MCP client 是 OAuth client，授權伺服器可與 server 同機或分離；server 必須實作 Protected Resource Metadata（RFC 9728），client 靠它發現授權伺服器。[MCP-Auth]
- Client 必須在授權與 token 請求都帶 `resource`（RFC 8707），值為 MCP server 的 canonical URI；server 必須驗證 token 的 audience 是自己，只接受發給自己的 token，且不得接受或轉送其他 token。[MCP-Auth]
- 每個 HTTP 請求都要帶 `Authorization: Bearer`；token 不可放 URI query；無效或過期回 401，scope 不足回 403 並在 `WWW-Authenticate` 帶 `error="insufficient_scope"`、`scope`、`resource_metadata`，且一次列出該操作需要的全部 scope。[MCP-Auth]
- Scope 採最小權限：初始只給低風險的探索／讀取 scope，高權限操作首次出現時再用 scope 挑戰升權；避免在 `scopes_supported` 公布全部 scope、避免 `*` 之類的大包 scope、不要只因 token 帶了 scope 就略過伺服器端授權邏輯。[MCP-Security] [MCP-Auth]
- Confused deputy（MCP proxy server 對第三方 API 使用 static client ID 並允許動態註冊時）：必須做 per-client consent（登記每位使用者核准的 `client_id`、同意頁顯示 client 名稱／scope／redirect_uri、CSRF 與防 iframe）、redirect_uri 精確比對、`state` 單次使用且在使用者同意後才設定；consent cookie 用 `__Host-` 前綴並綁定 client_id。[MCP-Security]
- Token passthrough 明文禁止：server 不得接受未明確發給自己的 token，也不要把 client 的 token 原樣轉給下游；否則會繞過限速等控制、破壞稽核軌跡與信任邊界。[MCP-Security]
- State handle hijacking（2026-07-28 版新增；拿掉 protocol session 後，對應 2025-11-25 版的 Session Hijacking 一節）：不能把「持有 handle」當成身分驗證；handle 用安全亂數產生、設有效期，並在伺服器端與已驗證使用者綁定（如以 `<user_id>:<handle>` 當 key，user ID 取自驗證過的 token）。[MCP-Security]
- 授權回應的 `iss`（RFC 9207）：授權伺服器應回傳；client 必須在兌換 code 前與記錄的 issuer 做字串比對，以防 mix-up attack。[MCP-Auth] [MCP-Security]
- 本機 server：用 stdio 限制只有 client 可存取；若走 HTTP，要求 token 或改用權限受限的 unix domain socket。[MCP-Security]
- Client 端 SSRF（OAuth discovery 的 URL 可能指向內網或雲端 metadata）：要求 HTTPS、擋私有／link-local IP、驗證 redirect 目標、必要時用 egress proxy；不要自己手寫 IP 驗證。支援 Client ID Metadata Documents 的授權伺服器同樣要防。[MCP-Security]

## 官方 servers repo

- 該 repo 定位為 reference implementations，用來示範 MCP 功能與 SDK 用法，是給開發者參考的教學範例，不是 production-ready；使用者要自行評估安全需求與威脅模型。[MCP-Servers]
- README 說明想找 server 清單請看 MCP Registry，這個 repo 只收 steering group 維護的少數 reference servers。[MCP-Servers]
- 目前列出的 reference servers：Everything（測試用，含 prompts、resources、tools）、Fetch（網頁內容擷取與轉換）、Filesystem（可設存取控制的檔案操作）、Git、Memory（知識圖譜式記憶）、Sequential Thinking、Time。[MCP-Servers]
- 已封存到 servers-archived 的有 GitHub、GitLab、Google Drive、Google Maps、PostgreSQL、Puppeteer、Redis、Sentry、Slack、SQLite、Brave Search、AWS KB Retrieval、EverArt；部分已由官方或其他維護者接手（如 Brave Search 改由 Brave 官方 server、Slack 由 Zencoder 維護）。[MCP-Servers]
- TypeScript 版可用 `npx -y @modelcontextprotocol/server-memory` 啟動，Python 版可用 `uvx mcp-server-git`；README 列出的 SDK 涵蓋 C#、Go、Java、Kotlin、PHP、Python、Ruby、Rust、Swift、TypeScript。[MCP-Servers]

## MCP / ACP / A2A 比較

- 「ACP」有兩個，不要混用：Agent Client Protocol 標準化 code editor／IDE 與 coding agent 之間的通訊，類比 LSP [ACP-Intro]；IBM 的 Agent Communication Protocol 是 agent 之間的 REST 協定，IBM 頁面現已標示「ACP is now part of A2A under the Linux Foundation」[IBM-ACP]。下文的 ACP 預設指 Agent Client Protocol。
- IBM 頁面列出的 ACP 特色：REST 為基礎、SDK 可選、非同步為主但支援同步、串流用 SSE、可離線以 metadata 發現 agent；並附遷移指南連結。[IBM-ACP]

| 面向 | MCP | Agent Client Protocol | A2A |
|---|---|---|---|
| 連接誰與誰 | agent／模型 ↔ 工具、API、資料來源 [MCP-Tools] | 編輯器 ↔ coding agent [ACP-Intro] | 獨立、不透明的 agent ↔ agent（對等協作）[A2A-Spec] |
| 傳輸 | Streamable HTTP（POST 帶 `Mcp-Method`、`Mcp-Name` header）；本機另有 stdio [MCP-Changelog] [MCP-Auth] | 本機：子行程 JSON-RPC over stdio；遠端：HTTP 或 WebSocket（遠端支援仍在進行中）[ACP-Intro] | 協定綁定有 JSON-RPC 2.0 over HTTP(S)、gRPC、HTTP/REST，也可自訂；串流用 SSE [A2A-Spec] |
| 發現機制 | server 必須實作 `server/discover` [MCP-Changelog] | 編輯器依需求啟動 agent 子行程 [ACP-Arch] | Agent Card：well-known URI `/.well-known/agent-card.json`、registry、直接設定 [A2A-Spec] |
| 狀態模型 | 已移除 protocol-level session 與 `Mcp-Session-Id`；跨呼叫狀態用明確 handle [MCP-Changelog] [MCP-Tools] | 一條連線可有多個並行 session [ACP-Arch] | 有狀態的 `Task`（server 產生 `taskId`）加選用的 `contextId` 分組 [A2A-Spec] |
| 治理 | 本篇來源未載 | 本篇來源未載 | Linux Foundation 專案，由 Google 貢獻，Apache 2.0 [A2A-Repo] [LF-A2A] |
| 目前版本 | 2026-07-28 [MCP-Changelog] | 本篇來源未載 | `1.0.0`（最新釋出；前版 0.3.0、0.2.6、0.1.0）[A2A-Spec] |

### A2A 重點

- 定位：讓不同框架、廠商的 agent「as agents, not just as tools」互相溝通，且不暴露內部狀態、記憶或工具（opaque execution）。[A2A-Repo] [A2A-Spec]
- 分層：規範分三層，資料模型（`Task`、`Message`、`AgentCard`、`Part`、`Artifact`、`Extension`）、抽象操作、協定綁定；`spec/a2a.proto` 是唯一權威的 normative 定義。[A2A-Spec]
- Agent Card：A2A Server 必須提供，描述身分、能力、skills、端點與驗證需求；`supportedInterfaces` 依偏好順序列出傳輸與 URL，client 選第一個自己支援的。[A2A-Spec]
- Task 狀態：`TASK_STATE_SUBMITTED`、`WORKING`、`COMPLETED`、`FAILED`、`CANCELED`、`REJECTED`、`INPUT_REQUIRED`、`AUTH_REQUIRED`；其中 `COMPLETED`、`FAILED`、`CANCELED`、`REJECTED` 為終止狀態，終止後不能再收訊息。[A2A-Spec]
- 更新方式三種：輪詢 `GetTask`、串流（需 `capabilities.streaming` 為 `true`）、push notification webhook（需 `capabilities.pushNotifications` 為 `true`）。[A2A-Spec]
- 驗證：agent 被視為一般企業應用，client 從 Agent Card 的 `securitySchemes` 得知需求，憑證在帶外取得；server 必須驗證每個請求；任務中需要授權時可進入 `TASK_STATE_AUTH_REQUIRED` 交由 client 處理。[A2A-Spec]
- 與 MCP 的分工（spec Appendix B 原意）：兩者互補；MCP 負責 agent 如何連接與使用工具、API、資源，A2A 負責獨立 agent 作為對等方如何發現彼此、協商互動方式、管理共同任務；例如 A2A Server agent 為完成任務，可再用 MCP 呼叫底層工具。[A2A-Spec]
- 治理：Linux Foundation 於 2025-06-23 宣布接手 A2A，稱將維持 vendor neutral（新聞稿，屬宣示性質）。[LF-A2A]

### Agent Client Protocol 重點

- 啟動方式：使用者連接 agent 時，編輯器依需求啟動 agent 子行程，所有通訊走 stdin/stdout；一條連線支援多個並行 session。[ACP-Arch]
- 訊息模式：大量使用 JSON-RPC notification 讓 agent 即時串流更新到 UI；同時用 JSON-RPC 的雙向請求，讓 agent 對編輯器發請求，例如要求工具呼叫的權限。[ACP-Arch]
- 重用 MCP：盡量重用 MCP 的 JSON 表示與型別，另有顯示 diff 等 coding UX 的自訂型別；使用者可讀文字預設為 Markdown。[ACP-Intro] [ACP-Arch]
- 與 MCP 的接法：編輯器把使用者設定的 MCP server 設定傳給 agent，讓 agent 直接連 MCP server；編輯器自己要提供工具時，可把自己的 MCP server 當設定給 agent，並提供小型 proxy 把 stdio 請求轉回編輯器。[ACP-Arch]
- 信任假設：ACP 用於使用者信任的模型，編輯器仍可控制 agent 的工具呼叫，並提供本機檔案與 MCP server 的存取。[ACP-Arch]

### 什麼時候用哪個（本筆記歸納）

- 要讓 agent 取用工具、資料或 API：MCP，設計重點見本篇前面各節。
- 要讓編輯器或其他 client 驅動一個 coding agent（權限請求、串流更新、diff 顯示）：Agent Client Protocol。
- 要讓不同團隊或廠商的 agent 互相委派長時間任務、且彼此不共享內部狀態：A2A；IBM 的 Agent Communication Protocol 已併入 A2A，新設計不需另選它。
- 三者可疊用：編輯器經 Agent Client Protocol 驅動 agent，agent 用 MCP 取用工具，並經 A2A 委派給遠端 agent。
- harness 層對 MCP 與 ACP 分工的說明見 [harness-engineering.md](harness-engineering.md#工具-tools-與-skills)（MCP 負責 agent 對外，ACP 負責 client 對 harness）。

## 相關筆記

- [harness-engineering.md](harness-engineering.md#工具-tools-與-skills)：harness 層的工具取捨（tools、bash、code gen）與 skills。
- [agent-security.md](agent-security.md)：沙箱、權限與憑證，與本篇 MCP 授權／token 邊界互補。
- [../../work-experience/hermes-agent.md](../../work-experience/hermes-agent.md)：Hermes 的 Tool Broker 就是一個 MCP server，持有憑證並作為內部資源的單一出口。

## 來源

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Anthropic-Tools | [Writing effective tools for agents — with agents（Anthropic Engineering，2025-09-11）](https://www.anthropic.com/engineering/writing-tools-for-agents) | 全文（廠商性質） |
| Anthropic-CodeExec | [Code execution with MCP: Building more efficient agents（Anthropic Engineering，2025-11-04）](https://www.anthropic.com/engineering/code-execution-with-mcp) | 全文（廠商性質） |
| Anthropic-AdvTools | [Introducing advanced tool use on the Claude Developer Platform（Anthropic Engineering，2025-11-24）](https://www.anthropic.com/engineering/advanced-tool-use) | 全文（廠商性質） |
| MCP-Changelog | [Key Changes（Model Context Protocol，spec 2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/changelog) | 全文 |
| MCP-Tools | [Tools（Model Context Protocol，spec 2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | 全文 |
| MCP-Auth | [Authorization（Model Context Protocol，spec 2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) | 全文 |
| MCP-Security | [Security Best Practices（Model Context Protocol，2026-07-28）](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) | 全文 |
| MCP-Servers | [modelcontextprotocol/servers README（GitHub）](https://github.com/modelcontextprotocol/servers/blob/main/README.md) | 部分（開頭至 Getting Started） |
| A2A-Spec | [Agent2Agent (A2A) Protocol Specification（a2aproject/A2A，docs/specification.md，版本 1.0.0）](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) | 部分（§1 簡介、§2 核心概念、§3.4–3.5、§5.2、§7 驗證授權、§8 Agent Card、§9.1、Appendix B） |
| A2A-Repo | [Agent2Agent (A2A) Protocol README（a2aproject/A2A，GitHub）](https://github.com/a2aproject/A2A/blob/main/README.md) | 全文 |
| LF-A2A | [Linux Foundation Launches the Agent2Agent Protocol Project（The Linux Foundation，2025-06-23）](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents) | 全文（新聞稿，宣示性質） |
| IBM-ACP | [Agent Communication Protocol (ACP)（IBM Research）](https://research.ibm.com/projects/agent-communication-protocol) | 全文（廠商性質） |
| ACP-Intro | [Introduction（Agent Client Protocol）](https://agentclientprotocol.com/get-started/introduction) | 全文 |
| ACP-Arch | [Architecture（Agent Client Protocol）](https://agentclientprotocol.com/get-started/architecture) | 全文 |
