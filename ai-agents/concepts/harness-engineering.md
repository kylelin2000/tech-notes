# Harness Engineering 實作筆記

整理自 YouTube 頻道 AI Engineer (@aiDotEngineer) 搜尋 "harness" 的結果，另補 3 篇工程文章與 3 個開源 harness repo，目的是萃取對實作 agent harness 有用的做法，並標註每項資訊的來源。

- 整理日期：2026-10-06；2026-10-07 補入待讀清單的 22 支（由 agent 讀逐字稿後整理，見「範圍與方法」）；2026-11-12 補入 AI Engineer 頻道 2026-10 至 2026-11 上傳的新影片（由 Claude Sonnet 讀逐字稿摘要後併入，未逐支回看影片）
- 性質：個人學習筆記，非官方內容。內容為對公開演講的中文摘要與歸納，版權屬原講者與 AI Engineer，細節與數據請以原影片為準。
- 相關筆記：概念脈絡見 [prompt-to-graph.md](prompt-to-graph.md)（Prompt → Context → Harness → Loop → Graph 的發展史），本篇聚焦 Harness 層的實作做法。
- 使用方式：內文中的 `[講者簡稱]` 對應文末「來源索引」表，可直接點連結回原影片。部分影片來自廠商 (Oracle, Docker, Cast AI, RELAI, W&B, Google, Temporal, Factory, Cursor, OpenAI Codex, Anthropic)，帶宣傳性質，已在索引標註。數字後的 (@mm:ss) 是影片時間點，可直接跳去核對。閱讀範圍與限制見文末「範圍與方法」。

---

## 定義與基本觀念

- Harness = Agent 去掉模型後剩下的全部（loop，tools，context 管理，guardrails，memory，驗證，沙箱，觀測）。[Chambers] [Martinez] [Kumar]
- 容易混淆：ML 領域的 "eval harness" (lm-eval-harness) 是測試框架，與 agent harness 不同。[Kumar]
- Harness 不等於 agent loop，是包在 loop 外面的東西，甚至可以是 loop 外面再一層 loop。[Kumar]
- 為什麼要有：模型是租來的黑盒，會被換版、context 受限、行為不穩；harness 提供可靠性與控制，讓便宜或舊模型也能做事（GPT-3.5 示範，全程沒改 prompt）。[Kumar] [Martinez]
- 兩種 agent：我們使用的（Claude Code，Cursor，Kiro；harness 是 memory，skills，MCP，團隊標準）與我們建造的（還需要 loop 管理，擴展，身分，付款，執行環境，可觀測與評估）。[Chambers]
- 抽象層級演進：Messages API（自己寫 loop） → Agent SDK（打包 Claude Code harness） → Managed Agents（連同託管基礎設施一起給）。[Bhat&He] [L.Martin]
- Harness 也是一個「共同演化」的東西：模型釋出時常伴隨 harness 變更，模型訓練時就包含自家 harness（apply_patch，bash 引號語意）。[Prabaker] [Lopopolo] [Horthy-SF]
- 類比：模型是處理器，agent runtime 是作業系統，skills 是應用層。核心 scaffolding 可以薄到只剩 bash + 檔案系統，缺的是領域專業，所以「別再為每個領域重建 agent，改建 skills」。[Zhang&Murag]
- 第一方定義的趨同：Codex =「模型 + 統一 harness（工具執行、環境設定、內建安全）」，app、CLI、IDE、Slack、GitHub 共用同一個 harness；Google 則把 harness 與模型一起訓練後由平台託管 (Managed Agents)，並主張模型越強 scaffolding 越會脫落（專用檔案工具被 bash 取代）。[Codex-MC] [Leo]
- 兩層 loop：內層是 coding agent harness（context manager、tools/MCP、memory、skills loader），外層是 workflow（skills、sub agents、MCP、hooks），workflow 是塑造 harness 行為的藍圖。[Touil]
- 持久執行 (durability) 也該算 harness 的必要組成，而不是可選的基礎設施。[Warrick]
- Claude Agent SDK = 把 Claude Code 內部反覆重建的元件（tools、loop、prompts、檔案系統、skills、sub agents、compaction、hooks、memory）打包；講者主張 bash + 檔案系統是最強的通用 agent 工具，心力應放在怎麼拆 sub agent、怎麼設計搜尋介面、怎麼驗證，而不是重做 compactor。[Shihipar]
- Harness 的兩層切法：runtime（agent loop 在哪跑、state 怎麼存才能 resume，近似傳統軟體工程）與 context / orchestration（決定呼叫哪個模型、看到什麼 context，含 prompt、tools、memory、compaction，講者形容為 wild west）(@02:00)。[Katz]

## 設計原則與取捨（什麼該做，什麼該刪）

- Harness 內含的是「模型做不到什麼」的假設，模型升級後假設會過期。例：Sonnet 4.5 的 "context anxiety" 靠 context reset 補，Opus 4.5 不需要，reset 變成純負擔（延遲，cache 被丟）。每次換模型都要重新檢查哪些元件可以刪。[Bhat&He] [Prabaker] [CMA-1]
- 刪減的證據：Cursor 用約 200 行 agent 檔取代約 12，000 行 TypeScript；Manus 半年重構 harness 5 次；LangChain deep research 一年重寫 3 次；Vercel 砍掉 80% 工具；WorkOS 刪 95% skills 後結果更好。經驗法則：若模型進步後 harness 反而更複雜，很可能過度設計 ("build to delete")。[Schmid-NoCode] [Nisi]
- 不要過度設計 (bitter lesson)：做最少的 context 管理，在對的時間把指示給模型；context 的需求不會被模型進步取代。[Lopopolo]
- 相反觀點：弱模型更依賴 harness，同模型不同 harness 差距超過 20 個百分點（HarnessBench 52.4% 到 76.2%），所以投資 harness 可讓本地開源模型逼近前沿模型。[Bhargava]
- 「harness 不夠」：若問題出在模型訓練（如維護性，RL 只獎勵測試通過），再多 harness 或 loop 也補不了，要人讀程式碼並事先規劃。[Horthy-SF]
- 對模型要「引導不要規定」：指示寫目標與限制，不寫死步驟；流程固定就寫腳本。過度 prompt 會拖慢模型（GPT-5 被叫去讀完所有檔案後才改，很慢）。可以直接問模型「我的指示哪裡讓你變慢」。[Schmid-Evals] [Chen&Fioca]
- 順著模型訓練的習慣：工具要 in-distribution (apply_patch, shell + ripgrep)，與官方 harness 對齊。[Kundel] [Chen&Fioca]
- 依賴第一方 harness (Codex, Claude Code) 並從外面 steer，而不是自己重寫 coding harness；或用 SDK / app-server 嵌入。[Lopopolo] [Chen&Fioca] [Kundel]
- 嵌入 Codex 的實務：app server 是包住 harness 的 JSON-RPC 協定（stdio 或 WebSocket），有超過 120 種 client message，涵蓋 thread 與 turn、設定 goal、列 plugin、file search、改檔案系統，比 ACP 能更細地控制個別部件 (@05:00)。建議附加 developer instructions 而非改寫 base instructions，因為 OpenAI 持續為各模型調 prompt 使其 in distribution (@17:00)。協定在版本間會變，要把自己指定版本的 harness 一起打包出貨，不依賴使用者已安裝的 CLI (@09:01)。[Kundel-Harness]
- 並非所有問題都需要 agent：例 DevOps agent 花兩小時調 prompt，不如 90 秒寫 bash。多數生產環境 agent 是「大量確定性程式 + 少量 LLM 步驟」。[Horthy-12F]
- 先問要不要 agent：四項檢查（任務複雜度、價值、關鍵能力是否已去風險、出錯代價與發現難度）；決策樹畫得出來就做 workflow。預算反推：每任務約 10 美分只買得起 30 到 50k tokens (@03:01)。[Zhang-EA]
- 選題的兩個問題：能不能驗證它的工作（lint、編譯、執行），能不能回復（程式碼有 git；computer use 訂外送則不可逆，錯誤會累積）。兩者都是才是好的 agent 題目。[Shihipar]
- Agent 程式碼大約每六個月要重想或重寫一次，因為模型能力變化會讓舊假設失效；寫 code 快 10 倍，就該丟 code 快 10 倍。[Shihipar]
- 保持簡單：先只做 environment、tools、system prompt 三元件並反覆迭代，cache 軌跡、平行 tool call 等優化留到行為穩定之後。不同產品的 agent 骨幹幾乎相同，差別只在 tools 與 prompt。[Zhang-EA]
- Capability 不等於 reliability：更強的模型與更好的 spec / context 都不等於驗證；「work on the harness, not on the code」。[Sheikh]
- 瓶頸不在智力：Weitekamp 稱現在的 agent 是 "mismanaged genius"，缺的是指定、管理、重用與驗證工作的那一層；Alvoeiro 則說瓶頸已是人類注意力，「做什麼」留給人，「怎麼做」交給系統。[Weitekamp] [Alvoeiro]
- 讓系統隨模型變好：Factory 把編排寫在 prompt 與 skills（約 700 行文字），確定性邏輯只留很薄一層（跑驗證、handoff 問題沒處理就擋住）。與 [Nisi] 的「enforce with code」相反，見「意見分歧」。[Alvoeiro]
- 規劃 human-in-the-loop，實作才 AFK（人類日班、AI 夜班）；不要連想法、研究、QA 都自動化，否則產出缺乏品味的 slop，QA 是把人的品味灌回 codebase 的時機。[Pocock]
- Codebase 本身就是 harness：模組化、相關程式碼放一起、用模型熟悉的慣例（package.json 的 start script）、提供既有範例讓 agent 照抄；deep module（小介面、大功能）讓 agent 好導航好測試，AI 沒人看管時傾向產出 shallow 結構。[Zakariasson] [Pocock]
- 從小開始：目標先抓 2 到 3 倍而不是 100 倍；不要閉關三個月蓋 software factory，從小的增量 loop 開始交到同事手上；先做單一序列 loop，別急著平行。[LoopsDebate] [Parsons]
- 核心要小、能力放 plugin：把模型 context 成本當成核心的持續開銷，可選能力放邊緣；新能力依 capability ladder 決定放哪層（既有 owner → 既有 plugin 契約 → 窄的通用 SDK 能力 → 最後才動核心介面）。DeepSeek 的 harness 更徹底，連 shell、fs、todo、plan、compaction 都是 plugin，loop 本身只留文件化的擴充點。[OpenClaw-repo] [DeepSeek-H]
- 「harness 已死」的證據：UC Berkeley 比較 Pi、Codex、Claude Code 等 harness 在 7 個 frontier model 上，較新模型的 SWE-bench Lite 分數沒有顯著差異；Apple 與 EPFL 也發現專用 MLE harness 在 MLE-bench 差異不大 (@05:00)。但兩項研究都顯示 harness 對每題成本有顯著差異；講者調 cache hit rate、token efficiency、model mix，在不降品質下降低 Grokbot 的成本與延遲 (@13:01)。與 [Bhargava] 的 20 個百分點相反，見「意見分歧」。[Katz]
- 領域新就得把 guardrail 加回來：Cursor 一路刪 prompt 與 guardrail，但 Grokbot（長期存活、管理一群 worker 的 coordinator bot）因任務領域新（簡報、訂旅遊、溝通頻率、acting vs asking、memory）反而要加回 prompt 與 guardrail (@08:00)。Data flywheel：harness 讓更難的任務可行，資料回到實驗室，模型內化能力，原本的補丁才能刪 (@06:01)。[Katz]
- Shim 管理：補模型壞行為的確定性 guardrail（例：使用者等太久時提醒 agent）集中登錄，每次觸發都記錄，有 bot 監看儀表板，shim 不再觸發時自動開 PR 清掉 (@16:00)；少對使用者暴露 harness 內部，降低 Hyrum's Law 的變更成本 (@14:00)。[Katz]
- Prompt 債：think step-by-step、verification rituals、thoroughness 加強語、scratchpad 指引在 frontier 模型上不再需要，還增加 token 成本；互相矛盾的規則在舊模型被默默忽略，新模型會被搞混 (@02:00)。可用 Claude Code 的 checkup prompt audit 或 Claude API prompt audit 掃 skills、tools、prompts 移除反模式 (@03:00)。許多應用落在成本與品質 Pareto frontier 之內，原因是舊 prompt、沒用 cache、effort 設定不當等小錯誤 (@01:01)。[L.Martin-Prompts]
- 自建 harness 的演進（Arize 的 Alex agent）：從 2023 年底 prototype 到 2026 年合併為單一 agent 按需載入 skills，全部重建都是 harness 程式碼，沒訓練模型也沒用 agent framework (@04:01)。模型選擇預設「夠快夠好」，時間花在 harness；有些介面（如 filter with AI）單次小模型呼叫即可，不需要 loop (@14:01)。撐過每次重建的六個決策：自家產品全程 tracing、數學與資料在程式碼（程式算聚合，模型推理與解釋，以 tool 暴露）、CI 中的 golden dataset、有明顯修法的錯誤直接修、streaming 與持久化、skills (@18:01)。[F.Ali]

