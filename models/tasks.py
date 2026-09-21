from models.db import get_conn


def list_contacts_brief():
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, first_name, last_name, email, agent_id
        FROM signins
        WHERE is_contact = 1
        ORDER BY first_name, last_name
    """).fetchall()
    conn.close()
    return rows


def list_agents_brief():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, first_name, middle_name, last_name FROM agents ORDER BY last_name, first_name"
    ).fetchall()
    conn.close()
    return rows


def list_tasks():
    conn = get_conn()
    rows = conn.execute("""
         SELECT tasks.id, tasks.signin_id, tasks.title, tasks.due_date, tasks.priority,
             tasks.status, tasks.notes, tasks.created_at, signins.first_name, signins.last_name, signins.email,
             tasks.thank_you_selected, tasks.thank_you_date, tasks.thank_you_time,
             tasks.thank_you_send_now, tasks.follow_up_selected, tasks.follow_up_date,
               tasks.follow_up_time, tasks.follow_up_send_now, tasks.notes_email_selected,
               tasks.notes_email_date, tasks.notes_email_time, tasks.notes_email_send_now
        FROM tasks
        JOIN signins ON signins.id = tasks.signin_id
        ORDER BY CASE tasks.status WHEN 'Open' THEN 0 ELSE 1 END, tasks.due_date, tasks.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def list_dashboard_tasks():
    conn = get_conn()
    rows = conn.execute("""
        SELECT tasks.id, tasks.title, tasks.priority, tasks.status, tasks.notes,
               signins.first_name, signins.last_name, signins.email
        FROM tasks
        JOIN signins ON signins.id = tasks.signin_id
        ORDER BY CASE tasks.status WHEN 'Open' THEN 0 ELSE 1 END, tasks.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def insert_task(values):
    conn = get_conn()
    conn.execute("""
        INSERT INTO tasks (
            signin_id, agent_id, title, due_date, priority, status, notes,
            thank_you_selected, thank_you_date, thank_you_time, thank_you_send_now,
            follow_up_selected, follow_up_date, follow_up_time, follow_up_send_now,
            notes_email_selected, notes_email_date, notes_email_time, notes_email_send_now
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, values)
    conn.commit()
    conn.close()


def update_task(values, task_id):
    conn = get_conn()
    conn.execute("""
        UPDATE tasks
        SET signin_id = ?, agent_id = ?, title = ?, due_date = ?, priority = ?, status = ?, notes = ?,
            thank_you_selected = ?, thank_you_date = ?, thank_you_time = ?, thank_you_send_now = ?,
            follow_up_selected = ?, follow_up_date = ?, follow_up_time = ?, follow_up_send_now = ?,
            notes_email_selected = ?, notes_email_date = ?, notes_email_time = ?, notes_email_send_now = ?
        WHERE id = ?
    """, (*values, task_id))
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_conn()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def get_signin_email(signin_id):
    conn = get_conn()
    row = conn.execute("SELECT email FROM signins WHERE id = ?", (signin_id,)).fetchone()
    conn.close()
    return row


def get_signin_name_and_email(signin_id):
    conn = get_conn()
    row = conn.execute("SELECT first_name, email FROM signins WHERE id = ?", (signin_id,)).fetchone()
    conn.close()
    return row


def get_due_task_rows():
    conn = get_conn()
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
    conn.close()
    return rows


def mark_tasks_sent(task_id, updates):
    conn = get_conn()
    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
