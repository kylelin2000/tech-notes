# AI 對開發者生產力的實證

本篇整理「AI 工具讓開發者變快或變慢多少」的研究：METR 的隨機對照實驗（RCT）與後續、以及 Google DORA 2025 的大型調查。評估 agent 本身的能力與品質，見 [agent-evals.md](agent-evals.md)。內文的 `[簡稱]` 對應文末「來源」表。

## METR 2025 RCT：資深開源開發者

- 設計：16 位資深開源開發者，在自己長期貢獻的大型 repo 上完成 246 個真實任務（issue）；repo 平均約 23,000 stars、1,100,000 行程式碼，開發者平均有 5 年該 repo 經驗、1,500 個 commit。[METR-RCT] [METR-2025]
- 隨機方式：任務先由開發者列出並預估時間，再以模擬公平硬幣隨機分到「允許 AI」或「禁止 AI」；允許時可自選工具（也可不用），主要是 Cursor Pro 搭配 Claude 3.5/3.7 Sonnet；禁止時不得使用生成式 AI。任務平均約 2 小時，開發者時薪 $150，完成時間為自行回報。[METR-RCT] [METR-2025]
- 主要結果：允許 AI 時完成時間多 19%（作者把「完成時間百分比變化」定義為 S，正值稱 slowdown）；136 個任務允許 AI、110 個禁止。[METR-RCT]
- 預期與自評落差：事前預測可縮短 24%，事後自評仍認為縮短 20%；經濟學專家預測縮短 39%、ML 專家 38%。[METR-RCT]
- 活動分析（74 份有效螢幕錄影子集）：允許 AI 時，主動寫程式與查資料的時間比例較低，改為花在 prompt、等待與審查 AI 輸出，閒置比例也略高。[METR-RCT]
- 作者列的因素：檢視 21 項可能因素，5 項有證據助長變慢、10 項證據混合或不明、6 項有證據顯示不是原因（部落格寫 20 項，以論文為準）。[METR-RCT] [METR-2025]
  - 有證據助長：對 AI 過度樂觀、開發者對 repo 高度熟悉、repo 大而複雜、AI 可靠度低（接受不到 44% 的生成，約 9% 時間花在審查或清理 AI 輸出）、AI 吃不到 repo 的隱性脈絡。[METR-RCT]
  - 有證據顯示不是原因：不熟悉開發環境、作弊或少用 AI、任務流失、結果指標或估計方法不穩健、使用非前沿模型。[METR-RCT]
- 作者明說不代表什麼：不代表 AI 現在不能加速多數開發者，也不代表其他領域、近期模型或更好的使用方式不會有正向加速；結果可能與小型全新專案或不熟悉的 codebase 不同。作者也強調各因素分析並未針對多重比較設計統計檢定力，屬推測性證據。[METR-2025] [METR-RCT]
- 官方標註：METR 部落格現已標示這些結果「out of date」，不再反映當前影響。[METR-2025]

## METR 2026 後續與自評調查

- 為何改設計：2025 年 8 月起的第二輪（10 位原開發者加 47 位新招募者，時薪降為 $50）數據被 METR 認為對現況是「不可靠的訊號」。原因：愈來愈多開發者不願在沒有 AI 下工作而不參加；30% 到 50% 的開發者表示因為不想在沒有 AI 下做而不提交部分任務；時薪降低可能加重選擇效應；使用 agentic 工具時，開發者常在等 agent 完成時去做別的任務，任務時間難以自行回報。[METR-Uplift2026]
- 數字（照原文用語與正負號）：2025 年研究為「多花 19%」，信賴區間 +2% 到 +39%；原開發者子集「speedup of -18%」，區間 -38% 到 +9%；新招募開發者 -4%，區間 -15% 到 +9%。[METR-Uplift2026]
  - 原文以這組數字說明「raw results show some evidence for speedup」，即負值指完成時間縮短；兩個新區間都跨過 0。[METR-Uplift2026]
  - METR 的判斷是 2026 年初開發者「很可能」比 2025 年更受益，但因選擇效應，本輪資料只是這個增幅的很弱證據；不願在沒有 AI 下工作的開發者退出，使加速估計偏低，被篩掉的開發者與任務真正的加速可能高得多。[METR-Uplift2026]
- 後續方向：更短而密集的實驗、觀察性資料、問卷、固定任務實驗、開發者層級隨機化等。[METR-Uplift2026]
- 自評調查（2026 年 2 到 4 月，349 位技術工作者，含 87 位軟體工程師）：問的是「價值」變化而非速度。價值倍數的中位數落在 1.4 到 2 倍，速度倍數中位數 3 倍；回溯 2025 年 3 月 1.3 倍、2026 年 3 月 2 倍、預測 2027 年 3 月 2.5 倍。[METR-Survey2026]
- METR 對偏差的說法：樣本為便利抽樣、寄信回覆率約 2%，可能有顯著選擇偏差；調查結果不必然符合現實，並引用 2025 年研究中受試者高估了 40 個百分點；公開調查的估計常高於實地實驗。METR 員工回報的價值倍數最低，被推測可能與其熟知先前的認知落差有關；對回報 10 倍以上的 7 份回答細看，其中數份被判定為高估。[METR-Survey2026]

