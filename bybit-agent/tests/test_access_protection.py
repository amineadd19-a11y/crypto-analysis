import unittest

from app.main import access_denial


class AccessProtectionTests(unittest.TestCase):
    def test_rejects_missing_or_wrong_bearer_token(self):
        self.assertEqual(access_denial("/api/scan", "", True, "long-test-secret").status_code, 401)
        self.assertEqual(access_denial("/api/scan", "Bearer wrong", True, "long-test-secret").status_code, 401)

    def test_accepts_correct_bearer_token(self):
        self.assertIsNone(access_denial("/api/scan", "Bearer long-test-secret", True, "long-test-secret"))

    def test_fails_closed_if_token_required_but_missing(self):
        self.assertEqual(access_denial("/api/scan", "", True, "").status_code, 503)

    def test_health_and_dashboard_shell_remain_public(self):
        self.assertIsNone(access_denial("/health", "", True, "long-test-secret"))
        self.assertIsNone(access_denial("/", "", True, "long-test-secret"))

    def test_optional_token_does_not_protect_when_require_false(self):
        # REQUIRE_ACCESS_TOKEN=false must leave APIs open even if AGENT_ACCESS_TOKEN is set.
        self.assertIsNone(access_denial("/api/scan", "", False, "configured-secret"))
        self.assertIsNone(access_denial("/api/scan", "Bearer anything", False, "configured-secret"))


if __name__ == "__main__":
    unittest.main()
