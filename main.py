import os
import time
import requests

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

def tg_send(text: str) -> None:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        raise RuntimeError("Missing TG_BOT_TOKEN or TG_CHAT_ID env vars")
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

def main():
    tg_send("✅ *Kalshi MVP* 已启动（Render 在线）\n下一步：接入 Kalshi 扫描极端价 ≤ 0.08")
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
