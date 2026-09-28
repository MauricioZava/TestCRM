from models.db import get_conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            visitor_type TEXT,
            currently TEXT,
            working_with_broker TEXT,
            zip_code TEXT,
            heard_about_us TEXT,
            is_contact INTEGER DEFAULT 0,
            dashboard_hidden INTEGER DEFAULT 0,
            timeline TEXT,
            preapproval TEXT,
            notes TEXT,
            motivation_score INTEGER,
            followup_message TEXT,
            next_steps_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(signins)").fetchall()}
    for column in ("working_with_broker", "zip_code", "heard_about_us", "is_contact", "dashboard_hidden", "agent_id", "open_house_id", "contact_id", "first_name", "last_name", "alternate_phone", "preferred_contact_method", "best_time_to_contact", "contact_time_of_day", "lead_status", "property_type", "bedrooms", "preferred_areas"):
        if column not in existing_columns:
            column_type = "INTEGER" if column in ("agent_id", "open_house_id", "contact_id") else "INTEGER DEFAULT 0" if column == "is_contact" else "TEXT"
            if column == "dashboard_hidden":
                column_type = "INTEGER DEFAULT 0"
            c.execute(f"ALTER TABLE signins ADD COLUMN {column} {column_type}")

    # One-time backfill: split any legacy full "name" values into first_name / last_name.
    if "first_name" not in existing_columns or "last_name" not in existing_columns:
        legacy_rows = c.execute(
            "SELECT id, name FROM signins WHERE name IS NOT NULL AND name != '' "
            "AND (first_name IS NULL OR first_name = '')"
        ).fetchall()
        for row_id, full_name in legacy_rows:
            parts = full_name.strip().split(" ", 1)
            first = parts[0] if parts else ""
            last = parts[1] if len(parts) > 1 else ""
            c.execute("UPDATE signins SET first_name = ?, last_name = ? WHERE id = ?", (first, last, row_id))

    conn.commit()
    conn.close()


