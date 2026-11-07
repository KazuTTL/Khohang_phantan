# common/db.py
import sqlite3

def get_conn(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_warehouse_db(path, products):
    conn = get_conn(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT,
        quantity INTEGER DEFAULT 100,
        reserved INTEGER DEFAULT 0
    )""")
    
    # Kiểm tra và thêm cột quantity, reserved nếu bảng products đã tồn tại từ schema.sql
    existing_cols = [c["name"] for c in conn.execute("PRAGMA table_info(products)").fetchall()]
    if "quantity" not in existing_cols:
        conn.execute("ALTER TABLE products ADD COLUMN quantity INTEGER DEFAULT 100")
    if "reserved" not in existing_cols:
        conn.execute("ALTER TABLE products ADD COLUMN reserved INTEGER DEFAULT 0")

    conn.execute("""CREATE TABLE IF NOT EXISTS processed_txns (
        txn_id TEXT PRIMARY KEY,
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS message_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        txn_id TEXT,
        operation TEXT,
        payload TEXT,
        state TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    for p in products:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, quantity, reserved) VALUES (?,?,?,0)",
            (p["id"], p["name"], p.get("quantity", 100))
        )

    # Nếu có dữ liệu location_stock, đồng bộ số lượng sản phẩm
    try:
        conn.execute("""
            UPDATE products 
            SET quantity = (
                SELECT SUM(quantity) 
                FROM location_stock 
                WHERE location_stock.product_id = products.id
            )
            WHERE id IN (SELECT DISTINCT product_id FROM location_stock)
        """)
    except Exception:
        pass

    conn.commit()
    return conn
