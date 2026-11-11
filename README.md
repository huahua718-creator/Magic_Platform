# 奇幻數位魔術訂閱制平台 (Magic SaaS Multi-Trick Platform)

整合多款互動數位魔術，結合 **LINE Messaging API 滑動選單** + **LIFF 全螢幕互動** + **Firebase / Redis 雙模訂閱授權管理** + **多租戶狀態隔離**。

---

## 📂 專案統一根目錄架構

```text
Magic_Platform/
├── platform_core/                 # 【SaaS 平台核心】統一接收 LINE Webhook、訂閱驗證與選單
│   ├── main.py                    # 統一伺服端入口 & 掛載所有魔術前端
│   ├── config.py                  # TRICK_REGISTRY 魔術註冊表與環境變數
│   ├── requirements.txt           # 全平台 Python 套件依賴 (含 firebase-admin)
│   ├── run.py                     # 統一啟動腳本
│   └── saas/
│       ├── subscription_manager.py # 雙模訂閱授權 (Firebase Firestore / Redis) 與 Token 驗證
│       └── menu_builder.py        # 動態滑動魔術櫃 (Flex Carousel) & 底部快捷選單
│
├── magic_xray_liff/               # 【魔術 1】超感應 X 光 & 指尖刮刮樂透視撲克
│   ├── core/                      # Gemini AI 偵測 + OpenCV 鏡像正片疊底 + 迫牌演算法
│   └── static/magic.html          # LIFF 全英文科幻 UI (中央開關 -> 圓環讀取 -> 長按2秒顯影)
│
├── keycard/                       # 【魔術 2】數位透視眼 (WebAR 火柴人預言快照)
│   ├── index.html                 # 整合訂閱授權攔截 (/api/auth/verify)
│   ├── magic-cards.mind           # MindAR 撲克牌追蹤特徵檔
│   └── stickman1~3.mp4            # 綠幕去背火柴人 AR 動畫
│
├── render.yaml                    # 一鍵部署至 Render.com
└── .gitignore
```

---

## 💎 訂閱制與多租戶運作機制

1. **雙引擎訂閱資料庫**：
   - 設定 `FIREBASE_CREDENTIALS_JSON` 環境變數後，自動啟用 **Firebase Firestore**（`magicians` 集合）記錄訂閱會員、方案與到期日。
   - 若尚未設定 Firebase，自動降級使用 **Redis** 儲存訂閱資料，開箱即可馬上在 LINE 測試完整訂閱授權！
2. **多租戶安全隔離（Multi-Tenant）**：
   - 每個訂閱魔術師擁有獨立的輪次進度與秘密迫牌推播，多位魔術師同時現場表演**完全互不干擾**。
   - 啟動魔術會簽發當日防偽 Token (`?mid=...&token=...`)，未訂閱或過期的外部網址將被直接阻擋無法開啟。
3. **魔術選單與分級體驗**：
   - **魔術 1（X光透視撲克）**：訂閱魔術師無限制表演；未訂閱体験者預設每日可試玩 2 次。
   - **魔術 2（數位透視眼 AR）**：訂閱會員專屬道具，未訂閱用戶點擊選單將提示升級解鎖。

---

## 🎩 LINE Bot 指令一覽

### 通用 / 訂閱者操作
- **`魔術選單`** / **`選單`** / **`!menu`**：彈出「數位魔術櫃滑動卡片」與底部快捷鍵，選擇要表演的魔術。
- **`!sub`** / **`我的訂閱`**：查詢個人訂閱狀態、到期時間與您的 LINE User ID。
- **`!play xray_card`**：啟動 X 光透視撲克並取得專屬連結與首張迫牌。
- **`!play keycard_ar`**：啟動數位透視眼 WebAR 並取得授權連結。
- **`!reset`**：將個人的 X 光透視輪次歸零。

### 超級管理員（Platform Owner）專屬訂閱管理指令
- **`!grant <UserID> [天數]`**：為指定魔術師開通訂閱（預設 30 天），並自動推播通知對方！
  *範例：`!grant U1234567890abcdef 30`*
- **`!revoke <UserID>`**：停用指定用戶的訂閱權限。
- **`!subscribers`**：查看平台目前已登記的訂閱戶狀態清單。

---

## 🛠️ 如何新增第 3 個、第 4 個新魔術？

1. 將新魔術的資料夾放入 `Magic_Platform/`（例如 `Magic_Platform/mind_box/`）。
2. 在 `platform_core/config.py` 的 `TRICK_REGISTRY` 中註冊該魔術資料。
3. 在 `platform_core/main.py` 掛載該魔術的靜態目錄或 API 路由。
4. 魔術櫃滑動選單、訂閱權限驗證與 LINE 快捷按鈕會**全自動生效**！

