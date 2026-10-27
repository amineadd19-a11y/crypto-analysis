# Bybit AI Trader — guarded autonomous execution

FastAPI service for Bybit USDT perpetual multi-timeframe analysis, OAuth AI-subaccount connection, and a fail-closed live execution API. **Live trading remains OFF by default.** A scheduler must call the auto-cycle endpoint; Vercel request handlers do not provide an always-running background loop.

## Safety defaults

- `LIVE_TRADING_ENABLED=false` by default; live orders are rejected unless explicitly armed.
- `BYBIT_API_KEY` / `BYBIT_API_SECRET` must be dedicated AI-subaccount credentials configured server-side. Credentials are never accepted in order request bodies or returned to the browser.
- Withdrawals and transfers are not implemented.
- A separate `LIVE_TRADING_CONFIRMATION` secret is required in the `X-Live-Trade-Confirmation` request header.
- Mainnet additionally requires `LIVE_MAINNET_ACK=I_UNDERSTAND_REAL_FUNDS`. Prefer testing on TESTNET first.
- Only one open position per symbol is allowed; market entry requests include exchange-side stop loss and take profit.
- Order size is limited to at most 0.5% of equity at stop distance and no more than 100% equity notional. `MAX_DAILY_LOSS_USDT` defaults to 5 USDT. Incomplete daily PnL history causes execution to fail closed.
- Auto-cycle uses only Bybit-native market data. OKX fallback data is never allowed to trigger a Bybit live order.
- Auto-cycle requires the scanner's strongest non-countertrend signal, medium-high confidence, valid levels, and >=3x relative volume on 1m or 5m.
- `/api/trading/status` exposes non-secret configuration status. `/api/trading/execute` accepts a strictly validated one-off order. `/api/trading/auto-cycle` performs one scan-and-trade cycle and should only be invoked by a secured scheduler.
- Protect all endpoints with Vercel Authentication or `REQUIRE_ACCESS_TOKEN=true` plus a strong `AGENT_ACCESS_TOKEN`. Do not expose the auto-cycle route publicly.
- This software does not guarantee profit. Market orders may slip; attached protective orders must be checked on the exchange after fills. Backtest and testnet-test before mainnet.

## OAuth

1. On the dashboard, choose MAINNET or TESTNET and click **Start Bybit authorization**.
2. Authorize via the official PKCE flow, exchange the code if needed, then load AI subaccounts.
3. Select and verify the intended AI subaccount explicitly.

OAuth verification in the current dashboard is read-only and does not persist the returned API credentials. Configure the selected AI subaccount's trading-enabled API key and secret only as Vercel server-side environment variables if using live execution. Never use withdrawal permissions.

## Run locally

Python 3.11+:

```bash
cd bybit-agent
python -m venv .venv
# activate the environment
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Required deployment settings

Start with these safe settings:
- `LIVE_TRADING_ENABLED=false`
- `BYBIT_TESTNET=true`
- `REQUIRE_ACCESS_TOKEN=true`
- `AGENT_ACCESS_TOKEN=<long random secret>`
- `LIVE_TRADING_CONFIRMATION=<different long random secret>`
- `MAX_DAILY_LOSS_USDT=5`
- `MAX_RISK_PER_TRADE_PCT=0.5`

Only after end-to-end testnet verification, a human operator can explicitly configure mainnet credentials, set `BYBIT_TESTNET=false`, set `LIVE_MAINNET_ACK=I_UNDERSTAND_REAL_FUNDS`, and set `LIVE_TRADING_ENABLED=true`. This code does not change those settings automatically.

## Monitoring / deployment

The API is hosted on Vercel using `bybit-agent/vercel.json`. Vercel functions are request-driven, not an always-on process. Configure an external scheduler to call `POST /api/trading/auto-cycle` at the desired cadence with the application access token and separate live-trading confirmation header. Start with a slow cadence on testnet; do not run a public unauthenticated scheduler.
