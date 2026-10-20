# Bybit AI Trader — Demo-first agent

A separate Python service for Bybit USDT perpetual market analysis, with explainable LONG / SHORT / WAIT signals and an OAuth connection flow for Bybit AI Subaccounts. **Order execution remains disabled** until a separately reviewed execution phase adds per-order confirmation and hard risk controls.

## Safety defaults

- Public market-data endpoints require no credentials.
- OAuth tokens are entered in the dashboard and kept in browser session storage only; the server does not persist them.
- OAuth account verification retrieves the selected AI subaccount's credentials server-side and never returns the secret to the browser.
- The dashboard requires an explicit AI subaccount selection; it never auto-selects or auto-creates one.
- `TRADING_ENABLED=false` by default. No order-submission, withdrawal, or transfer endpoint is implemented.
- Signals are heuristic, not financial advice, and must be backtested before use.

## Run locally

Python 3.11+:

```bash
cd bybit-agent
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `/health`, then try `/api/scan?symbol=BTCUSDT&interval=5&limit=200`.

## Environment

Copy `.env.example` to `.env` for local development if needed. Public market scanning and the dashboard's OAuth flow do not require `BYBIT_API_KEY` or `BYBIT_API_SECRET`. Never commit access tokens, API keys, or secrets.

## Deployment status

The dashboard is deployed at https://bybit-ai-agent.vercel.app from the `feat/bybit-ai-agent-demo` branch. The API is hosted on Vercel using `bybit-agent/vercel.json`. A Render deployment attempt was blocked by a billing requirement; Railway was unavailable because the connected account trial had expired.

For public hosting, protect the deployment with Vercel Authentication or enable `REQUIRE_ACCESS_TOKEN=true` and configure a strong `AGENT_ACCESS_TOKEN`. `/health` stays public for health checks. The dashboard's Bybit OAuth access token is a different credential from this optional app-access token. Keep `TRADING_ENABLED=false`: this version has no order-submission endpoints.
