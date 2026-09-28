from flask import request, redirect, url_for, render_template

from extensions import app
from models.contacts import (
    FIELDS as CONTACT_FIELDS, archive_contact, get_contact as get_contact_record,
    insert_contact as insert_contact_record, list_contacts as list_contact_records,
    update_contact as update_contact_record,
)
from models.signins import (
    get_scoring_fields, get_full_scoring_fields, update_notes, get_contact_carryover_agent,
    mark_as_contact, get_email_and_followup, get_email,
)
from models.agents import list_agents_brief
from services.scoring import categorize_and_score
from services.email_service import send_email


CONTACT_FORM_SECTIONS = (
    ("Contact and lead", (
        ("FirstName", "First Name", "text"), ("LastName", "Last Name", "text"),
        ("Email", "Email", "email"), ("Phone", "Phone", "tel"),
        ("SecondaryPhone", "Secondary Phone", "tel"),
        ("PreferredContactMethod", "Preferred Contact Method", "text"),
        ("LeadSource", "Lead Source", "text"), ("CampaignID", "Campaign ID", "text"),
        ("ReferralName", "Referral Name", "text"), ("ReferralType", "Referral Type", "text"),
        ("InitialContactDate", "Initial Contact Date", "date"), ("LeadStatus", "Lead Status", "text"),
        ("LeadScore", "Lead Score", "number"), ("LastContactDate", "Last Contact Date", "date"),
        ("NextFollowUpDate", "Next Follow-Up Date", "date"),
        ("AssignedAgentID", "Assigned Agent", "agent"),
        ("PriorityLevel", "Priority Level", "text"),
    )),
    ("Property preferences", (
        ("DesiredCity", "Desired City", "text"), ("DesiredNeighborhood", "Desired Neighborhood", "text"),
        ("DesiredZipCode", "Desired Zip Code", "text"), ("PropertyType", "Property Type", "text"),
        ("BedsMin", "Minimum Beds", "number"), ("BathsMin", "Minimum Baths", "number"),
        ("SqFtMin", "Minimum Square Feet", "number"), ("BudgetMin", "Minimum Budget", "number"),
        ("BudgetMax", "Maximum Budget", "number"), ("PreApproved", "Pre-Approved", "checkbox"),
        ("LenderName", "Lender Name", "text"), ("PreApprovalAmount", "Pre-Approval Amount", "number"),
    )),
    ("Property and selling", (
        ("PropertyAddress", "Property Address", "text"), ("City", "City", "text"),
        ("State", "State", "text"), ("ZipCode", "Zip Code", "text"),
        ("EstimatedHomeValue", "Estimated Home Value", "number"),
        ("ReasonForSelling", "Reason for Selling", "textarea"),
        ("TimelineToSell", "Timeline to Sell", "text"),
    )),
    ("Activity and ownership", (
        ("Notes", "Notes", "textarea"),
        ("LastCommunicationType", "Last Communication Type", "text"),
        ("LastCommunicationSummary", "Last Communication Summary", "textarea"),
        ("NumberOfTouches", "Number of Touches", "number"), ("Tags", "Tags", "text"),
        ("CreatedByUserID", "Created By User ID", "number"),
        ("LeadOwnerTeamID", "Lead Owner Team ID", "text"),
        ("IsArchived", "Archived", "checkbox"), ("IsConverted", "Converted", "checkbox"),
        ("ConvertedDate", "Converted Date", "date"),
        ("ConvertedToContactID", "Converted To Contact ID", "number"),
        ("LeadPhotoURL", "Lead Photo URL", "url"), ("SocialMediaLinks", "Social Media Links", "textarea"),
    )),
)

INTEGER_FIELDS = {
    "LeadScore", "BedsMin", "SqFtMin", "NumberOfTouches", "CreatedByUserID", "AssignedAgentID", "IsArchived",
    "IsConverted", "ConvertedToContactID",
}
DECIMAL_FIELDS = {"BathsMin", "BudgetMin", "BudgetMax", "PreApprovalAmount", "EstimatedHomeValue"}
CHECKBOX_FIELDS = {"PreApproved", "IsArchived", "IsConverted"}
CONTACT_DISPLAY_GROUPS = (
    ("Identity and contact information", {
        "FirstName", "LastName", "Email", "Phone", "SecondaryPhone", "PreferredContactMethod",
    }),
    ("Customer Profile", {
        "DesiredCity", "DesiredNeighborhood", "DesiredZipCode", "PropertyType", "BedsMin",
        "BathsMin", "SqFtMin", "BudgetMin", "BudgetMax", "PreApproved", "LenderName",
        "PreApprovalAmount", "PropertyAddress", "City", "State", "ZipCode",
        "EstimatedHomeValue", "ReasonForSelling", "TimelineToSell",
    }),
    ("Lead and Marketing", set(CONTACT_FIELDS) - {
        "FirstName", "LastName", "Email", "Phone", "SecondaryPhone", "PreferredContactMethod",
        "DesiredCity", "DesiredNeighborhood", "DesiredZipCode", "PropertyType", "BedsMin",
        "BathsMin", "SqFtMin", "BudgetMin", "BudgetMax", "PreApproved", "LenderName",
        "PreApprovalAmount", "PropertyAddress", "City", "State", "ZipCode",
        "EstimatedHomeValue", "ReasonForSelling", "TimelineToSell",
    }),
)


