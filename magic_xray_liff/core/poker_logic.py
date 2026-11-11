import os
from datetime import datetime

# 花色循環: 梅花 (c) -> 方塊 (d) -> 黑桃 (s) -> 紅心 (h)
SUIT_CYCLE = ["c", "d", "s", "h"]

SUIT_NAME_MAP = {
    "c": "club",
    "d": "diamond",
    "s": "spade",
    "h": "heart"
}

RANK_NAME_MAP = {
    1: "1",
    11: "jack",
    12: "queen",
    13: "king"
}

def get_card_filename(suit: str, val: int) -> str:
    """
    將花色與點數轉換為單車牌圖檔名稱:
    例: 'c', 1 -> 'club_1.png'
        's', 11 -> 'spade_jack.png'
        'h', 12 -> 'heart_queen.png'
        'd', 13 -> 'diamond_king.png'
    """
    suit_name = SUIT_NAME_MAP.get(suit, suit)
    rank_name = RANK_NAME_MAP.get(val, str(val))
    return f"{suit_name}_{rank_name}.png"

def get_card_file_path(card_code: str, base_dir: str = "static/cards") -> str:
    """
    解析 card_code (如 'c11') 並尋找對應的實體圖檔路徑:
    優先尋找單車牌命名 (club_jack.png)，其次兼容舊版命名 (c11.png)
    """
    if len(card_code) >= 2:
        suit = card_code[0]
        try:
            val = int(card_code[1:])
            bicycle_name = get_card_filename(suit, val)
            bicycle_path = os.path.join(base_dir, bicycle_name)
            if os.path.exists(bicycle_path):
                return bicycle_path
        except ValueError:
            pass

    # 兼容舊版或其他自訂檔名
    legacy_path = os.path.join(base_dir, f"{card_code}.png")
    if os.path.exists(legacy_path):
        return legacy_path

    # 若未找到實體檔案，預設回傳單車牌名稱
    return os.path.join(base_dir, get_card_filename(card_code[0], int(card_code[1:])))

def get_base_suit(day: int) -> str:
    """第 1 張牌花色: 當日日期 mod 4"""
    r = day % 4
    if r == 1:
        return "c"  # 梅花
    elif r == 2:
        return "d"  # 方塊
    elif r == 3:
        return "h"  # 紅心
    else:
        return "s"  # 整除為黑桃

def calculate_magic_round(stage_index: int, target_date: datetime = None) -> dict:
    """
    計算當前輪次的目標牌與對應模式:
    - 偶數輪 (0, 2, 4...): XRAY (長按 X 光透視)
    - 奇數輪 (1, 3, 5...): SCRATCH (指尖刮刮樂)
    """
    if target_date is None:
        target_date = datetime.now()

    month = target_date.month
    day = target_date.day

    base_suit = get_base_suit(day)
    base_val = month

    if stage_index == 0:
        card_suit = base_suit
        card_val = base_val
    else:
        # 點數: 前一張 +5 (以 13 循環)
        card_val = ((base_val - 1 + (5 * stage_index)) % 13) + 1
        # 花色: c -> d -> s -> h 循環
        start_idx = SUIT_CYCLE.index(base_suit)
        suit_idx = (start_idx + stage_index) % len(SUIT_CYCLE)
        card_suit = SUIT_CYCLE[suit_idx]

    card_code = f"{card_suit}{card_val}"
    card_filename = get_card_filename(card_suit, card_val)
    card_file_path = get_card_file_path(card_code)
    
    val_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
    suit_map = {"c": "梅花", "d": "方塊", "s": "黑桃", "h": "紅心"}
    card_name = f"{suit_map[card_suit]} {val_map.get(card_val, str(card_val))}"

    # 模式交替: 偶數為 XRAY，奇數為 SCRATCH
    mode = "XRAY" if stage_index % 2 == 0 else "SCRATCH"
    mode_name = "【X光長按透視】" if mode == "XRAY" else "【指尖刮刮樂】"

    return {
        "stage": stage_index,
        "card_code": card_code,
        "card_filename": card_filename,
        "card_file_path": card_file_path,
        "card_name": card_name,
        "mode": mode,
        "mode_name": mode_name
    }

