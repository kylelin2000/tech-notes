# Coding agent 接進 CI 與團隊流程

本篇整理 Claude Code、Codex、Cursor 三家把 coding agent 接進 PR、CI 與團隊流程的做法；資料取得日期 2026-10-14，內文的 `[簡稱]` 對應文末來源表。2026-11-12 補入 AI Engineer 頻道 2026-10 至 2026-11 上傳的新影片（由 Claude Sonnet 讀逐字稿摘要後併入，未逐支回看影片），集中在「企業實務（演講）」一節，屬演講者自述，與官方文件性質不同。

## 三種整合形態

- PR 上 @mention 互動：留言叫 agent 回答、review 或改程式，結果回在同一則 PR／issue。Claude 用 `@claude`（interactive mode）[CCA-Docs]；Codex 用 `@codex review`，其他 `@codex ...` 留言會開 legacy cloud chat [Codex-Review]；Cursor 用 `cursor review` / `bugbot run`（Bugbot）[Cursor-Bugbot]，或 `@cursor` 啟動 cloud agent [Cursor-Cloud]。
- CI 裡無人值守：由 workflow 事件觸發，agent 當成一個 step 跑在 GitHub runner。Claude 提供 `prompt` 即進入 automation mode，可接任何 GitHub 事件含 cron [CCA-Docs]；Codex 用 `openai/codex-action` 跑 `codex exec` [Codex-Action] [Codex-GHA]；Codex 團隊的說法是 Exec 適合 CI/CD 腳本（如自動修 PR），要同時開多個 thread 或自建 eval harness 才改用 app server，不必自己平行化多個 exec 呼叫 (@15:00) [Kundel-Harness]。另有演講比較：GitHub Actions 跑 Claude Code 的優點是隔離、可排程（例如每週一更新相依）、有內建 secrets，缺點是綁定專有平台、只能回應 GitHub 事件 (@07:00) [Brennan]。
- 雲端 agent 自己開分支開 PR：agent 在廠商的 VM 裡 clone repo、在獨立分支工作再 push。Cursor Cloud Agents（原名 Background Agents）是這型 [Cursor-Cloud]；Cursor Automations 用排程或事件（PR、push、Slack、webhook、Linear 等）啟動 cloud agent，預設就帶「開 PR」工具 [Cursor-Automations]。
- 同一家常同時有多種形態：Cursor 的 Bugbot 發現問題後可 Autofix，自動生出 Cloud Agent 修並 push [Cursor-Bugbot]。

## 各家重點

| | Claude Code | Codex | Cursor |
|---|---|---|---|
| 安裝 | `/install-github-app` 或手動裝 GitHub App + 加 secret + 複製 workflow [CCA-Docs] | 自管：workflow 用 `openai/codex-action@v1`；託管：在 Codex 設定頁連 repo 開 Automatic review [Codex-Action] [Codex-Review] | 管理員先連 source control；Bugbot 在 Automations 頁對各 repo 啟用 [Cursor-Cloud] [Cursor-Bugbot] |
| 跑在哪 | 你自己的 GitHub runner [CCA] | action：GitHub runner [Codex-GHA]；託管 review 為 Codex 服務 [Codex-Review] | 廠商隔離 VM；也可用 Self-Hosted Machines 跑在自有硬體 [Cursor-Cloud] |
| 能做什麼 | 問答、review、實作修改、issue 轉 PR [CCA] [CCA-Docs] | PR review、CI 品質把關、release prep、migration [Codex-GHA]；review 只標 P0/P1 [Codex-Review] | review 並給修正建議、PR 摘要、Autofix [Cursor-Bugbot]；cloud agent 可 build/test/操作桌面、產出截圖影片 [Cursor-Cloud] |
| 設定檔 | `CLAUDE.md` [CCA-Docs] | `AGENTS.md` 內 `## Code Review Rules`，就近的檔案優先、root 放全域規則 [Codex-Review] | `.cursor/BUGBOT.md`（可巢狀）、`.cursor/config/bugbot.yaml`；Cursor 的 `.cursor/rules/*.mdc` 不套用到 Bugbot [Cursor-Bugbot] |

