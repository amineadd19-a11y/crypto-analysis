"""Upstream market-data client: timeouts, HTTP 5xx, CloudFront 403, success."""
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
    def test_successful_tickers(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            {
                "retCode": 0,
                "result": {"list": [{"symbol": "BTCUSDT", "lastPrice": "100.0"}]},
            }
        )
        payload = market_data.get_tickers(category="linear", symbol="BTCUSDT")
        self.assertEqual(payload["retCode"], 0)
        self.assertTrue(payload["_resolved_host"].startswith("https://"))
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("app.market_data.urlopen")
    def test_cloudfront_403_is_classified(self, mock_urlopen):
        body = b"{\n    error:The Amazon CloudFront distribution is configured to block access from your country\n}"
        mock_urlopen.side_effect = _http_error(403, body)
        with self.assertRaises(market_data.UpstreamMarketError) as caught:
            market_data.get_tickers(category="linear")
        self.assertEqual(caught.exception.kind, "cloudfront_block")
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("app.market_data.urlopen")
    def test_timeout_then_alternate_host(self, mock_urlopen):
        mock_urlopen.side_effect = [
            TimeoutError(),
            _FakeResponse({"retCode": 0, "result": {"list": []}}),
        ]
        payload = market_data.get_tickers(category="linear")
        self.assertEqual(payload["retCode"], 0)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("app.market_data.urlopen")
    def test_http_5xx_maps_to_upstream_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(502, b"Bad Gateway")
        with self.assertRaises(market_data.UpstreamMarketError) as caught:
            market_data.get_kline("linear", "BTCUSDT", "5", 200)
        self.assertEqual(caught.exception.kind, "http_error")
        self.assertEqual(caught.exception.status, 502)

    @patch("app.market_data.urlopen")
    def test_malformed_json(self, mock_urlopen):
        class Bad:
            status = 200

            def read(self):
                return b"not-json"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        mock_urlopen.side_effect = [Bad(), Bad()]
        with self.assertRaises(market_data.UpstreamMarketError) as caught:
            market_data.get_tickers()
        self.assertEqual(caught.exception.kind, "parse")

    @patch("app.market_data.urlopen")
    def test_bybit_retcode_nonzero(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse({"retCode": 10001, "retMsg": "params error"})
        with self.assertRaises(market_data.UpstreamMarketError) as caught:
            market_data.get_tickers()
        self.assertEqual(caught.exception.kind, "bybit_ret")

    @patch("app.market_data.urlopen")
    def test_raise_as_http_cloudfront_is_503(self, mock_urlopen):
        body = b"CloudFront block access from your country"
        mock_urlopen.side_effect = _http_error(403, body)
        with self.assertRaises(market_data.UpstreamMarketError) as upstream:
            market_data.get_tickers()
        with self.assertRaises(HTTPException) as http:
            market_data.raise_as_http(upstream.exception)
        self.assertEqual(http.exception.status_code, 503)
        detail = http.exception.detail
        self.assertEqual(detail["error"], "market_data_degraded")
        self.assertEqual(detail["kind"], "cloudfront_block")

    @patch("app.market_data.urlopen")
    def test_probe_reports_degraded_on_block(self, mock_urlopen):
        body = b"The Amazon CloudFront distribution is configured to block access from your country"
        mock_urlopen.side_effect = _http_error(403, body)
        result = market_data.probe_market_connectivity(timeout=2.0)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["kind"], "cloudfront_block")

    @patch("app.market_data.urlopen")
    def test_probe_ok(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            {"retCode": 0, "result": {"list": [{"symbol": "BTCUSDT", "lastPrice": "1"}]}}
        )
        result = market_data.probe_market_connectivity(timeout=2.0)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["sample_last_price_present"])

    @patch("app.market_data.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("Name or service not known")
        with self.assertRaises(market_data.UpstreamMarketError) as caught:
            market_data.get_tickers()
        self.assertEqual(caught.exception.kind, "network")
        self.assertEqual(mock_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
