"""
HỆ THỐNG QUẢN LÝ HÓA ĐƠN RỦI RO NỘI BỘ - WEB ENGINE ĐA MODULE (V4.1)
====================================================================
Phiên bản 4.1 Modularized:
  - Cấu trúc thư mục module hóa sạch sẽ: app/config, app/database, app/workflow, app/ingest, app/web.
  - Tách bạch giao diện HTML, CSS, JavaScript (app/static) giúp dễ dàng tùy biến UI/UX.
  - Tự động sao lưu an toàn CSDL hàng ngày (Auto Snapshot Backup).
  - Tối ưu hóa hiệu năng, loại bỏ hoàn toàn hiện tượng nghẽn mạng LAN DNS timeout.
  - Tự động khắc phục lỗi Unicode encoding trên console Windows.
"""

import sys

# Khắc phục triệt để lỗi Unicode charmap console trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.config import ConfigSecurityModule
from app.database import DatabaseEngineModule
from app.ingest import DocumentIngestModule
from app.web.server import build_windows_exe, run_web_engine_server

if __name__ == "__main__":
    DatabaseEngineModule.initialize_schema()

    if "--build-exe" in sys.argv:
        build_windows_exe()
    elif "--test-init" in sys.argv:
        active_dir, mode = ConfigSecurityModule.resolve_storage_dir()
        ident = ConfigSecurityModule.detect_internal_machine_identity("127.0.0.1")
        pdfs = ConfigSecurityModule.list_sharepdf_files()
        scan_test = DocumentIngestModule.scan_existing_pdf_in_sharepdf(pdfs[0]["name"]) if pdfs else {}
        print(
            f"Khởi tạo V4.1 Modular thành công! Mode: {mode} | Dir: {active_dir} | "
            f"Auto-Auth: {ident['domain_account']} -> {ident['matched_officer_name']} | "
            f"Sample PDFs: {len(pdfs)} | Scan test MSTs: {scan_test.get('mst_list')}"
        )
    else:
        run_web_engine_server()
