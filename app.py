import sqlite3
import smtplib
import csv
import io
import json
import threading
import time
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, make_response

from flask import Flask
app = Flask(__name__)
DB_NAME = "database.db"

# -----------------------------
# SMTP CONFIGURATION
# -----------------------------
SMTP_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "maury.zavala.68@gmail.com"
SMTP_PASSWORD = "zwmlarsyftfsccxo"
SMTP_FROM_EMAIL = "maury.zavala.68@gmail.com"
task_scheduler_started = False
task_scheduler_lock = threading.Lock()

# -----------------------------
# DELETE SIGN-IN
# -----------------------------

from flask import render_template
@app.route("/")
def index():
    return render_template("index.html")




@app.route("/delete_signin/<int:signin_id>")
def delete_signin(signin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE signins SET dashboard_hidden = 1 WHERE id = ?", (signin_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/contacts/<int:signin_id>/notes", methods=["POST"])
def update_contact_notes(signin_id):
    notes = request.form.get("notes", "").strip()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT visitor_type, timeline, preapproval, currently
        FROM signins
        WHERE id = ?
    """, (signin_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return "Sign-in record not found.", 404

    visitor_type, timeline, preapproval, currently = row
    motivation_score, followup_message, next_steps_json = categorize_and_score(
        visitor_type, timeline, preapproval, notes, currently
    )
    c.execute("""
        UPDATE signins
        SET notes = ?, motivation_score = ?, followup_message = ?, next_steps_json = ?
        WHERE id = ?
    """, (notes, motivation_score, followup_message, next_steps_json, signin_id))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# -----------------------------
# EXPORT CSV
# -----------------------------
@app.route("/export_csv")
def export_csv():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
         SELECT id, name, email, phone, visitor_type, currently,
             working_with_broker, zip_code, heard_about_us, timeline,
             preapproval, notes, motivation_score, followup_message,
             next_steps_json, created_at
        FROM signins
        ORDER BY motivation_score DESC, created_at DESC
    """)
    rows = c.fetchall()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "Name", "Email", "Phone", "Visitor Type", "Currently",
        "Timeline", "Preapproval", "Notes", "Motivation Score",
        "Follow-Up Message", "Next Steps JSON", "Created At"
    ])

    for row in rows:
        writer.writerow(row)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=signins.csv"
    response.headers["Content-Type"] = "text/csv"

    return response

# -----------------------------
# SEND EMAIL
# -----------------------------
def send_email(to_email, subject, body):
    if not SMTP_ENABLED:
        print("SMTP disabled — email not sent.")
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())

        print(f"Email sent to {to_email}")
        return True

    except Exception as e:
        print(f"Email error: {e}")
        return False

# -----------------------------
# HOMES DB
# -----------------------------
def init_homes_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS homes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            rooms TEXT,
            lot_size TEXT,
            is_current INTEGER DEFAULT 0
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(homes)").fetchall()}
    for column in ("rooms", "lot_size"):
        if column not in existing_columns:
            c.execute(f"ALTER TABLE homes ADD COLUMN {column} TEXT")
    conn.commit()
    conn.close()

def init_agents_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            brokerage TEXT,
            license_number TEXT,
            license_state TEXT,
            office_address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            website TEXT,
            specialties TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def init_tasks_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signin_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'Normal',
            status TEXT NOT NULL DEFAULT 'Open',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (signin_id) REFERENCES signins (id)
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
    for column in (
        "thank_you_selected", "thank_you_date", "thank_you_time", "thank_you_send_now",
        "follow_up_selected", "follow_up_date", "follow_up_time", "follow_up_send_now",
        "notes_email_selected", "notes_email_date", "notes_email_time", "notes_email_send_now",
        "thank_you_sent", "follow_up_sent", "notes_email_sent"
    ):
        if column not in existing_columns:
            column_type = "INTEGER DEFAULT 0" if column.endswith("selected") or column.endswith("send_now") or column.endswith("sent") else "TEXT"
            c.execute(f"ALTER TABLE tasks ADD COLUMN {column} {column_type}")
    conn.commit()
    conn.close()

