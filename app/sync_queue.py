"""
[MODULE LOCAL USER STAGING QUEUE & AUTO-SYNC ENGINE]
=====================================================
Giải pháp bộ đệm ghi độc lập theo từng Cán bộ (User-Specific Staging DB)
và hàng chờ tự động đồng bộ (Auto-Retry Queue) vào CSDL dùng chung \\\\qng-pthieu10\\SharePdf.

Nguyên lý hoạt động:
1. ĐỘC LẬP HOÀN TOÀN TẠI LOCAL:
   - Mỗi máy cá nhân khi người dùng bấm Lưu sẽ ghi tức thì vào CSDL hàng chờ cục bộ
     tại `%LOCALAPPDATA%\\QuanLyHoaDonRuiRo\\staging_<username>.db`.
   - Vì ghi vào ổ C: cục bộ riêng của từng người, tốc độ < 1ms và KHÔNG BAO GIỜ bị lỗi 'database is locked'.

2. TỰ ĐỘNG THỬ GHI VÀO CSDL DÙNG CHUNG:
   - Luồng đồng bộ ngầm ngay lập tức kết nối tới CSDL chính tại thư mục Share.
   - Nếu CSDL chính đang rảnh: Ghi ngay lập tức và commit an toàn.
   - Nếu CSDL chính đang bận / bị khóa bởi cán bộ khác: Hàng chờ tự động giữ bản ghi,
     thử lại (exponential backoff) trong luồng ngầm cho đến khi CSDL chính rảnh.

3. TỰ ĐỘNG XÓA CSDL TẠM ĐỂ NHẸ MÁY:
   - Ngay sau khi ghi thành công vào CSDL chính, bản ghi trong hàng chờ sẽ được xóa.
   - Khi hàng chờ trống (0 bản ghi), file CSDL tạm `staging_<username>.db` sẽ được đóng
     và TỰ ĐỘNG XÓA BỎ KHỎI Ổ ĐĨA CÁ NHÂN để giải phóng hoàn toàn dung lượng máy trạm.
   - File chỉ được giữ lại tạm thời nếu CSDL chính đang bận hoặc mất kết nối mạng.
"""

import gc
import json
import logging
import os
import re
import sqlite3
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import ConfigSecurityModule
from .database import DatabaseEngineModule

logger = logging.getLogger("SyncQueue")