def contact_display_groups(row):
    field_labels = {
        name: label
        for _, fields in CONTACT_FORM_SECTIONS
        for name, label, _ in fields
    }
    field_labels.update({
        "LeadID": "Lead ID",
        "LeadCreatedAt": "Lead Created At",
        "UpdatedAt": "Updated At",
    })
    groups = []
    for title, field_names in CONTACT_DISPLAY_GROUPS:
        fields = []
        for name, label in field_labels.items():
            if name not in field_names and name not in {"LeadID", "LeadCreatedAt", "UpdatedAt"}:
                continue
            if name in {"LeadID", "LeadCreatedAt", "UpdatedAt"} and title != "Lead and Marketing":
                continue
            value = row.get(name)
            if name in CHECKBOX_FIELDS:
                value = "Yes" if value else "No"
            elif value in (None, ""):
                value = "Not set"
            fields.append({"label": label, "value": value})
        groups.append({"title": title, "fields": fields})
    return groups


def contact_form_values():
    values = {}
    for field in CONTACT_FIELDS:
        raw = request.form.get(field, "").strip()
        if field in CHECKBOX_FIELDS:
            values[field] = 1 if raw in ("on", "1", "true") else 0
        elif field in INTEGER_FIELDS:
            values[field] = int(raw) if raw else None
        elif field in DECIMAL_FIELDS:
            values[field] = float(raw) if raw else None
        else:
            values[field] = raw or None
    return values


def contact_agent_options():
    return [
        {
            "id": row[0],
            "name": " ".join(part for part in row[1:4] if part).strip() or "Unnamed Agent",
        }
        for row in list_agents_brief()
    ]


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
        contact = {field: "" for field in CONTACT_FIELDS}
        contact.update(LeadStatus="New", IsArchived=0, IsConverted=0, NumberOfTouches=0)
        return render_template(
            "edit_contact.html", contact=contact, is_new=True,
            form_sections=CONTACT_FORM_SECTIONS, agents=contact_agent_options(),
        )

    values = contact_form_values()
    if not values["FirstName"] or not values["LastName"]:
        return "First and last name are required.", 400
    insert_contact_record(values)
    return redirect(url_for("contacts"))


@app.route("/contacts/delete/<int:signin_id>", methods=["POST"])
def delete_contact(signin_id):
    archive_contact(signin_id)
    return redirect(url_for("contacts"))


@app.route("/contacts")
def contacts():
    contacts_list = [
        {
            "id": row["LeadID"],
            "first_name": row["FirstName"],
            "last_name": row["LastName"],
            "name": " ".join(part for part in (row["FirstName"], row["LastName"]) if part),
            "email": row["Email"],
            "phone": row["Phone"],
            "alternate_phone": row["SecondaryPhone"],
            "preferred_contact_method": row["PreferredContactMethod"],
            "best_time_to_contact": "Not set",
            "lead_status": row["LeadStatus"],
            "visitor_type": row["LeadSource"] or "Lead",
            "currently": "Not set",
            "property_type": row["PropertyType"],
            "bedrooms": row["BedsMin"],
            "preferred_areas": ", ".join(part for part in (row["DesiredNeighborhood"], row["DesiredCity"]) if part),
            "working_with_broker": "Not set",
            "zip_code": row["DesiredZipCode"] or row["ZipCode"],
            "heard_about_us": row["LeadSource"],
            "timeline": row["TimelineToSell"],
            "preapproval": "Yes" if row["PreApproved"] else "No",
            "notes": row["Notes"],
            "motivation_score": row["LeadScore"] or 0,
            "followup_message": row["LastCommunicationSummary"],
            "next_steps": [],
            "created_at": row["LeadCreatedAt"],
            "agent_name": " ".join(part for part in (row["agent_first_name"], row["agent_middle_name"], row["agent_last_name"]) if part) or None,
            "field_groups": contact_display_groups(row),
        }
        for row in list_contact_records()
    ]
    edit_id = request.args.get("edit", type=int)
    edit_contact_data = next((contact for contact in contacts_list if contact["id"] == edit_id), None)
    return render_template("Contacts.html", contacts=contacts_list, edit_contact=edit_contact_data)


@app.route("/contacts/<int:signin_id>", methods=["GET", "POST"])
def edit_contact(signin_id):
    if request.method == "POST":
        if not get_contact_record(signin_id):
            return "Contact not found.", 404
        values = contact_form_values()
        if not values["FirstName"] or not values["LastName"]:
            return "First and last name are required.", 400
        update_contact_record(signin_id, values)
        return redirect(url_for("contacts"))

    contact = get_contact_record(signin_id)
    if not contact:
        return "Sign-in record not found.", 404
    return render_template(
        "edit_contact.html", contact=contact, is_new=False,
        form_sections=CONTACT_FORM_SECTIONS, agents=contact_agent_options(),
    )


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
