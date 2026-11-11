import redis
from datetime import datetime, timedelta
from config import REDIS_URL

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

class StateManager:
    @staticmethod
    def unlock_today() -> int:
        """解鎖當日表演，TTL 設至午夜 23:59:59"""
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        remaining_seconds = int((midnight - now).total_seconds())

        r.setex("magic:is_unlocked", remaining_seconds, "true")
        r.setex("magic:current_stage", remaining_seconds, 0)
        return remaining_seconds

    @staticmethod
    def is_unlocked() -> bool:
        return r.exists("magic:is_unlocked") == 1

    @staticmethod
    def get_current_stage() -> int:
        val = r.get("magic:current_stage")
        return int(val) if val else 0

    @staticmethod
    def get_remaining_seconds() -> int:
        ttl = r.ttl("magic:is_unlocked")
        return max(0, ttl) if ttl > 0 else 0

    @staticmethod
    def advance_stage() -> int:
        return r.incr("magic:current_stage")

    @staticmethod
    def reset_stage():
        r.set("magic:current_stage", 0)

    @staticmethod
    def get_user_quota(user_id: str, admin_user_id: str, max_limit: int = 2) -> dict:
        """
        查詢使用者當日使用次數與剩餘配額:
        管理員不受限制 (is_admin=True, remaining=999)
        非管理員當日最多體驗 max_limit (2) 次
        """
        if user_id == admin_user_id:
            return {"is_admin": True, "used": 0, "remaining": 999, "allowed": True}

        today_str = datetime.now().strftime("%Y%m%d")
        key = f"magic:user_quota:{today_str}:{user_id}"
        used = int(r.get(key) or 0)
        remaining = max(0, max_limit - used)
        return {
            "is_admin": False,
            "used": used,
            "remaining": remaining,
            "allowed": remaining > 0
        }

    @staticmethod
    def increment_user_usage(user_id: str, admin_user_id: str):
        """
        記錄使用者完成一次魔術表演 (增加使用次數並設定至午夜 TTL)
        """
        if user_id == admin_user_id:
            return

        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        key = f"magic:user_quota:{today_str}:{user_id}"

        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        ttl = int((midnight - now).total_seconds())

        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        pipe.execute()

