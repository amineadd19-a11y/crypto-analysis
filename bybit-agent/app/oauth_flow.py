"""Official Bybit AI-agent OAuth helpers (PKCE S256). Analysis-only; no trading."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import HTTPException
from pydantic import BaseModel, Field

OAUTH_CLIENT_ID = "ai-agent"
OAUTH_SCOPE = "ai-account"
OAUTH_HOSTS = {
    "mainnet": {
        "authorize": "https://www.bybit.com/oauth",
        "api_base": "https://api2.bybit.com",
        "redirect_uri": "https://www.bybit.com/oauth/callback",
    },
    "testnet": {
        "authorize": "https://testnet.bybit.com/oauth",
        "api_base": "https://api2-testnet.bybit.com",
        "redirect_uri": "https://testnet.bybit.com/oauth/callback",
    },
    "unify-test-3": {
        "authorize": "https://www.unify-test-3.bybit.com/zh-MY/oauth",
        "api_base": "https://api2.unify-test-3.bybit.com",
        "redirect_uri": "https://www.unify-test-3.bybit.com/oauth/callback",
    },
}


class OAuthStartRequest(BaseModel):
    environment: Literal["mainnet", "testnet", "unify-test-3"] = "mainnet"


class OAuthExchangeRequest(BaseModel):
    code: str = Field(min_length=8, max_length=2048)
    code_verifier: str = Field(min_length=43, max_length=128)
    environment: Literal["mainnet", "testnet", "unify-test-3"] = "mainnet"


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def start_oauth(environment: str) -> dict:
    host = OAUTH_HOSTS[environment]
    verifier, challenge = pkce_pair()
    state = secrets.token_hex(8)
    query = urlencode({
        "client_id": OAUTH_CLIENT_ID,
        "response_type": "code",
        "scope": OAUTH_SCOPE,
        "state": state,
        "redirect_uri": host["redirect_uri"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return {
        "environment": environment,
        "authorize_url": f"{host['authorize']}?{query}",
        "code_verifier": verifier,
        "state": state,
        "client_id": OAUTH_CLIENT_ID,
        "scope": OAUTH_SCOPE,
        "redirect_uri": host["redirect_uri"],
        "instructions": (
            "Open authorize_url, authorize on Bybit, paste access token or auth code. "
            "Do not paste API keys or secrets."
        ),
        "storage": "browser-session-only",
        "trading_enabled": False,
    }


def exchange_code(code: str, code_verifier: str, environment: str) -> dict:
    host = OAUTH_HOSTS[environment]
    url = f"{host['api_base']}/oauth/v1/public/access_token"
    data = urlencode({
        "client_id": OAUTH_CLIENT_ID,
        "code": code.strip(),
        "code_verifier": code_verifier.strip(),
    }).encode()
    request = URLRequest(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Bybit-AI-Trader/0.2",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        # HTTPError means DNS/TLS/connection succeeded and Bybit (or its edge) replied.
        # Surface only bounded, non-secret provider diagnostics instead of mislabeling it
        # as a network-connectivity failure.
        try:
            error_payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            ret_code = error_payload.get("retCode", error_payload.get("ret_code"))
            ret_msg = str(error_payload.get("retMsg", error_payload.get("ret_msg", "")))[:160]
            provider_detail = f" retCode={ret_code}; {ret_msg}" if ret_code is not None or ret_msg else ""
        except (ValueError, json.JSONDecodeError):
            provider_detail = ""
        raise HTTPException(
            status_code=502,
            detail=f"Bybit token endpoint returned HTTP {exc.code}.{provider_detail} Check environment and restart OAuth authorization.",
        ) from None
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        reason_text = str(reason).lower()
        if "name or service not known" in reason_text or "temporary failure in name resolution" in reason_text or "getaddrinfo failed" in reason_text:
            diagnosis = "DNS resolution failed"
        elif "timed out" in reason_text or isinstance(reason, TimeoutError):
            diagnosis = "connection timed out"
        elif "ssl" in reason_text or "certificate" in reason_text or "tls" in reason_text:
            diagnosis = "TLS handshake failed"
        elif "refused" in reason_text:
            diagnosis = "connection refused"
        else:
            diagnosis = "network connection failed"
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Bybit token endpoint ({diagnosis}). Check outbound connectivity from Vercel and retry with a fresh OAuth authorization code.",
        ) from None
    try:
        payload = json.loads(raw_body)
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="Bybit token endpoint returned a non-JSON response. Retry with a fresh OAuth authorization code.",
        ) from None
    ret = payload.get("retCode", payload.get("ret_code", 0))
    token_data = payload.get("result") or payload
    if ret not in (0, "0", None) and not token_data.get("access_token"):
        msg = str(payload.get("retMsg", payload.get("ret_msg", "")))[:180]
        raise HTTPException(
            status_code=401,
            detail=f"Token exchange failed (code {ret}). {msg} Start authorization again.",
        )
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Bybit did not return an access token.")
    return {
        "environment": environment,
        "access_token": access_token,
        "token_type": token_data.get("token_type", "bearer"),
        "expires_in": token_data.get("expires_in", 86400),
        "refresh_token": token_data.get("refresh_token"),
        "message": "Token exchange succeeded. Token is not stored on the server.",
        "storage": "browser-session-only",
        "trading_enabled": False,
    }
