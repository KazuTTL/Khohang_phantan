# database/seed_data.py
"""
Script nạp dữ liệu mẫu ban đầu cho toàn bộ hệ thống phân tán:
- 3 Chi nhánh kho: HN (Hà Nội), DN (Đà Nẵng), SG (TP. Hồ Chí Minh)
- 5 Hàng hóa dùng chung (D1)
- Hệ thống ô kệ phân cấp 5 tầng (D3) cho từng kho: Kho -> Khu -> Dãy -> Kệ -> Tầng -> Ô
- Tồn kho ban đầu gắn trực tiếp vào từng ô kệ
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_manager import init_db

WAREHOUSES = [
    {"id": "HN", "name": "Kho Tổng Miền Bắc (Hà Nội)", "address": "KCN Từ Liêm, Bắc Từ Liêm, Hà Nội", "phone": "024-3888-1111"},
    {"id": "DN", "name": "Kho Miền Trung (Đà Nẵng)", "address": "KCN Hòa Khánh, Liên Chiểu, Đà Nẵng", "phone": "0236-3999-222"},
    {"id": "SG", "name": "Kho Tổng Miền Nam (TP.HCM)", "address": "KCN Tân Bình, Tân Phú, TP.HCM", "phone": "028-3777-3333"},
]

PRODUCTS = [
    {"id": "SP001", "name": "Áo polo nam Cotton", "sku": "POLO-COT-01", "unit": "Cái", "category": "Thời trang", "price": 250000},
    {"id": "SP002", "name": "Quần jeans nam Slimfit", "sku": "JEAN-SLIM-02", "unit": "Cái", "category": "Thời trang", "price": 450000},
    {"id": "SP003", "name": "Giày Sneaker Running", "sku": "SNK-RUN-03", "unit": "Đôi", "category": "Giày dép", "price": 850000},
    {"id": "SP004", "name": "Balo Laptop chống nước 15.6 inch", "sku": "BALO-LAP-04", "unit": "Chiếc", "category": "Phụ kiện", "price": 550000},
    {"id": "SP005", "name": "Mũ lưỡi trai phong cách", "sku": "CAP-STY-05", "unit": "Cái", "category": "Phụ kiện", "price": 120000},
]

def generate_locations(wh_id):
    """Tạo các vị trí ô kệ mẫu cho kho: 2 Zone, mỗi Zone 2 Dãy, mỗi Dãy 2 Kệ, 2 Tầng, 2 Ô"""
    locs = []
    zones = ["ZONE-A", "ZONE-B"]
    for z in zones:
        for a in ["A01", "A02"]:
            for r in ["R01", "R02"]:
                for s in ["S01", "S02"]:
                    for b in ["B01", "B02"]:
                        loc_id = f"{wh_id}-{z}-{a}-{r}-{s}-{b}"
                        locs.append({
                            "id": loc_id,
                            "warehouse_id": wh_id,
                            "zone": z,
                            "aisle": a,
                            "rack": r,
                            "shelf": s,
                            "bin": b,
                            "capacity": 500,
                            "status": "AVAILABLE"
                        })
    return locs

def seed_warehouse(wh_id: str):
    db_path = f"logs/warehouse_{wh_id}.db"
    conn = init_db(db_path)
    
    # 1. Nạp Warehouses
    for w in WAREHOUSES:
        conn.execute("INSERT OR REPLACE INTO warehouses (id, name, address, phone, status) VALUES (?,?,?,?,?)",
                     (w["id"], w["name"], w["address"], w["phone"], "ACTIVE"))
    
    # 2. Nạp Products
    for p in PRODUCTS:
        conn.execute("INSERT OR REPLACE INTO products (id, name, sku, unit, category, price) VALUES (?,?,?,?,?,?)",
                     (p["id"], p["name"], p["sku"], p["unit"], p["category"], p["price"]))
    
    # 3. Nạp Locations
    locations = generate_locations(wh_id)
    for loc in locations:
        conn.execute("""INSERT OR REPLACE INTO locations (id, warehouse_id, zone, aisle, rack, shelf, bin, capacity, status)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                     (loc["id"], loc["warehouse_id"], loc["zone"], loc["aisle"], loc["rack"], loc["shelf"], loc["bin"], loc["capacity"], loc["status"]))
    
    # 4. Nạp Tồn kho mẫu ban đầu cho một số ô kệ
    # Ví dụ kho HN: SP001 ở ô 1, SP002 ở ô 2
    # Kho DN: SP001 ở ô 1
    # Kho SG: SP001 ở ô 1, SP003 ở ô 3
    sample_stock = [
        {"loc": f"{wh_id}-ZONE-A-A01-R01-S01-B01", "pid": "SP001", "qty": 100},
        {"loc": f"{wh_id}-ZONE-A-A01-R01-S01-B02", "pid": "SP002", "qty": 60},
        {"loc": f"{wh_id}-ZONE-B-A01-R01-S01-B01", "pid": "SP004", "qty": 40},
    ]
    for st in sample_stock:
        conn.execute("""INSERT OR REPLACE INTO location_stock (warehouse_id, location_id, product_id, quantity, reserved)
                        VALUES (?,?,?,?,0)""",
                     (wh_id, st["loc"], st["pid"], st["qty"]))
    
    conn.commit()
    print(f"[{wh_id}] Khoi tao thanh cong voi {len(locations)} vi tri o ke.")

def main():
    os.makedirs("logs", exist_ok=True)
    for w in WAREHOUSES:
        seed_warehouse(w["id"])
    print(">>> KHOI TAO DU LIEU CHO CA 3 CHI NHANH KHO THANH CONG! <<<")

if __name__ == "__main__":
    main()
