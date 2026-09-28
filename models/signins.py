from models.db import get_conn


def get_scoring_fields(signin_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT visitor_type, timeline, preapproval, currently
        FROM signins
        WHERE id = ?
    """, (signin_id,)).fetchone()
    conn.close()
    return row


def get_full_scoring_fields(signin_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT visitor_type, timeline, preapproval, currently, notes
        FROM signins
        WHERE id = ?
    """, (signin_id,)).fetchone()
    conn.close()
    return row


def update_notes(signin_id, notes, motivation_score, followup_message, next_steps_json):
    conn = get_conn()
    conn.execute("""
        UPDATE signins
        SET notes = ?, motivation_score = ?, followup_message = ?, next_steps_json = ?
        WHERE id = ?
    """, (notes, motivation_score, followup_message, next_steps_json, signin_id))
    conn.commit()
    conn.close()
    conn = get_conn()
    conn.execute("""
        UPDATE Contacts
        SET Notes = ?, LeadScore = ?, LastCommunicationSummary = ?, UpdatedAt = CURRENT_TIMESTAMP
        WHERE LeadID = (SELECT contact_id FROM signins WHERE id = ?)
    """, (notes, motivation_score, followup_message, signin_id))
    conn.commit()
    conn.close()


def hide_signin(signin_id):
    conn = get_conn()
    conn.execute("UPDATE signins SET dashboard_hidden = 1 WHERE id = ?", (signin_id,))
    conn.commit()
    conn.close()


def export_rows():
    conn = get_conn()
    rows = conn.execute("""
         SELECT id, first_name, last_name, email, phone, visitor_type, currently,
             property_type, bedrooms, preferred_areas,
             working_with_broker, zip_code, heard_about_us, timeline,
             preapproval, notes, motivation_score, followup_message,
             next_steps_json, created_at
        FROM signins
        ORDER BY motivation_score DESC, created_at DESC
    """).fetchall()
    conn.close()
    return rows


def insert_signin(data):
    conn = get_conn()
    conn.execute("""
        INSERT INTO signins (
            first_name, last_name, email, phone, alternate_phone, best_time_to_contact, contact_time_of_day, visitor_type, currently, property_type, bedrooms, preferred_areas, working_with_broker,
            zip_code, heard_about_us, timeline, preapproval, notes, agent_id, open_house_id,
            motivation_score, followup_message, next_steps_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()
    conn.close()


def get_contact_carryover_agent(signin_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT COALESCE(
            open_houses.agent_id,
            signins.agent_id,
            (
                SELECT scheduled.agent_id
                FROM open_houses AS scheduled
                WHERE scheduled.status = 'Scheduled'
                ORDER BY scheduled.event_date ASC, scheduled.start_time ASC
                LIMIT 1
            )
        )
        FROM signins
        LEFT JOIN open_houses ON open_houses.id = signins.open_house_id
        WHERE signins.id = ?
    """, (signin_id,)).fetchone()
    conn.close()
    return row


def mark_as_contact(signin_id, motivation_score, followup_message, next_steps_json, agent_id):
    conn = get_conn()
    conn.execute("""
        UPDATE signins
        SET is_contact = 1, motivation_score = ?, followup_message = ?, next_steps_json = ?, agent_id = ?
        WHERE id = ?
    """, (motivation_score, followup_message, next_steps_json, agent_id, signin_id))
    conn.commit()
    conn.close()
    conn = get_conn()
    row = conn.execute("""
        SELECT contact_id, first_name, last_name, email, phone, alternate_phone, preferred_contact_method,
            heard_about_us, lead_status, motivation_score, agent_id, preferred_areas, zip_code,
            property_type, bedrooms, preapproval, timeline, notes, created_at
        FROM signins WHERE id = ?
    """, (signin_id,)).fetchone()
    conn.close()
    if row:
        from models.contacts import insert_contact, upsert_signin_contact
        values = {
            "FirstName": row[1], "LastName": row[2], "Email": row[3], "Phone": row[4],
            "SecondaryPhone": row[5], "PreferredContactMethod": row[6], "LeadSource": row[7],
            "LeadStatus": row[8], "LeadScore": motivation_score, "AssignedAgentID": agent_id,
            "DesiredNeighborhood": row[11], "DesiredZipCode": row[12], "PropertyType": row[13],
            "BedsMin": int(row[14]) if str(row[14] or "").isdigit() else None,
            "PreApproved": 1 if row[15] == "yes" else 0, "TimelineToSell": row[16],
            "Notes": row[17], "InitialContactDate": row[18], "LastCommunicationSummary": followup_message,
        }
        if row[0]:
            upsert_signin_contact(row[0], values)
        else:
            lead_id = insert_contact(values)
            conn = get_conn()
            conn.execute("UPDATE signins SET contact_id = ? WHERE id = ?", (lead_id, signin_id))
            conn.commit()
            conn.close()


