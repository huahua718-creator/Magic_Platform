# 超感應透視魔術系統 (Magic X-Ray & Scratch LIFF System)

本專案整合「**管理員當日開通** + **雙招式自動交替 (X光長按 / 指尖刮刮樂)** + **動態迫牌演算法** + **關鍵字發送 LIFF 連結**」。

---

## 專案目錄結構

```text
magic_xray_liff/
├── config.py                 # 環境變數與全域設定
├── main.py                   # FastAPI 伺服端、LINE Webhook 與 LIFF 拍照處理
├── run.py                    # 快速啟動進入點
├── requirements.txt          # Python 依賴套件列表
├── .env.example              # 環境變數設定範本
├── README.md                 # 系統規格與使用說明文件
├── core/
│   ├── __init__.py
│   ├── poker_logic.py        # 撲克牌演算法與雙招式推算
│   ├── gemini_service.py     # Gemini Vision 辨識牌背 4 角 (含 OpenCV 備援)
│   └── image_processor.py    # OpenCV 鏡像正片疊底透視顯影
├── database/
│   ├── __init__.py
│   └── state_manager.py      # Redis 狀態管理 (TTL 自動於午夜鎖定)
├── static/
│   ├── magic.html            # LIFF 前端 (X光長按透視 + 指尖刮刮樂)
│   ├── cards/                # 52 張撲克牌牌面資源圖檔
│   └── temp/                 # 運行時動態生成之臨時照片與透視合成圖
└── scripts/
    └── generate_cards.py     # 一鍵生成 52 張標準牌面工具腳本
```

---

## 系統核心互動流程

```text
[前置設定]
魔術師 LINE 輸入: !unlock
   │
   ├──> 系統開通至當日 23:59:59 (Redis TTL 自動鎖定)
   └──> 秘書推播今日第 1 位目標牌 (模式: X光長按)

[現場表演]
任一人 (觀眾或魔術師) 在官方帳號輸入: 解鎖透視魔術
   │
   ├──> 檢查系統是否已解鎖 (未解鎖則回覆一般問候或不予理會)
   └──> 回傳帶有專屬 LIFF URL 的互動 Flex 訊息卡片

[觀眾進入 LIFF 網頁]
拍照上傳 (牌背) ──> 後端運算 (Gemini 座標 + OpenCV 鏡像正片疊底)
   │
   ├── 輪次 0, 2, 4... (偶數): 回傳 mode="XRAY"     --> 長按時透視 + 藍綠色X光掃描線
   └── 輪次 1, 3, 5... (奇數): 回傳 mode="SCRATCH"  --> 手指指尖在牌背多邊形內刮開
   │
   └── 自動推進輪次，並秘密推播通知魔術師下一位目標牌與模式！
```

---

## 快速安裝與啟動

### 1. 安裝環境與依賴套件

建議使用 Python 3.10 以上環境：

```bash
# 進入專案目錄
cd Desktop\magic_xray_liff

# 建立並啟用虛擬環境 (選用)
python -m venv venv
venv\Scripts\activate

# 安裝所需套件
pip install -r requirements.txt
```

### 2. 單車牌 (Bicycle Playing Cards) 檔名關聯

系統已建立與單車牌圖案的完整對應關聯（`static/cards/`）：
- **花色對應**：梅花 `c` -> `club`、方塊 `d` -> `diamond`、紅心 `h` -> `heart`、黑桃 `s` -> `spade`
- **點數對應**：`1` -> `1`、`2~10` -> `2~10`、`11` -> `jack`、`12` -> `queen`、`13` -> `king`
- **範例**：
  - `c1` -> `club_1.png`
  - `d11` -> `diamond_jack.png`
  - `h12` -> `heart_queen.png`
  - `s13` -> `spade_king.png`
- 您可隨時執行測試腳本驗證對應狀態：
  ```bash
  python tests/test_cards.py
  ```

### 3. 設定環境變數

複製 `.env.example` 為 `.env` 並填入參數：
```bash
copy .env.example .env
```

`.env` 內容：
- `LINE_CHANNEL_SECRET`: LINE Messaging API Channel Secret
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Messaging API Channel Access Token
- `BASE_URL`: 服務公開網址（例如 `https://xxxx.ngrok-free.app`）
- `ADMIN_USER_ID`: 魔術師的 LINE User ID
- `LIFF_URL`: LINE LIFF App 網址（例如 `https://liff.line.me/xxxxxx-xxxxxx`）
- `REDIS_URL`: Redis 連線網址（預設 `redis://localhost:6379/0`）
- `GEMINI_API_KEY`: Google Gemini API 金鑰

### 4. 啟動本機 Redis (若尚未啟動)

確保本機或遠端 Redis 正在執行於 `6379` 埠號。

### 5. 啟動服務

```bash
python run.py
```
或
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## LINE Developers 與 LIFF 設定說明

1. **Messaging API Webhook**:
   - Webhook URL 設定為: `https://<你的網域>/callback`
   - 開啟 **Use Webhook**。

2. **LIFF 設定**:
   - 在 LINE Developers 新增一個 LIFF App。
   - **Size**: Full (全螢幕)。
   - **Endpoint URL**: `https://<你的網域>/magic-app`
   - **Scope**: profile, openid, chat_message.write
   - 將產生的 LIFF URL (`https://liff.line.me/xxxx-xxxx`) 填入 `.env` 中的 `LIFF_URL`。

---

## 現場演出流程指南

1. **開場前 (魔術師開通)**：
   - 魔術師在 LINE 中向官方帳號發送 `!unlock`。
   - Bot 會秘密回覆：
     > ✅ 今日魔術已開通！  
     > ⏰ 有效時限：約 XX 小時（午夜自動上鎖）  
     > 👤 第 1 位表演模式：【X光長按透視】  
     > 👉 請迫首張牌：【梅花 11】(c11)  
   - 魔術師依據提示將手中的牌迫給第 1 位觀眾。

2. **第一位觀眾互動 (偶數輪 - X光透視)**：
   - 請觀眾在官方帳號輸入：「**解鎖透視魔術**」。
   - 手機收到 Flex 卡片，點選「**開啟感應鏡頭**」進入 LIFF。
   - 拍照上傳手中的牌背。
   - 畫面上提示：「⚡ 請長按住螢幕上的牌背，透視內部...」。
   - 觀眾長按時，藍綠色 X 光掃描線來回游移，牌背漸漸透明，浮現出鏡像透出的目標花色與點數！放開手立即復原。
   - 同時，後台靜默將輪次 +1，並向魔術師的 LINE 秘密推播第 2 位觀眾的模式與迫牌目標！

3. **第二位觀眾互動 (奇數輪 - 指尖刮刮樂)**：
   - 觀眾同樣輸入「**解鎖透視魔術**」並拍照。
   - 畫面自動切換為全新的「【指尖刮刮樂】」模式！
   - 提示：「✨ 請用指尖在牌背上擦拭，透出正面...」。
   - 觀眾用手指在撲克牌四角範圍內塗抹，牌背紋路隨指尖被擦除刮開，揭曉底層正面！

4. **輪次歸零 (選用)**：
   - 魔術師若需重設輪次，可發送指令 `!reset`。

