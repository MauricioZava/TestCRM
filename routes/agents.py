from flask import request, redirect, url_for, render_template

from extensions import app
from models.agents import FIELDS, list_agents, get_agent, insert_agent, update_agent, delete_agent
from models.brokers import list_brokers


AGENT_FORM_SECTIONS = (
    ("Core Identity", (
        ("id", "Agent ID", "readonly"),
        ("status", "Status", "status"),
        ("first_name", "First Name", "text"),
        ("middle_name", "Middle Name", "text"),
        ("last_name", "Last Name", "text"),
    )),
    ("Contact Information", (
        ("email", "Email", "email"),
        ("phone", "Phone", "tel"),
        ("mobile_phone", "Mobile Phone", "tel"),
        ("office_phone", "Office Phone", "tel"),
    )),
    ("Brokerage & Office Relationships", (
        ("broker_id", "Broker", "broker"),
        ("office_id", "Office ID", "number"),
        ("team_id", "Team ID", "number"),
    )),
    ("Licensing & Professional", (
        ("license_number", "License Number", "text"),
        ("license_state", "License State", "text"),
        ("license_expiration_date", "License Expiration Date", "date"),
        ("mls_id", "MLS ID", "text"),
        ("nrds_id", "NRDS ID", "text"),
        ("agent_type", "Agent Type", "text"),
        ("years_experience", "Years Experience", "number"),
        ("preferred_contact_method", "Preferred Contact Method", "text"),
    )),
    ("System Metadata", (
        ("created_at", "Created At", "readonly"),
        ("updated_at", "Updated At", "readonly"),
    )),
    ("Office Location", (
        ("office_address", "Office Address", "text"),
        ("city", "City", "text"),
        ("state", "State", "text"),
        ("zip_code", "Zip Code", "text"),
    )),
    ("Specializations & Tags", (
        ("specialties", "Specialties", "text"),
        ("agent_tags", "Agent Tags", "text"),
    )),
    ("Online Presence", (
        ("social_media_links", "Social Media Links", "textarea"),
        ("x_com_profile", "X.com Profile", "url"),
        ("profile_photo_url", "Photo URL", "url"),
        ("website", "Website", "url"),
    )),
    ("Notes", (("notes", "Notes", "textarea"),)),
)


def agent_form_fields():
    values = {name: request.form.get(name, "").strip() for name in FIELDS}
    for name in ("broker_id", "office_id", "team_id", "years_experience"):
        values[name] = request.form.get(name, type=int)
    return [values[name] for name in FIELDS]


@app.route("/agents")
def agents():
    return render_template("agents.html", agents=list_agents())


@app.route("/agents/new", methods=["GET", "POST"])
def create_agent():
    if request.method == "GET":
        agent = {field: "" for field in FIELDS}
        agent.update(name="", status="Active")
        return render_template(
            "edit_agent.html", agent=agent, brokers=list_brokers(),
            form_sections=AGENT_FORM_SECTIONS, is_new=True,
        )

    fields = agent_form_fields()
    if not fields[FIELDS.index("first_name")] or not fields[FIELDS.index("last_name")]:
        return "First name and last name are required.", 400
    insert_agent(fields)
    return redirect(url_for("agents"))


@app.route("/agents/<int:agent_id>", methods=["GET", "POST"])
def edit_agent(agent_id):
    if request.method == "POST":
        fields = agent_form_fields()
        if not fields[FIELDS.index("first_name")] or not fields[FIELDS.index("last_name")]:
            return "First name and last name are required.", 400
        update_agent(fields, agent_id)
        return redirect(url_for("agents"))

    agent = get_agent(agent_id)
    if not agent:
        return "Agent not found.", 404
    return render_template(
        "edit_agent.html", agent=agent, brokers=list_brokers(),
        form_sections=AGENT_FORM_SECTIONS, is_new=False,
    )


@app.route("/agents/delete/<int:agent_id>", methods=["POST"])
def remove_agent(agent_id):
    delete_agent(agent_id)
    return redirect(url_for("agents"))
