# Agent Evals：持續改進與評估

本篇從 [harness-engineering.md](harness-engineering.md) 的「持續改進與評估 (evals)」章節拆出，內容逐條照搬。2026-11-12 補入 AI Engineer 頻道 2026-10 至 2026-11 上傳的新影片（由 Claude Sonnet 讀逐字稿摘要後併入，未逐支回看影片）。內文的 `[簡稱]`（如 [Schmid-Evals]）對應文末「來源」表，完整索引見原筆記的來源索引。

## 做法

- Trace mining：讓 agent 讀其他 agent 的 trace，找情緒不佳的互動，壓縮後是否變笨，反事實（換模型會如何）；大型 trace 當外部物件查詢；dense feedback 優於單純通過/失敗。[Trivedy]
- 每次失敗都是 harness bug：修 harness 而不是修產出；每週一天 (garbage collection day) 把重複出現的 slop 轉為文件，lint 或 review agent。[Nisi] [Lopopolo]
- 可驗證的持續學習：失敗轉成可重播環境，修補前後有量測差異，並對舊環境做回歸測試；修補層級 (model, harness, memory) 取最小的耐久變更。[Feizi] [Jakovcevic]
- Skill eval 實作：JSON 測試案例（prompt，should_trigger，預期檢查） + 簡單 runner；多以 regex 斷言，複雜時用 LLM judge；隔離工作區，多次重複，測結果不測路徑，跨 harness，每次修改都跑，保留 eval 即使 skill 退役。[Schmid-Evals]
- 自動優化：GEPA 之類最佳化器直接調整被標記的 prompt。[Bhargava] [Feizi]
- 日常除錯：最有效的是親自讀 trace；其次把 transcript 丟給另一個 agent 找問題；觀察 evaluator 判斷與人類分歧處再調 prompt。[Prabaker]
- 現有 benchmark 缺乏對維護性的懲罰（SWE-Marathon，DeepSWE，Frontier Code 為較新嘗試）。[Horthy-SF]
- Eval flywheel：production 與離線研究環境跑逐位元組相同的 agent、同一種 trace 格式；每個 production 的失敗（與成功）都轉成離線 eval task；agent 設定寫成 YAML 以便大量產生變體並行測；評分本身最花時間，也要驗證評分的穩健性。[Aysola] [F.Ali]
- Benchmark 實戰（Cline，Terminal Bench 89 題從約 43% 起步 (@14:01)）：每題隔離環境、全部平行跑；派 agent 讀每個失敗 run 的 trace 標註原因；改進分三區：明顯缺陷（crash、被 rate limit）要修、針對模型家族的細調最關鍵、過擬合衝分是危險區。進步多半來自容器資源、timeout、thinking 行為與模型家族專屬 prompt，而不是換模型；hill climbing 與 vibe check 兩個都要。[Khan]
- Eval calcification：系統會變，靜態 benchmark 與手工資料集遲早失效。改以意圖 / 終態定義 eval、從 trace 自動長出測試集；約 80% 穩定部分 + 20% 持續變動由 agent 維護（比例為舉例）；做成 always-on 的線上評測。[Koc]
- 讓 agent 讀過去的 session，建議該新增哪些 automation、subagent 或 rule。[Codex-MC] [Zakariasson]
- 新模型推出時先拿掉既有 skills / markdown，用裸模型重新驗證：不同模型偏好不同（例如對全大寫強調的反應相反）。[LoopsDebate]
- 把一次表現極佳的 "golden session" 交給 agent 拆成可重用的 workflow。[Weitekamp]
- Harness 變更要當成模型變更來發布（Claude Code 品質事件）：三個 harness 層變更（預設 effort、清除舊 thinking 的 bug、system prompt 加字數限制）疊加後看起來像模型退化，API 與推論層其實沒動；code review、單元與 e2e 測試、dogfooding、原有 eval 都沒抓到。改進：每次 system prompt 變更跑跨模型的廣泛 eval 並逐行 ablation（這樣才看到 3% 的下降）、與特定模型相關的調整綁定該模型、soak period 加漸進 rollout、內部人員使用與公開版相同的 build。[Anthropic-PM]

### Rubric 與 LLM judge