def process_due_task_emails():
    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("""
        SELECT tasks.id, tasks.signin_id, tasks.notes,
               tasks.thank_you_selected, tasks.thank_you_date, tasks.thank_you_time, tasks.thank_you_sent,
               tasks.follow_up_selected, tasks.follow_up_date, tasks.follow_up_time, tasks.follow_up_sent,
               tasks.notes_email_selected, tasks.notes_email_date, tasks.notes_email_time, tasks.notes_email_sent,
               signins.email
        FROM tasks
        JOIN signins ON signins.id = tasks.signin_id
        WHERE signins.email IS NOT NULL AND signins.email != ''
    """).fetchall()

    for row in rows:
        task_id, signin_id, notes = row[0], row[1], row[2] or ""
        messages = []
        updates = []

        if row[3] and not row[6] and row[4] and row[5] and f"{row[4]} {row[5]}" <= now_text:
            messages.append("Thank you for visiting the open house. It was great meeting you!")
            updates.append("thank_you_sent = 1")
        if row[7] and not row[10] and row[8] and row[9] and f"{row[8]} {row[9]}" <= now_text:
            messages.append("I wanted to follow up after your open house visit. Please let me know how I can help.")
            updates.append("follow_up_sent = 1")
        if row[11] and not row[14] and row[12] and row[13] and f"{row[12]} {row[13]}" <= now_text:
            messages.append(notes)
            updates.append("notes_email_sent = 1")

        if messages:
            if send_email(row[15], "Open House Follow-Up", "\n\n".join(messages)):
                conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", (task_id,))

    conn.commit()
    conn.close()

def start_task_scheduler():
    global task_scheduler_started
    with task_scheduler_lock:
        if task_scheduler_started:
            return
        task_scheduler_started = True

    def scheduler_loop():
        while True:
            try:
                process_due_task_emails()
            except Exception as error:
                app.logger.error("Task email scheduler failed: %s", error)
            time.sleep(30)

    threading.Thread(target=scheduler_loop, daemon=True, name="task-email-scheduler").start()

@app.before_request
def ensure_task_scheduler():
    start_task_scheduler()

def init_open_houses_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS open_houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_id INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            visitor_capacity TEXT,
            rsvp_contact TEXT,
            public_notes TEXT,
            internal_notes TEXT,
            FOREIGN KEY (home_id) REFERENCES homes (id),
            FOREIGN KEY (agent_id) REFERENCES agents (id)
        )
    """)
    conn.commit()
    conn.close()

@app.route("/generate-open-house", methods=["GET", "POST"])
def generate_open_house():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action", "new")
        open_house_id = request.form.get("open_house_id")

        if action == "delete" and open_house_id:
            c.execute("DELETE FROM open_houses WHERE id = ?", (open_house_id,))
            conn.commit()
            conn.close()
            return redirect(url_for("generate_open_house"))

        if action in ("update", "delete") and not open_house_id:
            conn.close()
            return redirect(url_for("generate_open_house"))

        fields = [
            request.form.get(name, "").strip()
            for name in (
                "home_id", "agent_id", "event_date", "start_time", "end_time",
                "title", "status", "visitor_capacity", "rsvp_contact",
                "public_notes", "internal_notes"
            )
        ]

        if action == "update":
            c.execute("""
                UPDATE open_houses
                SET home_id = ?, agent_id = ?, event_date = ?, start_time = ?, end_time = ?,
                    title = ?, status = ?, visitor_capacity = ?, rsvp_contact = ?,
                    public_notes = ?, internal_notes = ?
                WHERE id = ?
            """, (*fields, open_house_id))
        else:
            c.execute("""
                INSERT INTO open_houses (
                    home_id, agent_id, event_date, start_time, end_time, title, status,
                    visitor_capacity, rsvp_contact, public_notes, internal_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, fields)

        conn.commit()
        conn.close()
        return redirect(url_for("generate_open_house"))

    c.execute("""
        SELECT id, property_id, address, city, state, zip_code
        FROM homes
        ORDER BY is_current DESC, address, city
    """)
    homes = [
        {"id": row[0], "property_id": row[1], "address": row[2], "city": row[3], "state": row[4], "zip_code": row[5]}
        for row in c.fetchall()
    ]

    c.execute("""
        SELECT id, first_name, middle_name, last_name, brokerage
        FROM agents
        ORDER BY last_name, first_name
    """)
    agents = [
        {"id": row[0], "first_name": row[1], "middle_name": row[2], "last_name": row[3], "brokerage": row[4]}
        for row in c.fetchall()
    ]

    c.execute("""
        SELECT oh.id, oh.home_id, oh.agent_id, oh.event_date, oh.start_time, oh.end_time,
               oh.title, oh.status, oh.visitor_capacity, oh.rsvp_contact,
               oh.public_notes, oh.internal_notes,
               h.property_id, h.address, h.city, h.state, h.zip_code,
               a.first_name, a.middle_name, a.last_name, a.brokerage
        FROM open_houses oh
        JOIN homes h ON h.id = oh.home_id
        JOIN agents a ON a.id = oh.agent_id
        ORDER BY oh.event_date DESC, oh.start_time DESC
    """)
    open_houses = [
        {
            "id": row[0], "home_id": row[1], "agent_id": row[2], "event_date": row[3],
            "start_time": row[4], "end_time": row[5], "title": row[6], "status": row[7],
            "visitor_capacity": row[8], "rsvp_contact": row[9], "public_notes": row[10],
            "internal_notes": row[11], "property_id": row[12], "address": row[13],
            "city": row[14], "state": row[15], "zip_code": row[16], "agent_first_name": row[17],
            "agent_middle_name": row[18], "agent_last_name": row[19], "brokerage": row[20],
        }
        for row in c.fetchall()
    ]
    conn.close()

    return render_template("GenerateOH.html", homes=homes, agents=agents, open_houses=open_houses)

