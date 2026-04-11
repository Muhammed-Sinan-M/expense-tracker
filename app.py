import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── Serve frontend ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("index.html")


# ─── USERS ────────────────────────────────────────────────────────────────────
@app.route("/api/users", methods=["GET"])
def get_users():
    res = supabase.table("users").select("*").execute()
    return jsonify(res.data)


@app.route("/api/users/<user_id>", methods=["PATCH"])
def update_user(user_id):
    body = request.get_json()
    allowed = {k: v for k, v in body.items() if k in ("name", "avatar_url", "balance")}
    res = supabase.table("users").update(allowed).eq("id", user_id).execute()
    return jsonify(res.data)


# ─── EXPENSES ─────────────────────────────────────────────────────────────────
@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    user_id = request.args.get("user_id")
    query = supabase.table("expenses").select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    res = query.execute()
    return jsonify(res.data)


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    body = request.get_json()
    required = ("title", "amount", "user_id")
    if not all(k in body for k in required):
        return jsonify({"error": "Missing required fields: title, amount, user_id"}), 400
    try:
        amount = float(body["amount"])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a positive number"}), 400

    payload = {
        "title": str(body["title"]).strip(),
        "amount": amount,
        "user_id": body["user_id"],
        "created_at": body.get("created_at", datetime.now(timezone.utc).isoformat()),
    }
    res = supabase.table("expenses").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.route("/api/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    supabase.table("expenses").delete().eq("id", expense_id).execute()
    return jsonify({"message": "Deleted"}), 200


# ─── RECEIVABLES ──────────────────────────────────────────────────────────────
@app.route("/api/receivables", methods=["GET"])
def get_receivables():
    user_id = request.args.get("user_id")
    query = (
        supabase.table("receivables")
        .select("*")
        .order("created_at", desc=True)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    res = query.execute()
    return jsonify(res.data)


@app.route("/api/receivables", methods=["POST"])
def add_receivable():
    body = request.get_json()
    required = ("person", "amount", "user_id")
    if not all(k in body for k in required):
        return jsonify({"error": "Missing required fields: person, amount, user_id"}), 400
    try:
        amount = float(body["amount"])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a positive number"}), 400

    payload = {
        "person": str(body["person"]).strip(),
        "amount": amount,
        "note": str(body.get("note", "")).strip() or None,
        "user_id": body["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = supabase.table("receivables").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.route("/api/receivables/<receivable_id>", methods=["DELETE"])
def delete_receivable(receivable_id):
    supabase.table("receivables").delete().eq("id", receivable_id).execute()
    return jsonify({"message": "Deleted"}), 200


# ─── DEBTS ────────────────────────────────────────────────────────────────────
@app.route("/api/debts", methods=["GET"])
def get_debts():
    user_id = request.args.get("user_id")
    query = (
        supabase.table("debts")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    res = query.execute()
    return jsonify(res.data)


@app.route("/api/debts", methods=["POST"])
def add_debt():
    body = request.get_json()
    required = ("person", "amount", "user_id")
    if not all(k in body for k in required):
        return jsonify({"error": "Missing required fields: person, amount, user_id"}), 400
    try:
        amount = float(body["amount"])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a positive number"}), 400

    payload = {
        "person": str(body["person"]).strip(),
        "amount": amount,
        "note": str(body.get("note", "")).strip() or None,
        "user_id": body["user_id"],
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = supabase.table("debts").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.route("/api/debts/<debt_id>/pay", methods=["POST"])
def mark_debt_paid(debt_id):
    debt_res = supabase.table("debts").select("*").eq("id", debt_id).single().execute()
    debt = debt_res.data

    if not debt:
        return jsonify({"error": "Debt not found"}), 404
    if debt["status"] == "paid":
        return jsonify({"error": "Debt already marked as paid"}), 400

    supabase.table("debts").update({"status": "paid"}).eq("id", debt_id).execute()

    expense_payload = {
        "title": f"Paid {debt['person']}",
        "amount": debt["amount"],
        "user_id": debt["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    exp_res = supabase.table("expenses").insert(expense_payload).execute()

    return jsonify({"message": "Debt paid", "expense": exp_res.data[0]}), 200


@app.route("/api/debts/<debt_id>", methods=["DELETE"])
def delete_debt(debt_id):
    supabase.table("debts").delete().eq("id", debt_id).execute()
    return jsonify({"message": "Deleted"}), 200


# ─── SUMMARY ──────────────────────────────────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
def get_summary():
    exp_res = supabase.table("expenses").select("user_id, amount").execute()
    debt_res = supabase.table("debts").select("user_id, amount").eq("status", "pending").execute()
    recv_res = supabase.table("receivables").select("user_id, amount").execute()

    totals = {}
    for row in exp_res.data:
        uid = row["user_id"]
        totals.setdefault(uid, {"expense_total": 0, "debt_total": 0, "receivable_total": 0})
        totals[uid]["expense_total"] += row["amount"]
    for row in debt_res.data:
        uid = row["user_id"]
        totals.setdefault(uid, {"expense_total": 0, "debt_total": 0, "receivable_total": 0})
        totals[uid]["debt_total"] += row["amount"]
    for row in recv_res.data:
        uid = row["user_id"]
        totals.setdefault(uid, {"expense_total": 0, "debt_total": 0, "receivable_total": 0})
        totals[uid]["receivable_total"] += row["amount"]

    return jsonify(totals)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
