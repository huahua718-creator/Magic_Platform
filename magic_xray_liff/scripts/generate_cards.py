"""
自動產生 52 張標準撲克牌圖檔至 static/cards 目錄下
檔名格式:
  c1.png ~ c13.png (梅花 1~13)
  d1.png ~ d13.png (方塊 1~13)
  s1.png ~ s13.png (黑桃 1~13)
  h1.png ~ h13.png (紅心 1~13)
"""
import os
import cv2
import numpy as np

def generate_deck():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "cards")
    os.makedirs(output_dir, exist_ok=True)

    suits = {
        "c": ("梅花", "♣", (40, 40, 40)),
        "d": ("方塊", "♦", (0, 0, 220)),
        "s": ("黑桃", "♠", (40, 40, 40)),
        "h": ("紅心", "♥", (0, 0, 220))
    }

    val_symbols = {1: "A", 11: "J", 12: "Q", 13: "K"}

    width, height = 500, 700

    print("開始生成 52 張撲克牌面資源...")
    for s_code, (s_name, s_symbol, color) in suits.items():
        for val in range(1, 14):
            display_val = val_symbols.get(val, str(val))
            card_code = f"{s_code}{val}"
            file_name = f"{card_code}.png"
            file_path = os.path.join(output_dir, file_name)

            # 建立撲克牌白底圓角卡片底圖
            img = np.ones((height, width, 3), dtype=np.uint8) * 255
            # 外框與裝飾線
            cv2.rectangle(img, (15, 15), (width - 15, height - 15), (220, 220, 220), 2)
            cv2.rectangle(img, (25, 25), (width - 25, height - 25), (240, 240, 240), 1)

            # 左上角點數與花色標記
            cv2.putText(img, display_val, (45, 95), cv2.FONT_HERSHEY_DUPLEX, 2.2, color, 4)
            cv2.putText(img, s_symbol, (45, 160), cv2.FONT_HERSHEY_DUPLEX, 1.8, color, 3)

            # 右下角顛倒點數與花色標記
            cv2.putText(img, display_val, (width - 100, height - 60), cv2.FONT_HERSHEY_DUPLEX, 2.2, color, 4)
            cv2.putText(img, s_symbol, (width - 100, height - 120), cv2.FONT_HERSHEY_DUPLEX, 1.8, color, 3)

            # 中央巨大花色與標誌
            center_text = f"{s_symbol} {display_val}"
            text_size = cv2.getTextSize(center_text, cv2.FONT_HERSHEY_DUPLEX, 2.8, 5)[0]
            cx = (width - text_size[0]) // 2
            cy = (height + text_size[1]) // 2
            cv2.putText(img, center_text, (cx, cy), cv2.FONT_HERSHEY_DUPLEX, 2.8, color, 5)

            cv2.imwrite(file_path, img)

    print(f"成功生成 52 張牌面於: {output_dir}")

if __name__ == "__main__":
    generate_deck()

