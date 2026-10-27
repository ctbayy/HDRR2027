"""
[MODULE DATABASE ENGINE & AUTO BACKUP]
Quản lý kết nối SQLite, tự động khởi tạo Schema, đánh chỉ mục (Index) tăng tốc,
nạp Seed Data từ app.seed_data, và tự động tạo Snapshot Backup định kỳ hàng ngày.
"""

import base64
import json
import re
import shutil
import sqlite3
import threading
import zlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import ConfigSecurityModule
from .seed_data import EMBEDDED_REAL_DATA_B64


class DatabaseEngineModule:
    _lock = threading.RLock()

    @classmethod
    def get_conn(cls) -> sqlite3.Connection:
        db_file = ConfigSecurityModule.get_db_path()
        conn = sqlite3.connect(str(db_file), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000;")
        # Nếu ở local thì bật WAL để đọc ghi đồng thời siêu nhanh không lo lock
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @classmethod
    def match_officer_by_account(cls, account_prefix: str) -> str:
        """Đối chiếu tự động username máy tính (VD: `bthan`, `pthieu10`) với danh mục CBQL."""
        if not account_prefix:
            return ""
        clean = re.sub(r"[0-9_\-]+$", "", account_prefix.lower().strip())
        try:
            with cls._lock, cls.get_conn() as conn:
                row = conn.execute(
                    """
                    SELECT can_bo_quan_ly FROM dm_nnt_cbql
                    WHERE LOWER(email_cbql) LIKE ? OR LOWER(email_cbql) LIKE ?
                    LIMIT 1
                    """,
                    (f"{account_prefix.lower()}%", f"{clean}%"),
                ).fetchone()
                if row and row["can_bo_quan_ly"]:
                    return row["can_bo_quan_ly"]
        except Exception:
            pass
        if "pthieu" in account_prefix.lower():
            return "Phan Trung Hiếu"
        return ""

    @classmethod
    def create_auto_backup(cls, force: bool = False) -> Optional[str]:
        """
        Tự động tạo bản sao lưu an toàn CSDL (Snapshot Backup) vào thư mục backups/.
        - Nếu force=False: chỉ sao lưu 1 lần mỗi ngày (csdl_hoa_don_rui_ro_YYYYMMDD.db.bak).
        - Nếu force=True: tạo bản sao lưu ngay lập tức (kèm giờ phút giây).
        """
        try:
            db_file = ConfigSecurityModule.get_db_path()
            if not db_file.exists():
                return None

            base_dir = ConfigSecurityModule.get_base_dir()
            backup_dir = base_dir / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            if force:
                now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"csdl_hoa_don_rui_ro_{now_tag}.db.bak"
            else:
                today_tag = datetime.now().strftime("%Y%m%d")
                backup_file = backup_dir / f"csdl_hoa_don_rui_ro_{today_tag}.db.bak"

            if force or not backup_file.exists():
                with cls._lock, cls.get_conn() as src_conn:
                    with sqlite3.connect(str(backup_file)) as dst_conn:
                        src_conn.backup(dst_conn)

            # Dọn dẹp backup cũ hơn 14 ngày
            all_baks = sorted(backup_dir.glob("csdl_hoa_don_rui_ro_*.db.bak"))
            if len(all_baks) > 14:
                for old_b in all_baks[:-14]:
                    try:
                        old_b.unlink()
                    except Exception:
                        pass

            return str(backup_file)
        except Exception:
            pass
        return None

    @classmethod
    def get_sys_config(cls, key: str, default: str = "") -> str:
        """Đọc một giá trị cấu hình hệ thống từ bảng sys_configs."""
        try:
            with cls._lock, cls.get_conn() as conn:
                row = conn.execute("SELECT value FROM sys_configs WHERE key = ?", (key,)).fetchone()
                if row and row["value"] is not None:
                    return str(row["value"])
        except Exception:
            pass
        return default

    @classmethod
    def set_sys_config(cls, key: str, value: str, updated_by: str = "Admin") -> None:
        """Ghi hoặc cập nhật một giá trị cấu hình hệ thống vào bảng sys_configs."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with cls._lock, cls.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO sys_configs (key, value, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (key, str(value), now_str, updated_by),
            )
            conn.commit()

    @classmethod
    def initialize_schema(cls) -> None:
        cls.create_auto_backup()

        with cls._lock, cls.get_conn() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS dm_nnt_cbql (
                    mst TEXT PRIMARY KEY,
                    ten_nnt TEXT,
                    can_bo_quan_ly TEXT,
                    email_cbql TEXT,
                    dia_chi TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS th_rui_ro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mst TEXT NOT NULL,
                    ve_viec TEXT NOT NULL,
                    cong_van TEXT NOT NULL,
                    mst_lien_quan TEXT,
                    so_den_vb TEXT,
                    so_ky_hieu_vb TEXT,
                    ngay_thang_vb TEXT,
                    noi_gui TEXT,
                    ngay_vb_den TEXT,
                    han_xu_ly TEXT,
                    edoc_url TEXT,
                    attachment_name TEXT,
                    attachment_sha256 TEXT,
                    created_by TEXT,
                    created_at TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS dsrr_2026 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    th_rui_ro_id INTEGER,
                    ngay_vb_den TEXT,
                    so_den_vb TEXT,
                    so_ky_hieu_vb TEXT,
                    ngay_thang_vb TEXT,
                    noi_gui TEXT,
                    lien_quan_cong_an TEXT,
                    mst TEXT NOT NULL,
                    ten_cong_ty TEXT,
                    tinh_trang_xu_ly TEXT DEFAULT 'Chưa xử lý',
                    can_bo_xu_ly TEXT,
                    viec_da_thuc_hien TEXT,
                    viec_tiep_tuc TEXT,
                    ghi_chu TEXT,
                    mst_rui_ro TEXT,
                    ten_cty_rui_ro TEXT,
                    nnt_giai_trinh TEXT,
                    cam_ket_so_hd INTEGER DEFAULT 0,
                    cam_ket_gia_tri REAL DEFAULT 0,
                    cam_ket_thue_gtgt REAL DEFAULT 0,
                    dieu_chinh_so_hd INTEGER DEFAULT 0,
                    dieu_chinh_giam_chi_phi REAL DEFAULT 0,
                    dieu_chinh_giam_khau_tru REAL DEFAULT 0,
                    dieu_chinh_thue_tndn REAL DEFAULT 0,
                    dieu_chinh_thue_gtgt REAL DEFAULT 0,
                    khong_kk_so_hd INTEGER DEFAULT 0,
                    khong_kk_gia_tri REAL DEFAULT 0,
                    khong_kk_thue_gtgt REAL DEFAULT 0,
                    khong_nhan_so_hd INTEGER DEFAULT 0,
                    khong_nhan_gia_tri REAL DEFAULT 0,
                    khong_nhan_thue_gtgt REAL DEFAULT 0,
                    de_xuat_xu_ly TEXT,
                    so_thong_bao TEXT,
                    ngay_thong_bao TEXT,
                    han_giai_trinh TEXT,
                    ket_qua_kiem_tra_phong_b TEXT,
                    edoc_url TEXT,
                    attachment_name TEXT,
                    result_pdf_name TEXT,
                    tbgt_pdf_name TEXT DEFAULT '',
                    bblv_pdf_name TEXT DEFAULT '',
                    pkt_pdf_name TEXT DEFAULT '',
                    noi_dung_pkt_phan_hoi TEXT DEFAULT '',
                    attachment_sha256 TEXT,
                    updated_by TEXT,
                    updated_at TEXT
                )
                """
            )

            # Đảm bảo các cột mở rộng luôn sẵn sàng
            existing_cols = [
                r["name"] for r in cur.execute("PRAGMA table_info(dsrr_2026)").fetchall()
            ]
            if "result_pdf_name" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN result_pdf_name TEXT DEFAULT ''")
            if "tbgt_pdf_name" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN tbgt_pdf_name TEXT DEFAULT ''")
            if "bblv_pdf_name" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN bblv_pdf_name TEXT DEFAULT ''")
            if "pkt_pdf_name" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN pkt_pdf_name TEXT DEFAULT ''")
            if "noi_dung_pkt_phan_hoi" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN noi_dung_pkt_phan_hoi TEXT DEFAULT ''")
            if "so_thong_bao" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN so_thong_bao TEXT DEFAULT ''")
            if "ngay_thong_bao" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN ngay_thong_bao TEXT DEFAULT ''")
            if "han_giai_trinh" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN han_giai_trinh TEXT DEFAULT ''")
            if "dieu_chinh_thue_tndn" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN dieu_chinh_thue_tndn REAL DEFAULT 0")
            if "dieu_chinh_thue_gtgt" not in existing_cols:
                cur.execute("ALTER TABLE dsrr_2026 ADD COLUMN dieu_chinh_thue_gtgt REAL DEFAULT 0")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stealth_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    user_agent TEXT,
                    officer_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    target_module TEXT NOT NULL,
                    target_mst TEXT,
                    record_id TEXT,
                    event_detail TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_configs (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT,
                    updated_by TEXT
                )
                """
            )

            # Các Index tăng tốc tìm kiếm tức thì trên bảng lớn
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dsrr_mst ON dsrr_2026(mst);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dsrr_mst_rr ON dsrr_2026(mst_rui_ro);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dsrr_status ON dsrr_2026(tinh_trang_xu_ly);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dsrr_officer ON dsrr_2026(can_bo_xu_ly);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_th_mst ON th_rui_ro(mst);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_th_mst_lq ON th_rui_ro(mst_lien_quan);")

            # Nạp Seed Data mầm nếu cơ sở dữ liệu trống
            cur.execute("SELECT COUNT(*) FROM dm_nnt_cbql")
            if cur.fetchone()[0] < 100:
                seed_data = json.loads(
                    zlib.decompress(base64.b64decode(EMBEDDED_REAL_DATA_B64)).decode("utf-8")
                )

                cur.execute("DELETE FROM dm_nnt_cbql")
                cur.executemany(
                    "INSERT OR REPLACE INTO dm_nnt_cbql (mst, ten_nnt, can_bo_quan_ly, email_cbql, dia_chi) VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            n["mst"],
                            n.get("ten_nnt", ""),
                            n.get("can_bo_quan_ly", ""),
                            n.get("email_cbql", ""),
                            n.get("dia_chi", ""),
                        )
                        for n in seed_data.get("nnt_list", [])
                    ],
                )

                cur.execute("SELECT COUNT(*) FROM th_rui_ro")
                if cur.fetchone()[0] == 0:
                    now_init = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    cur.executemany(
                        """
                        INSERT INTO th_rui_ro (
                            mst, ve_viec, cong_van, mst_lien_quan, created_by, created_at
                        ) VALUES (?, ?, ?, ?, 'Hệ thống (Nạp từ Google Sheet)', ?)
                        """,
                        [
                            (
                                r["mst"],
                                r["ve_viec"],
                                r["cong_van"],
                                r.get("mst_lien_quan", ""),
                                now_init,
                            )
                            for r in seed_data.get("th_rui_ro", [])
                        ],
                    )

                cur.execute("SELECT COUNT(*) FROM dsrr_2026")
                if cur.fetchone()[0] == 0:
                    now_init = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    dsrr_rows = []
                    for idx, r in enumerate(seed_data.get("dsrr_2026", [])):
                        att_pdf = "CB_6526_TCS2_QLDN1_CanhBao_MinhDuc.pdf" if idx == 0 else ""
                        res_pdf = (
                            "KQ_4300512503_CV0901_GiaiTrinh_MinhDuc.pdf"
                            if idx == 0
                            else ("KQ_4300341921_CV30_GiaiTrinh_PhucHung.pdf" if idx == 1 else "")
                        )
                        dsrr_rows.append(
                            (
                                r["ngay_vb_den"],
                                r["so_den_vb"],
                                r["so_ky_hieu_vb"],
                                r["ngay_thang_vb"],
                                r["noi_gui"],
                                r["lien_quan_cong_an"],
                                r["mst"],
                                r["ten_cong_ty"],
                                r["tinh_trang_xu_ly"],
                                r["can_bo_xu_ly"],
                                r["viec_da_thuc_hien"],
                                r["viec_tiep_tuc"],
                                r["ghi_chu"],
                                r["mst_rui_ro"],
                                r["ten_cty_rui_ro"],
                                r["nnt_giai_trinh"],
                                r["cam_ket_so_hd"],
                                r["cam_ket_gia_tri"],
                                r["cam_ket_thue_gtgt"],
                                r["dieu_chinh_so_hd"],
                                r["dieu_chinh_giam_chi_phi"],
                                r["dieu_chinh_giam_khau_tru"],
                                r["khong_kk_so_hd"],
                                r["khong_kk_gia_tri"],
                                r["khong_kk_thue_gtgt"],
                                r["khong_nhan_so_hd"],
                                r["khong_nhan_gia_tri"],
                                r["khong_nhan_thue_gtgt"],
                                r["de_xuat_xu_ly"],
                                att_pdf,
                                res_pdf,
                                now_init,
                            )
                        )
                    cur.executemany(
                        """
                        INSERT INTO dsrr_2026 (
                            ngay_vb_den, so_den_vb, so_ky_hieu_vb, ngay_thang_vb,
                            noi_gui, lien_quan_cong_an, mst, ten_cong_ty,
                            tinh_trang_xu_ly, can_bo_xu_ly, viec_da_thuc_hien,
                            viec_tiep_tuc, ghi_chu, mst_rui_ro, ten_cty_rui_ro,
                            nnt_giai_trinh, cam_ket_so_hd, cam_ket_gia_tri,
                            cam_ket_thue_gtgt, dieu_chinh_so_hd, dieu_chinh_giam_chi_phi,
                            dieu_chinh_giam_khau_tru, khong_kk_so_hd, khong_kk_gia_tri,
                            khong_kk_thue_gtgt, khong_nhan_so_hd, khong_nhan_gia_tri,
                            khong_nhan_thue_gtgt, de_xuat_xu_ly,
                            attachment_name, result_pdf_name, updated_by, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Hệ thống (Nạp từ Google Sheet)', ?)
                        """,
                        dsrr_rows,
                    )
            conn.commit()

        # Khởi tạo tài khoản Quản trị viên ban đầu nếu chưa có
        try:
            from .auth import AdminAuthModule
            AdminAuthModule.ensure_admin_initialized()
        except Exception:
            pass