## Agent loop 與控制流

- 最小 harness 骨架：prompt + 工具登錄 + 模型 + loop + 停止條件；工具 = 結構化 JSON 輸出 + switch 敘述。[Horthy-12F] [Kumar] [Miraje]
- Guardrails：max iterations（示範 6），max messages 觸發壓縮，harness 層級重試上限 (3)。GPT-4.1 fast reasoning 實測每次最多 8 到 12 次 tool call 後放棄；「耐心」可設成參數，難題轉給前沿模型，簡單題交給小模型。[Kumar] [Martinez]
- 確定性關卡優先於 prompt：用 TypeScript state machine 在 implementer，verifier，reviewer，closer 之間設 gate，未通過不能前進。"Enforce with code, not prompts"。[Nisi]
- Own your control flow (12-Factor)：自己決定 break，switch，summarize，LLM-as-judge；暫停/恢復用簡單 API，把 context 序列化進 DB 以 state id 恢復；工具呼叫與人類溝通統一（第一個 token 決定是 tool 或問人）。[Horthy-12F]
- Micro-agents：確定性 DAG 中嵌入 3 到 10 步的小 agent loop（部署機器人範例）。[Horthy-12F]
- 控制論式 loop（取代盲目 Ralph loop）：sensor (ast-grep, ESLint, grep) → setpoint → controller（確定性挑下一個小項） → actuator agent（搭配手寫 golden patterns skill） → 重新量測；一次只改一小塊，讓 PR 可讀；用排程 GitHub Action 一次跑一輪。[Mistele]
- Ralph loop：同一個 prompt 反覆餵給 CLI，每輪新 context；失敗要可預測。[Prabaker] [Mistele]
- Event-sourced harness：state + 同步 reducer + after-append hook；一切（串流 chunk，tool call，錯誤，circuit breaker）都是 append-only 事件；重啟時只重播 reducer，不重打 LLM。[Templestein]（部分）
- 長期目標：持續注入 continuation prompt 直到模型呼叫 update-goal 工具；目標要具體可驗證，不要寫長文。[Kundel]
- 子 agent 作法：spawn / send-input / wait / close 工具；背景 terminal 工具；子 agent 就是一般函式當工具，可把不相干工具分組。[Kundel] [Bhargava]
- 工具參數鎖定 (partial application)：先把目錄等參數綁死，模型看不到該參數，兼顧安全與自主。[Bhargava]
- Loop 三段：gather context → take action → verify。不要低估「怎麼找到 context」；需要規劃就插在前兩段之間（會增加延遲）；唯讀問題不必驗證，交給 agent 判斷，不硬性規定每一步。[Shihipar]
- 最笨的 Ralph：`while true` + `claude -p "實作下一個最重要的 ticket（TDD，做完 commit）"`，不預排依賴，讓模型每輪看剛完成的內容現場判斷。演進路線：同一 prompt 重複 → stop hook → 外部 while → 指向整份 ticket 清單。Claude Code `/loop` 是同一 session 的 cron（約 3 天要重啟），外部 while 則每輪新 session，逼資訊落到 repo。[Parsons]
- Ralph skill 要寫清楚：角色（接力賽的一棒：只做一個改動、丟掉 context、停止）、ticket 格式與狀態、crash 後復原規則（工作樹髒但測試通過 = 可能做完；測試失敗 = 丟棄）、停止條件（context 快滿或遇到不可逆動作就把進度寫回專案檔交給人）。[Parsons]
- Kanban 取代順序式 plan：每張 issue 標 AFK / human-in-the-loop 與 blocking 關係（形成 DAG），多個 agent 可同時領；用垂直切片 (tracer bullet) 而非 DB → API → UI 逐層切。Loop 腳本把 issue 檔與最近 5 個 commit 塞進 context，全部做完輸出結束訊號；先跑單次版觀察行為再放開成 loop。[Pocock]
- RPI：research（客觀找出系統怎麼運作與正確檔案）→ plan（確切步驟、檔名、code snippet、每步怎麼驗證）→ implement，階段之間做 intentional compaction；人審 research 與 plan，不只審 code。Agent 走偏時不要一路糾正到 context 用完，開新 context 重下任務並註明「別走那條路」。[Horthy-NV]
- 子 agent 只用來隔離 context（派去讀大量檔案，只回傳精簡結果），不要擬人化成前端、後端、QA 角色。[Horthy-NV] [Pocock] [Touil]
- Orchestrator / worker / validator（Factory Missions）：刻意 serial，因為平行 agent 會互踩改動、重複工作、做出不一致的架構決策；只在 feature 內對唯讀操作（搜尋、查 API、review）平行化。最長的 mission 跑了 16 天 (@08:01)。[Alvoeiro]
- Codex 的子 agent 實務：先 plan，再把檔案切成 slice 分給多個 subagent，最後主 agent 彙整（示範 20 個 reviewer 審 45 個檔，預設並行上限 6 (@38:03)）；每個 subagent 可各自設定 model、reasoning effort、sandbox mode、MCP、skills；用 stop hook 讓 agent 每回合結束後再推一輪以撐長任務。[Codex-MC]
- 規模化的三種型態：swarm（一個意圖扇出再收斂成一個 PR）、fleet（跨多 repo 扇出，如 CVE 修補）、events（由 webhook 觸發）。Runtime、orchestration、trigger 大致已解，缺的是 coordination：agent 之間接手、傳訊、確認自己完成了 SDLC 的哪一步，候選解法是 state machine、durable execution、CLI gateway。[Bichard]
- 把人工 SOP 變成 workflow：acpx（ACP 的 headless CLI）內含節點式 workflow，把 PR 處理（找意圖、評實作、解衝突、處理 review、讓 CI 通過）變成標準流程，人看到 PR 時機械工作已做完；review → refactor 迴圈只用來挖淺層 bug，不讓它做設計。[Solmaz]
- 遞迴 (RLM)：把完整 prompt 或整個 repo 當成 REPL 裡的變數，模型寫程式去探索、切片，需要時用 llm_query 遞迴委派子問題；設定最大步數與遞迴深度當預算；可包成 CLI 當 coding agent 的一個工具，用來翻超大語料。[Weitekamp] [Shashi]
- 人類是非同步 API：等人回覆不要寫成阻塞函式（服務一掛就丟進度），改用 durable execution 的 wait condition 暫停單一 workflow、用 signal 注入回覆、設 timeout；每筆工作拆成 child workflow，一個人類暫停只卡住一件事。[Warrick]
- Plan 由誰持有（Alex 的演進）：to-do list 當工具給模型，結果模型大半時間在更新清單（20 次以上 to-do 呼叫沒有實質工作），多次 tool call 後還會失焦；改為 harness 每次呼叫都把 plan 當 message 渲染，連 in-progress 標記後來也拿掉（未完成項依序就是下一步），現正測試完全不用 to-do tool，由 harness 管狀態與完成檢查 (@07:00)。[F.Ali]
- 結束 turn 用明確的 finish 呼叫：「沒有 tool call 的文字就是完成」在「這輪宣告步驟、下輪才呼叫」的模型上會壞；改為 finish 呼叫，plan 有未完成項時最多退回三次，迭代上限前一步發警告，最後 force finish。使用者可自選 provider，無法逐一測過，所以要對齊所有可能行為 (@08:01)。[F.Ali]
- 外層 DAG 保持確定性、節點內的 loop 保持自適應 (@16:00)（例：code review 做、檢查、依回饋修、夠好才放行，@05:30）；LangGraph 可管有環圖的 state (@04:00)。把 DAG state 注入 agent context，讓它知道自己在整體流程中的位置 (@10:00)。判斷哪個節點適合交給 agent：能否對照 policy 檢查、放進有界 loop、trace、fallback 到人類 (@13:00)。[Kormos]
- 單 agent 的三種失敗：agentic laziness（看過 35 個服務健康就推論其餘也沒事）、self-preferential bias、goal drift（compact 後「不要動 production」這類限制可能被遺失）(@72:01 到 @76:01)。fan-out 解法是每個 agent 只負責一小塊（50 個服務各一個），每個 reviewer 在獨立 context 做 adversarial review。代價是花費明顯高於單 agent，單 agent 30 秒能做完的事不適合；可分階段配模型與數量（scan 用 Haiku 每 ticker 兩個，review 用較強模型兩三個）(@27:01 到 @29:01)。上限約 1,000 個 agent（講者說 I think）(@46:01)，目前只支援一層巢狀 (@99:30)；子 agent 共享檔案系統但無目錄層級權限控管，只能靠 prompt 或 tool permissions 攔截 (@51:01)。[Avilla]

## Context engineering

