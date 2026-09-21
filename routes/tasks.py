from flask import request, redirect, url_for, render_template

from extensions import app
from models.tasks import (
    list_contacts_brief, list_agents_brief, list_tasks, insert_task, update_task,
    delete_task as delete_task_row, get_signin_email, get_signin_name_and_email,
)
from services.email_service import send_email


@app.route("/tasks")
def tasks():
    selected_contact_id = request.args.get("contact_id", type=int)

    contacts = [
        {
            "id": row[0],
            "name": " ".join(part for part in (row[1], row[2]) if part),
            "email": row[3],
            "agent_id": row[4],
        }
        for row in list_contacts_brief()
    ]
    agents = list_agents_brief()

    task_rows = list_tasks()
    task_list = [
        {
            "id": row[0],
            "signin_id": row[1],
            "title": row[2],
            "due_date": row[3],
            "priority": row[4],
            "status": row[5],
            "notes": row[6],
            "created_at": row[7],
            "client_name": " ".join(part for part in (row[8], row[9]) if part),
            "client_email": row[10],
            "thank_you_selected": bool(row[11]),
            "thank_you_date": row[12],
            "thank_you_time": row[13],
            "thank_you_send_now": bool(row[14]),
            "follow_up_selected": bool(row[15]),
            "follow_up_date": row[16],
            "follow_up_time": row[17],
            "follow_up_send_now": bool(row[18]),
            "notes_email_selected": bool(row[19]),
            "notes_email_date": row[20],
            "notes_email_time": row[21],
            "notes_email_send_now": bool(row[22]),
        }
        for row in task_rows
    ]
    selected_contact = next((contact for contact in contacts if contact["id"] == selected_contact_id), None)
    return render_template("tasks.html", contacts=contacts, agents=agents, tasks=task_list, selected_contact=selected_contact)


@app.route("/tasks/create", methods=["POST"])
def create_task():
    signin_id = request.form.get("signin_id", type=int)
    agent_id = request.form.get("agent_id", type=int)
    task_id = request.form.get("task_id", type=int)
    action = request.form.get("action", "create")

    if action == "send_email":
        if not signin_id:
            return "Client is required.", 400
        selected_messages = []
        message_fields = (
            ("thank_you_selected", "thank_you_notes"),
            ("follow_up_selected", "follow_up_notes"),
            ("notes_email_selected", "notes_email_notes"),
        )
        for selected_field, notes_field in message_fields:
            if request.form.get(selected_field) == "on":
                message = request.form.get(notes_field, "").strip()
                if not message:
                    return "Add a message to every selected email option.", 400
                selected_messages.append(message)
        if not selected_messages:
            return "Select at least one email option.", 400

        client = get_signin_name_and_email(signin_id)
        if not client or not client[1]:
            return "This client does not have an email address.", 400
        greeting = f"Hi {client[0] or 'there'},"
        send_email(client[1], "Open House Follow-Up", f"{greeting}\n\n" + "\n\n".join(selected_messages))
        return redirect(url_for("tasks"))

    if action == "delete":
        if not task_id:
            return "Task is required for deletion.", 400
        delete_task_row(task_id)
        return redirect(url_for("tasks"))

    title = request.form.get("title", "").strip()

    thank_you_selected = 1 if request.form.get("thank_you_selected") == "on" else 0
    follow_up_selected = 1 if request.form.get("follow_up_selected") == "on" else 0
    notes_email_selected = 1 if request.form.get("notes_email_selected") == "on" else 0
    if thank_you_selected and follow_up_selected:
        title = "Thank you and follow-up email"
    elif thank_you_selected:
        title = "Thank you for visiting"
    elif follow_up_selected:
        title = "Follow-up email"
    elif not title:
        title = "Client follow-up"

    if not signin_id:
        return "Client is required.", 400
    thank_you_send_now = 1 if thank_you_selected and request.form.get("thank_you_send_now") == "on" else 0
    follow_up_send_now = 1 if follow_up_selected and request.form.get("follow_up_send_now") == "on" else 0
    notes_email_send_now = 1 if notes_email_selected and request.form.get("notes_email_send_now") == "on" else 0
    thank_you_date = request.form.get("thank_you_date", "").strip()
    thank_you_time = request.form.get("thank_you_time", "").strip()
    follow_up_date = request.form.get("follow_up_date", "").strip()
    follow_up_time = request.form.get("follow_up_time", "").strip()
    notes_email_date = request.form.get("notes_email_date", "").strip()
    notes_email_time = request.form.get("notes_email_time", "").strip()
    notes = request.form.get("notes", "").strip()
    if thank_you_selected and not thank_you_send_now and (not thank_you_date or not thank_you_time):
        return "Choose Send Now or provide a thank-you date and time.", 400
    if follow_up_selected and not follow_up_send_now and (not follow_up_date or not follow_up_time):
        return "Choose Send Now or provide a follow-up date and time.", 400
    if notes_email_selected and not notes:
        return "Add a message in Notes before sending an email from notes.", 400
    if notes_email_selected and not notes_email_send_now and (not notes_email_date or not notes_email_time):
        return "Choose Send Now or provide an email date and time.", 400
    selected_titles = []
    if thank_you_selected:
        selected_titles.append("Thank you for visiting")
    if follow_up_selected:
        selected_titles.append("Follow-up email")
    if notes_email_selected:
        selected_titles.append("Email from notes")
    if selected_titles:
        title = " and ".join(selected_titles)

    values = (
        signin_id, agent_id, title, request.form.get("due_date", "").strip(),
        request.form.get("priority", "Normal").strip(),
        request.form.get("status", "Open").strip(), request.form.get("notes", "").strip(),
        thank_you_selected, thank_you_date, thank_you_time, thank_you_send_now,
        follow_up_selected, follow_up_date, follow_up_time, follow_up_send_now,
        notes_email_selected, notes_email_date, notes_email_time, notes_email_send_now
    )
    if action == "update":
        if not task_id:
            return "Task is required for an update.", 400
        update_task(values, task_id)
    else:
        insert_task(values)

    if thank_you_send_now or follow_up_send_now or notes_email_send_now:
        client = get_signin_email(signin_id)
        if client and client[0]:
            messages = []
            if thank_you_send_now:
                messages.append("Thank you for visiting the open house. It was great meeting you!")
            if follow_up_send_now:
                messages.append("I wanted to follow up after your open house visit. Please let me know how I can help.")
            if notes_email_send_now:
                messages.append(notes)
            send_email(client[0], "Open House Follow-Up", "\n\n".join(messages))
        return redirect(url_for("tasks"))
    return redirect(url_for("tasks"))


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    delete_task_row(task_id)
    return redirect(url_for("tasks"))
