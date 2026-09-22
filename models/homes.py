from models.db import get_conn


def list_homes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, property_id, agent_id, address, city, state, zip_code, rooms, lot_size, is_current, broker_id FROM homes")
    rows = c.fetchall()
    conn.close()
    return rows


def list_homes_brief():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, property_id, address, city, state, zip_code
        FROM homes
        ORDER BY is_current DESC, address, city
    """)
    rows = [
        {"id": row[0], "property_id": row[1], "address": row[2], "city": row[3], "state": row[4], "zip_code": row[5]}
        for row in c.fetchall()
    ]
    conn.close()
    return rows


def unset_current_home():
    conn = get_conn()
    conn.execute("UPDATE homes SET is_current = 0")
    conn.commit()
    conn.close()


def insert_home(property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current):
    conn = get_conn()
    conn.execute("""
        INSERT INTO homes (property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current))
    conn.commit()
    conn.close()


def update_home(home_id, property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current):
    conn = get_conn()
    conn.execute("""
        UPDATE homes
        SET property_id = ?, agent_id = ?, broker_id = ?, address = ?, city = ?, state = ?, zip_code = ?, rooms = ?, lot_size = ?, is_current = ?
        WHERE id = ?
    """, (property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current, home_id))
    conn.commit()
    conn.close()


def delete_home(home_id):
    conn = get_conn()
    conn.execute("DELETE FROM homes WHERE id = ?", (home_id,))
    conn.commit()
    conn.close()
