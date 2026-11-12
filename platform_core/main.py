import os
import sys
import uuid
from typing import Optional
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage,
    FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# 引入當前 platform_core 與魔術目錄 (確保不會產生命名衝突)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
XRAY_DIR = os.path.join(ROOT_DIR, "magic_xray_liff")
KEYCARD_DIR = os.path.join(ROOT_DIR, "keycard")
FROZEN_DIR = os.path.join(ROOT_DIR, "theFrozenProofMindAR")
DRAWCARDS_DIR = os.path.join(ROOT_DIR, "drawcards")
DRAWACARD_DIR = os.path.join(ROOT_DIR, "drawacard")
PICKONECARDS_DIR = os.path.join(ROOT_DIR, "pickonecards")

sys.path.insert(0, CURRENT_DIR)
sys.path.insert(1, ROOT_DIR)

from config import (
    LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN,
    BASE_URL, ADMIN_USER_ID, LIFF_URL, TRICK_REGISTRY
)
from saas.subscription_manager import SubscriptionManager
from saas.menu_builder import build_quick_reply, build_magic_carousel

# 複用 magic_xray_liff 核心影像與演算法引擎
from magic_xray_liff.core.gemini_service import detect_card_corners
from magic_xray_liff.core.image_processor import generate_xray_card
from magic_xray_liff.core.poker_logic import calculate_magic_round, get_card_file_path

app = FastAPI(title="Magic SaaS Multi-Trick Platform", version="2.0.0")

# 確保暫存與靜態資料夾存在
XRAY_STATIC_DIR = os.path.join(XRAY_DIR, "static")
XRAY_TEMP_DIR = os.path.join(XRAY_STATIC_DIR, "temp")
XRAY_CARDS_DIR = os.path.join(XRAY_STATIC_DIR, "cards")
os.makedirs(XRAY_TEMP_DIR, exist_ok=True)
os.makedirs(XRAY_CARDS_DIR, exist_ok=True)

# 掛載各魔術的靜態與前端頁面資源
app.mount("/tricks/xray", StaticFiles(directory=XRAY_STATIC_DIR), name="trick_xray")
app.mount("/static", StaticFiles(directory=XRAY_STATIC_DIR), name="legacy_static") # 兼容舊路徑
if os.path.exists(KEYCARD_DIR):
    app.mount("/tricks/keycard", StaticFiles(directory=KEYCARD_DIR, html=True), name="trick_keycard")
if os.path.exists(FROZEN_DIR):
    app.mount("/tricks/frozen", StaticFiles(directory=FROZEN_DIR, html=True), name="trick_frozen")
if os.path.exists(DRAWCARDS_DIR):
    app.mount("/tricks/drawcards", StaticFiles(directory=DRAWCARDS_DIR, html=True), name="trick_drawcards")
if os.path.exists(DRAWACARD_DIR):
    app.mount("/tricks/drawacard", StaticFiles(directory=DRAWACARD_DIR, html=True), name="trick_drawacard")
if os.path.exists(PICKONECARDS_DIR):
    app.mount("/tricks/pickonecards", StaticFiles(directory=PICKONECARDS_DIR, html=True), name="trick_pickonecards")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


def create_text_msg(text: str, quick_reply=None) -> TextMessage:
    """建立 TextMessage 並賦予快捷選單（避開 Pydantic v1 繼承與 alias 模型在 IDE 的 __init__ 靜態檢查誤判）"""
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


@app.get("/")
async def root():
    return {
        "platform": "Magic SaaS Multi-Trick Platform",
        "status": "online",
        "subscription_engine": SubscriptionManager.get_backend_type(),
        "registered_tricks": list(TRICK_REGISTRY.keys())
    }


@app.get("/diagnose")
async def platform_diagnose():
    """平台全域連線與訂閱引擎診斷"""
    from saas.subscription_manager import r
    try:
        r.ping()
        redis_ok = True
        redis_msg = "OK"
    except Exception as e:
        redis_ok = False
        redis_msg = str(e)

    try:
        with ApiClient(configuration) as api_client:
            bot_info = MessagingApi(api_client).get_bot_info()
            line_ok = True
            bot_name = bot_info.display_name
    except Exception as e:
        line_ok = False
        bot_name = str(e)

    return {
        "status": "HEALTHY" if (redis_ok and line_ok) else "ERROR",
        "subscription_engine": SubscriptionManager.get_backend_type(),
        "redis": {"connected": redis_ok, "detail": redis_msg},
        "line": {"token_valid": line_ok, "bot_name": bot_name},
        "tricks_count": len(TRICK_REGISTRY),
        "base_url": BASE_URL
    }


