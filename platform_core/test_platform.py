import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as platform_app
from saas.subscription_manager import SubscriptionManager
from saas.menu_builder import build_magic_carousel
from config import ADMIN_USER_ID, TRICK_REGISTRY

def test_platform():
    print("=" * 60)
    print("🔍 開始驗證【奇幻數位魔術訂閱制整合平台】")
    print("=" * 60)

    print(f"1. 訂閱後端引擎: {SubscriptionManager.get_backend_type()}")
    print(f"2. 已註冊魔術清單: {list(TRICK_REGISTRY.keys())}")

    # 測試超級管理員權限
    admin_access_xray = SubscriptionManager.can_access_trick(ADMIN_USER_ID, "xray_card")
    admin_access_keycard = SubscriptionManager.can_access_trick(ADMIN_USER_ID, "keycard_ar")
    admin_access_frozen = SubscriptionManager.can_access_trick(ADMIN_USER_ID, "frozen_proof_ar")
    admin_access_draw = SubscriptionManager.can_access_trick(ADMIN_USER_ID, "drawcards")
    admin_access_drawacard = SubscriptionManager.can_access_trick(ADMIN_USER_ID, "drawacard")
    admin_access_pickonecards = SubscriptionManager.can_access_trick(ADMIN_USER_ID, "pickonecards")
    assert all([
        admin_access_xray["allowed"],
        admin_access_keycard["allowed"],
        admin_access_frozen["allowed"],
        admin_access_draw["allowed"],
        admin_access_drawacard["allowed"],
        admin_access_pickonecards["allowed"],
    ]), "超級管理員應擁有所有魔術權限"
    print(f"3. 超級管理員權限 -> XRay: {admin_access_xray['allowed']} | Keycard AR: {admin_access_keycard['allowed']} | Frozen Proof: {admin_access_frozen['allowed']} | Drawcards: {admin_access_draw['allowed']} | Drawacard: {admin_access_drawacard['allowed']} | Pickonecards: {admin_access_pickonecards['allowed']}")

    # 測試一般未訂閱用戶權限
    test_guest = "U_GUEST_TEST_999"
    guest_xray = SubscriptionManager.can_access_trick(test_guest, "xray_card")
    guest_keycard = SubscriptionManager.can_access_trick(test_guest, "keycard_ar")
    guest_frozen = SubscriptionManager.can_access_trick(test_guest, "frozen_proof_ar")
    guest_draw = SubscriptionManager.can_access_trick(test_guest, "drawcards")
    guest_drawacard = SubscriptionManager.can_access_trick(test_guest, "drawacard")
    guest_pickonecards = SubscriptionManager.can_access_trick(test_guest, "pickonecards")
    assert not guest_drawacard["allowed"] and not guest_pickonecards["allowed"], "未訂閱用戶不應存取付費道具"
    print(f"4. 未訂閱遊客權限 -> XRay (試玩): {guest_xray['allowed']} (剩 {guest_xray.get('remaining')} 次) | Keycard AR: {guest_keycard['allowed']} | Frozen: {guest_frozen['allowed']} | Drawcards: {guest_draw['allowed']} | Drawacard: {guest_drawacard['allowed']} | Pickonecards: {guest_pickonecards['allowed']}")

    # 測試管理員授與訂閱資格 30 天
    print("5. 模擬超級管理員執行 !grant 授與測試會員 30 天訂閱...")
    sub_record = SubscriptionManager.grant_subscription(test_guest, days=30)
    sub_draw = SubscriptionManager.can_access_trick(test_guest, "drawcards")
    sub_drawacard = SubscriptionManager.can_access_trick(test_guest, "drawacard")
    sub_pickonecards = SubscriptionManager.can_access_trick(test_guest, "pickonecards")
    assert sub_draw["allowed"] and sub_drawacard["allowed"] and sub_pickonecards["allowed"], "訂閱後應解鎖所有 Pro 魔術"
    print(f"   訂閱開通結果 -> 到期日: {sub_record['expire_at']} | Drawcards 解鎖: {sub_draw['allowed']} | Drawacard 解鎖: {sub_drawacard['allowed']} | Pickonecards 解鎖: {sub_pickonecards['allowed']}")

    # 測試 Token 生成與驗證
    token = SubscriptionManager.generate_launch_token(test_guest, "pickonecards")
    valid = SubscriptionManager.verify_launch_token(test_guest, "pickonecards", token)
    tampered = SubscriptionManager.verify_launch_token(test_guest, "pickonecards", "fake_token_123")
    assert valid and not tampered, "Token 驗證邏輯異常"
    print(f"6. 防偽 Token 驗證 -> 正確 Token: {valid} | 偽造 Token: {tampered}")

    # 測試選單生成
    carousel = build_magic_carousel(test_guest)
    assert len(carousel["contents"]) == len(TRICK_REGISTRY) + 1
    print(f"7. 魔術櫃滑動卡片生成 -> 卡片數量: {len(carousel['contents'])} 張 ({len(TRICK_REGISTRY)}個魔術 + 1張訂閱狀態)")

    # 測試完畢撤銷測試用戶以保持資料庫乾淨
    SubscriptionManager.revoke_subscription(test_guest)
    revoked_pickonecards = SubscriptionManager.can_access_trick(test_guest, "pickonecards")
    assert not revoked_pickonecards["allowed"], "撤銷訂閱後應收回 pickonecards 授權"
    print(f"8. 停用測試訂閱驗證 -> Pickonecards 授權已回收: {not revoked_pickonecards['allowed']}")

    # 驗證靜態路徑掛載點
    print("9. 檢查所有魔術前端檔案路徑:")
    paths = [
        ("XRay", os.path.join(platform_app.XRAY_STATIC_DIR, 'magic.html')),
        ("Keycard AR", os.path.join(platform_app.KEYCARD_DIR, 'index.html')),
        ("Frozen Proof", os.path.join(platform_app.FROZEN_DIR, 'index.html')),
        ("Drawcards", os.path.join(platform_app.DRAWCARDS_DIR, 'index.html')),
        ("Drawacard", os.path.join(platform_app.DRAWACARD_DIR, 'index.html')),
        ("Pickonecards", os.path.join(platform_app.PICKONECARDS_DIR, 'index.html')),
    ]
    for label, p in paths:
        exists = os.path.exists(p)
        assert exists, f"缺少前端檔案: {p}"
        print(f"   {label} HTML 存在: {exists}")

    print("=" * 60)
    print("✅ 全平台架構與訂閱邏輯驗證 100% 通過！")
    print("=" * 60)

if __name__ == "__main__":
    test_platform()
