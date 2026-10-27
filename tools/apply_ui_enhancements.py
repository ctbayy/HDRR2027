"""
Script áp dụng 3 yêu cầu cải tiến giao diện:
1. Đồng bộ màu sắc chuyên nghiệp (Corporate Navy / Slate), loại bỏ màu sắc lòe loẹt làm rối mắt.
2. Thêm nút đính kèm tệp Công văn rủi ro (CVRR) tại giao diện chung và modal cập nhật kết quả.
3. Bố trí lại các bảng dữ liệu: chia tách Mã số thuế và Tên doanh nghiệp thành 2 cột riêng biệt.
"""

from pathlib import Path

# =========================================================================
# 1. CẬP NHẬT STYLE.CSS: ĐỒNG BỘ MÀU SẮC CHUẨN DOANH NGHIỆP / CÔNG SỞ THUẾ
# =========================================================================
css_path = Path("app/static/style.css")
css = css_path.read_text(encoding="utf-8")

# Thay thế các active-mod* thành phong cách đồng bộ navy/slate
old_nav_active = """.nav-btn.active-mod1 {
  background: linear-gradient(90deg, #1d4ed8, #1e40af);
  color: #fff;
  border-color: #60a5fa;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}

.nav-btn.active-mod2 {
  background: linear-gradient(90deg, #047857, #065f46);
  color: #fff;
  border-color: #34d399;
}

.nav-btn.active-mod3 {
  background: linear-gradient(90deg, #6d28d9, #5b21b6);
  color: #fff;
  border-color: #a78bfa;
}

.nav-btn.active-mod4 {
  background: linear-gradient(90deg, #b45309, #92400e);
  color: #fff;
  border-color: #fbbf24;
}

.nav-btn.active-mod5 {
  background: linear-gradient(90deg, #e11d48, #be123c);
  color: #fff;
  border-color: #fda4af;
  box-shadow: 0 2px 8px rgba(225, 29, 72, 0.3);
}"""

new_nav_active = """.nav-btn.active-mod0,
.nav-btn.active-mod1,
.nav-btn.active-mod2,
.nav-btn.active-mod3,
.nav-btn.active-mod4,
.nav-btn.active-mod5 {
  background: #1e293b !important;
  color: #ffffff !important;
  border: 1px solid #334155 !important;
  border-left: 4px solid #38bdf8 !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
  font-weight: 700 !important;
}

.nav-btn.active-mod0 .dot,
.nav-btn.active-mod1 .dot,
.nav-btn.active-mod2 .dot,
.nav-btn.active-mod3 .dot,
.nav-btn.active-mod4 .dot,
.nav-btn.active-mod5 .dot {
  background: #38bdf8 !important;
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.8) !important;
}"""

if old_nav_active in css:
    css = css.replace(old_nav_active, new_nav_active, 1)

# Thay thế các class card-action-* lòe loẹt thành thiết kế đồng bộ
old_card_actions = """.card-action-green::before { background: #059669; }
.card-action-green:hover { border-color: #6ee7b7; background: linear-gradient(135deg, #f0fdf4 0%, #fff 60%); }
.card-action-green .action-icon-wrap { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }

.card-action-blue::before { background: #2563eb; }
.card-action-blue:hover { border-color: #93c5fd; background: linear-gradient(135deg, #eff6ff 0%, #fff 60%); }
.card-action-blue .action-icon-wrap { background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }

.card-action-amber::before { background: #d97706; }
.card-action-amber:hover { border-color: #fde68a; background: linear-gradient(135deg, #fffbeb 0%, #fff 60%); }
.card-action-amber .action-icon-wrap { background: #fffbeb; color: #d97706; border-color: #fde68a; }

.card-action-purple::before { background: #7c3aed; }
.card-action-purple:hover { border-color: #c4b5fd; background: linear-gradient(135deg, #f5f3ff 0%, #fff 60%); }
.card-action-purple .action-icon-wrap { background: #f5f3ff; color: #7c3aed; border-color: #ddd6fe; }

.card-action-rose::before { background: #e11d48; }
.card-action-rose:hover { border-color: #fda4af; background: linear-gradient(135deg, #fff1f2 0%, #fff 60%); }
.card-action-rose .action-icon-wrap { background: #fff1f2; color: #e11d48; border-color: #fecdd3; }

.card-action-slate::before { background: #475569; }
.card-action-slate:hover { border-color: #cbd5e1; background: linear-gradient(135deg, #f8fafc 0%, #fff 60%); }
.card-action-slate .action-icon-wrap { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }"""

