# shipping/server.py
import sys, os, uuid
from flask import Flask, request, jsonify
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.heartbeat import HeartbeatSender

app = Flask(__name__)
PORT = 5005
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:7000")
shipments = {}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "UP",
        "service": "shipping",
        "port": PORT,
        "pid": os.getpid()
    })

@app.route("/prepare", methods=["POST"])
def prepare():
    data = request.json
    txn_id = data["txn_id"]
    shipments[txn_id] = {
        "txn_id": txn_id,
        "product_id": data.get("product_id"),
        "quantity": data.get("quantity"),
        "status": "PENDING"
    }
    print(f"[SHIPPING] PREPARE OK for {txn_id}")
    return jsonify({"commit": True})

@app.route("/commit", methods=["POST"])
def commit():
    txn_id = request.json["txn_id"]
    if txn_id in shipments:
        shipments[txn_id]["status"] = "SHIPPED"
        shipments[txn_id]["tracking"] = f"TRK-{uuid.uuid4().hex[:8].upper()}"
        print(f"[SHIPPING] COMMITTED {txn_id} (Tracking: {shipments[txn_id]['tracking']})")
    return jsonify({"ok": True, "shipment": shipments.get(txn_id)})

@app.route("/abort", methods=["POST"])
def abort():
    txn_id = request.json["txn_id"]
    shipments.pop(txn_id, None)
    print(f"[SHIPPING] ABORTED {txn_id}")
    return jsonify({"ok": True})

@app.route("/shipments", methods=["GET"])
def list_shipments():
    return jsonify(list(shipments.values()))

if __name__ == "__main__":
    HeartbeatSender(f"http://localhost:{PORT}", COORDINATOR_URL).start()
    print(f"[SHIPPING] Server starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
