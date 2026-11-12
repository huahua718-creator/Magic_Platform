import os
from dotenv import load_dotenv

# 嘗試讀取 platform_core 下的 .env，若無則讀取 magic_xray_liff 下的 .env 方便無縫切換
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")
if not os.path.exists(env_path):
    fallback_env = os.path.join(os.path.dirname(base_dir), "magic_xray_liff", ".env")
    if os.path.exists(fallback_env):
        env_path = fallback_env

load_dotenv(env_path)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_LINE_CHANNEL_ACCESS_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "YOUR_ADMIN_LINE_USER_ID")

# LIFF 設定 (建議在 LINE Developers 設定 Endpoint URL 為 BASE_URL/liff-router)
LIFF_URL = os.getenv("LIFF_URL", f"{BASE_URL}/liff-router")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Firebase 設定 (支援填入 JSON 字串或服務帳號憑證檔案路徑)
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
APP_SECRET_SALT = os.getenv("APP_SECRET_SALT", "magic-saas-secret-2026")

# 魔術註冊表 (未來新增魔術只需於此註冊，選單與訂閱權限自動生成!)
TRICK_REGISTRY = {
    "xray_card": {
        "id": "xray_card",
        "name": "超感應 X 光 & 刮刮樂透視",
        "short_name": "X光透視撲克",
        "subtitle": "AI 辨識牌背 + X光掃描與指尖刮刮樂雙招式輪替",
        "entry_path": "/tricks/xray/magic.html",
        "tier": "basic",  # basic / pro
        "free_trial_daily": 2,  # 未訂閱體驗者每日可體驗 2 次
        "color": "#06c755"
    },
    "keycard_ar": {
        "id": "keycard_ar",
        "name": "數位透視眼 (WebAR 火柴人)",
        "short_name": "數位透視眼 AR",
        "subtitle": "手機 WebAR 追蹤撲克牌 + 火柴人預言綠幕自動快照",
        "entry_path": "/tricks/keycard/index.html",
        "tier": "pro",    # pro 訂閱專屬
        "free_trial_daily": 0,  # 僅限訂閱會員使用
        "color": "#00aaff"
    },
    "frozen_proof_ar": {
        "id": "frozen_proof_ar",
        "name": "記憶流痕 (Frozen Proof AR)",
        "short_name": "記憶流痕 AR",
        "subtitle": "雙機黑屏時鐘手勢隱密選牌 + MindAR 即時相機留影預言",
        "entry_path": "/tricks/frozen/index.html",
        "tier": "pro",
        "free_trial_daily": 0,
        "color": "#a855f7"
    },
    "drawcards": {
        "id": "drawcards",
        "name": "多人畫牌 (Draw Cards)",
        "short_name": "多人畫牌",
        "subtitle": "極簡讀心術 + 隱形選牌矩陣 + 多人手繪 3D 翻牌",
        "entry_path": "/tricks/drawcards/index.html",
        "tier": "pro",
        "free_trial_daily": 0,
        "color": "#f59e0b"
    },
    "drawacard": {
        "id": "drawacard",
        "name": "畫魔術師 (Draw a Card)",
        "short_name": "畫魔術師",
        "subtitle": "手繪專屬魔術師進場 + 雙擊右下角密技選牌 + 3D 翻牌現形",
        "entry_path": "/tricks/drawacard/index.html",
        "tier": "pro",
        "free_trial_daily": 0,
        "color": "#10b981"
    },
    "pickonecards": {
        "id": "pickonecards",
        "name": "手機迫牌 (多人版)",
        "short_name": "手機迫牌多人版",
        "subtitle": "QR 連線多人同步迫牌 + 日期演算順延 + 長按隱密 4x13 滑動改牌",
        "entry_path": "/tricks/pickonecards/index.html",
        "tier": "pro",
        "free_trial_daily": 0,
        "color": "#e11d48"
    },
    "pinkingcard": {
        "id": "pinkingcard",
        "name": "單人迫牌 (The Prediction)",
        "short_name": "單人迫牌",
        "subtitle": "高速單機輪播瞬停 + 日期演算法連鎖預言 + 長按隱密指定首張強迫牌",
        "entry_path": "/tricks/pinkingcard/index.html",
        "tier": "pro",
        "free_trial_daily": 0,
        "color": "#db2777"
    }
}
