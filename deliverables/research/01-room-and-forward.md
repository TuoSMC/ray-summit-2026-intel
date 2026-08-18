# 01 — 這是什麼房間 + 前瞻訊號(P2b 維度 1)

> 底稿。狀態截至 2026-08-17。互盲產出。

## 判斷

- **主辦權在會前 3.5 週換人,換給了買機櫃的人。** Nscale 於 2026-07-30 以 15.5 億美元收購 Anyscale(Bloomberg 報導,**雙方未證實**);Nscale 同時是本屆白金贊助商、且有 keynote 席位(Josh Payne)。這不再只是開源社群年會,而是一家 GB300 大買家的主場。〔第三方 TechCrunch 2026-07-30〕
- **議程主軸從 8–10 條窄化成 4 條,每一條都吃 GPU。** 2026 只掛 Foundation Model Training / Multimodal Data Curation / Physical AI / LLM RL;2025 CFP 還有 Ray Ecosystem、Generative AI(含 Agents、MCP)、Research Frontiers。**軟體話題被擠掉,剩下全是算力題。**〔官方一手,2026 官網 + 2025-05-30 CFP〕
- **這房間的購買理由是「利用率」,不是規格。** Torc 自報 GPU 利用率 30–40% → 約 90%、資料量 4TB→38TB 同等牆鐘時間;Anyscale 自報 H100/H200 產線 >80% 利用率。**跟這群人談 TFLOPS 會冷場,談「同樣機櫃多跑幾成」會熱。**〔廠商自報〕

## 這是什麼房間

- 不是廠商展會,是工程社群年會 + 供應商聚集。官方定位對象是「builders, platform leads, and researchers」——**自建叢集的平台工程主管,不是採購。**〔官方一手〕
- Ray 已交給 PyTorch Foundation(2025-10-22,累計 2.37 億次下載,用戶含 OpenAI、Uber、Shopify、Netflix)。**治理中立,商業層在 Nscale 手上。**〔官方一手 pytorch.org〕
- 這裡決定的是「軟體怎麼排上硬體」,不是買哪台機器。講者來自 Discord、Spotify、Apple、Netflix、Amazon、Recursion、Adyen、Mercor 等自建平台團隊——**他們決定叢集拓撲、節點型別與利用率目標,這些決定才長成後面的採購單。**
- 票價 400–450 美元(5 張套票每張 750)= 工程師自費可及 → **來的人多半是實作者,不是簽核者。**〔官方一手〕

## 2025 → 2026 變了什麼

- **時間前挪 10 週**:2025 是 11/3–11/5,2026 是 8/24–8/26,同一個 Marriott Marquis。兩屆僅隔約 9.5 個月。〔官方一手〕
- **主軸重組(最關鍵)**:2025 CFP 的 8 個主題 → 2026 收斂成 4 個算力密集主軸,新增 **Physical AI**(2025 沒有)。〔官方一手,兩頁比對〕
- **vLLM 首次以獨立會議共構**:「first-ever vLLM Conference」由 Inferact 主辦,同場、Summit 票含全程,橫跨 8/25–8/26、15+ 場。〔官方一手 vllm.ai〕
- **vLLM 商業化了**:Inferact 於 2026-01 成立,$150M 種子、$800M 估值,a16z 與 Lightspeed 領投,Simon Mo 任 CEO。去年他掛「vLLM」,今年掛公司抬頭。〔第三方 SiliconANGLE 2026-01-22〕
- **話題從「怎麼管工作」變成「怎麼貼合機櫃」**:2025 keynote 發表 Lineage Tracking / Anyscale Runtime / Global Resource Scheduler;2026 前半年發表的是 GB300 NVL72 rack-aware scheduling。〔廠商自報〕

## 技術轉向 → 伺服器需求含意

