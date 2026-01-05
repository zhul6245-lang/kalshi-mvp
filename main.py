import os
import time
import requests

# =========================
# Telegram 环境变量（唯一标准）
# =========================
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

# =========================
# Telegram 发送函数
# =========================
def tg_send(text: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("❌ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过发送")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print("✅ Telegram 消息已发送")
    except Exception as e:
        print(f"❌ Telegram 发送失败: {e}")

# =========================
# 示例：交易触发函数（占位）
# 以后真正交易条件只在这里调用 tg_send
# =========================
def on_trade_trigger(
    symbol: str,
    side: str,
    price: float,
    mode: str
):
    """
    只有【真正满足买 / 卖条件】时才调用这个函数
    """
    msg = (
        f"📊 *Kalshi 交易触发*\n\n"
        f"• 合约: `{symbol}`\n"
        f"• 方向: *{side}*\n"
        f"• 价格: `{price}`\n"
        f"• 模式: `{mode}`\n\n"
        f"⚠️ 请确认是否执行"
    )
    tg_send(msg)

# =========================
# 主循环（现在不主动发任何消息）
# =========================
def main():
    print("🚀 Kalshi Bot 启动成功（Render 在线）")
    print("ℹ️ 当前为静默模式：仅在交易触发时推送")

    while True:
        # 这里以后接 Kalshi API / 扎针 / 波段逻辑
        # 现在什么都不做，防止刷屏
        time.sleep(60)

if __name__ == "__main__":
    main()
