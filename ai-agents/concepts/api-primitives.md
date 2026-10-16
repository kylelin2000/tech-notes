# API 層基本元件：structured outputs、tool calling、prompt caching

本篇整理在 Claude API 與 OpenAI API 上建 agent 時最常碰到的三個 API 層元件：structured outputs、tool calling schema、prompt caching。來源全是兩家的官方文件（廠商性質），資料取得日期 2026-10-14；模型名稱、價格與限制以文件當時的內容為準，會隨版本變動。內文的 `[簡稱]` 對應文末「來源」表。

## Structured outputs

- Claude 有兩個互補功能：JSON outputs（參數 `output_config.format`，`type: "json_schema"`）控制 Claude 的回應格式；strict tool use（工具定義加 `strict: true`）驗證工具名稱與輸入。兩者可獨立使用，也可在同一個請求合用。[Claude-StructOut]
- Claude 靠 constrained decoding（編譯 grammar 後約束取樣）保證輸出符合 schema。舊的 `output_format` 參數已搬到 `output_config.format`，不再需要 beta header；`output_format` 已棄用。[Claude-StructOut]
- OpenAI 有兩種形式：function calling（工具定義加 `strict: true`），以及 `json_schema` response format（Responses API 寫成 `text: { format: { type: "json_schema", "strict": true, "schema": ... } }`）。前身 JSON mode（`text.format` 設 `{ "type": "json_object" }`）只保證是合法 JSON，不保證符合 schema，官方建議能用 Structured Outputs 就不要用 JSON mode。[OpenAI-StructOut]
- OpenAI 的選擇準則：模型要連接系統內的工具、函式、資料，用 function calling；要結構化模型回覆使用者時的輸出，用 `text.format`。[OpenAI-StructOut]
- Claude 的對應區分（本筆記歸納）：JSON outputs 管「Claude 說什麼」，strict tool use 管「Claude 怎麼呼叫函式」；agent 流程需要可靠的工具參數加結構化的最終回覆時兩者合用。[Claude-StructOut]

### 支援的 JSON Schema 子集

- Claude 支援：基本型別、`enum`（僅字串、數字、布林、null）、`const`、`anyOf` 與 `allOf`（`allOf` 搭配 `$ref` 不支援）、`$ref` / `$def` / `definitions`（不支援外部 `$ref`）、`default`、`required`，以及 `date-time`、`date`、`uuid` 等字串 `format`；`minItems` 只支援 0 與 1。物件必須設 `additionalProperties: false`。[Claude-StructOut]
- Claude 不支援：遞迴 schema、數值限制（`minimum`、`maximum`、`multipleOf`）、字串長度限制（`minLength`、`maxLength`）、正規表達式的 backreference、lookahead／lookbehind、`\b`。用到不支援的功能會得到 400 錯誤。[Claude-StructOut]
- Claude 的複雜度上限（每個請求合計）：`strict: true` 的工具最多 20 個、optional 參數最多 24 個、使用 union type（`anyOf` 或型別陣列）的參數最多 16 個；超過內部上限會回 400「Schema is too complex for compilation」，編譯逾時上限 180 秒。降低複雜度的建議依序為：只對關鍵工具設 strict、減少 optional 參數、攤平巢狀結構、拆成多個請求。[Claude-StructOut]
- Claude 的輸出屬性順序：required 屬性在前、optional 在後；順序重要時就全部設 required。enum 與 `const` 字串的大小寫不保證完全一致（例如首字母），要不分大小寫比對。[Claude-StructOut]
- OpenAI 支援：String、Number、Boolean、Integer、Object、Array、Enum、`anyOf`；字串可用 `pattern` 與 `format`，數值可用 `multipleOf` 與 `minimum` / `maximum` 系列，陣列可用 `minItems` / `maxItems`；支援 definitions 與遞迴 schema。[OpenAI-StructOut]
- OpenAI 的硬性規定：根物件必須是 object 且不能是 `anyOf`；所有欄位都要列在 `required`（要表達 optional 就用與 `null` 的 union type）；每個物件都要 `additionalProperties: false`；輸出順序與 schema 的 key 順序相同。[OpenAI-StructOut]
- OpenAI 的大小上限：最多 5000 個物件屬性、10 層巢狀；屬性名、定義名、enum 值、const 值的總字數不超過 120,000 字元；enum 值總數最多 1000。尚不支援 `allOf`、`not`、`if` / `then` / `else` 等組合關鍵字；fine-tuned 模型另外不支援字串長度、`pattern`、`format`、數值與陣列範圍限制。[OpenAI-StructOut]
- 兩家都有首次請求延遲：Claude 首次使用某個 schema 要編譯 grammar，編譯結果從最後使用起快取 24 小時，改 schema 結構或工具集合會使快取失效，只改 `name` 或 `description` 不會；OpenAI 說首次請求會多一段處理 schema 的延遲，之後同 schema 不再多出延遲。[Claude-StructOut] [OpenAI-StructOut]