- 沒有 eval 就偵測不到改 prompt 後的 regression，也無法客觀比較 prompt 或模型版本、無法在 CI 設品質閘門；eval 不等於 unit test，agent 的邏輯只出現在 trace 裡且有多個合法輸出，trace 是 log、eval 才是 test，所以先要有 observability (@02:00 到 @03:00)。[Delucia-Evals]
- Eval 類型：LLM judge（label 加 explanation）、decision model（便宜快速，回機率與 true/false，沒有 explanation）、code eval（JSON 格式、關鍵字等確定性檢查）、人工 annotation、agent as a judge（成功條件很複雜時）；前四類可從開發一路用到上線 (@05:00)。[Delucia-Evals]
- 定義「好」要可判定：不寫 helpful、accurate，改寫「回答追問、天數符合需求、總額不超過預算」。Criteria 格式為 task、成功長相、失敗長相、被判斷的對象，各列約三點 pass/fail 條件，直接變成 judge prompt (@19:00 到 @22:00)。一個 judge 只判一個面向（講者稱有研究支持，未給出處），從少數 eval 起步再擴充（她的 agent 從 4 個到 32 個）；起手式是約 20 條 trace、一個維度、一個 judge (@20:00, @34:00)。[Delucia-Evals]
- LLM-as-judge 實務：用人能評分的 rubric，避免 0 到 5 或 1 到 10 的量表，盡量用二元分類，多面向就用多個二元 judge；用不同模型交叉評分並跑 replicate 看變異；pairwise 比較比單獨打分容易；評分用較小便宜的模型 (@30:00 到 @34:00)。[L.Martin-Prompts]
- Eval 取樣不要只挑某個模型失敗的題目（adversarial sampling），因為模型能力不均勻，換模型後分佈會失真；題目依 production 資料與第一原理選 (@32:00 到 @34:00)。好 eval 的條件：換更大模型或加 thinking 分數會升、frontier 有 headroom、run 之間低變異；題目含糊會留下永遠拿不到的 20%，讓 hill climbing 白燒 token (@10:01)。[L.Martin-Prompts]
- Judge 要做 meta-evaluation：拿人工 golden data 比相關係數與 binary accuracy，合格的 agreement 以人與人之間的 agreement 為基準（主觀任務本來就低）；Netflix 的例子是證明 judge 判為差的內容與觀眾放棄觀看等串流指標有因果相關 (@10:00)。[Wolfe]
- Judge 與 rubric 不同：judge 用通用品質準則，rubric 是任務專屬清單、每項獨立用 LLM 驗證，客觀性較高 (@08:00)。[Wolfe]
- 主觀任務的 eval 三段式：人工評估當 North Star（先與領域專家寫 quality guidelines，多人評同批資料看 agreement，依分歧修 guideline 到一致）、offline eval 放大實驗規模、A/B test 與 production monitoring 驗證，失敗案例回灌前面各段 (@04:00 到 @05:00, @13:00)。[Wolfe]
- 噪音是 eval 難的主因：agent 非確定性、題目少、grader 也是非確定性 LLM (@01:00)。用 power analysis 決定資料量（effect size、重抽樣估計的 noise、顯著水準），報分數附 confidence interval，對模型與 judge 都多次 resampling，才分得出真進步與噪音 (@06:00, @12:00)。[Wolfe]
- 規則式 verifier 不夠時：精確文字比對太脆弱（「waitlisted」與「seat confirmed」無法用字串區分），改用小模型當 judge 判語意是否符合契約，並保留單元測試避免 judge 漂移 (@39:00)。[Nisi-Proser] 另有構想在尾端用便宜的 decision model 當 verifier，因為由 agent 自己宣稱契約達成不可靠，換成 Haiku 與強模型結果差很大 (@26:01)。[OpenProse]
- Rubric 驅動的 hill-climb：除了 spec 與 plan，再給由 agent 起草的「成果長什麼樣」rubric，agent 對著它迭代，人看輸出後再改 rubric；三層迴圈為寫 rubric、對 rubric 爬坡、迭代 rubric 本身 (@14:01)。Agent 會對自己的 rubric 作弊：針對單一範例影片過擬合，跑到五支就失敗，所以 rubric 也要 review 並用多個樣本驗證 (@16:01)。[Kanazawa]
- Hill climbing 防過擬合：eval 切 train/test，優化器只看 train 的失敗，每輪同時看 test；train 升 test 持平就是過擬合（例：為單題加 OCR 工具，production 並不需要）(@12:00 到 @14:00)。不保證收斂，常因 eval 含糊或 grader 有錯，需要「卡住時把剩餘失敗分群檢查」的後備 (@36:01)。優化表面：prompt 與 skill 文字容易改且與行為耦合明確，但最易過擬合；改 harness 程式碼 diff 大、較難解讀 (@27:01)。[L.Martin-Prompts]
- Skill 是否有用要量：先做 with/without skill 對照（例：無 skill 解 5 題中 3 題，有 skill 全解，同時比 token 與時間）(@01:30)。進一步借 FActScore 概念把 skill 拆成每個約 25 到 30 項的可檢查命題，各配問題與預期答案，在兩種條件下由 judge（建議不同模型家族）評分，並確保題目不洩漏答案 (@04:00 到 @05:00)。[Petrov]
- 四象限解讀：兩邊都對 = skill 沒貢獻；無 skill 錯有 skill 對 = 真的教到東西；無 skill 對有 skill 錯 = 有害，最優先修；兩邊都錯 = skill 寫得差或遺漏 (@06:00)。有害項很少（約 400 項只找到 1 項）(@08:00)。刪掉模型已知內容後仍須重跑 eval 確認分數不變 (@12:00)。[Petrov]
- Rubric 用 markdown 寫成 skill 定義：評什麼、成功與失敗 label、通過門檻、定義內容；從幾條 bullet 起步再累積，藝術多於科學 (@09:00)。常見 scorer：redundant test、verbosity（拖慢目前最大瓶頸 code review）、efficiency（從 tool call 看是否有效率）(@06:00)。[Holmes]

