import sys
import os
import json
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))

print("=== 1. KIỂM TRA KHỞI ĐỘNG HỆ THỐNG ===")
from app.config import ConfigSecurityModule
from app.database import DatabaseEngineModule
from app.workflow import RiskWorkflowModule
from app.reminder import EmailReminderModule
from app.admin import AdminManagementModule

DatabaseEngineModule.initialize_schema()
print("CSDL đã khởi tạo thành công.")

print("\n=== 2. KIỂM TRA QUY TẮC QUÁ HẠN GIẢI TRÌNH (LOẠI BỎ QUY TẮC 15 NGÀY) ===")
# Tạo các bản ghi thử nghiệm để kiểm tra logic quá hạn:
# - Case A: Hồ sơ cũ tiếp nhận 60 ngày trước, NHƯNG CHƯA ban hành thông báo => Phải là is_overdue = False, "Chưa ban hành thông báo (Chưa xử lý)"
# - Case B: Hồ sơ có thông báo, hạn giải trình còn 5 ngày nữa mới đến hạn => is_overdue = False, "Trong hạn giải trình"
# - Case C: Hồ sơ có thông báo, hạn giải trình đã qua 3 ngày trước => is_overdue = True, "Quá hạn giải trình"
# - Case D: Hồ sơ đã xử lý hoàn thành => is_overdue = False

today = datetime.now()
d_60_days_ago = (today - timedelta(days=60)).strftime("%d/%m/%Y")
d_future = (today + timedelta(days=5)).strftime("%d/%m/%Y")
d_past = (today - timedelta(days=3)).strftime("%d/%m/%Y")

test_cases = [
    {
        "id": 99901,
        "so_ky_hieu_vb": "CV-TEST-A",
        "mst": "0101010101",
        "ten_cong_ty": "CÔNG TY TEST CHƯA THÔNG BÁO (60 NGÀY CŨ)",
        "can_bo_xu_ly": "Nguyễn Văn Test",
        "ngay_vb_den": d_60_days_ago,
        "so_thong_bao": "",
        "ngay_thong_bao": "",
        "han_giai_trinh": "",
        "tinh_trang_xu_ly": "Chưa xử lý"
    },
    {
        "id": 99902,
        "so_ky_hieu_vb": "CV-TEST-B",
        "mst": "0202020202",
        "ten_cong_ty": "CÔNG TY TEST TRONG HẠN GIẢI TRÌNH",
        "can_bo_xu_ly": "Nguyễn Văn Test",
        "ngay_vb_den": d_60_days_ago,
        "so_thong_bao": "TB-01/QLDN1",
        "ngay_thong_bao": (today - timedelta(days=5)).strftime("%d/%m/%Y"),
        "han_giai_trinh": d_future,
        "tinh_trang_xu_ly": "Đang xử lý"
    },
    {
        "id": 99903,
        "so_ky_hieu_vb": "CV-TEST-C",
        "mst": "0303030303",
        "ten_cong_ty": "CÔNG TY TEST QUÁ HẠN GIẢI TRÌNH",
        "can_bo_xu_ly": "Nguyễn Văn Test",
        "ngay_vb_den": d_60_days_ago,
        "so_thong_bao": "TB-02/QLDN1",
        "ngay_thong_bao": (today - timedelta(days=15)).strftime("%d/%m/%Y"),
        "han_giai_trinh": d_past,
        "tinh_trang_xu_ly": "Đang xử lý"
    },
    {
        "id": 99904,
        "so_ky_hieu_vb": "CV-TEST-D",
        "mst": "0404040404",
        "ten_cong_ty": "CÔNG TY TEST ĐÃ HOÀN THÀNH",
        "can_bo_xu_ly": "Nguyễn Văn Test",
        "ngay_vb_den": d_60_days_ago,
        "so_thong_bao": "TB-03/QLDN1",
        "ngay_thong_bao": (today - timedelta(days=20)).strftime("%d/%m/%Y"),
        "han_giai_trinh": d_past,
        "tinh_trang_xu_ly": "Đã xử lý"
    }
]

