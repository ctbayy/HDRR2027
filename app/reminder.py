"""
[MODULE EMAIL REMINDER & OUTLOOK INTEGRATION]
Tự động rà soát các hồ sơ rủi ro chậm tiến độ / quá hạn chưa có kết quả giải trình (DSRR 2026),
tự động đối chiếu Email cán bộ quản lý (@gdt.gov.vn) từ danh mục dm_nnt_cbql,
và khởi tạo email đôn đốc gửi qua Microsoft Outlook (đơn lẻ hoặc tổng hợp theo cán bộ).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .database import DatabaseEngineModule


class EmailReminderModule:
    @classmethod
    def get_officer_email_map(cls) -> Dict[str, str]:
        """Tạo từ điển tra cứu nhanh {tên cán bộ viết thường: email @gdt.gov.vn} từ dm_nnt_cbql."""
        email_map: Dict[str, str] = {}
        try:
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT TRIM(can_bo_quan_ly) AS cb, TRIM(email_cbql) AS em
                    FROM dm_nnt_cbql
                    WHERE can_bo_quan_ly IS NOT NULL AND can_bo_quan_ly != ''
                      AND email_cbql IS NOT NULL AND email_cbql != ''
                    """
                ).fetchall()
                for r in rows:
                    cb = r["cb"].strip()
                    em = r["em"].strip()
                    if cb and em:
                        email_map[cb.lower()] = em
        except Exception:
            pass
        return email_map

    @classmethod
    def lookup_officer_email(cls, officer_name: str, email_map: Optional[Dict[str, str]] = None) -> str:
        """Tra cứu chính xác hoặc gần đúng địa chỉ email ngành thuế của cán bộ."""
        if not officer_name:
            return ""
        name_clean = officer_name.strip()
        name_lower = name_clean.lower()

        # 1. Nếu tên có kèm username trong ngoặc [bthan], [pthieu10]...
        bracket_match = re.search(r"\[([a-zA-Z0-9_\-\.]+)\]", name_clean)
        if bracket_match:
            user = bracket_match.group(1).lower()
            return f"{user}@gdt.gov.vn"

        if email_map is None:
            email_map = cls.get_officer_email_map()

        # 2. Khớp tuyệt đối tên
        if name_lower in email_map:
            return email_map[name_lower]

        # 3. Khớp tương đối
        for known_name, email in email_map.items():
            if known_name in name_lower or name_lower in known_name:
                return email

        # 4. Trường hợp đặc biệt đồng chí Phan Trung Hiếu
        if "phan trung hiếu" in name_lower or "pthieu" in name_lower:
            return "pthieu1.qng@gdt.gov.vn"

        return ""

    @staticmethod
    def parse_date_safe(date_str: str) -> Optional[datetime]:
        """Chuyển đổi chuỗi ngày linh hoạt (dd/mm/yyyy hoặc yyyy-mm-dd) thành đối tượng datetime."""
        if not date_str:
            return None
        clean = date_str.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y"):
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue
        # Thử tìm chuỗi dd/mm/yyyy bên trong chuỗi dài
        m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", clean)
        if m:
            try:
                return datetime.strptime(m.group(1), "%d/%m/%Y")
            except ValueError:
                pass
        return None

    @classmethod
    def get_overdue_reminders(
        cls, days_threshold: int = 15, officer_filter: str = "", filter_mode: str = ""
    ) -> Dict[str, Any]:
        """
        Quét toàn bộ hồ sơ chưa hoàn tất (tinh_trang_xu_ly != 'Đã xử lý').
        QUY TẮC MỚI: Chỉ tính chậm nếu theo mốc thời hạn ban hành thông báo giải trình (+10 ngày làm việc).
        Các hồ sơ còn lại thì đưa vào trạng thái chưa xử lý / trong hạn, không tính là chậm tiến độ.
        """
        email_map = cls.get_officer_email_map()
        now = datetime.now()

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, th_rui_ro_id, ngay_vb_den, so_den_vb, so_ky_hieu_vb,
                       ngay_thang_vb, noi_gui, lien_quan_cong_an, mst, ten_cong_ty,
                       tinh_trang_xu_ly, can_bo_xu_ly, viec_da_thuc_hien, viec_tiep_tuc,
                       ghi_chu, mst_rui_ro, ten_cty_rui_ro, nnt_giai_trinh,
                       cam_ket_so_hd, dieu_chinh_so_hd, khong_kk_so_hd, khong_nhan_so_hd,
                       so_thong_bao, ngay_thong_bao, han_giai_trinh,
                       dieu_chinh_thue_tndn, dieu_chinh_thue_gtgt,
                       result_pdf_name, attachment_name, updated_at
                FROM dsrr_2026
                WHERE tinh_trang_xu_ly != 'Đã xử lý'
                ORDER BY id DESC
                """
            ).fetchall()

        records: List[Dict[str, Any]] = []
        officers_summary: Dict[str, Dict[str, Any]] = {}
        total_pending = len(rows)

        for r in rows:
            rec = dict(r)
            officer = (rec.get("can_bo_xu_ly") or "").strip()
            if officer_filter and officer != officer_filter:
                continue

            email = cls.lookup_officer_email(officer, email_map)
            rec["officer_email"] = email

            # Tính số ngày từ lúc tiếp nhận đến hiện tại
            d_den = cls.parse_date_safe(rec.get("ngay_vb_den") or "")
            if not d_den:
                d_den = cls.parse_date_safe(rec.get("ngay_thang_vb") or "")

            if d_den:
                days_elapsed = max(0, (now - d_den).days)
            else:
                days_elapsed = 0
            rec["days_elapsed"] = days_elapsed

            # Nếu có thời hạn giải trình theo thông báo (+10 ngày làm việc)
            han_gt_str = (rec.get("han_giai_trinh") or "").strip()
            d_han = cls.parse_date_safe(han_gt_str) if han_gt_str else None

            # Xác định hạn xử lý nếu có ghi nhận trong ghi chú
            han_xl_str = han_gt_str
            if not han_xl_str:
                ghi_chu = rec.get("ghi_chu") or ""
                han_match = re.search(r"Hạn (?:xử lý|XL)[:\s]*([0-9/]+)", ghi_chu, re.IGNORECASE)
                if han_match:
                    han_xl_str = han_match.group(1).strip()
            rec["han_xu_ly"] = han_xl_str

            # Đánh giá mức độ cảnh báo:
            # QUY TẮC MỚI: Chỉ tính chậm nếu theo mốc thời hạn ban hành thông báo giải trình (+10 ngày làm việc).
            # Các hồ sơ còn lại đưa vào trạng thái chưa xử lý / đang trong hạn, KHÔNG tính là chậm tiến độ.
            is_overdue = False
            overdue_days = 0
            if d_han and now.date() > d_han.date():
                overdue_days = (now.date() - d_han.date()).days
                is_overdue = True
                urgency = "critical" if overdue_days >= 7 else "warning"
                urgency_label = f"Quá hạn giải trình {overdue_days} ngày"
                rec["days_overdue_deadline"] = overdue_days
            elif d_han:
                days_left = max(0, (d_han.date() - now.date()).days)
                urgency = "normal"
                urgency_label = f"Trong hạn giải trình (còn {days_left} ngày)"
                rec["days_overdue_deadline"] = 0
            else:
                urgency = "normal"
                urgency_label = "Chưa ban hành thông báo (Chưa xử lý)"
                rec["days_overdue_deadline"] = 0

            rec["urgency"] = urgency
            rec["urgency_label"] = urgency_label
            rec["is_overdue"] = is_overdue

            # Khởi tạo mẫu email đơn lẻ
            mail_data = cls.generate_single_reminder_email(rec)
            rec["email_subject"] = mail_data["subject"]
            rec["email_body"] = mail_data["full_body"]
            rec["mailto_url"] = mail_data["mailto_url"]

            records.append(rec)

            # Thống kê tổng hợp theo từng cán bộ
            off_key = officer or "Chưa phân công"
            if off_key not in officers_summary:
                officers_summary[off_key] = {
                    "officer_name": off_key,
                    "email": email,
                    "total_pending": 0,
                    "overdue_count": 0,
                    "critical_count": 0,
                    "record_ids": [],
                }
            officers_summary[off_key]["total_pending"] += 1
            officers_summary[off_key]["record_ids"].append(rec["id"])
            if rec["is_overdue"]:
                officers_summary[off_key]["overdue_count"] += 1
            if urgency == "critical":
                officers_summary[off_key]["critical_count"] += 1

        # Sắp xếp hồ sơ: quá hạn nhiều nhất lên đầu
        records.sort(
            key=lambda x: (
                1 if x["is_overdue"] else 0,
                x.get("days_overdue_deadline", 0),
                x["id"],
            ),
            reverse=True,
        )

        overdue_records = [r for r in records if r["is_overdue"]]

        # Lọc theo filter_mode nếu có
        display_records = records
        if filter_mode == "OVERDUE_ONLY":
            display_records = overdue_records
        elif filter_mode == "NO_TB":
            display_records = [r for r in records if not (r.get("so_thong_bao") or r.get("han_giai_trinh"))]
        elif filter_mode == "WITH_TB_VALID":
            display_records = [r for r in records if (r.get("so_thong_bao") or r.get("han_giai_trinh")) and not r["is_overdue"]]

        return {
            "total_pending": total_pending,
            "overdue_count": len(overdue_records),
            "threshold_days": days_threshold,
            "filter_mode": filter_mode,
            "officers_summary": sorted(
                list(officers_summary.values()),
                key=lambda x: (x["overdue_count"], x["total_pending"]),
                reverse=True,
            ),
            "records": display_records,
            "overdue_records": overdue_records,
        }

    @classmethod
    def generate_single_reminder_email(cls, rec: Dict[str, Any]) -> Dict[str, str]:
        """Tạo tiêu đề và nội dung email đôn đốc gửi đích danh cho 1 hồ sơ rủi ro."""
        officer = (rec.get("can_bo_xu_ly") or "").strip() or "Cán bộ phụ trách"
        email = (rec.get("officer_email") or "").strip()
        mst = (rec.get("mst") or "").strip()
        ten_dn = (rec.get("ten_cong_ty") or "Doanh nghiệp").strip()
        mst_rr = (rec.get("mst_rui_ro") or "").strip()
        ten_rr = (rec.get("ten_cty_rui_ro") or "").strip()
        so_kh = (rec.get("so_ky_hieu_vb") or "").strip()
        so_den = (rec.get("so_den_vb") or "").strip()
        ngay_den = (rec.get("ngay_vb_den") or "").strip()
        noi_gui = (rec.get("noi_gui") or "").strip()
        tinh_trang = (rec.get("tinh_trang_xu_ly") or "Chưa xử lý").strip()
        days = rec.get("days_elapsed", 0)
        viec_da_lam = (rec.get("viec_da_thuc_hien") or "").strip() or "(Chưa có thông tin)"
        ghi_chu = (rec.get("ghi_chu") or "").strip() or "(Chưa có)"

        so_tb = (rec.get("so_thong_bao") or "").strip()
        ngay_tb = (rec.get("ngay_thong_bao") or "").strip()
        han_gt = (rec.get("han_giai_trinh") or "").strip()
        days_od_deadline = rec.get("days_overdue_deadline", 0)

        if days_od_deadline > 0:
            subject = f"[NHẮC VIỆC HÓA ĐƠN RỦI RO] Đôn đốc giải trình MST {mst} - {ten_dn} (Quá hạn {days_od_deadline} ngày)"
        else:
            subject = f"[NHẮC VIỆC HÓA ĐƠN RỦI RO] Đôn đốc giải trình MST {mst} - {ten_dn} (Chậm {days} ngày)"

        # 1. Bản đầy đủ (phục vụ hiển thị chi tiết & Copy vào Clipboard)
        full_body_lines = [
            f"Kính gửi đồng chí {officer},",
            "",
            "Hệ thống Quản lý Hóa đơn Rủi ro xin thông báo và đôn đốc tiến độ xử lý hồ sơ rủi ro sau:",
            "=" * 60,
            f"1. DOANH NGHIỆP CẦN XỬ LÝ:",
            f"   - Mã số thuế: {mst}",
            f"   - Tên người nộp thuế: {ten_dn}",
            "",
            f"2. NGUỒN CẢNH BÁO RỦI RO:",
            f"   - Doanh nghiệp rủi ro (bên bán): {ten_rr} (Mã số thuế: {mst_rr})",
            f"   - Văn bản cảnh báo: Số {so_kh} (Số đến: {so_den}) do {noi_gui} gửi",
            f"   - Ngày tiếp nhận hồ sơ: {ngay_den}",
            f"   - Thời gian tồn đọng từ ngày tiếp nhận đến nay: {days} NGÀY",
            "",
            f"3. HIỆN TRẠNG XỬ LÝ & THỜI HẠN GIẢI TRÌNH:",
            f"   - Tình trạng: {tinh_trang}",
            f"   - Những việc cơ quan thuế đã thực hiện: {viec_da_lam}",
            f"   - Số thông báo yêu cầu giải trình: {so_tb or '(Chưa nhập)'} | Ngày ban hành: {ngay_tb or '-'}",
            f"   - Thời hạn giải trình (+10 ngày làm việc): {han_gt or 'Chưa xác định'}" + (f" (ĐÃ QUÁ HẠN {days_od_deadline} NGÀY)" if days_od_deadline > 0 else ""),
            f"   - Ghi chú / Công văn giải trình: {ghi_chu}",
            "=" * 60,
            "",
            "Đề nghị đồng chí khẩn trương:",
            "- Liên hệ người nộp thuế đôn đốc gửi văn bản và hồ sơ giải trình;",
            "- Rà soát, xác định số liệu hóa đơn thuộc 4 nhóm (Cam kết / Tự điều chỉnh / Không kê khai / Không nhận được);",
            "- Cập nhật tiến độ xử lý và đính kèm File PDF Kết quả lên hệ thống.",
            "",
            "Trân trọng cảm ơn đồng chí./.",
        ]
        full_body = "\r\n".join(full_body_lines)

        # 2. Bản cô đọng (để URL mailto: luôn an toàn tuyệt đối < 1500 ký tự, chạy mượt trên Windows ShellExecute và Outlook)
        ten_dn_short = (ten_dn[:50] + "...") if len(ten_dn) > 50 else ten_dn
        ten_rr_short = (ten_rr[:40] + "...") if len(ten_rr) > 40 else ten_rr
        viec_short = (viec_da_lam[:60] + "...") if len(viec_da_lam) > 60 else viec_da_lam

        concise_body_lines = [
            f"Kính gửi đồng chí {officer},",
            "",
            f"Đôn đốc hồ sơ rủi ro" + (f" ĐÃ QUÁ HẠN GIẢI TRÌNH {days_od_deadline} NGÀY:" if days_od_deadline > 0 else f" đã tiếp nhận {days} ngày chưa hoàn thành:"),
            f"• Doanh nghiệp: {ten_dn_short} (Mã số thuế: {mst})",
            f"• Doanh nghiệp bán có rủi ro: {ten_rr_short} (Mã số thuế: {mst_rr})",
            f"• Đã thực hiện: {viec_short}" + (f" | Hạn giải trình: {han_gt}" if han_gt else ""),
            f"• Tình trạng: {tinh_trang}",
            "",
            "Đề nghị đồng chí khẩn trương liên hệ người nộp thuế đôn đốc giải trình và cập nhật kết quả lên hệ thống.",
            "",
            "Trân trọng cảm ơn./.",
        ]
        concise_body = "\r\n".join(concise_body_lines)

        mailto_url = f"mailto:{email}?subject={quote(subject)}&body={quote(concise_body)}"

        return {
            "email": email,
            "subject": subject,
            "full_body": full_body,
            "concise_body": concise_body,
            "mailto_url": mailto_url,
        }

    @classmethod
    def generate_officer_summary_email(
        cls, officer_name: str, records: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Tạo email nhắc nhở tổng hợp danh sách các hồ sơ chậm tiến độ gửi cho một cán bộ."""
        if not records:
            return {
                "email": "",
                "subject": "",
                "full_body": "",
                "concise_body": "",
                "mailto_url": "",
            }

        email = records[0].get("officer_email") or ""
        if not email:
            email_map = cls.get_officer_email_map()
            email = cls.lookup_officer_email(officer_name, email_map)

        count = len(records)
        subject = f"[NHẮC VIỆC TỔNG HỢP] Đôn đốc {count} hồ sơ rủi ro quá hạn chưa cập nhật kết quả - Đồng chí {officer_name}"

        # 1. Bản chi tiết
        full_body_lines = [
            f"Kính gửi đồng chí {officer_name},",
            "",
            f"Hệ thống Quản lý Hóa đơn Rủi ro rà soát định kỳ và ghi nhận đồng chí hiện đang phụ trách {count} hồ sơ rủi ro đã tiếp nhận thời gian lâu nhưng chưa hoàn tất cập nhật kết quả giải trình:",
            "=" * 70,
        ]

        for idx, r in enumerate(records, start=1):
            mst = r.get("mst", "")
            ten_dn = r.get("ten_cong_ty", "")
            mst_rr = r.get("mst_rui_ro", "")
            ngay_den = r.get("ngay_vb_den", "-")
            days = r.get("days_elapsed", 0)
            st = r.get("tinh_trang_xu_ly", "Chưa xử lý")
            full_body_lines.append(
                f"{idx}. Mã số thuế: {mst} - {ten_dn}\n"
                f"   • Bên bán rủi ro: {mst_rr} | Tiếp nhận: {ngay_den} ({days} ngày qua)\n"
                f"   • Trạng thái: {st}"
            )

        full_body_lines.extend(
            [
                "=" * 70,
                "",
                "Đề nghị đồng chí khẩn trương rà soát đôn đốc người nộp thuế, phối hợp cập nhật số liệu và kết quả lên hệ thống để phục vụ công tác giám sát, tổng hợp báo cáo ngành thuế.",
                "",
                "Trân trọng cảm ơn đồng chí./.",
            ]
        )
        full_body = "\r\n".join(full_body_lines)

        # 2. Bản cô đọng cho URL mailto (tối đa 5 hồ sơ tiêu biểu để URL không vượt quá giới hạn hệ điều hành)
        concise_lines = [
            f"Kính gửi đồng chí {officer_name},",
            "",
            f"Hệ thống Quản lý Hóa đơn Rủi ro ghi nhận đồng chí đang có {count} hồ sơ chậm cập nhật kết quả:",
        ]
        for idx, r in enumerate(records[:5], start=1):
            concise_lines.append(
                f"{idx}. MST {r.get('mst')}: {r.get('ten_cong_ty', '')[:35]} (Chậm {r.get('days_elapsed', 0)} ngày - {r.get('tinh_trang_xu_ly')})"
            )
        if count > 5:
            concise_lines.append(f"... và {count - 5} hồ sơ khác đang chờ xử lý trên hệ thống.")

        concise_lines.extend(
            [
                "",
                "Đề nghị đồng chí khẩn trương rà soát đôn đốc người nộp thuế và cập nhật kết quả lên hệ thống.",
                "",
                "Trân trọng./.",
            ]
        )
        concise_body = "\r\n".join(concise_lines)

        mailto_url = f"mailto:{email}?subject={quote(subject)}&body={quote(concise_body)}"

        return {
            "email": email,
            "subject": subject,
            "full_body": full_body,
            "concise_body": concise_body,
            "mailto_url": mailto_url,
        }
