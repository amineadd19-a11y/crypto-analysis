from __future__ import annotations
import aiohttp
from .config import SETTINGS

async def send_telegram(text: str) -> bool:
    if not SETTINGS.telegram_bot_token or not SETTINGS.telegram_chat_id:
        print("[ALERT] Telegram is not configured:\n" + text, flush=True)
        return False
    url = f"https://api.telegram.org/bot{SETTINGS.telegram_bot_token}/sendMessage"
    payload = {"chat_id": SETTINGS.telegram_chat_id, "text": text, "disable_web_page_preview": True}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=10) as r:
            ok = r.status == 200
            if not ok:
                print(f"Telegram error {r.status}: {await r.text()}", flush=True)
            return ok


def format_alert(symbol: str, signal: dict) -> str:
    d = signal["direction"]
    emoji = "🔴" if d == "SHORT" else "🟢"
    return (
        f"{emoji} MEXC REVERSAL SETUP\n\n"
        f"{symbol} — {d}\n"
        f"Score: {signal['score']}/100\n"
        f"Price: {signal['price']:.10g}\n"
        f"Entry: {signal['entry_low']:.10g} → {signal['entry_high']:.10g}\n"
        f"Invalidation: {signal['invalid']:.10g}\n"
        f"TP1: {signal['tp1']:.10g}\n"
        f"TP2: {signal['tp2']:.10g}\n"
        f"TP3: {signal['tp3']:.10g}\n\n"
        f"1m move: {signal['move1']:+.2f}%\n"
        f"5m move: {signal['move5']:+.2f}%\n"
        f"Volume: {signal['vol_ratio']:.1f}x\n"
        f"RSI: {signal['rsi']:.1f}\n\n"
        f"Why: {', '.join(signal['reasons'])}\n\n"
        f"⚠️ Signal only — no order was placed."
    )
