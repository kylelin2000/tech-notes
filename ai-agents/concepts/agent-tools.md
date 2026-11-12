# Agent 工具：寫給 agent 用的工具與 MCP server 設計

本篇整理設計給 agent 使用的工具與 MCP server 的做法（工具切分、回傳內容、錯誤、評估迭代、工具過多時的處理、MCP spec 2026-07-28 版的實作重點、官方 servers repo），資料取得日期 2026-10-14。2026-11-12 補入 AI Engineer 頻道 2026-10 至 2026-11 上傳的新影片（由 Claude Sonnet 讀逐字稿摘要後併入，未逐支回看影片）。內文的 `[簡稱]` 對應文末「來源」表。

## 工具切分與命名

- 工具不是 API 的一對一包裝：agent 的 context 有限，應針對少數高影響的工作流程設計工具，再逐步擴充；例如用 `search_contacts` 或 `message_contact`，而不是 `list_contacts`。[Anthropic-Tools]
- 把經常串在一起的多步操作合併成一個工具：`schedule_event`（找空檔並排程）取代 `list_users` + `list_events` + `create_event`；`search_logs`（只回相關行與前後文）取代 `read_logs`；`get_customer_context` 取代 `get_customer_by_id` + `list_transactions` + `list_notes`。[Anthropic-Tools] 講者實例：Reducto 把每個 API endpoint 各做一個 MCP tool 後，全團隊試用時 agent 自信建出沒人說得清的 workflow；改成更少、帶工作結構的工具，如 classify 後接 extract 合成單一 classify-to-extract，每步回傳下一步的情境指引，讓 agent 不在已知正確的部分自由發揮 (@06:00)。[Arya]
- 每個工具要有清楚且不重疊的用途；工具太多或功能重疊，會讓 agent 選錯或走低效率的策略。[Anthropic-Tools]
- 用共同前綴做 namespacing（依服務如 `asana_search`、`jira_search`，或依資源如 `asana_projects_search`）；前綴或後綴式命名對評估結果有不小的影響，且因模型而異，要用自己的 eval 決定。[Anthropic-Tools]
- MCP 的名稱規則：長度建議 1 到 128 字元、區分大小寫，只用 A-Z a-z 0-9 `_` `-` `.`，同一 server 內唯一；跨 server 聚合時可能撞名，client 或 proxy 應自行加前綴消歧，不要依賴 serverInfo 的 server 名稱（不保證唯一）。[MCP-Tools]
- 需要跨呼叫狀態時（購物車、瀏覽器 context、資料庫 transaction），由建立工具回傳明確的 handle，後續工具把它當一般參數；handle 的保存期限寫進建立工具的描述，過期或不存在時回傳工具執行錯誤讓模型重建。（non-normative 指引）[MCP-Tools]
- 講者補充（各自的實作經驗，非規格）：agent 無狀態，Reducto 加一個 snapshot 工具，一次回傳 pipeline 目前狀態、整體流程與帶具體 error code 的錯誤，讓 agent 引用實際內容而不是猜變數名稱；原則是給帶領域知識（正確模式、狀態、validator）的工具，讓正確路徑同時是最簡單的路徑 (@07:00, @08:02)。[Arya]
- 慢速或外部 API（例如 gateway 有最大等待時間）用同步會卡死應用，講者改成 async handle：start job 與 check job status 兩個工具，agent 先拿 handle、稍後取結果；稱差異很大但沒給數字 (@12:00)。[Leone]
- 防止 agent 重複呼叫同一工具的無限迴圈：工具回應要清楚，並設每個工具的最大呼叫次數（例如 search 類限制三次）(@11:02)。[Leone]
- 重試可能造成重複執行：講者的 MCP bridge 在 client 重啟時只重放 initialize（只是 handshake），絕不重放結果不確定的 tool call；回收 shared server 時，逾時仍未回覆的 call 標為「可能已執行」，叫呼叫者去查證 (@15:01)。[Konda]

## 回傳內容與 token 量

