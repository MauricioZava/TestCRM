import csv
import io
import json

from flask import redirect, url_for, render_template, make_response

from extensions import app
from models.signins import list_dashboard_signins, export_rows
from models.tasks import list_dashboard_tasks


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    rows = list_dashboard_signins()
    task_rows = list_dashboard_tasks()

    dashboard_tasks = [
        {
            "id": row[0],
            "title": row[1],
            "priority": row[2],
            "status": row[3],
            "notes": row[4],
            "client_name": " ".join(part for part in (row[5], row[6]) if part),
            "client_email": row[7],
        }
        for row in task_rows
    ]

    signins = []
    for row in rows:
        signins.append({
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "name": " ".join(part for part in (row[1], row[2]) if part),
            "email": row[3],
            "phone": row[4],
            "alternate_phone": row[5],
            "visitor_type": row[6],
            "currently": row[7],
            "property_type": row[8],
            "bedrooms": row[9],
            "preferred_areas": row[10],
            "working_with_broker": row[11],
            "zip_code": row[12],
            "heard_about_us": row[13],
            "is_contact": bool(row[14]),
            "dashboard_hidden": bool(row[15]),
            "timeline": row[16],
            "preapproval": row[17],
            "notes": row[18],
            "motivation_score": row[19],
            "followup_message": row[20],
            "next_steps_json": json.loads(row[21]),
            "created_at": row[22],
            "agent_name": " ".join(part for part in row[23:26] if part),
        })

    return render_template("dashboard.html", signins=signins, dashboard_tasks=dashboard_tasks)


@app.route("/export_csv")
def export_csv():
    rows = export_rows()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "First Name", "Last Name", "Email", "Phone", "Visitor Type", "Currently",
        "Property Type", "Bedrooms", "Preferred Areas",
        "Timeline", "Preapproval", "Notes", "Motivation Score",
        "Follow-Up Message", "Next Steps JSON", "Created At"
    ])

    for row in rows:
        writer.writerow(row)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=signins.csv"
    response.headers["Content-Type"] = "text/csv"

    return response