@app.route("/agents", methods=["GET", "POST"])
def agents():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action", "add")
        agent_id = request.form.get("agent_id")

        if action == "delete" and agent_id:
            c.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()
            conn.close()
            return redirect(url_for("agents"))

        if action in ("update", "delete") and not agent_id:
            conn.close()
            return redirect(url_for("agents"))

        fields = [
            request.form.get(name, "").strip()
            for name in (
                "first_name", "middle_name", "last_name", "email", "phone",
                "brokerage", "license_number", "license_state", "office_address",
                "city", "state", "zip_code", "website", "specialties", "notes"
            )
        ]

        if action == "update":
            c.execute("""
                UPDATE agents
                SET first_name = ?, middle_name = ?, last_name = ?, email = ?, phone = ?,
                    brokerage = ?, license_number = ?, license_state = ?, office_address = ?,
                    city = ?, state = ?, zip_code = ?, website = ?, specialties = ?, notes = ?
                WHERE id = ?
            """, (*fields, agent_id))
        else:
            c.execute("""
                INSERT INTO agents (
                    first_name, middle_name, last_name, email, phone, brokerage,
                    license_number, license_state, office_address, city, state,
                    zip_code, website, specialties, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, fields)

        conn.commit()
        conn.close()
        return redirect(url_for("agents"))

    c.execute("""
        SELECT id, first_name, middle_name, last_name, email, phone, brokerage,
               license_number, license_state, office_address, city, state,
               zip_code, website, specialties, notes
        FROM agents
        ORDER BY last_name, first_name
    """)
    agent_rows = c.fetchall()
    conn.close()

    agents = [
        {
            "id": row[0],
            "first_name": row[1],
            "middle_name": row[2],
            "last_name": row[3],
            "email": row[4],
            "phone": row[5],
            "brokerage": row[6],
            "license_number": row[7],
            "license_state": row[8],
            "office_address": row[9],
            "city": row[10],
            "state": row[11],
            "zip_code": row[12],
            "website": row[13],
            "specialties": row[14],
            "notes": row[15],
        }
        for row in agent_rows
    ]
    return render_template("agents.html", agents=agents)

@app.route("/properties", methods=["GET", "POST"])
def properties():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action", "add")
        home_id = request.form.get("home_id")

        if action == "delete" and home_id:
            c.execute("DELETE FROM homes WHERE id = ?", (home_id,))
            conn.commit()
            conn.close()
            return redirect(url_for("properties"))

        if action in ("update", "delete") and not home_id:
            conn.close()
            return redirect(url_for("properties"))

        property_id = request.form.get("property_id")
        address = request.form.get("address")
        city = request.form.get("city")
        state = request.form.get("state")
        zip_code = request.form.get("zip_code")
        rooms = request.form.get("rooms")
        lot_size = request.form.get("lot_size")
        is_current = 1 if request.form.get("is_current") == "on" else 0

        # If this home is marked current, unset all others
        if is_current == 1:
            c.execute("UPDATE homes SET is_current = 0")

        if action == "update" and home_id:
            c.execute("""
                UPDATE homes
                SET property_id = ?, address = ?, city = ?, state = ?, zip_code = ?, rooms = ?, lot_size = ?, is_current = ?
                WHERE id = ?
            """, (property_id, address, city, state, zip_code, rooms, lot_size, is_current, home_id))
        else:
            c.execute("""
                INSERT INTO homes (property_id, address, city, state, zip_code, rooms, lot_size, is_current)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (property_id, address, city, state, zip_code, rooms, lot_size, is_current))

        conn.commit()
        conn.close()
        return redirect(url_for("properties"))

    # Load homes list
    c.execute("SELECT id, property_id, address, city, state, zip_code, rooms, lot_size, is_current FROM homes")
    homes = c.fetchall()
    conn.close()

    return render_template("properties.html", homes=homes)


