from __future__ import annotations
import asyncio, time
from .config import SETTINGS
from .mexc import MEXCClient
from .indicators import setup
from .notifier import send_telegram, format_alert

class Scanner:
    def __init__(self):
        self.mexc = MEXCClient(SETTINGS.symbols)
        self.last_alert: dict[tuple[str,str], float] = {}
        self.last_candle: dict[tuple[str,str], int] = {}
        self.sem = asyncio.Semaphore(8)

    async def evaluate(self, symbol: str, move1: float, move5: float):
        # Candidate gate keeps REST traffic low while the ticker WS watches the full market.
        short_candidate = SETTINGS.enable_short and (move1 >= SETTINGS.move_1m_pct or move5 >= SETTINGS.move_5m_pct)
        long_candidate = SETTINGS.enable_long and (move1 <= -SETTINGS.move_1m_pct or move5 <= -SETTINGS.move_5m_pct)
        if not (short_candidate or long_candidate):
            return
        async with self.sem:
            try:
                candles = await self.mexc.klines(symbol, "Min1", 120)
                if not candles:
                    return
                for direction, enabled in (("SHORT", short_candidate), ("LONG", long_candidate)):
                    if not enabled:
                        continue
                    signal = setup(__import__('pandas').DataFrame(candles), direction, SETTINGS.min_score)
                    if not signal:
                        continue
                    key = (symbol, direction)
                    now = time.time()
                    candle_id = candles[-1]["ts"]
                    if now - self.last_alert.get(key, 0) < SETTINGS.cooldown_minutes * 60:
                        continue
                    if SETTINGS.alert_once_per_candle and self.last_candle.get(key) == candle_id:
                        continue
                    self.last_alert[key] = now
                    self.last_candle[key] = candle_id
                    text = format_alert(symbol, signal)
                    await send_telegram(text)
            except Exception as exc:
                print(f"Evaluation error {symbol}: {exc}", flush=True)

    async def run(self):
        print("MEXC Reversal Monitor started", flush=True)
        print(f"Symbols: {'ALL USDT perpetuals' if not SETTINGS.symbols else ', '.join(SETTINGS.symbols)}", flush=True)
        print(f"Thresholds: 1m={SETTINGS.move_1m_pct}% 5m={SETTINGS.move_5m_pct}% volume={SETTINGS.volume_ratio}x score>={SETTINGS.min_score}", flush=True)
        await self.mexc.stream(self.evaluate)

if __name__ == "__main__":
    asyncio.run(Scanner().run())
