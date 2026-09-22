import json

from flask import request, redirect, url_for, render_template

from extensions import app
from models.signins import (
    get_scoring_fields, get_full_scoring_fields, update_notes, get_contact_carryover_agent,
    mark_as_contact, insert_contact, soft_delete_contact, list_contacts, get_contact,
    update_contact, get_email_and_followup, get_email,
)
from models.agents import list_agents_brief
from services.scoring import categorize_and_score
from services.email_service import send_email


@app.route("/contacts/<int:signin_id>/notes", methods=["POST"])
def update_contact_notes(signin_id):
    notes = request.form.get("notes", "").strip()
    row = get_scoring_fields(signin_id)

    if not row:
        return "Sign-in record not found.", 404

    visitor_type, timeline, preapproval, currently = row
    motivation_score, followup_message, next_steps_json = categorize_and_score(
        visitor_type, timeline, preapproval, notes, currently
    )
    update_notes(signin_id, notes, motivation_score, followup_message, next_steps_json)
    return redirect(url_for("dashboard"))


@app.route("/contacts/add/<int:signin_id>", methods=["POST"])
def add_contact(signin_id):
    row = get_full_scoring_fields(signin_id)
    if not row:
        return "Sign-in record not found.", 404

    visitor_type, timeline, preapproval, currently, notes = row
    motivation_score, followup_message, next_steps_json = categorize_and_score(
        visitor_type, timeline, preapproval, notes, currently
    )
    agent_row = get_contact_carryover_agent(signin_id)
    agent_id = agent_row[0] if agent_row else None

    mark_as_contact(signin_id, motivation_score, followup_message, next_steps_json, agent_id)
    return redirect(url_for("dashboard"))


@app.route("/contacts/new", methods=["GET", "POST"])
def create_contact():
    if request.method == "GET":
        thank_you_message = """Hi,

Thank you so much for visiting the open house today. It was a pleasure having you stop by, and I truly appreciate you taking the time to explore the property.

If you have any questions about the home, would like additional details, or want to schedule a private showing, feel free to reach out anytime. I'm here to help with anything you need.

Looking forward to connecting with you.

Warm regards,"""
        contact = {
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
            "alternate_phone": "",
            "preferred_contact_method": "email",
            "best_time_to_contact": "anytime",
            "lead_status": "new",
            "visitor_type": "buyer",
            "currently": "renting",
            "property_type": "single-family",
            "bedrooms": "",
            "preferred_areas": "",
            "working_with_broker": "no",
            "zip_code": "",
            "heard_about_us": "",
            "timeline": "browsing",
            "preapproval": "unknown",
            "notes": thank_you_message,
            "agent_id": None,
        }
        return render_template("edit_contact.html", contact=contact, is_new=True, agents=list_agents_brief())

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    alternate_phone = request.form.get("alternate_phone", "").strip()
    preferred_contact_method = request.form.get("preferred_contact_method", "email").strip()
    best_time_to_contact = request.form.get("best_time_to_contact", "anytime").strip()
    lead_status = request.form.get("lead_status", "new").strip()
    visitor_type = request.form.get("visitor_type", "buyer").strip()
    currently = request.form.get("currently", "renting").strip()
    property_type = request.form.get("property_type", "").strip()
    bedrooms = request.form.get("bedrooms", "").strip()
    preferred_areas = request.form.get("preferred_areas", "").strip()
    working_with_broker = "yes" if request.form.get("working_with_broker") == "yes" else "no"
    zip_code = request.form.get("zip_code", "").strip()
    heard_about_us = request.form.get("heard_about_us", "").strip()
    timeline = request.form.get("timeline", "browsing").strip()
    preapproval = request.form.get("preapproval", "unknown").strip()
    notes = request.form.get("notes", "").strip()
    agent_id = request.form.get("agent_id", type=int)

    motivation_score, followup_message, next_steps_json = categorize_and_score(
        visitor_type, timeline, preapproval, notes, currently
    )

    insert_contact((
        first_name, last_name, email, phone, alternate_phone, preferred_contact_method, best_time_to_contact, lead_status,
        visitor_type, currently, property_type, bedrooms, preferred_areas, working_with_broker,
        zip_code, heard_about_us, timeline, preapproval, notes,
        motivation_score, followup_message, next_steps_json, agent_id
    ))
    return redirect(url_for("contacts"))