@app.route("/address_suggestions")
def address_suggestions():
    query = request.args.get("q", "").strip()
    if len(query) < 3:
        return {"results": []}

    params = urlencode({
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5,
        "countrycodes": "us",
    })
    api_request = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": "OpenHouseAgent/1.0 address lookup"},
    )

    try:
        with urlopen(api_request, timeout=10) as response:
            listings = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        app.logger.warning("Public address search failed: %s", error)
        return {"results": [], "error": "Address search is temporarily unavailable."}, 503

    results = []
    for listing in listings:
        address = listing.get("address", {})
        results.append({
            "property_id": f"osm-{listing.get('osm_type', '').lower()}-{listing.get('osm_id', '')}",
            "address": address.get("house_number", "") + " " + address.get("road", ""),
            "city": address.get("city") or address.get("town") or address.get("village") or "",
            "state": address.get("state", ""),
            "zip_code": address.get("postcode", ""),
            "display_name": listing.get("display_name", ""),
        })

    return {"results": results}

# -----------------------------
# DATABASE INIT
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            visitor_type TEXT,
            currently TEXT,
            working_with_broker TEXT,
            zip_code TEXT,
            heard_about_us TEXT,
            is_contact INTEGER DEFAULT 0,
            dashboard_hidden INTEGER DEFAULT 0,
            timeline TEXT,
            preapproval TEXT,
            notes TEXT,
            motivation_score INTEGER,
            followup_message TEXT,
            next_steps_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(signins)").fetchall()}
    for column in ("working_with_broker", "zip_code", "heard_about_us", "is_contact", "dashboard_hidden"):
        if column not in existing_columns:
            column_type = "INTEGER DEFAULT 0" if column == "is_contact" else "TEXT"
            if column == "dashboard_hidden":
                column_type = "INTEGER DEFAULT 0"
            c.execute(f"ALTER TABLE signins ADD COLUMN {column} {column_type}")
    conn.commit()
    conn.close()

# -----------------------------
# SCORING + FOLLOWUP
# -----------------------------
def categorize_and_score(visitor_type, timeline, preapproval, notes, currently):
    score = 0

    if visitor_type == "buyer":
        score += 40
    elif visitor_type == "seller":
        score += 35
    elif visitor_type == "neighbor":
        score += 20
    elif visitor_type == "just-looking":
        score += 10

    if timeline == "0-3":
        score += 40
    elif timeline == "3-6":
        score += 25
    elif timeline == "6-12":
        score += 15
    else:
        score += 5

    if preapproval == "yes":
        score += 20
    elif preapproval == "no":
        score += 5

    if currently == "renting":
        score += 10
    elif currently == "own":
        score += 5

    notes_lower = (notes or "").lower()
    for kw in ["serious", "ready", "offer", "listing", "sell", "buy"]:
        if kw in notes_lower:
            score += 10

    score = min(score, 100)

    followup = generate_followup(visitor_type)
    next_steps_json = generate_next_steps(visitor_type, score)

    return score, followup, next_steps_json

def generate_followup(visitor_type):
    if visitor_type == "buyer":
        return "Thanks for visiting today! Here’s more information about the home."
    elif visitor_type == "seller":
        return "Great meeting you! I can prepare a quick home value estimate."
    elif visitor_type == "neighbor":
        return "Thanks for stopping by! If you know anyone moving, I’d love to help."
    elif visitor_type == "just-looking":
        return "Thanks for visiting! If you ever have questions, I’m here to help."
    return "Thank you for visiting the open house today!"

