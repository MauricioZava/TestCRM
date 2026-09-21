import json


def categorize_and_score(visitor_type, timeline, preapproval, notes, currently):
    score = 0

    if visitor_type == "buyer":
        score += 40
    elif visitor_type == "seller":
        score += 35
    elif visitor_type == "neighbor":
        score += 20
    elif visitor_type == "just-looking":
        score += 10

    if timeline == "0-3":
        score += 40
    elif timeline == "3-6":
        score += 25
    elif timeline == "6-12":
        score += 15
    else:
        score += 5

    if preapproval == "yes":
        score += 20
    elif preapproval == "no":
        score += 5

    if currently == "renting":
        score += 10
    elif currently == "own":
        score += 5

    notes_lower = (notes or "").lower()
    for kw in ["serious", "ready", "offer", "listing", "sell", "buy"]:
        if kw in notes_lower:
            score += 10

    score = min(score, 100)

    followup = generate_followup(visitor_type)
    next_steps_json = generate_next_steps(visitor_type, score)

    return score, followup, next_steps_json


def generate_followup(visitor_type):
    if visitor_type == "buyer":
        return "Thanks for visiting today! Here’s more information about the home."
    elif visitor_type == "seller":
        return "Great meeting you! I can prepare a quick home value estimate."
    elif visitor_type == "neighbor":
        return "Thanks for stopping by! If you know anyone moving, I’d love to help."
    elif visitor_type == "just-looking":
        return "Thanks for visiting! If you ever have questions, I’m here to help."
    return "Thank you for visiting the open house today!"


def generate_next_steps(visitor_type, score):
    steps = []

    if visitor_type == "buyer":
        steps.append("Send property brochure and similar listings.")
        if score >= 60:
            steps.append("Offer to schedule a private showing.")
        steps.append("Provide financing/pre-approval guidance.")

    elif visitor_type == "seller":
        steps.append("Offer a free CMA.")
        if score >= 60:
            steps.append("Suggest a listing consultation.")
        steps.append("Send a seller guide.")

    elif visitor_type == "neighbor":
        steps.append("Send a friendly thank-you message.")
        steps.append("Share referral program details.")

    elif visitor_type == "just-looking":
        steps.append("Send a friendly thank-you message.")
        steps.append("Offer to answer future real estate questions.")

    return json.dumps([{"task": s, "done": False} for s in steps])
