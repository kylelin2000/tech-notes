# Spec-driven development：spec-kit、Kiro 與 Böckeler 的評析

本篇整理 spec-driven development（SDD）的定義分級、spec-kit 與 Kiro 的流程、Birgitta Böckeler（刊於 martinfowler.com）的疑慮，以及與 superpowers、compound engineering 的對照；資料取得日期 2026-10-14，內文的 `[簡稱]` 對應文末來源表。

## SDD 是什麼

- SDD 的基本主張是在用 AI 寫 code 之前先寫 spec（「documentation first」），spec 成為人與 AI 共同的 source of truth。[Fowler-SDD]
- Böckeler 指出定義仍在變動，並依 spec 的生命週期分三級：spec-first（先寫好 spec，用於當次任務）、spec-anchored（任務完成後保留 spec，用於該功能的演進與維護）、spec-as-source（spec 是長期的主要原始檔，人只改 spec、不碰 code）。[Fowler-SDD]
- 作者看到的所有 SDD 做法都至少是 spec-first，但不是都追求 spec-anchored 或 spec-as-source，spec 長期怎麼維護常常沒說清楚。[Fowler-SDD]
- spec-kit 的方法論文件講得最激進：「規格不服務 code，code 服務規格」，維護軟體就是演進規格，code 是「最後一哩」。[SpecKit-SDD]
- 作者把 spec 定義為「以自然語言寫成、結構化且以行為為導向、用來引導 AI coding agent 的 artifact（或一組 artifact）」；並區分 spec 與 memory bank（規則檔、產品與 codebase 的高階描述）：後者每次 session 都適用，spec 只與建立或修改該功能的任務有關。[Fowler-SDD]
- 作者也提到「spec」已被語意擴散，有人把它當成「詳細 prompt」的同義詞。[Fowler-SDD]

## spec-kit：流程、指令與產出

- 流程是「constitution 每個專案一次；specify → plan → tasks → implement → converge 每個功能一次」，並重複 implement → converge 直到 convergence 回報 Converged。[SpecKit]
- 目前 README 的指令是 agent 內的 skill，不是終端機指令：`/speckit-constitution`、`/speckit-specify`、`/speckit-plan`、`/speckit-tasks`、`/speckit-implement`、`/speckit-converge`；需要額外品質關卡時可加 clarification、checklists 與 consistency analysis。[SpecKit]
- CLI 只負責安裝與初始化：`uv tool install specify-cli`，再 `specify init my-project --integration copilot`（需要 Python 3.11+ 與 uv）。[SpecKit]
- README 目前列出三個獨立入口，不是三個必經階段：SDD（核心內建）、Bug fixing（`specify extension add bug`，assess → fix → test，報告放 `.specify/bugs/<slug>/`，結論為 verified／partial／failed）、Idea assessment（`specify extension add assess`，intake → research → define → shape → decide，結論為 go／needs-clarification／kill）。[SpecKit]
- 方法論文件（`spec-driven.md`）用的是較舊的 `/speckit.specify`、`/speckit.plan`、`/speckit.tasks` 寫法，並提到 `/speckit.analyze`；與 README 的 `/speckit-*` 命名不同，以 README 為準。[SpecKit-SDD] [SpecKit]
- 方法論文件描述的產出：`/speckit.specify` 自動編號、建立 branch、產生 `specs/[branch-name]/spec.md`；`/speckit.plan` 產生 `plan.md`，並可產生 `research.md`、`data-model.md`、`contracts/`、`quickstart.md`；`/speckit.tasks` 讀 `plan.md`（必要）與其他文件，寫出 `tasks.md`，獨立任務標 `[P]` 以便平行。[SpecKit-SDD]
- constitution 放在 `memory/constitution.md`，是「不可變」的專案原則；文件列出九條 Article（如 Library-First、CLI Interface、Test-First、Simplicity、Anti-Abstraction、Integration-First），其中 IV–VI 由各專案自行定義。[SpecKit-SDD]
- 模板把約束寫進 prompt：spec 只談 WHAT/WHY、不談 HOW；不確定處必須標 `[NEEDS CLARIFICATION: ...]` 不准猜；plan 前有 Simplicity／Anti-Abstraction／Integration-First 等 gate，過不了要在 Complexity Tracking 寫理由；checklist 像是 spec 的「unit test」。[SpecKit-SDD]
- 方法論還主張回饋迴圈：production 的指標與事故應更新 spec，效能瓶頸變成新的非功能需求。[SpecKit-SDD]

## Kiro：三份文件與工作流

