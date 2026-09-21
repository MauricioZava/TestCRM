from flask import request, redirect, url_for, render_template

from extensions import app
from models.signins import insert_signin, hide_signin
from models.open_houses import get_scheduled_agent, get_next_scheduled_brief, get_next_scheduled
from services.scoring import categorize_and_score


@app.route("/delete_signin/<int:signin_id>")
def delete_signin(signin_id):
    hide_signin(signin_id)
    return redirect(url_for("dashboard"))


@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        alternate_phone = request.form.get("alternate_phone", "").strip()
        visitor_type = request.form.get("visitor_type", "").strip()
        currently = request.form.get("currently", "").strip()
        property_type = request.form.get("property_type", "").strip()
        bedrooms = request.form.get("bedrooms", "").strip()
        preferred_areas = request.form.get("preferred_areas", "").strip()
        working_with_broker = "yes" if request.form.get("working_with_broker") == "yes" else "no"
        zip_code = request.form.get("zip_code", "").strip()
        heard_about_us = request.form.get("heard_about_us", "").strip()
        timeline = request.form.get("timeline", "").strip()
        preapproval = request.form.get("preapproval", "").strip()
        notes = request.form.get("notes", "").strip()
        submitted_agent_id = request.form.get("agent_id", type=int)
        submitted_open_house_id = request.form.get("open_house_id", type=int)

        motivation_score, followup_message, next_steps_json = categorize_and_score(
            visitor_type, timeline, preapproval, notes, currently
        )

        open_house_id = submitted_open_house_id
        agent_id = None
        if open_house_id:
            selected_open_house = get_scheduled_agent(open_house_id)
            if selected_open_house:
                agent_id = selected_open_house[0]
            else:
                open_house_id = None

        if not open_house_id:
            open_house_row = get_next_scheduled_brief()
            if open_house_row:
                open_house_id, agent_id = open_house_row

        agent_id = agent_id or submitted_agent_id

        insert_signin((
            first_name, last_name, email, phone, alternate_phone, visitor_type, currently, property_type, bedrooms, preferred_areas, working_with_broker,
            zip_code, heard_about_us, timeline, preapproval, notes, agent_id, open_house_id,
            motivation_score, followup_message, next_steps_json
        ))

        return redirect(url_for("dashboard"))

    row = get_next_scheduled()

    open_house = None
    if row:
        agent_name = " ".join(part for part in row[8:11] if part)
        open_house = {
            "id": row[0],
            "date": row[1],
            "time": f"{row[2]} - {row[3]}",
            "address": f"{row[4]}, {row[5]}, {row[6]} {row[7]}",
            "agent_name": agent_name,
            "agent_id": row[11] if len(row) > 11 else None,
        }

    return render_template("signin.html", open_house=open_house)