new_card_actions = """/* THIẾT KẾ ĐỒNG BỘ THẺ THAO TÁC NHANH (QUICK ACTIONS) */
.quick-action-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: #2563eb;
  transition: all 0.2s ease;
  opacity: 0.7;
}

.quick-action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(30, 58, 138, 0.08);
  border-color: #93c5fd;
  background: #f8fafc;
}

.quick-action-card:hover::before {
  opacity: 1;
  width: 5px;
}

.action-icon-wrap {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1e40af;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.quick-action-card:hover .action-icon-wrap {
  background: #dbeafe;
  border-color: #93c5fd;
  transform: scale(1.05);
}"""

if old_card_actions in css:
    css = css.replace(old_card_actions, new_card_actions, 1)

# Thêm style bổ trợ cho nút đính kèm nhanh và bảng
extra_css = """
/* NÚT ĐÍNH KÈM NHANH FILE CVRR */
.btn-quick-attach {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  font-size: 11.5px;
  font-weight: 700;
  border: 1.5px dashed #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.btn-quick-attach:hover {
  background: #dbeafe;
  border-color: #1d4ed8;
  transform: translateY(-1px);
}

/* ĐỒNG BỘ STEP CARD TRONG MODAL */
.step-card {
  background: #ffffff !important;
  border: 1.5px solid #cbd5e1 !important;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.step-title {
  color: #0f172a !important;
  font-weight: 800;
  font-size: 13.5px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-num {
  background: #1e40af !important;
  color: #ffffff !important;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
}

/* BẢNG DỮ LIỆU ĐỒNG BỘ */
th {
  background: #f1f5f9 !important;
  color: #334155 !important;
  border-bottom: 2px solid #cbd5e1 !important;
  font-weight: 700 !important;
  font-size: 12px !important;
}
td code {
  background: #f1f5f9;
  padding: 2px 5px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}
"""
css += extra_css
css_path.write_text(css, encoding="utf-8")
print("1. Da cap nhat style.css thanh cong!")


# =========================================================================
# 2. CẬP NHẬT INDEX.HTML: CỘT BẢNG MÃ SỐ THUẾ & TÊN DOANH NGHIỆP TÁCH RỜI,
#    BỔ SUNG KHỐI ĐÍNH KÈM CVRR TRONG DSRR MODAL VÀ INPUT TOÀN CỤC
# =========================================================================
html_path = Path("app/static/index.html")
html = html_path.read_text(encoding="utf-8")

# Thêm input file ẩn toàn cục cho việc đính kèm CVRR ngay từ bảng
global_input = '<input type="file" id="globalCvrrFileInput" accept=".pdf" style="display:none;" onchange="onGlobalCvrrFileSelected(this)">'
if global_input not in html:
    html = html.replace("</body>", f"{global_input}\n</body>", 1)

# Bảng 1: Dashboard Recent Records (tbodyDashRecent thead)
old_dash_thead = """            <thead>
              <tr>
                <th style="width:230px;">Doanh nghiệp / Mã số thuế</th>
                <th style="width:190px;">Công văn đến</th>
                <th style="width:160px;">Cán bộ phụ trách</th>
                <th>Quá trình & Hạn giải trình (+10 ngày)</th>
                <th style="width:125px; text-align:center;">Trạng thái</th>
                <th style="width:110px; text-align:center;">Thao tác</th>
              </tr>
            </thead>"""

new_dash_thead = """            <thead>
              <tr>
                <th style="width:130px;">Mã số thuế</th>
                <th style="width:230px;">Tên Người nộp thuế</th>
                <th style="width:180px;">Công văn đến</th>
                <th style="width:150px;">Cán bộ phụ trách</th>
                <th>Quá trình & Hạn giải trình (+10 ngày)</th>
                <th style="width:120px; text-align:center;">Trạng thái</th>
                <th style="width:160px; text-align:center;">Tài liệu & Thao tác</th>
              </tr>
            </thead>"""

if old_dash_thead in html:
    html = html.replace(old_dash_thead, new_dash_thead, 1)

