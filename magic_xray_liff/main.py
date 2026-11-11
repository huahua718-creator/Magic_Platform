import os
import uuid
from typing import Optional
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage,
    FlexMessage, FlexContainer,
    QuickReply, QuickReplyItem, MessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

from config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, BASE_URL, ADMIN_USER_ID, LIFF_URL
from core.gemini_service import detect_card_corners
from core.image_processor import generate_xray_card
from core.poker_logic import calculate_magic_round, get_card_file_path
from database.state_manager import StateManager

def get_admin_quick_reply() -> QuickReply:
    """管理員專屬底部快速指令標籤選單"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="🔓 解鎖開通", text="!unlock")),
        QuickReplyItem(action=MessageAction(label="📊 狀態查詢", text="!status")),
        QuickReplyItem(action=MessageAction(label="🔄 輪次歸零", text="!reset")),
        QuickReplyItem(action=MessageAction(label="🔗 LIFF 網址", text="!liff")),
        QuickReplyItem(action=MessageAction(label="🎩 指令選單", text="!menu")),
        QuickReplyItem(action=MessageAction(label="🧪 連線測試", text="test"))
    ])

def create_text_msg(text: str, quick_reply=None) -> TextMessage:
    """建立 TextMessage 並安全設定快捷選單 (避開 Pydantic v1 繼承與 alias 模型在 IDE 的建構參數檢查誤判)"""
    data = {"text": text}
    if quick_reply is not None:
        data["quick_reply"] = quick_reply
    return TextMessage.parse_obj(data)

def create_flex_msg(alt_text: str, contents_dict: dict) -> FlexMessage:
    """建立 FlexMessage (避開 Pydantic v1 alias 在 IDE 的建構參數檢查誤判)"""
    return FlexMessage.parse_obj({
        "alt_text": alt_text,
        "contents": FlexContainer.from_dict(contents_dict)
    })

def send_reply(reply_token: str, messages: list):
    """發送 LINE 回覆訊息"""
    req = ReplyMessageRequest.parse_obj({"reply_token": reply_token, "messages": messages})
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(req)

def send_push(to_user_id: str, messages: list):
    """發送 LINE 主動推播訊息"""
    req = PushMessageRequest.parse_obj({"to": to_user_id, "messages": messages})
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).push_message(req)

app = FastAPI(title="Magic X-Ray LIFF System", version="1.0.0")

# 確保靜態資料夾存在並掛載
os.makedirs("static/temp", exist_ok=True)
os.makedirs("static/cards", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.get("/")
async def root():
    return {
        "service": "Magic X-Ray & Scratch LIFF System",
        "status": "online",
        "is_unlocked": StateManager.is_unlocked(),
        "current_stage": StateManager.get_current_stage()
    }

@app.get("/diagnose")
async def run_web_diagnose():
    """線上健康檢查與診斷端點"""
    redis_status = "OK"
    try:
        from database.state_manager import r
        r.ping()
        redis_ok = True
    except Exception as e:
        redis_ok = False
        redis_status = str(e)

    line_status = "OK"
    bot_name = ""
    try:
        with ApiClient(configuration) as api_client:
            bot_info = MessagingApi(api_client).get_bot_info()
            line_ok = True
            bot_name = bot_info.display_name
    except Exception as e:
        line_ok = False
        line_status = str(e)

    return {
        "status": "HEALTHY" if (redis_ok and line_ok) else "ERROR",
        "redis": {
            "connected": redis_ok,
            "detail": redis_status,
            "is_unlocked": StateManager.is_unlocked() if redis_ok else False,
            "current_stage": StateManager.get_current_stage() if redis_ok else 0
        },
        "line": {
            "token_valid": line_ok,
            "bot_name": bot_name,
            "detail": line_status
        },
        "admin_user_id_configured": bool(ADMIN_USER_ID and "YOUR_" not in ADMIN_USER_ID),
        "urls": {
            "base_url": BASE_URL,
            "liff_url": LIFF_URL
        }
    }

@app.get("/magic-app", response_class=HTMLResponse)
async def serve_magic_app():
    with open("static/magic.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        print("❌ [LINE Webhook] 簽章驗證失敗 (Invalid signature)！請確認 LINE_CHANNEL_SECRET 是否正確。")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"❌ [LINE Webhook] 處理訊息異常: {e}")
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id = event.source.user_id
    raw_text = event.message.text.strip()
    # 相容中文全形驚嘆號與大小寫
    text = raw_text.replace("！", "!").strip()
    cmd = text.lower()
    print(f"📩 [LINE 收到訊息] 來自: {user_id} | 內容: '{raw_text}' | 指令化: '{cmd}' | 是否為管理員: {user_id == ADMIN_USER_ID}")

    # 0. 萬用連線測試指令 (任何人輸入 test / ping / 測試 均可驗收 Webhook)
    if cmd in ["test", "ping", "測試", "連線測試"]:
        is_open = StateManager.is_unlocked()
        reply = (
            f"🏓 系統連線完全正常！\n\n"
            f"👤 您的 LINE User ID：\n{user_id}\n\n"
            f"👑 是否為管理員：{'✅ 是' if user_id == ADMIN_USER_ID else '❌ 否 (與系統設定不同)'}\n"
            f"🔮 今日魔術狀態：{'🟢 已開通' if is_open else '🔒 未開通'}"
        )
        qr = get_admin_quick_reply() if user_id == ADMIN_USER_ID else None
        send_reply(event.reply_token, [create_text_msg(reply, quick_reply=qr)])
        return

    # 1. 管理員管理指令
    if cmd in ["!menu", "!help", "menu", "選單", "指令"]:
        if user_id != ADMIN_USER_ID:
            return
        menu_text = (
            "🎩【魔術師管理指令選單】\n"
            "━━━━━━━━━━━━━━━\n"
            "⚡ !unlock : 開通今日表演 + 取得 LIFF 網址\n"
            "📊 !status : 查詢目前輪次、時效與迫牌目標\n"
            "🔄 !reset  : 將輪次歸零至首張牌\n"
            "🔗 !liff   : 直接取得透視魔術 LIFF 網頁\n"
            "🧪 test    : 系統連線與身分診斷\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 點擊下方快捷按鈕可立即發送指令！"
        )
        send_reply(event.reply_token, [create_text_msg(menu_text, quick_reply=get_admin_quick_reply())])
        return

    if cmd == "!unlock":
        if user_id != ADMIN_USER_ID:
            print(f"⚠️ [權限警告] 使用者 {user_id} 嘗試執行 !unlock，但與設定的 ADMIN_USER_ID ({ADMIN_USER_ID}) 不符！")
            send_reply(
                event.reply_token,
                [create_text_msg(f"⚠️ 權限不足。\n您的 LINE User ID 為：\n{user_id}\n請將此 ID 設定至 ADMIN_USER_ID 環境變數。")]
            )
            return

        secs = StateManager.unlock_today()
        hours = round(secs / 3600, 1)
        info = calculate_magic_round(0)

        # 包含 LIFF 網址的魔術師開通專用卡片
        flex_unlock = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ 今日魔術已開通！", "weight": "bold", "size": "lg", "color": "#06c755"},
                    {"type": "text", "text": f"⏰ 有效時限：約 {hours} 小時（午夜自動上鎖）", "size": "xs", "color": "#888888", "margin": "sm"},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {"type": "text", "text": f"👤 第 1 位表演模式：{info['mode_name']}", "weight": "bold", "size": "sm", "color": "#0099ff"},
                            {"type": "text", "text": f"👉 請迫首張牌：【{info['card_name']}】", "weight": "bold", "size": "md", "color": "#e60000", "margin": "xs"},
                            {"type": "text", "text": f"📄 單車牌檔名：{info['card_filename']}", "size": "xs", "color": "#666666", "margin": "xs"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#06c755",
                        "action": {
                            "type": "uri",
                            "label": "開啟透視魔術鏡頭 (LIFF)",
                            "uri": LIFF_URL
                        }
                    }
                ]
            }
        }

        send_reply(
            event.reply_token,
            [
                create_flex_msg("今日魔術已開通", flex_unlock),
                create_text_msg(f"🔗 LIFF 連結備用：\n{LIFF_URL}", quick_reply=get_admin_quick_reply())
            ]
        )
        return

    elif cmd == "!status":
        if user_id != ADMIN_USER_ID:
            return
        is_open = StateManager.is_unlocked()
        if not is_open:
            msg = "🔒 今日魔術尚未開通！請輸入 !unlock 進行解鎖。"
        else:
            stage = StateManager.get_current_stage()
            info = calculate_magic_round(stage)
            rem_secs = StateManager.get_remaining_seconds()
            rem_hours = round(rem_secs / 3600, 1)
            msg = (
                f"📊【魔術即時狀態】\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🟢 狀態：已開通（剩餘約 {rem_hours} 小時）\n"
                f"👥 目前輪次：第 {stage + 1} 位觀眾\n"
                f"✨ 目前模式：{info['mode_name']}\n"
                f"👉 當前迫牌：【{info['card_name']}】({info['card_filename']})\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🔗 LIFF 網址：\n{LIFF_URL}"
            )
        send_reply(event.reply_token, [create_text_msg(msg, quick_reply=get_admin_quick_reply())])
        return

    elif cmd in ["!liff", "liff"]:
        flex_liff = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "超感應透視魔術", "weight": "bold", "size": "xl", "color": "#06c755"},
                    {"type": "text", "text": "請進入連線系統，將手中的牌背拍照傳送。", "size": "sm", "color": "#888888", "margin": "md", "wrap": True}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#06c755",
                        "action": {
                            "type": "uri",
                            "label": "開啟感應鏡頭",
                            "uri": LIFF_URL
                        }
                    }
                ]
            }
        }
        qr = get_admin_quick_reply() if user_id == ADMIN_USER_ID else None
        send_reply(
            event.reply_token,
            [
                create_flex_msg("開啟感應鏡頭", flex_liff),
                create_text_msg(f"🔗 LIFF 直連網址：\n{LIFF_URL}", quick_reply=qr)
            ]
        )
        return

    elif cmd == "!reset":
        if user_id != ADMIN_USER_ID:
            return
        StateManager.reset_stage()
        info = calculate_magic_round(0)
        msg = f"🔄 輪次已歸零。\n首發模式：{info['mode_name']}\n迫牌目標：【{info['card_name']}】({info['card_filename']})"
        send_reply(event.reply_token, [create_text_msg(msg, quick_reply=get_admin_quick_reply())])
        return

    # 2. 任一人輸入「解鎖透視魔術」
    if text == "解鎖透視魔術":
        if not StateManager.is_unlocked():
            send_reply(event.reply_token, [create_text_msg("大師目前的感知通道尚未開啟，請稍候。")])
            return

        # 檢查非管理員每日體驗配額 (上限 2 次)
        quota = StateManager.get_user_quota(user_id, ADMIN_USER_ID, max_limit=2)
        if not quota["allowed"]:
            limit_msg = (
                "🔒 今日感應能量已達上限！\n"
                "━━━━━━━━━━━━━━━\n"
                "您今日的體驗次數已滿（每位觀眾每日限定 2 次）。\n"
                "感謝您的參與，請明天再來，或由魔術大師親自為您演示！"
            )
            send_reply(event.reply_token, [create_text_msg(limit_msg)])
            return

        # 系統已解鎖且有額度：回傳表演專用 LIFF 卡片 (網址附帶使用者身分參數)
        user_liff_url = f"{LIFF_URL}?uid={user_id}" if "?" not in LIFF_URL else f"{LIFF_URL}&uid={user_id}"
        remaining_tip = f"（今日剩餘體驗次數：{quota['remaining']} 次）" if not quota["is_admin"] else "（魔術師管理模式：不限次數）"

        flex_payload = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "超感應透視魔術", "weight": "bold", "size": "xl", "color": "#06c755"},
                    {"type": "text", "text": f"請進入連線系統，將手中的牌背拍照傳送。\n{remaining_tip}", "size": "xs", "color": "#888888", "margin": "md", "wrap": True}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#06c755",
                        "action": {
                            "type": "uri",
                            "label": "開啟感應鏡頭",
                            "uri": user_liff_url
                        }
                    }
                ]
            }
        }

        send_reply(event.reply_token, [create_flex_msg("開啟感應鏡頭", flex_payload)])

@handler.add(FollowEvent)
def handle_follow_event(event):
    """當新好友加入時，自動發送歡迎訊息與透視魔術入口卡片"""
    user_id = event.source.user_id
    print(f"🎉 [新好友加入] User ID: {user_id}")

    welcome_payload = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "✨ 歡迎進入超感應魔術世界", "weight": "bold", "size": "md", "color": "#06c755"},
                {"type": "text", "text": "請將您手中的撲克牌（牌背朝上）放置於桌上，點擊下方按鈕啟動感應相機拍照存證！", "size": "sm", "color": "#666666", "margin": "md", "wrap": True}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#06c755",
                    "action": {
                        "type": "uri",
                        "label": "開啟感應鏡頭",
                        "uri": LIFF_URL
                    }
                }
            ]
        }
    }

    try:
        send_reply(event.reply_token, [create_flex_msg("歡迎體驗超感應透視魔術", welcome_payload)])
    except Exception as e:
        print(f"❌ [歡迎訊息發送異常]: {e}")

@app.post("/api/liff/upload")
async def liff_upload_photo(
    photo: UploadFile = File(...),
    uid: Optional[str] = Form(None)
):
    """LIFF 拍照上傳後端運算端點"""
    if not StateManager.is_unlocked():
        return JSONResponse(status_code=403, content={"status": "LOCKED", "detail": "魔術今日尚未開通"})

    # 檢查該使用者的每日配額 (非管理員每日上限 2 次)
    if uid:
        quota = StateManager.get_user_quota(uid, ADMIN_USER_ID, max_limit=2)
        if not quota["allowed"]:
            return JSONResponse(status_code=403, content={"status": "LIMIT_REACHED", "detail": "今日感應能量已耗盡（每日限定體驗 2 次），請明天再來或由大師親自為您演示！"})

    save_dir = "static/temp"
    os.makedirs(save_dir, exist_ok=True)
    file_id = uuid.uuid4().hex
    orig_filename = f"orig_{file_id}.jpg"
    orig_path = os.path.join(save_dir, orig_filename)

    with open(orig_path, "wb") as f:
        content = await photo.read()
        f.write(content)

    # 1. 取得當前輪次的迫牌與招式模式
    stage = StateManager.get_current_stage()
    current_round = calculate_magic_round(stage)

    # 2. Gemini 辨識牌背 4 角
    corners = await detect_card_corners(orig_path)
    if not corners or len(corners) != 4:
        return JSONResponse(status_code=400, content={"status": "FAIL", "detail": "無法辨識牌背四角，請對焦後重新拍照"})

    # 3. OpenCV 鏡像正片疊底 (含極致記憶體控管)
    card_face_path = current_round.get("card_file_path") or get_card_file_path(current_round["card_code"])
    revealed_filename = f"revealed_{file_id}.jpg"
    revealed_path = os.path.join(save_dir, revealed_filename)

    _, corners = generate_xray_card(
        original_img_path=orig_path,
        card_face_path=card_face_path,
        corners=corners,
        output_path=revealed_path,
        opacity=0.88,
        mode=current_round["mode"]
    )

    # 4. 輪次推進 + 1，並扣除該使用者 1 次額度
    StateManager.advance_stage()
    if uid:
        StateManager.increment_user_usage(uid, ADMIN_USER_ID)
    next_round = calculate_magic_round(stage + 1)

    # 5. 秘密推播通知魔術師下一張牌與模式
    try:
        msg = (
            f"🔔 第 {stage + 1} 位表演完成 ({current_round['mode_name']})\n"
            f"👉 下一位模式：{next_round['mode_name']}\n"
            f"👉 請迫牌：【{next_round['card_name']}】({next_round['card_filename']})"
        )
        send_push(ADMIN_USER_ID, [create_text_msg(msg)])
    except Exception as e:
        print(f"Notify admin error: {e}")

    # 6. 回傳模式代碼與渲染所需資源
    return {
        "status": "SUCCESS",
        "mode": current_round["mode"], # "XRAY" 或 "SCRATCH"
        "original_url": f"{BASE_URL}/static/temp/{orig_filename}",
        "revealed_url": f"{BASE_URL}/static/temp/{revealed_filename}",
        "corners": corners
    }