- 預設假設 context 會被換出：設計時要持續刷新；自動 compaction 品質已提升 (GPT-5.4, server-side compaction)。[Lopopolo] [Kundel]
- 壓縮策略實測：單純截斷會失憶；LLM 摘要不一致且把重要性交給模型；有效作法是保留頭尾各約 100 字元，中段移入可檢索的 memory store（附 id，位置，預覽），去重，保留最新工具結果，不動 system prompt。[Delucia]
- 外部化 context：session 是 append-only 事件日誌，模型可回頭讀回被丟棄的片段（近似 Recursive Language Models），壓縮不再是破壞性。[L.Martin] [Bhat&He] [CMA-1] [L.Martin-Prompts]
- 延遲載入工具 (deferred tools + tool search)；skills 清單上限為 context 的 2%，超過就縮短描述；cache 友善排序。[Kundel]
- 以子 agent 承接大量資料的任務，主對話保持輕量。[Delucia] [Bhargava]
- 長對話要有測試：先載入 10 輪再測第 11 輪。[Delucia]
- 錯誤進 context 要壓縮：成功後清掉待處理錯誤，摘要不貼整段 stack trace。[Horthy-12F]
- 每次 loop 重新組裝 context（工具與 skills 依需求取用，向量索引檢索）。[Martinez]
- Context rot 實證：注意力隨 token 增加稀釋；資料全塞得進窗時加記憶體只增成本不增準度。[Martinez] [Druga]
- 檔案大小也是 harness 的一部分：用測試限制檔案不超過 350 行以節省 context。[Lopopolo]
- 讓程式碼「長得一致」（一種並發 helper，一種 ORM，一種 CI 腳本寫法），讓 token 更好預測。[Lopopolo]
- Smart / dumb zone 的實務數字：Horthy 以約 40% 為報酬遞減點（以 168k 視窗為例 (@06:01)），最難的問題壓在 60k 以下；Pocock 以約 100k 為上限，與視窗是 200k 還是 1M 無關（「1M 只是出貨更多 dumb zone」）。進入 dumb zone 的徵兆：agent 開始 hack 測試、把失敗歸咎於既有問題。[Horthy-NV] [LoopsDebate] [Pocock]
- 優化 context 的順序：正確性 > 完整性 > 大小，再看 trajectory（對話裡一直「出錯、被罵、再出錯」，模型會延續這個模式）。[Horthy-NV]
- 吃 context 的主要來源是測試 / build 輸出、檔案搜尋、MCP 倒出的大量 JSON 與 UUID；MCP 掛太多等於全程在 dumb zone。好的 compaction 內容是「與問題相關的確切檔案與行號」。[Horthy-NV]
- `/clear` vs compaction：Pocock 每次 `/clear` 回到同一個乾淨起點（Memento 式），不靠 compact；Horthy 做 intentional compaction，把 context 壓成 markdown、人審過再交給新 agent。兩者共通點是不依賴自動壓縮。[Pocock] [Horthy-NV]
- 常駐內容要極小（Pocock 看過 250k tokens 的常駐內容，一開場就在 dumb zone）。Push vs pull：CLAUDE.md 是 push，skill 是 pull；implementer 用 pull 讓它自取規範，reviewer 用 push 直接塞進 prompt。[Pocock]
- 不逐檔維護文件（離 code 越遠的文件越容易「說謊」），改成需要時派多個 subagent 對 codebase 垂直切片產生 research；做完的 PRD 與 plan 關掉，免得 doc rot 誤導之後的 agent。[Horthy-NV] [Pocock]
- 把 context 外部化到可程式化環境 (RLM)，是 grep、語意搜尋、摘要壓縮、記憶之外的另一條路。[Shashi] [Weitekamp]
- 非同步交給背景 agent 前，先同步寫長 spec / plan，把 context frontload。[Zakariasson]
- 像 agent 一樣思考：把自己放進它 10 到 20k tokens 的 context 實際走一遍任務，找出缺的資訊（computer use 範例缺螢幕解析度與建議動作，等於閉眼操作）。[Zhang-EA]
- 每次 tool call 的結果存成檔案、tool 只回傳路徑，長輸出也這樣處理，之後可搜尋覆查而不撐爆 context。大資料不要整份讀：給起始片段（如前 10 列），讓 agent 像人一樣導覽、grep、維護 scratch pad。[Shihipar]
- Server-side 狀態：用 interaction ID 帶回 context，免去自行管理 thought signatures，也避免多一個空白就 cache miss。[Leo]
- 為 prompt prefix cache 保持對話穩定：不重建過往 context，新增的 prompt / tool / context 要有界且確定，transcript bytes 不變，只有 compaction 可以改寫歷史；穩定 prompt 的變更延到下個 session 才生效。[OpenClaw-repo]
- Context 修剪的 bug 很難抓：Claude Code 為了配合 prompt cache 過期，在閒置 session 清除舊 thinking，本應只做一次卻變成每回合都清，agent 因此健忘、重複，還造成 cache miss 與用量暴增。修剪邏輯要測「閒置後恢復」「工具執行中途追問」這類邊界情況。[Anthropic-PM]
- 大量 tool 輸出（如 log）會撐爆 context，造成 overflow、hallucination、recall 下降；加大視窗不是解法，注意力曲線只記得開頭和結尾（lost in the middle）(@02:01)。技巧分四類：externalize（搬到外部儲存，用 memory pointer）、select、compress、isolate (@03:00)。Conversation manager 有 sliding window、summarization、兩者結合三種（示範摘要比例 50%、保留最近 4 則）(@04:01)。Anti-patterns：context stuffing、天真的 summarization（可能丟掉答案需要的資訊）、context pollution (@13:00)。Multi-agent swarm 共享整個 context 等於把垃圾灌給其他 agent，改在 agent 間只傳 memory pointer (@10:00)。[Leone]
- Trajectory 超過視窗時，harness 要求模型先寫 checkpoint 再丟掉被取代的內容，歷史有固定 token 預算 (@11:01)。[F.Ali]
- Sub agent 不是萬靈丹：每個 sub agent 仍需完整 context，環境 token 與延遲都重，所以要預建索引避免重複處理文件 (@07:00)。企業文件搜尋上線要考慮多租戶、從 Google Drive / SharePoint 抓權限 metadata 而不整批重索引、資料新鮮度 (@15:01)。[G.He]
- Context 太多會 overexplore（產生不存在的假設），太少會 underexplore，telemetry 又近乎無限，所以重點是「解題所需的精確 context 量」而非選哪種 RAG 實作 (@09:02, @13:01)。[Krovvidi]

## 工具 (Tools) 與 Skills

### 工具

- 工具設計：工具輸出就是 JSON，給模型熟悉的形狀；原生工具如 apply_patch，shell，ripgrep；以程式碼執行（持久 REPL + Playwright JS）取代一次一動作的 computer use。[Kundel]
- 範例：browser session 用純 Playwright 而非 MCP。[Kumar]
- MCP 負責 agent 對外，ACP 負責 client 對 harness：JSON-RPC，session，權限請求，可擴充方法；client，harness，tools，model 四者可分別放在不同位置。[Hancock]
- Code Mode（[Pai]，部分）：harness 的重點不只是產生程式碼，還要有一個安全的執行空間，並只在其中暴露受控的能力。
- Gateway：每個沙箱一個 MCP gateway 端點，集中控制工具/資源/prompt，harness 可替換。[Clark]
- 工具的問題：描述模糊、模型卡住時無法修改、永遠佔用 context。改法是寫成 skill 裡的 script（Claude 一直重寫同一段套投影片樣式的 Python，就讓它存進 skill，之後直接執行）。[Zhang&Murag]
- ACP 也可以讓 agent 呼叫另一個 agent，取代 PTY scraping 與「Opus 轉述給 Codex」的傳話遊戲。[Solmaz]
- Tools 與 prompt 是兩個主要設計決策：請模型檢查 tool description 與參數、system prompt 有無歧義，並把整段 trajectory 丟給它問「為什麼在這裡這樣做、怎樣能幫你做得更好」。[Zhang-EA]
- Codex plugin = skills + apps（外部服務連線）+ MCP 打包；雲端任務不載入本地 skills，因為 sandbox 無法判斷 skill 夾帶的腳本是否可信。[Codex-MC]
- Tools、bash、code generation 三選一的取捨：tools 結構化可靠但吃 context、難組合；bash 可組合、省 context 但要花時間探索；code gen 最能組合但最慢且需要 lint / 編譯。不可逆或需要使用者核可的原子動作（寫檔、寄信）做成專用 tool，可組合的動作（搜尋、GitHub、lint、memory）交給 bash，動態邏輯與資料分析用 code gen。[Shihipar]
- 自訂 CLI 放進檔案系統並在 system prompt 告知，每個 script 都支援 `--help`，讓模型逐層探索子指令（progressive disclosure）；資料轉成模型熟悉的介面（CSV 轉 SQLite 用 SQL 查）。[Shihipar]

### Skills 的實作

- 最小支援 = skill registry (name, description, path) + system prompt + 讀檔工具；progressive disclosure：平時只放 name/description。[Miraje] [Schmid-Evals]
- 描述是路由訊號：用使用者的措辭與 trigger words，彼此要有區別，寫 negative case；50% 失敗來自 skill 沒被觸發。[Miraje] [Schmid-Evals]
- 依「使用者意圖」切分，不依資料模型。[Miraje]
- SKILL.md 小於 500 行；人寫的優於 AI 生成；移除 no-op 指示；能寫成腳本就別寫成 skill。[Schmid-Evals]
- 不要把文件整份轉成 skill：10，000 行自動生成 skill 使任務正確率 97% 掉到 77%；改為 553 行手寫 "gotchas" 後 eval 時間 68 分降到 6 分。[Nisi]
- Skill 的類型：capability（模型進步後可退役）與 preference（長期保留並用 eval 保護）。[Schmid-Evals]
- 超過 10 個 skill 要檢索/embedding 做 shortlist；超過 100 個要治理（admission，ownership，boundaries，lifecycle/semver，定期審計）。[Miraje]
- Skill 當作 harness 的延伸而不是打包的 prompt：子 agent 對立審查，隨機種子腳本，stdout 輸出指示，hooks，記憶（存在 repo 的忽略資料夾），針對最弱模型設計。[Bakaus]（部分）
- 注意跨 harness 差異（如 Codex 需要使用者明確授權才會開 sub-agent）。[Bakaus]
- 在 harness 內放入使用者自訂 agent 檔 (AGENTS.md + skills) 而不是寫 Python 工具；以檔案擴充能力。[Schmid-NoCode]
- Skill 就是資料夾（SKILL.md + 其他檔案），可用 Git 版本管理；progressive disclosure 讓同時掛數百個。MCP 負責連接，skills 負責專業；用 skill creator 讓 Claude 把學到的程序寫成 skill，等於程序性記憶。[Zhang&Murag]
- 組織級治理：skills 照微服務原則設計（reusable、modular、discoverable、portable、specialized、composable）。不治理的後果與沒有 service catalog 的微服務一樣：重複造輪、品質退化、沒有 owner、安全缺口。集中式平台需要 catalog + 可搜尋的 MCP + 拉到本機的 CLI + 依賴 + 版本與生命週期 + 存取控制 + eval 與觀測，並由 architect、eng、infra、cyber leads 分領域擁有；先有治理再開 auto-evolving。可與 [Miraje] 對照。[Touil]
- 公開 skills 可能夾帶 prompt injection 與可執行腳本，需要安全檢查 pipeline。[Touil] [Codex-MC]
- 一整套小 skill 組成的流程：grill-me（一次一題、每題附推薦答案，可能 40 到 100 題）→ write-a-PRD（含 out-of-scope，保存被否決的決策）→ prd-to-issues → TDD → improve-codebase-architecture，依自己的失敗模式調整。[Pocock]
- Rules 不要一次裝滿，看到 agent 偏離時才補，像 SOP。[Zakariasson]
- Skill 的版本化與分享仍未解：GitHub 對非工程師太重，plugin marketplace 版本化的是 plugin 而不是 skill。[Parsons]
- SKILL.md 刪減有數據：frontier 模型對 skill 內容的通用理解約 70%，對確切 key、參數、數值、步驟只有約 22%（寬鬆與嚴格兩種評分），所以保留精確細節、刪掉通用概念，但這只是優化起點，刪減後仍要跑 evals 驗證 (@12:00)；較小模型已知比例較低，部分 skill 本來就是方向性的不必全刪 (@10:00, @10:30)。29 個 skill 約 14 美元（Haiku 作答、Sonnet 當 judge）(@09:00)。[Petrov]
- Skill 蒸餾（Voyager 式 skill library）：成功且有意義的 run，把 trace 交給 frontier 模型蒸餾成 skill；失敗 run 訊號更豐富，能補上缺少的 guardrail 與邊界情況 (@11:30)。長任務下初始軌跡決定成敗，skill 用來縮小搜尋空間 (@03:30)；最值得寫的是沒人想重新發現的儀式（回滾腳本與 feature flag 順序、對流失客戶的措辭）(@04:30)。論點是 frontier 智慧是租來的，把程序持久化成自己的資產也是不換模型就降成本的方法 (@14:30)。單一案例，講者為 MCP gateway 廠商。[Wilinski]
- 使用量數據：控制其他因素下，每週 30 次以上 skill 使用帶來約 30% 的 PR 產出提升，效果大於換模型；同一人換模型家族、Cursor 換 Claude Code、autocomplete 換 agentic 模式，PR 產出變化在統計上都不明顯 (@07:10, @08:02)。9 月時約半數工程師週幾乎沒用 skills，只有 12% 達到高使用量。講者公司販售量測工具；同一份資料的其他產出數據見 [productivity-evidence.md](productivity-evidence.md)。[Arcolano]

## 驗證，Evaluator 與品質關卡

