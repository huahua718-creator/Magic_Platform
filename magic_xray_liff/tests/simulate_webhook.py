import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hmac
import hashlib
import base64
import json
import requests
from config import LINE_CHANNEL_SECRET, BASE_URL, ADMIN_USER_ID

def test_webhook():
    url = f"{BASE_URL}/callback"
    print(f"測試向 Webhook 發送模擬訊息: {url}")

    # 模擬 LINE 傳送的 MessageEvent
    payload = {
        "destination": "Uebdd419003b5865c45bf93256833349d",
        "events": [
            {
                "type": "message",
                "message": {
                    "type": "text",
                    "id": "1234567890",
                    "text": "test"
                },
                "timestamp": 1620000000000,
                "source": {
                    "type": "user",
                    "userId": ADMIN_USER_ID
                },
                "replyToken": "00000000000000000000000000000000",
                "mode": "active"
            }
        ]
    }

    body = json.dumps(payload, ensure_ascii=False)
    # 計算 X-Line-Signature
    hash_obj = hmac.new(LINE_CHANNEL_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(hash_obj).decode('utf-8')

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Line-Signature": signature
    }

    print(f"發送請求中...")
    resp = requests.post(url, data=body.encode('utf-8'), headers=headers)
    print(f"狀態碼: {resp.status_code}")
    print(f"回傳內容: {resp.text}")

if __name__ == "__main__":
    test_webhook()
