import io
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import main
from app import oauth_flow


class OAuthEnvironmentDetectionTests(unittest.TestCase):
    @staticmethod
    def response(payload):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    @patch("app.oauth_accounts_core.urlopen")
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

    @patch("app.oauth_accounts_core.urlopen")
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

    @patch("app.oauth_accounts_core.urlopen")
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

    @patch("app.oauth_accounts_core.urlopen")
    def test_auto_detects_mainnet_without_second_request(self, mock_urlopen):
        mock_urlopen.return_value = self.response({"retCode": 0, "result": []})

        payload = main._bybit_oauth_get(
            "x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts"
        )

        self.assertEqual(payload["_resolved_environment"], "mainnet")
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("app.oauth_accounts_core.urlopen")
    def test_auto_all_hosts_fail_gives_clear_token_message(self, mock_urlopen):
        mock_urlopen.side_effect = [
            self.response({"retCode": 50000, "retMsg": "Token verify failed"}),
            self.response({"retCode": 50000, "retMsg": "Token verify failed"}),
            self.response({"retCode": 50000, "retMsg": "Token verify failed"}),
        ]
        with self.assertRaises(HTTPException) as caught:
            main._bybit_oauth_get("x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts")
        self.assertEqual(caught.exception.status_code, 401)
        self.assertIn("not an OAuth access token", caught.exception.detail)
        self.assertEqual(mock_urlopen.call_count, 3)


class OAuthStartAndExchangeTests(unittest.TestCase):
    def test_start_returns_pkce_authorize_url(self):
        result = main.bybit_oauth_start(main.OAuthStartRequest(environment="mainnet"))
        self.assertEqual(result["environment"], "mainnet")
        self.assertIn("client_id=ai-agent", result["authorize_url"])
        self.assertIn("code_challenge_method=S256", result["authorize_url"])
        self.assertIn("scope=ai-account", result["authorize_url"])
        self.assertTrue(result["authorize_url"].startswith("https://www.bybit.com/oauth?"))
        self.assertGreaterEqual(len(result["code_verifier"]), 43)
        self.assertFalse(result["trading_enabled"])

    def test_start_testnet_host(self):
        result = main.bybit_oauth_start(main.OAuthStartRequest(environment="testnet"))
        self.assertTrue(result["authorize_url"].startswith("https://testnet.bybit.com/oauth?"))

    @patch("app.oauth_flow.urlopen")
    def test_exchange_posts_code_and_verifier(self, mock_urlopen):
        mock_urlopen.return_value = io.BytesIO(
            json.dumps({"retCode": 0, "result": {"access_token": "tok_abc", "expires_in": 3600}}).encode()
        )
        result = main.bybit_oauth_exchange(
            main.OAuthExchangeRequest(
                code="authcode12345678",
                code_verifier="v" * 64,
                environment="mainnet",
            )
        )
        self.assertEqual(result["access_token"], "tok_abc")
        self.assertEqual(result["environment"], "mainnet")
        req = mock_urlopen.call_args.args[0]
        self.assertIn("/oauth/v1/public/access_token", req.full_url)
        body = req.data.decode()
        self.assertIn("client_id=ai-agent", body)
        self.assertIn("code=authcode12345678", body)
        self.assertIn("code_verifier=" + "v" * 64, body)

    @patch("app.oauth_flow.urlopen")
    def test_exchange_failure_is_401(self, mock_urlopen):
        mock_urlopen.return_value = io.BytesIO(
            json.dumps({"retCode": 10001, "retMsg": "code expired"}).encode()
        )
        with self.assertRaises(HTTPException) as caught:
            main.bybit_oauth_exchange(
                main.OAuthExchangeRequest(
                    code="authcode12345678",
                    code_verifier="v" * 64,
                    environment="mainnet",
                )
            )
        self.assertEqual(caught.exception.status_code, 401)
        self.assertIn("Token exchange failed", caught.exception.detail)


class OAuthAccountsAndCreateTests(unittest.TestCase):
    @staticmethod
    def response(payload):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    @patch("app.oauth_accounts_core.urlopen")
    def test_accounts_empty_returns_create_guidance(self, mock_urlopen):
        mock_urlopen.return_value = self.response({"retCode": 0, "result": []})
        result = main.bybit_oauth_accounts(
            main.OAuthAccountsRequest(access_token="x" * 30, environment="mainnet")
        )
        self.assertEqual(result["count"], 0)
        self.assertTrue(result["can_create"])
        self.assertIn("is_create=true", result["next_step"])
        self.assertEqual(result["create_endpoint"], "/api/bybit/oauth/create-account")
        self.assertFalse(result["trading_enabled"])

    @patch("app.oauth_accounts_core.urlopen")
    def test_accounts_parses_nickname_list(self, mock_urlopen):
        mock_urlopen.return_value = self.response({
            "retCode": 0,
            "result": [
                {"sub_member_id": "111", "nickname": "BotA"},
                {"sub_member_id": "222", "nickname": "BotB"},
            ],
        })
        result = main.bybit_oauth_accounts(
            main.OAuthAccountsRequest(access_token="x" * 30, environment="mainnet")
        )
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["accounts"][0]["name"], "BotA")
        self.assertEqual(result["accounts"][1]["sub_member_id"], "222")
        self.assertTrue(result["can_create"])

    @patch("app.oauth_accounts_core.HTTP")
    @patch("app.oauth_accounts_core.urlopen")
    def test_create_account_calls_is_create_true(self, mock_urlopen, mock_http):
        mock_urlopen.side_effect = [
            self.response({"retCode": 0, "result": []}),
            self.response({
                "retCode": 0,
                "result": {
                    "sub_member_id": "999",
                    "nickname": "NewAI",
                    "api_key": "AbCdE1234567890",
                    "api_secret": "secretvalue",
                },
            }),
        ]
        mock_http.return_value.get_wallet_balance.return_value = {"retCode": 0, "result": {}}
        result = main.bybit_oauth_create_account(
            main.OAuthAccountsRequest(access_token="x" * 30, environment="mainnet")
        )
        self.assertTrue(result["created"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["sub_member_id"], "999")
        self.assertFalse(result["trading_enabled"])
        self.assertIn("...", result["api_key_masked"])
        create_req = mock_urlopen.call_args_list[1].args[0]
        self.assertIn("is_create=true", create_req.full_url)
        self.assertIn("/oauth/v1/resource/restrict/ai_accounts", create_req.full_url)

    @patch("app.oauth_accounts_core.urlopen")
    def test_create_blocked_when_already_five(self, mock_urlopen):
        five = [{"sub_member_id": str(i), "nickname": f"A{i}"} for i in range(5)]
        mock_urlopen.return_value = self.response({"retCode": 0, "result": five})
        with self.assertRaises(HTTPException) as caught:
            main.bybit_oauth_create_account(
                main.OAuthAccountsRequest(access_token="x" * 30, environment="mainnet")
            )
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("at most 5", caught.exception.detail)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("app.oauth_accounts_core.urlopen")
    def test_auto_retries_on_token_verify_fail_without_ed(self, mock_urlopen):
        """Provider often returns 'Token verify fail' without trailing 'ed'."""
        mock_urlopen.side_effect = [
            self.response({"retCode": 50000, "retMsg": "Token verify fail"}),
            self.response({"retCode": 0, "result": []}),
        ]
        payload = main._bybit_oauth_get(
            "x" * 30, "auto", "/oauth/v1/resource/restrict/ai_accounts"
        )
        self.assertEqual(payload["_resolved_environment"], "testnet")
        self.assertEqual(mock_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
