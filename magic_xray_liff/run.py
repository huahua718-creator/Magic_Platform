import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    is_prod = os.getenv("RENDER") is not None or os.getenv("ENVIRONMENT") == "production"
    print(f"啟動透視魔術後端服務於 port {port} (Production: {is_prod})...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=not is_prod)

