# coordinator/server.py
"""
Distributed Transaction Coordinator (2PC) & Section 8.3 Reliable Client-Server Communication
- Tuân thủ Section 8.3 (Reliable client-server communication):
  + Idempotency key / Deduplication: At-Most-Once semantics chống thực thi lặp khi mất reply
  + Heartbeat & Node failure detection
  + Write-Ahead Log (WAL) lưu trữ trạng thái 2PC (PREPARE, COMMIT, ABORT)
"""
import sys, os, uuid, json, requests, time, threading
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

PORT = 7000
WAREHOUSES = {
    "HN": {"name": "Kho Hà Nội", "url": "http://127.0.0.1:5001"},
    "DN": {"name": "Kho Đà Nẵng", "url": "http://127.0.0.1:5002"},
    "SG": {"name": "Kho TP.HCM", "url": "http://127.0.0.1:5003"},
}
PAYMENT = {"name": "Dịch vụ Thanh toán", "url": "http://127.0.0.1:5004"}
SHIPPING = {"name": "Dịch vụ Vận chuyển", "url": "http://127.0.0.1:5005"}

os.makedirs("logs", exist_ok=True)
LOG_FILE = "logs/coordinator_log.jsonl"
IDEMPOTENCY_FILE = "logs/idempotency_store.json"

last_seen = {}
lock = threading.RLock()

# Load cached idempotency store (Mục 8.3: At-most-once semantics)
idempotency_store = {}
if os.path.exists(IDEMPOTENCY_FILE):
    try:
        with open(IDEMPOTENCY_FILE, "r", encoding="utf-8") as f:
            idempotency_store = json.load(f)
    except Exception:
        idempotency_store = {}

def save_idempotency():
    with lock:
        try:
            with open(IDEMPOTENCY_FILE, "w", encoding="utf-8") as f:
                json.dump(idempotency_store, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[COORDINATOR] Error saving idempotency: {e}")

def log_2pc(txn_id, request_id, state, extra=None):
    entry = {
        "txn": txn_id,
        "request_id": request_id,
        "state": state,
        "extra": extra,
        "ts": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    url = request.json.get("url")
    if url:
        with lock:
            last_seen[url] = time.time()
    return jsonify({"ok": True})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "UP",
        "service": "coordinator",
        "port": PORT,
        "pid": os.getpid()
    })

@app.route("/nodes", methods=["GET"])
def list_nodes():
    """Kiểm tra sức khỏe toàn bộ các node phân tán qua heartbeat"""
    now = time.time()
    nodes = []

    # Coordinator
    nodes.append({
        "id": "coordinator",
        "name": "Transaction Coordinator",
        "role": "2PC Leader / Arbiter",
        "port": PORT,
        "url": f"http://127.0.0.1:{PORT}",
        "status": "ONLINE",
        "pid": os.getpid(),
        "last_seen_sec": 0
    })

    # Warehouses
    for code, info in WAREHOUSES.items():
        url = info["url"]
        seen_sec = round(now - last_seen.get(url, last_seen.get(url.replace("127.0.0.1", "localhost"), 0)), 1)
        is_online = (seen_sec < 5.0)

        nodes.append({
            "id": f"warehouse_{code}",
            "code": code,
            "name": info["name"],
            "role": "Warehouse Participant",
            "port": int(url.split(":")[-1]),
            "url": url,
            "status": "ONLINE" if is_online else "OFFLINE",
            "last_seen_sec": seen_sec if not is_online else 0
        })

    # Payment
    p_url = PAYMENT["url"]
    p_seen = round(now - last_seen.get(p_url, last_seen.get(p_url.replace("127.0.0.1", "localhost"), 0)), 1)
    p_online = (p_seen < 5.0)
    nodes.append({
        "id": "payment",
        "name": PAYMENT["name"],
        "role": "Payment Participant",
        "port": 5004,
        "url": p_url,
        "status": "ONLINE" if p_online else "OFFLINE",
        "last_seen_sec": p_seen if not p_online else 0
    })

    # Shipping
    s_url = SHIPPING["url"]
    s_seen = round(now - last_seen.get(s_url, last_seen.get(s_url.replace("127.0.0.1", "localhost"), 0)), 1)
    s_online = (s_seen < 5.0)
    nodes.append({
        "id": "shipping",
        "name": SHIPPING["name"],
        "role": "Shipping Participant",
        "port": 5005,
        "url": s_url,
        "status": "ONLINE" if s_online else "OFFLINE",
        "last_seen_sec": s_seen if not s_online else 0
    })

    return jsonify({"nodes": nodes, "cluster_healthy": all(n["status"] == "ONLINE" for n in nodes)})