- 只回高訊號資訊，優先考慮上下文相關性而非彈性；避開 `uuid`、`256px_image_url`、`mime_type` 這類低階技術識別碼，改回 `name`、`image_url`、`file_type`。[Anthropic-Tools]
- 把不透明的英數 UUID 解析成有語意的名稱（甚至 0 起算的流水號）能降低幻覺、提高檢索準確度。[Anthropic-Tools]
- 大量輸出不要整份塞進 context，改成存起來只留指標：一個工具取回大量 log 後，把 log 存進儲存體並只把 ID 留在 context（Strands 用 agent state 保存），需要時再用 ID 讀取，做法是 fetch 與依 ID 讀取兩個工具 (@08:02)[Leone]；另一個團隊對巨大的 trace JSON 在 JSON 內截斷，agent 要完整內容時用 jq 寫程式取，理由是 agent 擅長寫程式 (@10:00)。[F.Ali]
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
- 錯誤訊息要含完整上下文，讓 agent 能直接據此自我修復 (@32:30)。[Nisi-Proser]
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
- 對 MCP server 可整個延遲載入（`mcp_toolset` 搭配 `default_config.defer_loading`），個別高頻工具再設 `defer_loading: false`。[Anthropic-AdvTools] 講者補充：OpenAI Codex app server 的 dynamic tools 也可標 deferred loading，由 tool search 工具按需找，講者建議新增的功能工具都標 deferred (@08:00, @16:00)。[Kundel-Harness]
- 講者的另一種壓低工具數量做法：連接器資料只暴露 describe（取得如何查的 schema）與 execute（讀寫刪）兩個 MCP 工具，其餘用 progressive discovery；限制塞進 tool description 的 context 量有幫助 (@05:01)。[Lopez]
- Programmatic Tool Calling：工具設 `allowed_callers`，由 Claude 寫程式在 code execution 中協調多個工具，中間結果不進 context，只回最終輸出；原文數字為複雜研究任務平均 token 由 43,588 降到 27,297（37%）。適合大量資料只需彙總、三個以上相依呼叫、平行處理；單次簡單查詢不划算。可平行或可安全重試（idempotent）的工具適合開放。[Anthropic-AdvTools]
- Code execution with MCP：把 MCP server 呈現為檔案系統上的程式碼 API（每個工具一個檔），agent 逐檔讀取需要的定義；原文範例 token 由 150,000 降到 2,000（98.7%）。也可改在 server 上加 `search_tools`，並用 detail level 參數控制回傳細節。[Anthropic-CodeExec]
- 其他好處：在執行環境內過濾 10,000 列只回 5 列、用程式寫迴圈與條件、中間結果預設不進模型（client 還可把 PII 先 tokenize）、可存檔續跑並把程式存成 skill。[Anthropic-CodeExec]
- 代價：需要安全的執行環境、sandbox、資源限制與監控，這些營運成本是直接呼叫工具不需要的。[Anthropic-CodeExec]

### Code mode 的講者實測與取捨

- 傳統 tool calling 的問題：大量 tool 目錄進 context、每次輸出累積，長任務出現 context rot，需要分頁、多輪與 compaction，增加延遲與成本 (@02:02)。code mode 改給「搜尋工具」「執行工具」與可寫程式的環境，讓 agent 循序、平行、條件式組合工具，只把必要結果回灌 context (@03:00)。[M.King]
- 講者列的四個理由：漸進揭露、可組合性（串接、fan-out）、token 效率（程式裡裁切輸出）、emergent behavior（agent 自行造工具；例如移除記錄中的 PII，在 context 內做會洩漏信用卡號，寫程式處理則不會）(@04:00)。[M.King]
- Arize 在 Phoenix 的演進：從 Bash 開始（sed、grep 加自家 CLI，輸出可存檔），加 Python sandbox，把 REST CRUD endpoint 提升成程式內可組合的 API，再加 SQL 做聚合（如 P95 latency 的 LLM span），避免逐頁翻 trace (@06:01)；也把 UI 操作做成 web worker 內的程式範式，雙向綁定瀏覽器 (@07:00)。[M.King]
- 風險與營運成本（補充上面的代價）：LLM 產生的程式碼、sandbox 資源與 egress、secret 不可回到 context、權限常過寬 (@08:00)；除錯變成除錯程式碼、工具參數變程式碼因此準確度要求更高、discovery 多一步 handshake、MCP 與 harness 都做 code mode 會有雙重 sandbox 與重複的 JSON 序列化 (@09:02)。[M.King]
- 未解問題：程式中途失敗無法從該步驟 resume；JavaScript 擅長 LLM 但不利數學；圖片等二進位要用簽名 URL 之類方式交出 sandbox；小模型可能能力不足，講者稱 frontier 模型在 code mode 表現最好 (@10:01)。[M.King]

## 給 agent 用的 CLI

