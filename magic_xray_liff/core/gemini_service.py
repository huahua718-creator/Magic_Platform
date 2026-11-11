import os
import json
import re
import cv2
import numpy as np
from PIL import Image
from config import GEMINI_API_KEY

def order_corners(pts: np.ndarray) -> list[list[float]]:
    """
    將四個角點依照 [左上, 右上, 右下, 左下] 順序排列
    """
    pts = np.array(pts, dtype=np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)

    # 左上角的 x + y 最小，右下角的 x + y 最大
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # 右上角的 y - x 最小 (或 x - y 最大)
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect.tolist()

def opencv_detect_fallback(image_path: str) -> list[list[float]] | None:
    """
    使用 OpenCV 邊緣與輪廓偵測作為四角辨識的備援/離線方案
    """
    image = cv2.imread(image_path)
    if image is None:
        return None

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) == 4 and cv2.contourArea(cnt) > (w * h * 0.05):
            pts = approx.reshape(4, 2)
            return order_corners(pts)

    # 若輪廓未明確檢測到，給出畫面中央約 60% 撲克牌比例區域作為防呆保護
    margin_w = w * 0.2
    margin_h = h * 0.15
    fallback_box = [
        [margin_w, margin_h],
        [w - margin_w, margin_h],
        [w - margin_w, h - margin_h],
        [margin_w, h - margin_h]
    ]
    return fallback_box

async def detect_card_corners(image_path: str) -> list[list[float]] | None:
    """
    使用 Gemini API 辨識照片中撲克牌背的四個角落座標。
    若無配置 API Key 或連線異常，自動切換至 OpenCV 影像分析備援機制。
    """
    if not GEMINI_API_KEY:
        return opencv_detect_fallback(image_path)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        # 讀取圖片寬高
        with Image.open(image_path) as img:
            img_w, img_h = img.size

        prompt = (
            "Detect the four corners of the playing card in this image. "
            "Return ONLY a JSON array with four [x, y] coordinates in pixel values, "
            "ordered as [top_left, top_right, bottom_right, bottom_left]. "
            "Example format: [[120, 150], [450, 160], [430, 680], [100, 670]]. "
            f"Image dimensions are width: {img_w}, height: {img_h}."
        )

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ]
        )

        text = response.text or ""
        # 尋找 JSON 陣列
        match = re.search(r"\[\s*\[\s*\d+.*\]\s*\]", text, re.DOTALL)
        if match:
            corners = json.loads(match.group(0))
            if len(corners) == 4:
                return order_corners(np.array(corners, dtype=np.float32))

    except Exception as e:
        print(f"[Gemini Vision] 呼叫異常或未配置，啟用 OpenCV 備援: {e}")

    return opencv_detect_fallback(image_path)