@app.get("/liff-router")
async def liff_router(trick: str = "xray_card", mid: str = "", uid: str = "", token: str = ""):
    """
    LIFF 統一轉導路由器:
    讓單一 LIFF App 可以根據網址參數，無縫進入不同魔術道具介面
    """
    if trick == "keycard_ar":
        target = f"/tricks/keycard/index.html?mid={mid}&token={token}"
    elif trick == "frozen_proof_ar":
        target = f"/tricks/frozen/index.html?mode=master&mid={mid}&token={token}"
    elif trick == "drawcards":
        target = f"/tricks/drawcards/index.html?mid={mid}&token={token}"
    elif trick == "drawacard":
        target = f"/tricks/drawacard/index.html?mid={mid}&token={token}"
    elif trick == "pickonecards":
        target = f"/tricks/pickonecards/index.html?mid={mid}&token={token}"
    else:
        target = f"/tricks/xray/magic.html?mid={mid}&uid={uid}&token={token}"
    return RedirectResponse(url=target)


@app.get("/magic-app")
async def legacy_magic_app_redirect(mid: str = "", uid: str = "", token: str = ""):
    """向下兼容原先 /magic-app 路徑"""
    return RedirectResponse(url=f"/tricks/xray/magic.html?mid={mid}&uid={uid}&token={token}")


@app.get("/api/auth/verify")
async def verify_trick_authorization(trick: str, mid: str = "", token: str = ""):
    """
    統一訂閱授權驗證 API (供純前端道具如 keycard_ar 載入前驗證)
    """
    if not mid or not token:
        return {"authorized": False, "message": "🔒 缺少訂閱授權憑證，請從官方帳號魔術選單進入！"}

    is_valid = SubscriptionManager.verify_launch_token(mid, trick, token)
    if not is_valid:
        return {"authorized": False, "message": "🔒 授權無效或訂閱已到期，請續費訂閱後再使用！"}

    return {"authorized": True, "magician_id": mid, "trick": trick}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"❌ [Webhook 處理異常]: {e}")
    return "OK"


