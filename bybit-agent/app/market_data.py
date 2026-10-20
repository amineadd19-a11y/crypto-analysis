"""Public Bybit market-data client with bounded timeouts and clear upstream errors.

Bybit serves market REST on api.bybit.com / api.bytick.com behind CloudFront.
Many cloud egress IPs (including typical Vercel/AWS ranges) receive HTTP 403
from CloudFront (\"block access from your country\") before application logic.
This module never fabricates prices; it surfaces degraded status instead.
"""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import HTTPException

# Official public hosts (docs: api.bybit.com and api.bytick.com).
MARKET_HOSTS = (
    "https://api.bybit.com",
    "https://api.bytick.com",
)

DEFAULT_TIMEOUT_SEC = 8.0
MAX_ATTEMPTS = 2  # primary host + one alternate; no retry storms


class UpstreamMarketError(Exception):
    """Structured failure talking to Bybit public market API."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        host: str | None = None,
        kind: str = "unknown",
        body_snippet: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.host = host
        self.kind = kind  # cloudfront_block | http_error | timeout | network | parse | bybit_ret
        self.body_snippet = body_snippet[:200]


def _classify_http_error(exc: HTTPError, host: str) -> UpstreamMarketError:
    raw = b""
    try:
        raw = exc.read() or b""
    except Exception:
        pass
    text = raw.decode("utf-8", errors="replace")
    lower = text.lower()
    if exc.code == 403 and (
        "cloudfront" in lower
        or "block access from your country" in lower
        or "request could not be satisfied" in lower
    ):
        return UpstreamMarketError(
            "Bybit CloudFront blocked this server IP (HTTP 403). "
            "Public market endpoints on api.bybit.com reject many cloud provider ranges. "
            "OAuth (api2.bybit.com) is unaffected. Market scan is degraded until egress is allowed.",
            status=403,
            host=host,
            kind="cloudfront_block",
            body_snippet=text,
        )
    return UpstreamMarketError(
        f"Bybit market HTTP {exc.code} from {host}.",
        status=exc.code,
        host=host,
        kind="http_error",
        body_snippet=text,
    )


def bybit_market_get(path: str, params: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT_SEC) -> dict:
    """GET a Bybit V5 public market path. Tries hosts in order; bounded attempts."""
    query = f"?{urlencode(params)}" if params else ""
    last: UpstreamMarketError | None = None
    for host in MARKET_HOSTS[:MAX_ATTEMPTS]:
        url = f"{host}{path}{query}"
        request = URLRequest(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Bybit-AI-Trader/0.2",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last = _classify_http_error(exc, host)
            if last.kind == "cloudfront_block":
                raise last
            continue
        except TimeoutError:
            last = UpstreamMarketError(
                f"Bybit market request timed out after {timeout}s ({host}).",
                host=host,
                kind="timeout",
            )
            continue
        except URLError as exc:
            last = UpstreamMarketError(
                f"Network error reaching Bybit market ({host}): {exc.reason!s}"[:180],
                host=host,
                kind="network",
            )
            continue
        except (ValueError, json.JSONDecodeError):
            last = UpstreamMarketError(
                f"Malformed JSON from Bybit market ({host}).",
                host=host,
                kind="parse",
            )
            continue

        ret = payload.get("retCode", payload.get("ret_code", 0))
        if ret not in (0, "0", None):
            msg = str(payload.get("retMsg", payload.get("ret_msg", "")))[:120]
            raise UpstreamMarketError(
                f"Bybit market rejected request (retCode {ret}). {msg}".strip(),
                status=None,
                host=host,
                kind="bybit_ret",
                body_snippet=msg,
            )
        payload["_resolved_host"] = host
        return payload

    if last is not None:
        raise last
    raise UpstreamMarketError("Bybit market data unavailable.", kind="unknown")


def probe_market_connectivity(timeout: float = 5.0) -> dict:
    """Lightweight readiness probe for /health. Does not fabricate prices."""
    started = time.monotonic()
    try:
        payload = bybit_market_get(
            "/v5/market/tickers",
            {"category": "linear", "symbol": "BTCUSDT"},
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        row = (payload.get("result") or {}).get("list") or []
        last = row[0].get("lastPrice") if row else None
        return {
            "status": "ok",
            "host": payload.get("_resolved_host"),
            "latency_ms": elapsed_ms,
            "sample_symbol": "BTCUSDT",
            "sample_last_price_present": bool(last),
        }
    except UpstreamMarketError as exc:
        return {
            "status": "degraded",
            "kind": exc.kind,
            "http_status": exc.status,
            "host": exp.host if False else exc.host,
            "message": exp.message if False else exc.message,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }


def raise_as_http(exc: UpstreamMarketError) -> None:
    """Map upstream errors to HTTP responses without inventing market data."""
    if exc.kind == "cloudfront_block":
        raise HTTPException(
            status_code=503,
            detail={
                "error": "market_data_degraded",
                "kind": exp.kind if False else exc.kind,
                "upstream_status": exc.status,
                "upstream_host": exc.host,
                "message": exc.message,
                "hint": (
                    "Server-side calls to api.bybit.com are blocked by Bybit's CDN for this host. "
                    "Health remains OK; OAuth uses a different host (api2). "
                    "Run the scanner on a non-cloud IP or wait for Bybit egress allowlisting."
                ),
            },
        )
    if exc.kind == "timeout":
        raise HTTPException(
            status_code=504,
            detail={
                "error": "market_data_timeout",
                "kind": exc.kind,
                "upstream_host": exp.host if False else exc.host,
                "message": exp.message if False else exc.message,
            },
        )
    raise HTTPException(
        status_code=502,
        detail={
            "error": "market_data_upstream",
            "kind": exp.kind if False else exc.kind,
            "upstream_status": exp.status if False else exc.status,
            "upstream_host": exp.host if False else exc.host,
            "message": exp.message if False else exc.message,
        },
    )


def get_tickers(category: str = "linear", symbol: str | None = None) -> dict:
    params: dict[str, Any] = {"category": category}
    if symbol:
        params["symbol"] = symbol
    return bybit_market_get("/v5/market/tickers", params)


def get_kline(category: str, symbol: str, interval: str, limit: int) -> dict:
    return bybit_market_get(
        "/v5/market/kline",
        {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
    )
