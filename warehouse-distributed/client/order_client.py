# client/order_client.py
"""
Reliable Client for Distributed Warehouse System
Tuân thủ Giáo trình Hệ phân tán - Mục 8.3 (Reliable client-server communication)
- 8.3.1 Point-to-point communication & RPC semantics under failures
- 8.3.2 Xử lý mất gói tin (Lost Request / Lost Reply): Retries với Timeout & Exponential Backoff
- 8.3.2 Đảm bảo ngữ nghĩa At-Most-Once bằng Idempotency Key (Request ID)
"""
import sys, os, uuid, time, requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

COORDINATOR = os.getenv("COORDINATOR_URL", "http://127.0.0.1:7000")

class ReliableOrderClient:
    def __init__(self, coordinator_url=COORDINATOR, max_retries=3, timeout_sec=5.0, backoff_factor=1.5):
        self.coordinator_url = coordinator_url
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec
        self.backoff_factor = backoff_factor

    def send_order_reliable(self, product_id, quantity, account, amount, request_id=None, preferred_warehouse=None):
        """
        Gửi yêu cầu đặt hàng với cơ chế Tin Cậy (Mục 8.3):
        - Nếu request_id không được truyền vào, tự động sinh UUID đại diện cho Idempotency Key.
        - Khi gặp sự cố mạng (Timeout, Connection refused): tự động Thử lại (Retry) với exponential backoff.
        - Phía Coordinator dùng request_id này để đảm bảo At-Most-Once (không xử lý lại 2 lần).
        """
        if not request_id:
            request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

        payload = {
            "request_id": request_id,
            "product_id": product_id,
            "quantity": quantity,
            "account": account,
            "amount": amount,
            "preferred_warehouse": preferred_warehouse
        }

        print(f"\n[CLIENT] >>> Gửi đơn hàng (Request ID: {request_id})")
        print(f"         Sản phẩm: {product_id} x {quantity} | Tài khoản: {account} ({amount} VNĐ)")

        current_delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"[CLIENT] Lần thử {attempt}/{self.max_retries}: Đang gửi RPC tới Coordinator ({self.coordinator_url}/order)...")
                r = requests.post(f"{self.coordinator_url}/order", json=payload, timeout=self.timeout_sec)
                
                res = r.json()
                if r.status_code == 200:
                    if res.get("is_duplicate"):
                        print(f"[CLIENT] [THÀNH CÔNG - IDEMPOTENT] Server đã nhận diện trùng lặp! Trả kết quả cache, không bị trừ tiền/hàng 2 lần.")
                    else:
                        print(f"[CLIENT] [THÀNH CÔNG] Đơn hàng đã hoàn tất qua 2PC! Txn ID: {res.get('txn_id')}")
                    return res
                else:
                    print(f"[CLIENT] [TỪ CHỐI] Server phản hồi lỗi: {res.get('reason')} - {res.get('message')}")
                    return res

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                print(f"[CLIENT] [LỖI MẠNG/TIMEOUT] Lần thử {attempt} thất bại ({type(e).__name__}).")
                if attempt < self.max_retries:
                    print(f"[CLIENT] Áp dụng Mục 8.3.2: Chờ {current_delay:.1f}s trước khi gửi lại...")
                    time.sleep(current_delay)
                    current_delay *= self.backoff_factor
                else:
                    print(f"[CLIENT] Đã thử {self.max_retries} lần nhưng không kết nối được Coordinator.")
                    return {"status": "ERROR", "reason": "server_unreachable_after_retries", "request_id": request_id}

    def simulate_duplicate_requests(self, product_id="SP001", quantity=1, account="alice", amount=200):
        """
        Mô phỏng tình huống Lost Reply trong Mục 8.3:
        1. Gửi request lần 1 -> Thành công
        2. Client tưởng mạng rớt nên gửi lại y nguyên cùng Request ID lần 2
        3. Kiểm tra xem Coordinator có trừ tiền & trừ hàng 2 lần hay chỉ trả kết quả cũ
        """
        fixed_request_id = f"TEST-DUP-{uuid.uuid4().hex[:6].upper()}"
        print("\n" + "="*70)
        print(f"MÔ PHỎNG MỤC 8.3: GỬI TRÙNG LẶP (DUPLICATE REQUEST / LOST REPLY)")
        print(f"Idempotency Key sử dụng: {fixed_request_id}")
        print("="*70)

        # Lần 1
        print("\n--- BƯỚC 1: GỬI LẦN ĐẦU TIÊN ---")
        res1 = self.send_order_reliable(product_id, quantity, account, amount, request_id=fixed_request_id)

        # Lần 2 (Giả lập Client bị mất gói phản hồi hoặc bấm đúp)
        print("\n--- BƯỚC 2: GỬI LẠI CÙNG REQUEST ID (GIẢ LẬP MẤT REPLY) ---")
        res2 = self.send_order_reliable(product_id, quantity, account, amount, request_id=fixed_request_id)

        print("\n" + "="*70)
        print("KẾT LUẬN KIỂM CHỨNG MỤC 8.3:")
        if res2.get("is_duplicate") is True:
            print(">>> ĐẠT CHUẨN MỤC 8.3: Hệ thống kích hoạt At-Most-Once Semantics!")
            print("    Hệ thống phát hiện Request ID đã xử lý và KHÔNG trừ kho / trừ tiền lần 2.")
        else:
            print(">>> CẢNH BÁO: Chưa xử lý trùng lặp đúng cách!")
        print("="*70)
        return res1, res2

def check_cluster_state():
    print("\n--- KIỂM TRA TRẠNG THÁI HỆ THỐNG ---")
    try:
        nodes = requests.get(f"{COORDINATOR}/nodes", timeout=2).json()
        print(f"Cụm hệ thống: {'HOẠT ĐỘNG TỐT' if nodes.get('cluster_healthy') else 'CÓ NODE OFFLINE'}")
        for n in nodes.get("nodes", []):
            print(f"  * {n['name']} ({n['url']}): {n['status']} (PID: {n.get('pid')})")
    except Exception as e:
        print(f"  Không thể kết nối Coordinator: {e}")

    try:
        accs = requests.get("http://localhost:5004/accounts", timeout=2).json()
        print("\nSố dư tài khoản:")
        for a in accs:
            print(f"  * {a['account']}: {a['balance']} VNĐ")
    except Exception:
        pass

if __name__ == "__main__":
    client = ReliableOrderClient()
    if len(sys.argv) > 1 and sys.argv[1] == "duplicate":
        client.simulate_duplicate_requests()
    else:
        check_cluster_state()
        client.simulate_duplicate_requests("SP001", 1, "alice", 200)
        check_cluster_state()