@handler.add(FollowEvent)
def handle_follow(event):
    """新好友加入自動發送平台歡迎詞與魔術選單"""
    user_id = event.source.user_id
    welcome_msg = create_text_msg(
        text=(
            "🎩 歡迎來到【奇幻數位魔術訂閱平台】！\n"
            "━━━━━━━━━━━━━━━\n"
            "這裡整合了多款最前沿的數位互動魔術道具。\n"
            "👇 請點擊下方「魔術選單」立即瀏覽與體驗，或查詢您的訂閱權限！"
        ),
        quick_reply=build_quick_reply(user_id)
    )
    try:
        send_reply(event.reply_token, [welcome_msg])
    except Exception as e:
        print(f"Follow reply error: {e}")


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id = event.source.user_id
    raw_text = event.message.text.strip()
    text = raw_text.replace("！", "!").strip()
    cmd = text.lower()
    print(f"📩 [Platform Bot] User={user_id} | Text='{raw_text}'")

    quick_reply = build_quick_reply(user_id)

    # 1. 系統連線與個人 ID 查詢
    if cmd in ["test", "ping", "測試", "id"]:
        profile = SubscriptionManager.get_magician_profile(user_id)
        reply = (
            f"🏓 平台服務連線正常！\n"
            f"💾 訂閱引擎：{SubscriptionManager.get_backend_type()}\n\n"
            f"👤 您的 LINE User ID（開通訂閱專用）：\n{user_id}\n\n"
            f"🎖️ 帳號身分：{profile['role']}\n"
            f"📅 訂閱到期：{profile['expire_at'] or '未訂閱'}"
        )
        send_reply(event.reply_token, [create_text_msg(reply, quick_reply=quick_reply)])
        return

    # 2. 魔術文字/滑動選單 (所有魔術總入口)
    if cmd in ["魔術選單", "選單", "!menu", "menu", "tricks", "!help", "指令"]:
        carousel_dict = build_magic_carousel(user_id)
        helper_txt = create_text_msg(
            "🎩 請左右滑動上方卡片挑選要演出的魔術，或點擊下方快捷按鈕：",
            quick_reply=quick_reply
        )
        send_reply(
            event.reply_token,
            [create_flex_msg("數位魔術櫃選單", carousel_dict), helper_txt]
        )
        return

    # 3. 查詢我的訂閱狀態
    if cmd in ["!sub", "訂閱", "我的訂閱", "!status"]:
        profile = SubscriptionManager.get_magician_profile(user_id)
        if profile["role"] == "super_admin":
            sub_msg = (
                "👑【平台超級管理員權限】\n"
                "━━━━━━━━━━━━━━━\n"
                "✅ 全系列魔術永久免費解鎖\n"
                "⚙️ 管理訂閱指令：\n"
                "• !grant <UserID> <天數>\n"
                "• !revoke <UserID>\n"
                "• !subscribers"
            )
        elif profile["is_subscribed"]:
            tricks_names = [TRICK_REGISTRY[t]["short_name"] for t in profile["unlocked_tricks"] if t in TRICK_REGISTRY]
            sub_msg = (
                f"💎【正式訂閱魔術師】\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📌 方案：{profile['plan'].upper()}\n"
                f"⏰ 到期時間：{profile['expire_at']}\n"
                f"🔓 已解鎖魔術：\n  • " + "\n  • ".join(tricks_names)
            )
        else:
            sub_msg = (
                "🔒【尚未成為訂閱會員】\n"
                "━━━━━━━━━━━━━━━\n"
                "您目前為免費體驗身分，僅可試玩基礎魔術（每日限次）。\n\n"
                "💡 如何開通全系列魔術訂閱？\n"
                f"請複製您的專屬 User ID：\n{user_id}\n\n"
                "聯繫管理員或透過訂閱付款開通，即可無限次使用 X光透視、數位透視眼 AR 與未來所有新魔術！"
            )
        send_reply(event.reply_token, [create_text_msg(sub_msg, quick_reply=quick_reply)])
        return

    # 4. 超級管理員：開通 / 停用訂閱戶指令
    if SubscriptionManager.is_super_admin(user_id):
        if cmd.startswith("!grant "):
            parts = text.split()
            if len(parts) >= 2:
                target_uid = parts[1]
                days = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 30
                rec = SubscriptionManager.grant_subscription(target_uid, days=days)
                reply_txt = f"✅ 已成功為用戶開通訂閱！\n👤 用戶：{target_uid}\n⏰ 到期日：{rec['expire_at']}\n🔓 權限：全系列魔術解鎖"
                # 同步私訊通知訂閱者
                try:
                    send_push(
                        target_uid,
                        [create_text_msg(f"🎉 恭喜！您的【奇幻魔術 SaaS 訂閱會員】已開通（有效期 {days} 天，至 {rec['expire_at'][:10]}）！\n現在請輸入「魔術選單」立即開始演出！", quick_reply=build_quick_reply(target_uid))]
                    )
                except Exception as pe:
                    reply_txt += f"\n⚠️ (私訊通知對方失敗: {pe})"
                send_reply(event.reply_token, [create_text_msg(reply_txt, quick_reply=quick_reply)])
                return

        elif cmd.startswith("!revoke "):
            parts = text.split()
            if len(parts) >= 2:
                target_uid = parts[1]
                SubscriptionManager.revoke_subscription(target_uid)
                send_reply(event.reply_token, [create_text_msg(f"🚫 已停用用戶 {target_uid} 的訂閱權限。", quick_reply=quick_reply)])
                return

        elif cmd == "!subscribers":
            subs = SubscriptionManager.list_all_subscribers()
            lines = [f"👥 平台登記訂閱名單 (共 {len(subs)} 筆):"]
            for s in subs[:15]:
                uid_short = s.get("user_id", "")[:10] + "..."
                lines.append(f"• {uid_short} | {s.get('status')} | 至 {str(s.get('expire_at'))[:10]}")
            send_reply(event.reply_token, [create_text_msg("\n".join(lines), quick_reply=quick_reply)])
            return

    # 5. 啟動指定魔術 (!play <trick_id> 或相容舊指令 !unlock)
    if cmd.startswith("!play ") or cmd == "!unlock":
        trick_id = "xray_card" if cmd == "!unlock" else text.split()[1].strip().lower()
        trick = TRICK_REGISTRY.get(trick_id)
        if not trick:
            send_reply(event.reply_token, [create_text_msg("❌ 找不到指定的魔術項目。", quick_reply=quick_reply)])
            return

        # 檢查訂閱權限或試玩配額
        access = SubscriptionManager.can_access_trick(user_id, trick_id)
        if not access["allowed"]:
            send_reply(event.reply_token, [create_text_msg(access["message"], quick_reply=quick_reply)])
            return

        # 生成專屬防偽啟動 Token 與魔術師獨立網址
        token = SubscriptionManager.generate_launch_token(user_id, trick_id)

        if trick_id == "xray_card":
            secs = SubscriptionManager.unlock_trick_session(user_id, "xray_card")
            hours = round(secs / 3600, 1)
            info = calculate_magic_round(0)
            launch_url = f"{BASE_URL}/tricks/xray/magic.html?mid={user_id}&uid={user_id}&token={token}"

            flex_xray = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "✅ X光透視魔術已啟動！", "weight": "bold", "size": "lg", "color": "#06c755"},
                        {"type": "text", "text": f"⏰ 本場次授權有效約 {hours} 小時（午夜自動鎖定）", "size": "xs", "color": "#888888", "margin": "sm"},
                        {"type": "separator", "margin": "md"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "margin": "md",
                            "contents": [
                                {"type": "text", "text": f"👤 第 1 位模式：{info['mode_name']}", "weight": "bold", "size": "sm", "color": "#0099ff"},
                                {"type": "text", "text": f"👉 請迫首張牌：【{info['card_name']}】", "weight": "bold", "size": "md", "color": "#e60000", "margin": "xs"},
                                {"type": "text", "text": f"📄 單車牌檔名：{info['card_filename']}", "size": "xs", "color": "#666666", "margin": "xs"}
                            ]
                        }
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
                            "action": {"type": "uri", "label": "⚡ 開啟感應相機 (X-Ray)", "uri": launch_url}
                        }
                    ]
                }
            }
            send_reply(
                event.reply_token,
                [
                    create_flex_msg("X光透視魔術已啟動", flex_xray),
                    create_text_msg(f"🔗 觀眾共用連結（請給觀眾或掃描）：\n{launch_url}", quick_reply=quick_reply)
                ]
            )
            return

        elif trick_id == "keycard_ar":
            launch_url = f"{BASE_URL}/tricks/keycard/index.html?mid={user_id}&token={token}&openExternalBrowser=1"
            flex_keycard = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "👁️ 數位透視眼 AR 已授權！", "weight": "bold", "size": "lg", "color": "#00aaff"},
                        {"type": "text", "text": "已為您的帳號簽發今日專用 AR 授權憑證。打開後畫面內建 QR Code 可直接讓觀眾手機掃描共玩！", "size": "xs", "color": "#666666", "margin": "md", "wrap": True}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#00aaff",
                            "action": {"type": "uri", "label": "👁️ 啟動數位透視眼 AR", "uri": launch_url}
                        }
                    ]
                }
            }
            send_reply(
                event.reply_token,
                [
                    create_flex_msg("數位透視眼 AR 已授權", flex_keycard),
                    create_text_msg(f"🔗 數位透視眼直連網址：\n{launch_url}", quick_reply=quick_reply)
                ]
            )
            return

        elif trick_id == "frozen_proof_ar":
            launch_url = f"{BASE_URL}/tricks/frozen/index.html?mode=master&mid={user_id}&token={token}&openExternalBrowser=1"
            flex_frozen = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🕯️ 記憶流痕 AR 已授權！", "weight": "bold", "size": "lg", "color": "#a855f7"},
                        {"type": "text", "text": "已簽發今日 Master 主控權限。進入後可生成觀眾掃描 QR Code，輕觸螢幕即可進入隱形黑屏 12 點鐘手勢秘密選牌！", "size": "xs", "color": "#666666", "margin": "md", "wrap": True}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#a855f7",
                            "action": {"type": "uri", "label": "🕯️ 啟動記憶流痕主控台", "uri": launch_url}
                        }
                    ]
                }
            }
            send_reply(
                event.reply_token,
                [
                    create_flex_msg("記憶流痕 AR 已授權", flex_frozen),
                    create_text_msg(f"🔗 記憶流痕主控台網址：\n{launch_url}", quick_reply=quick_reply)
                ]
            )
            return

        elif trick_id == "drawcards":
            launch_url = f"{BASE_URL}/tricks/drawcards/index.html?mid={user_id}&token={token}"
            flex_drawcards = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "✏️ 多人畫牌已授權！", "weight": "bold", "size": "lg", "color": "#f59e0b"},
                        {"type": "text", "text": "長按右下角隱形感應區可秘密設定首張牌，否則自動以今日日期演算法啟動。讓多位觀眾畫框後長按即可變身 3D 單車撲克！", "size": "xs", "color": "#666666", "margin": "md", "wrap": True}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#f59e0b",
                            "action": {"type": "uri", "label": "✏️ 啟動多人畫牌道具", "uri": launch_url}
                        }
                    ]
                }
            }
            send_reply(
                event.reply_token,
                [
                    create_flex_msg("多人畫牌已授權", flex_drawcards),
                    create_text_msg(f"🔗 多人畫牌直連網址：\n{launch_url}", quick_reply=quick_reply)
                ]
            )
            return

        elif trick_id == "drawacard":
            launch_url = f"{BASE_URL}/tricks/drawacard/index.html?mid={user_id}&token={token}"
            flex_drawacard = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🧙‍♂️ 畫魔術師已授權！", "weight": "bold", "size": "lg", "color": "#10b981"},
                        {"type": "text", "text": "雙擊右下角隱藏區可秘密設定撲克牌，未設定則依今日日期運算。先畫出魔術師並按 Next，再請觀眾畫框點擊即可施展 3D 翻牌預言！", "size": "xs", "color": "#666666", "margin": "md", "wrap": True}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#10b981",
                            "action": {"type": "uri", "label": "🧙‍♂️ 啟動畫魔術師道具", "uri": launch_url}
                        }
                    ]
                }
            }
            send_reply(
                event.reply_token,
                [
                    create_flex_msg("畫魔術師已授權", flex_drawacard),
                    create_text_msg(f"🔗 畫魔術師直連網址：\n{launch_url}", quick_reply=quick_reply)
                ]
            )
            return

        elif trick_id == "pickonecards":
            launch_url = f"{BASE_URL}/tricks/pickonecards/index.html?mid={user_id}&token={token}"
            flex_pickonecards = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🃏 手機迫牌(多人版)已授權！", "weight": "bold", "size": "lg", "color": "#e11d48"},
                        {"type": "text", "text": "讓觀眾掃描房號 QR Code 即時同步，第一位預設依日期運算（長按右下角可喚醒 4x13 矩陣自訂首張迫牌），多位觀眾各自停牌皆精準命中！", "size": "xs", "color": "#666666", "margin": "md", "wrap": True}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#e11d48",
                            "action": {"type": "uri", "label": "🃏 啟動手機迫牌(多人版)", "uri": launch_url}
                        }
                    ]
                }
            }
            send_reply(
                event.reply_token,
                [
                    create_flex_msg("手機迫牌(多人版)已授權", flex_pickonecards),
                    create_text_msg(f"🔗 手機迫牌(多人版)直連網址：\n{launch_url}", quick_reply=quick_reply)
                ]
            )
            return

    # 6. 重設 X 光透視輪次 (!reset)
    if cmd == "!reset":
        SubscriptionManager.reset_session_stage(user_id, "xray_card")
        info = calculate_magic_round(0)
        msg = f"🔄 您的 X光透視輪次已歸零。\n首發模式：{info['mode_name']}\n迫牌目標：【{info['card_name']}】({info['card_filename']})"
        send_reply(event.reply_token, [create_text_msg(msg, quick_reply=quick_reply)])
        return

    # 7. 相容「解鎖透視魔術」關鍵字
    if text == "解鎖透視魔術":
        # 如果沒有專屬 mid，預設檢查發送者自己的開通或導引至選單
        if not SubscriptionManager.is_session_unlocked(user_id, "xray_card") and not SubscriptionManager.is_session_unlocked(ADMIN_USER_ID, "xray_card"):
            send_reply(event.reply_token, [create_text_msg("大師目前的感知通道尚未開啟，請稍候或輸入「魔術選單」。", quick_reply=quick_reply)])
            return

        target_mid = user_id if SubscriptionManager.is_session_unlocked(user_id, "xray_card") else ADMIN_USER_ID
        token = SubscriptionManager.generate_launch_token(target_mid, "xray_card")
        launch_url = f"{BASE_URL}/tricks/xray/magic.html?mid={target_mid}&uid={user_id}&token={token}"

        flex_payload = {
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
                    {"type": "button", "style": "primary", "color": "#06c755", "action": {"type": "uri", "label": "開啟感應鏡頭", "uri": launch_url}}
                ]
            }
        }
        send_reply(event.reply_token, [create_flex_msg("開啟感應鏡頭", flex_payload)])