def generate_next_steps(visitor_type, score):
    steps = []

    if visitor_type == "buyer":
        steps.append("Send property brochure and similar listings.")
        if score >= 60:
            steps.append("Offer to schedule a private showing.")
        steps.append("Provide financing/pre-approval guidance.")

    elif visitor_type == "seller":
        steps.append("Offer a free CMA.")
        if score >= 60:
            steps.append("Suggest a listing consultation.")
        steps.append("Send a seller guide.")

    elif visitor_type == "neighbor":
        steps.append("Send a friendly thank-you message.")
        steps.append("Share referral program details.")

    elif visitor_type == "just-looking":
        steps.append("Send a friendly thank-you message.")
        steps.append("Offer to answer future real estate questions.")

    return json.dumps([{"task": s, "done": False} for s in steps])

# -----------------------------
# SIGN-IN PAGE
# -----------------------------
@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        visitor_type = request.form.get("visitor_type", "").strip()
        currently = request.form.get("currently", "").strip()
        working_with_broker = "yes" if request.form.get("working_with_broker") == "yes" else "no"
        zip_code = request.form.get("zip_code", "").strip()
        heard_about_us = request.form.get("heard_about_us", "").strip()
        timeline = request.form.get("timeline", "").strip()
        preapproval = request.form.get("preapproval", "").strip()
        notes = request.form.get("notes", "").strip()

        motivation_score, followup_message, next_steps_json = categorize_and_score(
            visitor_type, timeline, preapproval, notes, currently
        )

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            INSERT INTO signins (
                name, email, phone, visitor_type, currently, working_with_broker,
                zip_code, heard_about_us, timeline, preapproval, notes,
                motivation_score, followup_message, next_steps_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, email, phone, visitor_type, currently, working_with_broker,
            zip_code, heard_about_us, timeline, preapproval, notes,
            motivation_score, followup_message, next_steps_json
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    # Load the next scheduled open house selected in Generate Open House.
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
         SELECT oh.event_date, oh.start_time, oh.end_time,
             h.address, h.city, h.state, h.zip_code,
               a.first_name, a.middle_name, a.last_name
        FROM open_houses oh
        JOIN homes h ON h.id = oh.home_id
        JOIN agents a ON a.id = oh.agent_id
        WHERE oh.status = 'Scheduled'
        ORDER BY oh.event_date ASC, oh.start_time ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()

    open_house = None
    if row:
        agent_name = " ".join(part for part in row[7:10] if part)
        open_house = {
            "date": row[0],
            "time": f"{row[1]} - {row[2]}",
            "address": f"{row[3]}, {row[4]}, {row[5]} {row[6]}",
            "agent_name": agent_name,
        }

    return render_template("signin.html", open_house=open_house)


# -----------------------------
# DASHBOARD
# -----------------------------
@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
         SELECT id, name, email, phone, visitor_type, currently,
             working_with_broker, zip_code, heard_about_us, is_contact, dashboard_hidden, timeline,
             preapproval, notes, motivation_score, followup_message,
             next_steps_json, created_at
        FROM signins
         WHERE dashboard_hidden = 0
        ORDER BY motivation_score DESC, created_at DESC
    """)
    rows = c.fetchall()

    c.execute("""
        SELECT tasks.id, tasks.title, tasks.priority, tasks.status, tasks.notes,
               signins.name, signins.email
        FROM tasks
        JOIN signins ON signins.id = tasks.signin_id
        ORDER BY CASE tasks.status WHEN 'Open' THEN 0 ELSE 1 END, tasks.created_at DESC
    """)
    task_rows = c.fetchall()
    conn.close()

    signins = []
    dashboard_tasks = [
        {
            "id": row[0],
            "title": row[1],
            "priority": row[2],
            "status": row[3],
            "notes": row[4],
            "client_name": row[5],
            "client_email": row[6],
        }
        for row in task_rows
    ]
    for row in rows:
        signins.append({
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "visitor_type": row[4],
            "currently": row[5],
            "working_with_broker": row[6],
            "zip_code": row[7],
            "heard_about_us": row[8],
            "is_contact": bool(row[9]),
            "dashboard_hidden": bool(row[10]),
            "timeline": row[11],
            "preapproval": row[12],
            "notes": row[13],
            "motivation_score": row[14],
            "followup_message": row[15],
            "next_steps_json": json.loads(row[16]),
            "created_at": row[17],
        })





    return render_template("dashboard.html", signins=signins, dashboard_tasks=dashboard_tasks)

@app.route("/contacts/add/<int:signin_id>", methods=["POST"])
def add_contact(signin_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE signins SET is_contact = 1 WHERE id = ?", (signin_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/contacts/delete/<int:signin_id>", methods=["POST"])
def delete_contact(signin_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE signins SET is_contact = 0, dashboard_hidden = 1 WHERE id = ?", (signin_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("contacts"))

@app.route("/contacts")
def contacts():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
         SELECT id, name, email, phone, visitor_type, currently,
             working_with_broker, zip_code, heard_about_us, timeline,
             preapproval, notes, motivation_score, followup_message,
             next_steps_json, created_at
        FROM signins
        WHERE is_contact = 1
        ORDER BY created_at DESC
    """)
    rows = c.fetchall()
    conn.close()

    contacts = [
        {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "visitor_type": row[4],
            "currently": row[5],
            "working_with_broker": row[6],
            "zip_code": row[7],
            "heard_about_us": row[8],
            "timeline": row[9],
            "preapproval": row[10],
            "notes": row[11],
            "motivation_score": row[12],
            "followup_message": row[13],
            "next_steps": json.loads(row[14] or "[]"),
            "created_at": row[15],
        }
        for row in rows
    ]
    return render_template("Contacts.html", contacts=contacts)

