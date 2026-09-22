from flask import request, redirect, url_for, render_template

from extensions import app
from models.brokers import FIELDS, list_brokers, insert_broker, update_broker, delete_broker


@app.route("/brokers", methods=["GET", "POST"])
def brokers():
    if request.method == "POST":
        action = request.form.get("action", "add")
        broker_id = request.form.get("broker_id")

        if action == "delete" and broker_id:
            delete_broker(broker_id)
            return redirect(url_for("brokers"))

        if action in ("update", "delete") and not broker_id:
            return redirect(url_for("brokers"))

        fields = [request.form.get(name, "").strip() for name in FIELDS]
        if not fields[0]:
            return "Brokerage name is required.", 400

        if action == "update":
            update_broker(fields, broker_id)
        else:
            insert_broker(fields)
        return redirect(url_for("brokers"))

    return render_template("brokers.html", brokers=list_brokers())