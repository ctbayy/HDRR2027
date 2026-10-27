"""
[MODULE ADMIN MANAGEMENT & DIRECTORY INGEST]
Quản trị danh mục Người Nộp Thuế & Cán bộ Quản lý / Email (@gdt.gov.vn) tại bảng `dm_nnt_cbql`,
cho phép xem, tìm kiếm, phân trang, thêm mới, sửa, xóa,
kết xuất Excel và nạp dữ liệu từ file Excel (chế độ Upsert hoặc Replace).
"""

import io
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .database import DatabaseEngineModule


class AdminManagementModule:
    @classmethod
    def get_kpis(cls) -> Dict[str, Any]:
        """Tính toán các chỉ số thống kê về danh mục NNT và Cán bộ quản lý."""
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            total_nnt = conn.execute("SELECT COUNT(*) FROM dm_nnt_cbql").fetchone()[0]
            with_email = conn.execute(
                "SELECT COUNT(*) FROM dm_nnt_cbql WHERE email_cbql IS NOT NULL AND email_cbql != ''"
            ).fetchone()[0]
            distinct_officers = conn.execute(
                "SELECT COUNT(DISTINCT can_bo_quan_ly) FROM dm_nnt_cbql WHERE can_bo_quan_ly IS NOT NULL AND can_bo_quan_ly != ''"
            ).fetchone()[0]
            no_officer = conn.execute(
                "SELECT COUNT(*) FROM dm_nnt_cbql WHERE can_bo_quan_ly IS NULL OR can_bo_quan_ly = ''"
            ).fetchone()[0]

            # Top cán bộ quản lý nhiều NNT nhất
            top_officers = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT can_bo_quan_ly, email_cbql, COUNT(*) as nnt_count
                    FROM dm_nnt_cbql
                    WHERE can_bo_quan_ly IS NOT NULL AND can_bo_quan_ly != ''
                    GROUP BY can_bo_quan_ly
                    ORDER BY nnt_count DESC
                    LIMIT 8
                    """
                ).fetchall()
            ]

        return {
            "total_nnt": total_nnt,
            "with_email": with_email,
            "without_email": total_nnt - with_email,
            "distinct_officers": distinct_officers,
            "no_officer": no_officer,
            "top_officers": top_officers,
        }

    @classmethod
    def get_nnt_list(
        cls, page: int = 1, page_size: int = 50, search: str = "", officer_filter: str = ""
    ) -> Dict[str, Any]:
        """Lấy danh sách NNT có phân trang, tìm kiếm đa trường và lọc theo cán bộ quản lý."""
        page = max(1, int(page))
        page_size = max(10, min(200, int(page_size)))
        offset = (page - 1) * page_size

        where_clauses = []
        params: List[Any] = []

        if search:
            terms = [t.strip() for t in search.split() if t.strip()]
            for t in terms:
                where_clauses.append(
                    "(mst LIKE ? OR ten_nnt LIKE ? OR can_bo_quan_ly LIKE ? OR email_cbql LIKE ? OR dia_chi LIKE ?)"
                )
                p = f"%{t}%"
                params.extend([p, p, p, p, p])

        if officer_filter:
            where_clauses.append("can_bo_quan_ly = ?")
            params.append(officer_filter)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            total_records = conn.execute(f"SELECT COUNT(*) FROM dm_nnt_cbql {where_sql}", params).fetchone()[0]
            query_sql = f"""
                SELECT mst, ten_nnt, can_bo_quan_ly, email_cbql, dia_chi
                FROM dm_nnt_cbql
                {where_sql}
                ORDER BY can_bo_quan_ly ASC, mst ASC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(query_sql, params + [page_size, offset]).fetchall()

            # Lấy danh sách tất cả cán bộ quản lý phục vụ dropdown lọc
            officers = [
                r[0]
                for r in conn.execute(
                    """
                    SELECT DISTINCT can_bo_quan_ly FROM dm_nnt_cbql
                    WHERE can_bo_quan_ly IS NOT NULL AND can_bo_quan_ly != ''
                    ORDER BY can_bo_quan_ly ASC
                    """
                ).fetchall()
            ]

        total_pages = max(1, (total_records + page_size - 1) // page_size)

        return {
            "records": [dict(r) for r in rows],
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "officers": officers,
        }

    @classmethod
    def save_nnt_record(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Thêm mới hoặc cập nhật một bản ghi NNT & Cán bộ quản lý."""
        mst = (payload.get("mst") or "").strip()
        if not mst:
            raise ValueError("Mã số thuế không được để trống!")

        ten = (payload.get("ten_nnt") or "").strip()
        cb = (payload.get("can_bo_quan_ly") or "").strip()
        em = (payload.get("email_cbql") or "").strip()
        dc = (payload.get("dia_chi") or "").strip()

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
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
            conn.commit()

        return {"mst": mst, "ten_nnt": ten, "can_bo_quan_ly": cb, "email_cbql": em, "dia_chi": dc}

    @classmethod
    def delete_nnt_record(cls, mst: str) -> bool:
        """Xóa một bản ghi NNT khỏi danh mục."""
        if not mst:
            return False
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM dm_nnt_cbql WHERE mst = ?", (mst.strip(),))
            conn.commit()
            return cur.rowcount > 0

    @classmethod
    def import_excel_bytes(cls, file_bytes: bytes, mode: str = "upsert") -> Dict[str, Any]:
        """
        Nạp dữ liệu từ file Excel (.xlsx / .xls) vào bảng `dm_nnt_cbql`.
        Hỗ trợ 2 chế độ:
          - 'upsert': Cập nhật nếu trùng MST, thêm mới nếu chưa có (Mặc định - An toàn).
          - 'replace': Xóa sạch danh mục hiện tại và ghi đè danh mục mới hoàn toàn.
        """
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        except Exception as e:
            raise ValueError(f"Không thể đọc file Excel. Vui lòng kiểm tra định dạng file (.xlsx, .xls): {e}")

        # Chuẩn hóa tên các cột
        col_map = {str(c).strip().lower(): c for c in df.columns}

        def find_col(aliases: List[str]) -> Optional[str]:
            for a in aliases:
                for k, v in col_map.items():
                    if a in k:
                        return v
            return None

        mst_c = find_col(["mst", "mã số thuế", "ma_so_thue", "tax"])
        ten_c = find_col(["tên nnt", "ten_nnt", "người nộp thuế", "tên doanh nghiệp", "tên công ty", "tên đơn vị"])
        cb_c = find_col(["cán bộ quản lý", "can_bo_quan_ly", "cbql", "cán bộ", "can_bo", "chuyên viên"])
        em_c = find_col(["email cbql", "email_cbql", "email", "hòm thư", "mail"])
        dc_c = find_col(["địa chỉ", "dia_chi", "trụ sở", "address"])

        if not mst_c:
            raise ValueError(
                f"Không tìm thấy cột Mã số thuế trong file Excel! Các cột tìm thấy: {', '.join(df.columns)}"
            )

        added = 0
        updated = 0
        skipped = 0

        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            cur = conn.cursor()
            if mode == "replace":
                cur.execute("DELETE FROM dm_nnt_cbql")

            for _, row in df.iterrows():
                raw_mst = str(row.get(mst_c, "")).strip()
                if not raw_mst or raw_mst.lower() in ("nan", "none", "null"):
                    skipped += 1
                    continue

                # Làm sạch MST dạng số thập phân của Excel (ví dụ: 4300512503.0 -> 4300512503)
                if raw_mst.endswith(".0"):
                    raw_mst = raw_mst[:-2]

                ten = str(row.get(ten_c, "")).strip() if ten_c else ""
                cb = str(row.get(cb_c, "")).strip() if cb_c else ""
                em = str(row.get(em_c, "")).strip() if em_c else ""
                dc = str(row.get(dc_c, "")).strip() if dc_c else ""

                if ten.lower() in ("nan", "none"):
                    ten = ""
                if cb.lower() in ("nan", "none"):
                    cb = ""
                if em.lower() in ("nan", "none"):
                    em = ""
                if dc.lower() in ("nan", "none"):
                    dc = ""

                # Tự suy luận email nếu chưa có mà có tên cán bộ
                if not em and cb:
                    words = cb.split()
                    if words:
                        first_letters = "".join([w[0].lower() for w in words[:-1]])
                        last_name = words[-1].lower()
                        em = f"{first_letters}{last_name}.qng@gdt.gov.vn"

                existing = cur.execute("SELECT mst FROM dm_nnt_cbql WHERE mst = ?", (raw_mst,)).fetchone()
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
                        (ten, cb, em, dc, raw_mst),
                    )
                    updated += 1
                else:
                    cur.execute(
                        """
                        INSERT INTO dm_nnt_cbql (mst, ten_nnt, can_bo_quan_ly, email_cbql, dia_chi)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (raw_mst, ten, cb, em, dc),
                    )
                    added += 1

            conn.commit()

        return {
            "mode": mode,
            "total_rows": len(df),
            "added_count": added,
            "updated_count": updated,
            "skipped_count": skipped,
            "message": f"Nạp Excel thành công: Thêm mới {added} NNT, Cập nhật {updated} NNT (Bỏ qua {skipped} dòng trống).",
        }

    @classmethod
    def export_excel_bytes(cls) -> bytes:
        """Xuất toàn bộ danh mục NNT & Cán bộ quản lý ra file Excel."""
        with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
            df = pd.read_sql_query(
                """
                SELECT
                    mst AS 'Mã số thuế (*)',
                    ten_nnt AS 'Tên Người nộp thuế (*)',
                    can_bo_quan_ly AS 'Cán bộ quản lý (CBQL)',
                    email_cbql AS 'Email CBQL (@gdt.gov.vn)',
                    dia_chi AS 'Địa chỉ trụ sở'
                FROM dm_nnt_cbql
                ORDER BY can_bo_quan_ly ASC, mst ASC
                """,
                conn,
            )

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Danh_Muc_NNT_CBQL", index=False)
        return buf.getvalue()

    @classmethod
    def export_template_bytes(cls) -> bytes:
        """Xuất file Excel mẫu chuẩn hướng dẫn Admin nạp dữ liệu."""
        sample_data = [
            {
                "Mã số thuế (*)": "4300512503",
                "Tên Người nộp thuế (*)": "CÔNG TY CỔ PHẦN ĐẦU TƯ XÂY DỰNG MINH ĐỨC",
                "Cán bộ quản lý (CBQL)": "Trần Như Ngân",
                "Email CBQL (@gdt.gov.vn)": "tnngan.qng@gdt.gov.vn",
                "Địa chỉ trụ sở": "TP. Quảng Ngãi, Tỉnh Quảng Ngãi",
            },
            {
                "Mã số thuế (*)": "4300341921",
                "Tên Người nộp thuế (*)": "CÔNG TY CỔ PHẦN PHÚC HƯNG",
                "Cán bộ quản lý (CBQL)": "Phạm Thị Thúy Ánh",
                "Email CBQL (@gdt.gov.vn)": "pttanh.qng@gdt.gov.vn",
                "Địa chỉ trụ sở": "Huyện Bình Sơn, Tỉnh Quảng Ngãi",
            },
            {
                "Mã số thuế (*)": "4300476333",
                "Tên Người nộp thuế (*)": "TOÀ ÁN NHÂN DÂN TỈNH QUẢNG NGÃI",
                "Cán bộ quản lý (CBQL)": "Phan Trung Hiếu",
                "Email CBQL (@gdt.gov.vn)": "pthieu1.qng@gdt.gov.vn",
                "Địa chỉ trụ sở": "TP. Quảng Ngãi, Tỉnh Quảng Ngãi",
            },
            {
                "Mã số thuế (*)": "4300429492",
                "Tên Người nộp thuế (*)": "CÔNG TY CỔ PHẦN BAO BÌ DẦU KHÍ BÌNH SƠN",
                "Cán bộ quản lý (CBQL)": "Bùi Thị Huyền Ân",
                "Email CBQL (@gdt.gov.vn)": "bthan.qng@gdt.gov.vn",
                "Địa chỉ trụ sở": "KKT Dung Quất, Tỉnh Quảng Ngãi",
            },
        ]
        df = pd.DataFrame(sample_data)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Mau_Nap_NNT_CBQL", index=False)
        return buf.getvalue()
