with open('app/static/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update Step 2 of dsrrModal with:
# - Box TBGT with attachment
# - Box Mời làm việc with BBLV attachment
# - Box Chuyển thông tin phòng KTra with PKT attachment & response text
# - GTDN label for result PDF

old_step2 = """          <!-- SUB-BOX: SỐ THÔNG BÁO & NGÀY BAN HÀNH & HẠN GIẢI TRÌNH (+10 NGÀY LÀM VIỆC) -->
          <div id="boxTbDetails" style="background:#f5f3ff; border:1px solid #c4b5fd; border-radius:6px; padding:10px 12px; margin-top:6px;">
            <div style="font-size:12px; font-weight:800; color:#5b21b6; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
              <span>📋 Chi tiết Thông báo Giải trình & Thời hạn đôn đốc:</span>
              <span style="font-size:11px; font-weight:normal; color:#6b21a8;">(Tự động tính thời hạn giải trình = Ngày ban hành + 10 ngày làm việc)</span>
            </div>
            <div class="form-grid-3">
              <div class="form-group">
                <label for="md_so_thong_bao">Số thông báo giải trình:</label>
                <input type="text" id="md_so_thong_bao" placeholder="VD: 133/TB-QNG" style="background:#fff;">
              </div>
              <div class="form-group">
                <label for="md_ngay_thong_bao">Ngày ban hành thông báo:</label>
                <input type="text" id="md_ngay_thong_bao" placeholder="dd/mm/yyyy" oninput="onNgayThongBaoChanged()" style="background:#fff; font-weight:700;">
              </div>
              <div class="form-group">
                <label for="md_han_giai_trinh" style="color:#b91c1c; font-weight:800;">Thời hạn giải trình (+10 ngày làm việc):</label>
                <input type="text" id="md_han_giai_trinh" placeholder="Tự động tính (+10 ngày)" readonly style="background:#fef2f2; color:#b91c1c; font-weight:800;">
              </div>
            </div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">
              💡 <i>Thời hạn giải trình không tính thứ Bảy, Chủ nhật. Quá thời hạn này nếu doanh nghiệp chưa giải trình hoặc chưa cập nhật kết quả, hệ thống sẽ tự động gửi email đôn đốc qua Outlook.</i>
            </div>
          </div>
        </div>"""

new_step2 = """          <!-- 1. SUB-BOX: SỐ THÔNG BÁO & NGÀY BAN HÀNH & ĐÍNH KÈM THÔNG BÁO GIẢI TRÌNH (TBGT) -->
          <div id="boxTbDetails" style="background:#f5f3ff; border:1px solid #c4b5fd; border-radius:6px; padding:10px 12px; margin-top:6px;">
            <div style="font-size:12px; font-weight:800; color:#5b21b6; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
              <span>📋 Chi tiết Thông báo Giải trình & Thời hạn đôn đốc:</span>
              <span style="font-size:11px; font-weight:normal; color:#6b21a8;">(Tự động tính thời hạn giải trình = Ngày ban hành + 10 ngày làm việc)</span>
            </div>
            <div class="form-grid-3">
              <div class="form-group">
                <label for="md_so_thong_bao">Số thông báo giải trình:</label>
                <input type="text" id="md_so_thong_bao" placeholder="VD: 133/TB-QNG" style="background:#fff;">
              </div>
              <div class="form-group">
                <label for="md_ngay_thong_bao">Ngày ban hành thông báo:</label>
                <input type="text" id="md_ngay_thong_bao" placeholder="dd/mm/yyyy" oninput="onNgayThongBaoChanged()" style="background:#fff; font-weight:700;">
              </div>
              <div class="form-group">
                <label for="md_han_giai_trinh" style="color:#b91c1c; font-weight:800;">Thời hạn giải trình (+10 ngày làm việc):</label>
                <input type="text" id="md_han_giai_trinh" placeholder="Tự động tính (+10 ngày)" readonly style="background:#fef2f2; color:#b91c1c; font-weight:800;">
              </div>
            </div>
            <div class="form-group" style="margin-top:8px;">
              <label for="md_upload_tbgt_pdf" style="color:#5b21b6; font-weight:700;">📄 Đính kèm tệp Thông báo giải trình (Tự động đổi tên: <code>TBGT_ddmmyyyy_MST...pdf</code>):</label>
              <div style="display:flex; gap:6px; align-items:center;">
                <input type="file" id="md_upload_tbgt_pdf" accept=".pdf" style="background:#fff; flex:1;" onchange="handleUploadTbgtPdf(this)">
                <input type="hidden" id="md_tbgt_pdf">
              </div>
              <div id="md_tbgt_attached_box" style="margin-top:4px; font-size:12px; display:none;">
                <span>Đã đính kèm:</span>
                <a id="md_tbgt_attached_link" href="#" target="_blank" style="font-weight:700; color:#2563eb; text-decoration:none;"></a>
                <button type="button" class="btn btn-outline" style="padding:1px 6px; font-size:11px; margin-left:6px; color:#dc2626; border-color:#fca5a5;" onclick="clearAttachedTbgtPdf()">✕ Gỡ bỏ</button>
              </div>
            </div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">
              💡 <i>Thời hạn giải trình không tính thứ Bảy, Chủ nhật. Quá thời hạn này nếu doanh nghiệp chưa giải trình hoặc chưa cập nhật kết quả, hệ thống sẽ tự động gửi email đôn đốc qua Outlook.</i>
            </div>
          </div>

          <!-- 2. SUB-BOX: CHI TIẾT MỜI LÀM VIỆC & BIÊN BẢN LÀM VIỆC (BBLV) -->
          <div id="boxMlvDetails" style="display:none; background:#f0fdf4; border:1.5px solid #86efac; border-radius:6px; padding:10px 12px; margin-top:6px;">
            <div style="font-size:12px; font-weight:800; color:#166534; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
              <span>🤝 Chi tiết Mời Doanh nghiệp Làm việc & Đính kèm Biên bản Làm việc:</span>
            </div>
            <div class="form-grid-2">
              <div class="form-group">
                <label for="md_so_bblv">Số biên bản & Ngày làm việc:</label>
                <div style="display:flex; gap:6px;">
                  <input type="text" id="md_so_bblv" placeholder="Số BB (VD: 01/BBLV)" style="width:50%; background:#fff;">
                  <input type="text" id="md_ngay_bblv" placeholder="Ngày dd/mm/yyyy" style="width:50%; background:#fff; font-weight:700;">
                </div>
              </div>
              <div class="form-group">
                <label for="md_upload_bblv_pdf" style="color:#166534; font-weight:700;">📄 Đính kèm Biên bản làm việc (Tự động đổi tên: <code>BBLV_ddmmyyyy_MST...pdf</code>):</label>
                <div style="display:flex; gap:6px; align-items:center;">
                  <input type="file" id="md_upload_bblv_pdf" accept=".pdf" style="background:#fff; flex:1;" onchange="handleUploadBblvPdf(this)">
                  <input type="hidden" id="md_bblv_pdf">
                </div>
                <div id="md_bblv_attached_box" style="margin-top:4px; font-size:12px; display:none;">
                  <span>Đã đính kèm:</span>
                  <a id="md_bblv_attached_link" href="#" target="_blank" style="font-weight:700; color:#16a34a; text-decoration:none;"></a>
                  <button type="button" class="btn btn-outline" style="padding:1px 6px; font-size:11px; margin-left:6px; color:#dc2626; border-color:#fca5a5;" onclick="clearAttachedBblvPdf()">✕ Gỡ bỏ</button>
                </div>
              </div>
            </div>
          </div>

          <!-- 3. SUB-BOX: CHI TIẾT CHUYỂN THÔNG TIN & PHẢN HỒI TỪ PHÒNG KIỂM TRA (PKT) -->
          <div id="boxPktDetails" style="display:none; background:#faf5ff; border:1.5px solid #d8b4fe; border-radius:6px; padding:10px 12px; margin-top:6px;">
            <div style="font-size:12px; font-weight:800; color:#6b21a8; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
              <span>🏢 Phối Hợp & Phản Hồi Từ Phòng Kiểm Tra Thuế:</span>
            </div>
            <div class="form-grid-2">
              <div class="form-group">
                <label for="md_pkt_noi_dung" style="color:#581c87; font-weight:700;">Nội dung Phòng Kiểm tra phản hồi:</label>
                <textarea id="md_pkt_noi_dung" rows="2" style="background:#fff;" placeholder="Ghi nhận nội dung, kết luận phối hợp của Phòng Kiểm tra..."></textarea>
              </div>
              <div class="form-group">
                <label for="md_upload_pkt_pdf" style="color:#6b21a8; font-weight:700;">📄 Đính kèm File phản hồi Phòng KT (Tự động đổi tên: <code>PKT_ddmmyyyy_MST...pdf</code>):</label>
                <div style="display:flex; gap:6px; align-items:center;">
                  <input type="file" id="md_upload_pkt_pdf" accept=".pdf" style="background:#fff; flex:1;" onchange="handleUploadPktPdf(this)">
                  <input type="hidden" id="md_pkt_pdf">
                </div>
                <div id="md_pkt_attached_box" style="margin-top:4px; font-size:12px; display:none;">
                  <span>Đã đính kèm:</span>
                  <a id="md_pkt_attached_link" href="#" target="_blank" style="font-weight:700; color:#7c3aed; text-decoration:none;"></a>
                  <button type="button" class="btn btn-outline" style="padding:1px 6px; font-size:11px; margin-left:6px; color:#dc2626; border-color:#fca5a5;" onclick="clearAttachedPktPdf()">✕ Gỡ bỏ</button>
                </div>
              </div>
            </div>
          </div>
        </div>"""

assert old_step2 in c, "old_step2 not found in index.html"
c = c.replace(old_step2, new_step2, 1)

# 2. Update Result PDF label
old_lbl_res = '<label for="md_upload_result_pdf" style="color:#5b21b6; font-weight:800;">Chọn tệp PDF kết quả đính kèm:</label>'
new_lbl_res = '<label for="md_upload_result_pdf" style="color:#5b21b6; font-weight:800;">📄 Chọn tệp PDF Văn bản giải trình doanh nghiệp (Tự động đổi tên: <code>GTDN_ddmmyyyy_MST...pdf</code>):</label>'
assert old_lbl_res in c, "old_lbl_res not found in index.html"
c = c.replace(old_lbl_res, new_lbl_res, 1)

# 3. Add bundle zip download in modal footer
old_modal_footer = """    <div class="modal-footer" style="justify-content:flex-end;">
      <div style="display:flex; gap:10px;">
        <button class="btn btn-outline" onclick="closeDsrrModal()">Đóng [ESC]</button>
        <button class="btn btn-primary" id="btnSaveDsrrModal" onclick="saveDsrrUpdate()">💾 Lưu Kết quả Cập nhật [Ctrl+S]</button>
      </div>
    </div>"""

new_modal_footer = """    <div class="modal-footer" style="justify-content:space-between;">
      <button type="button" class="btn btn-outline" style="border-color:#3b82f6; color:#1d4ed8; font-weight:700; display:inline-flex; align-items:center; gap:6px;" onclick="downloadRecordBundleZip(document.getElementById('md_id').value)" title="Gom toàn bộ file CVRR, TBGT, GTDN, BBLV, PKT và tóm tắt tiến độ tải về trong 1 file ZIP">
        📦 Tải Trọn Bộ Hồ Sơ (ZIP)
      </button>
      <div style="display:flex; gap:10px;">
        <button class="btn btn-outline" onclick="closeDsrrModal()">Đóng [ESC]</button>
        <button class="btn btn-primary" id="btnSaveDsrrModal" onclick="saveDsrrUpdate()">💾 Lưu Kết quả Cập nhật [Ctrl+S]</button>
      </div>
    </div>"""

assert old_modal_footer in c, "old_modal_footer not found in index.html"
c = c.replace(old_modal_footer, new_modal_footer, 1)

# 4. Add Download All SharePdf ZIP button in mod_sharepdf
old_share_btns = """          <div style="display:flex; gap:8px;">
            <button class="btn btn-success" onclick="triggerManualBackup()">💾 Sao lưu CSDL Ngay</button>
            <button class="btn btn-outline" onclick="promptChangeSharePath()">📁 Đổi / Kiểm tra Đường dẫn</button>
            <button class="btn btn-primary" onclick="refreshData()">🔄 Quét lại Kho PDF</button>
          </div>"""

new_share_btns = """          <div style="display:flex; gap:8px;">
            <button class="btn btn-outline" style="border-color:#10b981; color:#047857; font-weight:700;" onclick="downloadAllSharePdfZip()" title="Gom toàn bộ file PDF trong kho lưu trữ SharePdf tải về 1 lần dạng .ZIP">📦 Tải Trọn Bộ Kho PDF (ZIP)</button>
            <button class="btn btn-success" onclick="triggerManualBackup()">💾 Sao lưu CSDL Ngay</button>
            <button class="btn btn-outline" onclick="promptChangeSharePath()">📁 Đổi / Kiểm tra Đường dẫn</button>
            <button class="btn btn-primary" onclick="refreshData()">🔄 Quét lại Kho PDF</button>
          </div>"""

assert old_share_btns in c, "old_share_btns not found in index.html"
c = c.replace(old_share_btns, new_share_btns, 1)

with open('app/static/index.html', 'w', encoding='utf-8') as f:
    f.write(c)

print("Updated index.html modal and sharepdf successfully!")
