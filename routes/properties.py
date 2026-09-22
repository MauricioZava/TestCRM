import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import request, redirect, url_for, render_template

from extensions import app
from models.homes import (
    list_homes, list_homes_brief, unset_current_home,
    insert_home, update_home, delete_home,
)
from models.agents import list_agents_brief
from models.brokers import list_brokers


@app.route("/properties", methods=["GET", "POST"])
def properties():
    if request.method == "POST":
        action = request.form.get("action", "add")
        home_id = request.form.get("home_id")

        if action == "delete" and home_id:
            delete_home(home_id)
            return redirect(url_for("properties"))

        if action in ("update", "delete") and not home_id:
            return redirect(url_for("properties"))

        property_id = request.form.get("property_id")
        address = request.form.get("address")
        city = request.form.get("city")
        state = request.form.get("state")
        zip_code = request.form.get("zip_code")
        rooms = request.form.get("rooms")
        lot_size = request.form.get("lot_size")
        agent_id = request.form.get("agent_id", type=int)
        broker_id = request.form.get("broker_id", type=int)
        is_current = 1 if request.form.get("is_current") == "on" else 0

        # If this home is marked current, unset all others
        if is_current == 1:
            unset_current_home()

        if action == "update" and home_id:
            update_home(home_id, property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current)
        else:
            insert_home(property_id, agent_id, broker_id, address, city, state, zip_code, rooms, lot_size, is_current)

        return redirect(url_for("properties"))

    homes = list_homes()
    agents = [
        {"id": row[0], "first_name": row[1], "middle_name": row[2], "last_name": row[3]}
        for row in list_agents_brief()
    ]

    return render_template("properties.html", homes=homes, agents=agents, brokers=list_brokers())


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
