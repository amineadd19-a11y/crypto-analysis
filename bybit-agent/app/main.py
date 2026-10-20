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
    version="0.1.0",
    description="Independent analysis-only scanner for Bybit USDT perpetual markets.",
)

# Public market data only. Trading routes are intentionally not implemented.
client = HTTP(
    testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
    timeout=10,
    force_retry=True,
    max_retries=2,
    retry_delay=1,
)

def access_denial(path: str, authorization: str, require_token: bool, expected_token: str):
    """Return an HTTP denial response when a protected request is unauthorized."""
    if path in {"/health", "/"}:
        return None
    expected_token = expected_token.strip()
    if require_token and not expected_token:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service access protection is not configured."},
        )
    if expected_token and not hmac.compare_digest(authorization, f"Bearer {expected_token}"):
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})
    return None


# Public deployments can require a bearer token. Keep local development convenient,
# but configure REQUIRE_ACCESS_TOKEN=true on any public host.
@app.middleware("http")
async def protect_public_endpoints(request: Request, call_next):
    require_token = os.getenv("REQUIRE_ACCESS_TOKEN", "false").lower() == "true"
    expected_token = os.getenv("AGENT_ACCESS_TOKEN", "")
    denial = access_denial(
        request.url.path,
        request.headers.get("authorization", ""),
        require_token,
        expected_token,
    )
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
    reasons: list[str] = []

    # Conservative trend-following filters; this is a heuristic, not a profit guarantee.
    if last > e20[-1] > e50[-1] and current_rsi >= 50 and hist > 0:
        direction: Literal["LONG", "SHORT", "WAIT"] = "LONG"
        reasons = ["Close above EMA20 and EMA50", "EMA20 above EMA50", "RSI supports upward momentum", "MACD histogram positive"]
    elif last < e20[-1] < e50[-1] and current_rsi <= 50 and hist < 0:
        direction = "SHORT"
        reasons = ["Close below EMA20 and EMA50", "EMA20 below EMA50", "RSI supports downward momentum", "MACD histogram negative"]
    else:
        direction = "WAIT"
        reasons = ["Trend/momentum filters do not align; no trade signal"]

    return {
        "signal": direction,
        "last_close": last,
        "ema20": e20[-1],
        "ema50": e50[-1],
        "ema200": e200[-1],
        "rsi14": round(current_rsi, 2),
        "macd_histogram": hist,
        "reasons": reasons,
        "execution": "DISABLED",
    }


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).with_name("dashboard.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bybit-ai-trader", "trading_enabled": False}