# Bảng 2: Bảng theo dõi DSRR (tbodyDsrr thead)
old_dsrr_thead = """            <thead>
              <tr>
                <th class="sortable" onclick="sortDsrrTable('id')" style="width:130px;" title="Bấm để sắp xếp theo STT / Số văn bản">1. Công văn đến <span id="sort_icon_dsrr_id" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('mst')" style="width:220px;" title="Bấm để sắp xếp theo Mã số thuế / Tên doanh nghiệp">2. Doanh nghiệp quản lý <span id="sort_icon_dsrr_mst" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('tinh_trang')" style="width:155px;" title="Bấm để sắp xếp theo Trạng thái / Cán bộ">3. Trạng thái & Cán bộ <span id="sort_icon_dsrr_tinh_trang" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('mst_rr')" style="width:185px;" title="Bấm để sắp xếp theo Doanh nghiệp rủi ro">4. DN bán rủi ro <span id="sort_icon_dsrr_mst_rr" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('han_gt')" title="Bấm để sắp xếp theo Hạn giải trình / Tiến độ">5. Tiến độ & Hạn giải trình <span id="sort_icon_dsrr_han_gt" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('so_tien')" style="width:230px;" title="Bấm để sắp xếp theo Số liệu tiền thuế / hóa đơn">6. Số liệu hóa đơn & Thuế nộp <span id="sort_icon_dsrr_so_tien" class="sort-indicator">↕</span></th>
                <th style="width:155px;">7. Hồ sơ kết quả & Thao tác</th>
              </tr>
            </thead>"""

new_dsrr_thead = """            <thead>
              <tr>
                <th class="sortable" onclick="sortDsrrTable('id')" style="width:130px;" title="Bấm để sắp xếp theo STT / Số văn bản">1. Công văn đến <span id="sort_icon_dsrr_id" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('mst')" style="width:125px;" title="Bấm để sắp xếp theo Mã số thuế">2. Mã số thuế <span id="sort_icon_dsrr_mst" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('ten_cong_ty')" style="width:220px;" title="Bấm để sắp xếp theo Tên doanh nghiệp">3. Tên Người nộp thuế <span id="sort_icon_dsrr_ten_cong_ty" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('tinh_trang')" style="width:145px;" title="Bấm để sắp xếp theo Trạng thái / Cán bộ">4. Trạng thái & Cán bộ <span id="sort_icon_dsrr_tinh_trang" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('mst_rr')" style="width:165px;" title="Bấm để sắp xếp theo Doanh nghiệp rủi ro">5. DN bán rủi ro <span id="sort_icon_dsrr_mst_rr" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('han_gt')" title="Bấm để sắp xếp theo Hạn giải trình / Tiến độ">6. Tiến độ & Hạn giải trình <span id="sort_icon_dsrr_han_gt" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortDsrrTable('so_tien')" style="width:175px;" title="Bấm để sắp xếp theo Số liệu tiền thuế">7. Thuế tự điều chỉnh <span id="sort_icon_dsrr_so_tien" class="sort-indicator">↕</span></th>
                <th style="width:170px; text-align:center;">8. Tài liệu & Thao tác</th>
              </tr>
            </thead>"""

if old_dsrr_thead in html:
    html = html.replace(old_dsrr_thead, new_dsrr_thead, 1)

# Bảng 3: Bảng tra cứu Inspect (tbodyInspectResult thead)
old_inspect_thead = """            <thead>
              <tr>
                <th class="sortable" onclick="sortInspectTable('id')" style="width:60px;" title="Bấm để sắp xếp theo STT">STT <span id="sort_icon_inspect_id" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst')" style="width:220px;" title="Bấm để sắp xếp theo MST/Doanh nghiệp">Doanh nghiệp quản lý <span id="sort_icon_inspect_mst" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst_rr')" style="width:180px;" title="Bấm để sắp xếp theo DN bán rủi ro">DN bán rủi ro <span id="sort_icon_inspect_mst_rr" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('so_cv')" style="width:160px;" title="Bấm để sắp xếp theo Công văn đến">Công văn đến <span id="sort_icon_inspect_so_cv" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('tinh_trang')" style="width:150px;" title="Bấm để sắp xếp theo Trạng thái & Cán bộ">Trạng thái & Cán bộ <span id="sort_icon_inspect_tinh_trang" class="sort-indicator">↕</span></th>
                <th>Quá trình xử lý & Hạn giải trình</th>
                <th style="width:180px; text-align:center;">Tài liệu kết quả</th>
              </tr>
            </thead>"""

