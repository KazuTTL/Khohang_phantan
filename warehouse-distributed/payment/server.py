# payment/server.py
import sys, os
from flask import Flask, request, jsonify
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_conn
from common.heartbeat import HeartbeatSender

app = Flask(__name__)
PORT = 5004
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:7000")
DB = "logs/payment.db"
os.makedirs("logs", exist_ok=True)
conn = get_conn(DB)

conn.execute("CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, balance REAL)")
conn.execute("""CREATE TABLE IF NOT EXISTS reservations (
    txn_id TEXT PRIMARY KEY, account TEXT, amount REAL)""")
conn.execute("INSERT OR IGNORE INTO accounts VALUES ('alice', 10000000.0)")
conn.execute("INSERT OR IGNORE INTO accounts VALUES ('bob', 5000000.0)")
conn.execute("UPDATE accounts SET balance = 10000000.0 WHERE id = 'alice' AND balance < 10000")
conn.execute("UPDATE accounts SET balance = 5000000.0 WHERE id = 'bob' AND balance < 10000")
conn.commit()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "UP",
        "service": "payment",
        "port": PORT,
        "pid": os.getpid()
    })

@app.route("/prepare", methods=["POST"])
def prepare():
    data = request.json
    txn_id, account, amount = data["txn_id"], data["account"], data["amount"]
    r = conn.execute("SELECT account FROM reservations WHERE txn_id=?", (txn_id,)).fetchone()
    if r:
        return jsonify({"commit": True})
    row = conn.execute("SELECT balance FROM accounts WHERE id=?", (account,)).fetchone()
    if not row or row["balance"] < amount:
        print(f"[PAYMENT] PREPARE REJECTED for {txn_id} (Insufficient funds for {account})")
        return jsonify({"commit": False, "reason": "insufficient_funds"})
    conn.execute("INSERT INTO reservations VALUES (?,?,?)", (txn_id, account, amount))
    conn.commit()
    print(f"[PAYMENT] PREPARE OK for {txn_id} (Reserved {amount} from {account})")
    return jsonify({"commit": True})

@app.route("/commit", methods=["POST"])
def commit():
    txn_id = request.json["txn_id"]
    r = conn.execute("SELECT account, amount FROM reservations WHERE txn_id=?", (txn_id,)).fetchone()
    if r:
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE id=?", (r["amount"], r["account"]))
        conn.execute("DELETE FROM reservations WHERE txn_id=?", (txn_id,))
        conn.commit()
        print(f"[PAYMENT] COMMITTED {txn_id} (Deducted {r['amount']} from {r['account']})")
    return jsonify({"ok": True})

@app.route("/abort", methods=["POST"])
def abort():
    txn_id = request.json["txn_id"]
    conn.execute("DELETE FROM reservations WHERE txn_id=?", (txn_id,))
    conn.commit()
    print(f"[PAYMENT] ABORTED {txn_id}")
    return jsonify({"ok": True})

@app.route("/balance/<account>", methods=["GET"])
def balance(account):
    r = conn.execute("SELECT balance FROM accounts WHERE id=?", (account,)).fetchone()
    return jsonify({"account": account, "balance": r["balance"] if r else None})

@app.route("/accounts", methods=["GET"])
def list_accounts():
    rows = conn.execute("SELECT id, balance FROM accounts").fetchall()
    return jsonify([{"account": r["id"], "balance": r["balance"]} for r in rows])

if __name__ == "__main__":
    HeartbeatSender(f"http://localhost:{PORT}", COORDINATOR_URL).start()
    print(f"[PAYMENT] Server starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
