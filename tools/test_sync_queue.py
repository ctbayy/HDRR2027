import sys
import os
import time
import sqlite3
import json

sys.path.insert(0, os.path.abspath('.'))

from app.database import DatabaseEngineModule
from app.sync_queue import LocalSyncEngineModule
from app.config import ConfigSecurityModule

DatabaseEngineModule.initialize_schema()

# Tạo 1 bản ghi mẫu để test
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    conn.execute("DELETE FROM dsrr_2026 WHERE id = 99999")
    conn.execute("""
        INSERT INTO dsrr_2026 (id, mst, ten_cong_ty, can_bo_xu_ly, tinh_trang_xu_ly)
        VALUES (99999, '0999999999', 'CÔNG TY BAN ĐẦU CHƯA SYNC', 'Nguyễn Văn Test', 'Chưa xử lý')
    """)
    conn.commit()

test_id = 99999

print("=== TEST 1: THỰC HIỆN GHI BÌNH THƯỜNG KHI CENTRAL DB RẢNH ===")
test_user = "can_bo_test_1"
user_db = LocalSyncEngineModule.get_user_staging_db_path(test_user)
# Clean up if existed
LocalSyncEngineModule._cleanup_user_staging_db(user_db)

assert not user_db.exists(), "File DB tạm của user ban đầu không được tồn tại"

# Test payload UPDATE_DSRR
payload_update = {
    "officer_name": "Nguyễn Văn Test",
    "ten_cong_ty": "CÔNG TY ĐÃ SYNC QUA QUEUE",
    "tinh_trang_xu_ly": "Đang xử lý",
    "can_bo_xu_ly": "Nguyễn Văn Test",
    "viec_da_thuc_hien": "Thông báo giải trình",
    "so_thong_bao": "TB-SYNC/2026",
    "ngay_thong_bao": "25/10/2026",
    "cam_ket_so_hd": 5,
    "cam_ket_gia_tri": 125000000,
    "nnt_giai_trinh": "Doanh nghiệp đã giải trình chi tiết qua queue"
}

ok, status, res = LocalSyncEngineModule.enqueue_and_sync(test_user, "UPDATE_DSRR", str(test_id), payload_update)
print(f"Kết quả lưu: ok={ok}, status={status}")
assert ok is True
assert status == "COMMITTED_CENTRAL"

# Kiểm tra dữ liệu trong Central DB
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    row = conn.execute("SELECT ten_cong_ty, so_thong_bao, cam_ket_so_hd, nnt_giai_trinh FROM dsrr_2026 WHERE id = ?", (test_id,)).fetchone()
    print("Dữ liệu trong Central DB sau khi sync:", dict(row))
    assert row["ten_cong_ty"] == "CÔNG TY ĐÃ SYNC QUA QUEUE"
    assert row["so_thong_bao"] == "TB-SYNC/2026"
    assert row["cam_ket_so_hd"] == 5

# KIỂM TRA ĐIỀU KIỆN QUAN TRỌNG:
# File DB tạm của user ĐÃ BỊ XÓA BỎ KHỎI MÁY để nhẹ máy!
time.sleep(0.3)
print(f"File DB tạm {user_db.name} tồn tại trên máy?: {user_db.exists()}")
assert not user_db.exists(), "LỖI: DB tạm phải được tự động xóa sau khi đã ghi thành công vào Central DB!"
print("=> ĐẠT YÊU CẦU 1: Ghi thành công vào Central DB & tự động xóa sạch DB tạm cá nhân!")

print("\n=== TEST 2: GIẢ LẬP CENTRAL DB BỊ KHÓA (LOCKED) BỞI USER KHÁC ===")
central_path = ConfigSecurityModule.get_db_path()

# Mở kết nối riêng giữ khóa EXCLUSIVE
lock_conn = sqlite3.connect(str(central_path), timeout=0.1)
lock_conn.execute("BEGIN EXCLUSIVE TRANSACTION;")

test_user_2 = "can_bo_test_2"
user_db_2 = LocalSyncEngineModule.get_user_staging_db_path(test_user_2)
LocalSyncEngineModule._cleanup_user_staging_db(user_db_2)

payload_locked = {
    "officer_name": "Trần Thị Lock",
    "ten_cong_ty": "CÔNG TY KHI CENTRAL DB ĐANG LOCKED",
    "tinh_trang_xu_ly": "Đang xử lý",
    "can_bo_xu_ly": "Trần Thị Lock",
    "so_thong_bao": "TB-LOCKED/2026",
    "cam_ket_so_hd": 10
}

# User 2 lưu khi Central đang locked
ok2, status2, res2 = LocalSyncEngineModule.enqueue_and_sync(test_user_2, "UPDATE_DSRR", str(test_id), payload_locked)
print(f"Kết quả khi Central bị khóa: ok={ok2}, status={status2}")
print(f"Phản hồi: {res2}")

assert ok2 is True, "Hệ thống vẫn phải trả về thành công cho user (không được văng lỗi locked)!"
assert status2 == "QUEUED_LOCAL_PENDING", "Trạng thái phải là QUEUED_LOCAL_PENDING"

# Kiểm tra: Vì Central DB đang locked, DB tạm của user 2 PHẢI ĐƯỢC GIỮ LẠI trên máy
assert user_db_2.exists(), "DB tạm phải được giữ lại khi chưa ghi được vào Central DB!"
print(f"DB tạm {user_db_2.name} đang giữ bản ghi chờ: {user_db_2.exists()}")

# Giờ mở khóa Central DB
print("\n=== GIẢI PHÓNG KHÓA TRÊN CENTRAL DB VÀ THỰC HIỆN SYNC LẠI ===")
lock_conn.rollback()
lock_conn.close()

# Kích hoạt flush hàng chờ
flush_ok, rem, err = LocalSyncEngineModule.flush_user_queue(test_user_2)
print(f"Kết quả flush lại: flush_ok={flush_ok}, remaining={rem}")
assert flush_ok is True
assert rem == 0

# Kiểm tra dữ liệu trong Central DB đã được cập nhật thành công
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    row = conn.execute("SELECT ten_cong_ty, so_thong_bao, cam_ket_so_hd FROM dsrr_2026 WHERE id = ?", (test_id,)).fetchone()
    print("Dữ liệu trong Central DB sau khi rảnh và sync lại:", dict(row))
    assert row["ten_cong_ty"] == "CÔNG TY KHI CENTRAL DB ĐANG LOCKED"
    assert row["so_thong_bao"] == "TB-LOCKED/2026"
    assert row["cam_ket_so_hd"] == 10

# Kiểm tra file DB tạm của user 2 ĐÃ ĐƯỢC TỰ ĐỘNG XÓA
time.sleep(0.3)
print(f"File DB tạm {user_db_2.name} sau khi sync xong có còn trên máy?: {user_db_2.exists()}")
assert not user_db_2.exists(), "DB tạm của user 2 phải được xóa sạch sau khi sync thành công!"

# Dọn dẹp bản ghi test
with DatabaseEngineModule._lock, DatabaseEngineModule.get_conn() as conn:
    conn.execute("DELETE FROM dsrr_2026 WHERE id = 99999")
    conn.commit()

print("\n=== TẤT CẢ CÁC BÀI TEST SYNC QUEUE ĐỀU THÀNH CÔNG 100%! ===")