new_inspect_thead = """            <thead>
              <tr>
                <th class="sortable" onclick="sortInspectTable('id')" style="width:55px;" title="Bấm để sắp xếp theo STT">STT <span id="sort_icon_inspect_id" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst')" style="width:125px;" title="Bấm để sắp xếp theo Mã số thuế">Mã số thuế <span id="sort_icon_inspect_mst" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('ten_cong_ty')" style="width:210px;" title="Bấm để sắp xếp theo Tên doanh nghiệp">Tên Doanh nghiệp <span id="sort_icon_inspect_ten_cong_ty" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst_rr')" style="width:165px;" title="Bấm để sắp xếp theo DN bán rủi ro">DN bán rủi ro <span id="sort_icon_inspect_mst_rr" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('so_cv')" style="width:140px;" title="Bấm để sắp xếp theo Công văn đến">Công văn đến <span id="sort_icon_inspect_so_cv" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('tinh_trang')" style="width:145px;" title="Bấm để sắp xếp theo Trạng thái & Cán bộ">Trạng thái & Cán bộ <span id="sort_icon_inspect_tinh_trang" class="sort-indicator">↕</span></th>
                <th>Quá trình xử lý & Hạn giải trình</th>
                <th style="width:170px; text-align:center;">Tài liệu & Thao tác</th>
              </tr>
            </thead>"""

if old_inspect_thead in html:
    html = html.replace(old_inspect_thead, new_inspect_thead, 1)

# Bảng 4: Bảng nhắc việc Outlook (tbodyReminderRows thead)
old_reminder_thead = """            <tr>
              <th style="width:45px;">STT</th>
              <th style="width:190px;">Cán bộ xử lý & Email (@gdt.gov.vn)</th>
              <th style="width:230px;">Doanh nghiệp & MST cần xử lý</th>
              <th style="width:170px;">DN có dấu hiệu rủi ro</th>
              <th style="width:150px;">Thời gian tồn đọng</th>
              <th>Tiến độ hiện tại</th>
              <th style="width:165px; text-align:center;">Thao tác Outlook</th>
            </tr>"""

new_reminder_thead = """            <tr>
              <th style="width:45px;">STT</th>
              <th style="width:180px;">Cán bộ xử lý & Email (@gdt.gov.vn)</th>
              <th style="width:125px;">Mã số thuế</th>
              <th style="width:210px;">Tên Doanh nghiệp cần xử lý</th>
              <th style="width:160px;">DN có dấu hiệu rủi ro</th>
              <th style="width:130px;">Thời gian tồn đọng</th>
              <th>Tiến độ hiện tại</th>
              <th style="width:150px; text-align:center;">Thao tác Outlook</th>
            </tr>"""

if old_reminder_thead in html:
    html = html.replace(old_reminder_thead, new_reminder_thead, 1)

# Bổ sung khối ĐÍNH KÈM CÔNG VĂN RỦI RO (CVRR) vào Bước 1 của dsrrModal
old_modal_step1 = """        <div class="form-grid-3">
          <div class="form-group">
            <label for="md_mst">Mã số thuế & Tên Doanh nghiệp thuộc cơ quan thuế quản lý</label>
            <div style="display:flex; gap:6px;">
              <input type="text" id="md_mst" readonly style="width:130px; background:#e2e8f0; font-weight:800;">
              <input type="text" id="md_ten_cong_ty" style="flex:1; background:#fff;">
            </div>
          </div>
          <div class="form-group">
            <label for="md_tinh_trang">Tình trạng xử lý & Cán bộ thuế phụ trách quản lý</label>
            <div style="display:flex; gap:6px;">
              <select id="md_tinh_trang" style="width:155px; font-weight:800; background:#fff;">
                <option value="Chưa xử lý">🔴 Chưa xử lý</option>
                <option value="Đang xử lý">🟡 Đang xử lý</option>
                <option value="Đã xử lý">🟢 Đã xử lý</option>
              </select>
              <input type="text" id="md_can_bo" placeholder="Cán bộ xử lý" style="flex:1; background:#fff;">
            </div>
          </div>
          <div class="form-group">
            <label for="md_mst_rr">Mã số thuế & Tên Doanh nghiệp bán có dấu hiệu rủi ro</label>
            <div style="display:flex; gap:6px;">
              <input type="text" id="md_mst_rr" style="width:125px; background:#fff; color:#dc2626; font-weight:800;">
              <input type="text" id="md_ten_cty_rr" placeholder="Tên doanh nghiệp rủi ro" style="flex:1; background:#fff;">
            </div>
          </div>
        </div>
      </div>"""

