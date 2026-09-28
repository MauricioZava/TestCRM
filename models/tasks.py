import json

from models.db import get_conn


def list_contacts_brief():
    conn = get_conn()
    rows = conn.execute("""
        SELECT LeadID, FirstName, LastName, Email, AssignedAgentID
        FROM Contacts
        WHERE IsArchived = 0
        ORDER BY FirstName, LastName
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


def list_task_types():
    conn = get_conn()
    rows = conn.execute(
        "SELECT TaskTypeName FROM TaskTypes ORDER BY TaskTypeID"
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def list_tasks():
    conn = get_conn()
    rows = conn.execute("""
         SELECT tasks.id, tasks.signin_id, tasks.title, tasks.due_date, tasks.priority,
             tasks.status, tasks.notes, tasks.created_at, Contacts.FirstName, Contacts.LastName, Contacts.Email,
             tasks.thank_you_selected, tasks.thank_you_date, tasks.thank_you_time,
             tasks.thank_you_send_now, tasks.follow_up_selected, tasks.follow_up_date,
               tasks.follow_up_time, tasks.follow_up_send_now, tasks.notes_email_selected,
                             tasks.notes_email_date, tasks.notes_email_time, tasks.notes_email_send_now,
                             tasks.task_type
        FROM tasks
        JOIN Contacts ON Contacts.LeadID = tasks.signin_id
        ORDER BY CASE tasks.status
            WHEN 'Pending' THEN 0 WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1
            WHEN 'Overdue' THEN 2 WHEN 'Completed' THEN 3 WHEN 'Canceled' THEN 4 ELSE 5
        END, tasks.due_date, tasks.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def list_dashboard_tasks():
    conn = get_conn()
    rows = conn.execute("""
           SELECT tasks.id, tasks.title, tasks.priority, tasks.status, tasks.notes,
               Contacts.FirstName, Contacts.LastName, Contacts.Email, tasks.task_type
        FROM tasks
         JOIN Contacts ON Contacts.LeadID = tasks.signin_id
        ORDER BY CASE tasks.status
            WHEN 'Pending' THEN 0 WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1
            WHEN 'Overdue' THEN 2 WHEN 'Completed' THEN 3 WHEN 'Canceled' THEN 4 ELSE 5
        END, tasks.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def _task_snapshot(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    columns = [column[1] for column in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    return dict(zip(columns, row))


def _write_task_history(conn, task_id, action, before, after, changed_by):
    snapshot = after or before or {}
    conn.execute("""
        INSERT INTO TaskHistory (TaskID, Action, TaskTitle, BeforeData, AfterData, ChangedBy)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        task_id, action, snapshot.get("title"),
        json.dumps(before, sort_keys=True) if before is not None else None,
        json.dumps(after, sort_keys=True) if after is not None else None,
        changed_by,
    ))


def list_task_history(limit=500):
    conn = get_conn()
    rows = conn.execute("""
        SELECT HistoryID, TaskID, Action, TaskTitle, BeforeData, AfterData, ChangedBy, ChangedAt
        FROM TaskHistory
        ORDER BY HistoryID DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    columns = ("history_id", "task_id", "action", "task_title", "before_data", "after_data", "changed_by", "changed_at")
    return [dict(zip(columns, row)) for row in rows]


def insert_task(values, changed_by=None):
    conn = get_conn()
    cursor = conn.execute("""
        INSERT INTO tasks (
            signin_id, agent_id, title, due_date, priority, task_type, status, notes,
            thank_you_selected, thank_you_date, thank_you_time, thank_you_send_now,
            follow_up_selected, follow_up_date, follow_up_time, follow_up_send_now,
            notes_email_selected, notes_email_date, notes_email_time, notes_email_send_now
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, values)
    task_id = cursor.lastrowid
    after = _task_snapshot(conn, task_id)
    _write_task_history(conn, task_id, "Created", None, after, changed_by)
    conn.commit()
    conn.close()
    return task_id


def update_task(values, task_id, changed_by=None):
    conn = get_conn()
    before = _task_snapshot(conn, task_id)
    conn.execute("""
        UPDATE tasks
        SET signin_id = ?, agent_id = ?, title = ?, due_date = ?, priority = ?, task_type = ?, status = ?, notes = ?,
            thank_you_selected = ?, thank_you_date = ?, thank_you_time = ?, thank_you_send_now = ?,
            follow_up_selected = ?, follow_up_date = ?, follow_up_time = ?, follow_up_send_now = ?,
            notes_email_selected = ?, notes_email_date = ?, notes_email_time = ?, notes_email_send_now = ?
        WHERE id = ?
    """, (*values, task_id))
    after = _task_snapshot(conn, task_id)
    if before is not None and after is not None:
        _write_task_history(conn, task_id, "Updated", before, after, changed_by)
    conn.commit()
    conn.close()


def delete_task(task_id, changed_by=None):
    conn = get_conn()
    before = _task_snapshot(conn, task_id)
    if before is not None:
        _write_task_history(conn, task_id, "Deleted", before, None, changed_by)
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def get_signin_email(signin_id):
    conn = get_conn()
    row = conn.execute("SELECT Email FROM Contacts WHERE LeadID = ?", (signin_id,)).fetchone()
    conn.close()
    return row


def get_signin_name_and_email(signin_id):
    conn = get_conn()
    row = conn.execute("SELECT FirstName, Email FROM Contacts WHERE LeadID = ?", (signin_id,)).fetchone()
    conn.close()
    return row


def get_due_task_rows():
    conn = get_conn()
    rows = conn.execute("""
        SELECT tasks.id, tasks.signin_id, tasks.notes,
               tasks.thank_you_selected, tasks.thank_you_date, tasks.thank_you_time, tasks.thank_you_sent,
               tasks.follow_up_selected, tasks.follow_up_date, tasks.follow_up_time, tasks.follow_up_sent,
               tasks.notes_email_selected, tasks.notes_email_date, tasks.notes_email_time, tasks.notes_email_sent,
             Contacts.Email
        FROM tasks
         JOIN Contacts ON Contacts.LeadID = tasks.signin_id
         WHERE Contacts.Email IS NOT NULL AND Contacts.Email != ''
    """).fetchall()
    conn.close()
    return rows


def mark_tasks_sent(task_id, updates):
    conn = get_conn()
    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
