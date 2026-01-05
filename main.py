import os
import json
import time
import random
import logging
from typing import Any, Dict, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()  # 只允许这个 chat_id 控制机器人

# 扫描器开关：先把“按钮系统”跑通，默认不扫 Kalshi（避免429）
ENABLE_SCANNER = os.getenv("ENABLE_SCANNER", "0").strip()  # 0/1
SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "45").strip())

# Render Disk（推荐挂载到 /var/data），没有也能跑（会丢状态）
DATA_DIR = os.getenv("DATA_DIR", "/var/data").strip()
STATE_PATH = os.path.join(DATA_DIR, "state.json")

# —— 你以后接 Kalshi 再用 —— #
KALSHI_API_BASE = os.getenv("KALSHI_API_BASE", "https://trading-api.kalshi.com").strip()


def ensure_ready():
    if not TG_BOT_TOKEN:
        raise RuntimeError("Missing env var: TG_BOT_TOKEN")
    if not TG_CHAT_ID:
        raise RuntimeError("Missing env var: TG_CHAT_ID")

    # 确保 DATA_DIR 存在（有些环境没有 /var/data）
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        # 失败就退回当前目录
        global STATE_PATH
        STATE_PATH = "state.json"
        logging.warning("DATA_DIR not writable; fallback STATE_PATH=./state.json")


def load_state() -> Dict[str, Any]:
    default = {
        "auto_enabled": False,      # False=半自动；True=全自动
        "trading_paused": False,    # True=紧急暂停（不下单/不提醒）
        "last_signal_hash": None,   # 防重复推送用
        "updated_at": int(time.time()),
    }
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 合并默认字段
        for k, v in default.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return default


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = int(time.time())
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"save_state failed: {e}")


def tg_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def build_keyboard(state: Dict[str, Any]) -> Dict[str, Any]:
    auto_txt = "🟢 全自动：ON" if state["auto_enabled"] else "🟡 半自动：OFF"
    pause_txt = "⛔ 暂停交易" if not state["trading_paused"] else "▶️ 继续交易"

    return {
        "inline_keyboard": [
            [{"text": auto_txt, "callback_data": "toggle_auto"}],
            [{"text": pause_txt, "callback_data": "toggle_pause"}],
            [{"text": "📌 状态", "callback_data": "status"}],
        ]
    }


def send_panel(chat_id: str, state: Dict[str, Any], text: str) -> None:
    tg_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": build_keyboard(state),
        },
    )


def answer_callback(callback_id: str, text: str = "") -> None:
    tg_api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})


def only_owner(chat_id: str) -> bool:
    return str(chat_id).strip() == TG_CHAT_ID


def short_status(state: Dict[str, Any]) -> str:
    auto_line = "🟢 当前模式：全自动" if state["auto_enabled"] else "🟡 当前模式：半自动（需你确认）"
    pause_line = "⛔ 交易状态：已暂停" if state["trading_paused"] else "✅ 交易状态：运行中"
    return f"{auto_line}\n{pause_line}\n\n（你随时点按钮切换）"


# =======================
# 下面是 “扫描器占位逻辑”
# 先把按钮系统跑通，后续我们再把 Kalshi 扫描逻辑接进来
# =======================

def fake_detect_signal() -> Optional[Dict[str, Any]]:
    """
    占位：先不请求 Kalshi。
    你想测试机器人是否能推送，可以把下面的 return 打开。
    """
    return None

    # 测试用（需要时取消注释）：
    # return {
    #     "type": "BUY",
    #     "market": "TEST-MARKET",
    #     "price": 0.05,
    #     "reason": "测试信号：满足条件",
    # }


def signal_hash(sig: Dict[str, Any]) -> str:
    # 用最关键字段做去重
    return f"{sig.get('type')}|{sig.get('market')}|{sig.get('price')}"


