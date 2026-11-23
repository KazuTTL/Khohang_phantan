# backend/shared/cluster_infra.py
"""
Hạ tầng Cụm Hệ thống Phân tán cho từng Site:
1. Load Balancer & Multi-Instance Middleware: Điều phối Round-Robin giữa 2 App Instance trên mỗi Site.
2. Local DB Replicator: Sao lưu nóng (Hot Replication) từ DB Primary sang DB Replica Dự phòng.
"""
import os
import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import Request

logger = logging.getLogger("ClusterInfra")


class SiteLoadBalancer:
    """Mô phỏng Load Balancer điều phối lưu lượng Round-Robin vào các App Instance của Site"""

    def __init__(self, site_name: str, lb_name: str, instances: List[str]):
        self.site_name = site_name
        self.lb_name = lb_name
        self.instances = instances
        self._counter = 0
        self.stats: Dict[str, int] = {inst: 0 for inst in instances}

    def next_instance(self) -> str:
        inst = self.instances[self._counter % len(self.instances)]
        self._counter += 1
        self.stats[inst] = self.stats.get(inst, 0) + 1
        return inst

    def get_status(self) -> Dict[str, Any]:
        return {
            "site": self.site_name,
            "load_balancer": self.lb_name,
            "algorithm": "ROUND_ROBIN",
            "total_requests": self._counter,
            "instances": [
                {
                    "instance_id": inst,
                    "status": "UP",
                    "requests_served": self.stats.get(inst, 0)
                }
                for inst in self.instances
            ]
        }


class LocalDBReplicator:
    """Tiến trình nhân bản nóng từ DB Primary sang DB Replica Dự phòng (SQLite Online Backup API)"""

    def __init__(self, primary_db_path: str, replica_db_path: str):
        self.primary_db_path = primary_db_path
        self.replica_db_path = replica_db_path
        self.last_replicated_at: str = ""
        self.replication_count: int = 0
        self.last_error: str = ""
        self.is_healthy: bool = False

    def replicate_once(self) -> bool:
        if not os.path.exists(self.primary_db_path):
            return False
        src_conn = None
        dst_conn = None
        try:
            src_conn = sqlite3.connect(self.primary_db_path, timeout=10.0)
            dst_conn = sqlite3.connect(self.replica_db_path, timeout=10.0)
            with dst_conn:
                src_conn.backup(dst_conn, pages=50, sleep=0.005)
            self.last_replicated_at = datetime.utcnow().isoformat()
            self.replication_count += 1
            self.last_error = ""
            self.is_healthy = True
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_healthy = False
            logger.warning(f"[DB REPLICA] Lỗi nhân bản {self.primary_db_path} -> {self.replica_db_path}: {e}")
            return False
        finally:
            if dst_conn:
                dst_conn.close()
            if src_conn:
                src_conn.close()

    async def run_loop(self, interval_seconds: float = 5.0):
        logger.info(f"[DB REPLICA] Khởi động Replication: {self.primary_db_path} -> {self.replica_db_path}")
        while True:
            try:
                await asyncio.to_thread(self.replicate_once)
            except asyncio.CancelledError:
                logger.info("[DB REPLICA] Dừng tiến trình Replication.")
                break
            except Exception as e:
                logger.error(f"[DB REPLICA] Ngoại lệ vòng lặp: {e}")
            await asyncio.sleep(interval_seconds)

    def get_status(self) -> Dict[str, Any]:
        primary_size = os.path.getsize(self.primary_db_path) if os.path.exists(self.primary_db_path) else 0
        replica_size = os.path.getsize(self.replica_db_path) if os.path.exists(self.replica_db_path) else 0
        return {
            "primary_db": os.path.basename(self.primary_db_path),
            "replica_db": os.path.basename(self.replica_db_path),
            "primary_size_bytes": primary_size,
            "replica_size_bytes": replica_size,
            "replication_count": self.replication_count,
            "last_replicated_at": self.last_replicated_at,
            "replica_healthy": self.is_healthy,
            "last_error": self.last_error or None
        }

    def read_replica_preview(self, table_name: str, limit: int = 20) -> Dict[str, Any]:
        """Đọc trực tiếp dữ liệu tồn kho từ DB Replica Dự phòng (Chế độ Read-Only Failover)"""
        self.replicate_once()
        if not os.path.exists(self.replica_db_path):
            return {"status": "UNAVAILABLE", "rows": [], "replica_db": os.path.basename(self.replica_db_path)}
        conn = None
        try:
            conn = sqlite3.connect(self.replica_db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            return {
                "status": "OK",
                "source": "DB_REPLICA_STANDBY",
                "replica_db": os.path.basename(self.replica_db_path),
                "last_replicated_at": self.last_replicated_at,
                "row_count": len(rows),
                "rows": rows
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "rows": []}
        finally:
            if conn:
                conn.close()


_wan_state = {"online": True}


def is_wan_online() -> bool:
    return _wan_state["online"]


def set_wan_online(online: bool) -> bool:
    _wan_state["online"] = bool(online)
    logger.warning(f"[WAN LINK] Trạng thái kết nối WAN tới Trung tâm đã chuyển sang: {'ONLINE' if online else 'OFFLINE (SIMULATED)'}")
    return _wan_state["online"]


def resolve_sqlite_paths(database_url: str, default_primary: str) -> tuple[str, str]:
    """Trích xuất đường dẫn file Primary DB và tạo đường dẫn file Replica DB tương ứng"""
    if database_url.startswith("sqlite:///"):
        raw_path = database_url.replace("sqlite:///", "", 1)
    else:
        raw_path = default_primary
    abs_primary = os.path.abspath(raw_path)
    base, ext = os.path.splitext(abs_primary)
    abs_replica = f"{base}_replica{ext or '.db'}"
    return abs_primary, abs_replica


def register_lb_middleware(app, lb: SiteLoadBalancer):
    """Gắn Middleware Load Balancer để phân phối request và gắn header theo dõi Instance"""
    @app.middleware("http")
    async def load_balancer_middleware(request: Request, call_next):
        instance_id = lb.next_instance()
        response = await call_next(request)
        response.headers["X-Load-Balancer"] = lb.lb_name
        response.headers["X-Served-By-Instance"] = instance_id
        response.headers["X-DB-Role"] = "Primary (Replica Synced)"
        return response