### 從 trace 與對話挖失敗

- 閉環：蒐集團隊所有 agent conversation，用依自訂 rubric 的 scoring agent 評分，濾出失敗找原因，再由定時執行的 agent 對 skills 與設定提出修改，持續評分看分數變化 (@02:01)。PR merge 後觸發，每個 conversation 一個評分 agent，可隨機抽樣省 token，每筆都要寫出失敗或通過的原因 (@10:01)。[Holmes]
- 需要 tool call 級的 trace，因為 agent 會繞過路障而不告訴你：測試環境 skill 裡有過期指示，agent 靠亂 ping port 試出環境，團隊只看到「多花約 2 分鐘」(@08:01)。Skill Doctor 可在單機一次性掃描 Claude、Codex 等對話批次評分；有分數 dashboard 才能把某次 skill 改動對應到分數轉折點，可見的分數比看不到的 memory 或 dreaming 更能證明「改動有效」(@13:01, @16:01)。[Holmes]
- Agent 的 bug 很少是顯式錯誤：status 是 ok，但同一 turn 有 43 個相同 tool call 或 227 秒回應才是問題，多長算太長取決於用例；用讀 trace 的 agent 自動找 (@16:01)。Judge 仍需人的 gold labels 對齊，速度對品質的取捨是人的判斷 (@17:00)。[F.Ali]
- 把 transcript 當 eval：agent 實際跑過的指令就是 test case，緊接著的下一步是粗略的 answer key；新舊版重放，檢查排序改動後後續用到的結果仍在前面、改格式沒遺漏；agent 換參數重試通常就是失敗案例；留幾個 case 不拿來調、專門打分 (@07:02)。先備份 transcript（Claude Code 可能 30 天後刪掉不活躍的），搜「工具名稱加 pipe」與「同工具馬上換參數重呼叫」(@11:01)。[Bhardwaj-CLI]
- 不是所有 trace 都該變 memory：多數留作可查的歷史，部分變成離線 eval 資料集，只有小部分改變 agent memory；全轉成 long-term 反而讓 agent 難以推理 (@13:00)。[Broekhuizen]
- 把真實使用者失敗變成測試：蒐集 thumbs up/down 與觀測資料，重現問題、判斷是 tool call 還是其他環節，加進 eval pipeline；人工審查加客戶回饋能抓到最後約 5% 的 edge case (@13:30)。[Lokanathan]
- 使用者的正負回饋與引導都當 eval 訊號；評估分五層：正向回饋、負向回饋、軌跡可追蹤、與最佳工程師的調查比較評分、信心校準，新模型、新用例或架構變更時重跑 (@15:01 到 @16:02)。[Krovvidi]
- 遇到歧義（兩種讀法、沒見過的文件類型）不該猜也不該停，要用 ask user question 類工具提問；eval 裡把「做出不穩固假設」判為失敗，獎勵提問 (@10:00)。另記錄每個 MCP session 的 prompt、請同事匯出 Claude Code session，看人在哪裡推翻 agent、模型何時信心低，回饋進長期指引 (@13:00)。[Arya]
- 人工回饋迴圈的實例：人在 comment 回覆同意或反對並說明原因，每天收集，on-call 每週讀一次手動更新規則，沒有自動改規則 (@18:02)。評測看兩種錯：漏放（bad PR 被 approve）與誤升級（fine PR 送給人）；miss rate 約 2% 多半是規則缺口而非判斷失誤，miss 案例變成新規則 (@20:02)。指標為自報、無對照組。[Joshi]

