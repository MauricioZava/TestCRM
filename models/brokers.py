from models.db import get_conn


FIELDS = (
    "company_name", "first_name", "last_name", "contact_name", "email", "phone", "office_address",
    "city", "state", "zip_code", "website", "notes", "license_number", "license_state",
    "license_expiration_date", "mls_id", "nrds_id", "broker_type", "years_experience", "office_id",
    "is_primary_broker", "status", "preferred_contact_method", "tags", "social_media_links", "profile_photo_url"
)


def list_brokers():
    conn = get_conn()
    rows = conn.execute(
        f"SELECT id, {', '.join(FIELDS)}, created_at, updated_at FROM brokers ORDER BY company_name"
    ).fetchall()
    conn.close()
    return [dict(zip(("id", *FIELDS, "created_at", "updated_at"), row)) for row in rows]


def insert_broker(fields):
    conn = get_conn()
    conn.execute(
        f"INSERT INTO brokers ({', '.join(FIELDS)}, created_at, updated_at) "
        f"VALUES ({', '.join('?' for _ in FIELDS)}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        fields,
    )
    conn.commit()
    conn.close()


def update_broker(fields, broker_id):
    conn = get_conn()
    assignments = ", ".join(f"{name} = ?" for name in FIELDS) + ", updated_at = CURRENT_TIMESTAMP"
    conn.execute(f"UPDATE brokers SET {assignments} WHERE id = ?", (*fields, broker_id))
    conn.commit()
    conn.close()


def delete_broker(broker_id):
    conn = get_conn()
    conn.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
    conn.commit()
    conn.close()