def insert_contact(data):
    conn = get_conn()
    conn.execute("""
        INSERT INTO signins (
            first_name, last_name, email, phone, alternate_phone, preferred_contact_method, best_time_to_contact, lead_status,
            visitor_type, currently, property_type, bedrooms, preferred_areas, working_with_broker,
            zip_code, heard_about_us, is_contact, timeline, preapproval, notes,
            motivation_score, followup_message, next_steps_json, agent_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()
    conn.close()


def soft_delete_contact(signin_id):
    conn = get_conn()
    conn.execute("UPDATE signins SET is_contact = 0, dashboard_hidden = 1 WHERE id = ?", (signin_id,))
    conn.commit()
    conn.close()


def list_contacts():
    conn = get_conn()
    rows = conn.execute("""
         SELECT signins.id, signins.first_name, signins.last_name, signins.email, signins.phone, signins.alternate_phone,
             signins.preferred_contact_method, signins.best_time_to_contact, signins.lead_status,
             signins.visitor_type, signins.currently,
             signins.property_type, signins.bedrooms, signins.preferred_areas,
             signins.working_with_broker, signins.zip_code, signins.heard_about_us, signins.timeline,
             signins.preapproval, signins.notes, signins.motivation_score, signins.followup_message,
             signins.next_steps_json, signins.created_at,
             agents.first_name, agents.middle_name, agents.last_name
        FROM signins
        LEFT JOIN agents ON agents.id = signins.agent_id
        WHERE signins.is_contact = 1
        ORDER BY signins.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def list_dashboard_signins():
    conn = get_conn()
    rows = conn.execute("""
         SELECT signins.id, signins.first_name, signins.last_name, signins.email, signins.phone, signins.alternate_phone, signins.best_time_to_contact, signins.visitor_type, signins.currently,
             signins.property_type, signins.bedrooms, signins.preferred_areas,
             signins.working_with_broker, signins.zip_code, signins.heard_about_us, signins.is_contact, signins.dashboard_hidden, signins.timeline,
             signins.preapproval, signins.notes, signins.motivation_score, signins.followup_message,
             signins.next_steps_json, signins.created_at, agents.first_name, agents.middle_name, agents.last_name
               , signins.contact_time_of_day
        FROM signins
        LEFT JOIN open_houses ON open_houses.id = signins.open_house_id
        LEFT JOIN agents ON agents.id = COALESCE(
            open_houses.agent_id,
            signins.agent_id,
            (
                SELECT scheduled.agent_id
                FROM open_houses AS scheduled
                WHERE scheduled.status = 'Scheduled'
                ORDER BY scheduled.event_date ASC, scheduled.start_time ASC
                LIMIT 1
            )
        )
                 WHERE signins.dashboard_hidden = 0
                     AND (signins.preferred_contact_method IS NULL OR signins.preferred_contact_method = '')
        ORDER BY signins.motivation_score DESC, signins.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def get_contact(signin_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT id, first_name, last_name, email, phone, alternate_phone, preferred_contact_method, best_time_to_contact, lead_status,
               visitor_type, currently, property_type, bedrooms, preferred_areas,
               working_with_broker, zip_code, heard_about_us,
               timeline, preapproval, notes, agent_id
        FROM signins
        WHERE id = ?
    """, (signin_id,)).fetchone()
    conn.close()
    return row


def update_contact(signin_id, data):
    conn = get_conn()
    conn.execute("""
        UPDATE signins
        SET first_name = ?, last_name = ?, email = ?, phone = ?, alternate_phone = ?,
            preferred_contact_method = ?, best_time_to_contact = ?, lead_status = ?, visitor_type = ?, currently = ?,
            property_type = ?, bedrooms = ?, preferred_areas = ?,
            working_with_broker = ?, zip_code = ?, heard_about_us = ?,
            timeline = ?, preapproval = ?, notes = ?, motivation_score = ?,
            followup_message = ?, next_steps_json = ?, agent_id = ?
        WHERE id = ?
    """, (*data, signin_id))
    conn.commit()
    conn.close()


def get_email_and_followup(signin_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT Email, LastCommunicationSummary
        FROM Contacts
        WHERE LeadID = ?
    """, (signin_id,)).fetchone()
    conn.close()
    return row


def get_email(signin_id):
    conn = get_conn()
    row = conn.execute("SELECT Email FROM Contacts WHERE LeadID = ?", (signin_id,)).fetchone()
    conn.close()
    return row