### 回歸與發布

- 改善一個維度不等於整體變好：在 support agent prompt 加一行「執行任何動作前先確認」，action safety 上升 17 點、task completion 下降 17 點，平均淨零 (@03:00)。Diff 只是一行 markdown，行為變化（多餘步驟、sub-agent 協作、tool 呼叫軌跡）只存在 trace：diff 告訴你改了什麼，trace 告訴你發生什麼 (@05:00)。[Jakovcevic]
- 五步 regression loop：dataset 直接取 production trace 不用合成，涵蓋一般流程、已知失敗、edge case 與容易被忘的「要保護的成功流程」(@06:30)；evaluator 把 hallucination、accuracy、tool trajectory、step efficiency 轉成 0/1 或多級分數，確定性用 code evaluator、非確定性用 LLM judge (@08:00)；baseline 後只改一個東西（prompt、handoff、tool、模型）重跑比較，換貴五倍的模型要靠數字證明 ROI (@09:45)。範例 100 筆資料集調整後 action safety +18、task completion +6 (@12:00)；每個失敗都變成新的 regression 測試 (@17:00)。[Jakovcevic]
- 歷史 PR 資料集：約每 1,000 個 PR 才有 1 個重大 bug，不做資料集就看不出 review agent 退步；bug 型態會變，約 80 到 90% 是舊錯誤重現，新的 agent 會犯新型態錯誤，所以要持續更新 (@07:00)。[Gupta]
- 所有 production session 都 trace 並成為回歸資料集，可把整個 session 存成 dataset 重播某一 turn；用 experiments 對 harness 變更做 A/B (@15:01)。[F.Ali]
- 回歸要保留舊能力：更強的新模型仍可能做不到舊模型做得好的事（講者舉 Google Assistant 換成 Gemini 後設提醒失效），要持續測已知任務與過去的失敗 (@12:30)。分數到 85 到 90 就該把 eval 變難，避免 benchmark 飽和 (@13:00)。[Lokanathan]
- 測整個 workflow 而不只最終答案：要求只換圖片背景，結果多了兩個把手；100 步的流程每步都要評輸入、輸出與預期，並依該步功能設計測試 (@06:30)。Holistic 評測 = CI 自動檢查 + 持續人工審查（不要讓 agent 當最終審查者）+ adversarial 測試 (@07:30)。先問「必須發生什麼、絕不能發生什麼、何時該停」；eval 拿 100 分代表太簡單 (@05:30)。[Lokanathan]
- 在 Harbor 之類框架把 agent 放進關閉網路的 sandbox，多次 trial 降 flake，verifier 給 1 或 0，追蹤各任務 pass@k，並取 trajectory 供 prompt hill climbing (@12:01)。[M.King]
- 模型選型：先看通用 Pareto 前緣縮小候選，原型階段用短名單自己測，上線前自建 benchmark 比 3 到 5 個模型；通用排名不一定符合自己的任務（例：Gemini 系列在複雜試算表任務上強）(@18:00)。[Cameron]
- 記憶類功能的信任要靠自己的 evals 驗證：dreaming 只看到「九個 session 說錯、一個說對」時可能漏掉洞見，官方稱客戶 evals 有顯著進步但未給數字 (@14:01)。Outcomes 功能讓你寫明確 rubric 與最大迭代數，由 verifier agent 驅動 agent 直到達標 (@10:01)。[CMA-3]
- 外圈：online evaluator 給 production trace 評分，低分 trace 進 offline eval 集，hill climb，通過後進 regression 測試 (@62:00)。自建 50 張客服 ticket 的合成 eval 並注入反模式，模擬遷移到新模型，遷移後再跑 prompt audit 同時降成本並提升表現（講者自建、非公開基準，數字字幕可能有誤）(@04:00)。[L.Martin-Prompts]
- 在 metric 與 eval 之間：metric 只告訴你「可能壞了」，eval 才告訴你 failure mode；judge 與人類標註做 alignment 後，再把 eval 變成跑在新 trace 上的 online eval，product、eng、support、security 都參與定義成功 (@33:00)。[Delucia-Evals]

### 何時能放手