class LocalSyncEngineModule:
    _lock = threading.RLock()
    _worker_thread: Optional[threading.Thread] = None
    _stop_worker_evt = threading.Event()
    _trigger_evt = threading.Event()

    @classmethod
    def get_staging_dir(cls) -> Path:
        """Thư mục lưu DB tạm độc lập cho từng user tại %LOCALAPPDATA%\\QuanLyHoaDonRuiRo."""
        base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "QuanLyHoaDonRuiRo"
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except Exception:
            fallback = Path(tempfile.gettempdir()) / "QuanLyHoaDonRuiRo"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    @classmethod
    def sanitize_user_id(cls, user_id: str) -> str:
        """Làm sạch tên username để an toàn cho tên file trên Windows."""
        if not user_id:
            user_id = "default_user"
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(user_id).strip())
        return clean or "user"

    @classmethod
    def get_user_staging_db_path(cls, user_id: str) -> Path:
        """Đường dẫn file .db tạm của user cụ thể."""
        s_user = cls.sanitize_user_id(user_id)
        return cls.get_staging_dir() / f"staging_{s_user}.db"

    @classmethod
    def _open_staging_conn(cls, db_path: Path) -> sqlite3.Connection:
        """Mở kết nối DB tạm của user với PRAGMA DELETE mode để đóng là xóa được ngay."""
        conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Dùng DELETE mode để không để lại file -wal và -shm phụ trên Windows
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS local_staging_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT DEFAULT ''
            );
            """
        )
        conn.commit()
        return conn

    @classmethod
    def enqueue_action(cls, user_id: str, action_type: str, target_id: str, payload: Dict[str, Any]) -> int:
        """
        Bước 1: Ghi bản ghi vào CSDL tạm cá nhân (Local Staging DB).
        Tốc độ siêu nhanh, độc lập trên máy tính cá nhân.
        """
        db_path = cls.get_user_staging_db_path(user_id)
        payload_json = json.dumps(payload, ensure_ascii=False)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        with cls._lock:
            conn = cls._open_staging_conn(db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO local_staging_queue (user_id, action_type, target_id, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, action_type, str(target_id), payload_json, now_str),
                )
                conn.commit()
                staged_id = cur.lastrowid
            finally:
                conn.close()

        return staged_id

    @classmethod
    def enqueue_and_sync(
        cls, user_id: str, action_type: str, target_id: str, payload: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Thực hiện chu trình 3 bước hoàn chỉnh:
        1. Ghi vào Local Staging DB của User.
        2. Thử đẩy ngay vào Central DB.
        3. Nếu Central bận/khóa: giữ lại trong hàng chờ và chuyển cho worker ngầm;
           Nếu Central ghi xong: tự động xóa bản ghi & dọn dẹp file .db của user.
        """
        staged_id = cls.enqueue_action(user_id, action_type, target_id, payload)

        # Thử đồng bộ ngay lập tức
        flush_ok, pending_count, err_msg = cls.flush_user_queue(user_id)

        if flush_ok:
            return (
                True,
                "COMMITTED_CENTRAL",
                {
                    "message": "Đã lưu và đồng bộ trực tiếp vào CSDL dùng chung thành công!",
                    "staged_id": staged_id,
                    "pending_remaining": 0,
                },
            )
        else:
            # Kích hoạt worker ngầm để tự động thử lại liên tục khi Central DB rảnh
            cls._trigger_evt.set()
            return (
                True,
                "QUEUED_LOCAL_PENDING",
                {
                    "message": "CSDL dùng chung đang bận/khóa. Dữ liệu đã lưu an toàn vào bộ đệm cá nhân và đang xếp hàng tự động ghi!",
                    "staged_id": staged_id,
                    "pending_remaining": pending_count,
                    "reason": err_msg,
                },
            )

    @classmethod
    def _execute_action_on_central_db(
        cls, conn: sqlite3.Connection, action_type: str, target_id: str, payload: Dict[str, Any]
    ) -> None:
        """Thực thi câu lệnh SQL nghiệp vụ trực tiếp trên kết nối Central DB."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if action_type == "UPDATE_DSRR":
            rec_id = int(target_id)
            officer = (payload.get("officer_name") or "Công chức").strip()
            so_tb = (payload.get("so_thong_bao") or "").strip()
            ngay_tb = (payload.get("ngay_thong_bao") or "").strip()
            han_gt = (payload.get("han_giai_trinh") or "").strip()
            if ngay_tb and not han_gt:
                from .workflow import add_working_days

                han_gt = add_working_days(ngay_tb, 10)

            conn.execute(
                """
                UPDATE dsrr_2026 SET
                    ten_cong_ty = ?,
                    tinh_trang_xu_ly = ?,
                    can_bo_xu_ly = ?,
                    viec_da_thuc_hien = ?,
                    viec_tiep_tuc = ?,
                    ghi_chu = ?,
                    ten_cty_rui_ro = ?,
                    nnt_giai_trinh = ?,
                    cam_ket_so_hd = ?,
                    cam_ket_gia_tri = ?,
                    cam_ket_thue_gtgt = ?,
                    dieu_chinh_so_hd = ?,
                    dieu_chinh_giam_chi_phi = ?,
                    dieu_chinh_giam_khau_tru = ?,
                    dieu_chinh_thue_tndn = ?,
                    dieu_chinh_thue_gtgt = ?,
                    khong_kk_so_hd = ?,
                    khong_kk_gia_tri = ?,
                    khong_kk_thue_gtgt = ?,
                    khong_nhan_so_hd = ?,
                    khong_nhan_gia_tri = ?,
                    khong_nhan_thue_gtgt = ?,
                    de_xuat_xu_ly = ?,
                    so_thong_bao = ?,
                    ngay_thong_bao = ?,
                    han_giai_trinh = ?,
                    ket_qua_kiem_tra_phong_b = ?,
                    noi_dung_pkt_phan_hoi = ?,
                    result_pdf_name = ?,
                    tbgt_pdf_name = ?,
                    bblv_pdf_name = ?,
                    pkt_pdf_name = ?,
                    attachment_name = CASE WHEN ? != '' THEN ? ELSE attachment_name END,
                    updated_by = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.get("ten_cong_ty", ""),
                    payload.get("tinh_trang_xu_ly", "Đang xử lý"),
                    payload.get("can_bo_xu_ly", ""),
                    payload.get("viec_da_thuc_hien", ""),
                    payload.get("viec_tiep_tuc", ""),
                    payload.get("ghi_chu", ""),
                    payload.get("ten_cty_rui_ro", ""),
                    payload.get("nnt_giai_trinh", ""),
                    int(float(payload.get("cam_ket_so_hd") or 0)),
                    float(payload.get("cam_ket_gia_tri") or 0),
                    float(payload.get("cam_ket_thue_gtgt") or 0),
                    int(float(payload.get("dieu_chinh_so_hd") or 0)),
                    float(payload.get("dieu_chinh_giam_chi_phi") or 0),
                    float(payload.get("dieu_chinh_giam_khau_tru") or 0),
                    float(payload.get("dieu_chinh_thue_tndn") or 0),
                    float(payload.get("dieu_chinh_thue_gtgt") or 0),
                    int(float(payload.get("khong_kk_so_hd") or 0)),
                    float(payload.get("khong_kk_gia_tri") or 0),
                    float(payload.get("khong_kk_thue_gtgt") or 0),
                    int(float(payload.get("khong_nhan_so_hd") or 0)),
                    float(payload.get("khong_nhan_gia_tri") or 0),
                    float(payload.get("khong_nhan_thue_gtgt") or 0),
                    payload.get("de_xuat_xu_ly", ""),
                    so_tb,
                    ngay_tb,
                    han_gt,
                    payload.get("ket_qua_kiem_tra_phong_b", ""),
                    payload.get("noi_dung_pkt_phan_hoi") or payload.get("ket_qua_kiem_tra_phong_b", ""),
                    payload.get("result_pdf_name", ""),
                    payload.get("tbgt_pdf_name", ""),
                    payload.get("bblv_pdf_name", ""),
                    payload.get("pkt_pdf_name", ""),
                    (payload.get("attachment_name") or "").strip(),
                    (payload.get("attachment_name") or "").strip(),
                    officer,
                    now_str,
                    rec_id,
                ),
            )

        elif action_type == "CREATE_TH":
            from .workflow import RiskWorkflowModule

            mst_rr = (payload.get("mst_rui_ro") or "").strip()
            ten_cty_rr = (payload.get("ten_cty_rui_ro") or "").strip()
            ve_viec = (payload.get("ve_viec") or "NNT bán trái phép hóa đơn").strip()
            so_den = (payload.get("so_den_vb") or "").strip()
            so_kh = (payload.get("so_ky_hieu_vb") or "").strip()
            ngay_vb = (payload.get("ngay_thang_vb") or "").strip()
            noi_gui = (payload.get("noi_gui") or "").strip()
            ngay_den = (payload.get("ngay_vb_den") or datetime.now().strftime("%d/%m/%Y")).strip()
            han_xl = (payload.get("han_xu_ly") or "").strip()
            mst_lq = (payload.get("mst_lien_quan") or "").strip()
            co_lq = bool(payload.get("co_lien_quan_truc_tiep", True))
            lien_quan_ca = (payload.get("lien_quan_cong_an") or "").strip()
            officer = (payload.get("officer_name") or "Công chức").strip()
            edoc_url = (payload.get("edoc_url") or "").strip()
            if not edoc_url and so_den:
                edoc_url = f"{ConfigSecurityModule.EDOC_BASE_URL}{so_den}"

            att_name = (payload.get("attachment_name") or "").strip()
            att_sha = (payload.get("attachment_sha256") or "").strip()
            cong_van_col_c = RiskWorkflowModule.build_cong_van_c_col(so_kh, ngay_vb, noi_gui)

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO th_rui_ro (
                    mst, ve_viec, cong_van, mst_lien_quan,
                    so_den_vb, so_ky_hieu_vb, ngay_thang_vb, noi_gui,
                    ngay_vb_den, han_xu_ly, edoc_url,
                    attachment_name, attachment_sha256, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mst_rr,
                    ve_viec,
                    cong_van_col_c,
                    mst_lq,
                    so_den,
                    so_kh,
                    ngay_vb,
                    noi_gui,
                    ngay_den,
                    han_xl,
                    edoc_url,
                    att_name,
                    att_sha,
                    officer,
                    now_str,
                ),
            )
            th_id = cur.lastrowid

            if co_lq and mst_lq:
                ten_dn = (payload.get("ten_cong_ty_lien_quan") or "").strip()
                cb_xu_ly = (payload.get("can_bo_xu_ly") or "").strip()
                auto_ten, auto_cb = RiskWorkflowModule.lookup_nnt(mst_lq)
                if not ten_dn:
                    ten_dn = auto_ten
                if not cb_xu_ly:
                    cb_xu_ly = auto_cb or officer

                cur.execute(
                    """
                    INSERT INTO dsrr_2026 (
                        th_rui_ro_id, ngay_vb_den, so_den_vb, so_ky_hieu_vb,
                        ngay_thang_vb, noi_gui, lien_quan_cong_an,
                        mst, ten_cong_ty, tinh_trang_xu_ly, can_bo_xu_ly,
                        ghi_chu, mst_rui_ro, ten_cty_rui_ro,
                        edoc_url, attachment_name, result_pdf_name, attachment_sha256,
                        updated_by, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Chưa xử lý', ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
                    """,
                    (
                        th_id,
                        ngay_den,
                        so_den,
                        so_kh,
                        ngay_vb,
                        noi_gui,
                        lien_quan_ca,
                        mst_lq,
                        ten_dn,
                        cb_xu_ly,
                        f"Hạn xử lý: {han_xl}" if han_xl else "",
                        mst_rr,
                        ten_cty_rr,
                        edoc_url,
                        att_name,
                        att_sha,
                        officer,
                        now_str,
                    ),
                )

        elif action_type == "SAVE_NNT":
            mst = (payload.get("mst") or "").strip()
            ten = (payload.get("ten_nnt") or "").strip()
            cb = (payload.get("can_bo_quan_ly") or "").strip()
            em = (payload.get("email_cbql") or "").strip()
            dc = (payload.get("dia_chi") or "").strip()
            conn.execute(
                """
                INSERT INTO dm_nnt_cbql (mst, ten_nnt, can_bo_quan_ly, email_cbql, dia_chi)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mst) DO UPDATE SET
                    ten_nnt = excluded.ten_nnt,
                    can_bo_quan_ly = excluded.can_bo_quan_ly,
                    email_cbql = excluded.email_cbql,
                    dia_chi = excluded.dia_chi
                """,
                (mst, ten, cb, em, dc),
            )

        elif action_type == "DELETE_NNT":
            del_mst = (target_id or payload.get("mst", "")).strip()
            conn.execute("DELETE FROM dm_nnt_cbql WHERE mst = ?", (del_mst,))

        else:
            raise ValueError(f"Hành động không xác định: {action_type}")

    @classmethod
    def get_central_conn(cls, timeout: float = 2.0) -> sqlite3.Connection:
        """Kết nối tới Central DB với timeout ngắn để phản hồi UI tức thì khi Central DB bị khóa."""
        db_file = ConfigSecurityModule.get_db_path()
        conn = sqlite3.connect(str(db_file), timeout=timeout, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)};")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @classmethod
    def flush_user_queue(cls, user_id: str) -> Tuple[bool, int, str]:
        """
        Đẩy tất cả bản ghi còn tồn đọng trong staging DB của user vào Central DB.
        - Xử lý retry nếu gặp 'database is locked'.
        - Xóa bản ghi đã commit thành công.
        - TỰ ĐỘNG XÓA FILE .DB CỦA USER NẾU HÀNG CHỜ ĐÃ SẠCH 100%.
        """
        db_path = cls.get_user_staging_db_path(user_id)
        if not db_path.exists():
            return True, 0, ""

        with cls._lock:
            # 1. Đọc danh sách bản ghi cần đồng bộ
            s_conn = cls._open_staging_conn(db_path)
            try:
                rows = s_conn.execute(
                    "SELECT id, action_type, target_id, payload_json, retry_count FROM local_staging_queue ORDER BY id ASC"
                ).fetchall()
            except Exception as e:
                return False, -1, f"Lỗi đọc DB tạm: {e}"
            finally:
                s_conn.close()

            if not rows:
                cls._cleanup_user_staging_db(db_path)
                return True, 0, ""

            # 2. Thử kết nối vào Central DB với cơ chế bắt lỗi locked & retry
            max_attempts = 3
            committed_ids = []
            last_err = ""

            for r in rows:
                item_id = r["id"]
                action_type = r["action_type"]
                target_id = r["target_id"]
                payload = json.loads(r["payload_json"])

                item_success = False
                for attempt in range(max_attempts):
                    try:
                        c_conn = cls.get_central_conn(timeout=1.0)
                        try:
                            cls._execute_action_on_central_db(c_conn, action_type, target_id, payload)
                            c_conn.commit()
                            item_success = True
                            committed_ids.append(item_id)
                        finally:
                            c_conn.close()
                        break
                    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
                        err_str = str(exc).lower()
                        if "locked" in err_str or "busy" in err_str:
                            last_err = f"Central DB đang bận/khóa (Lần thử {attempt + 1}/{max_attempts}): {exc}"
                            time.sleep(0.15 * (2**attempt))
                            continue
                        else:
                            last_err = f"Lỗi thực thi SQL: {exc}"
                            break
                    except Exception as exc:
                        last_err = f"Lỗi không xác định: {exc}"
                        break

                if not item_success:
                    # Cập nhật số lần thử
                    conn_err = cls._open_staging_conn(db_path)
                    try:
                        conn_err.execute(
                            "UPDATE local_staging_queue SET retry_count = retry_count + 1, last_error = ? WHERE id = ?",
                            (last_err, item_id),
                        )
                        conn_err.commit()
                    except Exception:
                        pass
                    finally:
                        conn_err.close()
                    break

            # 3. Xóa các bản ghi đã commit thành công khỏi Local Staging
            if committed_ids:
                s_del = cls._open_staging_conn(db_path)
                try:
                    q_marks = ",".join("?" for _ in committed_ids)
                    s_del.execute(f"DELETE FROM local_staging_queue WHERE id IN ({q_marks})", committed_ids)
                    s_del.commit()
                    remaining = s_del.execute("SELECT COUNT(*) FROM local_staging_queue").fetchone()[0]
                finally:
                    s_del.close()
            else:
                remaining = len(rows)

            # 4. YÊU CẦU ĐẶC BIỆT CỦA USER:
            # "sau khi ghi dữ liệu vào db chính xong thì thực hiện xóa db theo user người dùng đi cho nhẹ máy,
            #  chỉ giữ db khi chưa ghi được vào db chính."
            if remaining == 0:
                cls._cleanup_user_staging_db(db_path)
                return True, 0, ""
            else:
                return False, remaining, last_err

    @classmethod
    def _cleanup_user_staging_db(cls, db_path: Path) -> None:
        """Đóng kết nối và xóa sạch file .db của user để nhẹ máy hoàn toàn."""
        try:
            if not db_path.exists():
                return
            gc.collect()
            time.sleep(0.05)
            db_path.unlink(missing_ok=True)
            Path(f"{db_path}-wal").unlink(missing_ok=True)
            Path(f"{db_path}-shm").unlink(missing_ok=True)
        except Exception:
            pass

    @classmethod
    def flush_all_pending_queues(cls) -> Dict[str, Any]:
        """Quét toàn bộ các file staging_*.db còn tồn đọng và tự động đồng bộ."""
        s_dir = cls.get_staging_dir()
        db_files = list(s_dir.glob("staging_*.db"))
        total_remaining = 0
        flushed_users = []

        for f in db_files:
            m = re.match(r"staging_(.+)\.db$", f.name)
            if not m:
                continue
            u_name = m.group(1)
            ok, rem, err = cls.flush_user_queue(u_name)
            total_remaining += rem
            flushed_users.append({"user": u_name, "ok": ok, "remaining": rem, "error": err})

        return {"db_files_found": len(db_files), "total_pending": total_remaining, "details": flushed_users}

    @classmethod
    def get_sync_status(cls, user_id: str = "") -> Dict[str, Any]:
        """Kiểm tra trạng thái hàng chờ của user và toàn bộ hệ thống."""
        user_pending = 0
        if user_id:
            db_p = cls.get_user_staging_db_path(user_id)
            if db_p.exists():
                try:
                    c = cls._open_staging_conn(db_p)
                    user_pending = c.execute("SELECT COUNT(*) FROM local_staging_queue").fetchone()[0]
                    c.close()
                except Exception:
                    pass

        s_dir = cls.get_staging_dir()
        all_dbs = list(s_dir.glob("staging_*.db"))
        total_pending = 0
        for p in all_dbs:
            try:
                c = cls._open_staging_conn(p)
                total_pending += c.execute("SELECT COUNT(*) FROM local_staging_queue").fetchone()[0]
                c.close()
            except Exception:
                pass

        return {
            "user_id": user_id,
            "user_pending": user_pending,
            "total_system_pending": total_pending,
            "active_staging_files": len(all_dbs),
            "is_clean": (total_pending == 0 and len(all_dbs) == 0),
        }

    @classmethod
    def start_background_worker(cls) -> None:
        """Khởi động luồng ngầm chạy suốt vòng đời ứng dụng để tự động thử lại khi Central DB rảnh."""
        if cls._worker_thread is not None and cls._worker_thread.is_alive():
            return

        cls._stop_worker_evt.clear()

        def _worker_loop():
            try:
                cls.flush_all_pending_queues()
            except Exception:
                pass

            while not cls._stop_worker_evt.is_set():
                cls._trigger_evt.wait(timeout=4.0)
                cls._trigger_evt.clear()
                if cls._stop_worker_evt.is_set():
                    break
                try:
                    cls.flush_all_pending_queues()
                except Exception:
                    pass

        cls._worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="SyncQueueWorker")
        cls._worker_thread.start()

    @classmethod
    def stop_background_worker(cls) -> None:
        """Dừng luồng ngầm và thực hiện đợt flush cuối cùng trước khi thoát app."""
        cls._stop_worker_evt.set()
        cls._trigger_evt.set()
        if cls._worker_thread and cls._worker_thread.is_alive():
            cls._worker_thread.join(timeout=2.0)
        try:
            cls.flush_all_pending_queues()
        except Exception:
            pass
