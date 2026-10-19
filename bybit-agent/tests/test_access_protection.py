import os
import unittest
from unittest.mock import patch

from fastapi import Request
from fastapi.responses import JSONResponse

from app.main import protect_public_endpoints


def make_request(path="/", authorization=""):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"authorization", authorization.encode())] if authorization else [],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }
    return Request(scope)


class AccessProtectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_missing_or_wrong_bearer_token(self):
        async def call_next(_request):
            return JSONResponse({"ok": True})

        with patch.dict(os.environ, {"REQUIRE_ACCESS_TOKEN": "true", "AGENT_ACCESS_TOKEN": "long-test-secret"}):
            response = await protect_public_endpoints(make_request("/api/scan"), call_next)
        self.assertEqual(response.status_code, 401)

        with patch.dict(os.environ, {"REQUIRE_ACCESS_TOKEN": "true", "AGENT_ACCESS_TOKEN": "long-test-secret"}):
            response = await protect_public_endpoints(make_request("/api/scan", "Bearer wrong"), call_next)
        self.assertEqual(response.status_code, 401)

    async def test_accepts_correct_bearer_token(self):
        async def call_next(_request):
            return JSONResponse({"ok": True})

        with patch.dict(os.environ, {"REQUIRE_ACCESS_TOKEN": "true", "AGENT_ACCESS_TOKEN": "long-test-secret"}):
            response = await protect_public_endpoints(make_request("/api/scan", "Bearer long-test-secret"), call_next)
        self.assertEqual(response.status_code, 200)

    async def test_fails_closed_if_token_required_but_missing(self):
        async def call_next(_request):
            return JSONResponse({"ok": True})

        with patch.dict(os.environ, {"REQUIRE_ACCESS_TOKEN": "true", "AGENT_ACCESS_TOKEN": ""}):
            response = await protect_public_endpoints(make_request("/api/scan"), call_next)
        self.assertEqual(response.status_code, 503)

    async def test_health_and_dashboard_shell_remain_public(self):
        async def call_next(_request):
            return JSONResponse({"status": "ok"})

        with patch.dict(os.environ, {"REQUIRE_ACCESS_TOKEN": "true", "AGENT_ACCESS_TOKEN": "long-test-secret"}):
            for path in ("/health", "/"):
                response = await protect_public_endpoints(make_request(path), call_next)
                self.assertEqual(response.status_code, 200, path)


if __name__ == "__main__":
    unittest.main()
