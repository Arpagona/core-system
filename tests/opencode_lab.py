import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from console import Console
from opencode_lab import OpenCodeLab, verify_proposal


def event(expression):
    return json.dumps({"type": "text", "part": {"text": expression}})


class OpenCodeLabTest(unittest.TestCase):
    def test_wrong_arithmetic_and_unexpected_output(self):
        self.assertEqual(verify_proposal(event("quantity + unit_price"))["state"], "failed")
        with self.assertRaises(ValueError):
            verify_proposal(event("print(quantity)"))

    def test_launch_requires_token_and_returns_diff_and_tests(self):
        lab = OpenCodeLab(None, None, None)
        started = threading.Event()
        finish = threading.Event()

        def propose():
            started.set()
            finish.wait(3)
            return event("quantity * unit_price")

        with (
            patch.object(lab, "configured", return_value=True),
            patch.object(lab, "request", side_effect=propose),
            ThreadingHTTPServer(("127.0.0.1", 0), Console) as server,
        ):
            server.token = "token"
            server.opencode_lab = lab
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            url = f"http://127.0.0.1:{server.server_port}/api/opencode-lab"
            headers = {"Content-Type": "application/json", "X-Console-Token": "token"}

            def get():
                with urlopen(url, timeout=3) as response:
                    return json.load(response)

            def post(data, request_headers):
                with urlopen(Request(url, data, request_headers), timeout=3) as response:
                    return response.status

            try:
                with self.assertRaises(HTTPError) as denied:
                    post(b"{}", {"Content-Type": "application/json"})
                self.assertEqual(denied.exception.code, 403)
                denied.exception.close()
                with self.assertRaises(HTTPError) as invalid:
                    post(b'{"goal":"autre consigne"}', headers)
                self.assertEqual(invalid.exception.code, 400)
                invalid.exception.close()
                self.assertEqual(post(b"{}", headers), 202)
                self.assertTrue(started.wait(3))
                self.assertEqual(get()["state"], "running")
                with self.assertRaises(HTTPError) as conflict:
                    post(b"{}", headers)
                self.assertEqual(conflict.exception.code, 409)
                conflict.exception.close()
                finish.set()
                deadline = time.monotonic() + 3
                while (result := get())["state"] == "running" and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(result["state"], "passed")
                self.assertIn("+    return quantity * unit_price", result["diff"])
                self.assertEqual(len(result["tests"]), 3)
                self.assertTrue(all(test["passed"] for test in result["tests"]))
            finally:
                finish.set()
                server.shutdown()
                server_thread.join()


if __name__ == "__main__":
    unittest.main()