以下全是講者的實作經驗與實測，不是規格。

- MCP 與 CLI 都做成薄介面：只負責接指令、呼叫平台、格式化結果；平台一天部署超過 10 次，所以用 OpenAPI spec 當單一事實來源去產生介面 (@03:00)。[Lopez]
- 設計原則：複雜查詢輸入用 JSON 比一堆 flag 更不用猜，輸出 JSON 可接 jq 裁剪 (@11:03)；名詞加動詞結構要全資源一致，若 agent 反覆犯同樣錯或呼叫錯指令，把它當成契約不夠明顯，改 CLI 而不是改提示 (@12:00)；不能有互動式 prompt，認證改用 flag、環境變數、設定檔並在帶外完成 (@15:00)。[Lopez]
- Skill 隨 CLI 發佈，否則 agent 不知道有這個 CLI；description 要能在相關問題被觸發，主 skill 指向 references 檔案漸進載入 (@13:00)。[Lopez]
- MCP vs CLI 取捨（Lopez 的看法）：MCP 規格實作不一，provider 有額外限制（講者稱 Claude 對 server 與 tool description 有 2KB 上限，字幕如此說，未對照官方文件）、工具執行時間有限；優點是 hosted 永遠最新、適合非技術使用者與快速原型。CLI 適合技術使用者、長任務、超長輸出（導向檔案再 head/tail），但要處理版本更新，沒有上限時 agent 可能陷入迴圈空轉 (@16:03)。[Lopez]
- MCP 認證與 elicitation 的實務：講者說規格偏重 OAuth、主要 client 也傾向它（例如 Anthropic custom connector 註冊沒有填 bearer token 的地方），使用者期待像手機 app 長期免重登 (@06:00)；elicitation 的 form mode 不能傳憑證，較新的 URL mode client 支援不一（講者說 Claude Desktop 直接回不支援），所以他們自己做連結加 widget (@08:00)。教訓是規格有但各 client 實作不一。[Lopez]
- 把人工驗證動作做成 deterministic CLI，不只寫在 prompt 或 skill：示範的 CLI 含 up/down、doctor、drive（join、reload、reset）、觀測（snapshot、storage、console、network、screenshot）、prove（Playwright 確定性檢查）、judge（小型快速模型的語意檢查），輸出回饋給 agent 自我修正，且對所有團隊成員一致 (@18:00)。[Nisi-Proser]
- 約 20,000 次 agent 呼叫（14 個 CLI）的 transcript 分析：約四分之一輸出被接到 head、grep、tail、Python、sort、wc 等 filter，read-heavy 指令更高（git show 與 cargo test 各 62%）；agent 用 pipe 繞過摩擦卻不回報 bug，所以 pipe 本身就是 bug report (@01:00)。[Bhardwaj-CLI]
- Pipe 會吃掉錯誤：沒開 pipefail 時 pipeline 回傳最後一個指令的 exit code，`cargo test | head` 可能顯示成功；tail 只看到三行無害輸出就漏掉錯誤。做法是失敗時最後幾行放簡短摘要加完整 log 路徑 (@02:02)。[Bhardwaj-CLI]
- 講者自己的工具稽核：80% 的 session 查詢輸出被接 filter，且 83% 的 pipe 是同一子指令加同樣 pipe 工具、出現至少 10 次的固定模式，所以該內建成旗標 (@03:00)。輸出大小上限不等於選擇：一個 120 萬字元的 session，搜尋命中附近只要約 3,000 字元，要提供只讀命中周圍、只要最後幾則、compact 模式（一行一筆，比 JSON 小約 6 倍）等選擇旗標，而不是只加截斷 (@04:02)。[Bhardwaj-CLI]
- 外部佐證（講者轉述文章，細節字幕未明說）：Infracost 把 jq/Python 過濾搬進 CLI、加 compact 格式與 skill，六題難題從 0/6 變 6/6，整個 benchmark 成本降 41% (@06:00)。[Bhardwaj-CLI]
- Skill.md、help 文字、錯誤訊息就是介面，agent 照字面執行：講者把 `--deep` 旗標改成 no-op 但 skill 沒改，95 次搜尋 95 次仍傳該旗標，改寫 skill 後為 0 次；新旗標到位後 pipe 讀取比例從 82% 降到約四分之一 (@06:00)。旗標要被用到才有效：55% 的 pipeline 只有 tail 或 sed，先出 range 與 limit 旗標；GitHub CLI 的 `list --limit` agent 用 81%，cargo test quiet 模式只有約十分之一會用，要在 help 與 skill 教；大輸出預設少印並寫「showing 20 of 300, 加 offset 20 看下一段」(@08:01)。[Bhardwaj-CLI]
- Agent mode：許多 harness 會設環境變數，CLI 可偵測後輸出不同格式。DuckDB 的做法是給純文字表格並說明省略幾列與如何取回、超大查詢提早停並明說、錯誤用 JSON；模型讀入的輸出少 59%，但只佔總 token 約 0.5%，成本與時間沒變，所以要量 turn 數與答對率，不只量 token (@09:02)。[Bhardwaj-CLI]
- 不要全丟給 agent 設計：agent 設計給 agent 用的工具傾向想像成人用再外掛。講者引用的研究稱多數官方 MCP server 只是包 API、97% 的真實 MCP tool description 有問題、agent 自己寫的 context file 沒提升成功率且更貴（未查證原研究）；合理分工是人決定工具該長怎樣，讓 agent 對照真實 transcript 檢查 (@10:01)。[Bhardwaj-CLI]