### 失敗與拒答時的行為

- Claude 拒答時 `stop_reason` 為 `"refusal"`，回 200 並照生成的 token 計費，輸出可能不符合 schema；`stop_reason: "max_tokens"` 表示被截斷、輸出可能不完整，要調高 `max_tokens` 重試。要求在欄位裡寫「思考過程」可能觸發 `reasoning_extraction` 拒答，改要求簡短說明。[Claude-StructOut]
- OpenAI 拒答時回應會多一個 `refusal` 欄位；拒答或 max tokens 截斷都可能產生不符合 schema 的回應，程式要分支處理。[OpenAI-StructOut]
- 輸入與 schema 不相干時，模型仍會努力貼合 schema，可能產生幻覺值；OpenAI 建議在 prompt 寫明無法完成時要回傳空值或特定句子。Structured Outputs 仍可能有內容錯誤，只保證格式。[OpenAI-StructOut]
- Claude 的相容性限制：與 citations 不相容（開啟會回 400），也與 message prefilling 不相容；grammar 只套用在 Claude 的直接輸出，不套用於 tool call、tool result 與 thinking。[Claude-StructOut]
- Claude 的 `output_config.format` 會自動多注入一段說明輸出格式的 system prompt（input token 略增），且更動 `output_config.format` 會使該對話的 prompt cache 失效。[Claude-StructOut]

## Tool calling schema

- Claude 的工具分兩類，差別在執行位置：client tools（含自訂工具與 Anthropic 定義 schema 的 `bash`、`text_editor`）在你的應用程式執行，Claude 回 `stop_reason: "tool_use"` 與一或多個 `tool_use` block，你執行後用 `tool_result` 送回；server tools（`web_search`、`web_fetch`、`code_execution`、`tool_search`）在 Anthropic 的基礎設施執行，不需要你處理執行。[Claude-ToolUse]
- Claude 的自訂工具定義含 `name`、`description`、`input_schema`（JSON Schema，含 `properties` 與 `required`）；加 `strict: true` 可保證呼叫符合 schema。[Claude-ToolUse]
- OpenAI 的 function 定義含 `type`（固定 `function`）、`name`、`description`、`parameters`（JSON Schema）、`strict`；另有以 namespace 分組相關工具，以及接受自由文字輸入、可用 Lark 或 regex grammar 約束的 custom tools。[OpenAI-FnCall]
- OpenAI 的 strict mode：官方建議一律開啟；要求每個物件 `additionalProperties: false`、所有欄位都列入 `required`（optional 用 `null` union）。省略 `strict` 時，Responses API 會嘗試把 schema 正規化成 strict，不行則退回非 strict（回應中 `strict` 顯示 `false`），Chat Completions 預設非 strict。[OpenAI-FnCall]
- tool_choice：Claude 文件中可見 `auto`（預設，由模型決定）、`any`、`tool`、`none`；要強制呼叫工具不要靠 prompt，而是設 `tool_choice`。OpenAI 有 `auto`、`required`（至少呼叫一個）、強制單一函式（`{"type": "function", "name": ...}`）、`allowed_tools`（限制可呼叫的子集），以及 `"none"`。[Claude-ToolUse] [OpenAI-FnCall]
- 平行呼叫：Claude 在 `tool_choice` 內設 `disable_parallel_tool_use: true`（範例為 `{"type": "auto", "disable_parallel_tool_use": true}`）限制每回合最多一個工具呼叫；OpenAI 設 `parallel_tool_calls: false`，確保零個或一個。OpenAI 提醒回應可能含零、一或多個呼叫，程式應假設有多個。[Claude-ToolUse] [OpenAI-FnCall]
- 回傳結果：Claude 在下一個 user 訊息放 `tool_result` block，帶 `tool_use_id` 與 `content`（字串，或 `text`、`image`、`document`、`search_result` block 陣列）；`tool_result` 必須緊接在對應的 `tool_use` 之後，且在 content 陣列中排在任何文字之前，否則回 400。[Claude-ToolCalls] OpenAI 在 `input` 附加 `function_call_output`，以 `call_id` 對應（輸出通常是字串，格式自訂，也可傳影像或檔案物件陣列；無回傳值時回 `"success"` 之類的字串）。推理模型（如 GPT-5、o4-mini）回應中的 reasoning items 也必須連同 tool output 一起送回。[Claude-ToolUse] [OpenAI-FnCall]
- 錯誤回傳：Claude 在 `tool_result` 設 `is_error: true`，`content` 放錯誤訊息；官方建議寫出哪裡錯、下一步該怎麼做（例如 `"Rate limit exceeded. Retry after 60 seconds."`），不要只寫 `"failed"`。缺必填參數時也可用 `is_error` 回報，Claude 會補上資訊再試；server tools 的錯誤由 Claude 自行處理。[Claude-ToolCalls] OpenAI 文件只說結果字串的格式自訂，可含錯誤碼，模型會自行解讀。[OpenAI-FnCall]
- 工具定義本身計入 input token：Claude 使用工具時會自動加一段 tool use system prompt（例如 Claude Sonnet 5.5 在 `auto` / `none` 為 286 tokens，Claude Sonnet 5 為 354 tokens），另加 `tools` 參數、`tool_use` 與 `tool_result` block 的 token；OpenAI 的函式定義也計入 context 與 input 計費，建議開局可用函式少於 20 個（軟性建議）。[Claude-ToolUse] [OpenAI-FnCall]
- 工具太多時：OpenAI 的 `tool_search` 搭配 `defer_loading: true` 延後載入（`gpt-5.4` 以後支援）；Claude 對應的 server tool 是 `tool_search`。[OpenAI-FnCall] [Claude-ToolUse]