def handle_signal(state: Dict[str, Any], sig: Dict[str, Any]) -> None:
    """
    只在 BUY/SELL 或 待确认时推送（不刷屏）
    """
    if state["trading_paused"]:
        return

    h = signal_hash(sig)
    if state.get("last_signal_hash") == h:
        return  # 防重复刷同一条

    state["last_signal_hash"] = h
    save_state(state)

    typ = sig.get("type", "SIGNAL")
    market = sig.get("market", "")
    price = sig.get("price", "")
    reason = sig.get("reason", "")

    if state["auto_enabled"]:
        # 全自动：这里未来会接“模拟下单/卖出”
        text = f"🚨【{typ}｜全自动执行】\n市场：{market}\n价格：{price}\n原因：{reason}\n\n（目前是模拟盘框架：下一步接 Kalshi paper 下单）"
        send_panel(TG_CHAT_ID, state, text)
    else:
        # 半自动：提醒 + 你确认（下一步我们会加“确认下单”的按钮）
        text = f"🔔【{typ}｜半自动提醒】\n市场：{market}\n价格：{price}\n原因：{reason}\n\n你现在是半自动：需要你确认后才会执行。"
        send_panel(TG_CHAT_ID, state, text)


# =======================
# Telegram 轮询主循环
# =======================

def process_update(state: Dict[str, Any], upd: Dict[str, Any]) -> None:
    # 1) 处理按钮回调
    if "callback_query" in upd:
        cq = upd["callback_query"]
        cb_id = cq.get("id")
        data = cq.get("data", "")
        msg = cq.get("message", {})
        chat_id = msg.get("chat", {}).get("id")

        # 只允许你本人控制
        if not only_owner(chat_id):
            if cb_id:
                answer_callback(cb_id, "无权限")
            return

        if data == "toggle_auto":
            state["auto_enabled"] = not state["auto_enabled"]
            save_state(state)
            if cb_id:
                answer_callback(cb_id, "已切换")
            send_panel(str(chat_id), state, short_status(state))
            return

        if data == "toggle_pause":
            state["trading_paused"] = not state["trading_paused"]
            save_state(state)
            if cb_id:
                answer_callback(cb_id, "已更新")
            send_panel(str(chat_id), state, short_status(state))
            return

        if data == "status":
            if cb_id:
                answer_callback(cb_id, "状态")
            send_panel(str(chat_id), state, short_status(state))
            return

        if cb_id:
            answer_callback(cb_id, "未知操作")
        return

    # 2) 处理文本消息（/start 等）
    if "message" in upd:
        msg = upd["message"]
        chat_id = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip()

        if not only_owner(chat_id):
            return

        if text in ("/start", "/panel", "/status"):
            send_panel(str(chat_id), state, "✅ 控制面板已打开\n" + short_status(state))
            return


def tg_get_updates(offset: int) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates"
    params = {
        "timeout": 30,   # long polling
        "offset": offset,
        "allowed_updates": json.dumps(["message", "callback_query"]),
    }
    r = requests.get(url, params=params, timeout=35)
    r.raise_for_status()
    return r.json()


def main():
    ensure_ready()
    state = load_state()

    # 启动时发一次面板（不刷屏）
    try:
        send_panel(TG_CHAT_ID, state, "🟢 机器人已启动\n" + short_status(state))
    except Exception as e:
        logging.warning(f"Telegram start message failed: {e}")

    offset = 0
    backoff = 1

    last_scan_ts = 0

    while True:
        # —— 1) Telegram 轮询 —— #
        try:
            data = tg_get_updates(offset)
            if not data.get("ok"):
                raise RuntimeError(f"getUpdates not ok: {data}")

            for upd in data.get("result", []):
                offset = max(offset, upd["update_id"] + 1)
                process_update(state, upd)

            backoff = 1  # 成功就复位
        except Exception as e:
            logging.warning(f"Telegram polling error: {e}")
            time.sleep(min(30, backoff))
            backoff = min(30, backoff * 2)

        # —— 2) 扫描器（默认关闭，避免429）—— #
        now = time.time()
        if ENABLE_SCANNER == "1" and now - last_scan_ts >= SCAN_INTERVAL_SEC:
            last_scan_ts = now
            try:
                sig = fake_detect_signal()
                if sig:
                    handle_signal(state, sig)
            except Exception as e:
                logging.warning(f"Scanner error: {e}")

        # 小睡，避免 CPU 空转
        time.sleep(0.2)


if __name__ == "__main__":
    main()
