from datetime import datetime

from flask import request, redirect, url_for, render_template

from extensions import app
from models.homes import list_homes_brief, set_home_current
from models.agents import list_agents_with_brokerage
from models.open_houses import (
    list_open_houses_detailed, delete_open_house, insert_open_house, update_open_house,
    mark_completed_open_houses,
)


@app.route("/generate-open-house", methods=["GET", "POST"])
def generate_open_house():
    if request.method == "POST":
        action = request.form.get("action", "new")
        open_house_id = request.form.get("open_house_id", type=int)

        if action == "delete" and open_house_id:
            delete_open_house(open_house_id)
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

        if action == "update":
            if not update_open_house(fields, open_house_id):
                return "Open house not found.", 404
            saved_action = "updated"
        else:
            insert_open_house(fields)
            saved_action = "created"

        is_current = "1" in request.form.getlist("is_current")
        if not set_home_current(fields[0], is_current):
            return "Selected home was not found; current-home status was not updated.", 400
        return redirect(url_for("generate_open_house", saved=saved_action))

    homes = list_homes_brief()
    agents = [
        {"id": row[0], "first_name": row[1], "middle_name": row[2], "last_name": row[3], "brokerage": row[4]}
        for row in list_agents_with_brokerage()
    ]
    now = datetime.now()
    mark_completed_open_houses(now)
    open_houses = list_open_houses_detailed()

    return render_template(
        "GenerateOH.html",
        homes=homes,
        agents=agents,
        open_houses=open_houses,
        saved=request.args.get("saved"),
    )
