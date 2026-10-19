# Bybit AI Trader — Demo-first agent

A separate Python service for CryptoVision that reads Bybit linear USDT perpetual market data and generates explainable LONG / SHORT / WAIT signals. This first phase is **analysis-only**: it does not submit orders, and live trading is not implemented.

## Safety defaults

- Public market-data endpoints only; API keys are not needed for scanning.
- `TRADING_ENABLED=false` by default.
- No withdrawals, transfers, or account-management endpoints.
- Signals are not financial advice and must be tested before use.
- The next phase should add Bybit Demo Trading order execution with hard risk limits, after the scanner has been validated.

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

Copy `.env.example` to `.env` if needed. The market scanner uses public endpoints and needs no credentials. Never commit API keys or secrets.

## Deployment status

This agent is currently a GitHub feature branch, not a publicly hosted service. The included Dockerfile is configured for a container host that supports a repository subdirectory build context. A Render deployment attempt was blocked because the connected Render account requires billing information; no service was created. Railway is also unavailable in the connected account because its trial has expired.

For public hosting, set `REQUIRE_ACCESS_TOKEN=true` and set `AGENT_ACCESS_TOKEN` to a long random secret in the host's environment settings. Requests to `/`, `/api/*`, and documentation endpoints must send `Authorization: Bearer <AGENT_ACCESS_TOKEN>`. `/health` stays public for the host's health check. The service returns `503` if token protection is required but no token is configured. Never put the token in the browser code or commit it to GitHub. This bearer token is a basic access gate, not a replacement for HTTPS, request throttling, or proper user accounts.\n\nKeep `TRADING_ENABLED=false`: the current service has no order-submission endpoints and is analysis-only. Do not add exchange API credentials until a separately reviewed demo-execution phase is implemented.
