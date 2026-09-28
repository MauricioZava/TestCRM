from models.db import get_conn
from models.properties import (
    delete_property, insert_property, list_homes_brief, list_properties,
    set_home_current, update_property,
)


def list_homes():
    return [
        (
            row["PropertyID"], row.get("LegacyPropertyID"), row.get("AssignedAgentID"),
            row.get("Address"), row.get("City"), row.get("State"), row.get("ZipCode"),
            row.get("TotalRooms"), row.get("LotSize"), row.get("IsCurrentHome"), row.get("BrokerID"),
        )
        for row in list_properties()
    ]


def unset_current_home():
    conn = get_conn()
    conn.execute("UPDATE Properties SET IsCurrentHome = 0")
    conn.execute("UPDATE homes SET is_current = 0")
    conn.commit()
    conn.close()


def insert_home(property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current):
    return insert_property({
        "LegacyPropertyID": property_id, "AssignedAgentID": agent_id, "BrokerID": broker_id,
        "Address": address, "City": city, "State": state, "ZipCode": zip_code,
        "TotalRooms": rooms, "LotSize": lot_size, "IsCurrentHome": is_current,
    })


def update_home(home_id, property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current):
    return update_property(home_id, {
        "LegacyPropertyID": property_id, "AssignedAgentID": agent_id, "BrokerID": broker_id,
        "Address": address, "City": city, "State": state, "ZipCode": zip_code,
        "TotalRooms": rooms, "LotSize": lot_size, "IsCurrentHome": is_current,
    })


def delete_home(home_id):
    return delete_property(home_id)