- 每個 spec 產生三份檔案：`requirements.md`（bug 時為 `bugfix.md`）、`design.md`、`tasks.md`；工作流為 Requirements → Design → Tasks 三階段。[Kiro-Specs]
- Feature Specs 有兩種變體：Requirements-First（從系統行為出發，再產生 design 與 tasks；適合產品導向、架構彈性的情況）與 Design-First（從架構或偽代碼出發，再導出 requirements 與 tasks；適合有嚴格非功能需求、移植既有設計文件、先驗證技術可行性）。[Kiro-Feature]
- 兩者的取捨：Requirements-First 確保期望行為被明確寫下，實作可調整；Design-First 確保技術可行，需求可調整。[Kiro-Feature]
- `requirements.md` 使用 EARS 句型（`WHEN [條件] THE SYSTEM SHALL [行為]`），文件宣稱可測試、可追溯。[Kiro-Feature]
- 在進入 design 前可用 Analyze Requirements 檢查需求的矛盾、含糊、衝突與缺漏（文件列為 IDE 與 CLI 功能）。[Kiro-Feature] [Kiro-Specs]
- Quick Spec：一次產生三份文件、階段之間沒有核准關卡，只需先回答釐清問題；適合「理解充分、信任 Kiro 輸出」的功能。[Kiro-Feature] [Kiro-Specs]
- Bugfix Specs：以 `bugfix.md` 取代 requirements，內容為 current／expected／unchanged behavior 的 bug 分析，目標是找根因、設計修復並避免回歸。[Kiro-Specs]
- 執行 tasks.md 時，Kiro 會建依賴圖並分「wave」平行執行，同一 wave 內並行、wave 之間循序。[Kiro-Specs]
- Feature Specs 官方標明不適合：bug 修復（改用 Bugfix Specs）與沒有明確目標的探索式寫碼。[Kiro-Feature]
- 與 spec 分開的 memory bank 在 Kiro 叫 steering，預設產生 `product.md`、`structure.md`、`tech.md`（依 Böckeler 的使用經驗）。[Fowler-SDD]

## Böckeler 的評析與疑慮

- 分級判斷（作者自己嘗試，2025 年 9 月使用）：Kiro 大致是 spec-first；spec-kit 因為每個 spec 開一條 branch，較像「變更請求期間」的活文件，仍屬 spec-first；Tessl（當時 private beta）是唯一明說朝 spec-anchored、並探索 spec-as-source 的（code 頂端標 `// GENERATED FROM SPEC - DO NOT EDIT`）。[Fowler-SDD]
- 一套流程不適合所有大小：Kiro 修一個小 bug 產生 4 個 user story、16 條 acceptance criteria，作者形容是「用大鎚敲核桃」；spec-kit 用在約 3–5 點的功能也覺得過度，花在跑與審的時間夠作者用一般 AI 輔助寫完且更有掌控感。[Fowler-SDD]
- 審 markdown 比審 code 累：spec-kit 產生大量彼此重複、也與既有 code 重複的 markdown，作者「寧可審 code」；Kiro 只有三份檔稍好，但對小 bug 仍過於冗長。[Fowler-SDD]
- 虛假的掌控感：即使有模板、checklist、constitution，agent 仍常不照做，也會因過度遵守 constitution 條文而走過頭；spec-kit 的研究步驟已寫明那些是既有類別，agent 卻當成新規格又生成一次而產生重複。[Fowler-SDD]
- 作者對「大量前置 spec 設計」持懷疑，因為掌控感來自小步迭代；而小的工作包似乎與 SDD 的理念相左。[Fowler-SDD]
- 功能性與技術性 spec 難以分開：用 spec-kit 時作者常搞不清楚何時該停在功能層、何時加技術細節，文件與教學的解讀也不一致。[Fowler-SDD]
- 目標使用者不明：demo 把 user story、產品目標都交給開發者做；作者不確定這是否適合還很模糊的大型功能（那需要更多產品與需求專業與利害關係人參與）。[Fowler-SDD]
- 與 MDD 的類比：spec-as-source 讓作者想起 model-driven development；MDD 在商業應用上沒起飛。LLM 去掉了預定義語法與 code generator，代價是非確定性，也失去可剖析結構帶來的工具支援；作者擔心 spec-anchored／spec-as-source 兼有兩者的缺點：缺乏彈性與非確定性。[Fowler-SDD]
- 非確定性實測：同一份 Tessl spec 多次生成的 code 不同，要把 spec 越寫越具體才能提高重複性。[Fowler-SDD]
- 作者的結論：spec-first 在許多情境確實有價值，但「SDD」一詞定義未定；對精細流程可能把既有工作流照搬給 AI，放大審查負擔與幻覺，並引用德文 Verschlimmbesserung（越改越糟）。[Fowler-SDD]
- 時效提醒：該文寫於 2025 年 9 月試用、10 月發表，作者自己註明工具演進很快；spec-kit 與 Kiro 的現況以上兩節的官方文件為準。[Fowler-SDD]

## 與 superpowers、compound engineering 對照

下表只填來源有寫的內容；「來源未載明」表示該 README 沒有相關說明。