## Agentic search：grep 還是 embeddings

- Claude Code 不做預建索引行得通，是因為程式碼的特性：repo 通常不大、半結構化、有 import 與 test 等線索形成自然階層、已在本機磁碟；講者引用 Boris 的說法，試過向量資料庫後放棄，原因是索引難與不斷變動的程式碼同步 (@02:00)。公司文件則混有 PDF、圖片、簡報，沒有可 grep 的資料夾結構，規模大、格式不標準、要管權限，選擇主要看資料規模與願意投入的整理成本 (@04:01)。[G.He]
- 規模經驗法則（講者主張）：約 100 到 1,000 個檔案可以只用本機檔案搜尋；數千至數百萬檔案就不能讓 agent 每次讀檔燒 token，需要預先索引給粗略方向 (@05:01)。[G.He]
- 不要手動決定 hybrid RAG 還是逐檔搜尋，給 harness 一組工具讓 agent 自己選：先用語意搜尋縮小範圍，再用 list、metadata 過濾、grep、read 深入 (@08:01)。五個工具：檢索、列檔或依 metadata 走訪、對特定檔 grep、讀內容（offset 加 max length）、頁面截圖索引；企業用建議 hybrid（BM25 加向量加權融合，再對前 100 筆做 LLM 重排），單用關鍵字或向量只是 baseline (@10:00)。[G.He]
- 複雜文件（圖表、掃描檔）要在 pre-index 階段結構化解析（表格轉 markdown 等保留空間資訊）並保存頁面截圖；評估 OCR 看表格表示與版面保真度 (@13:00)。儲存上資料落在磁碟前面加記憶體快取層，metadata 與權限在 ingest 時就標進向量庫以便在檢索層過濾 (@16:00)。Demo：135 個財報檔，agent 用檢索加 grep 加 read(offset, length) 像遠端檔案系統一樣查並引用來源 (@19:01)。[G.He]
- 反方意見：另一位講者（code review 產品）認為 grep 不精確又貴，agent trace 中大部分 token 是 grep、file read、cache write，改建內部知識庫 / living wiki 歸納每個功能與涉及檔案，並整合 Jira、Linear、Confluence、Notion，以判斷是否符合作者意圖 (@11:00)；這是廠商自家統計，沒有給對照數據。[Gupta]

## MCP spec 重點（2026-07-28 版）

