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
    version="0.2.2",
    description="Independent analysis-only scanner for Bybit USDT perpetual markets.",
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
    return {"status": "ok", "service": "bybit-ai-trader", "version": "0.2.2", "trading_enabled": False, "oauth": "pkce-s256", "market_data": market}


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


class OAuthAccountsRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    environment: Literal["mainnet", "testnet", "unify-test-3", "auto"] = "auto"


class OAuthSelectRequest(OAuthAccountsRequest):
    sub_member_id: str = Field(min_length=1, max_length=128)


def _bybit_oauth_get(access_token: str, environment: str, path: str, params: dict | None = None) -> dict:
    if environment == "auto":
        last_error = None
        for candidate in ("mainnet", "testnet", "unify-test-3"):
            try:
                payload = _bybit_oauth_get(access_token, candidate, path, params)
                payload["_resolved_environment"] = candidate
                return payload
            except HTTPException as exc:
                if exc.status_code == 502 and "code 50000" in str(exc.detail) and "Token verify failed" in str(exc.detail):
                    last_error = exc
                    continue
                raise
        raise HTTPException(status_code=401, detail="Bybit rejected this OAuth access token on MAINNET/TESTNET/UNIFY-TEST-3. Token verify failed usually means the token is expired, incomplete, or not an OAuth access token.") from last_error
    hosts = {"mainnet": "https://api2.bybit.com", "testnet": "https://api2-testnet.bybit.com", "unify-test-3": "https://api2.unify-test-3.bybit.com"}
    host = hosts.get(environment)
    if not host:
        raise HTTPException(status_code=400, detail="Unsupported Bybit OAuth environment.")
    url = host + path
    if params:
        url += "?" + urlencode(params)
    request = URLRequest(url, headers={"Authorization": f"Bearer {access_token.strip()}", "Accept": "application/json", "User-Agent": "Bybit-AI-Trader/0.2"})
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
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
        provider_message = str(payload.get("retMsg", payload.get("ret_msg", ""))).strip()[:180]
        detail = f"Bybit OAuth rejected the request (code {code})."
        if provider_message:
            detail += f" Provider message: {provider_message}"
        raise HTTPException(status_code=502, detail=detail)
    payload["_resolved_environment"] = environment
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
        accounts.append({"sub_member_id": str(member_id), "name": str(item.get("sub_member_name") or item.get("name") or item.get("nickname") or f"AI Subaccount {member_id}")})
    return accounts


@app.post("/api/bybit/oauth/accounts")
def bybit_oauth_accounts(body: OAuthAccountsRequest) -> dict:
    payload = _bybit_oauth_get(body.access_token, body.environment, "/oauth/v1/resource/restrict/ai_accounts")
    accounts = _oauth_result_accounts(payload)
    resolved_environment = payload.get("_resolved_environment", body.environment)
    return {"environment": resolved_environment, "accounts": accounts, "count": len(accounts), "can_create": len(accounts) < 5, "storage": "browser-session-only"}


@app.post("/api/bybit/oauth/verify")
def bybit_oauth_verify(body: OAuthSelectRequest) -> dict:
    payload = _bybit_oauth_get(body.access_token, body.environment, "/oauth/v1/resource/restrict/ai_accounts", {"sub_member_id": body.sub_member_id})
    resolved_environment = payload.get("_resolved_environment", body.environment)
    result = payload.get("result", [])
    account = result[0] if isinstance(result, list) and result else result if isinstance(result, dict) else None
    if not isinstance(account, dict) or not account.get("api_key") or not account.get("api_secret"):
        raise HTTPException(status_code=502, detail="Bybit did not return credentials for the selected AI subaccount.")
    try:
        private_client = HTTP(testnet=resolved_environment == "testnet", api_key=str(account["api_key"]), api_secret=str(account["api_secret"]), timeout=10, force_retry=False)
        response = private_client.get_wallet_balance(accountType="UNIFIED")
        if response.get("retCode") != 0:
            raise HTTPException(status_code=502, detail="Bybit returned credentials, but private account verification failed.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Private Bybit verification failed.")
    key = str(account["api_key"])
    return {"connected": True, "environment": resolved_environment, "sub_member_id": str(account.get("sub_member_id") or body.sub_member_id), "account_name": str(account.get("sub_member_name") or account.get("name") or "Bybit AI Subaccount"), "api_key_masked": (key[:5] + "..." + key[-4:]) if len(key) > 9 else "***", "trading_enabled": False, "orders_placed": False, "message": "Bybit OAuth and private account verification succeeded. No credentials returned to browser.", "storage": "browser-session-only"}


from app.market_routes import register_market_routes
register_market_routes(app, client, ALLOWED_INTERVALS, build_signal)
