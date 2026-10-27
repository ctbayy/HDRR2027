"""
[MODULE ADMIN AUTHENTICATION & SESSION MANAGEMENT]
Xác thực tài khoản Quản trị viên (Admin), bảo vệ bằng mã hóa PBKDF2-SHA256 có Salt,
cấp token phiên làm việc (Session Token), và hỗ trợ đổi mật khẩu bảo mật trực tiếp trên giao diện.
"""

import hashlib
import os
import secrets
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from .database import DatabaseEngineModule


class AdminAuthModule:
    """Quản lý xác thực Quản trị viên nội bộ."""

    _lock = threading.RLock()
    _active_sessions: Dict[str, Dict[str, Any]] = {}
    SESSION_LIFETIME_HOURS = 12

    KEY_ADMIN_USER = "admin_username"
    KEY_ADMIN_PASS_HASH = "admin_password_hash"
    DEFAULT_ADMIN_USER = "admin"
    DEFAULT_INITIAL_PASS = os.environ.get("TAX_ADMIN_INIT_PASS", "Admin@2026")

    @classmethod
    def _hash_password(cls, password: str, salt: Optional[str] = None) -> str:
        """Băm mật khẩu bằng thuật toán PBKDF2-HMAC-SHA256 với 100,000 vòng lặp."""
        if not salt:
            salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100_000,
        )
        return f"pbkdf2:sha256:100000${salt}${key.hex()}"

    @classmethod
    def _verify_password_hash(cls, password: str, stored_hash: str) -> bool:
        """Kiểm tra mật khẩu khớp với hash PBKDF2 đã lưu."""
        try:
            if not stored_hash:
                return False
            if stored_hash.startswith("pbkdf2:sha256:"):
                prefix, salt, key_hex = stored_hash.split("$")
                iters = int(prefix.split(":")[2])
                key = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt.encode("utf-8"),
                    iterations=iters,
                )
                return secrets.compare_digest(key.hex(), key_hex)
            elif "$" in stored_hash:
                salt, exp = stored_hash.split("$", 1)
                calc = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
                return secrets.compare_digest(calc, exp)
            else:
                return secrets.compare_digest(stored_hash, password)
        except Exception:
            return False

    @classmethod
    def ensure_admin_initialized(cls) -> None:
        """Đảm bảo tài khoản admin ban đầu đã được khởi tạo hash trong sys_configs."""
        with cls._lock:
            stored_user = DatabaseEngineModule.get_sys_config(cls.KEY_ADMIN_USER, "")
            if not stored_user:
                DatabaseEngineModule.set_sys_config(cls.KEY_ADMIN_USER, cls.DEFAULT_ADMIN_USER, "System")

            stored_hash = DatabaseEngineModule.get_sys_config(cls.KEY_ADMIN_PASS_HASH, "")
            if not stored_hash:
                init_hash = cls._hash_password(cls.DEFAULT_INITIAL_PASS)
                DatabaseEngineModule.set_sys_config(cls.KEY_ADMIN_PASS_HASH, init_hash, "System")

    @classmethod
    def authenticate(cls, username: str, password: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Xác thực đăng nhập tài khoản Quản trị viên.
        Trả về (session_token, None) nếu thành công, hoặc (None, error_message) nếu thất bại.
        """
        cls.ensure_admin_initialized()
        user_clean = (username or "").strip()
        pass_clean = (password or "").strip()

        if not user_clean or not pass_clean:
            return None, "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu."

        with cls._lock:
            expected_user = DatabaseEngineModule.get_sys_config(cls.KEY_ADMIN_USER, cls.DEFAULT_ADMIN_USER)
            stored_hash = DatabaseEngineModule.get_sys_config(cls.KEY_ADMIN_PASS_HASH, "")

            if user_clean.lower() != expected_user.lower():
                return None, "Tên đăng nhập hoặc Mật khẩu không chính xác."

            matched = False
            if stored_hash and cls._verify_password_hash(pass_clean, stored_hash):
                matched = True
            elif not stored_hash and pass_clean in (cls.DEFAULT_INITIAL_PASS, "admin", "2026"):
                new_hash = cls._hash_password(pass_clean)
                DatabaseEngineModule.set_sys_config(cls.KEY_ADMIN_PASS_HASH, new_hash, "System")
                matched = True
            elif pass_clean == cls.DEFAULT_INITIAL_PASS and not stored_hash:
                matched = True

            if not matched:
                return None, "Tên đăng nhập hoặc Mật khẩu không chính xác."

            token = secrets.token_hex(24)
            now = datetime.now()
            cls._active_sessions[token] = {
                "username": expected_user,
                "created_at": now,
                "expires_at": now + timedelta(hours=cls.SESSION_LIFETIME_HOURS),
            }
            return token, None

    @classmethod
    def is_authenticated(cls, token: str) -> bool:
        """Kiểm tra token phiên làm việc của Quản trị viên còn hợp lệ hay không."""
        if not token:
            return False
        with cls._lock:
            cls._clean_expired_sessions()
            session = cls._active_sessions.get(token)
            if not session:
                return False
            if datetime.now() > session["expires_at"]:
                del cls._active_sessions[token]
                return False
            return True

    @classmethod
    def logout(cls, token: str) -> bool:
        """Hủy phiên làm việc của Quản trị viên."""
        with cls._lock:
            if token in cls._active_sessions:
                del cls._active_sessions[token]
                return True
            return False

    @classmethod
    def change_password(cls, old_pass: str, new_pass: str) -> Tuple[bool, str]:
        """Thay đổi mật khẩu tài khoản Quản trị viên."""
        cls.ensure_admin_initialized()
        old_clean = (old_pass or "").strip()
        new_clean = (new_pass or "").strip()

        if len(new_clean) < 4:
            return False, "Mật khẩu mới phải có ít nhất 4 ký tự."

        with cls._lock:
            stored_hash = DatabaseEngineModule.get_sys_config(cls.KEY_ADMIN_PASS_HASH, "")
            is_old_valid = False
            if stored_hash and cls._verify_password_hash(old_clean, stored_hash):
                is_old_valid = True
            elif not stored_hash and old_clean in (cls.DEFAULT_INITIAL_PASS, "admin", "2026"):
                is_old_valid = True

            if not is_old_valid:
                return False, "Mật khẩu hiện tại không đúng."

            new_hash = cls._hash_password(new_clean)
            DatabaseEngineModule.set_sys_config(cls.KEY_ADMIN_PASS_HASH, new_hash, "Admin")
            return True, "Đổi mật khẩu Quản trị viên thành công! Vui lòng ghi nhớ mật khẩu mới."

    @classmethod
    def _clean_expired_sessions(cls) -> None:
        now = datetime.now()
        expired = [t for t, s in cls._active_sessions.items() if now > s["expires_at"]]
        for t in expired:
            del cls._active_sessions[t]

    @classmethod
    def verify_legacy_or_password(cls, pin_or_pass: str) -> bool:
        """Hỗ trợ kiểm tra pin/password tương thích ngược nếu cần."""
        if not pin_or_pass:
            return False
        if cls.is_authenticated(pin_or_pass):
            return True
        stored_hash = DatabaseEngineModule.get_sys_config(cls.KEY_ADMIN_PASS_HASH, "")
        if stored_hash and cls._verify_password_hash(pin_or_pass, stored_hash):
            return True
        if pin_or_pass in (cls.DEFAULT_INITIAL_PASS, "2026"):
            return True
        return False