- 不要讓同一個 context 自評：獨立 verifier（獨立 context，有 rubric）與 builder 組成迴圈。Claude Code 的 `goal`，Managed Agents 的 `outcomes` 即此概念。[L.Martin] [Prabaker] [Bakaus]
- Planner / Generator / Evaluator（GAN 式）：planner 只寫高層 spec（細節錯誤會級聯放大）；generator 與 evaluator 先協商 sprint contract（何謂完成，可測）；evaluator 要真的操作應用（Playwright，試玩）。卡住時整個丟掉重來而不是持續補丁。代價：慢且貴（範例約 US$200，6 小時）。[Prabaker]
- 確定性驗證：讀 tool-call 歷史判斷 agent 有沒有說謊（點了按鈕不代表成功，登入失敗要回報失敗）。[Kumar]
- 防作弊：agent 會 touch 一個標記檔假裝測過，改為把真實測試輸出做 SHA-256 存入並驗證；要求非程式證據（Playwright 錄影前後對照）；原則是讓做真的比說謊更容易。[Nisi]
- 靜態規則轉成 prompt：自訂 lint 與結構測試（package 隱私，層級依賴，zod schema 去重，fetch 必須帶 timeout 與 retry），且錯誤訊息要寫成補救指示，這是「在對的時間注入指示」。[Lopopolo]
- 各人設（前端架構，可靠性，擴展性）各建一個 review agent，每次 push 在 CI 跑，依文件回報 P2 以上阻擋項。[Lopopolo]
- Hooks：在每次編輯觸發 lint 並阻擋寫入，而不是事後抱怨。「若關卡可以被跳過，就會被跳過。」[Bakaus]
- 規劃勝於事後審查：產品審查 → 系統架構 → program design（型別，簽名，call graph） → 垂直切片；30 分鐘對齊省數小時審查。[Horthy-SF]
- 讓 loop 的輸出小而可讀，一個 loop 最多一個 PR 在審，回饋寫進受版控的 feedback 檔。[Mistele]
- 人工介入點：最後一哩（部署到 staging 前）才交人，並且看「意圖與規格」而非只看 diff。[CastAI]
- Hook 當驗證掛載點：agent 宣稱完成（session 結束）時自動跑外部驗證程式，失敗就回饋要求重做直到通過；同樣的關卡可放在 commit 前、multi-agent 中、非同步 agent。Pre-commit hook 輸出一段 prompt 當 back pressure，條件沒滿足前讓 loop 無法收斂。[Sheikh] [LoopsDebate]
- Validation contract：規劃階段、寫任何 code 之前先定義「完成」，複雜專案可達數百條 assertion，每個 feature 對應一或多條。理由：實作後才寫的測試只會確認既有決策，抓不到 bug。[Alvoeiro]
- 兩種 validator：scrutiny（test、type check、lint，加上每個 feature 一個 code review agent）與 user testing（像 QA 一樣實際操作應用）。Validator 用全新 context、沒看過這段程式碼，設計上就是對抗式；驗證幾乎不會一次通過，會產生 follow-up feature。可用不同供應商的模型驗證，避開同源訓練偏誤。[Alvoeiro]
- 確定性驗證優先（型別、linter、模擬測試、靜態分析）：非確定性驗證加越多越貴也越不可靠。Huntley 個人主張用 Haskell、Rust 這類型別強的語言更適合 loop。[LoopsDebate]
- Feedback loop 的品質是 agent 產出的天花板；要求 TDD red-green-refactor（較難作弊，也累積好測試）；review 前先清 context，讓 reviewer 在 smart zone 運作；人工 review 先看測試再看程式。[Pocock]
- 自動 code review 當第一關：全新 thread、專用 review prompt、以整個 repo 為脈絡找出沒改到的模組的二階影響；OpenAI 宣稱內部所有 PR 預設先過 Codex review。[Codex-MC]
- Code review 的核心是 mental alignment（讓團隊知道 codebase 怎麼變、為什麼），審 plan 能提早發現問題；PR 附上 agent 的 thread 與驗證步驟。[Horthy-NV]
- 讓系統可驗證：agent 能自己啟動專案並自測（Playwright e2e），UI 變更錄影回傳給人看。Agentic code owner 先評估 PR 風險，低風險自動核准、高風險找改過該處的人（約 80% 正確、20% 造成阻塞 (@27:01)）。[Zakariasson]
- 把「測試通過不夠，要驗證實際行為」寫進 skill；同一個 context 自我驗證會自我肯定，交給只帶少量 context 的 sub-agent。[Parsons]
- 驗證不只放在最後：有規則就在中途丟 error 並附回饋（Claude Code 在 agent 寫入「還沒讀過的檔案」時直接報錯要它先讀），模型會讀 error 自己調整；用 hook 偵測「沒寫 script 查資料就直接回答」並要求實際去讀。[Shihipar]
- 不靠真實 API 的回歸測試：錄製 session 快照（model 或使用者看得到的變更都要更新快照，無 key 即可重放）[DeepSeek-H]；以 mock 的模型服務腳本化回應、子程序啟動 CLI 跑 parity 情境 [ClawCode]。可機械檢查的不變式寫成 CI gate（如每檔 100% coverage、重複程式碼偵測）。[DeepSeek-H]
- 「status comes from records, not model prose」：要求截圖、影片、測試結果、smoke test 等憑證 (@11:45)。示範：UI 顯示報名成功但重新整理後資料消失（只驗 UI 沒驗持久化），驗證流程是 join 一個 email、查 storage 發現是空的 (@25:00)；這個結果讓 agent 知道還沒完成，之後的修復與留作回歸測試是講者口述，demo 中沒有實際跑 (@31:00, @36:00)。成功截圖不等於證明，要確認真的從頭走過 UI 可到達的路徑 (@31:15)。保留每次 run 的 receipts 夜間彙整失敗讓 agent 發 PR，PR 附操作錄影 (@50:30)。給目標與確認指令而不是路徑，過度規定可能降低表現 (@33:30)。[Nisi-Proser]
- 三種職責三種負責者：scripts 證明可證明的事實、agent 判斷需要 context 的事、人負責只有人該決定的事；source of truth 能回答的問題不交給 AI，也同時壓低成本 (@03:00)。要求 agent 誠實承認搜尋範圍：沒找到不等於不存在，只能說「在搜尋過的地方沒找到」，不得宣告 all clear (@14:02)；PR 描述的意圖不能抵銷程式碼中的發現 (@10:30)。講者自承設計錯誤：兩層檢查獨立平行觸發，彼此看不到對方結果或故障，一邊故障就等人、沒有 fallback；提案（未實作）改為單一入口 classifier (@24:01)；分層 merge 條件見 [coding-agent-ci.md](coding-agent-ci.md)，人工回饋迴圈見 [agent-evals.md](agent-evals.md)。[Joshi]
- Production 排障需要因果證據鏈：模型為了取悅使用者會給連貫但非因果的答案，被追問還會順著同意 (@10:00)；root cause 建不出證據鏈就以低信心輸出並指向別的方向 (@14:00)，同時顯示被排除的假設（demo 中排除了同時間的 GCP outage）(@18:00)。講者為廠商。[Krovvidi]
- 讓不確定性可見：執行期錯誤是安靜的（跑 100 份文件漏掉第 30 頁的掃描，沒有 segfault），Extract 輸出 confidence score 與 bounding box，並做工具回餵模型優化 schema (@09:01)。把 agent 的信心與理由輸出成 MCP 的 prompt guidance，每次建立新東西都向使用者解釋做了什麼與為什麼 (@10:00)。核心問題是「agent 錯了誰付代價」：auto mode 出錯看不到，user-first 讓 agent 只剩聊天機器人，講者主張 agent 能力有範圍且人可驗證 (@02:01)。[Arya]

## 記憶 (Memory)

- 觀念：記憶是 write / manage / read 的控制迴圈，不是資料庫；recall policy 要當一級指標。[Druga]
- 實驗：資料能完全放進 context 時記憶沒有好處且更貴；長程（答案在第 124 步，問題在第 500 步）時，排序過的 decisions ledger 勝過向量 RAG 與「是否需要記憶」的 gating，而且更便宜；即使給 oracle 正確記憶模型也未必採用。[Druga]
- 不要預先規定記憶 schema，讓模型自己組織 (bitter lesson)；檔案或 DB 皆可，重點是簡單可程式化。[L.Martin]
- 同步寫入 (in-band) 會寫出錯誤或區域最佳的記憶，需要離線 "dreaming" 整理（Pokemon 例：原始記憶 5 次全部掉進陷阱，dreaming 後修正）。需用 eval 驗證離線算力值得。Managed Agents 的 Dreaming（research preview）對一個 memory store 與過去 30 天的 session transcript，用多個 sub agent 檢查 memory 漏記、session 遇到的問題與重複問題後更新 memory (@03:00)。[L.Martin] [Bhat&He] [CMA-3]
- 記憶種類：短期，長期，共享，episodic，procedural，semantic；另有關係型（entity graph，以走訪表達關聯）可與短期、長期組合 (@06:01)。[Martinez] [Malcolm] [Leone]
- 檔案與資料庫：檔案貼近模型習慣且附加便宜，但沒有交易一致性（平行 agent 要用 git worktree），沒有混合/向量搜尋與備份；建議混合式（短期放檔案，長期偏好升級進 DB）。這是 Oracle 的立場，其他講者 (L.Martin) 則主張重點是通用基底。[Martinez] [Malcolm] [L.Martin]
- Skill promotion：把耗時數小時的工作流蒸餾成更好的 SKILL.md，再退役舊版。[Martinez]
- Retro agent：讀 transcript (JSONL) 找 doom loop 與重複工具呼叫，更新通用與框架專屬 markdown 記憶。[Nisi]
- 語意層 (Umwelt)：把「沒說出口的」組織知識寫下來。[Martinez]
- 團隊共享記憶：跨時區共享 context（Git 只記錄程式碼，不記錄意圖）。[Malcolm]
- 檔案式三層記憶：raw（不可變原始資料）、index.yaml（入口，記每個來源的連結、作者、摘要）、wiki（LLM 產生的 concepts、entities、comparisons 衍生頁）。查詢順序 index → 來源摘要 → 衍生頁 → 最後才讀 raw；每次提問都留下痕跡，讓 wiki 持續演化。個人規模不需要向量 DB 或知識圖譜。[Iusztin&Bouchard]
- Skills 是程序性記憶：只記程序、不記一切；標準化格式讓未來的模型版本也能用。[Zhang&Murag]
- Continual learning：掃過去的 transcript，把使用者的糾正與偏好抽成 rules；merge 後 PR 上的人類 review comment 是高訊號資料。可與 [Nisi] 的 retro agent 對照。[Zakariasson]
- 共享記憶的存取控制仍是未解問題；先用 markdown，Notion 之類內容轉成 markdown 讓 agent 直接讀，不走 MCP。[LoopsDebate]
- 長期 memory 在實務中的收斂：試過 vector retrieval、episodic / semantic store、temporal knowledge graph，最後是每個使用者一個 markdown 檔（上限 8,000 字元），每個完整請求都載入，由 session 結束後的背景工作寫入。優點是小、精確、不撐爆 context、人工 labeler 可審查，單一寫入點也容易確保不混入其他使用者資料 (@12:00)。與 [Druga] [Iusztin&Bouchard] 的「小而簡單」同向。[F.Ali]
- Observability 只告訴你發生什麼，trace 要轉成 durable context 才算 memory，否則今天的錯會持續重現 (@04:00)。講者主張多數可見改善來自 procedural memory（金融 agent 語氣從建議式滑到指示式，靠更新規則解決）(@05:00)。working memory（本次 run 的 scratchpad、工具結果）與 long-term 要分開，迴圈簡化成 capture、analyze、update (@06:30, @08:00)。踩雷：長時間背景 agent 更新 memory 後，若 runtime state 或快取沒重新讀取，行為不會改變，要確認哪些內容被 cache、更新何時對後續 run 可見 (@13:40)。[Broekhuizen]

## 沙箱，權限與安全

- 本章內容已拆到 [agent-security.md](agent-security.md)。
- 憑證：沙箱內憑證數量應為零；在邊界注入（network proxy 於外送請求時加 token；vault 僅在工具執行時解密）。[Clark] [Bhat&He] [Schmid-NoCode] [Jain]
- Containment 優先於 human-in-the-loop：使用者約核准 93% 的 permission prompt，審核疲勞讓人工把關不可靠。[Anthropic-Contain]

## 狀態，可靠性與可觀測

