"""
Unit test kiểm thử toàn diện:
1. Xác thực Quản trị viên (AdminAuthModule):
   - Khởi tạo tài khoản Quản trị an toàn trong bảng sys_configs.
   - Đăng nhập tài khoản admin với mật khẩu ban đầu.
   - Đổi mật khẩu Quản trị (PBKDF2-SHA256 salted).
   - Kiểm tra vô hiệu hóa mật khẩu cũ và chấp nhận mật khẩu mới.
   - Đăng xuất hủy token.
2. HTTP Server Endpoints:
   - POST /api/admin/login
   - GET /api/admin/check_auth
   - GET /api/stealth/logs (bảo vệ 403 nếu không có token)
   - POST /api/admin/change_password
   - POST /api/admin/logout
"""

import json
import os
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath("."))

from app.auth import AdminAuthModule
from app.config import ConfigSecurityModule
from app.database import DatabaseEngineModule
from app.web.handler import WebEngineRequestHandler


def test_auth_module():
    print("=== 1. KIỂM THỬ ADMIN AUTH MODULE ===")
    DatabaseEngineModule.initialize_schema()
    AdminAuthModule.ensure_admin_initialized()

    # Thử đăng nhập sai
    bad_token, err = AdminAuthModule.authenticate("admin", "wrong_pass_123")
    assert bad_token is None, "Phải từ chối mật khẩu sai"
    print("✓ Từ chối mật khẩu sai thành công")

    # Đăng nhập ban đầu với Admin@2026
    token, err = AdminAuthModule.authenticate("admin", "Admin@2026")
    assert token is not None, f"Đăng nhập thất bại: {err}"
    assert AdminAuthModule.is_authenticated(token) is True, "Token phải hợp lệ"
    print(f"✓ Đăng nhập admin ban đầu thành công! Token: {token[:16]}...")

    # Đổi mật khẩu
    new_pass = "ChuyenNghiep@2026"
    ok, msg = AdminAuthModule.change_password("Admin@2026", new_pass)
    assert ok is True, f"Đổi mật khẩu thất bại: {msg}"
    print(f"✓ Đổi mật khẩu thành công: {msg}")

    # Mật khẩu cũ không còn tác dụng
    token_old, _ = AdminAuthModule.authenticate("admin", "Admin@2026")
    assert token_old is None, "Mật khẩu cũ không được phép đăng nhập nữa"
    print("✓ Mật khẩu cũ đã bị vô hiệu hóa hoàn toàn")

    # Mật khẩu mới hoạt động
    token_new, _ = AdminAuthModule.authenticate("admin", new_pass)
    assert token_new is not None, "Mật khẩu mới phải đăng nhập thành công"
    print("✓ Đăng nhập bằng mật khẩu mới thành công!")

    # Đăng xuất
    logged_out = AdminAuthModule.logout(token_new)
    assert logged_out is True
    assert AdminAuthModule.is_authenticated(token_new) is False
    print("✓ Đăng xuất hủy token thành công!")

    # Đổi lại về Admin@2026 để test HTTP server
    AdminAuthModule.change_password(new_pass, "Admin@2026")
    print("✓ Đã reset về Admin@2026 cho bài test tiếp theo")


def test_http_api():
    print("\n=== 2. KIỂM THỬ CÁC HTTP API XÁC THỰC VÀ NHẬT KÝ LƯU VẾT ===")
    port = 8789
    server = ThreadingHTTPServer(("127.0.0.1", port), WebEngineRequestHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)

    base_url = f"http://127.0.0.1:{port}"

    try:
        # A. Truy cập /api/stealth/logs khi CHƯA đăng nhập -> Phải trả về 403
        try:
            req = urllib.request.Request(f"{base_url}/api/stealth/logs")
            urllib.request.urlopen(req)
            assert False, "Chưa đăng nhập mà truy cập được logs là lỗi bảo mật!"
        except urllib.error.HTTPError as e:
            assert e.code in (401, 403), f"Mã lỗi mong muốn 403/401, nhận: {e.code}"
            print(f"✓ Bảo mật tốt: Chặn truy cập trái phép vào /api/stealth/logs ({e.code} Forbidden)")

        # B. Đăng nhập Admin qua HTTP POST /api/admin/login
        login_body = json.dumps({"username": "admin", "password": "Admin@2026"}).encode("utf-8")
        req_login = urllib.request.Request(
            f"{base_url}/api/admin/login",
            data=login_body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_login) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("success") is True, f"Login failed: {data}"
            token = data.get("token")
            assert token, "Không nhận được token"
            print(f"✓ POST /api/admin/login thành công! Token: {token[:16]}...")

        # C. Kiểm tra session qua GET /api/admin/check_auth
        req_check = urllib.request.Request(
            f"{base_url}/api/admin/check_auth",
            headers={"X-Admin-Token": token}
        )
        with urllib.request.urlopen(req_check) as resp:
            cdata = json.loads(resp.read().decode("utf-8"))
            assert cdata.get("authenticated") is True
            print("✓ GET /api/admin/check_auth xác nhận phiên Quản trị viên đang kích hoạt")

        # D. Lấy nhật ký qua GET /api/stealth/logs với Token hợp lệ -> Thành công 200
        req_logs = urllib.request.Request(
            f"{base_url}/api/stealth/logs",
            headers={"X-Admin-Token": token}
        )
        with urllib.request.urlopen(req_logs) as resp:
            assert resp.status == 200
            ldata = json.loads(resp.read().decode("utf-8"))
            logs = ldata.get("logs", [])
            print(f"✓ GET /api/stealth/logs với Token Admin thành công! Đã tải {len(logs)} bản ghi nhật ký")

        # E. Đổi mật khẩu qua POST /api/admin/change_password
        chpass_body = json.dumps({"old_password": "Admin@2026", "new_password": "TaxSecure@2026"}).encode("utf-8")
        req_chpass = urllib.request.Request(
            f"{base_url}/api/admin/change_password",
            data=chpass_body,
            headers={"Content-Type": "application/json", "X-Admin-Token": token}
        )
        with urllib.request.urlopen(req_chpass) as resp:
            chdata = json.loads(resp.read().decode("utf-8"))
            assert chdata.get("success") is True
            print(f"✓ POST /api/admin/change_password thành công: {chdata.get('message')}")

        # F. Đăng xuất qua POST /api/admin/logout
        req_logout = urllib.request.Request(
            f"{base_url}/api/admin/logout",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-Admin-Token": token}
        )
        with urllib.request.urlopen(req_logout) as resp:
            lodata = json.loads(resp.read().decode("utf-8"))
            assert lodata.get("success") is True
            print("✓ POST /api/admin/logout đăng xuất thành công")

        # Reset mật khẩu về ban đầu
        AdminAuthModule.change_password("TaxSecure@2026", "Admin@2026")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_auth_module()
    test_http_api()
    print("\n=== TẤT CẢ BÀI KIỂM THỬ XÁC THỰC ADMIN & NHẬT KÝ THÀNH CÔNG 100%! ===")
