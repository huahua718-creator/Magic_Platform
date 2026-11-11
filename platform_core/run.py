import uvicorn
import os
import sys

# 確保能導入 platform_core 模組
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    is_prod = os.getenv("RENDER") is not None or os.getenv("ENVIRONMENT") == "production"
    print(f"啟動【奇幻數位魔術訂閱平台】服務於 port {port} (Production: {is_prod})...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=not is_prod)
