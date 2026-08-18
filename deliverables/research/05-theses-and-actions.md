# 05 — 論點與現場行動(P2b 維度 5)

> 底稿。狀態截至 2026-08-17。互盲產出,未經跨維度合成。
> 每條標證據層級:官方一手 / 廠商自報 / 第三方 / 未證。

## 判斷
- 這房間裡真正簽伺服器訂單的是 neocloud,不是平台團隊;4 家 neocloud 贊助商裡,CoreWeave 與 Nscale 已公開綁 Dell、Nebius 自研走 ODM,**只有 Lambda 是既有客戶**(官方一手,SMCI PR 2025-08)。此行是情報場,不是開單場。
- Ray 的核心賣點是「同樣硬體多榨 2–3 倍」,短期對機箱生意是逆風:Torc 由 30–40% 拉到 90% GPU 利用率、epoch 20→5 分鐘,明說 *without additional hardware*(廠商自報,Anyscale blog)。要賣的是**異質節點與機房層**,不是多賣一櫃。
- Supermicro 不在官方贊助名單(官方一手,anyscale.com/ray-summit/2026,讀取 2026-08-17)。**這是 GAP,不是被排除**——但代表無主場、無展台、無正當推銷位。

## 論點與反證

**T1|OEM lock 已成形,縫隙在 Lambda 與未公開供應商的中小 neocloud。**
證據:Dell 交付 CoreWeave 市場首套 GB300 NVL72 與首套 Vera Rubin NVL72(官方一手,Dell blog);Nscale 用 Dell PowerEdge XE9712 + IRSS 整櫃(官方一手,Dell blog),且已簽 Microsoft 約 20 萬顆 GB300(官方一手,Nscale PR)。Verda(原 DataCrunch,自有 Helsinki/冰島機房,2026-04-24 募 $117M)硬體供應商**未證**(第三方,EU-Startups 2026-04)。
反證:若現場任一 neocloud 工程師說整櫃供應商是多源、或正在 requalify 第二供應商,T1 立刻失效,改打正面競標。

**T2|利用率提升會延後而非拉動節點採購——除非工作佇列同步變長。**
證據:Torc 4x 提速零增購(廠商自報);Robinhood 議程主題即「Right Resource, Right Job」異質叢集省成本。
反證:若平台團隊說利用率上去後排隊時間沒下降、反而擴大訓練規模,則利用率是需求放大器,論點反轉。

**T3|近場機會是 CPU 前處理節點與資料節點,不是 NVL72。**
證據:Torc 症狀為「GPU 飢餓、同機 CPU 打滿」(廠商自報);議程有 Robinhood 異質叢集、CoreWeave PB 級影片策展;SMCI 與 VAST 已有 CNode-X 聯合方案,用 CloudDC AS-1116CS-TN 與 SYS-212GB-FNR(官方一手,SMCI IR 2026-02)。
反證:若這些 workload 全以雲端 instance 消費且無 on-prem 計畫,則無 BOM 可談。

**T4|Physical AI 是唯一可能自建機房的買家群。**
證據:8/25 排有 Industry Leaders Roundtable - Physical AI(官方一手);Silver 贊助含 Path Robotics、Foxglove;Torc 單一 pipeline 已達 38TB(廠商自報)。
反證:若圓桌上這些公司都說模擬與訓練全部(100%)在超大規模雲上,資料落地論點不成立。〔此為待驗條件,非既有數據〕

## 現場優先順序

**Session(照這個順序卡位)**
1. **How the Data Center Shapes the workload** — 全場唯一直接談機房約束的題目;記下講者機房是自建、colo 還是租雲。講者**未證**。
2. **Industry Leaders Roundtable - Physical AI** — 一場抓齊多家 T4 買家,會後圍堵成本最低。
3. **Maximizing GB200/GB300 Performance with Domain-Aware Scheduling in Ray** — 問誰在跑 NVL72、幾櫃、熱與電的痛點。對照語言:GB300 NVL72 整櫃 132–140kW + DLC〔官方一手,supermicro.com/datasheet/datasheet_SuperCluster_GB300_NVL72.pdf,讀取 2026-08-17〕。
4. **Right Resource, Right Job: Robinhood's Journey…** — 他報出的節點型號清單就是一張現成 BOM。
5. **Petabyte-Scale Video Curation on CoreWeave** — 儲存與 CPU 節點比例,接 VAST 共同提案。
6. **Serving Frontier MoE Models at the Lowest Token Cost** — 推論端 TCO 話術。
7. 低優先:**Scaling LLM Workloads on TPUs with Ray**(TPU 無 OEM 機會,純競爭情報)、**Physical AI at Aerospace Scale**(衝堂則放棄)。

