from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
from config import TRICK_REGISTRY
from saas.subscription_manager import SubscriptionManager


def build_quick_reply(user_id: str) -> QuickReply:
    """建立對話底部快捷文字選單，讓魔術師單手一鍵點選操作"""
    items = [
        QuickReplyItem(action=MessageAction(label="🎩 魔術選單", text="魔術選單")),
        QuickReplyItem(action=MessageAction(label="⚡ X光透視", text="!play xray_card")),
        QuickReplyItem(action=MessageAction(label="👁️ 數位透視眼AR", text="!play keycard_ar")),
        QuickReplyItem(action=MessageAction(label="🕯️ 記憶流痕AR", text="!play frozen_proof_ar")),
        QuickReplyItem(action=MessageAction(label="✏️ 多人畫牌", text="!play drawcards")),
        QuickReplyItem(action=MessageAction(label="💎 訂閱狀態", text="!sub")),
    ]

    if SubscriptionManager.is_super_admin(user_id):
        items.append(QuickReplyItem(action=MessageAction(label="👥 訂閱戶名單", text="!subscribers")))
        items.append(QuickReplyItem(action=MessageAction(label="🧪 系統測試", text="test")))

    return QuickReply(items=items)


def build_magic_carousel(user_id: str) -> dict:
    """
    動態依據 TRICK_REGISTRY 與使用者訂閱狀態，生成可左右滑動的「魔術櫃選單卡片」
    """
    profile = SubscriptionManager.get_magician_profile(user_id)
    bubbles = []

    for trick_id, trick in TRICK_REGISTRY.items():
        access = SubscriptionManager.can_access_trick(user_id, trick_id)
        is_allowed = access["allowed"]

        if access.get("mode") in ["admin", "subscriber"]:
            badge_text = "✅ 已解鎖授權 (無限制)"
            badge_color = "#06c755"
            btn_label = f"⚡ 啟動【{trick['short_name']}】"
            btn_color = trick["color"]
            btn_text_cmd = f"!play {trick_id}"
        elif access.get("mode") == "free_trial":
            badge_text = f"🎁 免費體驗中 (剩 {access['remaining']} 次)"
            badge_color = "#ff9900"
            btn_label = f"⚡ 試玩【{trick['short_name']}】"
            btn_color = "#ff9900"
            btn_text_cmd = f"!play {trick_id}"
        else:
            badge_text = "🔒 訂閱會員專屬"
            badge_color = "#ff334b"
            btn_label = "💎 查看解鎖方案"
            btn_color = "#888888"
            btn_text_cmd = "!sub"

        bubble = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#111827",
                "contents": [
                    {"type": "text", "text": badge_text, "color": badge_color, "size": "xs", "weight": "bold"},
                    {"type": "text", "text": trick["name"], "color": "#ffffff", "size": "md", "weight": "bold", "margin": "sm", "wrap": True}
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": trick["subtitle"], "size": "xs", "color": "#666666", "wrap": True}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": btn_color,
                        "action": {
                            "type": "message",
                            "label": btn_label,
                            "text": btn_text_cmd
                        }
                    }
                ]
            }
        }
        bubbles.append(bubble)

    # 最後追加一張「訂閱資訊摘要卡片」
    role_map = {
        "super_admin": "👑 平台創辦人 (全權限)",
        "subscriber": "💎 正式訂閱魔術師",
        "expired": "⚠️ 訂閱已過期",
        "free_user": "👤 免費體驗帳號"
    }
    role_label = role_map.get(profile["role"], "一般用戶")
    expire_label = profile["expire_at"][:10] if profile["expire_at"] else "無"

    summary_bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1f2937",
            "contents": [
                {"type": "text", "text": "ACCOUNT STATUS", "color": "#00f2fe", "size": "xs", "weight": "bold"},
                {"type": "text", "text": "我的訂閱方案", "color": "#ffffff", "size": "md", "weight": "bold", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": f"身分：{role_label}", "size": "xs", "color": "#333333", "wrap": True},
                {"type": "text", "text": f"到期日：{expire_label}", "size": "xs", "color": "#333333"},
                {"type": "text", "text": f"解鎖魔術數：{len(profile['unlocked_tricks'])} / {len(TRICK_REGISTRY)}", "size": "xs", "color": "#06c755", "weight": "bold"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "message",
                        "label": "📊 詳細帳號資訊",
                        "text": "!sub"
                    }
                }
            ]
        }
    }
    bubbles.append(summary_bubble)

    return {
        "type": "carousel",
        "contents": bubbles
    }