@app.post("/api/liff/upload")
async def liff_upload_photo(
    photo: UploadFile = File(...),
    uid: Optional[str] = Form(None),
    mid: Optional[str] = Form(None),
    token: Optional[str] = Form(None)
):
    """多租戶 X光透視魔術拍照上傳處理端點"""
    magician_id = mid or ADMIN_USER_ID

    # 1. 若帶有訂閱授權 Token，驗證魔術師的訂閱資格
    if mid and token:
        if not SubscriptionManager.verify_launch_token(mid, "xray_card", token):
            return JSONResponse(status_code=403, content={"status": "UNAUTHORIZED", "detail": "此魔術連結授權已失效或訂閱已到期"})

    # 2. 檢查該魔術師場次是否開通
    if not SubscriptionManager.is_session_unlocked(magician_id, "xray_card"):
        return JSONResponse(status_code=403, content={"status": "LOCKED", "detail": "魔術今日尚未啟動，請魔術師於選單重新啟動"})

    # 3. 檢查觀眾 (uid) 若非訂閱者/管理員，每日限試玩 2 次
    viewer_id = uid or magician_id
    access = SubscriptionManager.can_access_trick(viewer_id, "xray_card")
    if not access["allowed"]:
        return JSONResponse(status_code=403, content={"status": "LIMIT_REACHED", "detail": access.get("message", "今日體驗次數已達上限")})

    file_id = uuid.uuid4().hex
    orig_filename = f"orig_{file_id}.jpg"
    orig_path = os.path.join(XRAY_TEMP_DIR, orig_filename)

    with open(orig_path, "wb") as f:
        content = await photo.read()
        f.write(content)

    # 取得該魔術師專屬輪次
    stage = SubscriptionManager.get_session_stage(magician_id, "xray_card")
    current_round = calculate_magic_round(stage)

    corners = await detect_card_corners(orig_path)
    if not corners or len(corners) != 4:
        return JSONResponse(status_code=400, content={"status": "FAIL", "detail": "Cannot detect card corners. Please retake photo."})

    card_face_path = get_card_file_path(current_round["card_code"], base_dir=XRAY_CARDS_DIR)
    revealed_filename = f"revealed_{file_id}.jpg"
    revealed_path = os.path.join(XRAY_TEMP_DIR, revealed_filename)

    _, corners = generate_xray_card(
        original_img_path=orig_path,
        card_face_path=card_face_path,
        corners=corners,
        output_path=revealed_path,
        opacity=0.88,
        mode=current_round["mode"]
    )

    # 推進該魔術師專屬輪次 + 扣除免費體驗次數 (若有)
    SubscriptionManager.advance_session_stage(magician_id, "xray_card")
    SubscriptionManager.increment_trial_usage(viewer_id, "xray_card")
    next_round = calculate_magic_round(stage + 1)

    # 只秘密推播給「正在表演的那位魔術師 (magician_id)」!
    try:
        msg = (
            f"🔔 第 {stage + 1} 位表演完成 ({current_round['mode_name']})\n"
            f"👉 下一位模式：{next_round['mode_name']}\n"
            f"👉 請迫牌：【{next_round['card_name']}】({next_round['card_filename']})"
        )
        send_push(magician_id, [create_text_msg(msg, quick_reply=build_quick_reply(magician_id))])
    except Exception as e:
        print(f"Notify magician {magician_id} error: {e}")

    return {
        "status": "SUCCESS",
        "mode": current_round["mode"],
        "original_url": f"{BASE_URL}/tricks/xray/temp/{orig_filename}",
        "revealed_url": f"{BASE_URL}/tricks/xray/temp/{revealed_filename}",
        "corners": corners
    }