- 「模型提議，harness 提交，收據證明」：transcript 不是證據，收據記錄突變，使用的授權，以及是否真的抵達使用者。[Govindarajan]
- 五種失敗：狀態未持久化（每個事實需有單一 owner 與可重現路徑）；多寫入者覆蓋（每個狀態邊界一條有序提交路徑，讀可平行）；工具無期限（deadline，watchdog，取消）；核准漂移；內部成功不等於使用者可見成功。[Govindarajan]
- Run receipt audit 五問：什麼觸發? 繼承什麼狀態? 用了什麼授權? 執行了什麼? 留下什麼證據?[Govindarajan]
- Session 事件日誌四狀態：idle，running，rescheduling，terminated；持久化可觀測並支援恢復。[Bhat&He]
- Idempotency key，鎖，排序，事件去重。[Govindarajan]
- 觀測先於一切：「observability 與 evals 要最先考慮」；觀測也是持續改進的基底。[Chambers] [Trivedy]
- 長程 loop 的耐久性：串流中斷後可續跑，持久化 thread，queue/steer/interrupt。[Bhagwat]
- 傳輸優化：當推論達 1000 token/s，瓶頸變成網路；websocket 模式只傳增量。[Kundel]
- 元件各自擴展而非全塞進一個容器（memory，loop，identity 獨立擴展）。[Chambers]
- 透過標準協定讓前端可替換 (ACP)。[Hancock]
- Durable execution 的切法：agent loop 放 workflow（確定性），模型與工具呼叫放 activity（非確定性）；worker 被殺掉後重播事件日誌（不重做）回到上次位置。可與 [Templestein] 的 event-sourced harness 對照。[Warrick]
- 結構化 handoff：worker 交接時填「完成了什麼、沒完成什麼、跑了哪些指令與 exit code、發現的問題」，讓錯誤在 milestone 邊界被抓出來，而不是「希望 agent 記得」。[Alvoeiro]
- 保存完整 trajectory（planning、code、observation、sub-call、budget）成 JSONL，可接任何 observability 平台。[Shashi]
- 監看背景 agent：跑了多久、有沒有碰任何檔案、有沒有原地打轉 (loop detection)。長任務要有 mission control 畫面：進度、預算消耗、目前 worker、handoff 摘要。[Zakariasson] [Alvoeiro]
- Telemetry in the loop：harness 知道哪裡壞了、花了多少，就能自我修正後繼續。[Koc]
- Model-visible ⟺ logged：任何進入 model request 的內容都必須能從 session log 重建，新增 model 可見的輸入就要新增 session event；已發佈的 session 格式只能加新版本，不得覆寫或刪除。可與 [Templestein] [Warrick] 的事件日誌對照。[DeepSeek-H]
- 每項狀態只有一個 owner，caller 只消費 owner 記錄的事實，快取與 projection 由 owner 衍生並有明確失效週期；SQLite 存取走 worker thread（多讀、單一寫入 broker），不在主執行緒做。對應 [Govindarajan] 的單一寫入者。[OpenClaw-repo]
- Brain / hands / session 解耦：第一版把 session log、harness、sandbox 塞同一個容器，變成 pet（壞了手工救；掉封包與容器死亡症狀相似難 debug；客戶資料在容器內無法查；連客戶 VPC 內的 MCP 要 network peering）(@05:00 到 @07:01)。改版為 session（append-only 事件 log）、brain（harness + Claude）、hands（sandbox、MCP tool call，隨需建立、用完即丟）：sandbox 掛了對 Claude 只是一次失敗的 tool call，harness 掛了換新的並從最後一個事件接續，只有 session log 需要保護 (@08:01)。不必等 sandbox 啟動就能先開始 inference，time to first token 降約 90%（講者口述）(@10:00)。[CMA-1]
- Sub agent 是分散式系統：orchestrator + workers + 共享可變狀態 + 併發結果合併，失敗模式有 partial failure、dirty read、unbounded fanout、retry 重跑整個任務連 side effect (@01:01)。Sub agent 做一半不丟 exception，而是回型別與成功相同的流暢文字，orchestrator 讀得到結論，讀不到背後做了多少工 (@04:01)。逾時只是「懷疑」不是事實：記成 unknown 並保留真正原因，例如首次啟動要下載的 server 被 30 秒 timeout 誤判（給 initialize 獨立 timeout）、server 崩潰時 timeout 覆蓋 exit code (@05:00)。讓失敗成為值：回傳結構化狀態（做了什麼、沒做什麼、證據、side effects），「檢查後沒問題」和「無法檢查」要分開 (@06:01)。[Konda]
- SAFE 一致性模型（S、A、F、E 四項，此處只收 S 與 F）：S source facts，每個傳遞的 fact 帶來源、版本、as-of 時間，決策只讀夠新的（例：資料 9:05、9:06 讀、9:07 決策，限制 5 分鐘則通過；9:15 第二次決策超限就拒絕並要求重讀）(@10:00 到 @12:00)。F fanout budgets：多 session 同時 npx cold start 搶同一 package cache 全部失敗，cold start 閘門預設一次兩個、等待上限 15 秒，容量要在啟動前預留，否則是 check-then-act race；下游 rate limit 可能只以一句文字出現，orchestrator 沒讀就會繼續開 worker (@17:00)。代價：不保證事實為真、不給 exactly-once、不 rollback、無跨 worker 全域順序，假設單一 orchestrator (@20:01)。[Konda]

## 長時間，非同步與組織級 harness

- 長時間運行模式：initializer 產出 feature_list.json（用 JSON 較不易被模型覆寫），progress 檔，git；每輪新 context → 看 progress/git log → 做一項 → 驗證 → commit → 標記通過。[Prabaker]
- 以檔案系統共享狀態而非依賴 context；留下 breadcrumb（試過什麼，發現什麼 bug）給下一個模型或人。[Prabaker]
- 雲端 harness：Slack 多人互動，雲端沙箱以增加平行度，產出是 PR；Claw：外部事件監聽，heartbeat，多通道，持久記憶，自我改進。[Bhagwat]
- 組織級 harness（多人共用，有自己的身分與憑證，主動通知）。[L.Martin]
- Teleport（關筆電後遠端沙箱繼續跑）與 Studio（團隊看板審查 plan）；Ferment（里程碑，自評分，部署到 staging）。[CastAI]
- 工作節奏：「每次我需要打 continue 都是 harness 的失敗」；技能說明讓 agent 做到測試綠燈為止。[Lopopolo]
- 時間地平線：METR 曲線（約 1 小時到約 12 小時）與 harness 共演化。[Prabaker] [L.Martin]
- 自建背景 agent 基礎設施的例子：Stripe Minions（驅動數千個 PR）、Ramp Inspect。GitHub、Linear 這類給人用的工具當 agent 協調層太嘈雜，人難以判斷何時介入。[Bichard]
- 開源專案規模：OpenClaw 每天 300 到 500 個 PR (@07:01)，把低品質 PR 當成「某處壞掉」的使用者回饋分類保存，而不是直接丟掉。[Solmaz]
- 事件觸發：Linear 一建 ticket 就啟動 cloud agent；feature flag 100% 推出兩週後自動開 issue 並派 agent 移除；Slack 訊息由 automation 分流、找重複、簡單的直接修。[Zakariasson]
- 個人級的多種 loop：worker loop（從專案檔挑下一步）、morning loop（早上 6 點簡報）、15 分鐘 heartbeat（查行事曆、傳訊息）。人永遠是審查瓶頸（隔夜產出 30 件待審）。[Parsons]
- 瓶頸理論：先修最大的瓶頸（審查、發佈），否則 AI 反而讓部分團隊變慢；協調問題可能其實是團隊太大。AI 產出變 2 到 3 倍後，團隊協作方式必須重整（Horthy 的三人團隊花了八週）。[Parsons] [Horthy-NV]
- 歸責：Git 一個 commit 只有一位 signer，agent 的行為最終必須能歸因到人。[LoopsDebate]
- AGENTS.md 當成 agent 的工作守則：分層、scoped AGENTS.md、程式碼地圖與 anti-patterns，並明定 agent 與人類維護者的授權邊界（例：自動化流程不得合併或關閉 PR / issue，不得直接 push main）。[OpenClaw-repo] [ClawCode]
- Software factory 的三個指標有順序：autonomy（要多少人類修正）、automation（能跑多久、要多少審查與信任才接受）、final quality；可以高 autonomy 低 automation，例如 agent 常一次做對你仍逐行審 (@03:00 到 @04:01)。三層中先做 control plane：所有工作從 issue tracker 開始，交給 sandbox 內的 headless agent，agent 開 PR，工程師在 PR 留言，讓所有接觸點可被後續工具讀取 (@11:00)；多數時間花在 improvement loops：每日或每週掃 codebase、常見開發 playbook、辨識重複任務並自動化、把學到的修正灌回 skill (@14:00)。難處：舊最佳實務幾週後可能變反模式、是計畫外工作與出貨競爭、所需資訊藏在本機 agent log 或個人腦中 (@09:01)。講者公司後段有產品介紹。[Knox]
- 顧問觀點的流程重設計：單純在原流程加工具沒用；迭代從兩週 sprint 轉向一到兩天的 Kanban 式，agent 夜間跑、人隔天驗證再重跑 (@05:01)。人類 review 逐步放手：先決定哪裡要人看，信心夠了就拿掉那一關 (@06:01)。build 與 test 壓縮後瓶頸移到上游需求撰寫與下游 release 頻率，橫向的合規、風險、設計規範需編碼給 agent (@14:00)。為 agent 準備 golden examples 而非 codebase 平均水準 (@11:30)。Skills 的問題是 curation：寫 PRD 一件事就能下載約 1,700 個 skills，造成選擇癱瘓 (@10:01)。講者無公開數據來源與方法。[Harrysson]
- 先做最小本機驗證再上線（Duolingo 寫測試 agent）：一個 Claude Code command 當 orchestrator（跑 Xcode coverage、選檔腳本、兩個 sub-agent 寫測試與開 PR），兩批共 57 個 PR 合併 27 個（約 50%），目的是觀察失敗模式 (@04:01)。對策：XCTest 與 Swift Testing 混用（寫明何時用哪個）、巨大 singleton 難 mock（改 protocol 版並加 lint 規則強制）、flaky 的 concurrency 測試（規則與範例寫進 testing skill），改善 codebase 同時讓人與 agent 都更好測 (@04:30)。上線用 Temporal：child workflow 平行 fan-out、retry / timeout、idempotency，共享狀態放 S3 (@03:01)。選檔腳本依「agent 寫得好測試的信心」打分（view model、repository、data source 加 2.5 倍，legacy 降權，大檔扣分，UI 先跳過）(@06:00)；CI 端的 PR 狀態機與防作弊見 [coding-agent-ci.md](coding-agent-ci.md)。[Agrawal]

## 成本與模型選擇

