"""
超感應透視魔術 - 系統連線全自動診斷工具
可診斷:
1. .env 環境變數是否完整配置
2. Redis 資料庫連線狀態
3. LINE Messaging API Token 有效性
4. 測試直接推播訊息至魔術師個人手機 LINE
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    ADMIN_USER_ID,
    BASE_URL,
    LIFF_URL,
    REDIS_URL,
    GEMINI_API_KEY
)

def run_diagnostics():
    print("=" * 60)
    print("🔍 [開始全自動系統連線診斷]")
    print("=" * 60)

    # 1. 檢查各變數是否已填寫
    print("\n[項目 1] 檢查環境變數配置:")
    vars_to_check = {
        "LINE_CHANNEL_SECRET": LINE_CHANNEL_SECRET,
        "LINE_CHANNEL_ACCESS_TOKEN": LINE_CHANNEL_ACCESS_TOKEN,
        "ADMIN_USER_ID": ADMIN_USER_ID,
        "BASE_URL": BASE_URL,
        "LIFF_URL": LIFF_URL,
        "REDIS_URL": REDIS_URL,
        "GEMINI_API_KEY": GEMINI_API_KEY
    }

    all_filled = True
    for key, val in vars_to_check.items():
        masked = str(val)[:6] + "..." + str(val)[-4:] if len(str(val)) > 12 else str(val)
        is_default = "your_" in str(val).lower() or val in ["", "YOUR_ADMIN_LINE_USER_ID", "YOUR_LINE_CHANNEL_SECRET", "YOUR_LINE_CHANNEL_ACCESS_TOKEN"]
        if is_default or not val:
            print(f"  ❌ {key}: 尚未填寫有效值 (目前值: {val})")
            all_filled = False
        else:
            print(f"  ✅ {key}: {masked}")

    # 2. 測試 Redis 連線
    print("\n[項目 2] 測試 Redis 資料庫連線:")
    try:
        import redis
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
        r.ping()
        print(f"  ✅ Redis 連線成功！(目前魔術開通狀態 is_unlocked: {r.exists('magic:is_unlocked') == 1})")
    except Exception as e:
        print(f"  ❌ Redis 連線失敗！詳細原因: {e}")

    # 3. 測試 LINE Messaging API Token
    print("\n[項目 3] 測試 LINE Messaging API 連線:")
    try:
        from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
        configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        with ApiClient(configuration) as api_client:
            bot_api = MessagingApi(api_client)
            bot_info = bot_api.get_bot_info()
            print(f"  ✅ LINE Messaging API Token 有效！")
            print(f"     官方帳號名稱: {bot_info.display_name}")
            print(f"     官方帳號 User ID: {bot_info.user_id}")

            # 4. 測試推播給魔術師
            print("\n[項目 4] 測試推播訊息給魔術師個人手機:")
            if ADMIN_USER_ID and not "YOUR_" in ADMIN_USER_ID:
                try:
                    test_msg = "🔔【魔術系統測試】若您收到此訊息，代表 LINE Messaging API 與魔術師 User ID 完全串接成功！"
                    bot_api.push_message(PushMessageRequest(to=ADMIN_USER_ID, messages=[TextMessage(text=test_msg)]))
                    print(f"  ✅ 測試推播發送成功！請檢查手機 LINE (User ID: {ADMIN_USER_ID}) 是否收到通知。")
                except Exception as push_err:
                    print(f"  ❌ 推播發送失敗！可能 ADMIN_USER_ID 有誤或未加官方帳號為好友: {push_err}")
            else:
                print("  ⚠️ 跳過推播測試: ADMIN_USER_ID 尚未填入有效值。")

    except Exception as line_err:
        print(f"  ❌ LINE Messaging API Token 驗證失敗: {line_err}")

    print("\n" + "=" * 60)
    print("診斷完畢！請根據上述 ❌ 標記項目進行修正。")
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostics()