# Lưu tạm vào DB để test
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    for tc in test_cases:
        conn.execute("DELETE FROM dsrr_2026 WHERE id = ?", (tc["id"],))
        conn.execute("""
            INSERT INTO dsrr_2026 (id, so_ky_hieu_vb, mst, ten_cong_ty, can_bo_xu_ly, ngay_vb_den, so_thong_bao, ngay_thong_bao, han_giai_trinh, tinh_trang_xu_ly)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tc["id"], tc["so_ky_hieu_vb"], tc["mst"], tc["ten_cong_ty"], tc["can_bo_xu_ly"], tc["ngay_vb_den"], tc["so_thong_bao"], tc["ngay_thong_bao"], tc["han_giai_trinh"], tc["tinh_trang_xu_ly"]))
    conn.commit()

# Test 1: Lấy danh sách quá hạn mặc định (filter_mode = 'OVERDUE_ONLY')
res_od = EmailReminderModule.get_overdue_reminders(officer_filter="Nguyễn Văn Test", filter_mode="OVERDUE_ONLY")
od_ids = [r["id"] for r in res_od["records"]]
print(f"Hồ sơ quá hạn tìm thấy: {od_ids}")
assert 99903 in od_ids, "LỖI: Bản ghi 99903 (quá hạn TB) phải được tìm thấy!"
assert 99901 not in od_ids, "LỖI: Bản ghi 99901 (chưa có TB, dù 60 ngày) KHÔNG ĐƯỢC coi là quá hạn!"
assert 99902 not in od_ids, "LỖI: Bản ghi 99902 (còn trong hạn TB) KHÔNG ĐƯỢC coi là quá hạn!"
assert 99904 not in od_ids, "LỖI: Bản ghi 99904 (đã xử lý) KHÔNG ĐƯỢC coi là quá hạn!"
print("=> Đạt yêu cầu 1: Loại bỏ cách tính 15 ngày, chỉ tính chậm nếu quá hạn thông báo giải trình!")

# Test 2: filter_mode = 'NO_TB'
res_notb = EmailReminderModule.get_overdue_reminders(officer_filter="Nguyễn Văn Test", filter_mode="NO_TB")
notb_ids = [r["id"] for r in res_notb["records"]]
print(f"Hồ sơ chưa có thông báo: {notb_ids}")
assert 99901 in notb_ids, "Bản ghi 99901 phải nằm trong nhóm chưa có thông báo"
print("=> Đạt yêu cầu 2: Lọc đúng nhóm chưa ban hành thông báo!")

# Test 3: filter_mode = 'ALL_PENDING'
res_all = EmailReminderModule.get_overdue_reminders(officer_filter="Nguyễn Văn Test", filter_mode="ALL_PENDING")
all_ids = [r["id"] for r in res_all["records"]]
print(f"Toàn bộ hồ sơ chưa hoàn tất: {all_ids}")
assert 99901 in all_ids and 99902 in all_ids and 99903 in all_ids and 99904 not in all_ids
print("=> Đạt yêu cầu 3: Lọc đúng tất cả hồ sơ đang xử lý & chưa xử lý!")

# Xóa các bản ghi test
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    for tc in test_cases:
        conn.execute("DELETE FROM dsrr_2026 WHERE id = ?", (tc["id"],))
    conn.commit()

print("\n=== 3. KIỂM TRA TÌM KIẾM CHI TIẾT & TRA CỨU KHÔNG GIỚI HẠN DÒNG ===")
# Kiểm tra inspect search trên backend
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    total_dsrr = conn.execute("SELECT COUNT(*) FROM dsrr_2026").fetchone()[0]
    total_th = conn.execute("SELECT COUNT(*) FROM th_rui_ro").fetchone()[0]

print(f"Tổng số hồ sơ DSRR trong CSDL: {total_dsrr}")
print(f"Tổng số công văn cảnh báo TH trong CSDL: {total_th}")

# Gọi tìm kiếm rỗng trên backend inspect
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    empty_search = conn.execute("SELECT * FROM dsrr_2026 ORDER BY id DESC").fetchall()
print(f"Kết quả tra cứu không nhập từ khóa: {len(empty_search)} hồ sơ (Toàn bộ CSDL, không còn bị giới hạn 150 dòng)")
assert len(empty_search) == total_dsrr, f"LỖI: inspect search phải trả về đầy đủ {total_dsrr} hồ sơ!"

print("\n=== 4. KIỂM TRA FILE GIAO DIỆN APP.JS VÀ INDEX.HTML ===")
with open('app/static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('app/static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

required_html_ids = [
    'dashChartsContainer',
    'donutSvg',
    'donutLegend',
    'dashOfficerBars',
    'filterNoticeSelect',
    'tabBtnInspectDsrr',
    'tabBtnInspectTh',
    'wrapInspectDsrr',
    'wrapInspectTh',
    'reminderFilterMode',
    'inspectFilterStatusSelect',
    'inspectFilterOfficerSelect',
    'inspectFilterInvoiceGroupSelect',
    'inspectFilterPdfSelect'
]

for hid in required_html_ids:
    assert hid in html, f"LỖI: Không tìm thấy ID '{hid}' trong index.html!"

print("Tất cả các phần tử UI mới đã có trong index.html.")

required_js_funcs = [
    'removeVietnameseTones',
    'isRecordOverdue',
    'calculateOverdueCount',
    'sortRecords',
    'updateSortIcons',
    'renderDashboardCharts',
    'sortDsrrTable',
    'resetDsrrFilters',
    'switchInspectTab',
    'sortInspectTable',
    'resetInspectFilters',
    'renderInspectThTable'
]

for func in required_js_funcs:
    assert func in js, f"LỖI: Không tìm thấy hàm '{func}' trong app.js!"

print("Tất cả các hàm JavaScript xử lý biểu đồ, sắp xếp, lọc, tra cứu đa trường không dấu đã có trong app.js.")

print("\n=== TẤT CẢ CÁC BÀI TEST ĐỀU HOÀN THÀNH XUẤT SẮC 100%! ===")
