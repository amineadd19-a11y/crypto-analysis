"""Upstream market-data client: Bybit, OKX fallback, timeouts, CloudFront 403."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fastapi import HTTPException

from app import market_data


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _http_error(code: int, body: bytes, url: str = "https://api.bybit.com/v5/market/tickers"):
    return HTTPError(url, code, "error", hdrs=None, fp=io.BytesIO(body))


class MarketDataClientTests(unittest.TestCase):
    @patch("app.market_data.urlopen")
    def test_successful_bybit_tickers(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            {"retCode": 0, "result": {"list": [{"symbol": "BTCUSDT", "lastPrice": "100.0"}]}}
        )
        payload = market_data.get_tickers(category="linear", symbol="BTCUSDT")
        self.assertEqual(payload["retCode"], 0)
        self.assertEqual(payload["_data_source"], "bybit")

    @patch("app.market_data.urlopen")
    def test_cloudfront_falls_back_to_okx(self, mock_urlopen):
        body = b"The Amazon CloudFront distribution is configured to block access from your country"
        mock_urlopen.side_effect = [
            _http_error(403, body),
            _FakeResponse({"code": "0", "data": [{"instType": "SWAP", "instId": "BTC-USDT-SWAP", "last": "50000", "open24h": "49000", "volCcy24h": "1000000"}]}),
        ]
        payload = market_data.get_tickers(category="linear", symbol="BTCUSDT")
        self.assertEqual(payload["_data_source"], "okx-public")
        self.assertEqual(payload["_bybit_error"], "cloudfront_block")
        self.assertEqual(payload["result"]["list"][0]["symbol"], "BTCUSDT")

    @patch("app.market_data.urlopen")
    def test_okx_kline_fallback(self, mock_urlopen):
        body = b"CloudFront block access from your country"
        mock_urlopen.side_effect = [
            _http_error(403, body, url="https://api.bybit.com/v5/market/kline"),
            _FakeResponse({"code": "0", "data": [["1000", "1", "2", "0.5", "1.5"], ["900", "1", "2", "0.5", "1.4"]]}),
        ]
        payload = market_data.get_kline("linear", "BTCUSDT", "5", 200)
        self.assertEqual(payload["_data_source"], "okx-public")

    @patch("app.market_data.urlopen")
    def test_probe_reports_okx_when_bybit_blocked(self, mock_urlopen):
        body = b"The Amazon CloudFront distribution is configured to block access from your country"

        def side_effect(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "bybit" in url or "bytick" in url:
                raise _http_error(403, body, url=url)
            return _FakeResponse({"code": "0", "data": [{"instId": "BTC-USDT-SWAP", "last": "1", "open24h": "1", "volCcy24h": "1"}]})

        mock_urlopen.side_effect = side_effect
        result = market_data.probe_market_connectivity(timeout=2.0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["active_source"], "okx-public")

    @patch("app.market_data.urlopen")
    def test_raise_as_http_cloudfront_is_503(self, mock_urlopen):
        body = b"CloudFront block access from your country"
        mock_urlopen.side_effect = _http_error(403, body)
        with self.assertRaises(market_data.UpstreamMarketError) as upstream:
            market_data.bybit_market_get("/v5/market/tickers")
        with self.assertRaises(HTTPException) as http:
            market_data.raise_as_http(upstream.exception)
        self.assertEqual(http.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
