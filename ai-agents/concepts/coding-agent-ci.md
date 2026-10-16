# Coding agent 接進 CI 與團隊流程

本篇整理 Claude Code、Codex、Cursor 三家把 coding agent 接進 PR、CI 與團隊流程的做法；資料取得日期 2026-10-14，內文的 `[簡稱]` 對應文末來源表。

## 三種整合形態

- PR 上 @mention 互動：留言叫 agent 回答、review 或改程式，結果回在同一則 PR／issue。Claude 用 `@claude`（interactive mode）[CCA-Docs]；Codex 用 `@codex review`，其他 `@codex ...` 留言會開 legacy cloud chat [Codex-Review]；Cursor 用 `cursor review` / `bugbot run`（Bugbot）[Cursor-Bugbot]，或 `@cursor` 啟動 cloud agent [Cursor-Cloud]。
- CI 裡無人值守：由 workflow 事件觸發，agent 當成一個 step 跑在 GitHub runner。Claude 提供 `prompt` 即進入 automation mode，可接任何 GitHub 事件含 cron [CCA-Docs]；Codex 用 `openai/codex-action` 跑 `codex exec` [Codex-Action] [Codex-GHA]。
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
