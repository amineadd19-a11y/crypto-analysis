# MEXC Futures Reversal Monitor

External, paper-only market monitor for MEXC USDT perpetuals. It watches the public Futures WebSocket ticker stream, detects abnormal 1m/5m moves, validates the setup with MEXC candlesticks, and sends Telegram alerts. It never places orders.

## What it detects
- Sharp 1m / 5m extensions (default: +3% / +7% for SHORT, -3% / -7% for LONG)
- Relative volume spike versus recent 1m candles
- EMA20 extension
- VWAP distance
- Rejection wick / candle structure
- RSI and momentum weakening
- 15m/1h trend context
- Cooldown + duplicate suppression

## Run
```bash
cd mexc-reversal-monitor
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app
```

Docker:
```bash
docker build -t mexc-reversal-monitor .
docker run --env-file .env mexc-reversal-monitor
```

No MEXC API key is required: market data is public. Telegram credentials are the only required secrets.

## Important
Alerts are signals, not guaranteed trades. The service is intentionally read-only and does not contain order-placement code.

MEXC Futures public WS: `wss://contract.mexc.com/edge`. K-line and ticker formats follow the public contract API documentation.