- Loop 只和 check 一樣可信：要先定義何謂「好」並有可靠的評估，否則多跑幾輪不代表更好 (@10:30)。Agent 不確定性高，不能只靠精確輸出比對，要用代表性資料集、重複多次的統計分析，搭配 traces 當新的 confidence mechanism (@12:00)。[Kormos]
- 三階段放手：先全程人工監督並與領域專家定義「好」；達到 policy 規定的信心門檻後改抽樣審查，用 traces 系統化檢查人沒看到的部分；再過門檻後人只處理例外，仍參與維護資料集。風險決策（如貸款最終 decision）維持人類主導 (@14:30)。[Kormos]

## 相關筆記

- [harness-engineering.md](harness-engineering.md)：Harness 實作做法總覽與完整來源索引
- [agent-security.md](agent-security.md)：沙箱、權限與憑證

## 來源

### 演講與影片

| 簡稱 | 影片 | 讀取程度 |
|---|---|---|
| Trivedy | [Improving Agents is a Data Mining Problem (LangChain)](https://www.youtube.com/watch?v=CvRngaQZQ3Y) | 全文 |
| Nisi | [How I deleted 95% of my agent skills (WorkOS)](https://www.youtube.com/watch?v=vy7o1g2iHY8) | 全文 |
| Lopopolo | [Harness Engineering: How to Build Software When Humans Steer, Ryan Lopopolo (OpenAI)](https://www.youtube.com/watch?v=am_oeAoUhew) | 全文 (含 Q&A) |
| Feizi | [Continual Learning for AI Agents (RELAI)](https://www.youtube.com/watch?v=2IxD9OB3XuQ) | 全文 (廠商性質) |
| Schmid-Evals | [Don't Ship Skills Without Evals (Google DeepMind)](https://www.youtube.com/watch?v=0vphxNt4wyk) | 全文 |
| Bhargava | [What if the harness mattered more than the model? (Etsy)](https://www.youtube.com/watch?v=2e9ANoOEn28) | 全文 |
| Prabaker | [Anthropic Workshop: Build Agents That Run for Hours](https://www.youtube.com/watch?v=mR-WAvEPRwE) | 部分 (關鍵字段落 + 資訊欄) |
| Horthy-SF | [Why Software Factories Fail, Dex Horthy](https://www.youtube.com/watch?v=Ib5GBkD555M) | 全文 |
| Aysola | [How We Built an Agent That Improves Itself, Zubin Aysola (Weights & Biases)](https://www.youtube.com/watch?v=XyV6bSMyq-I) | 全文 (agent 摘要，廠商性質) |
| Khan | [Evals Are Broken, Use Them Anyway, Ara Khan (Cline)](https://www.youtube.com/watch?v=QuuIywMG4s8) | 全文 (agent 摘要) |
| Koc | [Malleable Evals, Vincent Koc (OpenClaw / Comet)](https://www.youtube.com/watch?v=4VhbYlfC7Gs) | 全文 (agent 摘要) |
| Codex-MC | [OpenAI Codex Masterclass, Vaibhav Srivastav & Katia Gil Guzman (OpenAI)](https://www.youtube.com/watch?v=MhHEGMFCEB0) | 全文 (agent 摘要，廠商性質) |
| Zakariasson | [Building your own software factory, Eric Zakariasson (Cursor)](https://www.youtube.com/watch?v=rnDm57Py54A) | 全文 (agent 摘要，廠商性質) |
| LoopsDebate | [The Great Loops Debate, Dex Horthy, Geoff Huntley, Ian Livingstone, Greg Pstrucha](https://www.youtube.com/watch?v=c35YoMdnI78) | 全文 (agent 摘要) |
| Weitekamp | [Recursive Coding Agents, Raymond Weitekamp (OpenProse)](https://www.youtube.com/watch?v=3hXJI2q0Jz8) | 全文 (agent 摘要) |
| Kormos | [How to Know When an AI Agent Can Work Unsupervised, Evan Kormos (Coinbase)](https://www.youtube.com/watch?v=_4Ph2dhmUFI) | 全文 (agent 摘要，2026-11) |
| Gupta | [How to Build an AI Code Review Agent, Daksh Gupta (Greptile)](https://www.youtube.com/watch?v=4UtrRVtUN_g) | 全文 (agent 摘要，2026-11) |
| Kanazawa | [I Let Agents Refactor My Codebase for 3 Weeks. Then I Read the Code., Keiji Kanazawa (Microsoft)](https://www.youtube.com/watch?v=6TjFjHPjVH0) | 全文 (agent 摘要，2026-11) |
| OpenProse | [Stop Telling Agents How, OpenProse 團隊](https://www.youtube.com/watch?v=7T-gldvgfpo) | 全文 (agent 摘要，2026-11，廠商性質) |
| Lokanathan | [If Your AI Scores 100%, Your Eval Is Wrong, Ramakrishnan Lokanathan (eslams.com)](https://www.youtube.com/watch?v=7WUzHIF32vA) | 全文 (agent 摘要，2026-11) |
| M.King | [Stop Giving Your Agent Tools. Give It a Sandbox, Mikyo King (Arize AI)](https://www.youtube.com/watch?v=dAoOYFx7ZYw) | 全文 (agent 摘要，2026-11) |
| Krovvidi | [The 6 Pillars of an Agentic Harness for Production, Varun Krovvidi (Resolve AI)](https://www.youtube.com/watch?v=eXA2tjRZIbY) | 全文 (agent 摘要，2026-11，廠商性質) |
| Delucia-Evals | [How to Write Your First AI Eval, SallyAnn DeLucia (Arize AI)](https://www.youtube.com/watch?v=gv4w23xYj-0) | 全文 (agent 摘要，2026-11，廠商性質) |
| Arya | [Why We Deleted Our MCP Server and Rebuilt It, Abhi Arya (Reducto)](https://www.youtube.com/watch?v=jJQoVkd5yLg) | 全文 (agent 摘要，2026-11) |
| Broekhuizen | [Giving AI Agents Memory That Learns, Jake Broekhuizen (LangChain)](https://www.youtube.com/watch?v=KGFyOtl5ktI) | 全文 (agent 摘要，2026-11) |
| Joshi | [60% of Our Data PRs Now Merge With No Human Review, Chetas Joshi (Robinhood)](https://www.youtube.com/watch?v=MQiojLnK-E0) | 全文 (agent 摘要，2026-11) |
| Cameron | [Without Caching, Your AI Agent Costs 10x More, George Cameron (Artificial Analysis)](https://www.youtube.com/watch?v=prGP0huECPo) | 全文 (agent 摘要，2026-11) |
| Holmes | [Your AI Agent Is Hiding Its Mistakes From You, Ben Holmes (Warp)](https://www.youtube.com/watch?v=pz74r-4dGfQ) | 全文 (agent 摘要，2026-11) |
| Nisi-Proser | [Teach Your Agent to Prove It's Done, Nick Nisi & Zack Proser (WorkOS)](https://www.youtube.com/watch?v=q4WC4TowkBo) | 全文 (agent 摘要，2026-11) |
| CMA-3 | [Scheduled Agents, Dreaming and Q&A: Claude Managed Agents (Part 3 of 4) (Anthropic)](https://www.youtube.com/watch?v=qJtcEDc_WJU) | 全文 (agent 摘要，2026-11，廠商性質) |
| Bhardwaj-CLI | [Your Agent Hates Your CLI, Ayush Bhardwaj (Allos AI)](https://www.youtube.com/watch?v=rS36lYuvXQ8) | 全文 (agent 摘要，2026-11) |
| Jakovcevic | [Your Agent Fix Just Broke Something Else, Sofia Jakovcevic (Arize AI)](https://www.youtube.com/watch?v=v5tm5EAzsAs) | 全文 (agent 摘要，2026-11，廠商性質) |
| F.Ali | [We Kept Rebuilding Our AI Agent. Here's What Survived, Fuad Ali (Arize AI)](https://www.youtube.com/watch?v=YIhvrvHtonk) | 全文 (agent 摘要，2026-11) |
| L.Martin-Prompts | [Your Old Prompts Are Making Claude Worse, Lance Martin (Anthropic)](https://www.youtube.com/watch?v=ys6YQ2yfBpM) | 全文 (agent 摘要，2026-11) |
| Petrov | [Your SKILL.md Is 70% Stuff the Model Already Knows, Nikolay Petrov (Intel)](https://www.youtube.com/watch?v=yzx4IuEh_tU) | 全文 (agent 摘要，2026-11) |
| Wolfe | [How Netflix Evaluates AI When There's No Right Answer, Cameron Wolfe (Netflix)](https://www.youtube.com/watch?v=zLc8zeGeNaY) | 全文 (agent 摘要，2026-11) |

### 文章與程式庫

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Anthropic-PM | [An update on recent Claude Code quality reports (Anthropic Engineering)](https://www.anthropic.com/engineering/april-23-postmortem) | 全文 (agent 摘要) |
