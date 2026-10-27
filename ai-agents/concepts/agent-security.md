# Agent 安全：沙箱、權限與憑證

本篇的「做法」一節從 [harness-engineering.md](harness-engineering.md) 的「沙箱，權限與安全」章節拆出，逐條照搬；「Prompt injection 的系統性防禦」一節是後來新增（2026-10-14）。內文的 `[簡稱]`（如 [Clark]）對應文末「來源」表，「做法」一節的完整索引見原筆記的來源索引。

## 做法

- 憑證：沙箱內憑證數量應為零；在邊界注入（network proxy 於外送請求時加 token；vault 僅在工具執行時解密）。[Clark] [Bhat&He] [Schmid-NoCode] [Jain]
- Brain / Hands 解耦：模型 + loop 與工具執行環境分離，沙箱壞了就重建重試，brain 壞了從 session log 恢復；hands 可放在客戶 VPC；啟動可平行，首 token 延遲 p50 降 60%，p95 降超過 90%。[Bhat&He] [L.Martin]
- 依任務意圖建模沙箱：新聞室範例（研究員有網路無寫入工具，查核員無網路，發佈者只看過濾後內容），避免「不可信輸入」與「危險工具」同在一處；coding agent 只在 commit 的幾分鐘才有簽章金鑰。[Clark]
- 範圍化能力與意圖式存取：每個任務產生 just-in-time 工具（例如僅限事故頻道的 Slack 讀取）；當請求與原始意圖不符（調查延遲卻要寄信）就拒絕或升級給人。控制放在邊界外、與模型無關。[Jain]
- Auto-review：以唯讀、不可再開子 agent 的 review agent 審核升權請求，輸入含風險分類、完整 transcript 與使用者授權程度（刪掉你要求刪的檔 vs 刪掉從未提到的 .git）。用來減少 approval fatigue 而不開 full access。[Kundel]
- 沙箱技術：OS 層 seatbelt (macOS)，bubblewrap (Linux)，自製 Windows 沙箱；隔離強度從 fork/exec，container，gVisor 到 microVM (Firecracker, Cloud Hypervisor)；fork/exec 與 container 共用核心，有核心漏洞與 noisy neighbor 風險。[Kundel] [Bhardwaj]（部分）
- 沙箱持久化：增量快照，copy-on-write，可在別台節點還原，並支援樹狀搜尋式回溯。[Bhardwaj]（部分）
- 核准是有範圍的執行狀態（誰，哪個 session，哪個工具，參數，期限），會過期而非無限重試。[Govindarajan]
- 供應鏈與身分：Cross App Access (XAA) 讓 agent 沿用 SSO/IdP。[Clark]
- 調查數據：有寫入權限的 agent 比例從 52% 升到 89%（僅取自直播片段，未深讀，引用前請回原片確認）。[WF26]
- Credential-injecting proxy：在外送請求的 header 動態注入 token，模型只執行程式、永遠看不到密鑰，被 prompt injection 也無從洩漏 (Managed Agents)。[Leo]
- Swiss cheese 多層防禦：model alignment、harness（權限、prompt、對 bash 指令做 AST parsing）、sandbox（網路與檔案系統隔離）；重點是阻止外洩，sandbox 放在託管環境而不是滿是 secrets 的個人電腦。[Shihipar]
- 不要讓 secrets 以檔案形式存在：權限不足的 agent 會在檔案系統裡找更高權限的 token；RL 讓模型更會找漏洞，安全必須來自外圍基礎設施。[LoopsDebate]
- 隔離層級：開發任務用 VM 而不只是 container（container 不是牢靠邊界，K8s 上還有 noisy neighbor）；每個 cloud agent 一台獨立 VM，連 DB 與服務一起，避免 worktree 共用 DB / cache 的副作用。對照：Pocock 用 git worktree + Docker，Solmaz 用每任務一個 K8s pod。[Bichard] [Zakariasson] [Pocock] [Solmaz]
- 不可逆判準：「這件事能不能不尷尬地復原？」不能就不做，留註記交還給人。實作：email 只准草稿、AI 專屬金鑰保留稽核軌跡、開發工具唯讀、跑在獨立 VPS；留意 lethal trifecta（不可信輸入 + 網路 + 機密資料同在）。[Parsons]
- 依角色設 sandbox：review 與資安分析類 subagent 一律 read-only，要產文件的才給寫入。Guardian approvals（Codex 實驗功能）讓 subagent 判斷特權操作要不要叫人，以降低核准疲勞、取代 YOLO mode，概念同 [Kundel] 的 auto-review（講者現場示範沒成功）。[Codex-MC]
- 用 hook 禁止 agent 修改最敏感的區域（加密、認證）；為特定 invariant 建 security sentinel automation，只在改到相關檔案的 PR 上跑。[Zakariasson]
- Containment 優先於 human-in-the-loop：使用者約核准 93% 的 permission prompt，審核疲勞讓人工把關不可靠。Claude Code 用 OS 級 sandbox（Seatbelt / bubblewrap）預設允許讀取、寫入限於 workspace、網路預設禁止，沙箱內不再打斷使用者，permission prompt 減少 84%。[Anthropic-Contain]
- 隔離強度配合使用者的監督能力：claude.ai 用 gVisor 臨時容器；Claude Code 用 OS sandbox 加人工核准（開發者看得懂 bash）；Cowork 面向非技術使用者，用本機 VM 當常開的硬邊界，憑證留在 host keychain，VM 只拿 per-session、可撤銷的縮權 token。[Anthropic-Contain]
- 事故教訓是「自己寫的元件最脆弱」：trust dialog 之前就執行了 project hook、allowlist 內的 api.anthropic.com 被拿來外洩資料，而 hypervisor、seccomp、gVisor 都守住了。對應做法：project-open、config-load、localhost listener 一律視同外部請求；egress allowlist 當成 capability grant（VM 內的 MITM proxy 只放行帶本 VM session token 的請求）；symlink 先解析再驗證路徑；掛載分 read-only、read-write、read-write-no-delete。[Anthropic-Contain]
- Agent loop 放在 VM 外、只把程式碼執行放進 VM（VM 起不來時 agent 仍能回應除錯，同 [Bhat&He] 的 brain / hands 分離）；tool 回傳值進入 context 前由小而快的 classifier 檢查。Auto mode 的 classifier 約擋下 83% 過度積極行為、誤擋約 0.4% 良性指令，只能當縱深防禦的一層。[Anthropic-Contain]
- 瀏覽器本身就是 sandbox：檔案用 File System Access API（目前僅 Chrome）、網路用 CSP + `<iframe sandbox>`、程式碼執行放 Web Worker 裡的 WebAssembly，不需要數 GB 的本機容器。[Willison]

