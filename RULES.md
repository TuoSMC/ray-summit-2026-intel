# RULES.md — 棘輪禁令(每輪 P4 必掃;只增不減)

每條 = 一次真實踩坑。新教訓追加於對應節,附「來源戰役」。
§A 是物理定律(不可協商);§B 是製程紀律;§C 併入 impeccable craft-floor。

**修訂制度(2026-08-18 起):** 條款不刪。要改一條 §A,必須在 §D 寫出「修訂版 + 日期 + 理由 + 證據」,原文保留。
**衛生制度(§14.4):** 每條帶 `hits`(被 gate 擋下次數)。連續 5 場 0 hit → 移入 `loop/RULES-archive.md` 標 DORMANT,不刪除;再次觸發即回現役。**§A 與 §D 永不休眠。**

---

## §A Hard constraints — 違反 = 產出不可用

- **A1 純 ASCII。**(**已由 D1 條件化,見 §D**)HTML 檔案零個 >127 位元組。CJK:HTML 區 `&#xXXXX;`,
  `<script>` 區 `\uXXXX`(>0xFFFF 用 surrogate pair)。**entity 在 script 內
  不解碼** — 混用 = 直接出貨亂碼。原因:artifact 外框 `<meta charset>` 在
  瀏覽器 1024-byte 預掃描窗外。驗證:無 charset 的 `python3 -m http.server`
  開頁截圖。〔AMD-2026:「都是亂碼」事件〕
- **A2 禁 innerHTML。** 動態內容一律 `createElement`/`textContent`。〔安全 hook 強制〕
- **A3 零外部資源/零外送。** 禁 CDN、webfont、外圖、`script src`、fetch/XHR/
  beacon/WebSocket;全部 inline。證據來源 `href` 與 artifact 互連允許且必留。
- **A4 隱私。** 填入欄位只存 localStorage,不隨連結外傳;禁寫任何 PII 進可分享頁。
- **A5 發布對應。** 同檔名 → 同 URL;檔名即身分,不得改名重發。

## §B 製程紀律

- **B1 證據雙軸分離。** 產品生命週期(已發表/出貨中/爬坡/GA)≠ 證據品質
  (官方一手/廠商自報/第三方實測/未證)。**過度避險=事實錯誤**:把「無第三方
  實測」寫成「未上市」,對 sales 受眾比吹噓更糟。〔AMD-2026:MI4xx 118 處誤標〕
- **B2 矛盾偵測。** 同 40 字內出現「已發表/出貨」與「未上市/未量產」= fail。
- **B3 事實基準唯一。**(**已由 D2 改型別,見 §D**)場次/時間/房號只允許一個來源;
  任何頁面不得二源。多處版本 → 先修 drift 再編輯。
- **B4 subagent 結論 = 待驗 claim。** 助手的自信細節要對事實基準複查。
  〔AMD-2026:agent 誤判 Rivian/Bosch 為污染,官方講者名單打回〕
- **B5 使用者已決策項不得被舊底稿復原。** 底稿是追溯來源,不是現行指令;
  決策以 STATE.json `decisions[]` 為準。〔AMD-2026:GTM 順序 OEM-first 被用戶推翻〕
- **B6 hedge 要跟著翻譯走。** 翻譯/改寫不得把「廠商自報」變成裸斷言;
  數字/日期/產品名/人名/房號/URL 逐字不動 = fatal 級。
- **B7 簡中是詞彙工作,不是轉碼。** 內存≠记忆体、带宽≠频宽、性能≠效能、
  服务器/软件/硬件/网络/数据/集成/默认/登录/菜单。字元轉換工具產出視為錯誤。
- **B8 freshness 戳強制。** 每個帶時效的區塊要有「狀態截至 YYYY-MM-DD」;
  座位/報名狀態必附「以活動 App 為準」。
- **B9 workflow 腳本禁依賴 args 傳路徑。** campaign 路徑一律硬編進腳本;args 只准帶
  `campaignId` slug,經 scaffold 時寫好的查表換絕對路徑。slug 查不到 → 停,不得退回 CWD。
  replay/resume 時 args 可能重水化成字串,`undefined/` 漏進路徑後 agent 會把 A 戰役的檔案
  寫進 B 戰役目錄。〔Yotta-2026:6 份講者檔+1 份合成檔寫進 AMD 目錄〕

