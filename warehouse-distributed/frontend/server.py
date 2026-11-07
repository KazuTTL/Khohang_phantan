# frontend/server.py
"""
Frontend Web Gateway & Dashboard Server
Port: 8080
Provides:
- Web UI (Single Page Application)
- Cluster Orchestration (Start All, Stop All, Kill Node, Restart Node)
- Section 8.3 Demo APIs (Idempotency testing, Duplicate detection, Retry simulation)
- Real-time Aggregation (Stock across HN/DN/SG, Balances, Shipments, 2PC Logs)
"""
import sys, os, time, json, subprocess, requests
from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crash_injector.inject import SERVICES, get_node_status, kill_node, restart_node

app = Flask(__name__, template_folder="templates", static_folder="static")
PORT = 8080

COORDINATOR_URL = "http://127.0.0.1:7000"
WAREHOUSE_URLS = {
    "HN": "http://127.0.0.1:5001",
    "DN": "http://127.0.0.1:5002",
    "SG": "http://127.0.0.1:5003",
}
PAYMENT_URL = "http://127.0.0.1:5004"
SHIPPING_URL = "http://127.0.0.1:5005"

@app.route("/")
def index():
    return render_template("index.html")

# =============================================================================
# CLUSTER MONITORING & NODE MANAGEMENT
# =============================================================================

