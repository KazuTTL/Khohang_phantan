# database/db_manager.py
import sqlite3
import os

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

def get_connection(db_path: str):
    """Tạo kết nối SQLite thread-safe với Row factory dict"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path: str):
    """Khởi tạo toàn bộ bảng theo schema.sql nếu chưa tồn tại"""
    conn = get_connection(db_path)
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    return conn
