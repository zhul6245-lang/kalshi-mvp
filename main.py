import os
import time
import logging
import requests
from typing import Optional, Dict, Any, List

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ----------------------------
# Env helpers
# ----------------------------
def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v.strip()

def get_chat_id() -> str:
    # 兼容你之前用过的两种变量名
    cid = get_env("TG_CHAT_ID") or get_env("CHAT_ID")
    if not cid:
        raise RuntimeError("缺少环境变量：TG_CHAT_ID（或 CHAT_ID）")
    return cid

def get_bot_token() -> str:
    token = get_env("TG_BOT_TOKEN")
    if not token:
        raise RuntimeError("缺少环境变量：TG_BOT_TOKEN")
    return token

def parse_bool(v: str, default: bool = True) -> bool:
    if v is None:
        return default
    s = v.strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default

def parse_int(v: Optional[str], default: int) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default


# ----------------------------
# Telegram API
# ----------------------------
class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"

    def send_message(self, text: str) -> None:
        url = f"{self.base}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if not r.ok:
                logging.warning("sendMessage failed: %s %s", r.status_code, r.text[:200])
        except Exception as e:
            logging.warning("sendMessage exception: %s", e)

    def get_updates(self, offset: Optional[int], timeout_sec: int = 10) -> List[Dict[str, Any]]:
        url = f"{self.base}/getUpdates"
        params = {"timeout": timeout_sec}
        if offset is not None:
            params["offset"] = offset
        try:
            r = requests.get(url, params=params, timeout=timeout_sec + 10)
            if not r.ok:
                logging.warning("getUpdates failed: %s %s", r.status_code, r.text[:200])
                return []
            data = r.json()
            if not data.get("ok"):
                logging.warning("getUpdates not ok: %s", str(data)[:200])
                return []
            return data.get("result", []) or []
        except Exception as e:
            logging.warning("getUpdates exception: %s", e)
            return []


# ----------------------------
# Command handling
# ----------------------------
def build_help() -> str:
    return (
        "✅ Kalshi 推送机器人已上线\n\n"
        "可用指令：\n"
        "• /start 说明\n"
        "• /status 查看当前配置/运行状态\n"
        "• /on  开启扫描（本次运行有效）\n"
        "• /off 关闭扫描（本次运行有效）\n"
        "\n"
        "说明：\n"
        "• 是否长期开启/关闭：请在 Render 环境变量里改 ENABLE_SCANNER=true/false\n"
    )

def handle_command(text: str, enabled_runtime: bool, scan_interval: int) -> (Optional[str], Optional[bool]):
    t = (text or "").strip()

    if t in ("/start", "/help"):
        return build_help(), None

    if t == "/status":
        env_enabled = parse_bool(get_env("ENABLE_SCANNER", "true"), True)
        cid = get_env("TG_CHAT_ID") or get_env("CHAT_ID")
        return (
            "📡 当前状态\n"
            f"• 运行时 enabled = {enabled_runtime}\n"
            f"• 环境变量 ENABLE_SCANNER = {env_enabled}\n"
            f"• SCAN_INTERVAL_SEC = {scan_interval}\n"
            f"• CHAT_ID = {cid}\n"
        ), None

    if t == "/on":
        return "✅ 已开启扫描（本次运行有效）", True

    if t == "/off":
        return "⏸️ 已关闭扫描（本次运行有效）", False

    return None, None


# ----------------------------
# Scanner (你后续要接 Kalshi，就改这里)
# ----------------------------
def scan_kalshi() -> List[str]:
    """
    这里先留一个“安全占位”的扫描逻辑：
    - 默认不推送任何内容（避免刷屏）
    - 你以后要接 Kalshi API，把这里改成：返回需要推送的多行文本列表即可
    """
    return []


# ----------------------------
# Main loop
# ----------------------------
def main():
    token = get_bot_token()
    chat_id = get_chat_id()

    bot = TelegramBot(token=token, chat_id=chat_id)

    # 读取配置
    env_enabled = parse_bool(get_env("ENABLE_SCANNER", "true"), True)
    scan_interval = parse_int(get_env("SCAN_INTERVAL_SEC", "60"), 60)
    scan_interval = max(10, scan_interval)  # 最小 10 秒，防止太频繁

    enabled_runtime = env_enabled

    bot.send_message("✅ Render 已启动：机器人上线了。发送 /start 查看指令。")

    offset = None
    last_scan_ts = 0.0
    last_heartbeat_ts = 0.0

    while True:
        # 1) Telegram 长轮询收消息（timeout=10，保证扫描也能定时跑）
        updates = bot.get_updates(offset=offset, timeout_sec=10)
        for upd in updates:
            offset = (upd.get("update_id", 0) or 0) + 1

            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue

            text = msg.get("text") or ""
            if not text:
                continue

            reply, new_enabled = handle_command(text, enabled_runtime, scan_interval)
            if new_enabled is not None:
                enabled_runtime = new_enabled
            if reply:
                bot.send_message(reply)

        # 2) 定时扫描（不刷屏：只有 scan_kalshi() 有内容才推送）
        now = time.time()
        if enabled_runtime and (now - last_scan_ts) >= scan_interval:
            last_scan_ts = now
            try:
                lines = scan_kalshi()
                if lines:
                    # 合并推送，避免多条消息刷屏
                    bot.send_message("📊 Kalshi 自动推送\n\n" + "\n".join(lines))
                else:
                    logging.info("scan ok (no alerts)")
            except Exception as e:
                logging.warning("scan exception: %s", e)

        # 3) 心跳：每 6 小时发一条（证明没死机）
        if (now - last_heartbeat_ts) >= 6 * 3600:
            last_heartbeat_ts = now
            logging.info("heartbeat ok")

        time.sleep(0.2)


if __name__ == "__main__":
    main()