@app.route("/api/cluster/status", methods=["GET"])
def cluster_status():
    nodes = []
    all_up = True
    
    # 1. Coordinator
    coord_status = get_node_status("coordinator")
    nodes.append({
        "id": "coordinator",
        "name": "2PC Transaction Coordinator",
        "role": "Coordinator (Chương 8.3 & 8.5)",
        "port": 7000,
        "url": COORDINATOR_URL,
        "status": coord_status["status"],
        "pid": coord_status["pid"]
    })
    if coord_status["status"] != "ONLINE":
        all_up = False

    # 2. Warehouses
    for code in ["HN", "DN", "SG"]:
        st = get_node_status(code)
        wh_names = {"HN": "Kho Tổng Hà Nội", "DN": "Kho Miền Trung (Đà Nẵng)", "SG": "Kho Tổng TP.HCM"}
        nodes.append({
            "id": code,
            "name": wh_names.get(code, f"Kho {code}"),
            "role": f"Warehouse Participant ({code})",
            "port": SERVICES[code]["port"],
            "url": f"http://127.0.0.1:{SERVICES[code]['port']}",
            "status": st["status"],
            "pid": st["pid"]
        })
        if st["status"] != "ONLINE":
            all_up = False

    # 3. Payment
    pay_st = get_node_status("payment")
    nodes.append({
        "id": "payment",
        "name": "Dịch vụ Thanh toán (Payment)",
        "role": "Payment Participant",
        "port": 5004,
        "url": PAYMENT_URL,
        "status": pay_st["status"],
        "pid": pay_st["pid"]
    })
    if pay_st["status"] != "ONLINE":
        all_up = False

    # 4. Shipping
    ship_st = get_node_status("shipping")
    nodes.append({
        "id": "shipping",
        "name": "Dịch vụ Vận chuyển (Shipping)",
        "role": "Shipping Participant",
        "port": 5005,
        "url": SHIPPING_URL,
        "status": ship_st["status"],
        "pid": ship_st["pid"]
    })
    if ship_st["status"] != "ONLINE":
        all_up = False

    return jsonify({
        "nodes": nodes,
        "cluster_healthy": all_up,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/api/node/kill", methods=["POST"])
def api_kill_node():
    data = request.json or {}
    node_id = data.get("node_id")
    if not node_id:
        return jsonify({"ok": False, "error": "Thiếu node_id"}), 400
    success = kill_node(node_id)
    return jsonify({"ok": success, "node_id": node_id})

@app.route("/api/node/restart", methods=["POST"])
def api_restart_node():
    data = request.json or {}
    node_id = data.get("node_id")
    if not node_id:
        return jsonify({"ok": False, "error": "Thiếu node_id"}), 400
    success = restart_node(node_id)
    return jsonify({"ok": success, "node_id": node_id})

@app.route("/api/cluster/start_all", methods=["POST"])
def api_start_all():
    results = {}
    for s in ["HN", "DN", "SG", "payment", "shipping", "coordinator"]:
        st = get_node_status(s)
        if st["status"] == "OFFLINE":
            restart_node(s)
            results[s] = "STARTED"
        else:
            results[s] = "ALREADY_RUNNING"
    return jsonify({"ok": True, "results": results})

@app.route("/api/cluster/stop_all", methods=["POST"])
def api_stop_all():
    results = {}
    for s in ["coordinator", "HN", "DN", "SG", "payment", "shipping"]:
        st = get_node_status(s)
        if st["status"] == "ONLINE":
            kill_node(s)
            results[s] = "STOPPED"
        else:
            results[s] = "WAS_OFFLINE"
    return jsonify({"ok": True, "results": results})

# =============================================================================
# DATA AGGREGATION (STOCK, ACCOUNTS, SHIPMENTS, LOGS)
# =============================================================================

@app.route("/api/cluster/inventory", methods=["GET"])
def cluster_inventory():
    """Tổng hợp tồn kho toàn hệ thống từ 3 kho HN, DN, SG"""
    inventory = {"HN": [], "DN": [], "SG": []}
    for code, url in WAREHOUSE_URLS.items():
        try:
            r = requests.get(f"{url}/stock", timeout=1.5)
            if r.status_code == 200:
                inventory[code] = r.json()
        except Exception:
            inventory[code] = []
    return jsonify(inventory)

@app.route("/api/cluster/accounts", methods=["GET"])
def cluster_accounts():
    try:
        r = requests.get(f"{PAYMENT_URL}/accounts", timeout=1.5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass
    return jsonify([])

@app.route("/api/cluster/shipments", methods=["GET"])
def cluster_shipments():
    try:
        r = requests.get(f"{SHIPPING_URL}/shipments", timeout=1.5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass
    return jsonify([])

@app.route("/api/cluster/transactions", methods=["GET"])
def cluster_transactions():
    try:
        r = requests.get(f"{COORDINATOR_URL}/log", timeout=1.5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass
    return jsonify([])

@app.route("/api/cluster/idempotency", methods=["GET"])
def cluster_idempotency():
    try:
        r = requests.get(f"{COORDINATOR_URL}/idempotency/cache", timeout=1.5)
        if r.status_code == 200:
            return jsonify(r.json())
    except Exception:
        pass
    return jsonify({})

@app.route("/api/cluster/idempotency/clear", methods=["POST"])
def clear_idempotency():
    try:
        r = requests.post(f"{COORDINATOR_URL}/idempotency/clear", timeout=1.5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# ORDER & SECTION 8.3 RELIABLE RPC ENDPOINTS
# =============================================================================

@app.route("/api/order/submit", methods=["POST"])
def api_order_submit():
    """
    Gửi đơn hàng thông qua Coordinator với đầy đủ hỗ trợ Mục 8.3
    - Normal RPC
    - Duplicate Request (Kiểm thử At-Most-Once Idempotency)
    - Retry with Timeout (Mô phỏng xử lý Lost Request/Reply)
    """
    data = request.json or {}
    product_id = data.get("product_id", "SP001")
    quantity = int(data.get("quantity", 1))
    account = data.get("account", "alice")
    amount = float(data.get("amount", 250000))
    request_id = data.get("request_id")
    preferred_wh = data.get("preferred_warehouse")
    mode = data.get("mode", "normal") # "normal", "duplicate", "timeout_retry"

    start_time = time.time()
    
    # Kiểm tra xem Coordinator có sống không
    coord_st = get_node_status("coordinator")
    if coord_st["status"] != "ONLINE":
        return jsonify({
            "status": "ERROR",
            "reason": "coordinator_offline",
            "message": "Transaction Coordinator đang OFFLINE. Vui lòng bấm Khởi Động lại Coordinator!",
            "request_id": request_id
        }), 503

    payload = {
        "request_id": request_id,
        "product_id": product_id,
        "quantity": quantity,
        "account": account,
        "amount": amount,
        "preferred_warehouse": preferred_wh
    }

    try:
        # Nếu là chế độ timeout_retry, mô phỏng client retry 3 lần nếu có lỗi
        max_attempts = 3 if mode == "timeout_retry" else 1
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                r = requests.post(f"{COORDINATOR_URL}/order", json=payload, timeout=4)
                latency_ms = round((time.time() - start_time) * 1000, 1)
                res = r.json()
                res["latency_ms"] = latency_ms
                res["attempt"] = attempt
                return jsonify(res), r.status_code
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as ex:
                last_error = str(ex)
                if attempt < max_attempts:
                    time.sleep(1.0) # Backoff delay
                else:
                    break

        latency_ms = round((time.time() - start_time) * 1000, 1)
        return jsonify({
            "status": "ERROR",
            "reason": "connection_timeout_retries_exhausted",
            "message": f"Client đã thử lại {max_attempts} lần theo Mục 8.3.2 nhưng không nhận được phản hồi: {last_error}",
            "request_id": request_id,
            "latency_ms": latency_ms
        }), 504

    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "reason": "internal_error",
            "message": str(e),
            "request_id": request_id
        }), 500

@app.route("/api/seed_db", methods=["POST"])
def api_seed_db():
    """Nạp lại cơ sở dữ liệu mẫu ban đầu"""
    try:
        from database.seed_data import main as seed_main
        seed_main()
        return jsonify({"ok": True, "message": "Đã nạp lại dữ liệu thành công cho cả 3 kho!"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    print(f"[FRONTEND] Starting Web Dashboard on http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
