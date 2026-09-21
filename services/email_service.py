import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText

from models.tasks import get_due_task_rows, mark_tasks_sent

SMTP_ENABLED = True
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "maury.zavala.68@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "zwmlarsyftfsccxo")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USERNAME)

_task_scheduler_started = False
_task_scheduler_lock = threading.Lock()


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


def process_due_task_emails():
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")

    for row in get_due_task_rows():
        task_id, notes = row[0], row[2] or ""
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

        if messages and send_email(row[15], "Open House Follow-Up", "\n\n".join(messages)):
            mark_tasks_sent(task_id, updates)


def start_task_scheduler():
    global _task_scheduler_started
    with _task_scheduler_lock:
        if _task_scheduler_started:
            return
        _task_scheduler_started = True

    def scheduler_loop():
        from extensions import app
        while True:
            try:
                process_due_task_emails()
            except Exception as error:
                app.logger.error("Task email scheduler failed: %s", error)
            time.sleep(30)

    threading.Thread(target=scheduler_loop, daemon=True, name="task-email-scheduler").start()
