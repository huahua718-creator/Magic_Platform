import os
import gc
import cv2
import numpy as np

def create_fallback_card(card_code: str, width: int = 500, height: int = 700) -> np.ndarray:
    """
    若缺少實體牌面圖檔時，自動生成高解析度替代撲克牌面
    """
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (10, 10), (width - 10, height - 10), (200, 200, 200), 2)
    
    suit = card_code[0].lower() if len(card_code) > 0 else 's'
    val = card_code[1:] if len(card_code) > 1 else 'A'
    
    val_map = {"1": "A", "11": "J", "12": "Q", "13": "K"}
    display_val = val_map.get(val, val)
    
    suit_symbols = {"c": "C", "d": "D", "s": "S", "h": "H"}
    suit_char = suit_symbols.get(suit, suit)
    color = (0, 0, 220) if suit in ["d", "h"] else (20, 20, 20)

    # 繪製字樣
    cv2.putText(img, display_val, (40, 90), cv2.FONT_HERSHEY_DUPLEX, 2.2, color, 4)
    cv2.putText(img, suit_char, (40, 160), cv2.FONT_HERSHEY_DUPLEX, 1.8, color, 3)

    cv2.putText(img, f"{suit_char} {display_val}", (width // 2 - 120, height // 2 + 30),
                cv2.FONT_HERSHEY_DUPLEX, 2.8, color, 5)

    return img

def generate_xray_card(
    original_img_path: str,
    card_face_path: str,
    corners: list,
    output_path: str,
    opacity: float = 0.88,
    max_dim: int = 1200,
    mode: str = "XRAY"
) -> tuple[str, list]:
    """
    OpenCV 雙模式透視處理 (含極致記憶體控管):
    - mode == "XRAY": 將牌面水平鏡像後，執行「正片疊底 (Multiply Blending)」，保留牌背紋理並透出底層點數。
    - mode == "SCRATCH": 不鏡像、不執行正片疊底，直接將乾淨清晰的「正面牌面」完全覆蓋替換掉牌背（刮除牌背直接變成正面牌！），並融合環境明暗與微羽化邊緣。
    """
    orig_img = cv2.imread(original_img_path)
    if orig_img is None:
        raise ValueError(f"無法載入原圖: {original_img_path}")

    h_orig, w_orig = orig_img.shape[:2]

    # 後端安全防線: 限制最大尺寸
    if max(h_orig, w_orig) > max_dim:
        scale = max_dim / float(max(h_orig, w_orig))
        new_w = int(w_orig * scale)
        new_h = int(h_orig * scale)
        orig_img = cv2.resize(orig_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        cv2.imwrite(original_img_path, orig_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        corners = [[round(p[0] * scale, 1), round(p[1] * scale, 1)] for p in corners]
        h_orig, w_orig = new_h, new_w

    # 讀取牌面圖檔
    if os.path.exists(card_face_path):
        card_face = cv2.imread(card_face_path)
    else:
        code = os.path.splitext(os.path.basename(card_face_path))[0]
        card_face = create_fallback_card(code)

    # 依據模式決定是否水平鏡像: XRAY 需要鏡像透視感；SCRATCH 為刮掉牌背變成正面牌，不鏡像！
    if mode == "XRAY":
        face_to_warp = cv2.flip(card_face, 1)
    else:
        face_to_warp = card_face

    h_card, w_card = face_to_warp.shape[:2]

    src_pts = np.array([
        [0, 0],
        [w_card - 1, 0],
        [w_card - 1, h_card - 1],
        [0, h_card - 1]
    ], dtype=np.float32)

    dst_pts = np.array(corners, dtype=np.float32)

    # 計算透視變換矩陣並映射至原圖空間
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped_card = cv2.warpPerspective(
        face_to_warp,
        matrix,
        (w_orig, h_orig),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    # 建立撲克牌遮罩 (多邊形區域)
    mask = np.zeros((h_orig, w_orig), dtype=np.uint8)
    cv2.fillPoly(mask, [dst_pts.astype(np.int32)], 255)

    orig_float = orig_img.astype(np.float32)
    warped_float = warped_card.astype(np.float32)

    if mode == "XRAY":
        # 【X 光模式】：正片疊底 (Multiply Blending)，保留牌背紋理並穿透顯影
        mask_3c = cv2.merge([mask, mask, mask]) / 255.0
        multiply_blend = (orig_float * warped_float) / 255.0
        xray_tint = np.array([1.08, 1.05, 0.95], dtype=np.float32)
        multiply_blend = np.clip(multiply_blend * xray_tint, 0, 255)
        blended_card = orig_float * (1.0 - opacity) + multiply_blend * opacity
        final_img = orig_float * (1.0 - mask_3c) + blended_card * mask_3c
        del multiply_blend, blended_card
    else:
        # 【刮刮樂模式】：牌背完全消失變成乾淨牌面！
        # 1. 邊緣微柔化 (羽化 3x3) 讓牌邊與背景更融合
        soft_mask = cv2.GaussianBlur(mask, (5, 5), 0)
        mask_3c = cv2.merge([soft_mask, soft_mask, soft_mask]) / 255.0

        # 2. 自動適應桌面照片環境光影亮度 (使白底牌面自然融入環境，不會過度死白)
        mean_luma = np.mean(orig_img) / 255.0
        ambient_scale = np.clip(0.78 + (mean_luma * 0.25), 0.78, 0.98)
        adjusted_face = warped_float * ambient_scale

        # 3. 100% 替換掉原本的牌背，徹底覆蓋不留牌背花紋！
        final_img = orig_float * (1.0 - mask_3c) + adjusted_face * mask_3c
        del soft_mask, adjusted_face

    final_img = np.clip(final_img, 0, 255).astype(np.uint8)

    # 輸出儲存為壓縮 JPEG
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, final_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # 即時記憶體手動回收
    del orig_img, orig_float, warped_card, warped_float, final_img, mask, mask_3c
    gc.collect()

    return output_path, corners