- 以「每個任務成本」而非「每 token 成本」比較模型（同品質）：例如表面便宜的模型每任務可能更貴。Outcome-aware harness 可依任務自動挑模型並隨新模型上市切換；內部 3 個月 2.5 倍節省且 token 用量增加 1.5 倍。[CastAI]
- 先用前沿模型證明可行，再用 trace 指引做 harness engineering 讓開源模型逼近；之後才考慮 fine-tune，再回頭做 harness engineering；高用量時考慮硬體成本取代 token 成本。[Trivedy]
- 問題難度路由：難的送前沿，簡單的給小模型。[Martinez]
- 不擁有模型權重的 harness 建置者，在與模型一起 RL 訓練的第一方 harness 面前處於劣勢；選型時要把這點算進去。[Horthy-SF]
- 不同角色用不同模型：規劃用慢而謹慎的推理、實作用快速寫碼、驗證用精準遵循指令的模型；Pocock 用 Sonnet 實作、Opus 審查；Codex 的探索 subagent 用快速小模型並設 read-only。[Alvoeiro] [Pocock] [Codex-MC]
- 結構可以補償模型：validation contract 與 milestone checkpoint 讓非前沿、甚至 open-weight 模型也能跑完 mission；guardrails 越多越能改用小模型（Sheikh 的推論，未實測）。[Alvoeiro] [Sheikh]
- 「就燒 token，優化自己的時間」[Parsons] [Horthy-NV]；反方：失敗不會靜默，而是從帳單上大聲出現，疊 loop 不能用 token 買品質 [LoopsDebate]。
- Agent 缺乏 workflow 那樣的成本 / 延遲控制，需要能以時間、金錢、tokens 定義並強制執行的 budget（開放問題）。[Zhang-EA]
- 換模型不要當最早採用者，等幾週看是否經得起考驗；同一個模型在不同 harness 上表現不同，所以 eval 同時在測模型、harness 與題目品質。[Khan]
- 預設 reasoning effort 是產品層的取捨：Claude Code 曾把預設由 high 降到 medium 換取延遲與用量，使用者感受到智能下降後改回；使用者寧可預設高、簡單任務再自行調低，改預設時要在 UI 清楚顯示。[Anthropic-PM]
- 成本結構的重點在 2026 已從 output token 轉到每次呼叫的 input token 數、cache hit 比例與每任務步數 (@12:00)。案例（AA briefcase 知識工作 benchmark）：Opus 平均每任務約 21 美元，一個任務 165 步，單次 call 約 13 美分，answer token 只佔很小一部分（字幕數字零碎，可能有誤）(@11:00)。同一模型 Opus 5.5 從 low 約 1 美元到 max 約 21 美元每任務，因為 reasoning effort 也改變步數，reasoning token 進訊息歷史累積成後續 input (@14:00)。不同模型每任務成本差數個數量級（頂級超過 5 美元，便宜模型 5 美分以下），開放權重落後最強專有模型約 3 到 9 個月 (@07:00)；同一智慧等級的成本約一年降 10 倍，決策要預期價格快速變動 (@09:30)。任務分兩類：unlimited intelligence（更聰明總是更好）要問預算；limited intelligence（查上月訂閱花費，便宜與昂貴模型答案都是 80 美元）要找達到天花板的最便宜方案 (@17:00)。數據來自講者自家 benchmark。[Cameron]
- 模型選型：先看通用 Pareto 前緣縮小候選，原型階段用短名單自己測，上線前把短名單（至多約 5 個模型）拿去跑自建 benchmark；通用排名不一定符合自己的任務（例：Gemini 與 Anthropic 系列在複雜試算表任務上都強）(@05:00, @18:00)。[Cameron]
- Effort 原則：先試較強模型加低 effort，通常比較弱模型加高 effort 更省 token 因而更便宜 (@18:00)；frontier 難題上 extra high 或 max effort 的 token 用量比 medium、low 多很多，結果卻差不多 (@51:30)。用 hill climbing 降成本：設定「表現至少持平、成本下降」，搜 model、effort、prompt；單一案例從 Opus 高 effort 起步，先換新版 Opus 低 effort、再換更小的模型（表現略降、成本大降）、最後調 prompt 把表現救回，成本降約 90% 且表現明顯提升（講者所述）(@17:02)。[L.Martin-Prompts]
- 已知流程把路由與判斷從 LLM 搬到腳本與小模型，就能降級模型（單次 demo：平均 wall clock 從約 7.5 分鐘降到約 0.5 到 2 分鐘，講者口述，字幕可能有誤），代價是要先有成功的 run 可編譯（講者說那些 run 其實不太一致，@14:00） (@19:00, @19:30)。講者另說成本降「約 100%」，明顯誇大。[Blumenfeld]
- 新模型出來要重新評估哪個模型適合哪個任務；同一 workflow 內不同子任務（推理、確定性、影像、SQL、log）各 frontier model 擅長不同，講者舉例影像用 Gemini、確定性步驟用 OpenAI、開放式調查用 Claude (@07:00, @12:01)。[Krovvidi]
- Session 可設 budget（示範 1.25 美元），超過時收到事件，加預算後從原處續跑；刻意不告訴模型預算，因為目前模型知道預算會變得「焦慮」(@39:01, @84:02)。可回應上面 [Zhang-EA] 提的 budget 開放問題。[Avilla]

## 持續改進與評估 (evals)

- 本章內容已拆到 [agent-evals.md](agent-evals.md)。
- 每次失敗都是 harness bug：修 harness 而不是修產出。[Nisi] [Lopopolo]
- Harness 變更要當成模型變更來發布（Claude Code 品質事件）。[Anthropic-PM]

## 反例，風險與爭議點

- 關燈工廠（不讀程式碼）約三個月後失敗：出現無法靠 prompt 修的 bug，網站掛掉；RL 只獎勵測試通過，不獎勵架構品質。[Horthy-SF]
- 外部資料：導入 AI 後事故與每人 bug 上升，review 品質下滑（Faros AI 報告，經 [Horthy-SF] 引述）。
- Agent 會騙：假造測試通過，假報成功，範圍蔓延（自己把報告發成 PR）。[Nisi] [Kumar] [Jain]
- Fixed harness 在複雜變動環境脆弱；「適應式」harness 目前是概念，且有吸引子鎖定，單一文化，可讀性崩壞等風險。[Chandegra]
- 過度規定的記憶 schema 與過長 skill 都會讓表現變差。[L.Martin] [Nisi]
- 規模化 PR 難以審查：需縮小單次變更，並限制同時開啟 PR 數。[Mistele] [Horthy-SF]
- 技術面成本：重度 evaluator harness 又慢又貴，範例單次約 US$200。[Prabaker]
- 錯誤累積：每步錯誤率 5% 的步驟迴圈 10 到 20 次後，正確率可能只剩約一半（Pstrucha 的舉例）。[LoopsDebate]
- Agent 的壞習慣：愛複雜、會無上限堆疊；傾向討好而跳過步驟（被要求寫測試卻略過）；先全部實作再補測試；水平分層寫，延到最後才有整合回饋。[LoopsDebate] [Bichard] [Pocock]
- 失敗案例：Parquet Java 移除 Hadoop 依賴，research 與 plan 最後全部丟掉回白板重想。[Horthy-NV]
- Cognitive debt：不審查就失去對 codebase 的掌握；senior 工程師因為要清理 AI slop 越來越討厭 AI，staff 不用、junior 大量用，造成團隊裂痕。[Parsons] [Horthy-NV] [Pocock]
- Software factory 目前沒人真正解決：Huntley 自己的 Loom 六個月沒進展，Cursor 講者也承認尚未完全做到。[LoopsDebate] [Zakariasson]
- PM 用 vibe coding 做的 prototype 交給工程遷移很痛苦；建議把可互動的前端原型當成「意圖」交付，由工程重寫。[Zakariasson]
- Multi-agent 的新 injection 途徑：sub-agent 的輸出若被賦予較高信任會形成 trust escalation；長期記憶（CLAUDE.md、memory）被污染後每次啟動都會重新載入。[Anthropic-Contain]
- 三週重構的教訓：規格被曲解（要求加「agent skills」，plan 用了這個詞就核准，實際上 skill 和 action 是同一個東西、沒有 SKILL.md；核准 plan 不等於實作符合）(@05:01)。成本事故：月初收到約 100 美元的預算警示（平常一週的五倍），Codex 把 unit test 接到 production inference，一天跑約 30 輪；且每日自我反思 agent 產出是空的，因為重構弄壞了 prompt 管線 (@06:01)。重來時改寫新 spec 加 rubric，用四個框架（Claude Agent SDK、Codex、Copilot CLI、Pi）做 bake-off，並讓 Claude 與 Codex 互相多輪對抗式 review (@08:00, @18:01)。讀了 code 之後講者仍維持「不讀 code」的立場，只是改變做法 (@18:01)。個人專案經驗。[Kanazawa]

### 意見分歧

- 檔案 vs 資料庫記憶：Oracle 講者主張混合並以 DB 為主 [Martinez] [Malcolm]；Anthropic 講者主張任何通用基底皆可，避免預設 schema [L.Martin]。
- 自建 vs 依賴官方 harness：Lopopolo 主張從外面 steer 第一方 harness [Lopopolo]；Etsy 與 Cast AI 主張自建以支援本地/多模型 [Bhargava] [CastAI]；Chen&Fioca 建議以 SDK 嵌入 Codex。
- 有無 plan mode：Lopopolo 不使用，若用則把 plan 當 PR 審 [Lopopolo]；Horthy 主張大工作先規劃並對齊 [Horthy-SF]。
- 人要不要在迴圈中：OpenAI 與 Anthropic 傾向讓 agent 全自動（有 evaluator）[Lopopolo] [Prabaker]；HumanLayer 主張仍要讀程式碼 [Horthy-SF] [Mistele]。
- 編排放在 code 還是 prompt：[Nisi] 用 TypeScript state machine「enforce with code, not prompts」；Factory 把編排寫在 prompt 與 skills、確定性邏輯極薄，讓系統隨模型進步 [Alvoeiro]。
- 平行還是序列：Factory 刻意 serial [Alvoeiro]，Parsons 也主張先做單一 loop [Parsons]；Codex 與 Cursor 則大量平行 subagent 與 cloud agent，前提是先切好範圍避免衝突 [Codex-MC] [Zakariasson]。
- Loop 的實效（Great Loops Debate）：正方 Huntley、Livingstone 認為方向不可逆、軟體越可驗證越適合 loop；反方 Horthy、Pstrucha 認為炒作跑在紀律前面，仍要讀 code、往下一層抽象而不是往上。雙方共識：loop 在可驗證的任務上有效，架構判斷、成本、安全與歸責仍未解。[LoopsDebate]
- Spec 的角色：Pocock 反對 specs-to-code（只改 spec 不看 code 等於 vibe coding）[Pocock]；Horthy 認為「spec-driven」一詞已失去定義 [Horthy-NV]；Parsons 偏好 just-in-time spec，避免回到瀑布 [Parsons]；Factory 則在寫 code 前先寫 validation contract [Alvoeiro]。
- 隔離層級：VM [Bichard] [Zakariasson]、git worktree + Docker [Pocock]、每任務一個 K8s pod [Solmaz]。
- Harness 長期價值：「每次模型進步就刪掉」 [Schmid-NoCode] [Bhat&He] 與「harness 是限制因素」 [Bhat&He] [Bhargava] 並存，實務上是定期以 eval 重新審視。另一種看法是新模型上不同 harness 的分數已無顯著差異，但每題成本差異仍大，新領域反而要把 guardrail 加回來 [Katz]；Managed Agents 團隊也說 thick harness 與 thick skills 的邊界會變，誠實答案是每次換模型都要重跑 evals [CMA-3]。

## 現成資源（文章，程式庫，工具）