## Prompt caching：成本與延遲

### 機制

- Claude：快取整個前綴，順序為 `tools`、`system`、`messages`，到被 `cache_control` 標記的 block 為止。有兩種開法：頂層放一個 `cache_control: {"type": "ephemeral"}`（automatic caching，斷點自動落在最後一個可快取 block 並隨對話前移），或在個別 content block 上放 `cache_control`（explicit breakpoints，最多 4 個；automatic 會佔一個名額）。[Claude-Caching]
- Claude 的寫入只發生在斷點，讀取則從斷點往前回看最多 20 個 block，找先前請求寫過的項目；斷點應放在「跨請求內容相同的最後一個 block」，若斷點在每次都變的 block（時間戳、本次使用者訊息）上，每次都是新寫入、永遠讀不到。並行請求要等第一個回應開始後，快取才可用。[Claude-Caching]
- OpenAI：預設自動啟用，不需改程式。GPT-5.6 以後支援 implicit（預設，斷點放在最近一個合格訊息結尾）與 explicit 模式（`prompt_cache_options.mode: "explicit"`，在 input 訊息的 content block 加 `prompt_cache_breakpoint: { "mode": "explicit" }`，每個請求最多 4 個寫入）；較早的模型只有 implicit。[OpenAI-Caching]
- OpenAI 的 explicit-only 模式下，最後一個斷點之後的內容以一般未快取 input 價計費、不收寫入費，適合排除不會重用的變動內容。只靠 implicit 時，「共用前綴」不等於「已快取前綴」：若靜態內容後面直接接動態內容，要在靜態內容後加 explicit 斷點。[OpenAI-Caching]
- OpenAI 的快取位於單一機器，路由由系統處理；GPT-5.6 以前建議用穩定的 `prompt_cache_key` 讓相關請求導向同一快取（每個 key 約 15 requests/分鐘為宜），GPT-5.6 以後 key 只用於分開各客戶的快取計帳，也可防止跨使用者探測快取命中。[OpenAI-Caching]
- 兩家共通：快取不影響輸出生成；OpenAI 另說明快取的輸入 token 仍計入 tokens-per-minute 限制。[Claude-Caching] [OpenAI-Caching]

### 最小長度、TTL 與計價

