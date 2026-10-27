"""
[MODULE WEB ENGINE REQUEST HANDLER]
Xử lý các HTTP Request (RESTful API & Phục vụ file Static),
phân quyền LAN Guard, trích xuất danh tính máy trạm và ghi nhật ký ngầm (Audit Log).
"""

import base64
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from typing import Any, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from ..admin import AdminManagementModule
from ..audit import StealthAuditModule
from ..auth import AdminAuthModule
from ..config import ConfigSecurityModule
from ..database import DatabaseEngineModule
from ..ingest import DocumentIngestModule
from ..reminder import EmailReminderModule
from ..sap_sync import SAPSyncModule
from ..sync_queue import LocalSyncEngineModule
from ..workflow import RiskWorkflowModule
from .assets import load_asset_bytes


class WebEngineRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Tắt bớt log mặc định để console sạch đẹp
        pass

    def _check_lan_guard(self) -> bool:
        client_ip = self.client_address[0]
        if not ConfigSecurityModule.is_internal_lan_ip(client_ip):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden: Internal LAN Access Only.")
            return False
        return True

    def _is_admin_authenticated(self) -> bool:
        token = (
            self.headers.get("X-Admin-Token", "")
            or self.headers.get("X-Admin-Pin", "")
            or self.headers.get("X-Owner-Pin", "")
        ).strip()
        if not token:
            try:
                qs = parse_qs(urlparse(self.path).query)
                token = (qs.get("token") or qs.get("pin") or [""])[0].strip()
            except Exception:
                token = ""
        if not token:
            return False
        if AdminAuthModule.is_authenticated(token):
            return True
        return AdminAuthModule.verify_legacy_or_password(token)

    def _extract_caller(self) -> Tuple[str, str, str, str]:
        client_ip = self.client_address[0]
        ua = self.headers.get("User-Agent", "")
        ident = ConfigSecurityModule.detect_internal_machine_identity(client_ip)
        header_officer = unquote(self.headers.get("X-Officer-Name", "")).strip()
        officer = (
            f"{header_officer} [{ident['domain_account']}]"
            if header_officer
            else f"{ident['matched_officer_name']} [{ident['domain_account']}]"
        )
        dept = unquote(self.headers.get("X-Department", "Nội bộ CQT"))
        return client_ip, ua, officer, dept

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if not self._check_lan_guard():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        client_ip, ua, officer, dept = self._extract_caller()

        # 1. Phục vụ Trang chủ & Static Assets
        if path in ("/", "/index.html", "/hoadonruiro", "/qlhtdn", "/kiemtra"):
            raw = load_asset_bytes("index.html") or b"<h1>Index not found</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if path == "/static/style.css":
            raw = load_asset_bytes("style.css") or b""
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if path == "/static/app.js":
            raw = load_asset_bytes("app.js") or b""
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        # 2. Các API Nghiệp vụ
        if path == "/api/bootstrap":
            active_dir, mode = ConfigSecurityModule.resolve_storage_dir()
            machine_identity = ConfigSecurityModule.detect_internal_machine_identity(client_ip)
            self._send_json(
                {
                    "machine_identity": machine_identity,
                    "lan_ip": ConfigSecurityModule.get_lan_ip(),
                    "port": ConfigSecurityModule.PORT,
                    "client_ip": client_ip,
                    "unc_share_path": ConfigSecurityModule.TARGET_UNC_PATH,
                    "active_dir": str(active_dir),
                    "storage_mode": mode,
                }
            )
            return

        if path == "/api/nnt/lookup":
            q_mst = (qs.get("mst") or [""])[0].strip()
            ten_dn, cb_ql = RiskWorkflowModule.lookup_nnt(q_mst)
            self._send_json({"mst": q_mst, "ten_nnt": ten_dn, "can_bo_quan_ly": cb_ql})
            return

        if path == "/api/sharepdf/scan_existing":
            rel_name = (qs.get("name") or [""])[0].strip()
            info = DocumentIngestModule.scan_existing_pdf_in_sharepdf(rel_name)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="SCAN_EXISTING_PDF",
                target_module="SharePdf",
                event_detail=f"Quét nội dung file PDF có sẵn trong SharePdf: {rel_name}",
            )
            self._send_json(info)
            return

        if path == "/api/data":
            active_dir, mode = ConfigSecurityModule.resolve_storage_dir()
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                th_rows = [
                    dict(r)
                    for r in conn.execute("SELECT * FROM th_rui_ro ORDER BY id DESC").fetchall()
                ]
                dsrr_rows = [
                    dict(r)
                    for r in conn.execute("SELECT * FROM dsrr_2026 ORDER BY id DESC").fetchall()
                ]
            self._send_json(
                {
                    "th_rui_ro": th_rows,
                    "dsrr_2026": dsrr_rows,
                    "sharepdf_files": ConfigSecurityModule.list_sharepdf_files(),
                    "storage_mode": mode,
                    "active_dir": str(active_dir),
                }
            )
            return

        if path == "/api/dsrr/detail":
            rec_id = (qs.get("id") or [""])[0]
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                row = conn.execute("SELECT * FROM dsrr_2026 WHERE id = ?", (rec_id,)).fetchone()
            if not row:
                self._send_json({"error": "Not found"}, 404)
                return
            rec = dict(row)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="VIEW_DETAIL",
                target_module="DSRR 2026",
                target_mst=rec.get("mst", ""),
                record_id=str(rec_id),
                event_detail=f"Mở xem chi tiết hồ sơ DSRR #{rec_id} của DN {rec.get('ten_cong_ty') or rec.get('mst')}",
            )
            self._send_json(rec)
            return

        if path == "/api/inspect/search":
            q_mst = (qs.get("mst") or [""])[0].strip()
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                if q_mst:
                    terms = [t for t in q_mst.split() if t]
                    where_clauses = []
                    params = []
                    field_sql = """(
                        mst LIKE ? OR ten_cong_ty LIKE ? OR mst_rui_ro LIKE ? OR ten_cty_rui_ro LIKE ?
                        OR so_ky_hieu_vb LIKE ? OR so_den_vb LIKE ? OR noi_gui LIKE ? OR can_bo_xu_ly LIKE ?
                        OR viec_da_thuc_hien LIKE ? OR viec_tiep_tuc LIKE ? OR ghi_chu LIKE ?
                        OR nnt_giai_trinh LIKE ? OR de_xuat_xu_ly LIKE ? OR ket_qua_kiem_tra_phong_b LIKE ?
                        OR result_pdf_name LIKE ? OR attachment_name LIKE ? OR tinh_trang_xu_ly LIKE ?
                        OR so_thong_bao LIKE ? OR ngay_thong_bao LIKE ? OR han_giai_trinh LIKE ?
                        OR CAST(cam_ket_gia_tri AS TEXT) LIKE ? OR CAST(dieu_chinh_giam_chi_phi AS TEXT) LIKE ?
                        OR CAST(dieu_chinh_giam_khau_tru AS TEXT) LIKE ?
                        OR CAST(dieu_chinh_thue_tndn AS TEXT) LIKE ? OR CAST(dieu_chinh_thue_gtgt AS TEXT) LIKE ?
                    )"""
                    for term in terms:
                        where_clauses.append(field_sql)
                        p = f"%{term}%"
                        params.extend([p] * 25)
                    sql = f"SELECT * FROM dsrr_2026 WHERE {' AND '.join(where_clauses)} ORDER BY id DESC"
                    rows = conn.execute(sql, params).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM dsrr_2026 ORDER BY id DESC").fetchall()
            results = [dict(r) for r in rows]
            if q_mst:
                StealthAuditModule.record_event(
                    client_ip=client_ip,
                    user_agent=ua,
                    officer_name=officer,
                    department=dept,
                    event_type="SEARCH_MST",
                    target_module="Tra cứu (Phòng Kiểm tra)",
                    target_mst=q_mst,
                    event_detail=f"Tra cứu lịch sử rủi ro theo từ khóa '{q_mst}' (Trả về {len(results)} hồ sơ)",
                )
            self._send_json({"results": results})
            return

        if path == "/api/export/excel":
            caller_name = (qs.get("officer") or [officer])[0]
            excel_bytes = RiskWorkflowModule.export_excel_bytes()
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=caller_name,
                department=dept,
                event_type="EXPORT_EXCEL",
                target_module="DSRR 2026 & TH_Rủi ro",
                event_detail="Kết xuất file Excel chuẩn 2 sheet (DSRR 2026 & TH_Rủi ro)",
            )
            fname = f"Hoa_don_rui_ro_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)
            return

        if path == "/api/attachment":
            rel_name = (qs.get("name") or [""])[0].strip()
            caller_name = (qs.get("officer") or [officer])[0]
            vault = ConfigSecurityModule.get_pdf_vault_dir()
            target = (vault / rel_name).resolve()
            if not str(target).startswith(str(vault.resolve())) or not target.exists():
                self.send_response(404)
                self.end_headers()
                return
            data = target.read_bytes()
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=caller_name,
                department=dept,
                event_type="OPEN_PDF_SHAREPDF",
                target_module=r"Kho \\qng-pthieu10\SharePdf",
                event_detail=f"Mở xem file PDF trong SharePdf: {rel_name}",
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'inline; filename="{target.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/stealth/logs":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu đăng nhập quyền Quản trị viên"}, 403)
                return
            token = (
                self.headers.get("X-Admin-Token", "")
                or self.headers.get("X-Admin-Pin", "")
                or self.headers.get("X-Owner-Pin", "")
            ).strip()
            logs = StealthAuditModule.get_logs_for_owner(token)
            if logs is None:
                self._send_json({"error": "Unauthorized"}, 403)
                return
            self._send_json({"logs": logs})
            return

        if path == "/api/sync/status":
            stat = LocalSyncEngineModule.get_sync_status(user_id=officer)
            self._send_json(stat)
            return

        if path == "/api/dsrr/bundle_zip":
            rec_id = (qs.get("id") or [""])[0].strip()
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                row = conn.execute("SELECT * FROM dsrr_2026 WHERE id = ?", (rec_id,)).fetchone()
            if not row:
                self._send_json({"error": "Không tìm thấy hồ sơ rủi ro yêu cầu"}, 404)
                return
            rec = dict(row)
            zip_name, zip_bytes = DocumentIngestModule.bundle_record_zip_bytes(rec)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="DOWNLOAD_BUNDLE_ZIP",
                target_module="DSRR 2026",
                target_mst=rec.get("mst", ""),
                record_id=str(rec_id),
                event_detail=f"Tải trọn bộ dữ liệu hồ sơ #{rec_id} (MST: {rec.get('mst')}): {zip_name} ({len(zip_bytes)} bytes)",
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{zip_name}"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)
            return

        if path == "/api/sharepdf/download_all_zip":
            zip_name, zip_bytes = DocumentIngestModule.bundle_all_sharepdf_zip_bytes()
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="DOWNLOAD_ALL_SHAREPDF_ZIP",
                target_module=r"Kho \\qng-pthieu10\SharePdf",
                event_detail=f"Tải trọn bộ kho file SharePdf: {zip_name} ({len(zip_bytes)} bytes)",
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{zip_name}"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)
            return

        if path == "/api/reminders/list":
            mode = (qs.get("mode") or ["OVERDUE_ONLY"])[0].strip()
            days = int((qs.get("days") or ["15"])[0])
            off_f = (qs.get("officer") or [""])[0].strip()
            data = EmailReminderModule.get_overdue_reminders(
                days_threshold=days, officer_filter=off_f, filter_mode=mode
            )
            self._send_json(data)
            return

        if path == "/api/reminders/single":
            rec_id = (qs.get("id") or [""])[0].strip()
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                row = conn.execute("SELECT * FROM dsrr_2026 WHERE id = ?", (rec_id,)).fetchone()
            if not row:
                self._send_json({"error": "Not found"}, 404)
                return
            rec = dict(row)
            d_den = EmailReminderModule.parse_date_safe(rec.get("ngay_vb_den") or "") or EmailReminderModule.parse_date_safe(rec.get("ngay_thang_vb") or "")
            rec["days_elapsed"] = max(0, (datetime.now() - d_den).days) if d_den else 0
            email_map = EmailReminderModule.get_officer_email_map()
            rec["officer_email"] = EmailReminderModule.lookup_officer_email(rec.get("can_bo_xu_ly", ""), email_map)
            mail_data = EmailReminderModule.generate_single_reminder_email(rec)
            self._send_json(mail_data)
            return

        if path == "/api/reminders/officer_summary":
            off_name = (qs.get("officer") or [""])[0].strip()
            mode = (qs.get("mode") or ["OVERDUE_ONLY"])[0].strip()
            days = int((qs.get("days") or ["15"])[0])
            data = EmailReminderModule.get_overdue_reminders(
                days_threshold=days, officer_filter=off_name, filter_mode=mode
            )
            summary_mail = EmailReminderModule.generate_officer_summary_email(off_name, data.get("records", []))
            self._send_json(summary_mail)
            return

        # 3. Các API Quản trị Hệ thống, Danh mục NNT & Đồng bộ SAP
        if path == "/api/admin/check_auth":
            token = self.headers.get("X-Admin-Token", "").strip()
            valid = AdminAuthModule.is_authenticated(token)
            self._send_json({"authenticated": valid, "username": "admin" if valid else ""})
            return

        if path == "/api/admin/verify_pin":
            q_pin = (qs.get("pin") or [""])[0].strip()
            ok = AdminAuthModule.verify_legacy_or_password(q_pin)
            self._send_json({"valid": ok})
            return

        if path == "/api/admin/kpis":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên (Admin PIN)"}, 403)
                return
            self._send_json(AdminManagementModule.get_kpis())
            return

        if path == "/api/admin/nnt/list":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên (Admin PIN)"}, 403)
                return
            p = int((qs.get("page") or ["1"])[0])
            limit = int((qs.get("limit") or ["50"])[0])
            search = (qs.get("search") or [""])[0].strip()
            officer_f = (qs.get("officer") or [""])[0].strip()
            data = AdminManagementModule.get_nnt_list(page=p, page_size=limit, search=search, officer_filter=officer_f)
            self._send_json(data)
            return

        if path == "/api/admin/nnt/export":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized"}, 403)
                return
            excel_bytes = AdminManagementModule.export_excel_bytes()
            fname = f"DanhMuc_NNT_CBQL_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)
            return

        if path == "/api/admin/nnt/template":
            excel_bytes = AdminManagementModule.export_template_bytes()
            fname = "Mau_Excel_Nhap_NNT_CBQL.xlsx"
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)
            return

        if path == "/api/admin/sap/config":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized"}, 403)
                return
            cfg = SAPSyncModule.get_config()
            self._send_json(cfg)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if not self._check_lan_guard():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        client_ip, ua, officer, dept = self._extract_caller()
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if path == "/api/sharepdf/config":
            new_path = payload.get("share_path", "")
            ok, msg = ConfigSecurityModule.set_custom_share_path(new_path)
            self._send_json({"ok": ok, "message": msg})
            return

        if path == "/api/backup/now":
            bak = DatabaseEngineModule.create_auto_backup(force=True)
            if bak:
                self._send_json({"ok": True, "backup_file": bak})
            else:
                self._send_json({"ok": False, "error": "Không thể tạo bản sao lưu"}, 500)
            return

        if path == "/api/sync/flush":
            res = LocalSyncEngineModule.flush_all_pending_queues()
            self._send_json(res)
            return

        if path == "/api/th/create":
            payload["officer_name"] = officer
            ok, sync_status, meta = LocalSyncEngineModule.enqueue_and_sync(
                user_id=officer,
                action_type="CREATE_TH",
                target_id="",
                payload=payload,
            )
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="CREATE_TH_RR",
                target_module="TH_Rủi ro -> DSRR 2026",
                target_mst=payload.get("mst_rui_ro", ""),
                record_id=str(meta.get("staged_id", "")),
                event_detail=f"Nhập VB rủi ro MST {payload.get('mst_rui_ro')} | Trạng thái đồng bộ: {sync_status}",
            )
            self._send_json({
                "status": "ok",
                "sync_status": sync_status,
                "message": meta.get("message", "Đã tiếp nhận văn bản rủi ro thành công!"),
                "mst_lq": payload.get("mst_lien_quan", ""),
                "lien_quan_qldn1": bool(payload.get("mst_lien_quan")),
                "pending_remaining": meta.get("pending_remaining", 0),
            })
            return

        if path == "/api/dsrr/update":
            rec_id = int(payload["id"])
            payload["officer_name"] = officer
            ok, sync_status, meta = LocalSyncEngineModule.enqueue_and_sync(
                user_id=officer,
                action_type="UPDATE_DSRR",
                target_id=str(rec_id),
                payload=payload,
            )
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="UPDATE_DSRR",
                target_module="DSRR 2026",
                target_mst=payload.get("mst_rui_ro", ""),
                record_id=str(rec_id),
                event_detail=(
                    f"Cập nhật Hồ sơ #{rec_id} -> Trạng thái: {payload.get('tinh_trang_xu_ly')} | "
                    f"Đồng bộ: {sync_status} | "
                    f"Giải trình: {payload.get('nnt_giai_trinh', '')[:60]}"
                ),
            )
            self._send_json({
                "status": "ok",
                "sync_status": sync_status,
                "message": meta.get("message", "Đã cập nhật hồ sơ thành công!"),
                "pending_remaining": meta.get("pending_remaining", 0),
            })
            return

        if path == "/api/dsrr/attach_cvrr":
            rec_id = int(payload.get("id", 0))
            att_name = (payload.get("attachment_name") or "").strip()
            if not rec_id or not att_name:
                self._send_json({"error": "Thiếu id hoặc attachment_name"}, 400)
                return
            with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
                conn.execute(
                    "UPDATE dsrr_2026 SET attachment_name = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                    (att_name, officer, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), rec_id),
                )
                conn.commit()
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ATTACH_CVRR",
                target_module="DSRR 2026",
                record_id=str(rec_id),
                event_detail=f"Đính kèm tệp Công văn rủi ro: {att_name} cho hồ sơ #{rec_id}",
            )
            self._send_json({"status": "ok", "attachment_name": att_name, "message": f"Đã đính kèm tệp {att_name} thành công!"})
            return

        if path == "/api/ingest/pdf":
            filename = payload.get("filename") or "tai_lieu.pdf"
            pdf_bytes = base64.b64decode(payload.get("file_b64") or "")
            info = DocumentIngestModule.parse_pdf_bytes(pdf_bytes)

            doc_type = payload.get("doc_type") or "CVRR"
            parsed_msts = info.get("mst_list") or []
            mst = (
                payload.get("mst")
                or payload.get("mst_lq")
                or payload.get("mst_rr")
                or (parsed_msts[0] if parsed_msts else "")
            )
            date_str = payload.get("date") or payload.get("ngay_thong_bao") or info.get("ngay_thang_vb") or ""
            extra_info = (
                payload.get("extra_info")
                or payload.get("so_thong_bao")
                or payload.get("so_ky_hieu")
                or info.get("so_ky_hieu_vb")
                or ""
            )

            stored_name, sha_hex = DocumentIngestModule.store_pdf_in_sharepdf(
                filename=filename,
                file_bytes=pdf_bytes,
                prefix_tag=doc_type,
                mst=mst,
                date_str=date_str,
                extra_info=extra_info,
            )
            info["stored_name"] = stored_name
            info["sha256"] = sha_hex
            info["doc_type"] = doc_type
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="UPLOAD_PDF_SHAREPDF",
                target_module=r"Kho \\qng-pthieu10\SharePdf",
                target_mst=mst,
                event_detail=f"Tải lên & chuẩn hóa tên tệp [{doc_type}]: {stored_name}",
            )
            self._send_json(info)
            return

        if path == "/api/ingest/excel7col":
            excel_bytes = base64.b64decode(payload.get("file_b64") or "")
            records, err = DocumentIngestModule.parse_7col_edoc_excel(excel_bytes)
            if err:
                self._send_json({"error": err}, 400)
                return
            for rec in records:
                rec["officer_name"] = officer
                rec["co_lien_quan_truc_tiep"] = bool(rec.get("mst_lien_quan"))
                RiskWorkflowModule.create_warning_record(rec)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="IMPORT_EXCEL_7COL",
                target_module="TH_Rủi ro",
                event_detail=f"Import {len(records)} văn bản từ file Excel Quản lý văn bản",
            )
            self._send_json({"imported_count": len(records)})
            return

        if path == "/api/reminders/log":
            target_officer = payload.get("target_officer", "")
            target_email = payload.get("target_email", "")
            rec_id = payload.get("record_id", "")
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="TRIGGER_OUTLOOK_REMINDER",
                target_module="DSRR 2026 / Outlook Reminder",
                target_mst=payload.get("mst", ""),
                record_id=str(rec_id),
                event_detail=f"Kích hoạt mở email nhắc việc qua Outlook gửi đến cán bộ {target_officer} ({target_email}) cho hồ sơ #{rec_id}",
            )
            self._send_json({"status": "ok"})
            return

        # 4. Các API POST Quản trị & Xác thực Admin
        if path == "/api/admin/login":
            username = (payload.get("username") or "").strip()
            password = (payload.get("password") or "").strip()
            token, err = AdminAuthModule.authenticate(username, password)
            if token:
                StealthAuditModule.record_event(
                    client_ip=client_ip,
                    user_agent=ua,
                    officer_name=officer,
                    department=dept,
                    event_type="ADMIN_LOGIN_SUCCESS",
                    target_module="Quản trị Hệ thống",
                    event_detail=f"Đăng nhập thành công tài khoản Quản trị viên '{username}' từ IP {client_ip}",
                )
                self._send_json({"success": True, "token": token, "username": username})
            else:
                StealthAuditModule.record_event(
                    client_ip=client_ip,
                    user_agent=ua,
                    officer_name=officer,
                    department=dept,
                    event_type="ADMIN_LOGIN_FAILED",
                    target_module="Quản trị Hệ thống",
                    event_detail=f"Đăng nhập thất bại tài khoản '{username}' từ IP {client_ip}: {err}",
                )
                self._send_json({"success": False, "error": err or "Tên đăng nhập hoặc mật khẩu không chính xác"}, 401)
            return

        if path == "/api/admin/logout":
            token = self.headers.get("X-Admin-Token", "").strip()
            AdminAuthModule.logout(token)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ADMIN_LOGOUT",
                target_module="Quản trị Hệ thống",
                event_detail="Quản trị viên đăng xuất khỏi phiên làm việc",
            )
            self._send_json({"success": True})
            return

        if path == "/api/admin/change_password":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên"}, 403)
                return
            old_pass = payload.get("old_password", "")
            new_pass = payload.get("new_password", "")
            ok, msg = AdminAuthModule.change_password(old_pass, new_pass)
            if ok:
                StealthAuditModule.record_event(
                    client_ip=client_ip,
                    user_agent=ua,
                    officer_name=officer,
                    department=dept,
                    event_type="ADMIN_CHANGE_PASSWORD",
                    target_module="Quản trị Hệ thống",
                    event_detail="Đã cập nhật mật khẩu tài khoản Quản trị viên thành công",
                )
                self._send_json({"success": True, "message": msg})
            else:
                self._send_json({"success": False, "error": msg}, 400)
            return

        if path == "/api/admin/nnt/save":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên"}, 403)
                return
            mst = (payload.get("mst") or "").strip()
            ok, sync_status, meta = LocalSyncEngineModule.enqueue_and_sync(
                user_id=officer,
                action_type="SAVE_NNT",
                target_id=mst,
                payload=payload,
            )
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ADMIN_SAVE_NNT",
                target_module="Quản trị Danh mục NNT",
                target_mst=mst,
                event_detail=f"Cập nhật danh bạ NNT {mst} | Đồng bộ: {sync_status}",
            )
            self._send_json({
                "status": "ok",
                "sync_status": sync_status,
                "message": meta.get("message", "Đã lưu NNT thành công!"),
                "record": payload,
            })
            return

        if path == "/api/admin/nnt/delete":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên"}, 403)
                return
            del_mst = payload.get("mst", "").strip()
            ok, sync_status, meta = LocalSyncEngineModule.enqueue_and_sync(
                user_id=officer,
                action_type="DELETE_NNT",
                target_id=del_mst,
                payload={"mst": del_mst},
            )
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ADMIN_DELETE_NNT",
                target_module="Quản trị Danh mục NNT",
                target_mst=del_mst,
                event_detail=f"Xóa người nộp thuế MST {del_mst} khỏi danh mục | Đồng bộ: {sync_status}",
            )
            self._send_json({
                "status": "ok",
                "sync_status": sync_status,
                "message": meta.get("message", "Đã xóa NNT thành công!"),
            })
            return

        if path == "/api/admin/nnt/import":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên"}, 403)
                return
            file_b64 = payload.get("file_b64", "")
            mode = payload.get("mode", "upsert")
            excel_bytes = base64.b64decode(file_b64)
            res = AdminManagementModule.import_excel_bytes(excel_bytes, mode=mode)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ADMIN_IMPORT_EXCEL_NNT",
                target_module="Quản trị Danh mục NNT",
                event_detail=f"Import Excel NNT ({mode}): Thêm mới {res['added_count']}, Cập nhật {res['updated_count']}",
            )
            self._send_json(res)
            return

        if path == "/api/admin/sap/config":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên"}, 403)
                return
            saved_cfg = SAPSyncModule.save_config(payload, officer_name=officer)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ADMIN_CONFIG_SAP",
                target_module="Cấu hình SAP Connector",
                event_detail=f"Lưu cấu hình tích hợp SAP: Hệ thống {saved_cfg.get('sap_system_id')} | Script {saved_cfg.get('script_type')}",
            )
            self._send_json({"status": "ok", "config": saved_cfg})
            return

        if path == "/api/admin/sap/run":
            if not self._is_admin_authenticated():
                self._send_json({"error": "Unauthorized: Yêu cầu quyền Quản trị viên"}, 403)
                return
            override_cfg = payload.get("override_config")
            run_result = SAPSyncModule.run_sync(override_config=override_cfg, officer_name=officer)
            StealthAuditModule.record_event(
                client_ip=client_ip,
                user_agent=ua,
                officer_name=officer,
                department=dept,
                event_type="ADMIN_RUN_SAP_SYNC",
                target_module="Kích hoạt Đồng bộ SAP",
                event_detail=f"Chạy SAP Sync ({run_result['status']}): {run_result['message']}",
            )
            self._send_json(run_result)
            return
