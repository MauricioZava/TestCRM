from models.db import get_conn

FIELDS = (
    "first_name", "middle_name", "last_name", "email", "phone", "mobile_phone", "office_phone",
    "broker_id", "office_id", "team_id", "brokerage", "license_number", "license_state",
    "license_expiration_date", "mls_id", "nrds_id", "agent_type", "years_experience", "status",
    "preferred_contact_method", "agent_tags", "social_media_links", "profile_photo_url", "office_address",
    "city", "state", "zip_code", "website", "specialties", "notes"
)


def list_agents():
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"""
        SELECT id, {", ".join(FIELDS)}, created_at, updated_at
        FROM agents
        ORDER BY last_name, first_name
    """)
    rows = c.fetchall()
    conn.close()
    agents = []
    for row in rows:
        agent = dict(zip(("id", *FIELDS, "created_at", "updated_at"), row))
        display_name = " ".join(part for part in (agent["first_name"], agent["middle_name"], agent["last_name"]) if part).strip()
        agent["display_name"] = display_name or agent["first_name"] or agent["last_name"] or "Unnamed Agent"
        agent["name"] = agent["display_name"]
        agents.append(agent)
    return agents


def get_agent(agent_id):
    conn = get_conn()
    row = conn.execute(
        f"SELECT id, {', '.join(FIELDS)}, created_at, updated_at FROM agents WHERE id = ?",
        (agent_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    agent = dict(zip(("id", *FIELDS, "created_at", "updated_at"), row))
    display_name = " ".join(part for part in (agent["first_name"], agent["middle_name"], agent["last_name"]) if part).strip()
    agent["display_name"] = display_name or agent["first_name"] or agent["last_name"] or "Unnamed Agent"
    agent["name"] = agent["display_name"]
    return agent


def list_agents_brief():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, first_name, middle_name, last_name FROM agents ORDER BY last_name, first_name"
    ).fetchall()
    conn.close()
    return rows


def list_agents_with_brokerage():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, first_name, middle_name, last_name, brokerage FROM agents ORDER BY last_name, first_name"
    ).fetchall()
    conn.close()
    return rows


def insert_agent(fields):
    conn = get_conn()
    conn.execute(f"""
        INSERT INTO agents ({", ".join(FIELDS)}, created_at, updated_at)
        VALUES ({", ".join("?" for _ in FIELDS)}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, fields)
    conn.commit()
    conn.close()


def update_agent(fields, agent_id):
    conn = get_conn()
    assignments = ", ".join(f"{name} = ?" for name in FIELDS) + ", updated_at = CURRENT_TIMESTAMP"
    conn.execute(f"UPDATE agents SET {assignments} WHERE id = ?", (*fields, agent_id))
    conn.commit()
    conn.close()


def delete_agent(agent_id):
    conn = get_conn()
    conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    conn.commit()
    conn.close()