## Prompt injection 的系統性防禦

本節資料取得日期 2026-10-14。上方「做法」已有 lethal trifecta（[Parsons]）、classifier 當縱深防禦（[Anthropic-Contain]）、sandbox 與憑證隔離等條目，下面不重複，只補「為什麼要靠系統設計」「有哪些已發表的設計模式」與「標準怎麼說」。

### 為什麼偵測與過濾不夠

- LLM 分不出指令來自誰：所有內容最後都被串成同一串 token，無法可靠依來源判斷指令的重要性，所以在 prompt 裡叫它別照做，也無法保證每次有效。[Willison-Trifecta]
- 偵測類產品的「擋下 95% 攻擊」在 web 安全裡是不及格：攻擊者的工作就是找出漏網的那 1–5%；用 SQL injection 或 XSS 作類比，失敗率 1% 的防護會被很快打穿。「用更多 AI 解決 AI 安全問題」本質上仍是機率式的。[Willison-Trifecta] [Willison-CaMeL]
- 設計模式論文的立場：只要 agent 與其防禦仍建立在現有語言模型上，偵測與對抗訓練之類的改進仍屬啟發式、本質脆弱，通用 agent 不太可能有可靠的安全保證；因此改問「現在能建出哪些有用又能抗 prompt injection 的 agent」，代價是刻意限制 agent 能做的事。[DesignPatterns]
- OWASP 的說法較保守：因為生成式 AI 的隨機性，不確定是否存在萬無一失的預防方法，所列措施只是「降低影響」；RAG 與 fine-tuning 也無法完全緩解。[OWASP-LLM01]
- 指令與資料的角色邊界本身不牢：Willison 轉述的研究指出，模型對文字「風格」比對實際內容更敏感，把注入文字改寫成不像角色標籤內的風格（destyling）後，平均攻擊成功率從 61% 降到 10%，作者認為除非模型有真正的角色感知，否則防禦只會是打地鼠。[Willison-PI]（Willison 轉述，未讀一手來源）
- 近期例子都落在「靠規則或另一個模型把關」的那一層：Claude Cowork 的網域 allowlist 被允許清單內的 api.anthropic.com 繞過（2026-01）；Snowflake Cortex 把 `cat` 列為免核准，卻被 process substitution 繞過（2026-03）；web_fetch 限制只能開使用者給的或搜尋回傳的 URL，後來發現可沿著已抓頁面內的連結逐層外洩，Anthropic 已移除該能力（2026-07）；Rehberger 對 Claude Code auto mode 的攻擊據稱 80% 成功，且 classifier 曾放行惡意程序建立卻擋下清理指令（2026-08；Willison 事後補註，這例沒有 LLM 誤從網頁接受惡意指令，較接近 confused deputy 而非典型 prompt injection）。[Willison-PI]（Willison 轉述，未讀一手來源）
- 對照面：Anthropic 公布 auto mode 的評估（1,053 位測試者中只有 13.6% 拒絕被換成危險指令的 permission prompt，auto mode 會擋下 89%；第三方測 720 次攻擊無一成功），Willison 的看法是比起讓人一直按確認好得多，但仍不信任以 AI 為基礎的防護，偏好確定性的 sandbox；另有人以 6,000 次郵件攻擊都未能洩漏 OpenClaw 實例的機密，Willison 認為這不構成保證。[Willison-PI]（Willison 轉述，未讀一手來源）