### 活動製程(2026-08-18 追加)

- **B10 三份 catalog。** sessions ≠ speakers ≠ sponsors。join,不得融合。
  〔AMD-2026:Rivian/Bosch 誤報;Yotta-2026:87 名 speaker-only 歸零〕
- **B11 identity assert 先於任何研究寫入。** 活動名 + 日期 + sessionCount + 路徑前綴 + 每個
  orgs.json id 有來源。失敗 → `quarantine/`,停。〔Yotta-2026:跨戰役污染〕
- **B12 頁面預算。** 核心**六頁**(command-center / agenda / gtm / accounts / compare / glossary),
  除非 P0 明刪。深度頁只在 P0 點名時才生。〔AMD-2026:13 頁手刻;Yotta-2026「照 AMD 場複製」〕
- **B13 `未知 ≠ 無`。** 機器 gate。反駁「Dell 供這個站」不等於寫「沒有 Dell」。〔Yotta-2026〕
- **B14 i18n 在來源語言凍結之後才開始。** 簡中是詞彙。〔AMD-2026:1+8+8 再 12 頁〕
- **B15 競爭情報包不得上公開 host。** 無 ACL 的 host 一律禁。〔Yotta-2026:SITE.md public: true〕
- **B16 數字來自資料。** 手打總數 = 缺陷。〔AMD-2026:「185 speakers」〕
- **B17 不得複製上一場的頁面集、factbase、講者名單。** 〔Yotta-2026 STATE decision「照 AMD 場複製」〕
- **B18 landlord ≠ buyer。** 寫 server PO 的是租戶或 SI,不是機房業主。〔DLR-2026;dossiers LANDLORDS band〕
- **B19 先 CARD 後 FULL。** FULL 只在 P2a 三條 gate 全開時才寫。〔dossiers TIERS;Yotta-2026 369 名清單〕
- **B20 speaker ≠ company。** 人物檔是進 PO 的路徑,不是帳戶檔。〔dossiers §8 vs AMD 講者 dossier〕
- **B21 CRM/portal 是 kill-gate,唯讀。** agent 永不註冊。查現行法定名 + 別名。〔DLR tracker〕
- **B22 window ≠ trigger。** 不得發明月份。〔BUYWINDOW dossier〕
- **B23 政治/FEC 是選配深度,不是預設軸。** 〔dossiers methodology〕

### Loop 紀律(2026-08-18 追加)

- **B24 公司正本在帳本,不在戰役。** campaign 只存指標 + 本場 delta。`ledger_id` 是 loop key,
  `first_seen` 寫一次不得改寫,`seen_at[]` 每場追加。帳本命中的公司**不重研究**。
- **B25 別名不確定時建新卡,不合併。** 重複卡可救,錯誤合併會毒兩個帳戶。每次合併寫進 `corrections[]`。
- **B26 每場收尾必寫 `loop/campaigns.jsonl` 一行。** reused 比例上升、每家研究 token 下降,
  是每場要辯護的主張。沒有紀錄 = T1–T4 不可證偽。

## §C Craft(與 impeccable craft-floor 合併執法)

- **C1 token 配色。** 新元件只用 `var(--ink/--soft/--muted/--acc/--ok/--claim/
  --stop/--line/--surface/--bg)`;禁硬編 hex。頁面級規則會蓋掉你 — dark theme 隱形教訓。
  〔AMD-2026:statusstamp 粗體隱形〕
- **C2 字重只有 400/700。** typewriter 堆疊沒有中間字重;合成字重禁止。
- **C3 手機禁水平捲動。** 寬內容自己 `overflow-x:auto`;flex 子項記 `min-width:0`。
  720px 以下表格轉卡片。〔AMD-2026:900px 議程表手機橫拉〕
