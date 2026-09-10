from __future__ import annotations
import asyncio, json, time
from collections import defaultdict, deque
from dataclasses import dataclass
import aiohttp
import websockets

REST = "https://contract.mexc.com/api/v1/contract"
WS = "wss://contract.mexc.com/edge"

@dataclass
class Tick:
    ts: float
    price: float

class MEXCClient:
    def __init__(self, symbols: tuple[str, ...] = ()):
        self.symbols = set(symbols)
        self.history: dict[str, deque[Tick]] = defaultdict(lambda: deque(maxlen=600))
        self.last_ticker: dict[str, dict] = {}

    async def klines(self, symbol: str, interval: str, limit: int = 120) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{REST}/kline/{symbol}", params={"interval": interval}, timeout=10) as r:
                r.raise_for_status()
                payload = await r.json()
        d = payload.get("data") or {}
        rows = zip(d.get("time", []), d.get("open", []), d.get("high", []), d.get("low", []), d.get("close", []), d.get("vol", []))
        out = [{"ts": int(t), "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v)} for t,o,h,l,c,v in rows]
        return out[-limit:]

    async def candidate(self, symbol: str) -> tuple[float, float] | None:
        h = self.history.get(symbol)
        if not h or len(h) < 5:
            return None
        now = h[-1]
        p1 = next((x.price for x in reversed(h) if now.ts - x.ts >= 60), None)
        p5 = next((x.price for x in reversed(h) if now.ts - x.ts >= 300), None)
        if not p1 or not p5:
            return None
        return ((now.price / p1 - 1) * 100, (now.price / p5 - 1) * 100)

    async def stream(self, on_candidate):
        backoff = 1
        while True:
            try:
                async with websockets.connect(WS, ping_interval=20, ping_timeout=10, max_size=4_000_000) as ws:
                    await ws.send(json.dumps({"method": "sub.tickers", "param": {}}))
                    backoff = 1
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("channel") != "push.tickers":
                            continue
                        for t in msg.get("data", []):
                            symbol = str(t.get("symbol", ""))
                            if not symbol.endswith("_USDT"):
                                continue
                            if self.symbols and symbol not in self.symbols:
                                continue
                            price = float(t.get("lastPrice") or 0)
                            if price <= 0:
                                continue
                            ts = time.time()
                            self.history[symbol].append(Tick(ts, price))
                            self.last_ticker[symbol] = t
                            moves = await self.candidate(symbol)
                            if moves:
                                await on_candidate(symbol, moves[0], moves[1], t)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"MEXC WS error: {exc}; reconnecting in {backoff}s", flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