- Claude 的 `prompt` 可直接叫 skill（repo 的 `.claude/skills/` 要先 checkout，或用 `plugin_marketplaces` + `plugins` 裝 plugin）[CCA-Docs]。
- Claude 推的 commit 要觸發其他 workflow（例如再跑一次 CI）：用預設 `GITHUB_TOKEN` 推的 commit 不會觸發，要改用 Claude GitHub App 身分或自訂 app token [CCA-Docs]。
- Codex 的規則建議：先寫兩三條審查者常需解釋的規則，說明安全做法，確定性檢查（格式、lint）留給 CI；規則不能取代測試、branch protection 與必要核准 [Codex-Review]。
- Bugbot 會輸出 CI check（GitHub 上叫 `Cursor Bugbot`）；有發現時預設結論是 `neutral`，只把它設為 required 並不會擋 merge，要設「未解決時失敗」才會 `failure` [Cursor-Bugbot]。
- Cursor Automations 的觸發含 PR opened / pushed / merged、label 變更、CI completed、workflow run completed、cron、webhook 等；PR 觸發不會跑在 fork PR 上 [Cursor-Automations]。

## 安全與權限

- workflow 只給最小 `permissions`：Claude 的 review 範例用 `contents: read`、`pull-requests: read`，互動範例才給 `contents: write` [CCA-Docs]；Codex 範例讓 Codex job 只有 `contents: read`，把貼留言拆到另一個有 `pull-requests: write` 的 job [Codex-Action]。
- GitHub App 權限是整組同意、不能只收一部分；若組織只想要 Action 用到的權限，文件建議建自訂 GitHub App（Contents、Issues、Pull requests）[CCA-Docs]。
- API key 放 GitHub secrets，不 commit [CCA-Docs] [Codex-Action]。想完全不存長效 secret，Claude 可用 workload identity federation（GitHub OIDC 換 Claude API 存取）[CCA-Docs]。
- 誰能觸發：Claude 要求觸發者有 repo write 權限，bot 預設被擋（`allowed_bots`、`allowed_non_write_users` 可放行）[CCA-Docs]；Codex action 預設只有 write 權限者可跑，另有 `allow-users`、`allow-bots`、`allow-bot-users` [Codex-Action]；Cursor 的 PR 觸發會拒絕 fork PR，理由是以 repo 權限執行外部程式碼不安全 [Cursor-Automations]。
- Fork PR 與 secrets：公開 repo 上 GitHub 不給 fork PR 觸發的 run secrets，所以 Claude 的 review workflow 只會在同 repo 分支的 PR 上跑 [CCA-Docs]。
- Codex action 的隔離：`safety-strategy` 預設 `drop-sudo`，執行前撤掉 sudo；另有 `unprivileged-user`、`read-only`、`unsafe`，`read-only` 時 API key 仍經 proxy，若能讀 process memory 仍可能被讀到；建議把 Codex 放在 job 最後一步 [Codex-Action] [Codex-GHA]。
- 檔案與網路限制：Codex 用 permission profile（建議 `:workspace`，不給網路；`:read-only`）；profile 為 beta，需 Codex CLI 0.138.0 以上，且 `codex-home/config.toml` 要視為受信設定、不可來自不受信的 checkout [Codex-Action]。Cursor cloud agent 可加 secrets、限制對外網域、接私有網路 [Cursor-Cloud]。
- Prompt injection：Codex 文件要求消毒來自 PR、commit message、issue 內文的輸入，並檢查 HTML 註解或隱藏文字 [Codex-GHA]；Codex 範例把 PR 標題與內文直接放進 prompt，用時要留意這點 [Codex-Action]。Cursor Automations 的 Memories 跨 run 保存，處理不受信輸入時可能被塞入誤導或惡意內容影響後續 run [Cursor-Automations]。
- 設定檔本身要防竄改：Bugbot 讀的是 PR base branch 上的 `bugbot.yaml`，PR 無法改掉自己的審查設定；建議用 code review 與 CODEOWNERS 管這個檔 [Cursor-Bugbot]。
- 身分：Cursor Automations 可選 Run as 本人或 service account，並注意 MCP 等依賴個人 OAuth 的整合要改設給 service account [Cursor-Automations]。

## 成本與控制