- OpenAI 文章 openai.com/index/harness-engineering 與 Latent Space podcast latent.space/p/harness-eng。[Lopopolo]
- Martin Fowler 網站的 "Harness engineering for coding agents"；LangChain 相關文章。[Chambers]
- 12-Factor Agents：github.com/humanlayer/12-factor-agents。[Horthy-12F]
- Codex CLI/harness 開源 (Apache 2, Rust)；Responses API 開放 schema；app-server 協定。[Kundel] [Chen&Fioca] [Kundel-Harness]
- Claude Agent SDK，Managed Agents（agent，environment，session 三原件；outcomes；dreaming；deployment = agent + 排程 + 初始訊息 + 可掛載的 memory store / repo / 檔案）。[Bhat&He] [L.Martin] [CMA-3]
- Strands Agents SDK + Amazon Bedrock AgentCore（memory，runtime，harness 設定檔）；AWS Agent Toolkit。[Chambers]
- Goose harness 與 Agent Client Protocol (ACP)。[Hancock]
- Pi (minimal harness) 與 Kimchi (github.com/getkimchi/kimchi)。[CastAI] [Nisi]
- Agency 語言 (agency-lang) 內建 interrupts，partial application，GEPA。[Bhargava]
- Docker `sbx` 與 MCP Gateway；Okta XAA。[Clark] [Jain]
- LangSmith Engine（trace 探勘）；RELAI；Arize Alyx。[Trivedy] [Feizi] [Delucia]
- SkillsBench；HarnessBench；Impeccable (impeccable.style) 作為 skill 工程範例。[Schmid-Evals] [Bhargava] [Bakaus]
- Oracle Agent Memory Package 與 workshop repo (agent-harness-workshop)。[Martinez]
- acpx（ACP 的 headless CLI + workflow engine）；Spritz（每任務一個 pod 的 K8s agent orchestrator）。[Solmaz]
- RLM Code（獨立實作）、OpenProse、Pi 的遞迴 extension、recursivecodingagents.com。[Shashi] [Weitekamp]
- Sandcastle（git worktree + Docker 平行 Ralph）；grill-me、write-a-PRD、prd-to-issues 等 skills。[Pocock]
- Terminal Bench；Harbor（定義每題機器資源）；Modal、Daytona 作平行 eval 基礎設施。[Khan]
- Temporal 與 Google ADK、LangGraph 的整合。[Warrick]
- Gemini Interactions API 與 Managed Agents。[Leo]
- AI Research OS（index.yaml + wiki 的檔案式記憶，開源 repo）。[Iusztin&Bouchard]
- Codex plugins、automations、subagents、hooks、guardian approvals；Factory Missions；Cursor cloud agents、Bugbot。[Codex-MC] [Alvoeiro] [Zakariasson]
- 可參考的開源 harness：OpenClaw（Gateway + plugin 架構，AGENTS.md 是很完整的 agent 工作守則）、DeepSeek Harness `dsh`（everything-is-a-plugin、session 快照測試）、claw-code（Claude Code 風格 CLI 的 Rust 實作，自稱展示用而非正式產品）。[OpenClaw-repo] [DeepSeek-H] [ClawCode]
- Paul Kinlan 的瀏覽器 sandbox 文章與 Co-do 示範專案（經 [Willison] 轉介）。

---

## 建議的實作順序（綜合以上的歸納，非單一講者主張）

0. 先確認需要的是 agent 而不是 workflow（四項檢查），並設定每任務預算。[Zhang-EA]
1. 先寫最小 loop + 工具登錄 + 停止條件 + 迭代上限 + trace 紀錄（事件日誌）；結束用明確的 finish 呼叫。[Kumar] [Templestein] [Horthy-12F] [F.Ali]
2. 加入確定性 verify 關卡與防作弊（讀 trace，雜湊證據），掛在 hook 上；大任務先寫 validation contract 再實作。[Kumar] [Nisi] [Sheikh] [Alvoeiro] [Nisi-Proser]
3. 把持久狀態與憑證放在 harness 側，沙箱內憑證為零（見 [agent-security.md](agent-security.md)）；設 deadline 與單一寫入者。[Clark] [Govindarajan]
4. Context：頭尾保留 + 可檢索 memory store，延遲載入工具，大資料交給子 agent；工作量控制在約 40% / 100k 以內。[Delucia] [Kundel] [Horthy-NV] [Pocock] [Leone]
5. Skills 只放 "gotchas"，配 eval 與 ablation；每次換模型重跑。[Nisi] [Schmid-Evals]
6. 加獨立 evaluator（有 rubric 與真實操作工具），長任務才需要 planner 與 sprint contract。[Prabaker]
7. 記憶：先讓模型自己寫檔案；有跨 session 價值再加 recall 排序與離線整理，並量測 recall policy。[L.Martin] [Druga]
8. 建立 trace 探勘與回歸測試的改進迴圈（見 [agent-evals.md](agent-evals.md)）；每個失敗當成 harness bug。[Trivedy] [Feizi] [Nisi]
9. 定期用 eval 找可刪元件。[Bhat&He] [Schmid-NoCode]

---

