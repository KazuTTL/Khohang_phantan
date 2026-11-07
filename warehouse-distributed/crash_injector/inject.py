# crash_injector/inject.py
"""
Chaos & Crash Injector for Distributed Systems (Chương 8)
- Mô phỏng Server Crashes (Mục 8.3 & 8.5)
- Liệt kê PID và trạng thái các node
- Kill hoặc Restart từng node để kiểm thử khả năng chịu lỗi và phục hồi
"""
import os, sys, time, subprocess, requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SERVICES = {
    "coordinator": {"script": "coordinator/server.py", "port": 7000, "env": {}},
    "HN": {"script": "warehouse/server.py", "port": 5001, "env": {"WAREHOUSE_NAME": "HN", "PORT": "5001"}},
    "DN": {"script": "warehouse/server.py", "port": 5002, "env": {"WAREHOUSE_NAME": "DN", "PORT": "5002"}},
    "SG": {"script": "warehouse/server.py", "port": 5003, "env": {"WAREHOUSE_NAME": "SG", "PORT": "5003"}},
    "payment": {"script": "payment/server.py", "port": 5004, "env": {}},
    "shipping": {"script": "shipping/server.py", "port": 5005, "env": {}},
}

def get_node_status(name):
    cfg = SERVICES.get(name)
    if not cfg:
        return None
    port = cfg["port"]
    url = f"http://localhost:{port}/health"
    try:
        r = requests.get(url, timeout=1)
        if r.status_code == 200:
            return {"status": "ONLINE", "pid": r.json().get("pid"), "port": port}
    except Exception:
        pass
    return {"status": "OFFLINE", "pid": None, "port": port}

def kill_node(name):
    st = get_node_status(name)
    if not st or st["status"] == "OFFLINE":
        print(f"[-] Node {name} đang không hoạt động (OFFLINE).")
        return False
    pid = st["pid"]
    if not pid:
        print(f"[-] Không lấy được PID của node {name}.")
        return False
    try:
        os.kill(pid, 9)
        print(f"[+] [CRASH INJECTED] Đã đánh sập node {name} (PID: {pid})!")
        return True
    except Exception as e:
        print(f"[-] Lỗi khi kill PID {pid}: {e}")
        return False

def restart_node(name):
    cfg = SERVICES.get(name)
    if not cfg:
        print(f"[-] Không tìm thấy cấu hình node {name}.")
        return False
    
    st = get_node_status(name)
    if st["status"] == "ONLINE":
        print(f"[!] Node {name} đang chạy (PID: {st['pid']}). Đang dừng trước...")
        kill_node(name)
        time.sleep(1)

    env = os.environ.copy()
    env.update(cfg.get("env", {}))
    
    log_out = f"logs/{name.lower()}.out.log"
    log_err = f"logs/{name.lower()}.err.log"
    os.makedirs("logs", exist_ok=True)
    
    out_f = open(log_out, "a")
    err_f = open(log_err, "a")

    p = subprocess.Popen([sys.executable, cfg["script"]], env=env, stdout=out_f, stderr=err_f)
    print(f"[+] [RECOVERED] Đã khởi động lại node {name} (New PID: {p.pid}) trên port {cfg['port']}!")
    time.sleep(1.5)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python inject.py list                - Xem trạng thái các node")
        print("  python inject.py kill <name>         - Đánh sập node (HN, DN, SG, payment, shipping, coordinator)")
        print("  python inject.py restart <name>      - Khởi động lại node")
        print("  python inject.py delay_kill <name> <s> - Đánh sập node sau s giây")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "list":
        print("\n--- TRẠNG THÁI CÁC DỊCH VỤ ---")
        for s in SERVICES:
            st = get_node_status(s)
            print(f"  * Node {s:<12} [Port {st['port']}]: {st['status']} (PID: {st['pid']})")
    elif cmd == "kill" and len(sys.argv) >= 3:
        kill_node(sys.argv[2])
    elif cmd == "restart" and len(sys.argv) >= 3:
        restart_node(sys.argv[2])
    elif cmd == "delay_kill" and len(sys.argv) >= 4:
        target = sys.argv[2]
        sec = float(sys.argv[3])
        print(f"[!] Sẽ đánh sập node {target} sau {sec} giây...")
        time.sleep(sec)
        kill_node(target)
    else:
        print("[-] Lệnh không hợp lệ.")
