from flask import request, redirect, url_for, render_template

from extensions import app
from models.agents import FIELDS, list_agents, insert_agent, update_agent, delete_agent


@app.route("/agents", methods=["GET", "POST"])
def agents():
    if request.method == "POST":
        action = request.form.get("action", "add")
        agent_id = request.form.get("agent_id")

        if action == "delete" and agent_id:
            delete_agent(agent_id)
            return redirect(url_for("agents"))

        if action in ("update", "delete") and not agent_id:
            return redirect(url_for("agents"))

        fields = [request.form.get(name, "").strip() for name in FIELDS]

        if action == "update":
            update_agent(fields, agent_id)
        else:
            insert_agent(fields)

        return redirect(url_for("agents"))

    return render_template("agents.html", agents=list_agents())