@app.route("/tasks")
def tasks():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    selected_contact_id = request.args.get("contact_id", type=int)

    c.execute("""
        SELECT id, name, email
        FROM signins
        WHERE is_contact = 1
        ORDER BY name
    """)
    contacts = [{"id": row[0], "name": row[1], "email": row[2]} for row in c.fetchall()]

    c.execute("""
         SELECT tasks.id, tasks.signin_id, tasks.title, tasks.due_date, tasks.priority,
             tasks.status, tasks.notes, tasks.created_at, signins.name, signins.email,
             tasks.thank_you_selected, tasks.thank_you_date, tasks.thank_you_time,
             tasks.thank_you_send_now, tasks.follow_up_selected, tasks.follow_up_date,
               tasks.follow_up_time, tasks.follow_up_send_now, tasks.notes_email_selected,
               tasks.notes_email_date, tasks.notes_email_time, tasks.notes_email_send_now
        FROM tasks
        JOIN signins ON signins.id = tasks.signin_id
        ORDER BY CASE tasks.status WHEN 'Open' THEN 0 ELSE 1 END, tasks.due_date, tasks.created_at DESC
    """)
    task_rows = c.fetchall()
    conn.close()

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
            "client_name": row[8],
            "client_email": row[9],
            "thank_you_selected": bool(row[10]),
            "thank_you_date": row[11],
            "thank_you_time": row[12],
            "thank_you_send_now": bool(row[13]),
            "follow_up_selected": bool(row[14]),
            "follow_up_date": row[15],
            "follow_up_time": row[16],
            "follow_up_send_now": bool(row[17]),
            "notes_email_selected": bool(row[18]),
            "notes_email_date": row[19],
            "notes_email_time": row[20],
            "notes_email_send_now": bool(row[21]),
        }
        for row in task_rows
    ]
    selected_contact = next((contact for contact in contacts if contact["id"] == selected_contact_id), None)
    return render_template("tasks.html", contacts=contacts, tasks=task_list, selected_contact=selected_contact)

