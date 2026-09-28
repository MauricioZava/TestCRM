from models.db import get_conn


FIELDS = (
    "FirstName", "LastName", "Email", "Phone", "SecondaryPhone", "PreferredContactMethod",
    "LeadSource", "CampaignID", "ReferralName", "ReferralType", "InitialContactDate",
    "LeadStatus", "LeadScore", "LastContactDate", "NextFollowUpDate", "AssignedAgentID",
    "PriorityLevel", "DesiredCity", "DesiredNeighborhood", "DesiredZipCode", "PropertyType",
    "BedsMin", "BathsMin", "SqFtMin", "BudgetMin", "BudgetMax", "PreApproved", "LenderName",
    "PreApprovalAmount", "PropertyAddress", "City", "State", "ZipCode", "EstimatedHomeValue",
    "ReasonForSelling", "TimelineToSell", "Notes", "LastCommunicationType",
    "LastCommunicationSummary", "NumberOfTouches", "Tags", "CreatedByUserID", "LeadOwnerTeamID",
    "IsArchived", "IsConverted", "ConvertedDate", "ConvertedToContactID", "LeadPhotoURL",
    "SocialMediaLinks",
)


def list_contacts():
    conn = get_conn()
    rows = conn.execute("""
        SELECT Contacts.*, agents.first_name, agents.middle_name, agents.last_name
        FROM Contacts
        LEFT JOIN agents ON agents.id = Contacts.AssignedAgentID
        WHERE Contacts.IsArchived = 0
        ORDER BY Contacts.LeadCreatedAt DESC, Contacts.LeadID DESC
    """).fetchall()
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Contacts)").fetchall()]
    conn.close()
    return [dict(zip((*columns, "agent_first_name", "agent_middle_name", "agent_last_name"), row)) for row in rows]


def get_contact(lead_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM Contacts WHERE LeadID = ? AND IsArchived = 0", (lead_id,)).fetchone()
    columns = [column[1] for column in conn.execute("PRAGMA table_info(Contacts)").fetchall()]
    conn.close()
    return dict(zip(columns, row)) if row else None


def insert_contact(values):
    fields = [field for field in FIELDS if field in values]
    conn = get_conn()
    cursor = conn.execute(
        f"INSERT INTO Contacts ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        [values[field] for field in fields],
    )
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def update_contact(lead_id, values):
    fields = [field for field in FIELDS if field in values]
    assignments = ", ".join(f"{field} = ?" for field in fields)
    conn = get_conn()
    conn.execute(
        f"UPDATE Contacts SET {assignments}, UpdatedAt = CURRENT_TIMESTAMP WHERE LeadID = ?",
        [values[field] for field in fields] + [lead_id],
    )
    conn.commit()
    conn.close()


def archive_contact(lead_id):
    conn = get_conn()
    conn.execute("UPDATE Contacts SET IsArchived = 1, UpdatedAt = CURRENT_TIMESTAMP WHERE LeadID = ?", (lead_id,))
    conn.execute("UPDATE signins SET is_contact = 0, dashboard_hidden = 1 WHERE contact_id = ?", (lead_id,))
    conn.commit()
    conn.close()


def upsert_signin_contact(lead_id, values):
    fields = [field for field in FIELDS if field in values]
    columns = ["LeadID", *fields]
    updates = ", ".join(f"{field} = excluded.{field}" for field in fields)
    conn = get_conn()
    conn.execute(
        f"INSERT INTO Contacts ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
        f"ON CONFLICT(LeadID) DO UPDATE SET {updates}, IsArchived = 0, UpdatedAt = CURRENT_TIMESTAMP",
        [lead_id, *[values[field] for field in fields]],
    )
    conn.commit()
    conn.close()


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