**攤位對話(按賠率排序)**
1. **Lambda**(Gold)— 唯一既有關係;SMCI 曾代租 Vernon 21MW、10 年逾 $6 億並轉分租〔官方一手,sec.gov SMCI 10-K FY2024;第三方 datacenterdynamics.com,皆讀取 2026-08-17〕。目標:下一批機型與時程。
2. **Verda**(Gold)— 自有機房 + 新資金 + OEM 未證 = 最高賠率的新名字。
3. **VAST Data**(Gold)— 有現成聯合方案,走 co-sell 不走直銷。
4. **Nebius**(Gold)— 自研 + 台系 ODM(廠商自報),只問 CPU/儲存/網路節點是否外購。
5. **CoreWeave / Nscale**(Platinum)— 只做確認題,不推銷。
6. **平台團隊**(Uber/Pinterest/Netflix/Discord/Spotify/Apple/BMW/Robinhood)— 情報價值高於成交價值。Uber 自述跨 on-prem 與 OCI/GCP 逾 5,000 GPU(官方一手但時點舊,**現況未證**)。

## 五個問題與它們揭露什麼

| 問題 | 得到答案代表什麼 |
|---|---|
| 「你們的 Ray cluster 跑在自己機房、租的 colo,還是純雲端 instance?」 | 自建/colo = 可直銷;純雲 = 只能經 neocloud 間接,此人是情報來源不是買家 |
| 「CPU 前處理節點跟 GPU 節點是同一批機器、同一個採購週期嗎?」 | 分開 = 異質節點有獨立 BOM 與獨立汰換窗口(T3 成立);同批 = 只能等整體 refresh |
| 「你們最舊的那批 GPU 節點是哪一代,現在還在跑什麼?」 | 世代分佈就是 refresh 時鐘;A100/H100 仍在線 = 12–24 個月內有汰換對話 |
| 「這一櫃是誰整合的、on-site 誰做?」 | 「OEM 整櫃交付/IRSS」= OEM lock 已鎖;「我們自己 rack & stack」= 有縫,DCBBS 可切入 |
| 「下一批容量的瓶頸是 GPU 交期、電力,還是機房空間?」 | 電力/空間 = 液冷與 DCBBS 可談;GPU 交期 = 幫不上,禮貌結束 |

## 不要做什麼

- **不要在 CoreWeave / Nscale 攤位 pitch。** 它們是 Platinum 主辦夥伴且已公開綁 Dell(官方一手);在別人主場推銷會燒掉未來 co-sell 的門。
- **不要用「我們也有 GB300 NVL72」當開場。** 這房間買的是排程與利用率,規格開場會被歸類為機箱廠。
- **不要複述任何未經對方確認的 fleet 數字**(含上述 Uber 5,000 GPU)。問,不要說。
- **不要把「不在贊助名單」讀成「被排除」。** 那只證明沒買贊助,是 GAP。
- **不要以名片數當 KPI。** 帶回 5 個具名、可追的答案,勝過 50 張名片。
- **不要報價、不要承諾交期。** scout 沒有定價授權;先報價等於提前讓出議價權。

## GAP

- Supermicro 是否有 expo 攤位或員工講者:**未證**。贊助名單 ≠ 展商全表;到場第一件事是拿 expo 平面圖確認。
- 上述 8 場 session 的講者姓名與所屬公司:**未證**(agenda 子頁 404)。用現場 App 於 8/24 補齊再排時程。
- Verda / Lila Sciences / Encord / Simplismart / Parasail / Path Robotics 的硬體供應商:**未證**。
- CoreWeave 是否同時使用 Dell 以外 OEM、Nebius 的 ODM 名稱與是否外購 CPU/儲存節點:**未證**(僅有單邊公告)。
- 所有與會平台團隊的實際 fleet 規模與採購窗口:**未證**,本文一律不推估。