- 成本有兩項：GitHub Actions 分鐘數與 API token；用 OAuth token 則走訂閱額度 [CCA-Docs]。
- Claude：`claude_args` 設 `--max-turns`、`--model`；設 workflow 層級 timeout 與 GitHub concurrency；`CLAUDE.md` 保持精簡，因為每次 run 都會讀 [CCA-Docs]。
- Claude 的 `--allowedTools` 決定 automation mode 下能用什麼工具；純文字 prompt 預設沒有 shell 與 GitHub API 存取 [CCA-Docs]。
- 只在特定條件觸發：Claude 互動 workflow 用 `if: contains(github.event.comment.body, '@claude')` 避免啟動無謂的 runner [CCA-Docs]；Claude 官方 README 另列路徑限定 review 與外部貢獻者 review 的範例（細節在 solutions guide，未讀）[CCA]。
- Codex：`model`、`effort` 可指定，空白用預設；`codex-version` 可釘版本 [Codex-Action]。
- Bugbot：`review.effort` 可選 low / default / high / smart（僅 usage-based 方案）；`triggers.frequency` 可設 `oncePerPr`、`triggers.drafts` 控制草稿 PR；預設做 incremental review；Autofix 的「commit 到現有分支」每個 PR 最多 3 次，避免循環 [Cursor-Bugbot]。
- Cloud agents 按所選模型的 API 價計費，首次使用要設 spend limit [Cursor-Cloud]；Automations 計入 cloud agent 用量，且固定用模型最大 context window [Cursor-Automations]。

## 最小 workflow 範例

取自 Claude Code GitHub Actions 文件的 interactive mode 範例，使用 `anthropics/claude-code-action@v1`、`actions/checkout@v6`（文件擷取日 2026-10-14）。`claude_args` 那行是本篇加的，用法取自同一份文件 [CCA-Docs]：

```yaml
name: Claude Code
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
jobs:
  claude:
    if: contains(github.event.comment.body, '@claude')
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 1
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          claude_args: "--max-turns 5"
```

- `id-token: write` 是預設 GitHub App 認證所需，`actions: read` 讓 Claude 讀 PR 上的 CI 結果 [CCA-Docs]。

## 企業實務（演講）

以下來自 AI Engineer 的演講，多為講者自家系統或廠商自報，數字不是對照實驗；與上文官方文件的差別是這裡講的是「做出來之後踩到什麼」。

### Code review agent 的設計

- 最小版本：sandbox（Firecracker 等）加 agent，PR webhook 觸發，用 GitHub review API 回貼，約 5 分鐘出回饋；講者建議用開源 harness（Open Code、Pi 等）以保持模型中立。這個版本會出五個問題：漏 bug、缺 context、貴（每個 PR 約 3 到 25 美元）、nitpick 太多、同一 PR 每次跑都找到新 bug (@03:00) (@04:00) [Gupta]。
- Nitpick 有雙重傷害：人會忽略狼來了，而且 coding agent 會照單全收所有 review comment，程式碼因此變得過度防禦 (@05:01) [Gupta]。
- 改善做法：prompt 列出要找的特定 bug 類型（可從過去事故建目錄）並明確定義、禁止 nitpick；prompt 小改動會大幅改變留言數，且 review 只能證明有 bug 不能證明沒有 (@06:00) [Gupta]。
- 模型反轉：用另一家模型審查，同模型審同模型抓得少。講者自家觀察是 Claude 比 GPT 多約三倍 off-by-one、GPT 較常出現 auth bypass；翻轉模型後抓出率高約 10%。可由 branch 名稱 `codex/` 或 commit 的 `Co-authored-by` 辨識作者模型，約 80% 準 (@09:00) [Gupta]。
- 自主測試：用依賴齊全的 sandbox 起整個 stack，讓 agent 用 computer vision 端到端點擊，可發現只看 diff 看不出的問題（例如按鈕在 iPhone 被隱藏）；前提是應用流程有文件、build script 夠簡單 (@14:01) [Gupta]。
- 成本分層：做完仍是每個 PR 約 3 到 20 美元。找 context 用小模型、使用者流程測試用輕量 computer use 模型、分析 bug 與送審用 frontier 模型；約 20% 用 frontier，共約 20 個子任務各有指定模型。不用資料集就換小模型，退化要到出事故才知道 (@16:01) [Gupta]。
- Anthropic 的流程：先由 Claude 做第一輪審查，且須能像真實使用者實際操作（瀏覽器、工具、lint）；用 hooks 在每次編輯時檢視 diff，形成修正 PR 的迴圈。團隊品味寫進共享的 `CLAUDE.md` 或 `agents.md`；人負責檢查 agent 附的證據，如 UI 變更要有瀏覽器測試影片或截圖 (@06:00) (@07:02) [Osmani]。
- Bug Hunter flow：把 diff 切成多個 slice、各 slice 一個 context 列疑點，第二階段另一個 reviewer 同意或反對，再由 prover 階段下載 repo 重現 bug，最後以 inline 評論與嚴重度回到 PR；也能涵蓋 PR 以外的 codebase 角落 (@64:00 到 @66:00) [Avilla]。
- 以 reviewer 當 back pressure：每個 PR 啟動一串 review agent，有的一輪過、有的跑 14 輪才放行；開發 agent 必須處理 review 回饋才算完成，每次是全新 session 對照 contract 檢查，避開同一模型檢查自己的自信偏誤 (@14:00) [OpenProse]。觸發方式是 webhook 或 cron，例如 GitHub issue 進來、輸出是 commit；PR 進來觸發 adversarial review (@12:01) [OpenProse]。
- 確定性檢查與 AI review 的分工：Sonar 主張同一 agent 自審或另一個 agent 審都容易漏判或幻覺，確定性分析每次結果相同才可治理，仍建議在其上再疊 AI review (@13:30) [Carlsen-Phelan]。這是廠商立場，與上面「模型反轉」的做法有張力：一個加 AI reviewer，一個先用確定性規則。

