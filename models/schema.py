from models.db import get_conn


def init_db():
    conn = get_conn()
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
    for column in ("working_with_broker", "zip_code", "heard_about_us", "is_contact", "dashboard_hidden", "agent_id", "open_house_id", "first_name", "last_name", "alternate_phone", "preferred_contact_method", "best_time_to_contact", "lead_status", "property_type", "bedrooms", "preferred_areas"):
        if column not in existing_columns:
            column_type = "INTEGER" if column in ("agent_id", "open_house_id") else "INTEGER DEFAULT 0" if column == "is_contact" else "TEXT"
            if column == "dashboard_hidden":
                column_type = "INTEGER DEFAULT 0"
            c.execute(f"ALTER TABLE signins ADD COLUMN {column} {column_type}")

    # One-time backfill: split any legacy full "name" values into first_name / last_name.
    if "first_name" not in existing_columns or "last_name" not in existing_columns:
        legacy_rows = c.execute(
            "SELECT id, name FROM signins WHERE name IS NOT NULL AND name != '' "
            "AND (first_name IS NULL OR first_name = '')"
        ).fetchall()
        for row_id, full_name in legacy_rows:
            parts = full_name.strip().split(" ", 1)
            first = parts[0] if parts else ""
            last = parts[1] if len(parts) > 1 else ""
            c.execute("UPDATE signins SET first_name = ?, last_name = ? WHERE id = ?", (first, last, row_id))

    conn.commit()
    conn.close()


def init_homes_table():
    conn = get_conn()
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
    for column in ("rooms", "lot_size", "agent_id", "broker_id"):
        if column not in existing_columns:
            column_type = "INTEGER" if column in ("agent_id", "broker_id") else "TEXT"
            c.execute(f"ALTER TABLE homes ADD COLUMN {column} {column_type}")
    conn.commit()
    conn.close()


def init_agents_table():
    conn = get_conn()
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
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(agents)").fetchall()}
    agent_columns = (
        "middle_name", "email", "phone", "brokerage", "license_number",
        "license_state", "office_address", "city", "state", "zip_code",
        "website", "specialties", "notes"
    )
    for column in agent_columns:
        if column not in existing_columns:
            c.execute(f"ALTER TABLE agents ADD COLUMN {column} TEXT")
    conn.commit()
    conn.close()


def init_brokers_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            office_address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            website TEXT,
            notes TEXT
        )
    """)
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(brokers)").fetchall()}
    for column in ("first_name", "last_name"):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE brokers ADD COLUMN {column} TEXT")
    conn.commit()
    conn.close()


def init_tasks_table():
    conn = get_conn()
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
        "thank_you_sent", "follow_up_sent", "notes_email_sent", "agent_id"
    ):
        if column not in existing_columns:
            column_type = "INTEGER DEFAULT 0" if column.endswith("selected") or column.endswith("send_now") or column.endswith("sent") else "INTEGER" if column == "agent_id" else "TEXT"
            c.execute(f"ALTER TABLE tasks ADD COLUMN {column} {column_type}")
    conn.commit()
    conn.close()


def init_open_houses_table():
    conn = get_conn()
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
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(open_houses)").fetchall()}
    open_house_columns = (
        "title", "status", "visitor_capacity", "rsvp_contact",
        "public_notes", "internal_notes"
    )
    for column in open_house_columns:
        if column not in existing_columns:
            column_type = "TEXT NOT NULL DEFAULT 'Scheduled'" if column == "status" else "TEXT"
            c.execute(f"ALTER TABLE open_houses ADD COLUMN {column} {column_type}")
    conn.commit()
    conn.close()


def backfill_signin_open_houses():
    conn = get_conn()
    conn.execute("""
        UPDATE signins
        SET open_house_id = (
            SELECT id FROM open_houses
            WHERE status = 'Scheduled'
            ORDER BY event_date ASC, start_time ASC
            LIMIT 1
        )
        WHERE open_house_id IS NULL
    """)
    conn.execute("""
        UPDATE signins
        SET agent_id = (
            SELECT agent_id FROM open_houses
            WHERE open_houses.id = signins.open_house_id
        )
        WHERE agent_id IS NULL AND open_house_id IS NOT NULL
    """)
    conn.commit()
    conn.close()


def init_all():
    init_db()
    init_homes_table()
    init_agents_table()
    init_brokers_table()
    init_open_houses_table()
    backfill_signin_open_houses()
    init_tasks_table()
