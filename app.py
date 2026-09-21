import os
from datetime import timedelta

from flask import redirect, url_for, request, session

from extensions import app
from services.auth_service import load_or_create_secret_key
from services.email_service import start_task_scheduler
from models.schema import init_all

app.config["SECRET_KEY"] = load_or_create_secret_key()
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Set SESSION_COOKIE_SECURE=1 when the application is served over HTTPS.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

# Endpoints reachable without signing in: the login page, static assets, and the public
# open-house visitor kiosk form.
PUBLIC_ENDPOINTS = {"login", "static", "signin"}


@app.before_request
def require_login():
    endpoint = request.endpoint
    if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
        return None
    if not session.get("logged_in"):
        return redirect(url_for("login", next=request.path))
    return None


@app.before_request
def ensure_task_scheduler():
    start_task_scheduler()


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    if not app.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Import routes so their view functions register on the shared app instance.
from routes import auth, main, agents, properties, open_houses, signin, contacts, tasks  # noqa: E402,F401

if __name__ == "__main__":
    init_all()
    port = int(os.environ.get("PORT", 8080))
    # Bound to localhost so the app (and its SQLite database) is not reachable from the network/internet.
    # Set FLASK_DEBUG=1 only for local development; never enable debug mode on a shared/public host.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
   # app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=debug_mode)

app.run(host= "0.0.0.0", port=port, debug=debug_mode)