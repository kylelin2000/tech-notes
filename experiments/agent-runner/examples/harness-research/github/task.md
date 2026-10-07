# Task: 讀開源 agent harness / 框架的 repo，整理它的實作方式

## Item
帳本 key = owner/repo。payload 有 stars、evidence（README）、tree（檔案樹，evidence/<安全名>.tree.txt）。
兩個檔案都要讀；檔案樹用來推斷架構（主迴圈、工具、prompt 放在哪）。

## Fields
- repo（必填）
- what_it_is：一句話定位（必填）
- loop_and_tools：agent 主迴圈與工具怎麼設計（必填，README 沒講就寫「README 未說明」並依檔案樹推測、標明是推測）
- context_management：context / 記憶 / 狀態怎麼處理（必填，同上規則）
- notable_practices：值得借鏡的設計，條列（必填）
- maturity：活躍度與成熟度的判斷（依 stars、README 完整度），一句

## Rules
- 不要上網，只讀 evidence/ 裡已下載的檔案（檔名見 item 的 payload.evidence）。
- 以繁體中文撰寫，專有名詞、title 保留原文。用自己的話寫，不要大段照抄。
- 讀不到的欄位留空，不要猜。檔案損壞或內容與 agent harness 完全無關 → not-found 並寫明原因。
- done 時附 --evidence <payload.evidence>。result 較長時先用 Write 寫到 results/<安全檔名>.json 再用 --result @results/<安全檔名>.json。
