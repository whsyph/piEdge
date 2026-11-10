"""Operator login for the CMS: a password (scrypt hash) exchanged for signed, expiring sessions.

Files live next to server.py and are only readable by the service user (mode 0600):
  .cms_password  scrypt hash record of the operator password
  .cms_secret    HMAC key that signs session tokens; replacing it logs every session out

Nothing here holds state in memory that matters: a restart keeps sessions valid, and the
CLI (`server.py --set-password`) can change the password while the service is running
because both files are re-read when their modification time changes.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128
SESSION_SECONDS = 7 * 24 * 3600
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}

# Lockout per client address: after FREE_ATTEMPTS wrong passwords, wait LOCK_BASE seconds,
# doubling for every further FREE_ATTEMPTS failures, up to LOCK_MAX.
FREE_ATTEMPTS = 5
LOCK_BASE = 60
LOCK_MAX = 15 * 60


class PasswordError(ValueError):
    """The new password does not meet the policy."""


def check_policy(password):
    if not isinstance(password, str):
        raise PasswordError("password must be text")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordError(f"password must be at most {MAX_PASSWORD_LENGTH} characters")


def _b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, dklen=32, **SCRYPT)
    return {"alg": "scrypt", **SCRYPT, "salt": _b64(salt), "hash": _b64(digest)}


def verify_hash(password, record):
    try:
        salt = _unb64(record["salt"])
        expected = _unb64(record["hash"])
        params = {k: int(record[k]) for k in ("n", "r", "p")}
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, dklen=len(expected), **params)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return hmac.compare_digest(digest, expected)


def _write_private(path, text):
    tmp = f"{path}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)


class AuthStore:
    def __init__(self, directory, clock=time.time):
        self.password_file = os.path.join(directory, ".cms_password")
        self.secret_file = os.path.join(directory, ".cms_secret")
        self.clock = clock
        self._lock = threading.Lock()
        self._cache = {}  # path -> (mtime_ns, value)
        self._failures = {}  # client -> [count, locked_until]

    # -- files ---------------------------------------------------------------------
    def _read(self, path, parse):
        try:
            stamp = os.stat(path).st_mtime_ns
        except OSError:
            self._cache.pop(path, None)
            return None
        cached = self._cache.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = parse(handle.read())
        except (OSError, ValueError):
            return None
        self._cache[path] = (stamp, value)
        return value

    def _record(self):
        return self._read(self.password_file, json.loads)

    def _secret(self):
        return self._read(self.secret_file, lambda text: bytes.fromhex(text.strip()))

    def password_set(self):
        record = self._record()
        return isinstance(record, dict) and "hash" in record

    def set_password(self, password):
        """Store a new password and replace the signing key, which ends all existing sessions."""
        check_policy(password)
        with self._lock:
            _write_private(self.password_file, json.dumps(hash_password(password)))
            _write_private(self.secret_file, secrets.token_hex(32) + "\n")
            self._failures.clear()

    # -- sessions --------------------------------------------------------------------
    def issue_session(self):
        secret = self._secret()
        if not secret:
            with self._lock:
                if not self._secret():
                    _write_private(self.secret_file, secrets.token_hex(32) + "\n")
            secret = self._secret()
        payload = _b64(json.dumps({"exp": int(self.clock()) + SESSION_SECONDS}).encode("utf-8"))
        signature = _b64(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
        return f"{payload}.{signature}"

    def valid_session(self, token):
        secret = self._secret()
        if not secret or not isinstance(token, str) or token.count(".") != 1:
            return False
        payload, signature = token.split(".")
        good = _b64(hmac.new(secret, payload.encode("ascii", "ignore"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature.encode("ascii", "ignore"), good.encode("ascii")):
            return False
        try:
            return int(json.loads(_unb64(payload))["exp"]) > self.clock()
        except (KeyError, TypeError, ValueError):
            return False

    # -- login with lockout ------------------------------------------------------------
    def retry_after(self, client):
        """Seconds the client still has to wait before another attempt (0 = may try)."""
        with self._lock:
            entry = self._failures.get(client)
            return max(0, int(entry[1] - self.clock() + 0.999)) if entry else 0

    def _fail(self, client):
        with self._lock:
            count, _ = self._failures.get(client, (0, 0))
            count += 1
            locked_until = 0
            if count % FREE_ATTEMPTS == 0:
                steps = count // FREE_ATTEMPTS - 1
                locked_until = self.clock() + min(LOCK_MAX, LOCK_BASE * (2 ** steps))
            self._failures[client] = [count, locked_until]
            if len(self._failures) > 1000:  # bounded memory under address spraying
                oldest = sorted(self._failures, key=lambda c: self._failures[c][1])[:200]
                for key in oldest:
                    self._failures.pop(key, None)

    def check_login(self, client, password):
        """Returns ('ok', session) | ('locked', seconds) | ('wrong', None) | ('unset', None)."""
        wait = self.retry_after(client)
        if wait:
            return "locked", wait
        record = self._record()
        if not isinstance(record, dict):
            return "unset", None
        if isinstance(password, str) and len(password) <= MAX_PASSWORD_LENGTH and verify_hash(password, record):
            with self._lock:
                self._failures.pop(client, None)
            return "ok", self.issue_session()
        self._fail(client)
        wait = self.retry_after(client)
        return ("locked", wait) if wait else ("wrong", None)
