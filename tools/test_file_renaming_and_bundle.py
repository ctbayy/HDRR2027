import sys
import os
import io
import zipfile
import json

sys.path.insert(0, os.path.abspath('.'))

from app.database import DatabaseEngineModule
from app.ingest import DocumentIngestModule
from app.workflow import RiskWorkflowModule
from app.config import ConfigSecurityModule

DatabaseEngineModule.initialize_schema()

print("=== 1. KIỂM TRA QUY TẮC ĐẶT TÊN TỰ ĐỘNG CHUẨN HÓA ===")

# Test case 1: CVRR
f_cvrr = DocumentIngestModule.generate_standard_filename(
    doc_type="CVRR",
    mst="0318185232",
    date_str="26/12/2025",
    extra_info="6526-TCS2"
)
print("CVRR filename:", f_cvrr)
assert f_cvrr.startswith("CVRR_26122025_0318185232_6526_TCS2"), f"Lỗi tên CVRR: {f_cvrr}"

# Test case 2: TBGT
f_tbgt = DocumentIngestModule.generate_standard_filename(
    doc_type="TBGT",
    mst="4300512503",
    date_str="15/01/2026",
    extra_info="01/TB-QLDN1"
)
print("TBGT filename:", f_tbgt)
assert f_tbgt.startswith("TBGT_15012026_4300512503_01_TB_QLDN1"), f"Lỗi tên TBGT: {f_tbgt}"

# Test case 3: GTDN
f_gtdn = DocumentIngestModule.generate_standard_filename(
    doc_type="GTDN",
    mst="4300512503",
    date_str="20/01/2026",
    extra_info="CV0901-MD"
)
print("GTDN filename:", f_gtdn)
assert f_gtdn.startswith("GTDN_20012026_4300512503_CV0901_MD"), f"Lỗi tên GTDN: {f_gtdn}"

# Test case 4: BBLV
f_bblv = DocumentIngestModule.generate_standard_filename(
    doc_type="BBLV",
    mst="4300512503",
    date_str="22/01/2026",
    extra_info="01/BBLV"
)
print("BBLV filename:", f_bblv)
assert f_bblv.startswith("BBLV_22012026_4300512503_01_BBLV"), f"Lỗi tên BBLV: {f_bblv}"

# Test case 5: PKT
f_pkt = DocumentIngestModule.generate_standard_filename(
    doc_type="PKT",
    mst="4300512503",
    date_str="24/01/2026",
    extra_info="PhanHoiKT"
)
print("PKT filename:", f_pkt)
assert f_pkt.startswith("PKT_24012026_4300512503_PhanHoiKT"), f"Lỗi tên PKT: {f_pkt}"

print("=> Đạt yêu cầu 1: Tất cả 5 loại tệp đều được đổi tên theo đúng chuẩn CVRR / TBGT / GTDN / BBLV / PKT!")

print("\n=== 2. KIỂM TRA LƯU TỆP THỰC TẾ VÀO KHO SHAREPDF ===")
sample_pdf_bytes = ConfigSecurityModule._build_minimal_valid_pdf(["FILE THU NGHIEM QUY CHUAN DAT TEN"])

name_stored_cvrr, sha1 = DocumentIngestModule.store_pdf_in_sharepdf(
    filename="test_upload.pdf",
    file_bytes=sample_pdf_bytes,
    prefix_tag="CVRR",
    mst="0318185232",
    date_str="26/12/2025",
    extra_info="6526-TCS2"
)
name_stored_tbgt, sha2 = DocumentIngestModule.store_pdf_in_sharepdf(
    filename="test_tbgt.pdf",
    file_bytes=sample_pdf_bytes,
    prefix_tag="TBGT",
    mst="4300512503",
    date_str="15/01/2026",
    extra_info="TB-01"
)
name_stored_bblv, sha3 = DocumentIngestModule.store_pdf_in_sharepdf(
    filename="test_bblv.pdf",
    file_bytes=sample_pdf_bytes,
    prefix_tag="BBLV",
    mst="4300512503",
    date_str="22/01/2026",
    extra_info="BB-01"
)
name_stored_pkt, sha4 = DocumentIngestModule.store_pdf_in_sharepdf(
    filename="test_pkt.pdf",
    file_bytes=sample_pdf_bytes,
    prefix_tag="PKT",
    mst="4300512503",
    date_str="24/01/2026",
    extra_info="KetLuanKT"
)

vault = ConfigSecurityModule.get_pdf_vault_dir()
assert (vault / name_stored_cvrr).exists(), "File CVRR phải tồn tại trong SharePdf"
assert (vault / name_stored_tbgt).exists(), "File TBGT phải tồn tại trong SharePdf"
assert (vault / name_stored_bblv).exists(), "File BBLV phải tồn tại trong SharePdf"
assert (vault / name_stored_pkt).exists(), "File PKT phải tồn tại trong SharePdf"

