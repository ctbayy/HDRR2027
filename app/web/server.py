"""
[MODULE WEB ENGINE SERVER & PACKAGING]
Khởi chạy ThreadingHTTPServer, tự động mở cửa sổ trình duyệt Edge/Chrome ở chế độ App,
quản lý hàng chờ đồng bộ ngầm (LocalSyncEngineModule), và hỗ trợ đóng gói PyInstaller EXE.
"""

import os
import subprocess
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from ..config import ConfigSecurityModule
from ..database import DatabaseEngineModule
from ..sync_queue import LocalSyncEngineModule
from .handler import WebEngineRequestHandler


def launch_app_window(url: str) -> None:
    """Khởi động cửa sổ trình duyệt giao diện Desktop ứng dụng (Edge/Chrome App Mode)."""
    if os.name == "nt":
        candidate_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "msedge",
            "chrome",
        ]
        for browser_target in candidate_paths:
            try:
                if os.path.exists(browser_target) or browser_target in ("msedge", "chrome"):
                    subprocess.Popen([browser_target, f"--app={url}"])
                    return
            except Exception:
                continue
    webbrowser.open(url)


def run_web_engine_server() -> None:
    """Khởi chạy máy chủ HTTP và phục vụ ứng dụng."""
    DatabaseEngineModule.initialize_schema()
    LocalSyncEngineModule.start_background_worker()

    lan_ip = ConfigSecurityModule.get_lan_ip()
    port = ConfigSecurityModule.PORT
    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{lan_ip}:{port}"
    active_dir, mode = ConfigSecurityModule.resolve_storage_dir()

    print("=" * 78)
    print(r" HỆ THỐNG QUẢN LÝ HÓA ĐƠN RỦI RO V4.1 - GIẢ LẬP & KẾT NỐI \\qng-pthieu10\SharePdf")
    print("=" * 78)
    print(f" 1. Trên Laptop của bạn, truy cập    : {local_url}")
    print(f" 2. Đồng nghiệp trong LAN truy cập   : {lan_url}")
    print(f" 3. Thư mục SharePdf đang ánh xạ tại : {active_dir} ({mode})")
    print(f" 4. File CSDL .db dùng chung tại     : {ConfigSecurityModule.get_db_path()}")
    print(f" 5. Hàng chờ đồng bộ cá nhân (Queue) : Tự động cách ly & xóa sau khi ghi CSDL")
    print(f" 6. Phân hệ Quản trị & Nhật ký ngầm  : Bảo mật tài khoản Quản trị viên (Admin)")
    print("=" * 78)

    server = ThreadingHTTPServer(("0.0.0.0", port), WebEngineRequestHandler)
    threading.Timer(0.8, lambda: launch_app_window(local_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang dừng Web Engine và hoàn tất đồng bộ hàng chờ...")
    finally:
        LocalSyncEngineModule.stop_background_worker()
        server.server_close()
        print("Đã dừng an toàn.")


def build_windows_exe() -> None:
    """Tự động đóng gói toàn bộ ứng dụng thành file QuanLyHoaDonRuiRo.exe duy nhất."""
    print("Đang tiến hành đóng gói thành file QuanLyHoaDonRuiRo.exe...")
    base_dir = ConfigSecurityModule.get_base_dir()
    main_script = base_dir / "ung_dung_quan_ly_hoa_don_rui_ro.py"
    static_dir = base_dir / "app" / "static"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "QuanLyHoaDonRuiRo",
        f"--add-data={static_dir};app/static",
        str(main_script),
    ]
    subprocess.check_call(cmd)
    print("Hoàn tất! File chạy nằm tại thư mục: dist/QuanLyHoaDonRuiRo.exe")