### Lethal trifecta

- 定義：agent 同時具備三項能力就能被誘騙去取私有資料並送給攻擊者：(1) 能存取私有資料；(2) 暴露於不可信內容（任何攻擊者可控、能進到 LLM 的文字或圖片）；(3) 能對外溝通並可用來外洩資料。[Willison-Trifecta]
- 用法：把它當設計與盤點的檢查表，逐個 agent / 工具組合問「三項是否同時成立」；唯一可靠的辦法是切掉其中一項。對使用者自行混搭 MCP 工具的情況，廠商幫不上忙，只能避免三者同時出現。[Willison-Trifecta]
- 對外溝通的管道比想像的多：任何能發 HTTP 請求的工具（呼叫 API、載入圖片、甚至提供使用者點的連結）都能外洩；一個工具可以同時包辦三項（GitHub MCP 例：讀公開 issue、讀私有 repo、開 PR）。[Willison-Trifecta]
- 實務上最容易砍的是外洩那一項：2026-06 OpenAI 的 Lockdown Mode 限制對外請求以阻止外洩最後一步，Willison 稱其用確定性機制、不靠會被攻破的 AI 評估，但它不阻止注入內容出現，也暗示預設設定下沒有穩固防護。[Willison-PI]（Willison 轉述，未讀一手來源）
- 另見上方「做法」的 [Parsons]（不可逆判準與 trifecta 提醒）與 [Anthropic-Contain]（egress allowlist 視為 capability grant）。

### 六種 design patterns

共同原則：agent 一旦讀了不可信輸入，就必須被約束到該輸入不可能觸發任何有後果的動作，且輸出不能成為外洩或影響後續 agent 行為的管道。這些模式刻意限制 agent 能解的任務範圍，並且與 sandbox、使用者確認等「最佳實務」並用，而非取代。[DesignPatterns]