- **C4 sticky 慎用。** `overflow` 容器內的 sticky `<th>` 會破版。
- **C5 patch style 禁疊層。** 覆寫 `<style>` 必須 append 在檔案最末;疊到第三層時收斂成
  canonical 區塊。〔AMD-2026:copper 換膚失敗 + 五層 patch〕
- **C6 可及性底線。** 互動目標 ≥44×44 CSS px;對比 ≥4.5:1;切換元件帶
  aria-pressed/aria-current/aria-expanded;drawer/popover 可 Escape 關閉並還焦點;
  `prefers-reduced-motion` 關非必要動畫。

## §D 修訂(2026-08-18 起;原文保留在上,這裡是現行判準)

- **D1 = A1' 純 ASCII 依 host 條件化。**
  `STATE.campaign.host == artifact-sandbox` → A1 原文全效。
  `host ∈ {docs-local, private-acl}` → UTF-8,`<meta charset="utf-8">` 必須在檔案前 512 bytes,
  ASCII gate 跳過。
  **理由:** 1024-byte 預掃描窗是 artifact 外框的性質,不是 HTML 的性質。無條件編碼讓每個 diff
  不可讀且燒 token。**驗證不變:** artifact host 用無 charset 的 `python3 -m http.server` 截圖;
  local host 驗 meta 標籤位置。〔AMD-2026 建立 A1;2026-08-18 條件化〕
- **D2 = B3' 事實基準是 JSON。**
  `data/sessions.json` / `speakers.json` / `sponsors.json` 是來源。`NN-sessions-list.md` 是
  **產生的 view**,不得手改。兩者不合 → JSON 勝,view 重建。
  **理由:** B3 原文把 markdown 指為基準,Yotta 因此養出兩份議程(161 vs 160)。JSON 可被 gate 讀,
  markdown 不行。〔AMD-2026 建立 B3;Yotta-2026 雙 factbase;2026-08-18 改型別〕

每條修訂同時寫進 `STATE.corrections[]`(帶 `ruleAdded`)。

## §T Token 紀律

- **T1** 只有 `surface: true` 的 claim 才進 3 票互駁。〔AMD-2026:每個中間結論都投票〕
- **T2** 人物 dossier 先過名單 gate;公司 CARD 照發。〔AMD-2026:12 份 dossier 有 9 份是未確認的 2025 名字〕
- **T3** 便宜 gate 先於重跑矩陣。〔AMD-2026:改一句話重跑 390 案〕
- **T4** `accountBudget.maxFull` 預設 8,計本場**寫入**的 FULL,不計帳本沿用的。其餘一律留 CARD。
  〔Yotta-2026:369 名清單 + dossiers 預設 15 §§〕

## 執行方式

- P4b:`bin/qa-gate.sh <campaign-dir>` 機器掃 A1(依 D1 條件)/A2/A3/B2 + JS 語法;
  `check_facts.py` 掃 B13/B16/B19/B24/T4;`check_form.py` 掃 B12 頁面預算;
  `Skill(sourced-output-gate)` 掃 B1/B6。
- P4a:`Skill(impeccable)` `audit`+`critique` 掃 §C。
- P4c:`Skill(codex)` 外部紅隊;產出照 B4 當待驗 claim。
- 其餘(B3/B5/B7/B8/B25)是 review checklist,P4 時對照。
- P6:`Skill(retro)` 收教訓 → campaign RULES 加條款 → 上行本檔(runtime + canonical 雙份)
  → 跑 §14.4 衛生:記 `hits`、休眠 5 場 0 hit 者。

---

## 戰役棘輪 — Ray Summit 2026(P6 上行候選)

- **R1 `layer` / `classification` 必須容得下 GAP。** Y4「enum 就是 enum」與 Y5「敢標 GAP」在第一場真實戰役第一分鐘對撞:lap 1 沒做研究,layer 本來就未知,但 schema 沒有 GAP 成員,等於逼 agent 編一個 layer。**修法是加 GAP 進 enum,不是放寬成自由文字。** 自由文字仍然 fail。
  〔Ray-Summit-2026:28 張卡 × 5 條 = 140 個 F2 fail〕
