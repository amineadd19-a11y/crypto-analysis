import hmac
import json
import math
import os
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pybit.unified_trading import HTTP

app = FastAPI(
    title="Bybit AI Trader",
    version="0.2.4",
    description="Independent analysis-only multi-timeframe scanner for USDT perpetual markets.",
)

client = HTTP(
    testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
    timeout=8,
    force_retry=False,
    max_retries=1,
    retry_delay=0,
)

def access_denial(path: str, authorization: str, require_token: bool, expected_token: str):
    if path in {"/health", "/"}:
        return None
    expected_token = expected_token.strip()
    if not require_token:
        return None
    if not expected_token:
        return JSONResponse(status_code=503, content={"detail": "Service access protection is not configured."})
    if not hmac.compare_digest(authorization, f"Bearer {expected_token}"):
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})
    return None


@app.middleware("http")
async def protect_public_endpoints(request: Request, call_next):
    require_token = os.getenv("REQUIRE_ACCESS_TOKEN", "false").lower() == "true"
    expected_token = os.getenv("AGENT_ACCESS_TOKEN", "")
    denial = access_denial(request.url.path, request.headers.get("authorization", ""), require_token, expected_token)
    if denial is not None:
        return denial
    return await call_next(request)

ALLOWED_INTERVALS = {"1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "W", "M"}


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains, losses = [], []
    for before, after in zip(values[:-1], values[1:]):
        change = after - before
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_histogram(values: list[float]) -> float:
    if len(values) < 35:
        return 0.0
    fast = ema(values, 12)
    slow = ema(values, 26)
    line = [a - b for a, b in zip(fast, slow)]
    signal = ema(line, 9)
    return line[-1] - signal[-1]


def build_signal(closes: list[float]) -> dict:
    if len(closes) < 200:
        raise HTTPException(status_code=422, detail="Not enough candles; request at least 200 for EMA200.")
    if any(not math.isfinite(value) or value <= 0 for value in closes):
        raise HTTPException(status_code=422, detail="Close prices must be positive finite numbers.")
    e20, e50, e200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    last = closes[-1]
    current_rsi = rsi(closes)
    hist = macd_histogram(closes)
    if last > e20[-1] > e50[-1] and current_rsi >= 50 and hist > 0:
        direction: Literal["LONG", "SHORT", "WAIT"] = "LONG"
        reasons = ["Close above EMA20 and EMA50", "EMA20 above EMA50", "RSI supports upward momentum", "MACD histogram positive"]
    elif last < e20[-1] < e50[-1] and current_rsi <= 50 and hist < 0:
        direction = "SHORT"
        reasons = ["Close below EMA20 and EMA50", "EMA20 below EMA50", "RSI supports downward momentum", "MACD histogram negative"]
    else:
        direction = "WAIT"
        reasons = ["Trend/momentum filters do not align; no trade signal"]
    return {"signal": direction, "last_close": last, "ema20": e20[-1], "ema50": e50[-1], "ema200": e200[-1], "rsi14": round(current_rsi, 2), "macd_histogram": hist, "reasons": reasons, "execution": "DISABLED"}


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).with_name("dashboard.html"))


@app.get("/health")
def health() -> dict:
    from app.market_data import probe_market_connectivity
    market = probe_market_connectivity(timeout=4.0)
    return {"status": "ok", "service": "bybit-ai-trader", "version": "0.2.4", "trading_enabled": False, "oauth": "pkce-s256", "market_data": market, "scanner": "mtf-smart"}


@app.get("/api/bybit/account-connection")
def bybit_account_connection() -> dict:
    api_key = os.getenv("BYBIT_API_KEY", "").strip()
    api_secret = os.getenv("BYBIT_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=503, detail="Bybit account connection is not configured. Add BYBIT_API_KEY and BYBIT_API_SECRET as server-side environment variables.")
    try:
        private_client = HTTP(testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true", api_key=api_key, api_secret=api_secret, timeout=10, force_retry=False)
        response = private_client.get_wallet_balance(accountType="UNIFIED")
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit rejected the private API connection.")
        return {"connected": True, "environment": "testnet" if os.getenv("BYBIT_TESTNET", "false").lower() == "true" else "mainnet", "account_type": "UNIFIED", "trading_enabled": False, "orders_placed": False, "message": "Private Bybit API authentication succeeded. Read-only."}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to authenticate with Bybit.")


from app.oauth_flow import OAuthExchangeRequest, OAuthStartRequest, exchange_code, start_oauth


@app.post("/api/bybit/oauth/start")
def bybit_oauth_start(body: OAuthStartRequest) -> dict:
    return start_oauth(body.environment)


@app.post("/api/bybit/oauth/exchange")
def bybit_oauth_exchange(body: OAuthExchangeRequest) -> dict:
    return exchange_code(body.code, body.code_verifier, body.environment)


from app.oauth_accounts import (
    OAuthAccountsRequest,
    OAuthSelectRequest,
    bybit_oauth_get as _bybit_oauth_get,
    list_accounts as _list_accounts,
    create_account as _create_account,
    verify_account as _verify_account,
)


@app.post("/api/bybit/oauth/accounts")
def bybit_oauth_accounts(body: OAuthAccountsRequest) -> dict:
    return _list_accounts(body)


@app.post("/api/bybit/oauth/create-account")
def bybit_oauth_create_account(body: OAuthAccountsRequest) -> dict:
    """User-initiated only. Official Bybit agent path: is_create=true."""
    return _create_account(body)


@app.post("/api/bybit/oauth/verify")
def bybit_oauth_verify(body: OAuthSelectRequest) -> dict:
    return _verify_account(body)


from app.market_routes import register_market_routes
register_market_routes(app, client, ALLOWED_INTERVALS, build_signal)


from app.mtf_routes import register_mtf_routes
register_mtf_routes(app)