@app.get("/api/bybit/account-connection")
def bybit_account_connection() -> dict:
    """Verify private Bybit API credentials without placing orders or returning balances."""
    api_key = os.getenv("BYBIT_API_KEY", "").strip()
    api_secret = os.getenv("BYBIT_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=503,
            detail="Bybit account connection is not configured. Add BYBIT_API_KEY and BYBIT_API_SECRET as server-side environment variables.",
        )
    try:
        private_client = HTTP(
            testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
            api_key=api_key,
            api_secret=api_secret,
            timeout=10,
            force_retry=False,
        )
        response = private_client.get_wallet_balance(accountType="UNIFIED")
        if response.get("retCode") != 0:
            # Do not return the raw exchange response or any credential-related details.
            raise HTTPException(status_code=502, detail="Bybit rejected the private API connection. Check key permissions and testnet/mainnet selection.")
        return {
            "connected": True,
            "environment": "testnet" if os.getenv("BYBIT_TESTNET", "false").lower() == "true" else "mainnet",
            "account_type": "UNIFIED",
            "trading_enabled": False,
            "orders_placed": False,
            "message": "Private Bybit API authentication succeeded. This endpoint is read-only and does not place orders.",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to authenticate with Bybit. Check API key permissions, IP restrictions, and environment selection.")



class OAuthAccountsRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    environment: Literal["mainnet", "testnet"] = "mainnet"


class OAuthSelectRequest(OAuthAccountsRequest):
    sub_member_id: str = Field(min_length=1, max_length=128)


def _bybit_oauth_get(access_token: str, environment: str, path: str, params: dict | None = None) -> dict:
    """Call Bybit's official AI-subaccount OAuth resource API without logging or exposing tokens."""
    host = "https://api2-testnet.bybit.com" if environment == "testnet" else "https://api2.bybit.com"
    url = host + path
    if params:
        url += "?" + urlencode(params)
    request = URLRequest(url, headers={
        "Authorization": f"Bearer {access_token.strip()}",
        "Accept": "application/json",
        "User-Agent": "Bybit-AI-Trader/0.2",
    })
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Never forward raw provider responses, which may contain sensitive data.
        if exc.code in (401, 403):
            raise HTTPException(status_code=401, detail="Bybit OAuth token is invalid or expired. Authorize again.") from None
        raise HTTPException(status_code=502, detail="Bybit OAuth service returned an HTTP error.") from None
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Could not reach Bybit OAuth. Try again.") from None
    code = payload.get("retCode", payload.get("ret_code", 0))
    if code not in (0, "0", None):
        if str(code) in {"33004", "401", "10001"}:
            raise HTTPException(status_code=401, detail="Bybit OAuth token expired or is invalid. Authorize again.")
        if str(code) == "20039":
            raise HTTPException(status_code=400, detail="Bind two-factor authentication (2FA) on Bybit, then retry.")
        provider_message = payload.get("retMsg", payload.get("ret_msg", ""))
        provider_message = str(provider_message).strip()[:180]
        detail = f"Bybit OAuth rejected the request (code {code})."
        if provider_message:
            detail += f" Provider message: {provider_message}"
        detail += " Check that the selected MAINNET/TESTNET environment matches where you authorized."
        raise HTTPException(status_code=502, detail=detail)
    return payload


def _oauth_result_accounts(payload: dict) -> list[dict]:
    result = payload.get("result", [])
    if isinstance(result, dict):
        result = result.get("list", result.get("accounts", [result]))
    if not isinstance(result, list):
        return []
    accounts = []
    for item in result:
        if not isinstance(item, dict):
            continue
        member_id = item.get("sub_member_id") or item.get("subMemberId") or item.get("member_id")
        if member_id is None:
            continue
        accounts.append({
            "sub_member_id": str(member_id),
            "name": str(item.get("sub_member_name") or item.get("name") or item.get("nickname") or f"AI Subaccount {member_id}"),
        })
    return accounts


@app.post("/api/bybit/oauth/accounts")
def bybit_oauth_accounts(body: OAuthAccountsRequest) -> dict:
    """List AI subaccounts for a user-provided OAuth token; never persist the token."""
    payload = _bybit_oauth_get(body.access_token, body.environment, "/oauth/v1/resource/restrict/ai_accounts")
    accounts = _oauth_result_accounts(payload)
    return {
        "environment": body.environment,
        "accounts": accounts,
        "count": len(accounts),
        "can_create": len(accounts) < 5,
        "storage": "browser-session-only",
    }


@app.post("/api/bybit/oauth/verify")
def bybit_oauth_verify(body: OAuthSelectRequest) -> dict:
    """Verify the selected AI subaccount without returning or persisting API credentials."""
    payload = _bybit_oauth_get(
        body.access_token, body.environment,
        "/oauth/v1/resource/restrict/ai_accounts",
        {"sub_member_id": body.sub_member_id},
    )
    result = payload.get("result", [])
    account = result[0] if isinstance(result, list) and result else result if isinstance(result, dict) else None
    if not isinstance(account, dict) or not account.get("api_key") or not account.get("api_secret"):
        raise HTTPException(status_code=502, detail="Bybit did not return credentials for the selected AI subaccount.")
    try:
        private_client = HTTP(
            testnet=body.environment == "testnet",
            api_key=str(account["api_key"]),
            api_secret=str(account["api_secret"]),
            timeout=10,
            force_retry=False,
        )
        response = private_client.get_wallet_balance(accountType="UNIFIED")
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit returned credentials, but private account verification failed.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Private Bybit verification failed. Check the selected AI subaccount and permissions.")
    key = str(account["api_key"])
    return {
        "connected": True,
        "environment": body.environment,
        "sub_member_id": str(account.get("sub_member_id") or body.sub_member_id),
        "account_name": str(account.get("sub_member_name") or account.get("name") or "Bybit AI Subaccount"),
        "api_key_masked": (key[:5] + "..." + key[-4:]) if len(key) > 9 else "***",
        "trading_enabled": False,
        "orders_placed": False,
        "message": "Bybit OAuth and private account verification succeeded. No credentials were returned to the browser and no orders were placed.",
        "storage": "browser-session-only",
    }


@app.get("/api/market/tickers")
def tickers(category: str = Query(default="linear", pattern="^(linear|spot)$")) -> dict:
    try:
        response = client.get_tickers(category=category)
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit market data request failed.")
        return {"category": category, "result": response.get("result", {}).get("list", [])}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to reach Bybit market data.")


@app.get("/api/scan/top")
def scan_top(
    interval: str = Query(default="5"),
    limit: int = Query(default=200, ge=200, le=500),
    top_n: int = Query(default=10, ge=1, le=20),
    min_turnover: float = Query(default=5_000_000, gt=0),
) -> dict:
    """Scan a bounded shortlist of liquid USDT perpetuals; analysis only."""
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail="Unsupported interval.")
    try:
        response = client.get_tickers(category="linear")
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit ticker request failed.")
        tickers = response.get("result", {}).get("list", [])
        eligible = []
        for item in tickers:
            symbol = item.get("symbol", "")
            try:
                turnover = float(item.get("turnover24h", 0))
                last_price = float(item.get("lastPrice", 0))
                change = float(item.get("price24hPcnt", 0)) * 100
            except (TypeError, ValueError):
                continue
            if symbol.endswith("USDT") and last_price > 0 and turnover >= min_turnover:
                eligible.append((turnover, symbol, last_price, change))
        eligible.sort(key=lambda row: row[0], reverse=True)
        results = []
        for turnover, symbol, last_price, change in eligible[:top_n]:
            try:
                klines = client.get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
                if klines.get("retCode") != 0:
                    continue
                candles = klines.get("result", {}).get("list", [])
                if len(candles) > 1:
                    candles = candles[1:]
                candles = list(reversed(candles))
                closes = [float(row[4]) for row in candles]
                if len(closes) < 200 or any(not math.isfinite(v) or v <= 0 for v in closes):
                    continue
                analysis = build_signal(closes)
                results.append({
                    "symbol": symbol, "price": last_price,
                    "change24h_pct": round(change, 2), "turnover24h": turnover,
                    "signal": analysis["signal"], "rsi14": analysis["rsi14"],
                    "ema20": analysis["ema20"], "ema50": analysis["ema50"],
                    "reasons": analysis["reasons"],
                })
            except Exception:
                continue
        results.sort(key=lambda row: (row["signal"] != "WAIT", row["turnover24h"]), reverse=True)
        return {
            "category": "linear", "interval": interval, "scanned": len(results),
            "requested": top_n, "results": results, "execution": "DISABLED",
            "disclaimer": "Shortlist uses liquidity, then technical filters. No orders are placed.",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to scan the Bybit futures shortlist.")


@app.get("/api/scan")
def scan(
    symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30, pattern="^[A-Z0-9]+$"),
    interval: str = Query(default="5"),
    limit: int = Query(default=200, ge=200, le=1000),
) -> dict:
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail="Unsupported interval.")
    try:
        response = client.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit rejected the market data request.")
        candles = response.get("result", {}).get("list", [])
        # Bybit returns newest-first; the first candle may still be forming.
        # Exclude it to avoid signals changing before the candle closes.
        if len(candles) > 1:
            candles = candles[1:]
        # Indicators require chronological order.
        candles = list(reversed(candles))
        closes = [float(candle[4]) for candle in candles]
        if not closes or any(not math.isfinite(value) or value <= 0 for value in closes):
            raise HTTPException(status_code=502, detail="Invalid candle data from Bybit.")
        analysis = build_signal(closes)
        return {
            "symbol": symbol,
            "category": "linear",
            "interval": interval,
            "candles_used": len(closes),
            "analysis": analysis,
            "disclaimer": "Heuristic signal only. No orders are placed; validate with backtests and demo trading.",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to scan this symbol. Check the symbol and retry.")
