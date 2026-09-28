from models.db import get_conn


FIELDS = (
    "AssignedAgentID", "BrokerID", "Address", "City", "State", "ZipCode", "Bedrooms", "Bathrooms",
    "TotalRooms", "SquareFeet", "LotSize", "YearBuilt", "PropertyType", "GarageSpaces", "HOAFees",
    "Pool", "Stories", "ParcelNumber", "ListingStatus", "ListingPrice", "SoldPrice", "DaysOnMarket",
    "MLSNumber", "ListingAgentName", "ListingBrokerName", "MainPhotoURL", "PhotoGalleryJSON",
    "VirtualTourURL", "FloorPlanURL", "OpenHouseID", "IsOpenHouseActive", "OpenHouseDate",
    "OpenHouseNotes", "PropertyNotes", "Tags", "IsCurrentHome",
)


def list_properties():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM Properties ORDER BY IsCurrentHome DESC, Address, City").fetchall()
    columns = [row[1] for row in conn.execute("PRAGMA table_info(Properties)").fetchall()]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def get_property(property_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM Properties WHERE PropertyID = ?", (property_id,)).fetchone()
    columns = [column[1] for column in conn.execute("PRAGMA table_info(Properties)").fetchall()]
    conn.close()
    return dict(zip(columns, row)) if row else None


def _sync_legacy_home(conn, property_id, values):
    legacy_id = values.get("LegacyPropertyID")
    conn.execute("""
        INSERT INTO homes (id, property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            property_id = excluded.property_id, agent_id = excluded.agent_id,
            broker_id = excluded.broker_id, address = excluded.address,
            city = excluded.city, state = excluded.state, zip_code = excluded.zip_code,
            rooms = excluded.rooms, lot_size = excluded.lot_size, is_current = excluded.is_current
    """, (
        property_id, legacy_id, values.get("AssignedAgentID"), values.get("BrokerID"),
        values.get("Address"), values.get("City"), values.get("State"), values.get("ZipCode"),
        values.get("TotalRooms"), values.get("LotSize"), values.get("IsCurrentHome", 0),
    ))


def _unset_current(conn):
    conn.execute("UPDATE Properties SET IsCurrentHome = 0")
    conn.execute("UPDATE homes SET is_current = 0")


def insert_property(values):
    fields = [field for field in FIELDS if field in values]
    if "LegacyPropertyID" in values:
        fields.append("LegacyPropertyID")
    conn = get_conn()
    if values.get("IsCurrentHome"):
        _unset_current(conn)
    cursor = conn.execute(
        f"INSERT INTO Properties ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        [values[field] for field in fields],
    )
    property_id = cursor.lastrowid
    _sync_legacy_home(conn, property_id, values)
    conn.commit()
    conn.close()
    return property_id


def update_property(property_id, values):
    fields = [field for field in FIELDS if field in values]
    if "LegacyPropertyID" in values:
        fields.append("LegacyPropertyID")
    assignments = ", ".join(f"{field} = ?" for field in fields)
    conn = get_conn()
    if values.get("IsCurrentHome"):
        _unset_current(conn)
    cursor = conn.execute(
        f"UPDATE Properties SET {assignments}, UpdatedAt = CURRENT_TIMESTAMP WHERE PropertyID = ?",
        [values[field] for field in fields] + [property_id],
    )
    if cursor.rowcount:
        property_values = conn.execute("SELECT * FROM Properties WHERE PropertyID = ?", (property_id,)).fetchone()
        columns = [column[1] for column in conn.execute("PRAGMA table_info(Properties)").fetchall()]
        _sync_legacy_home(conn, property_id, dict(zip(columns, property_values)))
        if "IsOpenHouseActive" in values:
            conn.execute(
                "UPDATE OpenHouseList SET IsOpenHouseActive = ? WHERE home_id = ?",
                (values["IsOpenHouseActive"], property_id),
            )
    conn.commit()
    conn.close()
    return bool(cursor.rowcount)


def delete_property(property_id):
    conn = get_conn()
    conn.execute("DELETE FROM homes WHERE id = ?", (property_id,))
    cursor = conn.execute("DELETE FROM Properties WHERE PropertyID = ?", (property_id,))
    conn.commit()
    conn.close()
    return bool(cursor.rowcount)


def list_homes_brief():
    return [
        {
            "id": row["PropertyID"],
            "property_id": row.get("LegacyPropertyID") or str(row["PropertyID"]),
            "address": row["Address"],
            "city": row["City"],
            "state": row["State"],
            "zip_code": row["ZipCode"],
            "is_current": row["IsCurrentHome"],
            "is_open_house_active": row["IsOpenHouseActive"],
        }
        for row in list_properties()
    ]


def set_home_current(home_id, is_current):
    conn = get_conn()
    cursor = conn.execute("SELECT PropertyID FROM Properties WHERE PropertyID = ?", (home_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    if is_current:
        _unset_current(conn)
    conn.execute("UPDATE Properties SET IsCurrentHome = ?, UpdatedAt = CURRENT_TIMESTAMP WHERE PropertyID = ?", (int(is_current), home_id))
    conn.execute("UPDATE homes SET is_current = ? WHERE id = ?", (int(is_current), home_id))
    conn.commit()
    conn.close()
    return True


def set_open_house_active(property_id, is_active):
    conn = get_conn()
    cursor = conn.execute(
        "UPDATE Properties SET IsOpenHouseActive = ?, UpdatedAt = CURRENT_TIMESTAMP WHERE PropertyID = ?",
        (int(is_active), property_id),
    )
    conn.execute("UPDATE OpenHouseList SET IsOpenHouseActive = ? WHERE home_id = ?", (int(is_active), property_id))
    conn.commit()
    conn.close()
    return bool(cursor.rowcount)