- Action-Selector：agent 只把請求對應到預先定義的動作（像 LLM 驅動的 switch，動作可為帶參數的範本），工具回傳不回饋給 agent。代價：幾乎失去 LLM 模糊搜尋的好處，工作量轉移到預定義指令的設計，沒想到的良性請求會被擋。[DesignPatterns] [Willison-DP]
- Plan-Then-Execute：先在接觸不可信資料前定好固定的工具呼叫計畫，再執行；工具輸出不能讓 agent 偏離計畫（control flow integrity）。代價：後一步指令取決於前一步結果的任務難以預先承諾；而且仍擋不住內容被改寫（日程轉寄的信件本文）、看似無害的指令被重組（只承諾 `find` 與 `mv` 仍可能被誘導複製敏感檔），也不防使用者輸入本身的注入。[DesignPatterns] [Willison-DP]
- LLM Map-Reduce：每份不可信資料交給一個隔離、不能呼叫任意工具的 sub-agent 處理（map），輸出受限（布林值、預定類別，或用 regex 檢查），再由不用 LLM 的或受約束的 reduce 彙整。代價：任務必須能這樣拆；惡意檔案仍能騙過 map 讓自己被判為相關，導致錯誤的檔案被移動或複製。[DesignPatterns]
- Dual LLM：privileged LLM 規劃並使用工具、不碰不可信資料；quarantined LLM 處理不可信文字、沒有工具，回傳符號變數（`$VAR`），由非 LLM 的 orchestrator 在呼叫工具時才代換實際值。代價：需要 orchestrator 與符號記憶；任務無法嚴格拆解或 controller 難以規劃時失效；DeepMind 指出缺口：quarantined LLM 仍可能被注入而改寫要寄送的收件地址。[DesignPatterns] [Willison-CaMeL]
- Code-Then-Execute：agent 先寫出一段形式化程式（呼叫工具、並以無權限的 LLM 處理不可信文字）再執行，是 plan-then-execute 的一般化；CaMeL 即此模式的實作，用受限 DSL 讓資料流可完整追蹤。代價：與 plan-then-execute 同樣擋不住資料內容被改寫；實作成本見下節 CaMeL。[DesignPatterns] [Willison-DP]
- Context-Minimization：在後續步驟把使用者原話從 context 移除（例：先把請求轉成資料庫查詢，回覆客戶前丟掉原 prompt），防止使用者輸入的注入影響後續回覆。代價：後續回覆無法針對使用者說的內容調整；只擋使用者 prompt 這一路，不處理其他不可信資料。[DesignPatterns]
- 論文另有十個案例研究（OS 助理、SQL agent、Email/Calendar、客服、訂位、商品推薦、履歷篩選、藥品說明書、醫療診斷、軟體工程 agent），可依自己的場景對照，每個模式都附有 utility 與 security 的取捨。[DesignPatterns] [Willison-DP]

### CaMeL

- 做法：Google DeepMind 的 CaMeL（CApabilities for MachinE Learning）把使用者的（可信）請求轉成受限 Python 子集的程式，由自製 interpreter 逐步執行，因此控制流與資料流來自可信的請求，不可信資料無法改變程式流程；不需修改底層 LLM。[CaMeL] [Willison-CaMeL]
- P-LLM / Q-LLM：Privileged LLM 只看使用者請求並產生程式；Quarantined LLM 在程式中被呼叫來從不可信資料解析欄位（例如 `query_quarantined_llm("Find Bob's email address in [email]", output_schema=EmailStr)`），沒有工具權限。Q-LLM 可以用較小的模型，甚至在本機執行，P-LLM 的提供者因此看不到工具輸出。[CaMeL] [Willison-CaMeL]
- Capabilities 與資料流政策：每個值附帶 metadata（來源、誰可讀），interpreter 追蹤值之間的衍生關係（由不可信 `email` 取得的 `address` 也算不可信），並在每次呼叫工具前執行安全政策；政策可寫成任意 Python 邏輯，回傳 Allowed 或 Denied。例：`get_last_email` 一律允許，`send_email` 僅在收件人可信時才放行，否則詢問使用者。[CaMeL] [Willison-CaMeL]
- 成效：在 AgentDojo 上以可證明的安全解決 77% 的任務（無防護為 84%）；token 用量中位數為輸入 2.82 倍、輸出 2.73 倍。[CaMeL]
- 限制（論文自述）：不防不影響資料流的 text-to-text 攻擊（例如把郵件摘要成不同內容）與注入式釣魚，只能藉資料流圖讓 UI 顯示內容來源；使用者需要撰寫並維護安全政策，政策太嚴或含糊會需要使用者介入，造成 user fatigue；有 side-channel（例外、計時、外部資源的間接推論）；所有工具與服務都要理解 capabilities，否則 utility 下降；論文明言 prompt injection 並未被完全解決。[CaMeL] [Willison-CaMeL]

### OWASP 怎麼說

