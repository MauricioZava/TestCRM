from datetime import datetime

from flask import request, redirect, url_for, render_template

from extensions import app
from models.properties import list_homes_brief, set_open_house_active
from models.agents import list_agents_with_brokerage
from models.open_houses import (
    delete_open_house, insert_open_house, update_open_house, mark_completed_open_houses,
)


@app.route("/generate-open-house", methods=["GET", "POST"])
def generate_open_house():
    if request.method == "POST":
        action = request.form.get("action", "new")
        open_house_id = request.form.get("open_house_id", type=int)

        if action == "delete" and open_house_id:
            delete_open_house(open_house_id)
            return redirect(url_for("generate_open_house"))

        if action == "set_open_house_active":
            property_id = request.form.get("property_id", type=int)
            is_active = "1" in request.form.getlist("is_open_house_active")
            if not property_id or not set_open_house_active(property_id, is_active):
                return "Selected property was not found; open-house status was not updated.", 400
            return redirect(url_for("generate_open_house"))

        if action in ("update", "delete") and not open_house_id:
            return redirect(url_for("generate_open_house"))

        fields = [
            request.form.get(name, "").strip()
            for name in (
                "home_id", "agent_id", "event_date", "start_time", "end_time",
                "title", "status", "visitor_capacity", "rsvp_contact",
                "public_notes", "internal_notes"
            )
        ]

        if not fields[0] or not fields[1] or not fields[2] or not fields[3] or not fields[4]:
            return "Home, hosting agent, date, start time, and end time are required.", 400

        is_open_house_active = "1" in request.form.getlist("is_open_house_active")
        if not set_open_house_active(fields[0], is_open_house_active):
            return "Selected home was not found; open-house status was not updated.", 400

        if action == "update":
            if not update_open_house(fields, open_house_id):
                return "Open house not found.", 404
            saved_action = "updated"
        else:
            insert_open_house(fields)
            saved_action = "created"

        return redirect(url_for("generate_open_house", saved=saved_action))

    homes = list_homes_brief()
    agents = [
        {"id": row[0], "first_name": row[1], "middle_name": row[2], "last_name": row[3], "brokerage": row[4]}
        for row in list_agents_with_brokerage()
    ]
    now = datetime.now()
    mark_completed_open_houses(now)

    return render_template(
        "GenerateOH.html",
        homes=homes,
        agents=agents,
        saved=request.args.get("saved"),
    )