- 最小可快取長度：Claude 為 512 tokens（Claude Sonnet 5.5、Opus 5.5、Opus 5、Haiku 5.5 等）、1,024（Claude Sonnet 5、Opus 4.8）、2,048（Claude Opus 4.7）、4,096（Claude Opus 4.5 / 4.6、Haiku 4.5）；較短的提示不會快取，也不報錯。OpenAI GPT-5.6 以後為 1,024 個可見 input tokens，較早的模型依請求設定而異。[Claude-Caching] [OpenAI-Caching]
- TTL：Claude 預設 5 分鐘，每次使用免費刷新；`cache_control` 加 `"ttl": "1h"` 可用 1 小時。時間從寫入或讀取該項目的請求「開始」算起，不是回應結束。OpenAI GPT-5.6 以後用 `prompt_cache_options.ttl`，唯一值也是預設 `30m`（最近一次寫入或重用起至少 30 分鐘）；較早的模型用 `prompt_cache_retention`：GPT-5.5 與 GPT-5.5 Pro 只支援 `24h`（通常約 30 分鐘，最久 24 小時），其他較早的模型為 `in_memory`（閒置約 5 到 10 分鐘，最久一小時）或 `24h`。[Claude-Caching] [OpenAI-Caching]
- Claude 的倍率：5 分鐘寫入為基本 input 價的 1.25 倍，1 小時寫入為 2 倍，讀取為 0.1 倍；例外是 Claude Opus 5.5 與 Claude Sonnet 5.5 的讀取為 0.05 倍，Claude Fable 5.1 與 Claude Mythos 5.1 為 0.025 倍。[Claude-Caching]
- Claude 的實際價格（每百萬 token）：Claude Sonnet 5.5 基本 $2、5 分鐘寫入 $2.50、1 小時寫入 $4、命中 $0.10；Claude Opus 5 基本 $5、寫入 $6.25 / $10、命中 $0.50。斷點本身不收費，只依實際寫入與讀取計費。[Claude-Caching]
- OpenAI GPT-5.6 以後：寫入為未快取 input 價的 1.25 倍，讀取為 0.1 倍（GPT-6.1 Sol 為 0.05 倍）；寫一次再完整重用一次共 1.35 倍，雙倍處理未快取則為 2 倍。較早的模型沒有額外寫入費，讀取價依模型而定。[OpenAI-Caching]

### 哪些變動會讓快取失效

- Claude 的階層是 `tools` → `system` → `messages`，某層的變動會使該層與其後各層失效。修改工具定義（名稱、描述、參數）使全部失效；切換 web search 或 citations、速度模式（`speed`）使 system 與 messages 失效；`tool_choice`、圖片增減、thinking 參數、`output_config.effort` 變動使 messages 失效。[Claude-Caching]
- Claude 的 `tool_use` block 內 key 順序要穩定，有些語言（文件舉 Swift、Go）序列化時會隨機排序而破壞快取。[Claude-Caching]
- Claude 在部分模型可用 `{"role": "system"}` 訊息附加中途的系統指示，不改頂層 `system`，快取前綴就不變；另有 beta header `inline-tools-2026-09-15` 讓對話中途新增工具而不動 `tools`。[Claude-Caching]
- OpenAI 影響前綴的設定包括 `model`、`tools`（名稱、描述、schema、順序）、`parallel_tool_calls`、`text.format`、`reasoning.effort`、`text.verbosity`、`context_management`（compaction）。[OpenAI-Caching]
- OpenAI 對工具的建議：保持工具定義、順序、schema 不變；要停用工具用 `tool_choice: "none"`、要限縮子集用 `allowed_tools`，不要刪定義；需要時再載入的工具用 tool search 附加在 context 尾端。動態內容（時間戳、使用者專屬內容）放後面；改寫歷史、摘要、truncation 與 compaction 都會讓前綴改變。[OpenAI-Caching] [OpenAI-FnCall]

### 從 usage 看命中

- Claude：`usage` 內的 `cache_creation_input_tokens`（本次寫入）、`cache_read_input_tokens`（本次讀取）、`input_tokens`（最後一個斷點之後、未快取的部分）；總 input 為三者相加。兩個快取欄位都是 0，代表沒有快取（常見原因是未達最小長度）。[Claude-Caching]
- OpenAI：看 `usage.input_tokens_details.cached_tokens` 與 `cache_write_tokens`，以 cached tokens 除以總 input tokens 算命中率；GPT-5.6 以前的模型 `cached_tokens` 會排除隱藏 system token 並向下取整到 128 的倍數。官方範例中 LLM-as-a-judge 約 70%、multi-turn agent 超過 90%（文件註明為示意，實際依應用而異）。[OpenAI-Caching]

## 兩家對照表（本筆記歸納）

