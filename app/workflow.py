"""
[MODULE RISK WORKFLOW & BUSINESS LOGIC]
Điều phối luồng nghiệp vụ giữa 2 bộ phận:
  - Phòng Quản lý Hỗ trợ DN: Tiếp nhận cảnh báo (TH_Rủi ro) -> DSRR 2026, cập nhật kết quả giải trình 4 nhóm.
  - Phòng Kiểm tra: Tra cứu lịch sử rủi ro, đối chiếu số liệu, kết xuất báo cáo Excel 2 sheet chuẩn ngành thuế.
"""

import io
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from .config import ConfigSecurityModule
from .database import DatabaseEngineModule


def add_working_days(start_date_str: str, working_days: int = 10) -> str:
    """Cộng thêm n ngày làm việc (không tính Thứ 7, Chủ nhật)."""
    if not start_date_str:
        return ""
    try:
        clean = start_date_str.strip()
        if "/" in clean:
            d = datetime.strptime(clean, "%d/%m/%Y")
        elif "-" in clean:
            d = datetime.strptime(clean, "%Y-%m-%d")
        else:
            return ""
    except Exception:
        return ""

    count = 0
    while count < working_days:
        d += timedelta(days=1)
        if d.weekday() < 5:  # Thứ 2 đến Thứ 6
            count += 1
    return d.strftime("%d/%m/%Y")


