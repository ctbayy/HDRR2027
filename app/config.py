"""
[MODULE CẤU HÌNH & BẢO MẬT HẠ TẦNG]
Quản lý đường dẫn UNC (\\qng-pthieu10\\SharePdf), chế độ giả lập Laptop cá nhân,
xác thực danh tính máy trạm nội bộ qua LAN IP / Windows Account.
"""

import getpass
import ipaddress
import os
import platform
import re
import socket
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ConfigSecurityModule:
    """
    Quản lý đường dẫn `\\\\qng-pthieu10\\SharePdf` (tự động giả lập khi chạy trên laptop cá nhân)
    và tự động xác thực người dùng theo Account Windows / Tên máy nội bộ.
    """

    PORT = int(os.environ.get("TAX_ENGINE_PORT", "8686"))
    OWNER_SECRET_PIN = os.environ.get("TAX_OWNER_PIN", "2026")

    # Đường dẫn UNC mục tiêu tại cơ quan
    TARGET_UNC_PATH = os.environ.get("TAX_UNC_SHARE_PATH", r"\\qng-pthieu10\SharePdf")
    EDOC_BASE_URL = os.environ.get("TAX_EDOC_URL", "http://qlvb.noibo/vanban/chitiet?soden=")

    EXCEL_7_COLS = [
        "Số đến",
        "Số ký hiệu",
        "Ngày văn bản",
        "Nơi gửi",
        "Trích yếu",
        "Ngày đến",
        "Hạn xử lý",
    ]

    _active_storage_dir: Optional[Path] = None
    _storage_mode: str = "VIRTUAL_SIMULATION"  # 'REAL_UNC_LAN' hoặc 'VIRTUAL_SIMULATION'
    _dns_cache: Dict[str, str] = {}

    @classmethod
    def get_base_dir(cls) -> Path:
        """Thư mục gốc chứa mã nguồn hoặc file thực thi .exe"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent.parent

    @classmethod
    def resolve_storage_dir(cls) -> Tuple[Path, str]:
        """
        Kiểm tra nếu đang ở mạng cơ quan và truy cập được `\\\\qng-pthieu10\\SharePdf` thật thì dùng trực tiếp.
        Nếu đang ở Laptop cá nhân, tự động giả lập `\\\\qng-pthieu10\\SharePdf` tại thư mục cục bộ
        và tạo sẵn các file PDF mẫu để test ngay.
        """
        if cls._active_storage_dir is not None:
            return cls._active_storage_dir, cls._storage_mode

        # 1. Thử kết nối vào \\qng-pthieu10\SharePdf thật
        if os.environ.get("TAX_FORCE_REAL_UNC") == "1" or (
            os.name == "nt" and os.path.exists(cls.TARGET_UNC_PATH)
        ):
            try:
                unc_p = Path(cls.TARGET_UNC_PATH)
                unc_p.mkdir(parents=True, exist_ok=True)
                probe = unc_p / ".cqt_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                cls._active_storage_dir = unc_p
                cls._storage_mode = "REAL_UNC_LAN"
                cls._seed_sample_pdfs_if_empty(unc_p)
                return cls._active_storage_dir, cls._storage_mode
            except Exception:
                pass

        # 2. Chế độ Giả lập \\qng-pthieu10\SharePdf ngay trên Laptop cá nhân
        base_dir = cls.get_base_dir()
        sim_dir = base_dir / "GiaLap_qng-pthieu10_SharePdf"
        try:
            sim_dir.mkdir(parents=True, exist_ok=True)
            tconn = sqlite3.connect(str(sim_dir / ".probe.db"))
            tconn.execute("CREATE TABLE IF NOT EXISTS t (id INT)")
            tconn.close()
            (sim_dir / ".probe.db").unlink(missing_ok=True)
            cls._active_storage_dir = sim_dir
        except Exception:
            cls._active_storage_dir = Path(tempfile.gettempdir()) / "GiaLap_qng-pthieu10_SharePdf"
            cls._active_storage_dir.mkdir(parents=True, exist_ok=True)

        cls._storage_mode = "VIRTUAL_SIMULATION"
        cls._seed_sample_pdfs_if_empty(cls._active_storage_dir)
        return cls._active_storage_dir, cls._storage_mode

    @staticmethod
    def _build_minimal_valid_pdf(lines: List[str]) -> bytes:
        """Tạo file PDF chuẩn (đọc và quét chữ được bằng trình đọc PDF & trình duyệt)."""
        text_ops = ["BT", "/F1 12 Tf", "50 760 Td", "16 TL"]
        for ln in lines:
            safe_ascii = (
                ln.replace("(", "\\(")
                .replace(")", "\\)")
                .encode("latin-1", errors="ignore")
                .decode("latin-1")
            )
            text_ops.append(f"({safe_ascii}) Tj T*")
        text_ops.append("ET")
        stream_data = "\n".join(text_ops).encode("latin-1")

        objs = [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
            f"4 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1")
            + stream_data
            + b"\nendstream\nendobj\n",
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        ]
        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for o in objs:
            offsets.append(len(out))
            out.extend(o)
        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode("latin-1"))
        for off in offsets:
            out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
        out.extend(
            f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
                "latin-1"
            )
        )
        return bytes(out)

    @classmethod
    def create_web_shortcuts_in_sharepdf(cls, folder: Path) -> List[str]:
        """Tự động tạo các Shortcut Web (.url chuẩn Windows và .html mở nhanh thông minh)."""
        created_files: List[str] = []
        try:
            lan_ip = cls.get_lan_ip()
            hostname = socket.gethostname()
            host_target = lan_ip if lan_ip != "127.0.0.1" else "127.0.0.1"
            base_url = f"http://{host_target}:{cls.PORT}"
            named_url = f"http://qng-pthieu10:{cls.PORT}"

            # 1. Hai file Windows Internet Shortcut (.url)
            url_qlht = (
                "[InternetShortcut]\r\n"
                f"URL={base_url}/qlhtdn\r\n"
                "IconIndex=13\r\n"
                r"IconFile=C:\Windows\System32\shell32.dll" + "\r\n"
            )
            url_kt = (
                "[InternetShortcut]\r\n"
                f"URL={base_url}/kiemtra\r\n"
                "IconIndex=23\r\n"
                r"IconFile=C:\Windows\System32\shell32.dll" + "\r\n"
            )

            f1 = folder / "1_Mo_Phan_Mem_Hoa_Don_Rui_Ro_(Phong_QL_Ho_Tro_DN).url"
            f2 = folder / "2_Tra_Cuu_Ket_Qua_Hoa_Don_Rui_Ro_(Phong_Kiem_Tra).url"
            f1.write_bytes(url_qlht.encode("utf-8"))
            f2.write_bytes(url_kt.encode("utf-8"))
            created_files.extend([f1.name, f2.name])

            # 2. File cổng mở nhanh thông minh (.html)
            smart_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Mở Hệ thống Quản lý Hóa đơn Rủi ro 2026</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
  .box {{ background: #1e293b; border: 2px solid #3b82f6; border-radius: 16px; padding: 28px 34px; max-width: 560px; width: 92%; text-align: center; box-shadow: 0 20px 45px rgba(0,0,0,0.5); }}
  h2 {{ margin: 0 0 8px; color: #60a5fa; font-size: 20px; }}
  p {{ color: #cbd5e1; font-size: 13.5px; line-height: 1.5; margin-bottom: 20px; }}
  .btn-group {{ display: flex; flex-direction: column; gap: 12px; }}
  a.btn {{ display: block; padding: 14px 18px; border-radius: 10px; font-weight: 800; font-size: 14.5px; text-decoration: none; color: #fff; transition: 0.15s; }}
  a.qlht {{ background: linear-gradient(90deg, #1d4ed8, #1e40af); border: 1px solid #60a5fa; }}
  a.qlht:hover {{ filter: brightness(1.12); }}
  a.kt {{ background: linear-gradient(90deg, #6d28d9, #5b21b6); border: 1px solid #a78bfa; }}
  a.kt:hover {{ filter: brightness(1.12); }}
  .foot {{ margin-top: 18px; font-size: 12px; color: #94a3b8; }}
  code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #38bdf8; }}
</style>
</head>
<body>
  <div class="box">
    <h2>HỆ THỐNG QUẢN LÝ HÓA ĐƠN RỦI RO 2026</h2>
    <p>Chọn đúng bộ phận công tác của bạn để vào thẳng màn hình nghiệp vụ tương ứng (Hệ thống tự động nhận diện Account máy tính nội bộ):</p>
    <div class="btn-group">
      <a class="btn qlht" id="linkQlht" href="{base_url}/qlhtdn">✍️ VÀO PHÒNG QUẢN LÝ HỖ TRỢ DOANH NGHIỆP<br><span style="font-size:12px; font-weight:600; opacity:0.9;">(Tiếp nhận Công văn cảnh báo & Cập nhật Kết quả xử lý)</span></a>
      <a class="btn kt" id="linkKt" href="{base_url}/kiemtra">🔍 VÀO PHÒNG KIỂM TRA<br><span style="font-size:12px; font-weight:600; opacity:0.9;">(Tra cứu nhanh MST & Mở xem File PDF Kết quả giải trình)</span></a>
    </div>
    <div class="foot" id="statusFoot">Đang kết nối trạm chủ: <code>{base_url}</code> (Tên máy: <code>{hostname}</code>)</div>
  </div>
<script>
  (async function() {{
    const candidates = ["{base_url}", "http://127.0.0.1:{cls.PORT}", "{named_url}"];
    for (const u of candidates) {{
      try {{
        const ctrl = new AbortController();
        setTimeout(() => ctrl.abort(), 1200);
        const r = await fetch(u + "/api/bootstrap", {{ signal: ctrl.signal }});
        if (r.ok) {{
          document.getElementById("linkQlht").href = u + "/qlhtdn";
          document.getElementById("linkKt").href = u + "/kiemtra";
          document.getElementById("statusFoot").innerHTML = "🟢 Đã kết nối sẵn sàng với trạm chủ: <code>" + u + "</code>";
          break;
        }}
      }} catch (e) {{}}
    }}
  }})();
</script>
</body>
</html>"""
            f3 = folder / "Mo_Nhanh_He_Thong_Hoa_Don_Rui_Ro_2026.html"
            f3.write_text(smart_html, encoding="utf-8")
            created_files.append(f3.name)
        except Exception:
            pass
        return created_files

    @classmethod
    def _seed_sample_pdfs_if_empty(cls, folder: Path) -> None:
        """Tạo sẵn 3 file PDF mẫu và các Shortcut Web mở nhanh trong kho `\\\\qng-pthieu10\\SharePdf`."""
        cls.create_web_shortcuts_in_sharepdf(folder)
        try:
            if list(folder.glob("*.pdf")):
                return
            samples = {
                "CB_6526_TCS2_QLDN1_CanhBao_MinhDuc.pdf": [
                    "THUE CO SO 2 THANH PHO HO CHI MINH",
                    "So: 6526/TCS2-QLDN1",
                    "Ngay 26 thang 12 nam 2025",
                    "V/v: Canh bao NNT co dau hieu rui ro cao ve thue va hoa don",
                    "Doanh nghiep co dau hieu rui ro (MST ban): 0318185232 - CONG TY TNHH HAN HOAN HP",
                    "Doanh nghiep co lien quan truc tiep (MST mua): 4300512503 - CONG TY CP DAU TU XAY DUNG MINH DUC",
                ],
                "KQ_4300512503_CV0901_GiaiTrinh_MinhDuc.pdf": [
                    "CONG VAN GIAI TRINH VA KET QUA XU LY HOA DON RUI RO",
                    "So: 0901/CV/2026-MD",
                    "Ngay 09 thang 01 nam 2026",
                    "Don vi giai trinh: CONG TY CO PHAN DAU TU XAY DUNG MINH DUC - MST: 4300512503",
                    "Lien quan den MST rui ro: 0318185232 (Cong ty TNHH Han Hoan HP)",
                    "Ket qua: Tu ke khai dieu chinh giam 14 hoa don, giam chi phi 12.810.755.749 d, giam VAT 1.026.905.189 d.",
                ],
                "KQ_4300341921_CV30_GiaiTrinh_PhucHung.pdf": [
                    "HO SO KET QUA GIAI TRINH DOANH NGHIEP",
                    "So: 30/CTPH-TCKT",
                    "Ngay 30 thang 01 nam 2026",
                    "Don vi: CONG TY CO PHAN PHUC HUNG - MST: 4300341921",
                    "Lien quan MST rui ro: 0318674000",
                    "Ket qua: Cam ket mua vat tu y te phuc vu kham chua benh (3 hoa don, gia tri 21.800.000 d).",
                ],
            }
            for fname, text_lines in samples.items():
                (folder / fname).write_bytes(cls._build_minimal_valid_pdf(text_lines))
        except Exception:
            pass

    @classmethod
    def set_custom_share_path(cls, new_path: str) -> Tuple[bool, str]:
        from .database import DatabaseEngineModule

        raw = new_path.strip()
        if raw.upper() == "SIMULATE" or raw == cls.TARGET_UNC_PATH:
            cls._active_storage_dir = None
            folder, mode = cls.resolve_storage_dir()
            DatabaseEngineModule.initialize_schema()
            return True, f"Đang sử dụng kho {cls.TARGET_UNC_PATH} (Ánh xạ tại: {folder})"

        p = Path(raw)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".cqt_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            cls._active_storage_dir = p
            cls._storage_mode = "REAL_UNC_LAN"
            cls._seed_sample_pdfs_if_empty(p)
            DatabaseEngineModule.initialize_schema()
            return True, f"Đã trỏ nguồn dữ liệu .db và PDF tới: {p}"
        except Exception as exc:
            return False, f"Không thể mở đường dẫn '{raw}': {exc}"

    @classmethod
    def get_db_path(cls) -> Path:
        folder, _ = cls.resolve_storage_dir()
        return folder / "csdl_hoa_don_rui_ro_2026.db"

    @classmethod
    def get_pdf_vault_dir(cls) -> Path:
        folder, _ = cls.resolve_storage_dir()
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @classmethod
    def list_sharepdf_files(cls) -> List[Dict[str, Any]]:
        vault = cls.get_pdf_vault_dir()
        pdf_items: List[Dict[str, Any]] = []
        try:
            for p in sorted(vault.rglob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
                rel_name = str(p.relative_to(vault)).replace("\\", "/")
                stat = p.stat()
                unc_full = cls.TARGET_UNC_PATH.rstrip("\\") + "\\" + rel_name.replace("/", "\\")
                pdf_items.append(
                    {
                        "name": rel_name,
                        "size_kb": round(stat.st_size / 1024, 1),
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                        "unc_full_path": unc_full,
                        "local_real_path": str(p),
                    }
                )
        except Exception:
            pass
        return pdf_items[:500]

    @classmethod
    def detect_internal_machine_identity(cls, client_ip: str) -> Dict[str, str]:
        """
        Nhận diện tự động danh tính máy trạm theo Account Windows hoặc IP nội bộ.
        Có cơ chế cache và timeout nhanh tránh block luồng HTTP trong mạng LAN.
        """
        from .database import DatabaseEngineModule

        host_user = "congchuc"
        try:
            host_user = os.environ.get("USERNAME") or getpass.getuser() or "congchuc"
        except Exception:
            pass
        domain = os.environ.get("USERDOMAIN") or platform.node() or "CQT-LAN"
        local_hostname = socket.gethostname()
        lan_ip = cls.get_lan_ip()

        if client_ip in ("127.0.0.1", "::1", lan_ip):
            workstation_name = local_hostname
            account_id = host_user
        else:
            if client_ip in cls._dns_cache:
                workstation_name = cls._dns_cache[client_ip]
            else:
                workstation_name = client_ip
                try:
                    # Chạy reverse DNS nhưng không để treo lâu
                    orig_timeout = socket.getdefaulttimeout()
                    socket.setdefaulttimeout(0.3)
                    resolved_host, _, _ = socket.gethostbyaddr(client_ip)
                    socket.setdefaulttimeout(orig_timeout)
                    if resolved_host:
                        workstation_name = resolved_host.split(".")[0]
                except Exception:
                    pass
                cls._dns_cache[client_ip] = workstation_name

            m = re.search(r"(?:qng[\-_])?([a-zA-Z0-9]+)$", workstation_name)
            account_id = m.group(1).lower() if m else f"user_{client_ip.split('.')[-1]}"

        matched_name = DatabaseEngineModule.match_officer_by_account(account_id)
        display_name = matched_name or f"{account_id} ({workstation_name})"

        return {
            "account_id": account_id,
            "domain_account": f"{domain}\\{account_id}",
            "workstation": workstation_name,
            "client_ip": client_ip,
            "matched_officer_name": display_name,
        }

    @staticmethod
    def get_lan_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def is_internal_lan_ip(client_ip: str) -> bool:
        try:
            ip_obj = ipaddress.ip_address(client_ip)
            return ip_obj.is_private or ip_obj.is_loopback
        except ValueError:
            return False

    @classmethod
    def verify_owner_pin(cls, pin: str) -> bool:
        return (pin or "").strip() == cls.OWNER_SECRET_PIN
