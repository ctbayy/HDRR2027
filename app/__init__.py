"""
Hệ thống Quản lý Hóa đơn Rủi ro Nội bộ (HDRR) - Phiên bản 4.1 Modular
Phát triển cho Cơ quan Thuế
"""

import sys

# Đảm bảo console Windows luôn encode UTF-8 an toàn, không bao giờ bị UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "4.1.0"
__author__ = "Cơ quan Thuế"

from .web.server import run_web_engine_server, build_windows_exe

__all__ = ["run_web_engine_server", "build_windows_exe", "__version__"]
