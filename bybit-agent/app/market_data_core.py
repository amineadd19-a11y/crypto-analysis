"""Shared HTTP helpers and Bybit primary market client."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

BYBIT_HOSTS = ("https://api.bybit.com", "https://api.bytick.com")
DEFAULT_TIMEOUT_SEC = 8.0
MAX_BYBIT_ATTEMPTS = 2


class UpstreamMarketError(Exception):
    def __init__(self, message: str, *, status: int | None = None, host: str | None = None, kind: str = "unknown", body_snippet: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.host = host
        self.kind = kind
        self.body_snippet = body_snippet[:200]


def _http_get_json(url: str, timeout: float = DEFAULT_TIMEOUT_SEC) -> tuple[dict, str]:
    host = url.split("/")[0] + "//" + url.split("/")[2]
    request = URLRequest(url, headers={"Accept": "application/json", "User-Agent": "Bybit-AI-Trader/0.2.2"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), host
    except HTTPError as exc:
        raw = b""
        try:
            raw = exc.read() or b""
        except Exception:
            pass
        text = raw.decode("utf-8", errors="replace")
        lower = text.lower()
        if exc.code == 403 and ("cloudfront" in lower or "block access from your country" in lower or "request could not be satisfied" in lower):
            raise UpstreamMarketError("Bybit CloudFront blocked this server IP (HTTP 403).", status=403, host=host, kind="cloudfront_block", body_snippet=text) from None
        raise UpstreamMarketError(f"Market HTTP {exc.code} from {host}.", status=exc.code, host=host, kind="http_error", body_snippet=text) from None
    except TimeoutError:
        raise UpstreamMarketError(f"Market request timed out after {timeout}s ({host}).", host=host, kind="timeout") from None
    except URLError as exc:
        raise UpstreamMarketError(f"Network error reaching market host ({host}): {exc.reason!s}"[:180], host=host, kind="network") from None
    except (ValueError, json.JSONDecodeError):
        raise UpstreamMarketError(f"Malformed JSON from market host ({host}).", host=host, kind="parse") from None


def bybit_market_get(path: str, params: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT_SEC) -> dict:
    query = f"?{urlencode(params)}" if params else ""
    last: UpstreamMarketError | None = None
    for host in BYBIT_HOSTS[:MAX_BYBIT_ATTEMPTS]:
        try:
            payload, resolved = _http_get_json(f"{host}{path}{query}", timeout=timeout)
        except UpstreamMarketError as exc:
            last = exc
            if exc.kind == "cloudfront_block":
                raise
            continue
        ret = payload.get("retCode", payload.get("ret_code", 0))
        if ret not in (0, "0", None):
            msg = str(payload.get("retMsg", payload.get("ret_msg", "")))[:120]
            raise UpstreamMarketError(f"Bybit rejected request (retCode {ret}). {msg}".strip(), host=resolved, kind="bybit_ret", body_snippet=msg)
        payload["_resolved_host"] = resolved
        payload["_data_source"] = "bybit"
        return payload
    if last is not None:
        raise last
    raise UpstreamMarketError("Bybit market data unavailable.", kind="unknown")


def raise_as_http(exc: UpstreamMarketError) -> None:
    from fastapi import HTTPException
    if exc.kind == "cloudfront_block":
        raise HTTPException(status_code=503, detail={"error": "market_data_degraded", "kind": exc.kind, "upstream_status": exc.status, "upstream_host": exc.host, "message": exc.message, "hint": "Bybit public market REST blocked; OKX fallback may apply."})
    if exc.kind == "timeout":
        raise HTTPException(status_code=504, detail={"error": "market_data_timeout", "kind": exc.kind, "upstream_host": exc.host, "message": exc.message})
    raise HTTPException(status_code=502, detail={"error": "market_data_upstream", "kind": exc.kind, "upstream_status": exc.status, "upstream_host": exc.host, "message": exc.message})