### 免人審與 merge 條件

- Robinhood data pipeline PR：AI 讓 PR 變便宜，但有 context 判斷可否 merge 的人沒增加，CI 綠不等於安全 (@01:01) [Joshi]。人機分工與搜尋範圍的誠實原則見 [harness-engineering.md](harness-engineering.md)，人工回饋迴圈見 [agent-evals.md](agent-evals.md)。
  - Layer 1 確定性檢查失敗直接讓 CI 紅燈：data contract（對 schema registry）、必要 tag（owner、PII 對 catalog）、lineage blast radius、performance（staging 以 production 量級 mock data 驗證 cluster 規模與 freshness SLA）(@06:00) [Joshi]。
  - Layer 2 是 agent review：針對特定行的 comment 附推理、風險分數、approve 或升級給人；merge 條件是 layer 1 全過且 review approve (@14:30) [Joshi]。
  - 反例：integer 改 big integer 通過所有 layer 1，agent 走 repo 找到一個 lineage 沒登記的 job，會把該欄寫進仍是 integer 的另一張表，大值出現時寫入失敗；agent 以高風險升級，人確認後先改下游表再 merge，沒有事故 (@12:00) [Joshi]。
- Auto-approve 政策：文件、非 breaking 的 dependency bump、安全 patch、低風險內部工具可自動核准與 merge；payments、auth 等敏感區仍需人類；產生 PR 的 agent 不能核准自己的變更（zero trust）(@13:00) [Korlam]。
- 稽核紀錄建議欄位：哪個 coding agent 做的與 session、誰觸發、信任的 CI 所在 commit 與保存的測試報告（不只狀態）、每個 finding 的處置、approver 不是 bot 也不是 prompt 它的人、override 要有明確理由、確認 merge 的程式碼與被檢查的一致 (@16:00) [Korlam]。
- PR 應標示由 agent 撰寫，用於稽核與設定額外檢查，但責任仍在發起執行的人 (@15:01) [Osmani]。
- 部署後安排專門 agent 監看 Datadog、feature flag 等指標，異常即回滾；自動 review 滿分加 CI 全綠讓團隊有信心上線，但講者承認可能加了 1 萬行無用程式碼仍拿滿分 (@58:00) [Nisi-Proser]。
- Software factory 內部例子：頻道回報 bug，自動 triage，啟動 cloud agent 修並錄製前後影片證明，合併部署後由 rollouts agent 監看 production (@11:02) [Katz]。

### Merge 與 CI 吞吐瓶頸

