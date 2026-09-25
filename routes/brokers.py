from flask import abort, request, redirect, url_for, render_template

from extensions import app
from models.brokers import FIELDS, list_brokers, insert_broker, update_broker, delete_broker


@app.route("/brokers")
def brokers():
    return render_template("brokers.html", brokers=list_brokers())


def broker_form_fields():
    values = {name: request.form.get(name, "").strip() for name in FIELDS}
    values["years_experience"] = request.form.get("years_experience", type=int)
    values["office_id"] = request.form.get("office_id", type=int)
    values["is_primary_broker"] = 1 if request.form.get("is_primary_broker") else 0
    return [values[name] for name in FIELDS]


def broker_form_data():
    broker = {name: "" for name in FIELDS}
    broker.update(status="Active", is_primary_broker=0)
    return broker


@app.route("/brokers/new", methods=["GET", "POST"])
def create_broker():
    if request.method == "POST":
        fields = broker_form_fields()
        if not fields[0]:
            return "Brokerage name is required.", 400
        insert_broker(fields)
        return redirect(url_for("brokers"))

    return render_template("new_broker.html", broker=broker_form_data(), is_edit=False)


@app.route("/brokers/<int:broker_id>/edit", methods=["GET", "POST"])
def edit_broker(broker_id):
    broker = next((item for item in list_brokers() if item["id"] == broker_id), None)
    if not broker:
        abort(404)

    if request.method == "POST":
        fields = broker_form_fields()
        if not fields[0]:
            return "Brokerage name is required.", 400
        update_broker(fields, broker_id)
        return redirect(url_for("brokers"))

    return render_template("new_broker.html", broker=broker, is_edit=True)


@app.route("/brokers/<int:broker_id>/delete", methods=["POST"])
def remove_broker(broker_id):
    delete_broker(broker_id)
    return redirect(url_for("brokers"))