- LLM01:2025 的緩解清單（皆為降低影響，非根除）：(1) 在 system prompt 限定角色與能力；(2) 定義預期輸出格式並用確定性程式驗證；(3) 輸入與輸出過濾（語意過濾、字串檢查、RAG Triad 評估）；(4) 最小權限，API token 由應用程式用程式碼處理而非交給模型；(5) 高風險動作需人工核准；(6) 區隔並標示外部內容；(7) 對抗測試，把模型當成不可信使用者來測信任邊界。[OWASP-LLM01]
- 對照上面各節：LLM01 的 (4)(5)(6) 與設計模式、capabilities 同方向；(1)(3) 仍屬機率式防護，不要單獨依賴。這是本筆記的比較，不是 OWASP 的說法。
- Agentic Top 10（2026 版，2025-12 發布）與注入直接相關的條目：ASI01 Agent Goal Hijack（間接注入使 agent 的目標、任務選擇或決策路徑被改寫；與 LLM01 的差別在涵蓋多步驟的 agentic 影響）、ASI02 Tool Misuse and Exploitation（agent 在授權範圍內以不安全方式使用合法工具，起因包含 prompt injection）。次要相關：ASI05 Unexpected Code Execution（注入轉成可執行行為）、ASI06 Memory & Context Poisoning（注入的內容被存進記憶，影響後續）。[OWASP-AgenticTop10-PDF]
- ASI01 的緩解重點：所有自然語言輸入視為不可信；工具最小權限，高衝擊或改變目標的動作需人工核准；system prompt 鎖定且變更走設定管理；執行前驗證使用者與 agent 意圖並記錄偏離；記錄與監控目標、工具使用模式的基線。[OWASP-AgenticTop10-PDF]
- ASI02 的緩解重點：每個工具有最小權限 profile（scope、速率、egress allowlist）；逐次呼叫認證，高衝擊動作需人工確認並先給 dry-run；執行 sandbox 與 egress 控制；把 LLM 或 planner 輸出視為不可信，在執行前由 policy enforcement point 驗證意圖與參數、發短效憑證；用量預算；完整工具名與版本釘選；不可變的呼叫日誌與工具鏈異常偵測（如 DB 讀取後接外送）。[OWASP-AgenticTop10-PDF]
- 較早的 Threats and Mitigations 指南對應為 T6 Intent Breaking & Goal Manipulation 與 T2 Tool Misuse（含 Agent Hijacking，即 agent 讀入對抗性資料後被劫持）。[OWASP-Agentic-PDF] [OWASP-AgenticTop10-PDF]

### 套用到 Hermes

以下是本筆記根據 [Hermes 架構文件](../../work-experience/hermes-agent.md) 已寫內容，套用上面框架的推論，不是任何來源對 Hermes 的主張；文件沒寫的部分標為「未寫明」，需要實際查程式或設定確認。

- 不可信輸入有哪些（推論）：
  - 互動路徑：Telegram 與 Web UI 送來的訊息（誰能傳入文件未寫）；agent 經 broker 讀回的 Loki log、Jira saved filter 的內容、GitHub 內容，其中有外部人員可寫入的欄位（如案件文字、issue 內容）。
  - 排程路徑：`caserpt-analyze` 讀取的 CaseRpt 案件文字與 log；`ai-digest` 直連抓取的公開資料；`feedback-triage` 讀的稽核軌跡（其中含 agent 與工具的實際內容）。
  - 持久內容：`state.db`、`SOUL.md`（文件說永不刪除）；若不可信內容被寫進去，對應 ASI06 的情境（推論，文件未描述寫入路徑）。
