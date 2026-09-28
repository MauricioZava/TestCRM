import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import request, redirect, url_for, render_template

from extensions import app
from models.properties import FIELDS, list_properties, insert_property, update_property, delete_property
from models.agents import list_agents_brief
from models.brokers import list_brokers


PROPERTY_FORM_SECTIONS = (
    ("Assignment and location", (
        ("AssignedAgentID", "Assigned Agent ID", "text"), ("BrokerID", "Broker ID", "text"),
        ("Address", "Address", "text"), ("City", "City", "text"),
        ("State", "State", "text"), ("ZipCode", "Zip Code", "text"),
    )),
    ("Property details", (
        ("Bedrooms", "Bedrooms", "number"), ("Bathrooms", "Bathrooms", "number"),
        ("TotalRooms", "Total Rooms", "text"), ("SquareFeet", "Square Feet", "number"),
        ("LotSize", "Lot Size", "text"), ("YearBuilt", "Year Built", "number"),
        ("PropertyType", "Property Type", "text"), ("GarageSpaces", "Garage Spaces", "number"),
        ("HOAFees", "HOA Fees", "number"), ("Pool", "Pool", "checkbox"),
        ("Stories", "Stories", "number"), ("ParcelNumber", "Parcel Number", "text"),
    )),
    ("Listing", (
        ("ListingStatus", "Listing Status", "text"), ("ListingPrice", "Listing Price", "number"),
        ("SoldPrice", "Sold Price", "number"), ("DaysOnMarket", "Days on Market", "number"),
        ("MLSNumber", "MLS Number", "text"), ("ListingAgentName", "Listing Agent Name", "text"),
        ("ListingBrokerName", "Listing Broker Name", "text"),
    )),
    ("Media", (
        ("MainPhotoURL", "Main Photo URL", "url"), ("PhotoGalleryJSON", "Photo Gallery JSON", "textarea"),
        ("VirtualTourURL", "Virtual Tour URL", "url"), ("FloorPlanURL", "Floor Plan URL", "url"),
    )),
    ("Open house", (
        ("OpenHouseID", "Open House ID", "text"),
        ("IsOpenHouseActive", "Open House Active", "checkbox"),
        ("OpenHouseDate", "Open House Date", "date"), ("OpenHouseNotes", "Open House Notes", "textarea"),
    )),
    ("Notes and status", (
        ("PropertyNotes", "Property Notes", "textarea"), ("Tags", "Tags", "text"),
        ("IsCurrentHome", "Current Home", "checkbox"),
    )),
)

INTEGER_FIELDS = {
    "Bedrooms", "SquareFeet", "YearBuilt", "GarageSpaces", "Stories", "DaysOnMarket",
}
DECIMAL_FIELDS = {"Bathrooms", "HOAFees", "ListingPrice", "SoldPrice"}
CHECKBOX_FIELDS = {"Pool", "IsOpenHouseActive", "IsCurrentHome"}


def property_form_values():
    values = {}
    for field in FIELDS:
        raw = request.form.get(field, "").strip()
        if field in CHECKBOX_FIELDS:
            values[field] = 1 if raw in ("on", "1", "true") else 0
        elif field in INTEGER_FIELDS:
            values[field] = int(raw) if raw else None
        elif field in DECIMAL_FIELDS:
            values[field] = float(raw) if raw else None
        else:
            values[field] = raw or None
    return values


@app.route("/properties", methods=["GET", "POST"])
def properties():
    if request.method == "POST":
        action = request.form.get("action", "add")
        property_id = request.form.get("property_id", type=int)

        if action == "delete" and property_id:
            delete_property(property_id)
            return redirect(url_for("properties"))

        if action in ("update", "delete") and not property_id:
            return redirect(url_for("properties"))

        values = property_form_values()
        values["LegacyPropertyID"] = request.form.get("LegacyPropertyID", "").strip() or None
        if action == "update" and property_id:
            update_property(property_id, values)
        else:
            insert_property(values)

        return redirect(url_for("properties"))

    properties_list = list_properties()
    agents = [
        {"id": row[0], "first_name": row[1], "middle_name": row[2], "last_name": row[3]}
        for row in list_agents_brief()
    ]

    return render_template(
        "properties.html", properties=properties_list, agents=agents, brokers=list_brokers(),
        form_sections=PROPERTY_FORM_SECTIONS,
    )


@app.route("/address_suggestions")
def address_suggestions():
    query = request.args.get("q", "").strip()
    if len(query) < 3:
        return {"results": []}

    params = urlencode({
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5,
        "countrycodes": "us",
    })
    api_request = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": "OpenHouseAgent/1.0 address lookup"},
    )

    try:
        with urlopen(api_request, timeout=10) as response:
            listings = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        app.logger.warning("Public address search failed: %s", error)
        return {"results": [], "error": "Address search is temporarily unavailable."}, 503

    results = []
    for listing in listings:
        address = listing.get("address", {})
        results.append({
            "property_id": f"osm-{listing.get('osm_type', '').lower()}-{listing.get('osm_id', '')}",
            "address": address.get("house_number", "") + " " + address.get("road", ""),
            "city": address.get("city") or address.get("town") or address.get("village") or "",
            "state": address.get("state", ""),
            "zip_code": address.get("postcode", ""),
            "display_name": listing.get("display_name", ""),
        })

    return {"results": results}