def choose_warehouse(product_id, quantity, preferred_wh=None):
    """Tìm kho có đủ hàng để xử lý đơn (ưu tiên kho được chọn nếu có)"""
    candidate_order = list(WAREHOUSES.items())
    if preferred_wh and preferred_wh in WAREHOUSES:
        # Move preferred to front
        candidate_order = [(preferred_wh, WAREHOUSES[preferred_wh])] + [
            item for item in candidate_order if item[0] != preferred_wh
        ]

    for name, info in candidate_order:
        url = info["url"]
        try:
            r = requests.get(f"{url}/stock", timeout=2)
            if r.status_code == 200:
                for p in r.json():
                    avail = p.get("available", p.get("quantity", 0) - p.get("reserved", 0))
                    if p["id"] == product_id and avail >= quantity:
                        return name, url
        except Exception:
            continue
    return None, None

@app.route("/order", methods=["POST"])
def order():
    """
    Xử lý đặt hàng phân tán qua 2PC
    Mục 8.3: Kiểm tra Idempotency Key (At-Most-Once RPC Semantics)
    """
    data = request.json or {}
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))
    account = data.get("account", "alice")
    amount = float(data.get("amount", 100))
    preferred_wh = data.get("preferred_warehouse")

    # Mục 8.3.2: Nhận Request ID / Idempotency Key từ Client
    request_id = data.get("request_id") or data.get("idempotency_key")
    if not request_id:
        request_id = f"REQ-{uuid.uuid4().hex[:12].upper()}"

    # KIỂM TRA DEDUPLICATION (Mục 8.3 At-Most-Once Semantics):
    # Nếu Request ID đã từng thực hiện thành công/thất bại, trả về ngay kết quả đã lưu!
    with lock:
        if request_id in idempotency_store:
            cached = idempotency_store[request_id]
            print(f"[COORDINATOR] [IDEMPOTENT HIT] Request {request_id} already processed at {cached.get('time_str')}! Returning cached response.")
            return jsonify({
                **cached,
                "is_duplicate": True,
                "message": "At-Most-Once Semantics: Yêu cầu này đã được xử lý trước đó, hệ thống không thực hiện lại!"
            })

    # Tìm kho phù hợp
    wh_name, wh_url = choose_warehouse(product_id, quantity, preferred_wh)
    if not wh_url:
        result = {
            "status": "FAILED",
            "request_id": request_id,
            "reason": "out_of_stock_all_warehouses",
            "message": f"Hết hàng trên toàn bộ hệ thống kho cho sản phẩm {product_id}."
        }
        with lock:
            idempotency_store[request_id] = {**result, "time_str": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_idempotency()
        return jsonify(result), 400

    txn_id = str(uuid.uuid4())
    log_2pc(txn_id, request_id, "PREPARE_PHASE_STARTED", {"warehouse": wh_name, "product": product_id, "qty": quantity})

    # =========================================================================
    # PHASE 1: PREPARE (Bình chọn giao dịch)
    # =========================================================================
    votes = {}
    details = {}

    # 1. Warehouse Prepare
    try:
        r = requests.post(f"{wh_url}/prepare", json={"txn_id": txn_id, "product_id": product_id, "quantity": quantity}, timeout=3)
        res = r.json() if r.status_code == 200 else {}
        votes["warehouse"] = res.get("commit", False)
        details["warehouse"] = res
    except Exception as e:
        votes["warehouse"] = False
        details["warehouse"] = {"error": str(e)}

    # 2. Payment Prepare
    try:
        r = requests.post(f"{PAYMENT['url']}/prepare", json={"txn_id": txn_id, "account": account, "amount": amount}, timeout=3)
        res = r.json() if r.status_code == 200 else {}
        votes["payment"] = res.get("commit", False)
        details["payment"] = res
    except Exception as e:
        votes["payment"] = False
        details["payment"] = {"error": str(e)}

    # 3. Shipping Prepare
    try:
        r = requests.post(f"{SHIPPING['url']}/prepare", json={"txn_id": txn_id, "product_id": product_id, "quantity": quantity}, timeout=3)
        res = r.json() if r.status_code == 200 else {}
        votes["shipping"] = res.get("commit", False)
        details["shipping"] = res
    except Exception as e:
        votes["shipping"] = False
        details["shipping"] = {"error": str(e)}

    # =========================================================================
    # PHASE 2: COMMIT / ABORT (Quyết định toàn cục)
    # =========================================================================
    if all(votes.values()):
        # Tất cả đồng ý -> GLOBAL COMMIT
        log_2pc(txn_id, request_id, "GLOBAL_COMMIT", {"votes": votes, "warehouse": wh_name})
        shipping_res = {}
        for part_url in [wh_url, PAYMENT["url"], SHIPPING["url"]]:
            try:
                resp = requests.post(f"{part_url}/commit", json={"txn_id": txn_id}, timeout=3)
                if "5005" in part_url and resp.status_code == 200:
                    shipping_res = resp.json().get("shipment", {})
            except Exception as e:
                print(f"[COORDINATOR] Commit notify error for {part_url}: {e}")

        response_payload = {
            "status": "SUCCESS",
            "request_id": request_id,
            "txn_id": txn_id,
            "warehouse": wh_name,
            "product_id": product_id,
            "quantity": quantity,
            "account": account,
            "amount": amount,
            "votes": votes,
            "tracking": shipping_res.get("tracking", "N/A"),
            "is_duplicate": False,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Lưu lại idempotency cache (Mục 8.3)
        with lock:
            idempotency_store[request_id] = response_payload
            save_idempotency()

        return jsonify(response_payload)
    else:
        # Có ít nhất 1 node từ chối hoặc lỗi -> GLOBAL ABORT
        log_2pc(txn_id, request_id, "GLOBAL_ABORT", {"votes": votes, "details": details})
        for part_url in [wh_url, PAYMENT["url"], SHIPPING["url"]]:
            try:
                requests.post(f"{part_url}/abort", json={"txn_id": txn_id}, timeout=3)
            except Exception:
                pass

        fail_reason = "transaction_aborted"
        if not votes.get("warehouse"):
            fail_reason = "warehouse_rejected"
        elif not votes.get("payment"):
            fail_reason = "payment_rejected_insufficient_balance"
        elif not votes.get("shipping"):
            fail_reason = "shipping_rejected"

        response_payload = {
            "status": "FAILED",
            "request_id": request_id,
            "txn_id": txn_id,
            "reason": fail_reason,
            "votes": votes,
            "details": details,
            "is_duplicate": False,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        with lock:
            idempotency_store[request_id] = response_payload
            save_idempotency()

        return jsonify(response_payload), 400

@app.route("/log", methods=["GET"])
def get_log():
    if not os.path.exists(LOG_FILE):
        return jsonify([])
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    lines.reverse() # Mới nhất lên đầu
    return jsonify(lines[:100])

@app.route("/idempotency/cache", methods=["GET"])
def get_idempotency_cache():
    return jsonify(idempotency_store)

@app.route("/idempotency/clear", methods=["POST"])
def clear_idempotency_cache():
    global idempotency_store
    with lock:
        idempotency_store = {}
        save_idempotency()
    return jsonify({"ok": True, "message": "Idempotency cache cleared"})

if __name__ == "__main__":
    print(f"[COORDINATOR] Starting 2PC Coordinator on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