- 目前已擋住的一角：以 trifecta 看，是「憑證與私有資料的直接取得」以及「工具能做什麼」。LLM 不持憑證、所有內部呼叫經 broker、tool allowlist 預設 DENIED、Jira 動詞釘死在單一 saved filter、NetworkPolicy 讓 broker 成為唯一內部 egress、稽核軌跡可事後查。這相當於 [Clark] 與 OWASP ASI02 的「least privilege 與 egress 控制」方向，被劫持的 agent 拿不到密鑰、也無法呼叫 allowlist 之外的內部資源。
- 排程 job 的「固定 system prompt 加純 Python 的 `render_*` / `parse_*`」，讓格式與流程由程式決定，LLM 只做內容判斷，精神上近 Plan-Then-Execute 與 Map-Reduce 的受約束輸出，但文件的目的是輸出一致，沒有說是為了防注入（推論）。
- 還缺的一角（推論）：
  - 「讀不可信內容」與「有外送能力的工具」仍可能在同一個 context 內：互動 agent 讀 log、Jira、案件文字後，又能呼叫經 broker 的發送類動作（如 Teams）或開 issue；文件沒寫 broker 是否檢查外送動作的內容、收件者，也沒寫是否把兩者隔離（Dual LLM、Plan-Then-Execute、CaMeL 式資料流政策都屬此類，目前文件未見）。若外送端點可被注入內容影響，trifecta 的第三項仍在。
  - broker 的 allowlist 管的是「能呼叫哪些工具」，而不是「資料從哪來、能流到哪去」；ASI02 提到的 egress allowlist、工具鏈異常偵測（讀取後接外送）與 intent gate，文件未寫。
  - 例外的直連：`caserpt-analyze` 的 Jira、`loop-triage` 與 `feedback-triage` 的 GitHub 自帶 token（文件第 7 節自述憑證面較大），其中 `caserpt-analyze` 一邊讀案件文字一邊持有 Jira token，是最需要檢視的組合（推論）。
  - `ai-digest` 直連抓公開資料並做 LLM 摘要，再經 broker 發送到 Teams：不可信內容加對外管道，值得確認摘要輸出如何被渲染（Willison-PI 提到 Copilot Cowork 因外部圖片在顯示時外洩）。[Willison-PI]（Willison 轉述，未讀一手來源）
  - Multi-model council（`multi_council`）會把內容送到其他模型；文件只寫 opt-in 與 fail-closed，未寫送出的內容範圍（推論）。
- 建議的檢查順序（本筆記的建議）：先盤點每個 job 與互動 agent 的 trifecta 三項，再看哪些外送動作可以改為確定性檢查（固定收件者、內容長度與格式驗證）或需要人工核准；Web UI 與 Telegram 的輸入視為使用者提示注入的來源，另行確認誰有權傳訊。

## 相關筆記

- [harness-engineering.md](harness-engineering.md)：Harness 實作做法總覽與完整來源索引
- [agent-evals.md](agent-evals.md)：持續改進與評估（evals）
- [../../work-experience/hermes-agent.md](../../work-experience/hermes-agent.md)：Hermes 架構（「套用到 Hermes」一節的依據）

## 來源

### 演講與影片

