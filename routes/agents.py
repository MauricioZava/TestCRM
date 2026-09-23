from flask import request, redirect, url_for, render_template

from extensions import app
from models.agents import FIELDS, list_agents, get_agent, insert_agent, update_agent, delete_agent
from models.brokers import list_brokers


@app.route("/agents")
def agents():
    return render_template("agents.html", agents=list_agents())


@app.route("/agents/new", methods=["GET", "POST"])
def create_agent():
    if request.method == "GET":
        agent = {field: "" for field in FIELDS}
        agent["name"] = ""
        return render_template("edit_agent.html", agent=agent, brokers=list_brokers(), is_new=True)

    fields = [request.form.get(name, "").strip() for name in FIELDS]
    insert_agent(fields)
    return redirect(url_for("agents"))


@app.route("/agents/<int:agent_id>", methods=["GET", "POST"])
def edit_agent(agent_id):
    if request.method == "POST":
        fields = [request.form.get(name, "").strip() for name in FIELDS]
        update_agent(fields, agent_id)
        return redirect(url_for("agents"))

    agent = get_agent(agent_id)
    if not agent:
        return "Agent not found.", 404
    return render_template("edit_agent.html", agent=agent, brokers=list_brokers(), is_new=False)


@app.route("/agents/delete/<int:agent_id>", methods=["POST"])
def remove_agent(agent_id):
    delete_agent(agent_id)
    return redirect(url_for("agents"))
