# warehouse/server.py
import sys, os, json
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_conn, init_warehouse_db
from common.checkpoint import CheckpointManager
from common.heartbeat import HeartbeatSender

app = Flask(__name__)

WAREHOUSE_NAME = os.getenv("WAREHOUSE_NAME", "HN")
PORT = int(os.getenv("PORT", "5001"))
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:7000")
DB_PATH = f"logs/warehouse_{WAREHOUSE_NAME}.db"

PRODUCTS = [
    {"id": "SP001", "name": "Áo polo nam Cotton", "quantity": 100},
    {"id": "SP002", "name": "Quần jeans nam Slimfit", "quantity": 60},
    {"id": "SP003", "name": "Giày Sneaker Running", "quantity": 50},
    {"id": "SP004", "name": "Balo Laptop chống nước", "quantity": 40},
    {"id": "SP005", "name": "Mũ lưỡi trai phong cách", "quantity": 80},
    {"id": "P001", "name": "Áo thun", "quantity": 100},
    {"id": "P002", "name": "Quần jean", "quantity": 50},
]
conn = init_warehouse_db(DB_PATH, PRODUCTS)

def get_state():
    rows = conn.execute("SELECT id, quantity, reserved FROM products").fetchall()
    return {r["id"]: {"quantity": r["quantity"], "reserved": r["reserved"]} for r in rows}

def set_state(state):
    for pid, v in state.items():
        conn.execute("UPDATE products SET quantity=?, reserved=? WHERE id=?",
                     (v["quantity"], v["reserved"], pid))
    conn.commit()

ckpt = CheckpointManager(f"warehouse_{WAREHOUSE_NAME}", get_state, set_state)

def replay_entry(entry):
    if entry.get("op") == "COMMIT" and entry.get("state") == "READY":
        p = entry.get("payload", {})
        if "product_id" in p:
            conn.execute("UPDATE products SET quantity=quantity-?, reserved=reserved-? WHERE id=?",
                         (p["quantity"], p["quantity"], p["product_id"]))
            conn.execute("UPDATE processed_txns SET result='COMMITTED' WHERE txn_id=?",
                         (entry["txn_id"],))
            conn.commit()

ckpt.recover(replay_entry)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "UP",
        "warehouse": WAREHOUSE_NAME,
        "port": PORT,
        "pid": os.getpid()
    })

@app.route("/prepare", methods=["POST"])
def prepare():
    data = request.json
    txn_id = data["txn_id"]
    product_id = data["product_id"]
    qty = data["quantity"]

    row = conn.execute("SELECT result FROM processed_txns WHERE txn_id=?", (txn_id,)).fetchone()
    if row:
        return jsonify({"commit": row["result"] in ("PREPARED", "COMMITTED")})

    row = conn.execute("SELECT quantity, reserved FROM products WHERE id=?", (product_id,)).fetchone()
    if not row or (row["quantity"] - row["reserved"]) < qty:
        conn.execute("INSERT OR REPLACE INTO processed_txns (txn_id, operation, result) VALUES (?,?,?)", (txn_id, "ORDER_PREPARE", "ABORT"))
        conn.execute("INSERT INTO message_log (txn_id, operation, payload, state) VALUES (?,?,?,?)",
                     (txn_id, "PREPARE", json.dumps(data), "VOTE_ABORT"))
        conn.commit()
        ckpt.log_operation(txn_id, "PREPARE", data, "VOTE_ABORT")
        return jsonify({"commit": False, "reason": "out_of_stock"})

    conn.execute("UPDATE products SET reserved = reserved + ? WHERE id=?", (qty, product_id))
    conn.execute("INSERT OR REPLACE INTO processed_txns (txn_id, operation, result) VALUES (?,?,?)", (txn_id, "ORDER_PREPARE", "PREPARED"))
    conn.execute("INSERT INTO message_log (txn_id, operation, payload, state) VALUES (?,?,?,?)",
                 (txn_id, "PREPARE", json.dumps(data), "READY"))
    conn.commit()
    ckpt.log_operation(txn_id, "PREPARE", data, "READY")
    print(f"[{WAREHOUSE_NAME}] PREPARE OK for {txn_id} (Reserved: {qty} {product_id})")
    return jsonify({"commit": True})

@app.route("/commit", methods=["POST"])
def commit():
    txn_id = request.json["txn_id"]
    row = conn.execute("SELECT result FROM processed_txns WHERE txn_id=?", (txn_id,)).fetchone()
    if row and row["result"] == "COMMITTED":
        return jsonify({"ok": True})

    log_row = conn.execute("SELECT payload FROM message_log WHERE txn_id=? AND state='READY'",
                           (txn_id,)).fetchone()
    if log_row:
        p = json.loads(log_row["payload"])
        conn.execute("UPDATE products SET quantity=quantity-?, reserved=reserved-? WHERE id=?",
                     (p["quantity"], p["quantity"], p["product_id"]))
        conn.execute("UPDATE processed_txns SET result='COMMITTED' WHERE txn_id=?", (txn_id,))
        conn.execute("UPDATE message_log SET state='COMMITTED' WHERE txn_id=?", (txn_id,))
        conn.commit()
        ckpt.log_operation(txn_id, "COMMIT", {}, "COMMITTED")
        print(f"[{WAREHOUSE_NAME}] COMMITTED {txn_id} (Deducted: {p['quantity']} {p['product_id']})")
    return jsonify({"ok": True})

@app.route("/abort", methods=["POST"])
def abort():
    txn_id = request.json["txn_id"]
    log_row = conn.execute("SELECT payload FROM message_log WHERE txn_id=? AND state='READY'",
                           (txn_id,)).fetchone()
    if log_row:
        p = json.loads(log_row["payload"])
        conn.execute("UPDATE products SET reserved = reserved - ? WHERE id=?",
                     (p["quantity"], p["product_id"]))
    conn.execute("UPDATE processed_txns SET result='ABORTED' WHERE txn_id=?", (txn_id,))
    conn.execute("UPDATE message_log SET state='ABORTED' WHERE txn_id=?", (txn_id,))
    conn.commit()
    ckpt.log_operation(txn_id, "ABORT", {}, "ABORTED")
    print(f"[{WAREHOUSE_NAME}] ABORTED {txn_id}")
    return jsonify({"ok": True})

@app.route("/stock", methods=["GET"])
def stock():
    rows = conn.execute("SELECT id, name, quantity, reserved FROM products").fetchall()
    return jsonify([
        {
            "id": r["id"],
            "name": r["name"],
            "quantity": r["quantity"],
            "reserved": r["reserved"],
            "available": r["quantity"] - r["reserved"]
        } for r in rows
    ])

if __name__ == "__main__":
    HeartbeatSender(f"http://localhost:{PORT}", COORDINATOR_URL).start()
    print(f"[{WAREHOUSE_NAME}] Warehouse starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