- 相對前版 2025-11-25 的重大變更：移除 protocol-level session 與 `Mcp-Session-Id`，移除 initialize 握手，每個請求在 `_meta` 帶 protocol version 與 client capabilities；server 必須實作 `server/discover`；所有結果帶必填的 `resultType`；server 發起的請求改為 Multi Round-Trip Requests（`input_required`）。[MCP-Changelog]
- 其他影響 server 實作者的變更：`tools/list` 等 list 結果須帶 `ttlMs` 與 `cacheScope`；Streamable HTTP POST 須帶 `Mcp-Method`、`Mcp-Name` header；移除 SSE 串流續傳（斷線後 client 須用新 request ID 重發）；tasks 移到 extension。[MCP-Changelog]
- 已標為 Deprecated 的有 Roots、Sampling、Logging、HTTP+SSE transport，以及 Dynamic Client Registration（改推 Client ID Metadata Documents）；新實作不應採用。[MCP-Changelog]
- `tools/list`：結果不得隨連線或其他請求的副作用而變，但可依請求帶的授權（例如 scope）而不同；順序應固定，以利 client 快取與 prompt cache 命中。[MCP-Tools] [MCP-Changelog]
- `inputSchema` 必須是有效的 JSON Schema 物件（預設 2020-12）；無參數工具建議用 `{"type":"object","additionalProperties":false}`；`outputSchema` 與 `inputSchema` 現已允許任意 JSON Schema 2020-12 關鍵字。[MCP-Tools] [MCP-Changelog]
- `annotations` 描述工具行為，但 client 必須把它視為不可信，除非來自受信任的 server；Anthropic 文章提到它可揭露工具是否需 open-world 存取或有破壞性變更。[MCP-Tools] [Anthropic-Tools]
- `x-mcp-header` 可把基本型別參數鏡射成 `Mcp-Param-{name}` header 給中間設備路由；不要標在密碼、API key、PII 等敏感參數上，因為 header 對中間設備可見。[MCP-Tools]
- Server 的安全義務：驗證所有輸入、實作存取控制、對工具呼叫限速、清理輸出；client 應在敏感操作前徵求使用者確認。[MCP-Tools]
- 講者經驗（非規格）：用遠端 MCP server 當全公司 skill 的 source of truth，由伺服器依角色與查詢套政策給出適合版本，內部用了約 6 個月，並提到 MCP 社群有 skills over MCP 工作小組、API 尚未定案 (@08:00)；選用 tools 而非 resources 送 skill，理由是 resources 的 client 支援不一，tools 幾乎處處可用 (@09:00)。[Wilinski]
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
| Lopez | [Designing CLIs for Agents, Not Humans, Pedro Lopez (Airbyte)](https://www.youtube.com/watch?v=3wj6sgbi1YA) | 全文 (agent 摘要，2026-11) |
| Gupta | [How to Build an AI Code Review Agent, Daksh Gupta (Greptile)](https://www.youtube.com/watch?v=4UtrRVtUN_g) | 全文 (agent 摘要，2026-11) |
| Kundel-Harness | [Building on the Codex Harness, Dominik Kundel (OpenAI)](https://www.youtube.com/watch?v=9WiBJRO84yY) | 全文 (agent 摘要，2026-11) |
| M.King | [Stop Giving Your Agent Tools. Give It a Sandbox, Mikyo King (Arize AI)](https://www.youtube.com/watch?v=dAoOYFx7ZYw) | 全文 (agent 摘要，2026-11) |
| Leone | [Why Bigger Context Windows Won't Save Your Agent, Elizabeth Fuentes Leone (AWS)](https://www.youtube.com/watch?v=DrfyORO8RqA) | 全文 (agent 摘要，2026-11) |
| Konda | [Your Sub-Agents Are a Distributed System. Treat Them Like One., Girish Konda (Microsoft)](https://www.youtube.com/watch?v=DxP5aW4VknQ) | 全文 (agent 摘要，2026-11) |
| Arya | [Why We Deleted Our MCP Server and Rebuilt It, Abhi Arya (Reducto)](https://www.youtube.com/watch?v=jJQoVkd5yLg) | 全文 (agent 摘要，2026-11) |
| Nisi-Proser | [Teach Your Agent to Prove It's Done, Nick Nisi & Zack Proser (WorkOS)](https://www.youtube.com/watch?v=q4WC4TowkBo) | 全文 (agent 摘要，2026-11) |
| Bhardwaj-CLI | [Your Agent Hates Your CLI, Ayush Bhardwaj (Allos AI)](https://www.youtube.com/watch?v=rS36lYuvXQ8) | 全文 (agent 摘要，2026-11) |
| Wilinski | [From 36% to 100%: How Self-Improving Agents Write Their Own Skills, Rafal Wilinski (Runlayer)](https://www.youtube.com/watch?v=u-o0sW9nwmk) | 全文 (agent 摘要，2026-11)，廠商性質 |
| G.He | [Grep or Embeddings? Agentic Search Over Company Documents, George He (LlamaIndex)](https://www.youtube.com/watch?v=X4w2Pkz5tDY) | 全文 (agent 摘要，2026-11) |
| F.Ali | [We Kept Rebuilding Our AI Agent. Here's What Survived, Fuad Ali (Arize AI)](https://www.youtube.com/watch?v=YIhvrvHtonk) | 全文 (agent 摘要，2026-11) |
