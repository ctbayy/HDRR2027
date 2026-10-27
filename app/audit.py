"""
[MODULE STEALTH AUDIT & ACCESS TRACKER]
Lưu vết ngầm các hoạt động truy cập, tra cứu MST, tải file, sửa đổi hồ sơ.
Chỉ chủ sở hữu (với mã PIN bí mật) mới có quyền truy cập xem logs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .auth import AdminAuthModule
from .config import ConfigSecurityModule
from .database import DatabaseEngineModule


class StealthAuditModule:
    @classmethod
    def record_event(
        cls,
        client_ip: str,
        user_agent: str,
        officer_name: str,
        department: str,
        event_type: str,
        target_module: str,
        target_mst: str = "",
        record_id: str = "",
        event_detail: str = "",
    ) -> None:
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO stealth_audit_logs (
                    timestamp, client_ip, user_agent, officer_name,
                    department, event_type, target_module, target_mst, record_id, event_detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_str,
                    client_ip,
                    (user_agent or "")[:120],
                    officer_name or "Account Máy Nội Bộ",
                    department or "Chưa rõ",
                    event_type,
                    target_module,
                    target_mst,
                    str(record_id),
                    event_detail,
                ),
            )
            conn.commit()

    @classmethod
    def get_logs_for_owner(cls, token_or_pin: str, limit: int = 500) -> Optional[List[Dict[str, Any]]]:
        if not (AdminAuthModule.is_authenticated(token_or_pin) or AdminAuthModule.verify_legacy_or_password(token_or_pin)):
            return None
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM stealth_audit_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @classmethod
    def get_logs_count(cls) -> int:
        try:
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                r = conn.execute("SELECT COUNT(*) FROM stealth_audit_logs").fetchone()
                return int(r[0]) if r else 0
        except Exception:
            return 0