- **R2 `window: "none"` 是結論,不是空白。** 「查過沒有窗口」與「還沒查」不是同一件事。未查一律 `GAP`。B22 只講「不得發明月份」,沒講「不得用 none 冒充已查」——這條補上。
  〔Ray-Summit-2026:28 張卡全部誤填 none,被 F3 攔下〕
- **R3 摩擦要跑對階段。** `make.sh check-fresh` 在 P0 就要求 host,但 host 是 P5 的停。已把檢查移進 `require_host`,只有真的要建置的 target 才叫。
  〔Ray-Summit-2026:戰役釘住當天 check-fresh 就拒跑〕
- **R4 官方 catalog 可以只公布部分天數。** Ray Summit 是三天活動(8/24–8/26),T-7 時 catalog 只出 8/24、8/25。捲到底確認 50 張卡到底、只有兩個 day label 之後,才准寫進 `factbase.gaps`——**「未公布」不是「沒有」**。
  〔Ray-Summit-2026:第三天零場次〕
- **R5 catalog 可能一個講者都不給。** Cvent AgendaV2 的 session card 沒有 anchor、沒有頭像、carousel 是空的。`speakers.json` 只能來自行銷頁,且官方寫「and others」= 部分名單。不得用場次標題反推講者。
  〔Ray-Summit-2026:50 張卡零講者〕
- **R6 贊助名單不能讀散文摘要,要讀 logo 牆。** 第一次抓 sponsors 是用行銷頁的文字摘要,官方寫「and others」,結果 16 家漏成真實的 23 家,還把 Lila Sciences 誤標為 Gold 贊助。**tier 區塊的 `img` alt/src 才是來源。** 講者區的 logo 另外揭露 17 家完全沒被抓到的參與組織。
  〔Ray-Summit-2026:28 家 → 59 家,漏了一半以上〕
- **R7 配不到僱主的講者,不准生一個假公司。** join 遇到沒有 company_id 的講者時,曾建出 `ORG_GAP_<人名>` 這種佔位組織,它會流進 orgs.json、拿到一張卡、進帳本,污染跨活動的公司計數。**正確作法:講者留在 speakers.json 且 company_id 為 null,不進 join。** 〔Ray-Summit-2026:ORG_GAP_ANDREWDAI 一路長到帳本才被抓到,實際上 Andrew Dai 是 Elorian AI 創辦人〕
- **R8 「physical servers」不等於自有伺服器。** 租用的 dedicated hosting 也叫 physical server;判 `buys_servers=YES` 要看**誰擁有那台鐵**——自有機房、colo 機櫃、自行上架、汰換週期、硬體採購職缺,任一有據才算。反向也成立:部落格寫滿 AWS 的公司可能正在做 cloud exit。**兩邊都要查。** 〔Ray-Summit-2026:Discord 誤判為買方(實為租 i3D.net),Grab 誤判為 ruled-out(實已自建馬來西亞 colo、250 台自架)〕
- **R9 logo 出現在哪一區決定 role,不能一律當 exhibitor。** 官網有「贊助 tier」和「Also featuring sessions from」兩種 logo 牆,後者是**講者僱主,沒有攤位**。混為一談會讓業務去找不存在的攤位。抓 logo 時要一併記下它所屬的區塊標題。〔Ray-Summit-2026:19 家被誤標 exhibitor〕

## §D 修訂 — 本戰役

- **D3 = B15' 本戰役經使用者明示豁免。** B15(競爭情報包不上公開 host)在 Ray Summit 2026 被使用者以明示決定豁免:公開 GitHub repo + GitHub Pages,原樣發布。
  **豁免範圍僅限本戰役,不上行 governor RULES。** 下一場活動 B15 原文全效,除非再次明示豁免。
  **揭露內容已於決定前逐項列出**:12 張指名個人的戰術卡、指名取代競爭對手的句子、26 家 ruled-out 名單、SMCI 對 CoreWeave 供應占比的競爭情報。風險已說明為不可逆(fork / 索引 / archive.org)。
  〔Ray-Summit-2026,2026-08-17,使用者決定,記於 STATE.decisions[]〕
