"""
[MODULE ASSET LOADER]
Tải file HTML, CSS, JavaScript cho Web Engine.
Hỗ trợ cả môi trường phát triển (đọc file trực tiếp) và môi trường đóng gói PyInstaller.
"""

import sys
from pathlib import Path
from typing import Optional


def get_static_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Môi trường PyInstaller
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = base / "app" / "static"
        if candidate.exists():
            return candidate
        candidate2 = base / "static"
        if candidate2.exists():
            return candidate2

    # Môi trường chạy trực tiếp Python
    return Path(__file__).resolve().parent.parent / "static"


def load_asset_bytes(filename: str) -> Optional[bytes]:
    s_dir = get_static_dir()
    target = s_dir / filename
    if target.exists() and target.is_file():
        return target.read_bytes()
    return None
