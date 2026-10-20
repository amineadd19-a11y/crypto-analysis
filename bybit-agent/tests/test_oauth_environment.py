import io
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import main


class OAuthEnvironmentDetectionTests(unittest.TestCase):
    @staticmethod
    def response(payload):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    @patch("app.main.urlopen")
    def test_auto_retries_only_on_environment_mismatch(self, mock_urlopen):
        mock_urlopen.side_effect = [
            self.response({"retCode": 50000, "retMsg": "Token verify failed"}),
            self.response({"retCode": 0, "result": []}),
        ]

        payload = main._bybit_oauth_get(
            "x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts"
        )

        self.assertEqual(payload["_resolved_environment"], "testnet")
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIn("https://api2.bybit.com/", mock_urlopen.call_args_list[0].args[0].full_url)
        self.assertIn("https://api2-testnet.bybit.com/", mock_urlopen.call_args_list[1].args[0].full_url)


    @patch("app.main.urlopen")
    def test_auto_retries_unify_test_3_after_both_standard_hosts_reject(self, mock_urlopen):
        mock_urlopen.side_effect = [
            self.response({"retCode": 50000, "retMsg": "Token verify failed"}),
            self.response({"retCode": 50000, "retMsg": "Token verify failed"}),
            self.response({"retCode": 0, "result": []}),
        ]

        payload = main._bybit_oauth_get(
            "x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts"
        )

        self.assertEqual(payload["_resolved_environment"], "unify-test-3")
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertIn("https://api2.unify-test-3.bybit.com/", mock_urlopen.call_args_list[2].args[0].full_url)

    @patch("app.main.urlopen")
    def test_auto_does_not_retry_non_environment_errors(self, mock_urlopen):
        mock_urlopen.return_value = self.response(
            {"retCode": 20039, "retMsg": "2FA required"}
        )

        with self.assertRaises(HTTPException) as caught:
            main._bybit_oauth_get(
                "x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts"
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("2FA", caught.exception.detail)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("app.main.urlopen")
    def test_auto_detects_mainnet_without_second_request(self, mock_urlopen):
        mock_urlopen.return_value = self.response({"retCode": 0, "result": []})

        payload = main._bybit_oauth_get(
            "x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts"
        )

        self.assertEqual(payload["_resolved_environment"], "mainnet")
        self.assertEqual(mock_urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