| 面向 | Claude API | OpenAI API |
|---|---|---|
| 結構化回覆 | `output_config.format`（`type: "json_schema"`）[Claude-StructOut] | `text.format` 設 `json_schema` 加 `strict: true` [OpenAI-StructOut] |
| 工具參數保證 | 工具定義 `strict: true` [Claude-StructOut] | 函式定義 `strict: true`，建議一律開 [OpenAI-FnCall] |
| optional 欄位 | 可不列入 `required`，但計入 24 個上限 [Claude-StructOut] | 全部要 `required`，以 `null` union 表示 optional [OpenAI-StructOut] |
| 數值與長度限制 | 不支援 [Claude-StructOut] | 數值與陣列範圍可用（fine-tuned 模型除外）[OpenAI-StructOut] |
| 遞迴 schema | 不支援 [Claude-StructOut] | 支援 [OpenAI-StructOut] |
| 拒答訊號 | `stop_reason: "refusal"`（200，照常計費）[Claude-StructOut] | 回應中的 `refusal` 欄位 [OpenAI-StructOut] |
| 平行呼叫開關 | `tool_choice` 內 `disable_parallel_tool_use` [Claude-ToolUse] | `parallel_tool_calls: false` [OpenAI-FnCall] |
| 工具結果 | `tool_result` + `tool_use_id`，錯誤設 `is_error: true` [Claude-ToolCalls] | `function_call_output` + `call_id` [OpenAI-FnCall] |
| 快取開法 | `cache_control`（頂層自動或 block 斷點，至多 4 個）[Claude-Caching] | 預設自動；GPT-5.6 以後可選 explicit 斷點（每請求至多 4 個寫入）[OpenAI-Caching] |
| 最小長度 | 512 到 4,096 tokens，依模型 [Claude-Caching] | GPT-5.6 以後 1,024 tokens [OpenAI-Caching] |
| TTL | 預設 5 分鐘，可選 1 小時 [Claude-Caching] | GPT-5.6 以後 30 分鐘；GPT-5.5 只有 `24h`，其他較早的模型為 `in_memory` 或 `24h` [OpenAI-Caching] |
| 寫入／讀取倍率 | 寫 1.25 倍（5m）或 2 倍（1h），讀 0.1 倍（部分模型更低）[Claude-Caching] | GPT-5.6 以後寫 1.25 倍、讀 0.1 倍；較早無寫入費 [OpenAI-Caching] |
| 命中欄位 | `cache_read_input_tokens`、`cache_creation_input_tokens` [Claude-Caching] | `input_tokens_details.cached_tokens`、`cache_write_tokens` [OpenAI-Caching] |

## 相關筆記

- [agent-tools.md](agent-tools.md#工具太多時)：Tool Search 以延遲載入處理大量工具，且不破壞 prompt caching；本篇的工具定義變動會使快取失效，兩者合讀。
- [agent-tools.md](agent-tools.md#mcp-spec-重點2026-07-28-版)：MCP `tools/list` 的順序應固定，以利 client 快取與 prompt cache 命中。
- [harness-engineering.md](harness-engineering.md#context-engineering)：其中有「為 prompt prefix cache 保持對話穩定」的做法（不重建過往 context、只有 compaction 可改寫歷史）。

## 來源

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| Claude-StructOut | [Structured outputs（Claude API Docs，2026-10-14 取得）](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | 部分（開頭與 How it works、Strict tool use、Important considerations 至 Feature compatibility；Usage 與 Common use cases 的程式範例未讀）（廠商性質） |
| Claude-ToolUse | [Tool use with Claude（Claude API Docs，2026-10-14 取得）](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) | 部分（How tool use works、When Claude uses tools、Choose a tool、Pricing；define-tools、parallel-tool-use 子頁未讀）（廠商性質） |
| Claude-ToolCalls | [Handle tool calls（Claude API Docs，2026-10-14 取得）](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) | 部分（tool_result 格式與 Handling errors with is_error 兩節）（廠商性質） |
| Claude-Caching | [Prompt caching（Claude API Docs，2026-10-14 取得）](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | 部分（開頭至 Caching strategies、Cache limitations、What invalidates the cache、Tracking cache performance、Best practices、Troubleshooting；1 小時 TTL 細節、pre-warming、範例、FAQ 未細讀）（廠商性質） |
| OpenAI-StructOut | [Structured model outputs（OpenAI API Docs，2026-10-14 取得）](https://developers.openai.com/api/docs/guides/structured-outputs) | 大部分（文字說明全讀；程式範例區塊未讀）（廠商性質） |
| OpenAI-FnCall | [Function calling（OpenAI API Docs，2026-10-14 取得）](https://developers.openai.com/api/docs/guides/function-calling) | 大部分（至 Streaming 與 Custom tools 概述；Lark / regex grammar 細節略讀，程式範例未讀）（廠商性質） |
| OpenAI-Caching | [Prompt caching（OpenAI API Docs，2026-10-14 取得）](https://developers.openai.com/api/docs/guides/prompt-caching) | 全文文字說明（程式範例未讀）（廠商性質） |