| 議程訊號 | 對伺服器需求的含意 | 證據 |
|---|---|---|
| **Physical AI / 機器人**升為四大主軸,訓練日有 workshop,keynote 有 Torc、Bedrock | 新增一類**自建叢集買主**:自駕與機器人公司。形狀是「大量影片前處理 + VLA 大模型訓練」,資料量跳檔(Torc 4TB→38TB)。**這類客戶不租雲,會直接買機器。** | 官方一手 + 廠商自報 |
| **RL post-training** 獨立成主軸 | RL 要在**同一 fabric 內同時跑訓練與推論 rollout** → 要的是混合角色節點與統一互聯,不是純訓練機或純推論機。 | 官方一手 |
| **多模態資料策展**成主軸;Anyscale 以 NVIDIA **RTX PRO 4500 Blackwell Server Edition** 宣稱大規模去重成本較純 CPU 管線低 80% | **非旗艦 PCIe GPU 伺服器**的新需求池——不是 NVL72,是可大量出貨的標準 GPU 伺服器。**對 Supermicro 是最直接、最好賣的一塊。** | 廠商自報 2026-03-16 |
| **MoE 服務 + 分離式 prefill/decode + 多層 KV offload** | prefill 與 decode 獨立擴縮 → 異質節點配比、巨量 KV 快取記憶體與本地 NVMe、節點間高頻寬全變規格重點。VAST Data 掛金級正好呼應儲存側被拉進來。 | 官方一手 |
| **GB300 NVL72 拓撲感知排程** | 軟體開始感知機櫃 = 客戶**已跨多機櫃跑 100–500+ GPU**。命題從「賣一台」變成「交付完整 NVLink domain 與跨櫃網路」。 | 廠商自報 |
| **TPU / AMD / Intel 各有專場** | 非 NVIDIA 路線在這房間是被正常化的 → **多矽晶機型有真實聽眾**,可主動開這話題探需求。 | 官方一手 |

## 前瞻訊號(走廊上要抓的)

- **Nscale 展台與 Josh Payne 的 keynote 是本屆第一優先。** Nscale 已與微軟簽約約 20 萬顆 GB300:德州約 240MW 園區約 10.4 萬顆(Q3 2026 起分批)、葡萄牙 Sines 約 1.26 萬顆(Q1 2026 起)、英國 Loughton 50MW 約 2.3 萬顆(Q1 2027)。**這是真實的機櫃交付時間表。**〔官方一手 Nscale PR〕
- **競爭旗標:Dell 是 Nscale 的投資人**(與 NVIDIA、Nokia、Blue Owl、Aker 並列)。談 Nscale 供應鏈時要預設 Dell 已在裡面。〔第三方〕
- **Neocloud 密度異常高**:白金含 CoreWeave、Nscale;金級含 Nebius、Lambda;再加 AWS/Google/Azure。一場會至少 5 家 GPU 雲同時在場——**這是買方密度,不是展商密度。**〔官方一手〕
- **Nscale 融資動能**:收購前 23 天剛完成 9 億美元循環信貸,12 家銀行聯貸(含 J.P. Morgan、Goldman Sachs、Morgan Stanley)→ **有錢,且會繼續買。**〔第三方〕
- **推論堆疊的硬體適配決策權正在集中到 Inferact。** vLLM 是各家硬體後端進入生產的必經之路(NVIDIA、AMD、Google TPU、Intel 都派人上台);**誰能先進 vLLM 支援列表,誰的機型就先能賣。認識 Inferact 的人,價值高於認識任何一家雲。**〔官方一手 + 第三方〕

## GAP

- **8/26 的 session 未發布(截至 2026-08-17)= 缺口,不是沒有。** 官方結構顯示 8/26 有 keynote、午餐與 breakout。收購僅隔 3.5 週,**Nscale×Anyscale 的合體路線圖最可能壓在這一天。出發前務必再刷議程。**〔官方一手〕
- **官方從未公布任何一屆的參加人數或公司數。** 唯一找到的「1,325 家公司」是第三方平台預測值,非官方統計,**不要拿來當簡報數字。**〔第三方/預測〕
- **Ray 主軌的 session 標題裡看不到 GB200/GB300/NVL72/InfiniBand 等硬體字樣**——硬體話題藏在 vLLM 場次與供應商 keynote 裡。**要找硬體對話,往 vLLM 那半場走。**
- **Supermicro 不在任何贊助層級名單中** → 沒有主場優勢,全靠走廊與展台外接觸。〔官方一手〕
- **Nscale 的機櫃 OEM/ODM 供應商未公開**(僅知 Dell 為投資人)→ **這是現場最值得直接問出來的一題。**〔未證〕
- **Nscale 收購 Anyscale 一案雙方均未官方證實**(Bloomberg 報導、TechCrunch 轉載)。**寫進讀者頁面時必須保留「未經雙方證實」的 hedge。**