@app.route("/tasks/create", methods=["POST"])
def create_task():
    signin_id = request.form.get("signin_id", type=int)
    task_id = request.form.get("task_id", type=int)
    action = request.form.get("action", "create")

    if action == "delete":
        if not task_id:
            return "Task is required for deletion.", 400
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
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

    conn = sqlite3.connect(DB_NAME)
    values = (
        signin_id, title, request.form.get("due_date", "").strip(),
        request.form.get("priority", "Normal").strip(),
        request.form.get("status", "Open").strip(), request.form.get("notes", "").strip(),
        thank_you_selected, thank_you_date, thank_you_time, thank_you_send_now,
        follow_up_selected, follow_up_date, follow_up_time, follow_up_send_now,
        notes_email_selected, notes_email_date, notes_email_time, notes_email_send_now
    )
    if action == "update":
        if not task_id:
            conn.close()
            return "Task is required for an update.", 400
        conn.execute("""
            UPDATE tasks
            SET signin_id = ?, title = ?, due_date = ?, priority = ?, status = ?, notes = ?,
                thank_you_selected = ?, thank_you_date = ?, thank_you_time = ?, thank_you_send_now = ?,
                follow_up_selected = ?, follow_up_date = ?, follow_up_time = ?, follow_up_send_now = ?,
                notes_email_selected = ?, notes_email_date = ?, notes_email_time = ?, notes_email_send_now = ?
            WHERE id = ?
        """, (*values, task_id))
    else:
        conn.execute("""
            INSERT INTO tasks (
                signin_id, title, due_date, priority, status, notes,
                thank_you_selected, thank_you_date, thank_you_time, thank_you_send_now,
                follow_up_selected, follow_up_date, follow_up_time, follow_up_send_now,
                notes_email_selected, notes_email_date, notes_email_time, notes_email_send_now
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)
    conn.commit()

    if thank_you_send_now or follow_up_send_now or notes_email_send_now:
        client = conn.execute("SELECT name, email FROM signins WHERE id = ?", (signin_id,)).fetchone()
        conn.close()
        if client and client[1]:
            messages = []
            if thank_you_send_now:
                messages.append("Thank you for visiting the open house. It was great meeting you!")
            if follow_up_send_now:
                messages.append("I wanted to follow up after your open house visit. Please let me know how I can help.")
            if notes_email_send_now:
                messages.append(notes)
            send_email(client[1], "Open House Follow-Up", "\n\n".join(messages))
        return redirect(url_for("tasks"))
    conn.close()
    return redirect(url_for("tasks"))

@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("tasks"))

@app.route("/contacts/<int:signin_id>", methods=["GET", "POST"])
def edit_contact(signin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        visitor_type = request.form.get("visitor_type", "").strip()
        currently = request.form.get("currently", "").strip()
        timeline = request.form.get("timeline", "").strip()
        preapproval = request.form.get("preapproval", "").strip()
        notes = request.form.get("notes", "").strip()

        motivation_score, followup_message, next_steps_json = categorize_and_score(
            visitor_type, timeline, preapproval, notes, currently
        )
        c.execute("""
            UPDATE signins
            SET name = ?, email = ?, phone = ?, visitor_type = ?, currently = ?,
                timeline = ?, preapproval = ?, notes = ?, motivation_score = ?,
                followup_message = ?, next_steps_json = ?
            WHERE id = ?
        """, (
            name, email, phone, visitor_type, currently, timeline, preapproval,
            notes, motivation_score, followup_message, next_steps_json, signin_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    c.execute("""
        SELECT id, name, email, phone, visitor_type, currently, timeline,
               preapproval, notes
        FROM signins
        WHERE id = ?
    """, (signin_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Sign-in record not found.", 404

    contact = {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "phone": row[3],
        "visitor_type": row[4],
        "currently": row[5],
        "timeline": row[6],
        "preapproval": row[7],
        "notes": row[8],
    }
    return render_template("edit_contact.html", contact=contact)

@app.route("/send_email/<int:signin_id>")
def send_email_from_dashboard(signin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT name, email, followup_message
        FROM signins
        WHERE id = ?
    """, (signin_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Sign-in record not found."

    name, email, followup_message = row

    if not email:
        return "This visitor did not provide an email address."

    subject = "Thank You for Visiting the Open House"
    body = followup_message

    send_email(email, subject, body)

    return redirect(url_for("contacts"))

@app.route("/send_custom_email/<int:signin_id>", methods=["POST"])
def send_custom_email(signin_id):
    subject = request.form.get("subject", "Open House Follow-Up").strip()
    body = request.form.get("body", "").strip()

    if not body:
        return "Email message cannot be empty.", 400

    conn = sqlite3.connect(DB_NAME)
    row = conn.execute("SELECT email FROM signins WHERE id = ?", (signin_id,)).fetchone()
    conn.close()

    if not row:
        return "Sign-in record not found.", 404
    if not row[0]:
        return "This visitor did not provide an email address.", 400

    send_email(row[0], subject or "Open House Follow-Up", body)
    return redirect(url_for("contacts"))


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    init_db()
    init_homes_table()
    init_agents_table()
    init_open_houses_table()
    init_tasks_table()

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)

