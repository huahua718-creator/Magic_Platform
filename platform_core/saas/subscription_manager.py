import os
import json
import hmac
import hashlib
import redis
from datetime import datetime, timedelta
from typing import Optional
from config import REDIS_URL, ADMIN_USER_ID, FIREBASE_CREDENTIALS_JSON, APP_SECRET_SALT, TRICK_REGISTRY

# 初始化 Redis
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# 嘗試初始化 Firebase Firestore (若尚未配置憑證，則優雅切換至 Redis 訂閱儲存引擎)
firestore_db = None
if FIREBASE_CREDENTIALS_JSON:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            if os.path.exists(FIREBASE_CREDENTIALS_JSON):
                cred = credentials.Certificate(FIREBASE_CREDENTIALS_JSON)
            else:
                cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
                cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        firestore_db = firestore.client()
        print("🔥 [Firebase] Firestore 訂閱資料庫連線成功！")
    except Exception as e:
        print(f"⚠️ [Firebase] 初始化失敗，已自動切換為 Redis 訂閱引擎: {e}")
        firestore_db = None
else:
    print("ℹ️ [Subscription] 尚未設定 FIREBASE_CREDENTIALS_JSON，目前使用 Redis 作為訂閱授權資料庫。")


class SubscriptionManager:
    """
    SaaS 魔術訂閱與多租戶狀態管理器
    支援 Firebase Firestore 正式引擎與 Redis 即時引擎雙模切換
    """

    @staticmethod
    def get_backend_type() -> str:
        return "Firebase Firestore" if firestore_db is not None else "Redis Engine"

    @staticmethod
    def is_super_admin(user_id: str) -> bool:
        return user_id == ADMIN_USER_ID

    @staticmethod
    def get_magician_profile(user_id: str) -> dict:
        """取得魔術師的訂閱資料與已解鎖魔術清單"""
        # 超級管理員永遠享有全權限與無限期訂閱
        if SubscriptionManager.is_super_admin(user_id):
            return {
                "user_id": user_id,
                "role": "super_admin",
                "status": "active",
                "plan": "platform_owner",
                "expire_at": "2099-12-31T23:59:59",
                "unlocked_tricks": list(TRICK_REGISTRY.keys()),
                "is_subscribed": True
            }

        data = None
        if firestore_db is not None:
            doc = firestore_db.collection("magicians").document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
        else:
            raw = r.get(f"saas:magician:{user_id}")
            if raw:
                data = json.loads(raw)

        if not data:
            return {
                "user_id": user_id,
                "role": "free_user",
                "status": "inactive",
                "plan": "free",
                "expire_at": None,
                "unlocked_tricks": [],
                "is_subscribed": False
            }

        # 檢查訂閱是否過期
        expire_str = data.get("expire_at")
        is_active = False
        if data.get("status") == "active" and expire_str:
            try:
                expire_dt = datetime.fromisoformat(expire_str.replace("Z", ""))
                if expire_dt > datetime.now():
                    is_active = True
            except Exception:
                pass

        return {
            "user_id": user_id,
            "role": "subscriber" if is_active else "expired",
            "status": "active" if is_active else "expired",
            "plan": data.get("plan", "basic"),
            "expire_at": expire_str,
            "unlocked_tricks": data.get("unlocked_tricks", []) if is_active else [],
            "is_subscribed": is_active
        }

    @staticmethod
    def grant_subscription(user_id: str, days: int = 30, plan: str = "pro", tricks: Optional[list] = None) -> dict:
        """開通或延長指定魔術師的訂閱天數"""
        if tricks is None:
            tricks = list(TRICK_REGISTRY.keys())

        profile = SubscriptionManager.get_magician_profile(user_id)
        now = datetime.now()

        # 若原本還在訂閱期內，從原本到期日往後累加天數
        base_dt = now
        if profile["is_subscribed"] and profile["expire_at"]:
            try:
                old_dt = datetime.fromisoformat(profile["expire_at"].replace("Z", ""))
                if old_dt > now:
                    base_dt = old_dt
            except Exception:
                pass

        new_expire = base_dt + timedelta(days=days)
        record = {
            "user_id": user_id,
            "status": "active",
            "plan": plan,
            "expire_at": new_expire.isoformat(timespec="seconds"),
            "unlocked_tricks": tricks,
            "updated_at": now.isoformat(timespec="seconds")
        }

        if firestore_db is not None:
            firestore_db.collection("magicians").document(user_id).set(record, merge=True)
        else:
            r.set(f"saas:magician:{user_id}", json.dumps(record))
            r.sadd("saas:all_subscribers", user_id)

        return record

    @staticmethod
    def revoke_subscription(user_id: str) -> bool:
        """停用指定用戶的訂閱"""
        if firestore_db is not None:
            firestore_db.collection("magicians").document(user_id).set(
                {"status": "revoked", "unlocked_tricks": []}, merge=True
            )
        else:
            raw = r.get(f"saas:magician:{user_id}")
            if raw:
                data = json.loads(raw)
                data["status"] = "revoked"
                data["unlocked_tricks"] = []
                r.set(f"saas:magician:{user_id}", json.dumps(data))
        return True

    @staticmethod
    def list_all_subscribers() -> list:
        """列出所有訂閱紀錄 (供超級管理員查看)"""
        results = []
        if firestore_db is not None:
            docs = firestore_db.collection("magicians").stream()
            for doc in docs:
                results.append(doc.to_dict())
        else:
            uids = r.smembers("saas:all_subscribers")
            for uid in uids:
                results.append(SubscriptionManager.get_magician_profile(uid))
        return results

    @staticmethod
    def can_access_trick(user_id: str, trick_id: str) -> dict:
        """
        檢查使用者是否能執行指定魔術:
        - 超級管理員: 無限存取
        - 訂閱會員且解鎖該魔術: 無限存取
        - 未訂閱用戶: 檢查該魔術是否允許每日免費試玩配額
        """
        trick = TRICK_REGISTRY.get(trick_id)
        if not trick:
            return {"allowed": False, "reason": "TRICK_NOT_FOUND"}

        profile = SubscriptionManager.get_magician_profile(user_id)
        if profile["role"] == "super_admin":
            return {"allowed": True, "mode": "admin", "remaining": 999}

        if profile["is_subscribed"] and trick_id in profile["unlocked_tricks"]:
            return {"allowed": True, "mode": "subscriber", "remaining": 999}

        # 未訂閱者：檢查試玩配額
        free_limit = trick.get("free_trial_daily", 0)
        if free_limit <= 0:
            return {
                "allowed": False,
                "reason": "SUBSCRIPTION_REQUIRED",
                "message": f"🔒 「{trick['name']}」為訂閱會員專屬魔術，請訂閱後即可解鎖使用！"
            }

        today_str = datetime.now().strftime("%Y%m%d")
        quota_key = f"saas:trial_quota:{today_str}:{trick_id}:{user_id}"
        used = int(r.get(quota_key) or 0)
        if used >= free_limit:
            return {
                "allowed": False,
                "reason": "TRIAL_LIMIT_REACHED",
                "message": f"🔒 今日免費試玩次數已達上限（每日限 {free_limit} 次）。訂閱正式版即可享有無限次數演出！"
            }

        return {"allowed": True, "mode": "free_trial", "remaining": free_limit - used}

    @staticmethod
    def increment_trial_usage(user_id: str, trick_id: str):
        """扣除免費體驗者一次配額"""
        profile = SubscriptionManager.get_magician_profile(user_id)
        if profile["is_subscribed"] or profile["role"] == "super_admin":
            return

        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        quota_key = f"saas:trial_quota:{today_str}:{trick_id}:{user_id}"
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        ttl = int((midnight - now).total_seconds())

        pipe = r.pipeline()
        pipe.incr(quota_key)
        pipe.expire(quota_key, ttl)
        pipe.execute()

    # ---------------- 授權 Token 簽章與多租戶表演狀態 ----------------

    @staticmethod
    def generate_launch_token(magician_id: str, trick_id: str) -> str:
        """
        產生當日有效防偽 Token，避免未授權人士直接猜測網址進入魔術道具頁面
        """
        today_str = datetime.now().strftime("%Y%m%d")
        raw_msg = f"{magician_id}:{trick_id}:{today_str}"
        sig = hmac.new(APP_SECRET_SALT.encode("utf-8"), raw_msg.encode("utf-8"), hashlib.sha256).hexdigest()
        return sig[:16]

    @staticmethod
    def verify_launch_token(magician_id: str, trick_id: str, token: str) -> bool:
        """驗證連線請求是否由合格訂閱者的官方視窗發出"""
        if not magician_id or not token:
            return False
        expected = SubscriptionManager.generate_launch_token(magician_id, trick_id)
        if not hmac.compare_digest(expected, token):
            return False
        access = SubscriptionManager.can_access_trick(magician_id, trick_id)
        return access["allowed"]

    @staticmethod
    def unlock_trick_session(magician_id: str, trick_id: str) -> int:
        """為特定魔術師開啟當日表演通道 (TTL 至午夜 23:59:59)"""
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        ttl = int((midnight - now).total_seconds())

        r.setex(f"saas:session:{magician_id}:{trick_id}:unlocked", ttl, "true")
        r.setex(f"saas:session:{magician_id}:{trick_id}:stage", ttl, 0)
        return ttl

    @staticmethod
    def is_session_unlocked(magician_id: str, trick_id: str) -> bool:
        return r.exists(f"saas:session:{magician_id}:{trick_id}:unlocked") == 1

    @staticmethod
    def get_session_stage(magician_id: str, trick_id: str) -> int:
        val = r.get(f"saas:session:{magician_id}:{trick_id}:stage")
        return int(val) if val else 0

    @staticmethod
    def advance_session_stage(magician_id: str, trick_id: str) -> int:
        return r.incr(f"saas:session:{magician_id}:{trick_id}:stage")

    @staticmethod
    def reset_session_stage(magician_id: str, trick_id: str):
        r.set(f"saas:session:{magician_id}:{trick_id}:stage", 0)