- **R12 建置基礎設施不准渲染給讀者。** `data/termbase.json` 是 i18n 翻譯記憶(存在理由是 B7:簡中要查詞彙表,不能用字元轉換工具),只有 `i18n_overlay` 該讀它。它被接進 glossary 頁,結果讀者看到「bandwidth 頻寬 / server 伺服器 / software 軟體」——業務當然知道這些字,這讓整頁看起來像半成品。
  **判準:一個檔案如果是「給產生器看的」,它就不該有渲染路徑。** glossary 要放的是**會場語言**(Ray Data / vLLM / MoE / prefill-decode 拆分 / NVL72 / VLA / neocloud / whitebox),而且每條要能回答「業務為什麼要在意」——答不出來的詞不該上頁面。
  〔Ray-Summit-2026:build_fragments.py:1097 把 termbase.terms 倒進 glossary〕
- **R13 這包東西不對讀者解釋它自己。** 內部欄位名(`ledger_id`、`asOf`)、內部 token(`GAP`)、內部分類法(landlord/operator/tenant/channel)、證據等級標籤、產線概念,**全部不上讀者面**。它們是給產生器和 gate 看的。
  一個詞如果需要讀者翻到別處查,它在會場上就已經失敗了——**要解釋就解釋在那一格自己的說明文字裡**,不開參考章節。
  同理,已經在別頁算過的數字不要再開一頁重列一次。
  〔Ray-Summit-2026:glossary 整頁被讀者退回,核心頁由六降五〕
- **R14 「已部署」要比對 commit,不能只看狀態字。** GitHub Pages 的 `builds/latest` 在新 commit 還在 building 時,回的可能是**上一次**建置的 `status: built`。只看狀態就會回報成功,而線上還是舊檔。
  **正確判準:`builds/latest.commit == git rev-parse HEAD` 且 `status == built`,再加一次破快取的 curl 比對「線上位元組數 == 本機位元組數」與一個只有新版才有的字串。**
  同一個原則適用所有「非同步發布」:狀態欄位是它自己的說法,實際內容才是證據。
  〔Ray-Summit-2026:回報 built 但線上仍是舊版,靠檔案大小 710,340 vs 713,277 才抓到〕

**R15 — 註冊過的錨點必須真的被印出來,交叉連結必須在成品裡解析得到。**
`reg()` 註冊一個 id 只是承諾,`id="..."` 印在該元素上才是兌現。
兩者分離時,連結看起來完全正常,點下去什麼都不會發生 —— 這比壞掉的連結更貴,
因為沒有人會回報它。
折頁版(onepage)另有一層:`accounts.html#acct-x` 在單檔文件裡是死的,
必須先剝掉檔名再處理裸檔名連結,順序反了會變成 `#accounts#acct-x`。
**gate:** `onepage.py` 現在檢查 (a) 沒有任何 `href="*.html#"` 存活,
(b) 每一個 `href="#id"` 在同一份文件裡找得到 `id`。
〔Ray-Summit-2026:323 條交叉連結曾經全部是死的,五道 gate 全綠〕

**R16 — 晶片型號是有年份的東西,不准當成沒有年份的標籤印出來。**
`H100` 這四個字元對讀者沒有時間感。同一顆在客戶機隊裡代表「舊到該換」還是
「舊到已經回本、還在賺」,是完全相反的兩種銷售動作,而型號本身不會告訴你是哪一種。
所以每一次出現都要連到它的世代履歷:發布日、量產日、上一代、下一代、供貨狀態。
**上市月數要用算的**(GA 對 factbase 日期),寫死的「大約兩年」隔月就是錯的。
**NVIDIA 不公布資料中心 GPU 的 EOL** —— 它的 GPU 停產通知是 NDA 夥伴文件。
所以 EOL 是永久 GAP,不是研究沒做完;生命週期狀態要按 OEM 分開講。
〔Ray-Summit-2026:143 處型號提及,原本全部沒有時間資訊;
 而「還在線＝12-24 個月內要換」這條論點被 NVIDIA 自己的法說會推翻〕