new_modal_step1 = """        <div class="form-grid-3">
          <div class="form-group">
            <label for="md_mst">Mã số thuế & Tên Doanh nghiệp thuộc cơ quan thuế quản lý</label>
            <div style="display:flex; gap:6px;">
              <input type="text" id="md_mst" readonly style="width:130px; background:#f1f5f9; font-weight:800; color:#1e40af;">
              <input type="text" id="md_ten_cong_ty" style="flex:1; background:#fff; font-weight:700;">
            </div>
          </div>
          <div class="form-group">
            <label for="md_tinh_trang">Tình trạng xử lý & Cán bộ thuế phụ trách quản lý</label>
            <div style="display:flex; gap:6px;">
              <select id="md_tinh_trang" style="width:155px; font-weight:800; background:#fff;">
                <option value="Chưa xử lý">🔴 Chưa xử lý</option>
                <option value="Đang xử lý">🟡 Đang xử lý</option>
                <option value="Đã xử lý">🟢 Đã xử lý</option>
              </select>
              <input type="text" id="md_can_bo" placeholder="Cán bộ xử lý" style="flex:1; background:#fff;">
            </div>
          </div>
          <div class="form-group">
            <label for="md_mst_rr">Mã số thuế & Tên Doanh nghiệp bán có dấu hiệu rủi ro</label>
            <div style="display:flex; gap:6px;">
              <input type="text" id="md_mst_rr" style="width:125px; background:#fff; color:#dc2626; font-weight:800;">
              <input type="text" id="md_ten_cty_rr" placeholder="Tên doanh nghiệp rủi ro" style="flex:1; background:#fff;">
            </div>
          </div>
        </div>

        <!-- BỔ SUNG: KHỐI ĐÍNH KÈM & QUẢN LÝ TỆP CÔNG VĂN RỦI RO (CVRR) -->
        <div style="margin-top:10px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:10px 14px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
              <span style="font-weight:700; color:#1e40af; font-size:12.5px;">📎 Tệp Công văn Cảnh báo Rủi ro Ban đầu (CVRR):</span>
              <span style="font-size:11px; color:#64748b; margin-left:6px;">(Chuẩn hóa tên tệp: <code>CVRR_ddmmyyyy_MST...pdf</code>)</span>
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
              <input type="file" id="md_upload_cvrr_pdf" accept=".pdf" style="display:none;" onchange="handleUploadCvrrPdf(this)">
              <button type="button" class="btn btn-outline" style="border-color:#3b82f6; color:#1d4ed8; font-weight:700; font-size:12px; padding:4px 10px;" onclick="document.getElementById('md_upload_cvrr_pdf').click()">
                📁 Chọn Tệp CVRR Đính Kèm
              </button>
              <input type="hidden" id="md_attachment_name">
            </div>
          </div>
          <div id="md_cvrr_attached_box" style="margin-top:6px; font-size:12px; display:none; align-items:center; gap:8px;">
            <span style="color:#475569;">Đã đính kèm:</span>
            <a id="md_cvrr_attached_link" href="#" target="_blank" class="badge-pdf" style="background:#eff6ff; color:#1e40af; border-color:#bfdbfe; font-weight:700; text-decoration:none;"></a>
            <button type="button" class="btn btn-outline" style="padding:1px 6px; font-size:11px; color:#dc2626; border-color:#fca5a5;" onclick="clearAttachedCvrrPdf()">✕ Gỡ bỏ</button>
          </div>
        </div>
      </div>"""

if old_modal_step1 in html:
    html = html.replace(old_modal_step1, new_modal_step1, 1)

html_path.write_text(html, encoding="utf-8")
print("2. Da cap nhat index.html thanh cong!")
