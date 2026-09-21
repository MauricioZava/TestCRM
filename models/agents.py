from models.db import get_conn

FIELDS = (
    "first_name", "middle_name", "last_name", "email", "phone",
    "brokerage", "license_number", "license_state", "office_address",
    "city", "state", "zip_code", "website", "specialties", "notes"
)


def list_agents():
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"""
        SELECT id, {", ".join(FIELDS)}
        FROM agents
        ORDER BY last_name, first_name
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(zip(("id", *FIELDS), row)) for row in rows]


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
        INSERT INTO agents ({", ".join(FIELDS)})
        VALUES ({", ".join("?" for _ in FIELDS)})
    """, fields)
    conn.commit()
    conn.close()


def update_agent(fields, agent_id):
    conn = get_conn()
    assignments = ", ".join(f"{name} = ?" for name in FIELDS)
    conn.execute(f"UPDATE agents SET {assignments} WHERE id = ?", (*fields, agent_id))
    conn.commit()
    conn.close()


def delete_agent(agent_id):
    conn = get_conn()
    conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    conn.commit()
    conn.close()