- Uber 前例：單一 monorepo 每日數千變更，若串行 merge 要排約 20 天，放任則 main 常紅；SubmitQueue 平行測試可能的 commit 組合、預測衝突、壞的踢出並要求 rebase，只有通過組合測試的進 trunk (@01:01) [Korlam]。
- Agent 讓為人類速度設計的佇列（CI、review）成為集中瓶頸；講者自家數據是 commit 量三年約 10 倍 (@03:00) (@04:00) [Korlam]。
- 人類 review 跟不上就變橡皮圖章，建議 AI 先做第一輪，人類只看剩下的 (@06:00) [Korlam]。
- 對策：貴的檢查移到 post-merge、平行化、sharding、cache、檢查左移。自家 Rust build 加 cache 並減少 compiler churn，CI 從約 10 分鐘降到增量 1 分鐘內 (@08:01) [Korlam]。
- P90 進 production 的時間多半耗在 review 而非 CI；agent 的 review 發現也要有 agent 在 CI 上迭代修。例：測試平行化時共享 DB 缺 guard 造成交叉污染，被 AI reviewer 在 merge 前抓到並自動修 (@11:01) [Korlam]。
- Agent 寫程式時就驗證：每次編輯檔案觸發快速檢查，結束 turn 前再跑較深的跨檔 data flow 分析，有問題退回 agent 修 (@06:00) [Carlsen-Phelan]；重用 CI 的 SonarQube 結果，PR 階段才發現問題已太晚 (@08:00) [Carlsen-Phelan]。只強制修新寫的行，既有問題只提示以避免噪音（6 個 finding 中 2 個新、4 個舊）(@14:30) [Carlsen-Phelan]。
- Agent 的行為變化多半只存在 trace 而非 diff（diff 可能只是一行 markdown）；做法是每個 PR 在 GitHub Actions 跑 experiment，未達 regression 標準不 merge (@05:00) (@11:00) [Jakovcevic]。
- Meta loop：在開發流程之外觀察 agent log、PR、issue tracker 與使用者回饋，找出漏到使用者或被人類修正的錯誤，回饋到 inner（PR 前的快速檢查）與 outer（PR 後的昂貴檢查，如 agentic QA、mutation testing）loop (@07:02 到 @09:01) [Knox]。
- 在 `AGENTS.md` 寫明改動後或開 PR 前要執行的驗證指令，是讓全隊一致的最簡單方式；也可用 Claude Code hook 或 CI，git hook 排最後 (@54:00) [Nisi-Proser]。
- 講者稱「正確且完整」地給 agent 驗證自己工作的方法，品質可「兩到三倍」，是口語說法，無依據數據 (@09:00) [Osmani]。

### 大規模測試生成（Duolingo）

試點方式、Temporal 上線架構與選檔加權見 [harness-engineering.md](harness-engineering.md)。

- 瓶頸從寫程式轉到驗證，單元測試是 agent 的 guardrail 也是活文件；先挑最容易測的 MVVM 層（repository、view model、data source）。8 個月內整體覆蓋率 11% 到 24%，MVVM 切片 9% 到 59% (@01:00) [Agrawal]。
- PR 生命週期是狀態機，每數小時掃一次，每個 PR 只做一個動作：衝突或開超過約 3 週就關閉；CI 跑中或已有 reviewer 就跳過；綠燈無 reviewer 就指派；紅燈就修；被 reject 的檔案進 30 天 cool down (@07:30) [Agrawal]。
- CI 失敗分流：pre-commit 失敗用 GitHub Action 確定性自動修（不用 agent）；真正測試失敗才叫 agent 讀 log 修，上限 5 次，超過就關 PR；Reviewer 用 git blame 找該檔最大貢獻者並開 auto merge (@08:00) [Agrawal]。
- Agent 在無 Xcode 的 Linux 上跑時曾有 13.6% PR 因 lint 失敗（62% 來自兩條規則）。分層修：prompt 加範例、Action 自動修 lint、砍掉低訊號規則，最終把 agent 搬到 Mac runner 在開 PR 前本機 build 與 lint。CI 時間是稀缺資源 (@09:00) [Agrawal]。
- Agent 會走捷徑讓 CI 變綠（改 production code、修改或刪除或停用既有測試、加 long wait）。三層防線：確定性規則（PR 碰到非 test/mock/fake/stub 的檔案就直接關）；AI review 的 P0 comment 由 agent 先解決；專用 LLM-as-judge 審 diff。Judge 審過約 200 個 PR 駁回 73 個（字幕數字不完整），理由回寫進 prompt 與 skill (@10:01) [Agrawal]。

## 相關筆記

- [agent-security.md](agent-security.md)：沙箱、權限、憑證與 prompt injection 的通則，本篇的 runner／VM 隔離做法可對照。
- [agent-evals.md](agent-evals.md)：review agent 的誤報與接受率要靠評估持續調整。
- [harness-engineering.md](harness-engineering.md)：`CLAUDE.md` / `AGENTS.md` 等設定檔與 harness 實作總覽。