def init_contacts_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Contacts (
            LeadID INTEGER PRIMARY KEY AUTOINCREMENT,
            FirstName TEXT,
            LastName TEXT,
            Email TEXT,
            Phone TEXT,
            SecondaryPhone TEXT,
            PreferredContactMethod TEXT,
            LeadSource TEXT,
            CampaignID INTEGER,
            ReferralName TEXT,
            ReferralType TEXT,
            InitialContactDate TEXT,
            LeadCreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            LeadStatus TEXT,
            LeadScore INTEGER,
            LastContactDate TEXT,
            NextFollowUpDate TEXT,
            AssignedAgentID INTEGER,
            PriorityLevel TEXT,
            DesiredCity TEXT,
            DesiredNeighborhood TEXT,
            DesiredZipCode TEXT,
            PropertyType TEXT,
            BedsMin INTEGER,
            BathsMin REAL,
            SqFtMin INTEGER,
            BudgetMin REAL,
            BudgetMax REAL,
            PreApproved INTEGER,
            LenderName TEXT,
            PreApprovalAmount REAL,
            PropertyAddress TEXT,
            City TEXT,
            State TEXT,
            ZipCode TEXT,
            EstimatedHomeValue REAL,
            ReasonForSelling TEXT,
            TimelineToSell TEXT,
            Notes TEXT,
            LastCommunicationType TEXT,
            LastCommunicationSummary TEXT,
            NumberOfTouches INTEGER DEFAULT 0,
            Tags TEXT,
            CreatedByUserID INTEGER,
            UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            LeadOwnerTeamID INTEGER,
            IsArchived INTEGER DEFAULT 0,
            IsConverted INTEGER DEFAULT 0,
            ConvertedDate TEXT,
            ConvertedToContactID INTEGER,
            LeadPhotoURL TEXT,
            SocialMediaLinks TEXT
        )
    """)
    conn.execute("""
        INSERT INTO Contacts (
            LeadID, FirstName, LastName, Email, Phone, SecondaryPhone, PreferredContactMethod,
            LeadSource, InitialContactDate, LeadCreatedAt, LeadStatus, LeadScore, AssignedAgentID,
            DesiredNeighborhood, DesiredZipCode, PropertyType, BedsMin, PreApproved, TimelineToSell,
            Notes, LastCommunicationSummary, NumberOfTouches, IsArchived
        )
        SELECT signins.id, signins.first_name, signins.last_name, signins.email, signins.phone,
            signins.alternate_phone, signins.preferred_contact_method, signins.heard_about_us,
            signins.created_at, signins.created_at, signins.lead_status, signins.motivation_score,
            signins.agent_id, signins.preferred_areas, signins.zip_code, signins.property_type,
            CASE WHEN signins.bedrooms GLOB '[0-9]*' THEN CAST(signins.bedrooms AS INTEGER) END,
            CASE WHEN lower(signins.preapproval) = 'yes' THEN 1 ELSE 0 END, signins.timeline,
            signins.notes, signins.followup_message, 0, 0
        FROM signins
        WHERE signins.is_contact = 1
            AND NOT EXISTS (SELECT 1 FROM Contacts WHERE Contacts.LeadID = signins.id)
    """)
    conn.execute("""
        UPDATE signins
        SET contact_id = id
        WHERE is_contact = 1 AND contact_id IS NULL
            AND EXISTS (SELECT 1 FROM Contacts WHERE Contacts.LeadID = signins.id)
    """)
    max_signin_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM signins").fetchone()[0]
    sequence = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'Contacts'").fetchone()
    if sequence:
        conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'Contacts'", (max_signin_id,))
    elif max_signin_id:
        conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('Contacts', ?)", (max_signin_id,))
    conn.commit()
    conn.close()


def init_homes_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS homes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            rooms TEXT,
            lot_size TEXT,
            is_current INTEGER DEFAULT 0
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(homes)").fetchall()}
    for column in ("rooms", "lot_size", "agent_id", "broker_id"):
        if column not in existing_columns:
            column_type = "INTEGER" if column in ("agent_id", "broker_id") else "TEXT"
            c.execute(f"ALTER TABLE homes ADD COLUMN {column} {column_type}")
    c.execute("""
        CREATE TABLE IF NOT EXISTS Properties (
            PropertyID INTEGER PRIMARY KEY AUTOINCREMENT,
            AssignedAgentID INTEGER,
            BrokerID INTEGER,
            Address TEXT,
            City TEXT,
            State TEXT,
            ZipCode TEXT,
            Bedrooms INTEGER,
            Bathrooms REAL,
            TotalRooms TEXT,
            SquareFeet INTEGER,
            LotSize TEXT,
            YearBuilt INTEGER,
            PropertyType TEXT,
            GarageSpaces INTEGER,
            HOAFees REAL,
            Pool INTEGER DEFAULT 0,
            Stories INTEGER,
            ParcelNumber TEXT,
            ListingStatus TEXT,
            ListingPrice REAL,
            SoldPrice REAL,
            DaysOnMarket INTEGER,
            MLSNumber TEXT,
            ListingAgentName TEXT,
            ListingBrokerName TEXT,
            MainPhotoURL TEXT,
            PhotoGalleryJSON TEXT,
            VirtualTourURL TEXT,
            FloorPlanURL TEXT,
            OpenHouseID INTEGER,
            IsOpenHouseActive INTEGER DEFAULT 0,
            OpenHouseDate TEXT,
            OpenHouseNotes TEXT,
            PropertyNotes TEXT,
            Tags TEXT,
            IsCurrentHome INTEGER DEFAULT 0,
            CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            LegacyPropertyID TEXT
        )
    """)
    c.execute("""
        INSERT INTO Properties (
            PropertyID, AssignedAgentID, BrokerID, Address, City, State, ZipCode,
            TotalRooms, LotSize, IsCurrentHome, LegacyPropertyID
        )
        SELECT homes.id, homes.agent_id, homes.broker_id, homes.address, homes.city,
            homes.state, homes.zip_code, homes.rooms, homes.lot_size, homes.is_current,
            homes.property_id
        FROM homes
        WHERE NOT EXISTS (SELECT 1 FROM Properties WHERE Properties.PropertyID = homes.id)
    """)
    max_home_id = c.execute("SELECT COALESCE(MAX(id), 0) FROM homes").fetchone()[0]
    property_sequence = c.execute("SELECT seq FROM sqlite_sequence WHERE lower(name) = 'properties'").fetchone()
    if property_sequence:
        c.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE lower(name) = 'properties'", (max_home_id,))
    elif max_home_id:
        c.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('Properties', ?)", (max_home_id,))
    conn.commit()
    conn.close()


def init_agents_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            mobile_phone TEXT,
            office_phone TEXT,
            broker_id INTEGER,
            office_id INTEGER,
            team_id INTEGER,
            brokerage TEXT,
            license_number TEXT,
            license_state TEXT,
            license_expiration_date TEXT,
            mls_id TEXT,
            nrds_id TEXT,
            agent_type TEXT,
            years_experience INTEGER,
            status TEXT,
            preferred_contact_method TEXT,
            agent_tags TEXT,
            social_media_links TEXT,
            x_com_profile TEXT,
            profile_photo_url TEXT,
            office_address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            website TEXT,
            specialties TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(agents)").fetchall()}
    agent_columns = {
        "first_name": "TEXT",
        "middle_name": "TEXT",
        "last_name": "TEXT",
        "email": "TEXT",
        "phone": "TEXT",
        "mobile_phone": "TEXT",
        "office_phone": "TEXT",
        "broker_id": "INTEGER",
        "office_id": "INTEGER",
        "team_id": "INTEGER",
        "brokerage": "TEXT",
        "license_number": "TEXT",
        "license_state": "TEXT",
        "license_expiration_date": "TEXT",
        "mls_id": "TEXT",
        "nrds_id": "TEXT",
        "agent_type": "TEXT",
        "years_experience": "INTEGER",
        "status": "TEXT",
        "preferred_contact_method": "TEXT",
        "agent_tags": "TEXT",
        "social_media_links": "TEXT",
        "x_com_profile": "TEXT",
        "profile_photo_url": "TEXT",
        "office_address": "TEXT",
        "city": "TEXT",
        "state": "TEXT",
        "zip_code": "TEXT",
        "website": "TEXT",
        "specialties": "TEXT",
        "notes": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    for column, column_type in agent_columns.items():
        if column not in existing_columns:
            c.execute(f"ALTER TABLE agents ADD COLUMN {column} {column_type}")
    c.execute("UPDATE agents SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    c.execute("UPDATE agents SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    conn.commit()
    conn.close()


def init_brokers_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            office_address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            website TEXT,
            notes TEXT,
            license_number TEXT,
            license_state TEXT,
            license_expiration_date TEXT,
            mls_id TEXT,
            nrds_id TEXT,
            broker_type TEXT,
            years_experience INTEGER,
            office_id INTEGER,
            is_primary_broker INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            preferred_contact_method TEXT,
            tags TEXT,
            social_media_links TEXT,
            profile_photo_url TEXT
        )
    """)
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(brokers)").fetchall()}
    broker_columns = {
        "first_name": "TEXT",
        "last_name": "TEXT",
        "license_number": "TEXT",
        "license_state": "TEXT",
        "license_expiration_date": "TEXT",
        "mls_id": "TEXT",
        "nrds_id": "TEXT",
        "broker_type": "TEXT",
        "years_experience": "INTEGER",
        "office_id": "INTEGER",
        "is_primary_broker": "INTEGER DEFAULT 0",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "status": "TEXT",
        "preferred_contact_method": "TEXT",
        "tags": "TEXT",
        "social_media_links": "TEXT",
        "profile_photo_url": "TEXT",
    }
    for column, column_type in broker_columns.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE brokers ADD COLUMN {column} {column_type}")
    conn.execute("UPDATE brokers SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    conn.execute("UPDATE brokers SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    conn.commit()
    conn.close()


def init_tasks_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signin_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'Normal',
            status TEXT NOT NULL DEFAULT 'Open',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (signin_id) REFERENCES signins (id)
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
    for column in (
        "thank_you_selected", "thank_you_date", "thank_you_time", "thank_you_send_now",
        "follow_up_selected", "follow_up_date", "follow_up_time", "follow_up_send_now",
        "notes_email_selected", "notes_email_date", "notes_email_time", "notes_email_send_now",
        "thank_you_sent", "follow_up_sent", "notes_email_sent", "agent_id", "task_type"
    ):
        if column not in existing_columns:
            column_type = "INTEGER DEFAULT 0" if column.endswith("selected") or column.endswith("send_now") or column.endswith("sent") else "INTEGER" if column == "agent_id" else "TEXT"
            c.execute(f"ALTER TABLE tasks ADD COLUMN {column} {column_type}")
    conn.commit()
    conn.close()


def init_task_types_table():
    task_types = (
        "Call", "Email", "Text", "Showing", "Open House Prep", "Document Request",
        "Contract Review", "Follow-up", "Closing Prep", "Inspection Coordination",
        "Appraisal Coordination", "Listing Prep", "Marketing Task", "Social Media Post",
        "Lead Qualification", "Lead Nurture", "Custom",
    )
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS TaskTypes (
            TaskTypeID INTEGER PRIMARY KEY AUTOINCREMENT,
            TaskTypeName TEXT NOT NULL UNIQUE
        )
    """)
    conn.executemany(
        "INSERT OR IGNORE INTO TaskTypes (TaskTypeName) VALUES (?)",
        ((task_type,) for task_type in task_types),
    )
    conn.commit()
    conn.close()


def init_task_history_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS TaskHistory (
            HistoryID INTEGER PRIMARY KEY AUTOINCREMENT,
            TaskID INTEGER,
            Action TEXT NOT NULL,
            TaskTitle TEXT,
            BeforeData TEXT,
            AfterData TEXT,
            ChangedBy TEXT,
            ChangedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_history_changed_at ON TaskHistory (ChangedAt DESC)")
    conn.commit()
    conn.close()


def init_open_houses_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS open_houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_id INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            visitor_capacity TEXT,
            rsvp_contact TEXT,
            public_notes TEXT,
            internal_notes TEXT,
            FOREIGN KEY (home_id) REFERENCES Properties (PropertyID),
            FOREIGN KEY (agent_id) REFERENCES agents (id)
        )
    """)
    existing_columns = {row[1] for row in c.execute("PRAGMA table_info(open_houses)").fetchall()}
    open_house_columns = (
        "title", "status", "visitor_capacity", "rsvp_contact",
        "public_notes", "internal_notes"
    )
    for column in open_house_columns:
        if column not in existing_columns:
            column_type = "TEXT NOT NULL DEFAULT 'Scheduled'" if column == "status" else "TEXT"
            c.execute(f"ALTER TABLE open_houses ADD COLUMN {column} {column_type}")
    c.execute("""
        CREATE TABLE IF NOT EXISTS OpenHouseList (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_id INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            visitor_capacity TEXT,
            rsvp_contact TEXT,
            public_notes TEXT,
            internal_notes TEXT,
            IsOpenHouseActive INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (home_id) REFERENCES Properties (PropertyID),
            FOREIGN KEY (agent_id) REFERENCES agents (id)
        )
    """)
    existing_list_columns = {
        row[1] for row in c.execute("PRAGMA table_info(OpenHouseList)").fetchall()
    }
    if "IsOpenHouseActive" not in existing_list_columns:
        c.execute(
            "ALTER TABLE OpenHouseList ADD COLUMN IsOpenHouseActive INTEGER NOT NULL DEFAULT 0"
        )
    c.execute("""
        INSERT OR IGNORE INTO OpenHouseList (
            id, home_id, agent_id, event_date, start_time, end_time, title, status,
            visitor_capacity, rsvp_contact, public_notes, internal_notes, IsOpenHouseActive
        )
        SELECT oh.id, oh.home_id, oh.agent_id, oh.event_date, oh.start_time, oh.end_time,
            oh.title, oh.status, oh.visitor_capacity, oh.rsvp_contact, oh.public_notes,
            oh.internal_notes, COALESCE(p.IsOpenHouseActive, 0)
        FROM open_houses AS oh
        LEFT JOIN Properties AS p ON p.PropertyID = oh.home_id
    """)
    c.execute("""
        UPDATE OpenHouseList
        SET IsOpenHouseActive = COALESCE(
            (SELECT IsOpenHouseActive FROM Properties WHERE PropertyID = OpenHouseList.home_id),
            0
        )
    """)
    conn.commit()
    conn.close()


def backfill_signin_open_houses():
    conn = get_conn()
    conn.execute("""
        UPDATE signins
        SET open_house_id = (
            SELECT id FROM open_houses
            WHERE status = 'Scheduled'
            ORDER BY event_date ASC, start_time ASC
            LIMIT 1
        )
        WHERE open_house_id IS NULL
    """)
    conn.execute("""
        UPDATE signins
        SET agent_id = (
            SELECT agent_id FROM open_houses
            WHERE open_houses.id = signins.open_house_id
        )
        WHERE agent_id IS NULL AND open_house_id IS NOT NULL
    """)
    conn.commit()
    conn.close()


def init_all():
    init_db()
    init_contacts_table()
    init_homes_table()
    init_agents_table()
    init_brokers_table()
    init_open_houses_table()
    backfill_signin_open_houses()
    init_tasks_table()
    init_task_types_table()
    init_task_history_table()
    init_task_types_table()
