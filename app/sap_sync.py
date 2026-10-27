"""
[MODULE SAP AUTO-SYNC INTEGRATION HOOK & CONNECTOR]
Slot chờ cấu hình và kích hoạt kịch bản tự động (SAP GUI Scripting / RPA / Python)
kết nối ứng dụng Quản lý Thuế SAP/TMS để lấy danh bạ NNT & Cán bộ Quản lý (CBQL/Email),
sau đó tự động đồng bộ vào cơ sở dữ liệu `dm_nnt_cbql`.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .database import DatabaseEngineModule

# Template mẫu Python Script tự động hóa SAP GUI qua win32com
SAMPLE_PYTHON_SAP_SCRIPT = '''# ==============================================================================
# KỊCH BẢN TỰ ĐỘNG HÓA SAP GUI SCRIPTING (PYTHON WIN32COM)
# Nhiệm vụ: Tự động đăng nhập/bám vào phiên SAP đang mở, chạy T-Code tra cứu
# danh bạ NNT & Cán bộ thụ lý, kết xuất dữ liệu nạp vào hệ thống HDRR.
# ==============================================================================
import sys
import json
import win32com.client

def run_sap_extraction():
    logs = []
    records = []
    
    try:
        logs.append("[SAP-INFO] Kết nối đối tượng COM SAPGUI...")
        sap_gui_auto = win32com.client.GetObject("SAPGUI")
        if not sap_gui_auto:
            raise Exception("Không tìm thấy tiến trình SAP GUI đang chạy trên máy tính.")
            
        application = sap_gui_auto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
        logs.append(f"[SAP-INFO] Đã kết nối Session: {session.Info.SystemName} / Client {session.Info.Client}")
        
        # Mở T-Code tra cứu danh bạ phân công NNT & CBQL
        tcode = "/nZ_QLNNT_CBQL"
        logs.append(f"[SAP-INFO] Gọi Transaction: {tcode}")
        session.findById("wnd[0]/tbar[0]/okcd").text = tcode
        session.findById("wnd[0]").sendVKey(0)
        
        # Thực thi tìm kiếm (F8 / Execute)
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        
        # Đọc dữ liệu từ GridView hoặc xuất file
        # (Ở đây script có thể in ra JSON stdout theo định dạng bên dưới)
        logs.append("[SAP-INFO] Trích xuất thành công danh bạ từ SAP Grid.")
        
    except Exception as e:
        logs.append(f"[SAP-ERROR] Lỗi thực thi SAP GUI Scripting: {e}")
        
    # Xuất kết quả chuẩn JSON ra stdout để ứng dụng HDRR tự động bắt
    output = {
        "status": "success" if records else "demo_or_error",
        "logs": logs,
        "records": records
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    run_sap_extraction()
'''

# Template mẫu VBScript do SAP GUI Script Recording tạo ra
SAMPLE_VBS_SAP_SCRIPT = '''' ==============================================================================
' KỊCH BẢN VBSCRIPT TỰ ĐỘNG HÓA SAP GUI (GHI BẰNG SCRIPT RECORDER)
' ==============================================================================
If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session    = connection.Children(0)
End If
If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nSE16N"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtGD-TAB").text = "ZTAX_NNT_CBQL"
session.findById("wnd[0]/tbar[1]/btn[8]").press
' Xuất dữ liệu ra file Excel tạm để HDRR thu nhận
' session.findById("wnd[0]/tbar[1]/btn[43]").press
'''


class SAPSyncModule:
    CONFIG_KEY = "sap_sync_configuration"

    DEFAULT_CONFIG = {
        "enabled": False,
        "sap_system_id": "PRD_TMS",
        "sap_client": "100",
        "sap_tcode": "Z_QLNNT_CBQL",
        "script_type": "simulation_test",  # simulation_test | inline_python | inline_vbs | external_file
        "external_script_path": r"C:\Scripts\sap_extract_cbql.py",
        "custom_script_code": SAMPLE_PYTHON_SAP_SCRIPT,
        "auto_ingest_to_db": True,
        "ingest_mode": "upsert",  # upsert | replace
        "last_sync_time": "",
        "last_sync_status": "CHƯA_CHẠY",
        "last_sync_message": "Chưa thực hiện đồng bộ lần nào.",
        "last_synced_count": 0,
    }

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Lấy cấu hình tích hợp SAP hiện tại từ CSDL sys_configs."""
        raw = DatabaseEngineModule.get_sys_config(cls.CONFIG_KEY, "")
        if raw:
            try:
                cfg = json.loads(raw)
                # Đảm bảo đầy đủ các key mặc định
                merged = dict(cls.DEFAULT_CONFIG)
                merged.update(cfg)
                return merged
            except Exception:
                pass
        return dict(cls.DEFAULT_CONFIG)

    @classmethod
    def save_config(cls, new_cfg: Dict[str, Any], officer_name: str = "Admin") -> Dict[str, Any]:
        """Lưu cấu hình tích hợp SAP vào CSDL sys_configs."""
        current = cls.get_config()
        current.update(new_cfg)
        DatabaseEngineModule.set_sys_config(
            cls.CONFIG_KEY, json.dumps(current, ensure_ascii=False), updated_by=officer_name
        )
        return current

    @classmethod
    def run_sync(cls, override_config: Optional[Dict[str, Any]] = None, officer_name: str = "Admin") -> Dict[str, Any]:
        """
        Kích hoạt chạy slot kịch bản SAP Auto-Sync.
        Hỗ trợ 4 chế độ:
          1. simulation_test: Chạy giả lập thử nghiệm đường ống dữ liệu SAP.
          2. inline_python: Thực thi mã Python Script được Admin viết/dán trực tiếp trên giao diện web.
          3. inline_vbs: Thực thi mã VBScript qua cscript.exe trên Windows.
          4. external_file: Thực thi file script có sẵn theo đường dẫn trên máy chủ.
        Sau đó tự động nạp kết quả vào bảng dm_nnt_cbql nếu auto_ingest_to_db=True.
        """
        cfg = cls.get_config()
        if override_config:
            cfg.update(override_config)

        start_time = time.time()
        start_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        logs: List[str] = [f"[{start_str}] [SAP-START] Bắt đầu kích hoạt quy trình đồng bộ tự động từ SAP..."]
        logs.append(f"[{start_str}] [SAP-INFO] Hệ thống: {cfg.get('sap_system_id')} | Client: {cfg.get('sap_client')} | T-Code: {cfg.get('sap_tcode')}")
        logs.append(f"[{start_str}] [SAP-INFO] Chế độ kịch bản: {cfg.get('script_type')}")

        script_type = cfg.get("script_type", "simulation_test")
        records: List[Dict[str, str]] = []
        status = "success"
        message = ""

        try:
            if script_type == "simulation_test":
                # Chế độ giả lập thông minh: Quét các cán bộ hiện có và sinh ra các bản ghi cập nhật mẫu từ SAP
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-SIM] Khởi chạy bộ mô phỏng SAP GUI Scripting Adapter...")
                time.sleep(0.6)  # Giả lập thời gian handshake với SAP
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-SIM] Đã bắt thành công SAP Session PRD_TMS (Client 100).")
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-SIM] Thực thi Transaction Code: {cfg.get('sap_tcode')}...")
                time.sleep(0.4)
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-SIM] Trích xuất bảng phân công NNT & CBT thành công.")

                # Sinh dữ liệu mẫu từ các cán bộ thực tế trong hệ thống để người dùng kiểm tra ngay
                records = cls._generate_simulation_records()
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-SIM] Tổng cộng nhận diện {len(records)} bản ghi phân công từ SAP.")

            elif script_type in ("inline_python", "inline_vbs"):
                code = cfg.get("custom_script_code", "")
                if not code.strip():
                    raise ValueError("Nội dung mã kịch bản Script trống! Vui lòng nhập mã script SAP.")

                ext = ".py" if script_type == "inline_python" else ".vbs"
                with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False, encoding="utf-8") as tf:
                    tf.write(code)
                    tmp_script_path = tf.name

                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-RUN] Đã tạo file script tạm: {tmp_script_path}")
                records, sub_logs = cls._execute_script_file(tmp_script_path, script_type)
                logs.extend(sub_logs)

                # Dọn dẹp file tạm
                try:
                    os.unlink(tmp_script_path)
                except Exception:
                    pass

            elif script_type == "external_file":
                file_path = cfg.get("external_script_path", "")
                if not file_path or not Path(file_path).exists():
                    raise FileNotFoundError(f"Không tìm thấy file kịch bản SAP tại đường dẫn: {file_path}")

                file_ext = Path(file_path).suffix.lower()
                stype = "inline_python" if file_ext == ".py" else ("inline_vbs" if file_ext == ".vbs" else "external_file")
                records, sub_logs = cls._execute_script_file(file_path, stype)
                logs.extend(sub_logs)

            else:
                raise ValueError(f"Loại kịch bản '{script_type}' không được hỗ trợ.")

            # Tự động nạp vào CSDL nếu bật auto_ingest
            added_cnt = 0
            updated_cnt = 0
            if cfg.get("auto_ingest_to_db", True) and records:
                ingest_mode = cfg.get("ingest_mode", "upsert")
                added_cnt, updated_cnt = cls.ingest_sap_records_to_db(records, mode=ingest_mode)
                logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-DB] Đã đồng bộ vào dm_nnt_cbql ({ingest_mode.upper()}): "
                    f"+{added_cnt} thêm mới, {updated_cnt} cập nhật."
                )

            duration = round(time.time() - start_time, 2)
            message = (
                f"Đồng bộ SAP hoàn thành thành công trong {duration}s! "
                f"Trích xuất {len(records)} NNT, cập nhật CSDL: +{added_cnt} mới, {updated_cnt} sửa."
            )
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-SUCCESS] {message}")

        except Exception as e:
            status = "error"
            duration = round(time.time() - start_time, 2)
            message = f"Lỗi trong quá trình chạy kịch bản SAP: {str(e)}"
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [SAP-ERROR] {message}")

        # Lưu lại trạng thái đồng bộ cuối cùng
        cfg["last_sync_time"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cfg["last_sync_status"] = "THÀNH_CÔNG" if status == "success" else "LỖI"
        cfg["last_sync_message"] = message
        cfg["last_synced_count"] = len(records)
        cls.save_config(cfg, officer_name=officer_name)

        return {
            "status": status,
            "message": message,
            "records_count": len(records),
            "added_count": added_cnt if "added_cnt" in locals() else 0,
            "updated_count": updated_cnt if "updated_cnt" in locals() else 0,
            "duration_seconds": duration,
            "logs": logs,
            "sample_records": records[:10] if records else [],
        }

    @classmethod
    def _execute_script_file(cls, script_path: str, script_type: str) -> Tuple[List[Dict[str, str]], List[str]]:
        """Thực thi file script (Python hoặc VBScript) và thu thập dữ liệu đầu ra."""
        sub_logs = []
        records = []
        p = Path(script_path)

        if script_type == "inline_vbs" or p.suffix.lower() == ".vbs":
            cmd = ["cscript.exe", "//nologo", str(p)]
        else:
            cmd = [sys.executable, str(p)]

        sub_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [EXEC] Thực thi lệnh: {' '.join(cmd)}")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)

        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            raise RuntimeError(f"Script kết thúc với mã lỗi {res.returncode}: {err}")

        stdout = res.stdout.strip()
        sub_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [EXEC-OUT] Script đã hoàn thành, kích thước output: {len(stdout)} ký tự.")

        # Thử đọc định dạng JSON từ output của script
        if stdout:
            try:
                # Tìm chuỗi JSON trong output
                start_idx = stdout.find("{")
                end_idx = stdout.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    raw_json = stdout[start_idx : end_idx + 1]
                    data = json.loads(raw_json)
                    if isinstance(data, dict):
                        if "logs" in data and isinstance(data["logs"], list):
                            sub_logs.extend(data["logs"])
                        if "records" in data and isinstance(data["records"], list):
                            records = data["records"]
                    elif isinstance(data, list):
                        records = data
            except Exception as e:
                sub_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [PARSE-WARN] Không thể phân tích JSON từ stdout: {e}")

        # Nếu script tạo ra file Excel/CSV đầu ra ngầm trong thư mục chạy
        export_candidates = list(p.parent.glob("*.xlsx")) + list(p.parent.glob("*.csv"))
        if not records and export_candidates:
            latest = max(export_candidates, key=lambda f: f.stat().st_mtime)
            # Nếu file vừa được tạo trong vòng 3 phút qua
            if time.time() - latest.stat().st_mtime < 180:
                sub_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [AUTO-DETECT] Tìm thấy file dữ liệu xuất từ SAP: {latest.name}")
                if latest.suffix.lower() == ".csv":
                    df = pd.read_csv(latest, dtype=str)
                else:
                    df = pd.read_excel(latest, dtype=str)
                records = cls._dataframe_to_nnt_records(df)

        return records, sub_logs

    @staticmethod
    def _dataframe_to_nnt_records(df: pd.DataFrame) -> List[Dict[str, str]]:
        """Chuẩn hóa cột DataFrame thành danh sách bản ghi NNT & CBQL."""
        cols = {str(c).strip().lower(): c for c in df.columns}
        mst_col = next((cols[k] for k in cols if any(x in k for x in ["mst", "mã số thuế", "tax"])), None)
        ten_col = next((cols[k] for k in cols if any(x in k for x in ["ten", "tên", "người nộp thuế", "doanh nghiệp"])), None)
        cb_col = next((cols[k] for k in cols if any(x in k for x in ["cán bộ", "can_bo", "cbql", "chuyên viên", "quản lý"])), None)
        em_col = next((cols[k] for k in cols if any(x in k for x in ["email", "hòm thư", "mail"])), None)
        dc_col = next((cols[k] for k in cols if any(x in k for x in ["địa chỉ", "dia_chi", "address"])), None)

        results = []
        if not mst_col:
            return results

        for _, row in df.iterrows():
            mst = str(row.get(mst_col, "")).strip()
            if not mst or mst.lower() in ("nan", "none"):
                continue
            # Làm sạch MST dạng float như 4300512503.0
            if mst.endswith(".0"):
                mst = mst[:-2]
            results.append({
                "mst": mst,
                "ten_nnt": str(row.get(ten_col, "")).strip() if ten_col else "",
                "can_bo_quan_ly": str(row.get(cb_col, "")).strip() if cb_col else "",
                "email_cbql": str(row.get(em_col, "")).strip() if em_col else "",
                "dia_chi": str(row.get(dc_col, "")).strip() if dc_col else "",
            })
        return results

    @classmethod
    def _generate_simulation_records(cls) -> List[Dict[str, str]]:
        """Sinh danh bạ NNT & CBT mẫu mô phỏng từ dữ liệu thực tế ngành thuế Quảng Ngãi."""
        sample_officers = [
            ("Bùi Thị Huyền Ân", "bthan.qng@gdt.gov.vn"),
            ("Phan Trung Hiếu", "pthieu1.qng@gdt.gov.vn"),
            ("Lê Thị Mai Phương", "ltmphuong.qng@gdt.gov.vn"),
            ("Phạm Thị Duyên", "ptduyen.qng@gdt.gov.vn"),
            ("Trần Thị Ngọc Quyên", "ttnquyen.qng@gdt.gov.vn"),
            ("Lê Thị Như Thư", "ltnthu.qng@gdt.gov.vn"),
            ("Trần Như Ngân", "tnngan.qng@gdt.gov.vn"),
            ("Nguyễn Phạm Trà My", "nptmy.qng@gdt.gov.vn"),
            ("Trần Thị Diễm", "ttdiem.qng@gdt.gov.vn"),
        ]

        # Lấy 15 MST thực tế từ bảng DSRR 2026 để làm phong phú dữ liệu đồng bộ
        records = []
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            rows = conn.execute("SELECT mst, ten_cong_ty, can_bo_xu_ly FROM dsrr_2026 ORDER BY id DESC LIMIT 15").fetchall()
            for idx, r in enumerate(rows):
                mst = r["mst"]
                ten = r["ten_cong_ty"] or f"DOANH NGHIỆP ĐỒNG BỘ SAP #{idx+1}"
                cb, em = sample_officers[idx % len(sample_officers)]
                records.append({
                    "mst": mst,
                    "ten_nnt": ten,
                    "can_bo_quan_ly": cb,
                    "email_cbql": em,
                    "dia_chi": f"Khu kinh tế Dung Quất / TP Quảng Ngãi, Tỉnh Quảng Ngãi (Đồng bộ SAP TMS {datetime.now().strftime('%d/%m/%Y')})",
                })
        return records

    @classmethod
    def ingest_sap_records_to_db(cls, records: List[Dict[str, str]], mode: str = "upsert") -> Tuple[int, int]:
        """Nạp danh sách bản ghi trích xuất được từ SAP vào bảng dm_nnt_cbql."""
        added = 0
        updated = 0

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            cur = conn.cursor()
            if mode == "replace":
                cur.execute("DELETE FROM dm_nnt_cbql")

            for r in records:
                mst = (r.get("mst") or "").strip()
                if not mst:
                    continue
                ten = (r.get("ten_nnt") or "").strip()
                cb = (r.get("can_bo_quan_ly") or "").strip()
                em = (r.get("email_cbql") or "").strip()
                dc = (r.get("dia_chi") or "").strip()

                # Tự suy luận email nếu trống nhưng có tên cán bộ
                if not em and cb:
                    # Gợi ý email theo quy ước ngành thuế nếu thiếu
                    words = cb.split()
                    if words:
                        first_letters = "".join([w[0].lower() for w in words[:-1]])
                        last_name = words[-1].lower()
                        # Chuẩn hóa tiếng việt không dấu đơn giản
                        em = f"{first_letters}{last_name}.qng@gdt.gov.vn"

                existing = cur.execute("SELECT mst FROM dm_nnt_cbql WHERE mst = ?", (mst,)).fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE dm_nnt_cbql SET
                            ten_nnt = COALESCE(NULLIF(?, ''), ten_nnt),
                            can_bo_quan_ly = COALESCE(NULLIF(?, ''), can_bo_quan_ly),
                            email_cbql = COALESCE(NULLIF(?, ''), email_cbql),
                            dia_chi = COALESCE(NULLIF(?, ''), dia_chi)
                        WHERE mst = ?
                        """,
                        (ten, cb, em, dc, mst),
                    )
                    updated += 1
                else:
                    cur.execute(
                        """
                        INSERT INTO dm_nnt_cbql (mst, ten_nnt, can_bo_quan_ly, email_cbql, dia_chi)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (mst, ten, cb, em, dc),
                    )
                    added += 1

            conn.commit()
        return added, updated
