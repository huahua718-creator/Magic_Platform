import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.poker_logic import calculate_magic_round, get_card_file_path, SUIT_CYCLE

def test_deck_mapping():
    print("=== 測試 52 張撲克牌與單車牌圖檔關聯 ===")
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "cards")
    missing = []
    success_count = 0

    for s in SUIT_CYCLE:
        for v in range(1, 14):
            code = f"{s}{v}"
            path = get_card_file_path(code, base_dir)
            if not os.path.exists(path):
                missing.append((code, path))
            else:
                success_count += 1

    if missing:
        print(f"❌ 有 {len(missing)} 張牌未對應到檔案:")
        for m in missing:
            print(m)
    else:
        print(f"✅ 全部 {success_count} 張撲克牌 (4花色 x 13點數) 均 100% 成功對應至單車牌圖檔！")

    print("\n=== 測試前 5 輪推算與檔案關聯 ===")
    for stage in range(5):
        info = calculate_magic_round(stage)
        exists = os.path.exists(info["card_file_path"])
        print(f"輪次 {stage}: {info['mode_name']} -> 【{info['card_name']}】({info['card_filename']}) -> 檔案存在: {exists}")

if __name__ == "__main__":
    test_deck_mapping()