| 簡稱 | 影片 | 讀取程度 |
|---|---|---|
| Clark | [How Many Credentials Should Your AI Agent Have? Zero. (Docker)](https://www.youtube.com/watch?v=ZUZVNKFSmTM) | 全文 (廠商性質) |
| Bhat&He | [Claude Managed Agents and Evolution of Agentic Surfaces (Anthropic)](https://www.youtube.com/watch?v=K0X9QDRkIdg) | 全文 |
| Schmid-NoCode | [Agents Without Code: Skills, YAML, and Filesystems (Google DeepMind)](https://www.youtube.com/watch?v=fjF8EKnxKCU) | 全文 |
| Jain | [Unlock Agent Autonomy: The Runtime for AI-Native Systems (Docker)](https://www.youtube.com/watch?v=zaGyGgLW3SM) | 全文 (廠商性質) |
| L.Martin | [Claude for Long-Horizon Tasks, Lance Martin (Anthropic)](https://www.youtube.com/watch?v=9QebvrrY3KY) | 全文 |
| Kundel | [How Codex Works (OpenAI)](https://www.youtube.com/watch?v=shRR1e2HXMk) | 全文 |
| Bhardwaj | [From fork() to Fleet: Agent Sandbox Cloud (OpenAI)](https://www.youtube.com/watch?v=OqM67QG_Ikk) | 部分 (關鍵字段落 + 資訊欄) |
| Govindarajan | [The Model Was Right. The Harness Failed. (OpenAI)](https://www.youtube.com/watch?v=BInpv7lGp1o) | 全文 |
| WF26 | [WF26 Harness Engineering 全天直播 (551 分鐘)](https://www.youtube.com/watch?v=I2cbIws9j10) | 僅少數段落, 未深讀 |
| Leo | [An Interaction Is All You Need, Ivan Leo (Google DeepMind)](https://www.youtube.com/watch?v=8aVbXXvJUY4) | 全文 (agent 摘要，廠商性質) |
| Shihipar | [Claude Agent SDK [Full Workshop], Thariq Shihipar (Anthropic)](https://www.youtube.com/watch?v=TqC1qOfiVcQ) | 全文 (agent 摘要，廠商性質) |
| LoopsDebate | [The Great Loops Debate, Dex Horthy, Geoff Huntley, Ian Livingstone, Greg Pstrucha](https://www.youtube.com/watch?v=c35YoMdnI78) | 全文 (agent 摘要) |
| Bichard | [The Missing Primitive for Agent Swarms, Lou Bichard (Ona)](https://www.youtube.com/watch?v=5Sui_OnSRlY) | 全文 (agent 摘要) |
| Zakariasson | [Building your own software factory, Eric Zakariasson (Cursor)](https://www.youtube.com/watch?v=rnDm57Py54A) | 全文 (agent 摘要，廠商性質) |
| Pocock | [Full Walkthrough: Workflow for AI Coding, Matt Pocock](https://www.youtube.com/watch?v=-QFHIoCo-Ko) | 全文 (agent 摘要) |
| Solmaz | [Scaling Agents on Kubernetes with acpx and ACP, Onur Solmaz (OpenClaw)](https://www.youtube.com/watch?v=VaS2h-dY1-4) | 全文 (agent 摘要) |
| Parsons | [Ralph Loops: Build Dumb AI Loops That Ship, Chris Parsons (Cherrypick)](https://www.youtube.com/watch?v=2TLXsxkz0zI) | 全文 (agent 摘要) |
| Codex-MC | [OpenAI Codex Masterclass, Vaibhav Srivastav & Katia Gil Guzman (OpenAI)](https://www.youtube.com/watch?v=MhHEGMFCEB0) | 全文 (agent 摘要，廠商性質) |

### 文章與程式庫

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Anthropic-Contain | [How we contain Claude across products (Anthropic Engineering)](https://www.anthropic.com/engineering/how-we-contain-claude) | 全文 (agent 摘要) |
| Willison | [the browser is the sandbox, Simon Willison](https://simonwillison.net/2026/Jan/25/the-browser-is-the-sandbox/) | 全文 (agent 摘要，轉介 Paul Kinlan 的文章) |
| Willison-PI | [Simon Willison on prompt-injection（tag 頁，Simon Willison）](https://simonwillison.net/tags/prompt-injection/) | 部分（tag 頁收錄的 2026 年各篇 Willison 文章；其引用的一手研究與事件報告未讀） |
| Willison-Trifecta | [The lethal trifecta for AI agents: private data, untrusted content, and external communication（Simon Willison，2025-06-16）](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) | 全文 |
| Willison-DP | [Design Patterns for Securing LLM Agents against Prompt Injections（Simon Willison，2025-06-13）](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/) | 全文 |
| Willison-CaMeL | [CaMeL offers a promising new direction for mitigating prompt injection attacks（Simon Willison，2025-04-11）](https://simonwillison.net/2025/Apr/11/camel/) | 全文 |

### 論文與標準

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| DesignPatterns | [Design Patterns for Securing LLM Agents against Prompt Injections（Beurer-Kellner 等，arXiv 2506.08837，2025）](https://arxiv.org/abs/2506.08837) | 部分（摘要、第 2–3 節六種模式、案例研究的 utility/security 段落） |
| CaMeL | [Defeating Prompt Injections by Design（Debenedetti、Shumailov 等，Google DeepMind，arXiv 2503.18813v2）](https://arxiv.org/abs/2503.18813) | 部分（摘要、非目標、token 成本、side channel 與討論段落） |
| OWASP-LLM01 | [LLM01:2025 Prompt Injection（OWASP Gen AI Security Project）](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) | 全文 |
| OWASP-AgenticTop10-PDF | [OWASP Top 10 For Agentic Applications 2026（OWASP Gen AI Security Project，2025-12）](https://genai.owasp.org/download/52117/?tmstv=1765059207) | 部分（ASI01、ASI02 全文；ASI05、ASI06 說明段） |
| OWASP-Agentic-PDF | [Agentic AI - Threats and Mitigations v1.1（OWASP Gen AI Security Project，2025-12）](https://genai.owasp.org/download/45674/?tmstv=1739819891) | 部分（T2、T6 表列） |
