from flask import render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

from extensions import app
from services.auth_service import (
    ADMIN_USERNAME, ADMIN_PASSWORD_HASH,
    is_locked_out, register_failed_login, clear_failed_logins,
)


def _client_ip():
    return request.remote_addr or "unknown"


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        ip = _client_ip()
        remaining_lockout = is_locked_out(ip)
        if remaining_lockout:
            error = f"Too many failed attempts. Try again in {remaining_lockout} seconds."
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
                clear_failed_logins(ip)
                session.clear()
                session["logged_in"] = True
                session["username"] = username
                session.permanent = True
                next_url = request.args.get("next") or request.form.get("next")
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect(url_for("dashboard"))
            register_failed_login(ip)
            error = "Invalid username or password."

    return render_template("login.html", error=error, next=request.args.get("next", ""))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))
