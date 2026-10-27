"""
[MODULE DOCUMENT INGEST & PDF/EXCEL PARSER]
Bóc tách dữ liệu từ file PDF công văn cảnh báo, lưu trữ vào kho SharePdf,
và phân tích file Excel 7 cột từ phần mềm Quản lý văn bản (QLVB).
"""

import hashlib
import io
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .config import ConfigSecurityModule

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


def fmt_vnd(val: Any) -> str:
    try:
        n = float(val or 0)
        return f"{n:,.0f}".replace(",", ".")
    except Exception:
        return "0"


class DocumentIngestModule:
    @staticmethod
    def parse_pdf_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
        """Trích xuất tự động Số ký hiệu, Ngày văn bản, Nơi gửi, Về việc và các MST từ PDF."""
        full_text = ""
        if pdfplumber is not None:
            try:
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages:
                        full_text += (page.extract_text() or "") + "\n"
            except Exception:
                pass

        if not full_text.strip():
            # Fallback regex bóc tách luồng text thô nếu không có pdfplumber
            raw_latin = pdf_bytes.decode("latin-1", errors="ignore")
            chunks = re.findall(r"\(([^\(\)]+)\)\s*Tj", raw_latin)
            full_text = "\n".join(chunks)

        so_kh_match = re.search(r"(?:Số|So)\s*:\s*([0-9A-Za-z/\-\.]+)", full_text, flags=re.IGNORECASE)
        so_ky_hieu = so_kh_match.group(1).strip() if so_kh_match else ""

        ngay_match = re.search(
            r"(?:ngày|ngay)\s+(\d{1,2})\s+(?:tháng|thang)\s+(\d{1,2})\s+(?:năm|nam)\s+(\d{4})",
            full_text,
            flags=re.IGNORECASE,
        )
        ngay_vb = (
            f"{int(ngay_match.group(1)):02d}/{int(ngay_match.group(2)):02d}/{ngay_match.group(3)}"
            if ngay_match
            else ""
        )

        vv_match = re.search(r"(?:V/v|Về việc|Ve viec)\s*[:\-]?\s*([^\n]+)", full_text, flags=re.IGNORECASE)
        ve_viec = vv_match.group(1).strip() if vv_match else "NNT có dấu hiệu rủi ro về hóa đơn"

        noi_gui_match = re.search(
            r"((?:THUẾ|CHI CỤC THUẾ|CỤC THUẾ|THUE CO SO)[^\n]{3,65})",
            full_text[:700],
            flags=re.IGNORECASE,
        )
        noi_gui = noi_gui_match.group(1).strip().title() if noi_gui_match else ""

        mst_list = list(dict.fromkeys(re.findall(r"\b\d{10}(?:-\d{3})?\b", full_text)))
        return {
            "so_ky_hieu_vb": so_ky_hieu,
            "ngay_thang_vb": ngay_vb,
            "noi_gui": noi_gui,
            "ve_viec": ve_viec,
            "mst_list": mst_list,
        }

    @staticmethod
    def format_date_compact(date_str: str) -> str:
        """Chuyển đổi các định dạng ngày dd/mm/yyyy hoặc yyyy-mm-dd thành ddmmyyyy."""
        if not date_str:
            return datetime.now().strftime("%d%m%Y")
        clean = re.sub(r"[^0-9]", "", str(date_str).strip())
        if len(clean) == 8:
            # Nếu bắt đầu bằng 20.. (dạng yyyymmdd) thì chuyển sang ddmmyyyy
            if clean.startswith("20") and int(clean[4:6]) <= 12 and int(clean[6:8]) <= 31:
                return f"{clean[6:8]}{clean[4:6]}{clean[:4]}"
            return clean
        try:
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
                dt = datetime.strptime(str(date_str).strip(), fmt)
                return dt.strftime("%d%m%Y")
        except Exception:
            pass
        return datetime.now().strftime("%d%m%Y")

    @classmethod
    def generate_standard_filename(
        cls,
        doc_type: str = "VB",
        mst: str = "",
        date_str: str = "",
        extra_info: str = "",
        original_filename: str = "",
    ) -> str:
        """
        Quy chuẩn đặt tên tệp khi lưu vào SharePdf theo chỉ đạo:
        - CVRR_ddmmyyyy_MST_... : Công văn rủi ro (Văn bản cảnh báo)
        - TBGT_ddmmyyyy_MST_... : Thông báo giải trình
        - GTDN_ddmmyyyy_MST_... : Văn bản giải trình của doanh nghiệp
        - BBLV_ddmmyyyy_MST_... : Biên bản làm việc với doanh nghiệp
        - PKT_ddmmyyyy_MST_...  : Văn bản / Tài liệu phản hồi của phòng Kiểm tra
        """
        raw_type = (doc_type or "VB").upper().strip()
        if raw_type in ("CVRR", "TBGT", "GTDN", "BBLV", "PKT"):
            doc_type = raw_type
        elif any(k in raw_type for k in ("CANHBAO", "CV", "RR", "VANBAN")):
            doc_type = "CVRR"
        elif any(k in raw_type for k in ("THONGBAO", "TB")):
            doc_type = "TBGT"
        elif any(k in raw_type for k in ("GIAITRINH", "GT", "KQ")):
            doc_type = "GTDN"
        elif any(k in raw_type for k in ("BIENBAN", "BBLV", "LAMVIEC")):
            doc_type = "BBLV"
        elif any(k in raw_type for k in ("KIEMTRA", "PKT", "KT")):
            doc_type = "PKT"
        else:
            doc_type = "CVRR"

        date_tag = cls.format_date_compact(date_str)

        # Chuẩn hóa MST: loại bỏ ký tự lạ
        clean_mst = re.sub(r"[^0-9A-Za-z\-]", "", (mst or "").strip())
        if not clean_mst:
            clean_mst = "CHUA_MST"

        # Chuẩn hóa extra_info (Số công văn, số thông báo, hoặc tên tệp gốc)
        clean_extra = ""
        info_candidate = (extra_info or original_filename or "").strip()
        if info_candidate:
            clean_extra = re.sub(r"\.pdf$", "", info_candidate, flags=re.IGNORECASE)
            clean_extra = re.sub(r"[^0-9A-Za-z_]", "_", clean_extra)
            clean_extra = re.sub(r"_+", "_", clean_extra).strip("_")

        if len(clean_extra) > 40:
            clean_extra = clean_extra[:40].rstrip("_")

        if clean_extra:
            base_name = f"{doc_type}_{date_tag}_{clean_mst}_{clean_extra}.pdf"
        else:
            base_name = f"{doc_type}_{date_tag}_{clean_mst}.pdf"

        # Chống ghi đè nếu đã tồn tại file cùng tên trong SharePdf
        vault = ConfigSecurityModule.get_pdf_vault_dir()
        target = vault / base_name
        counter = 1
        name_no_ext = base_name[:-4]
        while target.exists():
            target = vault / f"{name_no_ext}_{counter}.pdf"
            counter += 1

        return target.name

    @classmethod
    def store_pdf_in_sharepdf(
        cls,
        filename: str,
        file_bytes: bytes,
        prefix_tag: str = "VB",
        mst: str = "",
        date_str: str = "",
        extra_info: str = "",
    ) -> Tuple[str, str]:
        """Lưu file PDF vào SharePdf theo định danh quy chuẩn CVRR / TBGT / GTDN / BBLV / PKT."""
        vault = ConfigSecurityModule.get_pdf_vault_dir()
        sha256_hex = hashlib.sha256(file_bytes).hexdigest()

        stored_name = cls.generate_standard_filename(
            doc_type=prefix_tag,
            mst=mst,
            date_str=date_str,
            extra_info=extra_info,
            original_filename=filename,
        )
        target_path = vault / stored_name
        target_path.write_bytes(file_bytes)
        return stored_name, sha256_hex

    @classmethod
    def bundle_record_zip_bytes(cls, rec: Dict[str, Any]) -> Tuple[str, bytes]:
        """
        Gom trọn bộ hồ sơ gồm tất cả file PDF đính kèm (CVRR, TBGT, GTDN, BBLV, PKT)
        và file tổng hợp tiến độ dạng text vào một file ZIP duy nhất.
        """
        vault = ConfigSecurityModule.get_pdf_vault_dir()
        mst = (rec.get("mst") or "MST").strip()
        date_now = datetime.now().strftime("%d%m%Y")
        zip_filename = f"TronBoHoSo_{mst}_{date_now}.zip"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Tạo file tóm tắt chi tiết hồ sơ
            summary_text = (
                f"================================================================================\r\n"
                f"       HỒ SƠ QUẢN LÝ HÓA ĐƠN RỦI RO - CHI TIẾT THEO DÕI VÀ KẾT QUẢ GIẢI TRÌNH\r\n"
                f"================================================================================\r\n"
                f"MÃ SỐ THUẾ DOANH NGHIỆP  : {rec.get('mst', '')}\r\n"
                f"TÊN NGƯỜI NỘP THUẾ       : {rec.get('ten_cong_ty', '')}\r\n"
                f"CÁN BỘ THUẾ QUẢN LÝ      : {rec.get('can_bo_xu_ly', '')}\r\n"
                f"TÌNH TRẠNG XỬ LÝ         : {rec.get('tinh_trang_xu_ly', '')}\r\n"
                f"QUÁ TRÌNH ĐÃ XỬ LÝ       : {rec.get('viec_da_thuc_hien', '')}\r\n"
                f"SỐ THÔNG BÁO GIẢI TRÌNH  : {rec.get('so_thong_bao', '')}\r\n"
                f"NGÀY BAN HÀNH THÔNG BÁO  : {rec.get('ngay_thong_bao', '')}\r\n"
                f"THỜI HẠN GIẢI TRÌNH (+10): {rec.get('han_giai_trinh', '')}\r\n"
                f"GHI CHÚ TIẾN ĐỘ          : {rec.get('ghi_chu', '')}\r\n"
                f"NỘI DUNG NNT GIẢI TRÌNH  : {rec.get('nnt_giai_trinh', '')}\r\n"
                f"Ý KIẾN / ĐỀ XUẤT XỬ LÝ   : {rec.get('de_xuat_xu_ly', '')}\r\n"
                f"NỘI DUNG PHÒNG KT PHẢN HỒI: {rec.get('noi_dung_pkt_phan_hoi') or rec.get('ket_qua_kiem_tra_phong_b', '')}\r\n"
                f"--------------------------------------------------------------------------------\r\n"
                f"SỐ LIỆU ĐIỀU CHỈNH THUẾ:\r\n"
                f" - Số tiền giảm chi phí       : {fmt_vnd(rec.get('dieu_chinh_giam_chi_phi'))} VNĐ\r\n"
                f" - Số tiền giảm khấu trừ thuế : {fmt_vnd(rec.get('dieu_chinh_giam_khau_tru'))} VNĐ\r\n"
                f" - Số thuế TNDN phải nộp      : {fmt_vnd(rec.get('dieu_chinh_thue_tndn'))} VNĐ\r\n"
                f" - Số thuế GTGT phải nộp      : {fmt_vnd(rec.get('dieu_chinh_thue_gtgt'))} VNĐ\r\n"
                f"--------------------------------------------------------------------------------\r\n"
                f"DANH SÁCH TỆP ĐÍNH KÈM TRONG HỒ SƠ:\r\n"
                f" 1. [CVRR] Công văn cảnh báo rủi ro : {rec.get('attachment_name') or '(Chưa đính kèm)'}\r\n"
                f" 2. [TBGT] Thông báo giải trình     : {rec.get('tbgt_pdf_name') or '(Chưa đính kèm)'}\r\n"
                f" 3. [GTDN] Văn bản giải trình NNT   : {rec.get('result_pdf_name') or '(Chưa đính kèm)'}\r\n"
                f" 4. [BBLV] Biên bản làm việc        : {rec.get('bblv_pdf_name') or '(Chưa đính kèm)'}\r\n"
                f" 5. [PKT]  Phản hồi Phòng Kiểm tra  : {rec.get('pkt_pdf_name') or '(Chưa đính kèm)'}\r\n"
                f"================================================================================\r\n"
                f"Kết xuất ngày {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} bởi hệ thống Quản lý Hóa đơn Rủi ro.\r\n"
            )
            zf.writestr(f"00_Thong_Tin_Ho_So_Rui_Ro_{mst}.txt", summary_text.encode("utf-8"))

            # 2. Gom tất cả các file PDF đính kèm có thật trong kho SharePdf
            pdf_fields = [
                ("CVRR", rec.get("attachment_name")),
                ("TBGT", rec.get("tbgt_pdf_name")),
                ("GTDN", rec.get("result_pdf_name")),
                ("BBLV", rec.get("bblv_pdf_name")),
                ("PKT", rec.get("pkt_pdf_name")),
            ]

            added_names = set()
            for tag, fname in pdf_fields:
                if not fname:
                    continue
                clean_fn = str(fname).strip().replace("\\", "/")
                target = (vault / clean_fn).resolve()
                if target.exists() and target.is_file() and target.name not in added_names:
                    zf.write(target, arcname=target.name)
                    added_names.add(target.name)

        return zip_filename, buf.getvalue()

    @classmethod
    def bundle_all_sharepdf_zip_bytes(cls) -> Tuple[str, bytes]:
        """Gom toàn bộ các tệp PDF đang lưu trong SharePdf thành một tệp ZIP."""
        vault = ConfigSecurityModule.get_pdf_vault_dir()
        date_now = datetime.now().strftime("%d%m%Y_%H%M")
        zip_filename = f"Kho_SharePdf_TronBo_{date_now}.zip"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(vault.rglob("*.pdf")):
                if p.is_file():
                    rel_name = str(p.relative_to(vault)).replace("\\", "/")
                    zf.write(p, arcname=rel_name)

        return zip_filename, buf.getvalue()

    @staticmethod
    def scan_existing_pdf_in_sharepdf(rel_filename: str) -> Dict[str, Any]:
        vault = ConfigSecurityModule.get_pdf_vault_dir()
        target = (vault / rel_filename).resolve()
        if not str(target).startswith(str(vault.resolve())) or not target.exists():
            return {"error": f"Không tìm thấy file {rel_filename} trong SharePdf."}
        raw = target.read_bytes()
        info = DocumentIngestModule.parse_pdf_bytes(raw)
        info["stored_name"] = rel_filename
        info["sha256"] = hashlib.sha256(raw).hexdigest()
        return info

    @staticmethod
    def parse_7col_edoc_excel(excel_bytes: bytes) -> Tuple[List[Dict[str, str]], Optional[str]]:
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes))
        except Exception as exc:
            return [], f"Không thể đọc file Excel: {exc}"

        missing = [c for c in ConfigSecurityModule.EXCEL_7_COLS if c not in df.columns]
        if missing:
            return [], f"File Excel thiếu các cột chuẩn: {', '.join(missing)}"

        records: List[Dict[str, str]] = []
        for _, row in df.iterrows():
            trich_yeu = str(row.get("Trích yếu", "") or "").strip()
            msts = re.findall(r"\b\d{10}(?:-\d{3})?\b", trich_yeu)
            mst_rr = msts[0] if len(msts) >= 1 else "CHUA_RO_MST"
            mst_lq = msts[1] if len(msts) >= 2 else ""
            records.append(
                {
                    "so_den_vb": str(row.get("Số đến", "") or "").strip(),
                    "so_ky_hieu_vb": str(row.get("Số ký hiệu", "") or "").strip(),
                    "ngay_thang_vb": str(row.get("Ngày văn bản", "") or "").strip(),
                    "noi_gui": str(row.get("Nơi gửi", "") or "").strip(),
                    "ve_viec": trich_yeu or "Cảnh báo rủi ro hóa đơn",
                    "ngay_vb_den": str(row.get("Ngày đến", "") or "").strip(),
                    "han_xu_ly": str(row.get("Hạn xử lý", "") or "").strip(),
                    "mst_rui_ro": mst_rr,
                    "mst_lien_quan": mst_lq,
                }
            )
        return records, None