@app.route("/contacts/delete/<int:signin_id>", methods=["POST"])
def delete_contact(signin_id):
    soft_delete_contact(signin_id)
    return redirect(url_for("contacts"))


@app.route("/contacts")
def contacts():
    rows = list_contacts()

    contacts_list = [
        {
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "name": " ".join(part for part in (row[1], row[2]) if part),
            "email": row[3],
            "phone": row[4],
            "alternate_phone": row[5],
            "preferred_contact_method": row[6],
            "best_time_to_contact": row[7],
            "lead_status": row[8],
            "visitor_type": row[9],
            "currently": row[10],
            "property_type": row[11],
            "bedrooms": row[12],
            "preferred_areas": row[13],
            "working_with_broker": row[14],
            "zip_code": row[15],
            "heard_about_us": row[16],
            "timeline": row[17],
            "preapproval": row[18],
            "notes": row[19],
            "motivation_score": row[20],
            "followup_message": row[21],
            "next_steps": json.loads(row[22] or "[]"),
            "created_at": row[23],
            "agent_name": " ".join(part for part in row[24:27] if part) or None,
        }
        for row in rows
    ]
    edit_id = request.args.get("edit", type=int)
    edit_contact_data = next((contact for contact in contacts_list if contact["id"] == edit_id), None)
    return render_template("Contacts.html", contacts=contacts_list, edit_contact=edit_contact_data)


@app.route("/contacts/<int:signin_id>", methods=["GET", "POST"])
def edit_contact(signin_id):
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        alternate_phone = request.form.get("alternate_phone", "").strip()
        preferred_contact_method = request.form.get("preferred_contact_method", "email").strip()
        best_time_to_contact = request.form.get("best_time_to_contact", "anytime").strip()
        lead_status = request.form.get("lead_status", "new").strip()
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
        agent_id = request.form.get("agent_id", type=int)

        motivation_score, followup_message, next_steps_json = categorize_and_score(
            visitor_type, timeline, preapproval, notes, currently
        )
        update_contact(signin_id, (
            first_name, last_name, email, phone, alternate_phone, preferred_contact_method, best_time_to_contact, lead_status,
            visitor_type, currently, property_type, bedrooms, preferred_areas,
            working_with_broker, zip_code, heard_about_us,
            timeline, preapproval,
            notes, motivation_score, followup_message, next_steps_json, agent_id
        ))
        return redirect(url_for("contacts"))

    row = get_contact(signin_id)
    if not row:
        return "Sign-in record not found.", 404

    contact = {
        "id": row[0],
        "first_name": row[1] or "",
        "last_name": row[2] or "",
        "email": row[3] or "",
        "phone": row[4] or "",
        "alternate_phone": row[5] or "",
        "preferred_contact_method": row[6] or "email",
        "best_time_to_contact": row[7] or "anytime",
        "lead_status": row[8] or "new",
        "visitor_type": row[9],
        "currently": row[10],
        "property_type": row[11] or "",
        "bedrooms": row[12] or "",
        "preferred_areas": row[13] or "",
        "working_with_broker": row[14] or "no",
        "zip_code": row[15] or "",
        "heard_about_us": row[16] or "",
        "timeline": row[17],
        "preapproval": row[18],
        "notes": row[19],
        "agent_id": row[20],
    }
    return render_template("edit_contact.html", contact=contact, is_new=False, agents=list_agents_brief())


@app.route("/send_email/<int:signin_id>")
def send_email_from_dashboard(signin_id):
    row = get_email_and_followup(signin_id)

    if not row:
        return "Sign-in record not found."

    email, followup_message = row

    if not email:
        return "This visitor did not provide an email address."

    send_email(email, "Thank You for Visiting the Open House", followup_message)

    return redirect(url_for("contacts"))


@app.route("/send_custom_email/<int:signin_id>", methods=["POST"])
def send_custom_email(signin_id):
    subject = request.form.get("subject", "Open House Follow-Up").strip()
    body = request.form.get("body", "").strip()

    if not body:
        return "Email message cannot be empty.", 400

    row = get_email(signin_id)

    if not row:
        return "Sign-in record not found.", 404
    if not row[0]:
        return "This visitor did not provide an email address.", 400

    send_email(row[0], subject or "Open House Follow-Up", body)
    return redirect(url_for("contacts"))