## DORA 2025：產業調查

- 樣本與方法：2025 年 6 月 13 日到 7 月 21 日的全球問卷，共 4,867 位受訪者，加上超過 100 小時的質性資料；為相關性的調查分析，不是隨機實驗。[DORA-2025]
- 核心結論：AI 的主要角色是「放大器」（amplifier），放大高績效組織的優勢，也放大掙扎組織的失能；最大報酬來自內部平台品質、工作流程清晰度與團隊對齊等組織系統，而非工具本身。[DORA-2025]
- 採用與信任：90% 受訪者在工作中使用 AI，超過 80% 認為提升了生產力，但 30% 對 AI 產出的程式碼幾乎不信任或毫不信任。[DORA-2025]
- 與吞吐量、穩定性的關係：AI 採用現在與軟體交付吞吐量呈正向關係（相較去年為重要轉變），但仍與交付不穩定性（instability）上升有關。2024 年報告曾估計每增加 25% 採用率，吞吐量下降 1.5%、不穩定性上升 7.2%。[DORA-2025]
  - 報告檢查「AI 是否緩解不穩定性的傷害」，沒有發現這種調節效果。[DORA-2025]
- DORA AI Capabilities Model 七項能力（從 15 項候選中挑出，與 AI 使用有交互作用）：[DORA-2025]
  1. 清楚且被傳達的 AI 立場（clear and communicated AI stance）
  2. 健康的資料生態系（healthy data ecosystems）
  3. AI 可存取的內部資料（AI-accessible internal data）
  4. 強健的版本控制實務（strong version control practices）
  5. 小批量工作（working in small batches）
  6. 以使用者為中心（user-centric focus）
  7. 高品質的內部平台（quality internal platforms）
- 七種團隊型態及占比（依績效、穩定性與福祉聚類）：Foundational challenges 10%、Legacy bottleneck 11%、Constrained by process 17%、High impact, low cadence 7%、Stable and methodical 15%、Pragmatic performers 20%、Harmonious high-achiever 20%。[DORA-2025]
- DORA 報告自己引用 METR 的 19% 與 20% 落差，作為「廣泛採用不等於廣泛價值」的提醒。[DORA-2025]

## 怎麼讀這些數字（本筆記歸納）

- 三種證據性質不同：RCT 量的是客觀完成時間，但樣本小（16 人）、情境窄；DORA 是大樣本調查，結果是統計關聯與自評感受；METR 2026 調查明講是自評，且問的是價值而非速度。三者不能直接換算成同一個「X% 變快」。
- 自評容易偏高：RCT 中事前預測 24%、事後自評 20%，實測卻是變慢 19%；METR 自己的調查文章也以此提醒讀者對自評倍數保持懷疑。
- 時間點與模型版本不同：19% 變慢對應 2025 年 2 到 6 月的工具（Cursor 搭 Claude 3.5/3.7 Sonnet）；2026 年數字來自較晚的工具，但因選擇效應 METR 自己只視為弱證據，不應拿來與 2025 年數字做精確比較。
- 情境差異：RCT 的受試者是對大型成熟 repo 極度熟悉的開發者，作者自己指出這些條件不適用於許多場景；DORA 則偏向組織層級的交付結果，與個人任務速度是不同問題。

## 相關筆記

- [agent-evals.md](agent-evals.md)：評估 agent 本身（trace、benchmark、eval flywheel），不是衡量開發者生產力。
- [harness-engineering.md](harness-engineering.md)：harness 實作總覽；其中提到的 METR「時間地平線」曲線是另一項研究（衡量模型能自主完成的任務長度），和本篇的開發者 RCT 不同，不要混為一談。

## 來源

| 簡稱 | 來源 | 讀取程度 |
|---|---|---|
| METR-RCT | [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity（arXiv 2507.09089，2025-07）](https://arxiv.org/abs/2507.09089) | 部分（摘要、§1–§4 含 Table 1；附錄僅略讀） |
| METR-2025 | [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity（METR，2025-07-10）](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) | 全文 |
| METR-Uplift2026 | [We are Changing our Developer Productivity Experiment Design（METR，2026-02-24）](https://metr.org/blog/2026-02-24-uplift-update/) | 全文 |
| METR-Survey2026 | [Measuring the Self-Reported Impact of Early-2026 AI on Technical Worker Productivity（METR，2026-05-11）](https://metr.org/blog/2026-05-11-ai-usage-survey/) | 部分（摘要、方法、結果、建議；附錄僅略讀） |
| DORA-2025 | [State of AI-assisted Software Development 2025（Google Cloud DORA，2025）](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf) | 部分（廠商性質；摘要與 key findings、軟體交付績效與七種團隊型態、AI 與關鍵成果、AI Capabilities Model、受訪者概況；其餘章節未讀） |
