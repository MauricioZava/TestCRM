import os
import secrets
import threading
import time

from werkzeug.security import generate_password_hash

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY_FILE = os.path.join(APP_DIR, ".secret_key")

# Temporary login credentials — override with ADMIN_USERNAME / ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH)
# environment variables before deploying anywhere other than your own machine.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Maury")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH") or generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "Maury")
)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300
_login_attempts = {}
_login_attempts_lock = threading.Lock()


def load_or_create_secret_key():
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, "r", encoding="utf-8") as key_file:
            existing = key_file.read().strip()
            if existing:
                return existing
    new_key = secrets.token_hex(32)
    with open(SECRET_KEY_FILE, "w", encoding="utf-8") as key_file:
        key_file.write(new_key)
    return new_key


def is_locked_out(ip):
    with _login_attempts_lock:
        record = _login_attempts.get(ip)
        if not record:
            return 0
        if record["count"] >= MAX_LOGIN_ATTEMPTS and time.time() < record["locked_until"]:
            return int(record["locked_until"] - time.time())
        return 0


def register_failed_login(ip):
    with _login_attempts_lock:
        record = _login_attempts.setdefault(ip, {"count": 0, "locked_until": 0})
        record["count"] += 1
        if record["count"] >= MAX_LOGIN_ATTEMPTS:
            record["locked_until"] = time.time() + LOGIN_LOCKOUT_SECONDS


def clear_failed_logins(ip):
    with _login_attempts_lock:
        _login_attempts.pop(ip, None)