print("Đã tạo và kiểm tra 4 file trong SharePdf thành công:")
print(" - CVRR:", name_stored_cvrr)
print(" - TBGT:", name_stored_tbgt)
print(" - BBLV:", name_stored_bblv)
print(" - PKT :", name_stored_pkt)

print("\n=== 3. KIỂM TRA ĐÓNG GÓI TRỌN BỘ HỒ SƠ THÀNH FILE ZIP (BUNDLE ZIP) ===")
test_rec = {
    "id": 8888,
    "mst": "4300512503",
    "ten_cong_ty": "CÔNG TY CP ĐẦU TƯ XÂY DỰNG MINH ĐỨC",
    "can_bo_xu_ly": "Phan Trung Hiếu",
    "tinh_trang_xu_ly": "Đang xử lý",
    "viec_da_thuc_hien": "Mời làm việc & Thông báo giải trình",
    "so_thong_bao": "01/TB-QLDN1",
    "ngay_thong_bao": "15/01/2026",
    "han_giai_trinh": "29/01/2026",
    "ghi_chu": "Doanh nghiệp đã đến làm việc ngày 22/01/2026",
    "nnt_giai_trinh": "Doanh nghiệp tự nguyện điều chỉnh giảm chi phí 12.8 tỷ",
    "de_xuat_xu_ly": "Chấp nhận giải trình, kiểm tra thực địa",
    "noi_dung_pkt_phan_hoi": "Phòng Kiểm tra thống nhất ý kiến xử lý",
    "dieu_chinh_giam_chi_phi": 12810755749,
    "dieu_chinh_giam_khau_tru": 1026905189,
    "dieu_chinh_thue_tndn": 2562151149,
    "dieu_chinh_thue_gtgt": 1026905189,
    "attachment_name": name_stored_cvrr,
    "tbgt_pdf_name": name_stored_tbgt,
    "result_pdf_name": "",
    "bblv_pdf_name": name_stored_bblv,
    "pkt_pdf_name": name_stored_pkt,
}

zip_name, zip_bytes = DocumentIngestModule.bundle_record_zip_bytes(test_rec)
print(f"File ZIP đã tạo: {zip_name} (Dung lượng: {len(zip_bytes)} bytes)")

assert zip_name.startswith("TronBoHoSo_4300512503_")
assert len(zip_bytes) > 500, "File ZIP phải có nội dung"

# Mở thử file ZIP để kiểm tra các file bên trong
with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
    file_list = z.namelist()
    print("Danh sách tệp bên trong ZIP:")
    for f in file_list:
        print("  *", f)
    
    assert any("00_Thong_Tin_Ho_So_Rui_Ro_4300512503.txt" in f for f in file_list), "Thiếu file tóm tắt hồ sơ!"
    assert name_stored_cvrr in file_list, f"Thiếu {name_stored_cvrr} trong ZIP!"
    assert name_stored_tbgt in file_list, f"Thiếu {name_stored_tbgt} trong ZIP!"
    assert name_stored_bblv in file_list, f"Thiếu {name_stored_bblv} trong ZIP!"
    assert name_stored_pkt in file_list, f"Thiếu {name_stored_pkt} trong ZIP!"

    # Đọc nội dung file tóm tắt txt
    txt_content = z.read("00_Thong_Tin_Ho_So_Rui_Ro_4300512503.txt").decode("utf-8")
    assert "CÔNG TY CP ĐẦU TƯ XÂY DỰNG MINH ĐỨC" in txt_content
    assert "12.810.755.749" in txt_content
    assert "Phan Trung Hiếu" in txt_content
    assert name_stored_bblv in txt_content

print("=> Đạt yêu cầu 2: Gom trọn bộ hồ sơ thành file ZIP gửi kết quả 1 lần hoạt động hoàn hảo!")

print("\n=== 4. KIỂM TRA ĐÓNG GÓI TOÀN BỘ KHO SHAREPDF DẠNG ZIP ===")
all_zip_name, all_zip_bytes = DocumentIngestModule.bundle_all_sharepdf_zip_bytes()
print(f"File toàn bộ kho PDF ZIP: {all_zip_name} ({len(all_zip_bytes)} bytes)")
with zipfile.ZipFile(io.BytesIO(all_zip_bytes), "r") as z:
    all_files = z.namelist()
    print(f"Tổng cộng có {len(all_files)} file PDF trong kho được nén thành công.")
    assert len(all_files) >= 4

print("\n=== TẤT CẢ CÁC BÀI TEST CHUẨN HÓA TÊN FILE VÀ ZIP BUNDLE THÀNH CÔNG 100%! ===")