| | spec-kit | Kiro | superpowers | compound engineering |
|---|---|---|---|---|
| 起點 | `/speckit-constitution`（一次）再 `/speckit-specify` [SpecKit] | 選 Feature 或 Bug，再選 Requirements-First／Design-First [Kiro-Specs] [Kiro-Feature] | 偵測到你在建東西時先用 brainstorming 追問意圖 [Superpowers] | `/ce-brainstorm` 產出僅含需求的 unified plan [CompoundEng] |
| 主要產物 | spec、plan、tasks（及 research、contracts 等）[SpecKit-SDD] | requirements.md、design.md、tasks.md [Kiro-Specs] | 設計文件（專案才寫成文件）、2–5 分鐘粒度的 plan [Superpowers] | 一份從需求長到實作計畫的 plan artifact、`docs/solutions/` 的 learning [CompoundEng] |
| 人在哪裡把關 | 每個 skill 逐一呼叫並審查結果 [SpecKit]；方法論要求測試先經使用者核准 [SpecKit-SDD] | 各階段核准（Quick Spec 例外）[Kiro-Feature] | 設計分段呈現並簽核，之後 agent 可自主工作數小時 [Superpowers] | review 階段（`/ce-code-review` 為 report-only，local apply 需明確執行）[CompoundEng]；`/lfg` 則全程不中斷 [CompoundEng] |
| 經驗如何回流 | 方法論主張以 production 指標與事故更新 spec [SpecKit-SDD] | 來源未載明 | 來源未載明（README 的 `diagnosing-superpowers` 針對 session 除錯） [Superpowers] | `/ce-compound` 寫入 `docs/solutions/`，下一輪 brainstorm 與 plan 讀取 [CompoundEng] |

- superpowers 的 spec 是對話產物：「從對話裡引出 spec」，再交由 TDD 與 subagent 驅動的實作（每個任務一個 subagent、任務間 review，或 inline 執行再做一次整體 review）；README 沒有談 spec 長期保存或維護。[Superpowers]
- compound engineering 的重點不在 spec 本身，而在迴圈尾端「把學到的東西寫下來」，其稱 80% 心力放在規劃與 review、20% 在執行。[CompoundEng]
- 三者共通的設計是人在「執行前」審核計畫或設計；差別在於 spec-kit／Kiro 把中間文件做成固定檔案結構，superpowers 與 compound engineering 以 skill 串成流程。（本筆記歸納）

## 什麼時候值得用

- 來源明確支持的：需要先把需求或設計想清楚的複雜功能、多個實作任務、需要團隊協作文件、需求或設計需要迭代時，Kiro 建議用 Feature Specs；bug 與沒有明確目標的探索則不適合。[Kiro-Feature]
- 理解充分的功能可用 Quick Spec 省下階段關卡；有嚴格非功能需求或要先驗證可行性則從 Design-First 起手。[Kiro-Feature]
- Böckeler 的實測提醒：小 bug 與中小型功能套完整流程成本高於收益，工具至少應提供不同大小與類型變更的多種流程。[Fowler-SDD]
- 作者也指出 spec-first 的原則本身有價值，並建議把 spec 與跨 session 的 memory bank（規則檔）分開看。[Fowler-SDD]
- spec-kit 把 bug 修復與想法評估獨立成可選 extension，不必先走完整 SDD。[SpecKit]
- 若要把 spec 當長期資產（spec-anchored 以上），Böckeler 認為需先看 MDD 的教訓；作者也說目前缺乏長期使用的實例回報。[Fowler-SDD]
- 本筆記歸納：小改動走輕量流程、大且不確定的功能先確認是否有人能產出需求再上 SDD；這是對上述來源的綜合，不是任何來源的原話。

## 相關筆記

- [agentic-engineering-patterns.md](agentic-engineering-patterns.md)：agent 開發工作流的模式，SDD 是其中「先計畫再執行」的一種具體做法。
- [harness-engineering.md](harness-engineering.md)：規則檔、skill、hook 等 harness 元件；constitution 與 steering 屬於同類。
- [prompt-to-graph.md](prompt-to-graph.md)：把 prompt 流程改成圖狀流程，可對照 SDD 的固定階段。
- [../README.md](../README.md)：書籤區收有 superpowers 與 compound engineering。

## 來源

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| SpecKit | [Spec Kit README（GitHub）](https://github.com/github/spec-kit/blob/main/README.md) | 全文；廠商性質 |
| SpecKit-SDD | [Specification-Driven Development（spec-driven.md，GitHub）](https://github.com/github/spec-kit/blob/main/spec-driven.md) | 全文；廠商性質（命名為舊版 `/speckit.*`） |
| Kiro-Specs | [Specs（Kiro 文件）](https://kiro.dev/docs/specs/) | 全文；廠商性質 |
| Kiro-Feature | [Feature Specs（Kiro 文件）](https://kiro.dev/docs/specs/feature-specs/) | 全文；廠商性質 |
| Fowler-SDD | [Understanding Spec-Driven-Development: Kiro, spec-kit, and Tessl（Birgitta Böckeler，martinfowler.com，2025-10-15）](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) | 全文 |
| Superpowers | [obra/superpowers README](https://github.com/obra/superpowers/blob/main/README.md) | 部分（How it works、Basic Workflow、What's Inside；略過安裝）；廠商性質 |
| CompoundEng | [EveryInc/compound-engineering-plugin README](https://github.com/EveryInc/compound-engineering-plugin/blob/main/README.md) | 部分（Philosophy、The loop、Try it、Skills；略過安裝）；廠商性質 |