class RiskWorkflowModule:
    @staticmethod
    def build_cong_van_c_col(so_ky_hieu: str, ngay_vb: str, noi_gui: str) -> str:
        """Tạo định dạng Cột C chuẩn của sheet TH_Rủi ro."""
        return (
            f"Công văn số {(so_ky_hieu or '...').strip()} "
            f"ngày {(ngay_vb or '...').strip()} "
            f"của {(noi_gui or '...').strip()}"
        )

    @staticmethod
    def lookup_nnt(mst: str) -> Tuple[str, str]:
        """Tra cứu nhanh Tên NNT và Cán bộ quản lý từ bảng dm_nnt_cbql."""
        if not mst:
            return "", ""
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            row = conn.execute(
                "SELECT ten_nnt, can_bo_quan_ly FROM dm_nnt_cbql WHERE mst = ?",
                (mst.strip(),),
            ).fetchone()
            if row:
                return row["ten_nnt"] or "", row["can_bo_quan_ly"] or ""
        return "", ""

    @classmethod
    def create_warning_record(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Tiếp nhận văn bản rủi ro mới vào TH_Rủi ro, nếu có đơn vị liên quan trực tiếp thì chuyển DSRR 2026."""
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

        cong_van_col_c = cls.build_cong_van_c_col(so_kh, ngay_vb, noi_gui)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
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

            dsrr_id = None
            ten_dn = (payload.get("ten_cong_ty_lien_quan") or "").strip()
            cb_xu_ly = (payload.get("can_bo_xu_ly") or "").strip()

            if co_lq and mst_lq:
                auto_ten, auto_cb = cls.lookup_nnt(mst_lq)
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
                dsrr_id = cur.lastrowid
            conn.commit()

        return {
            "th_id": th_id,
            "dsrr_id": dsrr_id,
            "cong_van": cong_van_col_c,
            "mst_lq": mst_lq,
            "ten_dn": ten_dn,
            "can_bo_xu_ly": cb_xu_ly,
            "lien_quan_qldn1": bool(dsrr_id),
        }

    @classmethod
    def update_dsrr_record(cls, rec_id: int, payload: Dict[str, Any]) -> None:
        """Cập nhật thông tin xử lý, tiến độ giải trình & số liệu 4 nhóm hóa đơn tại DSRR 2026."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        officer = (payload.get("officer_name") or "Công chức").strip()
        so_tb = (payload.get("so_thong_bao") or "").strip()
        ngay_tb = (payload.get("ngay_thong_bao") or "").strip()
        han_gt = (payload.get("han_giai_trinh") or "").strip()
        if ngay_tb and not han_gt:
            han_gt = add_working_days(ngay_tb, 10)

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
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
            conn.commit()

    @classmethod
    def export_excel_bytes(cls) -> bytes:
        """Xuất file Excel chuẩn gồm 2 sheet: 'DSRR 2026' và 'TH_Rủi ro'."""
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            df_th = pd.read_sql_query(
                """
                SELECT
                    mst AS 'Mã số thuế bên bán rủi ro',
                    ve_viec AS 'Nội dung văn bản',
                    cong_van AS 'Công văn cảnh báo rủi ro',
                    mst_lien_quan AS 'Mã số thuế doanh nghiệp quản lý liên quan',
                    attachment_name AS 'File PDF Cảnh báo'
                FROM th_rui_ro ORDER BY id ASC
                """,
                conn,
            )
            df_dsrr = pd.read_sql_query(
                """
                SELECT
                    id AS 'STT',
                    ngay_vb_den AS 'Ngày văn bản đến',
                    so_den_vb AS 'Số đến của văn bản',
                    so_ky_hieu_vb AS 'Số ký hiệu văn bản',
                    ngay_thang_vb AS 'Ngày tháng văn bản',
                    noi_gui AS 'Nơi gửi',
                    lien_quan_cong_an AS 'Liên quan Công An',
                    mst AS 'Mã số thuế',
                    ten_cong_ty AS 'Tên Doanh nghiệp',
                    tinh_trang_xu_ly AS 'Tình trạng xử lý',
                    can_bo_xu_ly AS 'Cán bộ thuế phụ trách',
                    viec_da_thuc_hien AS 'Những việc cơ quan thuế đã thực hiện',
                    so_thong_bao AS 'Số thông báo giải trình',
                    ngay_thong_bao AS 'Ngày ban hành thông báo',
                    han_giai_trinh AS 'Thời hạn giải trình (+10 ngày làm việc)',
                    ghi_chu AS 'Ghi chú tiến độ',
                    mst_rui_ro AS 'Mã số thuế có dấu hiệu rủi ro',
                    ten_cty_rui_ro AS 'Tên công ty có dấu hiệu rủi ro',
                    nnt_giai_trinh AS 'Nội dung Người nộp thuế giải trình',
                    cam_ket_so_hd AS 'Số lượng hóa đơn (Cam kết có mua bán)',
                    cam_ket_gia_tri AS 'Tổng giá trị chưa thuế (Cam kết)',
                    cam_ket_thue_gtgt AS 'Tiền thuế giá trị gia tăng (Cam kết)',
                    dieu_chinh_so_hd AS 'Số lượng hóa đơn (Tự điều chỉnh)',
                    dieu_chinh_giam_chi_phi AS 'Giảm chi phí',
                    dieu_chinh_giam_khau_tru AS 'Giảm khấu trừ thuế GTGT',
                    dieu_chinh_thue_tndn AS 'Số thuế TNDN phải nộp (Tự điều chỉnh)',
                    dieu_chinh_thue_gtgt AS 'Số thuế GTGT phải nộp (Tự điều chỉnh)',
                    khong_kk_so_hd AS 'Số lượng hóa đơn (Có nhận nhưng không kê khai)',
                    khong_kk_gia_tri AS 'Giá trị chưa thuế (Không kê khai)',
                    khong_kk_thue_gtgt AS 'Tiền thuế giá trị gia tăng (Không kê khai)',
                    khong_nhan_so_hd AS 'Số lượng hóa đơn (Không nhận được hóa đơn)',
                    khong_nhan_gia_tri AS 'Giá trị chưa thuế (Không nhận hóa đơn)',
                    khong_nhan_thue_gtgt AS 'Tiền thuế giá trị gia tăng (Không nhận hóa đơn)',
                    de_xuat_xu_ly AS 'Đề xuất biện pháp xử lý tiếp theo',
                    result_pdf_name AS 'File PDF Kết quả đính kèm'
                FROM dsrr_2026 ORDER BY id ASC
                """,
                conn,
            )

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_dsrr.to_excel(writer, sheet_name="DSRR 2026", index=False)
            df_th.to_excel(writer, sheet_name="TH_Rủi ro", index=False)
        return buf.getvalue()
