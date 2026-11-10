"""Operator password: hashing, signed sessions, lockout, and the HTTP login flow."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cms_auth  # noqa: E402
import server  # noqa: E402

LEGACY_TOKEN = "legacy-token-" + "x" * 20


class FakeClock:
    def __init__(self, now=1_800_000_000):
        self.now = now

    def __call__(self):
        return self.now


class AuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.store = cms_auth.AuthStore(self.tmp.name, clock=self.clock)

    def test_policy(self):
        for bad in ("", "12345", "x" * 129, None, 123456, b"secret1"):
            with self.assertRaises(cms_auth.PasswordError, msg=repr(bad)):
                cms_auth.check_policy(bad)
        cms_auth.check_policy("123456")
        cms_auth.check_policy("kata sandi panjang dengan spasi")

    def test_hash_is_salted_and_verifies_only_the_right_password(self):
        a, b = cms_auth.hash_password("rahasia1"), cms_auth.hash_password("rahasia1")
        self.assertNotEqual(a["salt"], b["salt"])
        self.assertNotEqual(a["hash"], b["hash"])
        self.assertTrue(cms_auth.verify_hash("rahasia1", a))
        self.assertFalse(cms_auth.verify_hash("rahasia2", a))
        self.assertFalse(cms_auth.verify_hash("rahasia1", {}))
        self.assertFalse(cms_auth.verify_hash("rahasia1", dict(a, hash="!!!")))
        self.assertNotIn("rahasia1", json.dumps(a))

    @unittest.skipIf(os.name == "nt", "POSIX file modes")
    def test_files_are_private(self):
        self.store.set_password("rahasia1")
        for name in (".cms_password", ".cms_secret"):
            self.assertEqual(os.stat(Path(self.tmp.name) / name).st_mode & 0o777, 0o600)

    def test_login_before_a_password_exists_is_reported(self):
        self.assertFalse(self.store.password_set())
        self.assertEqual(self.store.check_login("10.0.0.1", "whatever"), ("unset", None))

    def test_session_roundtrip_expiry_and_tampering(self):
        self.store.set_password("rahasia1")
        outcome, token = self.store.check_login("10.0.0.1", "rahasia1")
        self.assertEqual(outcome, "ok")
        self.assertTrue(self.store.valid_session(token))
        self.clock.now += cms_auth.SESSION_SECONDS - 5
        self.assertTrue(self.store.valid_session(token))
        self.clock.now += 10
        self.assertFalse(self.store.valid_session(token))  # expired
        self.clock.now -= 10
        payload, signature = token.split(".")
        forged = cms_auth._b64(json.dumps({"exp": self.clock.now + 10 ** 9}).encode()) + "." + signature
        for bad in (forged, payload, token + "x", "", "a.b.c", None, 5):
            self.assertFalse(self.store.valid_session(bad), repr(bad))

    def test_sessions_survive_a_restart_but_not_a_password_change(self):
        self.store.set_password("rahasia1")
        _, token = self.store.check_login("10.0.0.1", "rahasia1")
        restarted = cms_auth.AuthStore(self.tmp.name, clock=self.clock)
        self.assertTrue(restarted.valid_session(token))
        restarted.set_password("rahasia2")
        self.assertFalse(restarted.valid_session(token))
        self.assertFalse(self.store.valid_session(token))  # the running instance notices the new key
        self.assertEqual(self.store.check_login("10.0.0.1", "rahasia2")[0], "ok")

    def test_lockout_escalates_and_is_per_client(self):
        self.store.set_password("rahasia1")
        for _ in range(4):
            self.assertEqual(self.store.check_login("a", "nope"), ("wrong", None))
        self.assertEqual(self.store.check_login("a", "nope"), ("locked", 60))        # 5th failure
        self.assertEqual(self.store.check_login("a", "rahasia1")[0], "locked")       # even the right one waits
        self.assertEqual(self.store.check_login("b", "rahasia1")[0], "ok")           # another client is unaffected
        self.clock.now += 61
        for _ in range(4):
            self.assertEqual(self.store.check_login("a", "nope")[0], "wrong")
        self.assertEqual(self.store.check_login("a", "nope"), ("locked", 120))       # doubled
        self.clock.now += 121
        self.assertEqual(self.store.check_login("a", "rahasia1")[0], "ok")
        self.assertEqual(self.store.retry_after("a"), 0)                              # success clears the history
        for _ in range(4):
            self.store.check_login("a", "nope")
        self.assertEqual(self.store.check_login("a", "nope"), ("locked", 60))

    def test_oversized_or_non_text_passwords_are_just_wrong(self):
        self.store.set_password("rahasia1")
        for bad in ("x" * 100000, None, 123456, ["rahasia1"]):
            self.assertEqual(self.store.check_login("c", bad)[0], "wrong")
            self.clock.now += 10_000


class LoginHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        schedules = Path(self.tmp.name) / "schedules.json"
        schedules.write_text('{"events": []}', encoding="utf-8")
        self.store = cms_auth.AuthStore(self.tmp.name)
        for key, value in (("AUTH", self.store), ("TOKEN", LEGACY_TOKEN), ("SCHEDULES_FILE", str(schedules)),
                           ("CONFIG", dict(server.DEFAULT_CONFIG))):
            patch = unittest.mock.patch.object(server, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.SignageRequestHandler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        unittest.mock.patch.object(server.time, "sleep").start()  # skip the anti-guessing delays
        self.addCleanup(unittest.mock.patch.stopall)

    def call(self, method, path, body=None, token=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = dict(headers or {})
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=hdrs)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw
        return response.status, payload, dict(response.getheaders())

    def test_info_is_public_and_reports_whether_a_password_exists(self):
        self.assertEqual(self.call("GET", "/api/auth/info")[:2], (200, {"password_set": False}))
        self.store.set_password("rahasia1")
        self.assertEqual(self.call("GET", "/api/auth/info")[:2], (200, {"password_set": True}))

    def test_login_flow(self):
        self.assertEqual(self.call("POST", "/api/login", {"password": "rahasia1"})[0], 409)  # nothing set yet
        self.store.set_password("rahasia1")
        self.assertEqual(self.call("GET", "/api/schedule/config")[0], 401)
        self.assertEqual(self.call("POST", "/api/login", {"password": "salah"})[0], 401)
        self.assertEqual(self.call("POST", "/api/login", {})[0], 401)
        status, payload, _ = self.call("POST", "/api/login", {"password": "rahasia1"})
        self.assertEqual(status, 200)
        token = payload["token"]
        self.assertNotIn("rahasia1", json.dumps(payload))
        self.assertEqual(self.call("GET", "/api/schedule/config", token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/schedule/config", token=token + "x")[0], 401)
        self.assertEqual(self.call("GET", "/api/schedule/config", token=LEGACY_TOKEN)[0], 200)  # script/recovery key

    def test_login_input_validation_and_origin_rule(self):
        self.store.set_password("rahasia1")
        self.assertEqual(self.call("POST", "/api/login", [1, 2])[0], 400)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/login", body=b"password=rahasia1",
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(conn.getresponse().status, 415)
        conn.close()
        self.assertEqual(self.call("POST", "/api/login", {"password": "rahasia1"},
                                   headers={"Origin": "http://evil.example"})[0], 403)

    def test_repeated_failures_lock_the_client_out_with_retry_after(self):
        self.store.set_password("rahasia1")
        for _ in range(4):
            self.assertEqual(self.call("POST", "/api/login", {"password": "x"})[0], 401)
        status, payload, headers = self.call("POST", "/api/login", {"password": "x"})
        self.assertEqual(status, 429)
        self.assertGreater(payload["retry_after"], 0)
        self.assertEqual(headers["Retry-After"], str(payload["retry_after"]))
        self.assertEqual(self.call("POST", "/api/login", {"password": "rahasia1"})[0], 429)

    def test_change_password(self):
        self.store.set_password("rahasia1")
        _, payload, _ = self.call("POST", "/api/login", {"password": "rahasia1"})
        old = payload["token"]
        change = lambda body, token=old: self.call("POST", "/api/password/change", body, token=token)  # noqa: E731
        self.assertEqual(self.call("POST", "/api/password/change", {"current": "rahasia1", "new": "baru-123"})[0], 401)
        self.assertEqual(change({"current": "salah", "new": "baru-123"})[0], 403)
        self.assertEqual(change({"current": "rahasia1", "new": "pend"})[0], 400)
        self.assertEqual(change({"new": "baru-123"})[0], 403)  # the current password is mandatory once one exists
        status, payload, _ = change({"current": "rahasia1", "new": "baru-123"})
        self.assertEqual(status, 200)
        self.assertEqual(self.call("GET", "/api/schedule/config", token=old)[0], 401)             # old sessions are out
        self.assertEqual(self.call("GET", "/api/schedule/config", token=payload["token"])[0], 200)  # caller stays in
        self.assertEqual(self.call("POST", "/api/login", {"password": "rahasia1"})[0], 401)
        self.assertEqual(self.call("POST", "/api/login", {"password": "baru-123"})[0], 200)

    def test_token_holder_can_set_the_first_password(self):
        status, payload, _ = self.call("POST", "/api/password/change", {"new": "pertama-1"}, token=LEGACY_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(self.call("POST", "/api/login", {"password": "pertama-1"})[0], 200)
        self.assertEqual(self.call("GET", "/api/schedule/config", token=payload["token"])[0], 200)
        # without any credential nobody can claim the empty slot
        fresh = cms_auth.AuthStore(tempfile.mkdtemp())
        with unittest.mock.patch.object(server, "AUTH", fresh):
            self.assertEqual(self.call("POST", "/api/password/change", {"new": "diambil-1"})[0], 401)
            self.assertFalse(fresh.password_set())


class InstallerCoverageTests(unittest.TestCase):
    def test_install_script_copies_every_local_module_the_server_imports(self):
        import ast
        source = (ROOT / "server.py").read_text(encoding="utf-8")
        local = {f.stem for f in ROOT.glob("*.py")} - {"server"}
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        needed = sorted(imported & local)
        self.assertIn("cms_auth", needed)
        script = (ROOT / "install-cms.sh").read_text(encoding="utf-8")
        for module in needed:
            self.assertEqual(script.count(f"{module}.py"), 2,
                             f"install-cms.sh must check for and copy {module}.py")


if __name__ == "__main__":
    unittest.main()
