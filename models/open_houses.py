from models.db import get_conn


def list_open_houses_detailed():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT oh.id, oh.home_id, oh.agent_id, oh.event_date, oh.start_time, oh.end_time,
               oh.title, oh.status, oh.visitor_capacity, oh.rsvp_contact,
               oh.public_notes, oh.internal_notes,
               h.property_id, h.address, h.city, h.state, h.zip_code, h.is_current,
               a.first_name, a.middle_name, a.last_name, a.brokerage
        FROM open_houses oh
        LEFT JOIN homes h ON h.id = oh.home_id
        LEFT JOIN agents a ON a.id = oh.agent_id
        ORDER BY oh.event_date DESC, oh.start_time DESC
    """)
    rows = [
        {
            "id": row[0], "home_id": row[1], "agent_id": row[2], "event_date": row[3],
            "start_time": row[4], "end_time": row[5], "title": row[6], "status": row[7],
            "visitor_capacity": row[8], "rsvp_contact": row[9], "public_notes": row[10],
            "internal_notes": row[11], "property_id": row[12], "address": row[13],
            "city": row[14], "state": row[15], "zip_code": row[16], "is_current": row[17],
            "agent_first_name": row[18], "agent_middle_name": row[19], "agent_last_name": row[20],
            "brokerage": row[21],
        }
        for row in c.fetchall()
    ]
    conn.close()
    return rows


def delete_open_house(open_house_id):
    conn = get_conn()
    conn.execute("DELETE FROM open_houses WHERE id = ?", (open_house_id,))
    conn.commit()
    conn.close()


def insert_open_house(fields):
    conn = get_conn()
    conn.execute("""
        INSERT INTO open_houses (
            home_id, agent_id, event_date, start_time, end_time, title, status,
            visitor_capacity, rsvp_contact, public_notes, internal_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, fields)
    conn.commit()
    conn.close()


def update_open_house(fields, open_house_id):
    conn = get_conn()
    cursor = conn.execute("""
        UPDATE open_houses
        SET home_id = ?, agent_id = ?, event_date = ?, start_time = ?, end_time = ?,
            title = ?, status = ?, visitor_capacity = ?, rsvp_contact = ?,
            public_notes = ?, internal_notes = ?
        WHERE id = ?
    """, (*fields, open_house_id))
    conn.commit()
    updated_count = cursor.rowcount
    conn.close()
    return updated_count


def mark_completed_open_houses(now):
    conn = get_conn()
    cursor = conn.execute(
        """
        UPDATE open_houses
        SET status = 'Completed'
        WHERE lower(trim(status)) = 'scheduled'
          AND datetime(event_date || ' ' || end_time) <= datetime(?)
        """,
        (now.isoformat(sep=" ", timespec="seconds"),),
    )
    conn.commit()
    updated_count = cursor.rowcount
    conn.close()
    return updated_count


def get_next_scheduled():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
                 SELECT oh.id, oh.event_date, oh.start_time, oh.end_time,
             h.address, h.city, h.state, h.zip_code,
                             a.first_name, a.middle_name, a.last_name, oh.agent_id
        FROM open_houses oh
        JOIN homes h ON h.id = oh.home_id
        JOIN agents a ON a.id = oh.agent_id
        WHERE oh.status = 'Scheduled'
        ORDER BY oh.event_date ASC, oh.start_time ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return row


def get_scheduled_agent(open_house_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT agent_id
        FROM open_houses
        WHERE id = ? AND status = 'Scheduled'
    """, (open_house_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_next_scheduled_brief():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, agent_id
        FROM open_houses
        WHERE status = 'Scheduled'
        ORDER BY event_date ASC, start_time ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    return row
