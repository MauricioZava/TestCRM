from datetime import datetime

from flask import request, redirect, url_for, render_template

from extensions import app
from models.homes import list_homes_brief
from models.signins import insert_signin, hide_signin
from models.open_houses import get_scheduled_agent, list_open_houses_detailed
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
        best_time_to_contact = request.form.get("best_time_to_contact", "").strip()
        contact_time_of_day = request.form.get("contact_time_of_day", "").strip()
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

        insert_signin((
            first_name, last_name, email, phone, alternate_phone, best_time_to_contact, contact_time_of_day, visitor_type, currently, property_type, bedrooms, preferred_areas, working_with_broker,
            zip_code, heard_about_us, timeline, preapproval, notes, agent_id, open_house_id,
            motivation_score, followup_message, next_steps_json
        ))

        return redirect(url_for("dashboard"))

    open_house = None
    current_home = next((home for home in list_homes_brief() if home["is_current"]), None)
    now = datetime.now()
    upcoming_open_houses = []
    for event in list_open_houses_detailed():
        if not current_home or event["home_id"] != current_home["id"]:
            continue
        if (event["status"] or "").strip().lower() != "scheduled":
            continue
        try:
            event_start = datetime.fromisoformat(f"{event['event_date']}T{event['start_time']}")
        except (TypeError, ValueError):
            continue
        if event_start > now:
            upcoming_open_houses.append((event_start, event))

    if upcoming_open_houses:
        _, event = min(upcoming_open_houses, key=lambda item: item[0])
        agent_name = " ".join(
            part for part in (event["agent_first_name"], event["agent_middle_name"], event["agent_last_name"]) if part
        )
        address_parts = (event["address"], event["city"], event["state"], event["zip_code"])
        open_house = {
            "id": event["id"],
            "date": event["event_date"],
            "time": f"{event['start_time']} - {event['end_time']}",
            "address": ", ".join(part for part in address_parts[:3] if part) + (f" {address_parts[3]}" if address_parts[3] else ""),
            "agent_name": agent_name,
            "agent_id": event["agent_id"],
        }
    elif current_home:
        address_parts = (current_home["address"], current_home["city"], current_home["state"], current_home["zip_code"])
        open_house = {
            "id": None,
            "date": None,
            "time": None,
            "address": ", ".join(part for part in address_parts[:3] if part) + (f" {address_parts[3]}" if address_parts[3] else ""),
            "agent_name": None,
            "agent_id": None,
        }

    return render_template("signin.html", open_house=open_house)
