from models.db import get_conn


FIELDS = (
    "company_name", "first_name", "last_name", "contact_name", "email", "phone", "office_address",
    "city", "state", "zip_code", "website", "notes"
)


def list_brokers():
    conn = get_conn()
    rows = conn.execute(
        f"SELECT id, {', '.join(FIELDS)} FROM brokers ORDER BY company_name"
    ).fetchall()
    conn.close()
    return [dict(zip(("id", *FIELDS), row)) for row in rows]


def insert_broker(fields):
    conn = get_conn()
    conn.execute(
        f"INSERT INTO brokers ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)})",
        fields,
    )
    conn.commit()
    conn.close()


def update_broker(fields, broker_id):
    conn = get_conn()
    assignments = ", ".join(f"{name} = ?" for name in FIELDS)
    conn.execute(f"UPDATE brokers SET {assignments} WHERE id = ?", (*fields, broker_id))
    conn.commit()
    conn.close()


def delete_broker(broker_id):
    conn = get_conn()
    conn.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
    conn.commit()
    conn.close()