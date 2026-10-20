"""AI Subaccount list / create / verify against official Bybit OAuth endpoints.

Official create: GET /oauth/v1/resource/restrict/ai_accounts?is_create=true
Official list:   GET /oauth/v1/resource/restrict/ai_accounts
Official bind:   GET /oauth/v1/resource/restrict/ai_accounts?sub_member_id=...
"""
from __future__ import annotations

import json
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import HTTPException
from pydantic import BaseModel, Field
from pybit.unified_trading import HTTP

OAUTH_API_HOSTS = {
    "mainnet": "https://api2.bybit.com",
    "testnet": "https://api2-testnet.bybit.com",
    "unify-test-3": "https://api2.unify-test-3.bybit.com",
}


class OAuthAccountsRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    environment: Literal["mainnet", "testnet", "unify-test-3", "auto"] = "auto"


class OAuthSelectRequest(OAuthAccountsRequest):
    sub_member_id: str = Field(min_length=1, max_length=128)


def bybit_oauth_get(access_token: str, environment: str, path: str, params: dict | None = None) -> dict:
    if environment == "auto":
        last_error = None
        for candidate in ("mainnet", "testnet", "unify-test-3"):
            try:
                payload = bybit_oauth_get(access_token, candidate, path, params)
                payload["_resolved_environment"] = candidate
                return payload
            except HTTPException as exc:
                detail = str(exc.detail)
                if exc.status_code == 502 and "code 50000" in detail and "Token verify fail" in detail:
                    last_error = exc
                    continue
                raise
        raise HTTPException(
            status_code=401,
            detail=(
                "Bybit rejected this OAuth access token on MAINNET/TESTNET/UNIFY-TEST-3. "
                "Token verify fail usually means the token is expired, incomplete, exchanged "
                "for a different environment, or is not an OAuth access token from the agent flow."
            ),
        ) from last_error

    host = OAUTH_API_HOSTS.get(environment)
    if not host:
        raise HTTPException(status_code=400, detail="Unsupported Bybit OAuth environment.")
    url = host + path
    if params:
        url += "?" + urlencode(params)
    request = URLRequest(
        url,
        headers={
            "Authorization": f"Bearer {access_token.strip()}",
            "Accept": "application/json",
            "User-Agent": "Bybit-AI-Trader/0.2",
        },
    )
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


def oauth_result_accounts(payload: dict) -> list[dict]:
    result = payload.get("result", [])
    if isinstance(result, dict):
        if result.get("api_key") or result.get("sub_member_id") or result.get("subMemberId"):
            if "list" not in result and "accounts" not in result:
                member_id = result.get("sub_member_id") or result.get("subMemberId") or result.get("member_id")
                if member_id is not None:
                    return [{
                        "sub_member_id": str(member_id),
                        "name": str(
                            result.get("sub_member_name")
                            or result.get("name")
                            or result.get("nickname")
                            or f"AI Subaccount {member_id}"
                        ),
                    }]
        result = result.get("list", result.get("accounts", []))
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
            "name": str(
                item.get("sub_member_name")
                or item.get("name")
                or item.get("nickname")
                or f"AI Subaccount {member_id}"
            ),
        })
    return accounts


def oauth_extract_credential_account(payload: dict) -> dict | None:
    result = payload.get("result", [])
    if isinstance(result, list) and result:
        account = result[0]
    elif isinstance(result, dict):
        account = result
    else:
        account = None
    if not isinstance(account, dict):
        return None
    if not account.get("api_key") or not account.get("api_secret"):
        return None
    return account


def verify_ai_subaccount_credentials(account: dict, resolved_environment: str, sub_member_id_fallback: str = "") -> dict:
    try:
        private_client = HTTP(
            testnet=resolved_environment == "testnet",
            api_key=str(account["api_key"]),
            api_secret=str(account["api_secret"]),
            timeout=10,
            force_retry=False,
        )
        response = private_client.get_wallet_balance(accountType="UNIFIED")
        if response.get("retCode") != 0:
            raise HTTPException(
                status_code=502,
                detail="Bybit returned credentials, but private account verification failed.",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Private Bybit verification failed.")
    key = str(account["api_key"])
    return {
        "connected": True,
        "environment": resolved_environment,
        "sub_member_id": str(account.get("sub_member_id") or account.get("subMemberId") or sub_member_id_fallback),
        "account_name": str(
            account.get("sub_member_name")
            or account.get("name")
            or account.get("nickname")
            or "Bybit AI Subaccount"
        ),
        "api_key_masked": (key[:5] + "..." + key[-4:]) if len(key) > 9 else "***",
        "trading_enabled": False,
        "orders_placed": False,
        "message": "Bybit OAuth and private account verification succeeded. No credentials returned to browser.",
        "storage": "browser-session-only",
    }