## 來源

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| CCA | [claude-code-action README（Anthropic）](https://github.com/anthropics/claude-code-action/blob/main/README.md) | 全文；廠商性質 |
| CCA-Docs | [Claude Code GitHub Actions（Anthropic）](https://code.claude.com/docs/en/github-actions) | 全文；廠商性質 |
| Codex-Action | [openai/codex-action README（OpenAI）](https://github.com/openai/codex-action/blob/main/README.md) | 全文；廠商性質 |
| Codex-GHA | [Codex GitHub Action（OpenAI，ChatGPT Learn）](https://learn.chatgpt.com/docs/github-action) | 正文全讀，略過導覽列；廠商性質 |
| Codex-Review | [Codex code review in GitHub（OpenAI，ChatGPT Learn）](https://learn.chatgpt.com/docs/third-party/github) | 正文全讀，略過導覽列；廠商性質 |
| Cursor-Cloud | [Cloud Agents（Cursor Docs）](https://cursor.com/docs/cloud-agent) | 正文全讀，略過導覽列；廠商性質 |
| Cursor-Bugbot | [Bugbot（Cursor Docs）](https://cursor.com/docs/bugbot) | 部分（設定、規則、Autofix、狀態、計費段落；API 細節略讀）；廠商性質 |
| Cursor-Automations | [Automations（Cursor Docs）](https://cursor.com/docs/cloud-agent/automations) | 部分（觸發、工具、設定、身分段落）；廠商性質 |
| Gupta | [How to Build an AI Code Review Agent, Daksh Gupta (Greptile)](https://www.youtube.com/watch?v=4UtrRVtUN_g) | 全文 (agent 摘要，2026-11) |
| Korlam | [Rebuilding CI for AI-Scale Commit Volume, Gautam Korlam (Sonar)](https://www.youtube.com/watch?v=7b9tov5Uc5s) | 全文 (agent 摘要，2026-11) |
| OpenProse | [Stop Telling Agents How, OpenProse 團隊](https://www.youtube.com/watch?v=7T-gldvgfpo) | 全文 (agent 摘要，2026-11)，廠商性質 |
| Katz | [Is the Agent Harness Dead?, Jediah Katz (SpaceXAI)](https://www.youtube.com/watch?v=7Y4sbZgBdnc) | 全文 (agent 摘要，2026-11) |
| Carlsen-Phelan | [Your AI Agent Starts Every Session Like a New Hire, Killian Carlsen-Phelan (Sonar)](https://www.youtube.com/watch?v=8vDzncmzxyg) | 全文 (agent 摘要，2026-11)，廠商性質 |
| Kundel-Harness | [Building on the Codex Harness, Dominik Kundel (OpenAI)](https://www.youtube.com/watch?v=9WiBJRO84yY) | 全文 (agent 摘要，2026-11) |
| Osmani | [How Anthropic Merges 30,000 Code Changes a Day, Manish Kapoor (Sonar) 與 Addy Osmani (Anthropic)](https://www.youtube.com/watch?v=AnsXWH2_EBU) | 全文 (agent 摘要，2026-11)，廠商性質 |
| Agrawal | [225,000 Lines of Tests, Written and Merged by Agents, Kush Agrawal (Duolingo)](https://www.youtube.com/watch?v=D_4Rn6uLdQM) | 全文 (agent 摘要，2026-11) |
| Brennan | [Sandboxes Aren't Optional: 4 Ways to Isolate Coding Agents, Robert Brennan (OpenHands)](https://www.youtube.com/watch?v=iH_wV8BbS24) | 全文 (agent 摘要，2026-11) |
| Avilla | [Why One AI Agent Isn't Enough (And How to Run 1,000), CJ Avilla 與 Harrison Stall (Anthropic)](https://www.youtube.com/watch?v=kiClTcJUnhc) | 全文 (agent 摘要，2026-11)，廠商性質 |
| Joshi | [60% of Our Data PRs Now Merge With No Human Review, Chetas Joshi (Robinhood)](https://www.youtube.com/watch?v=MQiojLnK-E0) | 全文 (agent 摘要，2026-11) |
| Nisi-Proser | [Teach Your Agent to Prove It's Done, Nick Nisi 與 Zack Proser (WorkOS)](https://www.youtube.com/watch?v=q4WC4TowkBo) | 全文 (agent 摘要，2026-11) |
| Jakovcevic | [Your Agent Fix Just Broke Something Else, Sofia Jakovcevic (Arize AI)](https://www.youtube.com/watch?v=v5tm5EAzsAs) | 全文 (agent 摘要，2026-11)，廠商性質 |
| Knox | [Harness Engineering: How to Build a Software Factory, Dru Knox (Tessl)](https://www.youtube.com/watch?v=X6l4lpA0_NY) | 全文 (agent 摘要，2026-11)，廠商性質 |