## 範圍與方法（本筆記的限制）
- 搜尋結果共 208 筆，去重後 158 支影片，其中 55 支逐字稿提到 "harness" 5 次以上。
- 已實際讀過逐字稿與資訊欄的有 33 支 (28 支全文，5 支只讀關鍵字附近段落，標（部分）)；另有 1 支 9 小時直播只取了少數數據點。見文末來源索引。
- 沒讀的：其餘影片已評估相關度，高相關者列入文末「待讀清單」（2026-10-07 已全數讀完併入），低相關者已移除，另有 3 支下載失敗（兩個長篇大會直播與一支音樂生成）。
- 逐字稿是 YouTube 英文自動字幕，內容為中文整理；數字與引述以影片內容為準，重要數據請回原片確認。
- 同一觀點有多人提到時，來源標籤會並列。
- 標（部分）的影片只讀了關鍵字附近段落與資訊欄，包含 [Prabaker] [Bakaus] [Templestein] [Bhardwaj] [Pai]；其中 [Prabaker] 在內文引用較多，細節請特別回原片確認。
- [WF26] 為 9 小時直播，只取了少數段落，引用的數據未經深讀驗證。
- 廠商影片（Oracle、Docker、Cast AI、RELAI）立場偏向自家產品，「意見分歧」一節已盡量並列其他講者的觀點。
- 同日另補 3 篇工程文章與 3 個開源 harness repo（索引「文章與程式庫」）：文章由 agent 讀全文；repo 只讀 README、AGENTS.md / CLAUDE.md 與檔案樹，沒有讀原始碼，架構描述以這些文件為準。
- 2026-10-07 補入的 22 支（索引中「agent 摘要」者）：用 [agent-runner](../../tools/agent-runner/README.md#實跑範例examplestalks) 抓英文自動字幕，由 Claude Sonnet 逐支讀完整逐字稿，依本筆記章節產出結構化摘要（每點附時間），再由 Claude Opus 挑選、去重後併入。沒有人逐支回看影片；自動字幕會聽錯人名與數字，數字後附 (@mm:ss) 方便核對。W&B、Google、Temporal、Factory、Cursor、OpenAI Codex、Anthropic（Skills、Agent SDK）這幾場被 agent 判定為較重的產品宣傳。
- 2026-11-12 補入：用 yt-dlp 列出頻道最新 400 支上傳，其中 274 支晚於前次最新的已收錄影片；依標題挑出 47 支與本系列筆記主題相關的（略過金融領域應用、GPU／推論基礎設施、語音、支付等），抓英文自動字幕，由 Claude Sonnet 逐支讀完整逐字稿摘要，再由 Claude Sonnet 依主題併入各篇筆記（本篇只收不屬於 evals、security、tools、CI、生產力、SDD、graph、API 的點），Claude Opus 抽查。沒有人逐支回看影片；時間點是依約每 60 秒一個字幕標記估的，誤差約一分鐘。

---

## 來源索引

| 簡稱 | 影片 | 讀取程度 |
|---|---|---|
| Kumar | [Harnesses in AI: A Deep Dive, Tejas Kumar (IBM)](https://www.youtube.com/watch?v=C_GG5g38vLU) | 全文 |
| Chambers | [Harness Engineering: Building the Production Cage, Mike Chambers (AWS)](https://www.youtube.com/watch?v=gxVZ_1tuuq4) | 全文 |
| Lopopolo | [Harness Engineering: How to Build Software When Humans Steer, Ryan Lopopolo (OpenAI)](https://www.youtube.com/watch?v=am_oeAoUhew) | 全文 (含 Q&A) |
| Martinez | [Total Recall: Agent Memory and Harness Engineering, Ignacio Martinez (Oracle)](https://www.youtube.com/watch?v=xs-ob87TTzg) | 全文 |
| Chandegra | [Beyond the Harness: Adaptive Engineering, Rajiv Chandegra](https://www.youtube.com/watch?v=qdZzND79mcg) | 全文 |
| Bhat&He | [Claude Managed Agents and Evolution of Agentic Surfaces (Anthropic)](https://www.youtube.com/watch?v=K0X9QDRkIdg) | 全文 |
| Prabaker | [Anthropic Workshop: Build Agents That Run for Hours](https://www.youtube.com/watch?v=mR-WAvEPRwE) | 部分 (關鍵字段落 + 資訊欄) |
| L.Martin | [Claude for Long-Horizon Tasks, Lance Martin (Anthropic)](https://www.youtube.com/watch?v=9QebvrrY3KY) | 全文 |
| Chen&Fioca | [Future-Proof Coding Agents (OpenAI)](https://www.youtube.com/watch?v=wVl6ZjELpBk) | 全文 |
| Trivedy | [Improving Agents is a Data Mining Problem (LangChain)](https://www.youtube.com/watch?v=CvRngaQZQ3Y) | 全文 |
| Govindarajan | [The Model Was Right. The Harness Failed. (OpenAI)](https://www.youtube.com/watch?v=BInpv7lGp1o) | 全文 |
| Bhargava | [What if the harness mattered more than the model? (Etsy)](https://www.youtube.com/watch?v=2e9ANoOEn28) | 全文 |
| Bhagwat | [Every Harness Will Become A Claw (Mastra)](https://www.youtube.com/watch?v=8qWIPUia2O8) | 全文 |
| Miraje | [Skills are new features: Skill-Centric Harness (FactSet)](https://www.youtube.com/watch?v=7jjudsEhBtM) | 全文 |
| Kundel | [How Codex Works (OpenAI)](https://www.youtube.com/watch?v=shRR1e2HXMk) | 全文 |
| Hancock | [ACP: The Universal Remote Control for AI Agents (Block)](https://www.youtube.com/watch?v=YkNulwcc5jk) | 全文 |
| CastAI | [Stop Rationing Tokens: Let the Harness Pick the Model (Kimchi)](https://www.youtube.com/watch?v=48YUYDjwfYY) | 全文 (廠商宣傳性質) |
| Druga | [Memory Harnesses for Long-Running Research Agents (Sakana.ai)](https://www.youtube.com/watch?v=R3-anFK1YM8) | 全文 |
| Bakaus | [The Dark Arts of Skill Engineering](https://www.youtube.com/watch?v=SQMCtZX3trg) | 部分 (關鍵字段落 + 資訊欄) |
| Malcolm | [No Memory, No Harness (Oracle)](https://www.youtube.com/watch?v=jA_x7F8caHI) | 全文 (廠商宣傳性質) |
| Horthy-SF | [Why Software Factories Fail, Dex Horthy](https://www.youtube.com/watch?v=Ib5GBkD555M) | 全文 |
| Templestein | [Make your own event-sourced agent harness (Iterate)](https://www.youtube.com/watch?v=vi-2nasppAg) | 部分 (關鍵字段落 + 資訊欄) |
| Feizi | [Continual Learning for AI Agents (RELAI)](https://www.youtube.com/watch?v=2IxD9OB3XuQ) | 全文 (廠商性質) |
| Jain | [Unlock Agent Autonomy: The Runtime for AI-Native Systems (Docker)](https://www.youtube.com/watch?v=zaGyGgLW3SM) | 全文 (廠商性質) |
| Nisi | [How I deleted 95% of my agent skills (WorkOS)](https://www.youtube.com/watch?v=vy7o1g2iHY8) | 全文 |
| Delucia | [How we solved Context Management in Agents (Arize)](https://www.youtube.com/watch?v=esY99nYXxR4) | 全文 |
| Mistele | [Loop Engineering from First Principles (HumanLayer)](https://www.youtube.com/watch?v=xIt_mTQp6mY) | 全文 |
| Schmid-Evals | [Don't Ship Skills Without Evals (Google DeepMind)](https://www.youtube.com/watch?v=0vphxNt4wyk) | 全文 |
| Horthy-12F | [12-Factor Agents (HumanLayer, 2025-07)](https://www.youtube.com/watch?v=8kMaTybvDUw) | 全文 |
| Clark | [How Many Credentials Should Your AI Agent Have? Zero. (Docker)](https://www.youtube.com/watch?v=ZUZVNKFSmTM) | 全文 (廠商性質) |
| Schmid-NoCode | [Agents Without Code: Skills, YAML, and Filesystems (Google DeepMind)](https://www.youtube.com/watch?v=fjF8EKnxKCU) | 全文 |
| Bhardwaj | [From fork() to Fleet: Agent Sandbox Cloud (OpenAI)](https://www.youtube.com/watch?v=OqM67QG_Ikk) | 部分 (關鍵字段落 + 資訊欄) |
| Pai | [Code Mode: Let the Code do the Talking — Sunil Pai, Cloudflare](https://www.youtube.com/watch?v=8txf05vVVl4) | 部分 (僅讀關鍵字附近段落) |
| WF26 | [WF26 Harness Engineering 全天直播 (551 分鐘)](https://www.youtube.com/watch?v=I2cbIws9j10) | 僅少數段落, 未深讀 |
| Sheikh | [Your coding agent doesn't always follow your rules, Talha Sheikh (Checkout.com)](https://www.youtube.com/watch?v=MpZzWMdmQCE) | 全文 (agent 摘要) |
| Aysola | [How We Built an Agent That Improves Itself, Zubin Aysola (Weights & Biases)](https://www.youtube.com/watch?v=XyV6bSMyq-I) | 全文 (agent 摘要，廠商性質) |
| Bichard | [The Missing Primitive for Agent Swarms, Lou Bichard (Ona)](https://www.youtube.com/watch?v=5Sui_OnSRlY) | 全文 (agent 摘要) |
| Solmaz | [Scaling Agents on Kubernetes with acpx and ACP, Onur Solmaz (OpenClaw)](https://www.youtube.com/watch?v=VaS2h-dY1-4) | 全文 (agent 摘要) |
| Leo | [An Interaction Is All You Need, Ivan Leo (Google DeepMind)](https://www.youtube.com/watch?v=8aVbXXvJUY4) | 全文 (agent 摘要，廠商性質) |
| Warrick | [The Human Is an Async API, Melanie Warrick (Temporal)](https://www.youtube.com/watch?v=jc3kbZkuHTo) | 全文 (agent 摘要，廠商性質) |
| Touil | [AI-Native Organisations Run on Skills, Imad Touil (QuantumBlack)](https://www.youtube.com/watch?v=M05vON8i0aI) | 全文 (agent 摘要) |
| Zhang&Murag | [Don't Build Agents, Build Skills Instead, Barry Zhang & Mahesh Murag (Anthropic)](https://www.youtube.com/watch?v=CEvIs9y1uog) | 全文 (agent 摘要，廠商性質) |
| LoopsDebate | [The Great Loops Debate, Dex Horthy, Geoff Huntley, Ian Livingstone, Greg Pstrucha](https://www.youtube.com/watch?v=c35YoMdnI78) | 全文 (agent 摘要) |
| Parsons | [Ralph Loops: Build Dumb AI Loops That Ship, Chris Parsons (Cherrypick)](https://www.youtube.com/watch?v=2TLXsxkz0zI) | 全文 (agent 摘要) |
| Weitekamp | [Recursive Coding Agents, Raymond Weitekamp (OpenProse)](https://www.youtube.com/watch?v=3hXJI2q0Jz8) | 全文 (agent 摘要) |
| Shashi | [RLM: Recursive Language Models for Large Codebases, Shashi (Superagentic AI)](https://www.youtube.com/watch?v=8oyalrfwgjw) | 全文 (agent 摘要) |
| Codex-MC | [OpenAI Codex Masterclass, Vaibhav Srivastav & Katia Gil Guzman (OpenAI)](https://www.youtube.com/watch?v=MhHEGMFCEB0) | 全文 (agent 摘要，廠商性質) |
| Horthy-NV | [No Vibes Allowed, Dex Horthy (HumanLayer)](https://www.youtube.com/watch?v=rmvDxxNubIg) | 全文 (agent 摘要) |
| Alvoeiro | [The Multi-Agent Architecture That Actually Ships, Luke Alvoeiro (Factory)](https://www.youtube.com/watch?v=ow1we5PzK-o) | 全文 (agent 摘要，廠商性質) |
| Zakariasson | [Building your own software factory, Eric Zakariasson (Cursor)](https://www.youtube.com/watch?v=rnDm57Py54A) | 全文 (agent 摘要，廠商性質) |
| Pocock | [Full Walkthrough: Workflow for AI Coding, Matt Pocock](https://www.youtube.com/watch?v=-QFHIoCo-Ko) | 全文 (agent 摘要) |
| Khan | [Evals Are Broken, Use Them Anyway, Ara Khan (Cline)](https://www.youtube.com/watch?v=QuuIywMG4s8) | 全文 (agent 摘要) |
| Koc | [Malleable Evals, Vincent Koc (OpenClaw / Comet)](https://www.youtube.com/watch?v=4VhbYlfC7Gs) | 全文 (agent 摘要) |
| Iusztin&Bouchard | [Turn 10,994 Notes Into Memory, Paul Iusztin & Louis-François Bouchard](https://www.youtube.com/watch?v=ZRM_TfEZcIo) | 全文 (agent 摘要) |
| Zhang-EA | [How We Build Effective Agents, Barry Zhang (Anthropic, 2025)](https://www.youtube.com/watch?v=D7_ipDqhtwk) | 全文 (agent 摘要) |
| Shihipar | [Claude Agent SDK [Full Workshop], Thariq Shihipar (Anthropic)](https://www.youtube.com/watch?v=TqC1qOfiVcQ) | 全文 (agent 摘要，廠商性質) |
| Katz | [Is the Agent Harness Dead?, Jediah Katz (SpaceXAI)](https://www.youtube.com/watch?v=7Y4sbZgBdnc) | 全文 (agent 摘要，2026-11) |
| CMA-1 | [Decoupling the Brain from the Hands: Claude Managed Agents (Part 1 of 4) (Anthropic)](https://www.youtube.com/watch?v=Uv0nAf_7tyU) | 全文 (agent 摘要，2026-11) |
| CMA-3 | [Scheduled Agents, Dreaming and Q&A: Claude Managed Agents (Part 3 of 4) (Anthropic)](https://www.youtube.com/watch?v=qJtcEDc_WJU) | 全文 (agent 摘要，2026-11，廠商性質) |
| Kundel-Harness | [Building on the Codex Harness, Dominik Kundel (OpenAI)](https://www.youtube.com/watch?v=9WiBJRO84yY) | 全文 (agent 摘要，2026-11) |
| Wilinski | [From 36% to 100%: How Self-Improving Agents Write Their Own Skills, Rafal Wilinski (Runlayer)](https://www.youtube.com/watch?v=u-o0sW9nwmk) | 全文 (agent 摘要，2026-11，廠商性質) |
| Petrov | [Your SKILL.md Is 70% Stuff the Model Already Knows, Nikolay Petrov (Intel)](https://www.youtube.com/watch?v=yzx4IuEh_tU) | 全文 (agent 摘要，2026-11) |
| L.Martin-Prompts | [Your Old Prompts Are Making Claude Worse, Lance Martin (Anthropic)](https://www.youtube.com/watch?v=ys6YQ2yfBpM) | 全文 (agent 摘要，2026-11) |
| F.Ali | [We Kept Rebuilding Our AI Agent. Here's What Survived, Fuad Ali (Arize AI)](https://www.youtube.com/watch?v=YIhvrvHtonk) | 全文 (agent 摘要，2026-11) |
| Knox | [Harness Engineering: How to Build a Software Factory, Dru Knox (Tessl)](https://www.youtube.com/watch?v=X6l4lpA0_NY) | 全文 (agent 摘要，2026-11) |
| Harrysson | [What the Top Companies Do Differently With AI Coding, Martin Harrysson & Prakhar Dixit (McKinsey)](https://www.youtube.com/watch?v=21tuT-e4NVo) | 全文 (agent 摘要，2026-11) |
| Avilla | [Why One AI Agent Isn't Enough (And How to Run 1,000), CJ Avilla & Harrison Stall (Anthropic)](https://www.youtube.com/watch?v=kiClTcJUnhc) | 全文 (agent 摘要，2026-11，廠商性質) |
| Konda | [Your Sub-Agents Are a Distributed System. Treat Them Like One., Girish Konda (Microsoft)](https://www.youtube.com/watch?v=DxP5aW4VknQ) | 全文 (agent 摘要，2026-11) |
| Joshi | [60% of Our Data PRs Now Merge With No Human Review, Chetas Joshi (Robinhood)](https://www.youtube.com/watch?v=MQiojLnK-E0) | 全文 (agent 摘要，2026-11) |
| Nisi-Proser | [Teach Your Agent to Prove It's Done, Nick Nisi & Zack Proser (WorkOS)](https://www.youtube.com/watch?v=q4WC4TowkBo) | 全文 (agent 摘要，2026-11) |
| Broekhuizen | [Giving AI Agents Memory That Learns, Jake Broekhuizen (LangChain)](https://www.youtube.com/watch?v=KGFyOtl5ktI) | 全文 (agent 摘要，2026-11) |
| Leone | [Why Bigger Context Windows Won't Save Your Agent, Elizabeth Fuentes Leone (AWS)](https://www.youtube.com/watch?v=DrfyORO8RqA) | 全文 (agent 摘要，2026-11) |
| Cameron | [Without Caching, Your AI Agent Costs 10x More, George Cameron (Artificial Analysis)](https://www.youtube.com/watch?v=prGP0huECPo) | 全文 (agent 摘要，2026-11) |
| Krovvidi | [The 6 Pillars of an Agentic Harness for Production, Varun Krovvidi (Resolve AI)](https://www.youtube.com/watch?v=eXA2tjRZIbY) | 全文 (agent 摘要，2026-11，廠商性質) |
| Blumenfeld | [Make Your AI Agents Predictable With Graph Engineering, Zachary Blumenfeld (Neo4j)](https://www.youtube.com/watch?v=g_NgCLTibiM) | 全文 (agent 摘要，2026-11，廠商性質) |
| Kormos | [How to Know When an AI Agent Can Work Unsupervised, Evan Kormos (Coinbase)](https://www.youtube.com/watch?v=_4Ph2dhmUFI) | 全文 (agent 摘要，2026-11) |
| Kanazawa | [I Let Agents Refactor My Codebase for 3 Weeks. Then I Read the Code., Keiji Kanazawa (Microsoft)](https://www.youtube.com/watch?v=6TjFjHPjVH0) | 全文 (agent 摘要，2026-11) |
| Arya | [Why We Deleted Our MCP Server and Rebuilt It, Abhi Arya (Reducto)](https://www.youtube.com/watch?v=jJQoVkd5yLg) | 全文 (agent 摘要，2026-11) |
| Arcolano | [Better AI Models Won't Fix Your Engineering Team, Nicholas Arcolano (Jellyfish)](https://www.youtube.com/watch?v=Ve2bAarPA2I) | 全文 (agent 摘要，2026-11) |
| G.He | [Grep or Embeddings? Agentic Search Over Company Documents, George He (LlamaIndex)](https://www.youtube.com/watch?v=X4w2Pkz5tDY) | 全文 (agent 摘要，2026-11) |
| Agrawal | [225,000 Lines of Tests, Written and Merged by Agents, Kush Agrawal (Duolingo)](https://www.youtube.com/watch?v=D_4Rn6uLdQM) | 全文 (agent 摘要，2026-11) |

### 文章與程式庫

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Anthropic-Contain | [How we contain Claude across products (Anthropic Engineering)](https://www.anthropic.com/engineering/how-we-contain-claude) | 全文 (agent 摘要) |
| Anthropic-PM | [An update on recent Claude Code quality reports (Anthropic Engineering)](https://www.anthropic.com/engineering/april-23-postmortem) | 全文 (agent 摘要) |
| Willison | [the browser is the sandbox, Simon Willison](https://simonwillison.net/2026/Jan/25/the-browser-is-the-sandbox/) | 全文 (agent 摘要，轉介 Paul Kinlan 的文章) |
| OpenClaw-repo | [openclaw/openclaw](https://github.com/openclaw/openclaw) | README + AGENTS.md + 檔案樹 (agent 摘要) |
| DeepSeek-H | [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | README + AGENTS.md + 檔案樹 (agent 摘要) |
| ClawCode | [ultraworkers/claw-code](https://github.com/ultraworkers/claw-code) | README + AGENTS.md + 檔案樹 (agent 摘要) |

## 待讀清單

原清單 22 支已在 2026-10-07 由 agent 讀完併入（見來源索引「agent 摘要」）。目前沒有待讀項目。
