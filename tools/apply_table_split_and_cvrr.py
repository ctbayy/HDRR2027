"""
Script ap dung:
1. Cap nhat index.html inspect table thead thanh 8 cot tach rieng MST va Ten NNT.
2. Cap nhat app/static/app.js:
   - sortRecords: ho tro 'ten_cong_ty' va tach 'mst'
   - renderDashboard: tach MST va Ten NNT thanh 2 o rieng, nut dinh kem CVRR, colspan=7
   - renderDsrrTable: tach MST va Ten NNT thanh 2 o rieng, nut dinh kem CVRR, colspan=8
   - executeInspectorSearch: tach MST va Ten NNT thanh 2 o rieng, nut dinh kem CVRR, colspan=8
   - renderReminderTableRows: tach MST va Ten NNT thanh 2 o rieng, colspan=8
   - openDsrrModal: load attachment_name va hien thi link/box
   - saveDsrrUpdate: gui kem attachment_name
   - bo sung ham clearAttachedCvrrPdf, handleUploadCvrrPdf, triggerQuickUploadCvrr, onGlobalCvrrFileSelected
"""

from pathlib import Path
import re

# =========================================================================
# 1. CAP NHAT INDEX.HTML
# =========================================================================
html_file = Path("app/static/index.html")
html_text = html_file.read_text(encoding="utf-8")

# Tim va thay the thead cua mod_inspect
old_inspect_needle = """<th class="sortable" onclick="sortInspectTable('id')" style="width:60px;" title="Bấm để sắp xếp theo STT">STT <span id="sort_icon_inspect_id" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst')" style="width:220px;" title="Bấm để sắp xếp theo Mã số thuế / Tên NNT">Doanh nghiệp NNT (MST & Tên) <span id="sort_icon_inspect_mst" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst_rr')" style="width:190px;" title="Bấm để sắp xếp theo DN rủi ro">DN bán có dấu hiệu rủi ro <span id="sort_icon_inspect_mst_rr" class="sort-indicator">↕</span></th>"""

new_inspect_needle = """<th class="sortable" onclick="sortInspectTable('id')" style="width:55px;" title="Bấm để sắp xếp theo STT">STT <span id="sort_icon_inspect_id" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst')" style="width:125px;" title="Bấm để sắp xếp theo Mã số thuế">Mã số thuế <span id="sort_icon_inspect_mst" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('ten_cong_ty')" style="width:210px;" title="Bấm để sắp xếp theo Tên người nộp thuế">Tên Người nộp thuế <span id="sort_icon_inspect_ten_cong_ty" class="sort-indicator">↕</span></th>
                <th class="sortable" onclick="sortInspectTable('mst_rr')" style="width:170px;" title="Bấm để sắp xếp theo DN bán rủi ro">DN bán có dấu hiệu rủi ro <span id="sort_icon_inspect_mst_rr" class="sort-indicator">↕</span></th>"""

if old_inspect_needle in html_text:
    html_text = html_text.replace(old_inspect_needle, new_inspect_needle, 1)
    print("1. Da cap nhat inspect table thead trong index.html")
else:
    print("Warning: old_inspect_needle khong tim thay trong index.html")

html_file.write_text(html_text, encoding="utf-8")


# =========================================================================
# 2. CAP NHAT APP/STATIC/APP.JS
# =========================================================================
js_file = Path("app/static/app.js")
js_text = js_file.read_text(encoding="utf-8")

# A. sortRecords
old_sort_mst = """      case 'mst':
        valA = ((a.mst || '') + ' ' + (a.ten_cong_ty || '')).toLowerCase();
        valB = ((b.mst || '') + ' ' + (b.ten_cong_ty || '')).toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;"""

new_sort_mst = """      case 'mst':
        valA = String(a.mst || '').toLowerCase();
        valB = String(b.mst || '').toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;
      case 'ten_cong_ty':
        valA = String(a.ten_cong_ty || '').toLowerCase();
        valB = String(b.ten_cong_ty || '').toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;"""

if old_sort_mst in js_text:
    js_text = js_text.replace(old_sort_mst, new_sort_mst, 1)
    print("2A. Da cap nhat sortRecords")
else:
    print("Warning: old_sort_mst khong tim thay")

# B. renderDashboard - tbodyRecent
old_dash_recent = """    if (displayList.length === 0) {
      tbodyRecent.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:25px; color:#64748b;">Chưa có dữ liệu hồ sơ rủi ro.</td></tr>`;
    } else {
      tbodyRecent.innerHTML = displayList.map(r => {
        const isOd = isRecordOverdue(r);
        return `
        <tr class="${rowColorClass(r.tinh_trang_xu_ly)} ${isOd ? 'row-overdue' : ''}">
          <td>
            <b style="color:#0f172a; font-size:13px;">${r.mst || '-'}</b><br>
            <span style="font-size:12px; font-weight:600; color:#1e293b;">${r.ten_cong_ty || ''}</span>
          </td>
          <td>
            <b style="color:#1e40af; font-size:12px;">${r.so_ky_hieu_vb || '-'}</b><br>
            <small style="color:#64748b;">Ngày đến: ${r.ngay_vb_den || '-'}</small>
            ${r.so_den_vb ? `<div style="font-size:11px; color:#334155;">Số đến: <b>${r.so_den_vb}</b></div>` : ''}
          </td>
          <td>
            <div style="font-size:12px; font-weight:700; color:#0f172a;">👤 ${r.can_bo_xu_ly || 'Chưa phân công'}</div>
          </td>
          <td>
            ${r.so_thong_bao ? `<div style="font-size:11.5px; color:#5b21b6;"><b>• Số TB:</b> ${r.so_thong_bao} ${r.ngay_thong_bao ? `(${r.ngay_thong_bao})` : ''}</div>` : ''}
            ${r.han_giai_trinh ? `<div style="font-size:11.5px; color:#b91c1c; font-weight:700;"><b>• Hạn giải trình (+10 ngày):</b> ${r.han_giai_trinh} ${isOd ? '<span class="badge badge-pending" style="font-size:10px; padding:1px 4px;">HẾT HẠN</span>' : ''}</div>` : ''}
            ${r.viec_da_thuc_hien ? `<div style="font-size:11.5px; color:#475569;">• ${r.viec_da_thuc_hien}</div>` : ''}
          </td>
          <td style="text-align:center;">
            ${isOd ? '<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:800;">⏰ Quá hạn TB</span>' : statusBadge(r.tinh_trang_xu_ly)}
          </td>
          <td style="text-align:center;">
            <button class="btn btn-primary" style="padding:4px 9px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">✍️ Cập nhật</button>
          </td>
        </tr>
      `;
      }).join('');
    }"""

new_dash_recent = """    if (displayList.length === 0) {
      tbodyRecent.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:25px; color:#64748b;">Chưa có dữ liệu hồ sơ rủi ro.</td></tr>`;
    } else {
      tbodyRecent.innerHTML = displayList.map(r => {
        const isOd = isRecordOverdue(r);
        return `
        <tr class="${rowColorClass(r.tinh_trang_xu_ly)} ${isOd ? 'row-overdue' : ''}">
          <td style="white-space:nowrap;">
            <b style="color:#0f172a; font-size:13px;">${escapeHtml(r.mst || '-')}</b>
          </td>
          <td>
            <span style="font-size:12px; font-weight:600; color:#1e293b;">${escapeHtml(r.ten_cong_ty || '')}</span>
          </td>
          <td>
            <b style="color:#1e40af; font-size:12px;">${escapeHtml(r.so_ky_hieu_vb || '-')}</b><br>
            <small style="color:#64748b;">Ngày đến: ${escapeHtml(r.ngay_vb_den || '-')}</small>
            ${r.so_den_vb ? `<div style="font-size:11px; color:#334155;">Số đến: <b>${escapeHtml(r.so_den_vb)}</b></div>` : ''}
            ${r.attachment_name ? `<div style="margin-top:3px;"><a href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" style="font-size:11px; color:#2563eb; font-weight:600; text-decoration:none;">📎 ${escapeHtml(r.attachment_name)}</a></div>` : `<div style="margin-top:3px;"><button class="btn btn-quick-attach" onclick="triggerQuickUploadCvrr(${r.id}, '${escapeHtml(r.mst||'')}', '${escapeHtml(r.ngay_vb_den||r.ngay_thang_vb||'')}', '${escapeHtml(r.so_ky_hieu_vb||'')}')" title="Đính kèm tệp Công văn rủi ro (PDF)">+ 📎 Đính kèm CVRR</button></div>`}
          </td>
          <td>
            <div style="font-size:12px; font-weight:700; color:#0f172a;">👤 ${escapeHtml(r.can_bo_xu_ly || 'Chưa phân công')}</div>
          </td>
          <td>
            ${r.so_thong_bao ? `<div style="font-size:11.5px; color:#5b21b6;"><b>• Số TB:</b> ${escapeHtml(r.so_thong_bao)} ${r.ngay_thong_bao ? `(${escapeHtml(r.ngay_thong_bao)})` : ''}</div>` : ''}
            ${r.han_giai_trinh ? `<div style="font-size:11.5px; color:#b91c1c; font-weight:700;"><b>• Hạn giải trình (+10 ngày):</b> ${escapeHtml(r.han_giai_trinh)} ${isOd ? '<span class="badge badge-pending" style="font-size:10px; padding:1px 4px;">HẾT HẠN</span>' : ''}</div>` : ''}
            ${r.viec_da_thuc_hien ? `<div style="font-size:11.5px; color:#475569;">• ${escapeHtml(r.viec_da_thuc_hien)}</div>` : ''}
          </td>
          <td style="text-align:center;">
            ${isOd ? '<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:800;">⏰ Quá hạn TB</span>' : statusBadge(r.tinh_trang_xu_ly)}
          </td>
          <td style="text-align:center;">
            <button class="btn btn-primary" style="padding:4px 9px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">✍️ Cập nhật</button>
          </td>
        </tr>
      `;
      }).join('');
    }"""

if old_dash_recent in js_text:
    js_text = js_text.replace(old_dash_recent, new_dash_recent, 1)
    print("2B. Da cap nhat renderDashboard")
else:
    print("Warning: old_dash_recent khong tim thay")

# C. renderDsrrTable
old_dsrr_tbody = """  if (sorted.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:35px; color:#64748b; font-size:13px;">
      🔍 Không tìm thấy hồ sơ nào khớp với từ khóa "<b>${rawQ}</b>" hoặc bộ lọc hiện tại.<br>
      <button class="btn btn-outline" style="margin-top:10px;" onclick="resetDsrrFilters()">Xóa bộ lọc để xem lại tất cả</button>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = sorted.map(r => {
    const isOd = isRecordOverdue(r);
    return `
    <tr class="${rowColorClass(r.tinh_trang_xu_ly)} ${isOd ? 'row-overdue' : ''}">
      <td>
        <span style="color:#64748b; font-size:11px;">STT #${r.id}</span><br>
        <b style="color:#1e40af; font-size:13px;">${highlightKeywords(r.so_ky_hieu_vb || '-', searchTerms)}</b><br>
        <small style="color:#475569;">Ngày văn bản: ${r.ngay_thang_vb || '-'}<br>Ngày đến: ${r.ngay_vb_den || '-'}</small>
        ${r.so_den_vb ? `<div style="font-size:11px; color:#0f172a; margin-top:2px;">Số đến: <b>${highlightKeywords(r.so_den_vb, searchTerms)}</b></div>` : ''}
      </td>
      <td>
        <b style="color:#0f172a; font-size:13.5px;">${highlightKeywords(r.mst || 'Chưa rõ MST', searchTerms)}</b><br>
        <span style="font-weight:600; color:#1e293b;">${highlightKeywords(r.ten_cong_ty || '', searchTerms)}</span>
        ${r.noi_gui ? `<div style="font-size:11px; color:#64748b; margin-top:3px;">Nơi gửi: ${highlightKeywords(r.noi_gui, searchTerms)}</div>` : ''}
      </td>
      <td>
        ${isOd ? '<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:800;">⏰ Quá hạn TB</span>' : statusBadge(r.tinh_trang_xu_ly)}<br>
        <div style="font-weight:700; color:#0f172a; margin-top:5px;">👤 ${highlightKeywords(r.can_bo_xu_ly || 'Chưa phân công', searchTerms)}</div>
      </td>
      <td>
        <code style="color:#dc2626; font-weight:900; font-size:13px;">${highlightKeywords(r.mst_rui_ro || '-', searchTerms)}</code><br>
        <span style="font-size:12px;">${highlightKeywords(r.ten_cty_rui_ro || '', searchTerms)}</span>
      </td>
      <td>
        ${r.viec_da_thuc_hien ? `<div><b style="color:#1e40af;">• Đã thực hiện:</b> ${highlightKeywords(r.viec_da_thuc_hien, searchTerms)}</div>` : ''}
        ${r.so_thong_bao ? `<div style="font-size:11.5px; color:#5b21b6;"><b>• Số thông báo:</b> ${highlightKeywords(r.so_thong_bao, searchTerms)} ${r.ngay_thong_bao ? `(${r.ngay_thong_bao})` : ''}</div>` : ''}
        ${r.han_giai_trinh ? `<div style="font-size:11.5px; color:#b91c1c; font-weight:700;"><b>• Hạn giải trình (+10 ngày):</b> ${highlightKeywords(r.han_giai_trinh, searchTerms)} ${isOd ? '<span class="badge badge-pending" style="font-size:10px; padding:1px 4px;">HẾT HẠN</span>' : ''}</div>` : ''}
        ${r.ghi_chu ? `<div><b style="color:#475569;">• Công văn giải trình:</b> ${highlightKeywords(r.ghi_chu, searchTerms)}</div>` : ''}
        ${r.nnt_giai_trinh ? `<div style="margin-top:3px;"><b style="color:#059669;">• Nội dung giải trình:</b> ${highlightKeywords(r.nnt_giai_trinh, searchTerms)}</div>` : ''}
        ${r.de_xuat_xu_ly ? `<div style="margin-top:2px; color:#b45309;">• Đề xuất xử lý:</b> ${highlightKeywords(r.de_xuat_xu_ly, searchTerms)}</div>` : ''}
        ${r.ket_qua_kiem_tra_phong_b ? `<div style="margin-top:2px; color:#6d28d9;">• Phòng Kiểm tra:</b> ${highlightKeywords(r.ket_qua_kiem_tra_phong_b, searchTerms)}</div>` : ''}
      </td>
      <td>${formatInvoiceSummaryPills(r)}</td>
      <td>
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#eff6ff; color:#1e40af; border-color:#bfdbfe;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Công văn cảnh báo rủi ro">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : ''}
        ${r.tbgt_pdf_name ? `<a class="badge-pdf" style="background:#f5f3ff; color:#6b21a8; border-color:#ddd6fe;" href="/api/attachment?name=${encodeURIComponent(r.tbgt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Thông báo giải trình">📋 ${highlightKeywords(r.tbgt_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.result_pdf_name ? `<a class="badge-pdf" style="background:#ecfdf5; color:#065f46; border-color:#a7f3d0;" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Văn bản giải trình NNT">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.bblv_pdf_name ? `<a class="badge-pdf" style="background:#f0fdf4; color:#166534; border-color:#bbf7d0;" href="/api/attachment?name=${encodeURIComponent(r.bblv_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Biên bản làm việc">🤝 ${highlightKeywords(r.bblv_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.pkt_pdf_name ? `<a class="badge-pdf" style="background:#faf5ff; color:#581c87; border-color:#e9d5ff;" href="/api/attachment?name=${encodeURIComponent(r.pkt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Phản hồi Phòng Kiểm tra">🏢 ${highlightKeywords(r.pkt_pdf_name, searchTerms)}</a><br>` : ''}
        <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
          <button class="btn ${isKt ? 'btn-outline' : 'btn-primary'}" style="padding:4px 8px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">
            ${isKt ? '👁️ Xem' : '✍️ Cập nhật'}
          </button>
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px; border-color:#3b82f6; color:#1d4ed8; font-weight:700;" onclick="downloadRecordBundleZip(${r.id})" title="Gom trọn bộ file CVRR, TBGT, GTDN, BBLV, PKT tải về file ZIP">
            📦 ZIP
          </button>
          ${(!isKt && r.tinh_trang_xu_ly !== 'Đã xử lý') ? `
            <button class="btn btn-warning-subtle" style="padding:4px 7px; font-size:11.5px; display:inline-flex; align-items:center; gap:3px;" onclick="openRowOutlookReminder(${r.id})" title="Mở Microsoft Outlook gửi email đôn đốc xử lý hồ sơ này">
              📧 Nhắc
            </button>
          ` : ''}
        </div>
      </td>
    </tr>
  `;
  }).join('');"""

new_dsrr_tbody = """  if (sorted.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:35px; color:#64748b; font-size:13px;">
      🔍 Không tìm thấy hồ sơ nào khớp với từ khóa "<b>${rawQ}</b>" hoặc bộ lọc hiện tại.<br>
      <button class="btn btn-outline" style="margin-top:10px;" onclick="resetDsrrFilters()">Xóa bộ lọc để xem lại tất cả</button>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = sorted.map(r => {
    const isOd = isRecordOverdue(r);
    return `
    <tr class="${rowColorClass(r.tinh_trang_xu_ly)} ${isOd ? 'row-overdue' : ''}">
      <td>
        <span style="color:#64748b; font-size:11px;">STT #${r.id}</span><br>
        <b style="color:#1e40af; font-size:13px;">${highlightKeywords(r.so_ky_hieu_vb || '-', searchTerms)}</b><br>
        <small style="color:#475569;">Ngày văn bản: ${r.ngay_thang_vb || '-'}<br>Ngày đến: ${r.ngay_vb_den || '-'}</small>
        ${r.so_den_vb ? `<div style="font-size:11px; color:#0f172a; margin-top:2px;">Số đến: <b>${highlightKeywords(r.so_den_vb, searchTerms)}</b></div>` : ''}
      </td>
      <td style="white-space:nowrap;">
        <b style="color:#0f172a; font-size:13.5px;">${highlightKeywords(r.mst || 'Chưa rõ MST', searchTerms)}</b>
      </td>
      <td>
        <span style="font-weight:600; color:#1e293b;">${highlightKeywords(r.ten_cong_ty || '', searchTerms)}</span>
        ${r.noi_gui ? `<div style="font-size:11px; color:#64748b; margin-top:3px;">Nơi gửi: ${highlightKeywords(r.noi_gui, searchTerms)}</div>` : ''}
      </td>
      <td>
        ${isOd ? '<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:800;">⏰ Quá hạn TB</span>' : statusBadge(r.tinh_trang_xu_ly)}<br>
        <div style="font-weight:700; color:#0f172a; margin-top:5px;">👤 ${highlightKeywords(r.can_bo_xu_ly || 'Chưa phân công', searchTerms)}</div>
      </td>
      <td>
        <code style="color:#dc2626; font-weight:900; font-size:13px;">${highlightKeywords(r.mst_rui_ro || '-', searchTerms)}</code><br>
        <span style="font-size:12px;">${highlightKeywords(r.ten_cty_rui_ro || '', searchTerms)}</span>
      </td>
      <td>
        ${r.viec_da_thuc_hien ? `<div><b style="color:#1e40af;">• Đã thực hiện:</b> ${highlightKeywords(r.viec_da_thuc_hien, searchTerms)}</div>` : ''}
        ${r.so_thong_bao ? `<div style="font-size:11.5px; color:#5b21b6;"><b>• Số thông báo:</b> ${highlightKeywords(r.so_thong_bao, searchTerms)} ${r.ngay_thong_bao ? `(${r.ngay_thong_bao})` : ''}</div>` : ''}
        ${r.han_giai_trinh ? `<div style="font-size:11.5px; color:#b91c1c; font-weight:700;"><b>• Hạn giải trình (+10 ngày):</b> ${highlightKeywords(r.han_giai_trinh, searchTerms)} ${isOd ? '<span class="badge badge-pending" style="font-size:10px; padding:1px 4px;">HẾT HẠN</span>' : ''}</div>` : ''}
        ${r.ghi_chu ? `<div><b style="color:#475569;">• Công văn giải trình:</b> ${highlightKeywords(r.ghi_chu, searchTerms)}</div>` : ''}
        ${r.nnt_giai_trinh ? `<div style="margin-top:3px;"><b style="color:#059669;">• Nội dung giải trình:</b> ${highlightKeywords(r.nnt_giai_trinh, searchTerms)}</div>` : ''}
        ${r.de_xuat_xu_ly ? `<div style="margin-top:2px; color:#b45309;">• Đề xuất xử lý:</b> ${highlightKeywords(r.de_xuat_xu_ly, searchTerms)}</div>` : ''}
        ${r.ket_qua_kiem_tra_phong_b ? `<div style="margin-top:2px; color:#6d28d9;">• Phòng Kiểm tra:</b> ${highlightKeywords(r.ket_qua_kiem_tra_phong_b, searchTerms)}</div>` : ''}
      </td>
      <td>${formatInvoiceSummaryPills(r)}</td>
      <td>
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#eff6ff; color:#1e40af; border-color:#bfdbfe;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Công văn cảnh báo rủi ro">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : `<button class="btn btn-quick-attach" style="margin-bottom:4px;" onclick="triggerQuickUploadCvrr(${r.id}, '${escapeHtml(r.mst||'')}', '${escapeHtml(r.ngay_vb_den||r.ngay_thang_vb||'')}', '${escapeHtml(r.so_ky_hieu_vb||'')}')" title="Đính kèm tệp Công văn rủi ro (PDF)">+ 📎 Đính kèm CVRR</button><br>`}
        ${r.tbgt_pdf_name ? `<a class="badge-pdf" style="background:#f5f3ff; color:#6b21a8; border-color:#ddd6fe;" href="/api/attachment?name=${encodeURIComponent(r.tbgt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Thông báo giải trình">📋 ${highlightKeywords(r.tbgt_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.result_pdf_name ? `<a class="badge-pdf" style="background:#ecfdf5; color:#065f46; border-color:#a7f3d0;" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Văn bản giải trình NNT">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.bblv_pdf_name ? `<a class="badge-pdf" style="background:#f0fdf4; color:#166534; border-color:#bbf7d0;" href="/api/attachment?name=${encodeURIComponent(r.bblv_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Biên bản làm việc">🤝 ${highlightKeywords(r.bblv_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.pkt_pdf_name ? `<a class="badge-pdf" style="background:#faf5ff; color:#581c87; border-color:#e9d5ff;" href="/api/attachment?name=${encodeURIComponent(r.pkt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Phản hồi Phòng Kiểm tra">🏢 ${highlightKeywords(r.pkt_pdf_name, searchTerms)}</a><br>` : ''}
        <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
          <button class="btn ${isKt ? 'btn-outline' : 'btn-primary'}" style="padding:4px 8px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">
            ${isKt ? '👁️ Xem' : '✍️ Cập nhật'}
          </button>
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px; border-color:#3b82f6; color:#1d4ed8; font-weight:700;" onclick="downloadRecordBundleZip(${r.id})" title="Gom trọn bộ file CVRR, TBGT, GTDN, BBLV, PKT tải về file ZIP">
            📦 ZIP
          </button>
          ${(!isKt && r.tinh_trang_xu_ly !== 'Đã xử lý') ? `
            <button class="btn btn-warning-subtle" style="padding:4px 7px; font-size:11.5px; display:inline-flex; align-items:center; gap:3px;" onclick="openRowOutlookReminder(${r.id})" title="Mở Microsoft Outlook gửi email đôn đốc xử lý hồ sơ này">
              📧 Nhắc
            </button>
          ` : ''}
        </div>
      </td>
    </tr>
  `;
  }).join('');"""

if old_dsrr_tbody in js_text:
    js_text = js_text.replace(old_dsrr_tbody, new_dsrr_tbody, 1)
    print("2C. Da cap nhat renderDsrrTable")
else:
    print("Warning: old_dsrr_tbody khong tim thay")

# D. executeInspectorSearch
old_inspect_tbody = """  if (sorted.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:35px; color:#64748b;">
      🔍 Không tìm thấy kết quả nào khớp với từ khóa "<b>${rawQ}</b>" hoặc tiêu chí lọc hiện tại.<br>
      <button class="btn btn-outline" style="margin-top:10px;" onclick="resetInspectFilters()">Đặt lại bộ lọc tra cứu</button>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = sorted.map(r => {
    const isOd = isRecordOverdue(r);
    return `
    <tr class="${rowColorClass(r.tinh_trang_xu_ly)} ${isOd ? 'row-overdue' : ''}">
      <td style="text-align:center; font-weight:700; color:#64748b;">#${r.id}</td>
      <td>
        <b style="font-size:13.5px; color:#0f172a;">${highlightKeywords(r.mst || '-', searchTerms)}</b><br>
        <span style="font-weight:600; color:#1e293b;">${highlightKeywords(r.ten_cong_ty || '', searchTerms)}</span>
      </td>
      <td>
        <code style="color:#dc2626; font-weight:900; font-size:13px;">${highlightKeywords(r.mst_rui_ro || '', searchTerms)}</code><br>
        <small style="color:#475569;">${highlightKeywords(r.ten_cty_rui_ro || '', searchTerms)}</small>
      </td>
      <td>
        <b style="color:#1e40af;">${highlightKeywords(r.so_ky_hieu_vb || '', searchTerms)}</b><br>
        <small>Ngày đến: ${r.ngay_vb_den || r.ngay_thang_vb || '-'}<br>${highlightKeywords(r.noi_gui || '', searchTerms)}</small>
      </td>
      <td>
        ${isOd ? '<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:800;">⏰ Quá hạn TB</span>' : statusBadge(r.tinh_trang_xu_ly)}<br>
        <small style="font-weight:700; color:#0f172a; margin-top:4px; display:inline-block;">👤 ${highlightKeywords(r.can_bo_xu_ly || 'Chưa phân công', searchTerms)}</small>
      </td>
      <td>
        ${r.viec_da_thuc_hien ? `<div><b>• Đã thực hiện:</b> ${highlightKeywords(r.viec_da_thuc_hien, searchTerms)}</div>` : ''}
        ${r.so_thong_bao ? `<div style="font-size:11.5px; color:#5b21b6;"><b>• Số thông báo:</b> ${highlightKeywords(r.so_thong_bao, searchTerms)} ${r.ngay_thong_bao ? `(${r.ngay_thong_bao})` : ''}</div>` : ''}
        ${r.han_giai_trinh ? `<div style="font-size:11.5px; color:#b91c1c; font-weight:700;"><b>• Hạn giải trình (+10 ngày):</b> ${highlightKeywords(r.han_giai_trinh, searchTerms)} ${isOd ? '<span class="badge badge-pending" style="font-size:10px; padding:1px 4px;">HẾT HẠN</span>' : ''}</div>` : ''}
        ${r.nnt_giai_trinh ? `<div><b>• Nội dung giải trình:</b> ${highlightKeywords(r.nnt_giai_trinh, searchTerms)}</div>` : ''}
        ${r.de_xuat_xu_ly ? `<div style="color:#b45309;"><b>• Đề xuất xử lý:</b> ${highlightKeywords(r.de_xuat_xu_ly, searchTerms)}</div>` : ''}
        <div style="margin-top:4px;">${formatInvoiceSummaryPills(r)}</div>
      </td>
      <td>
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#eff6ff; color:#1e40af; border-color:#bfdbfe;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Công văn cảnh báo rủi ro">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : ''}
        ${r.tbgt_pdf_name ? `<a class="badge-pdf" style="background:#f5f3ff; color:#6b21a8; border-color:#ddd6fe;" href="/api/attachment?name=${encodeURIComponent(r.tbgt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Thông báo giải trình">📋 ${highlightKeywords(r.tbgt_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.result_pdf_name ? `<a class="badge-pdf" style="background:#ecfdf5; color:#065f46; border-color:#a7f3d0;" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Văn bản giải trình NNT">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.bblv_pdf_name ? `<a class="badge-pdf" style="background:#f0fdf4; color:#166534; border-color:#bbf7d0;" href="/api/attachment?name=${encodeURIComponent(r.bblv_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Biên bản làm việc">🤝 ${highlightKeywords(r.bblv_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.pkt_pdf_name ? `<a class="badge-pdf" style="background:#faf5ff; color:#581c87; border-color:#e9d5ff;" href="/api/attachment?name=${encodeURIComponent(r.pkt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Phản hồi Phòng Kiểm tra">🏢 ${highlightKeywords(r.pkt_pdf_name, searchTerms)}</a><br>` : ''}
        <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">👁️ Xem</button>
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px; border-color:#3b82f6; color:#1d4ed8; font-weight:700;" onclick="downloadRecordBundleZip(${r.id})" title="Gom trọn bộ file CVRR, TBGT, GTDN, BBLV, PKT tải về file ZIP">📦 Tải ZIP</button>
        </div>
      </td>
    </tr>
  `;
  }).join('');"""

new_inspect_tbody = """  if (sorted.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:35px; color:#64748b;">
      🔍 Không tìm thấy kết quả nào khớp với từ khóa "<b>${rawQ}</b>" hoặc tiêu chí lọc hiện tại.<br>
      <button class="btn btn-outline" style="margin-top:10px;" onclick="resetInspectFilters()">Đặt lại bộ lọc tra cứu</button>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = sorted.map(r => {
    const isOd = isRecordOverdue(r);
    return `
    <tr class="${rowColorClass(r.tinh_trang_xu_ly)} ${isOd ? 'row-overdue' : ''}">
      <td style="text-align:center; font-weight:700; color:#64748b;">#${r.id}</td>
      <td style="white-space:nowrap;">
        <b style="font-size:13.5px; color:#0f172a;">${highlightKeywords(r.mst || '-', searchTerms)}</b>
      </td>
      <td>
        <span style="font-weight:600; color:#1e293b;">${highlightKeywords(r.ten_cong_ty || '', searchTerms)}</span>
      </td>
      <td>
        <code style="color:#dc2626; font-weight:900; font-size:13px;">${highlightKeywords(r.mst_rui_ro || '', searchTerms)}</code><br>
        <small style="color:#475569;">${highlightKeywords(r.ten_cty_rui_ro || '', searchTerms)}</small>
      </td>
      <td>
        <b style="color:#1e40af;">${highlightKeywords(r.so_ky_hieu_vb || '', searchTerms)}</b><br>
        <small>Ngày đến: ${r.ngay_vb_den || r.ngay_thang_vb || '-'}<br>${highlightKeywords(r.noi_gui || '', searchTerms)}</small>
      </td>
      <td>
        ${isOd ? '<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:800;">⏰ Quá hạn TB</span>' : statusBadge(r.tinh_trang_xu_ly)}<br>
        <small style="font-weight:700; color:#0f172a; margin-top:4px; display:inline-block;">👤 ${highlightKeywords(r.can_bo_xu_ly || 'Chưa phân công', searchTerms)}</small>
      </td>
      <td>
        ${r.viec_da_thuc_hien ? `<div><b>• Đã thực hiện:</b> ${highlightKeywords(r.viec_da_thuc_hien, searchTerms)}</div>` : ''}
        ${r.so_thong_bao ? `<div style="font-size:11.5px; color:#5b21b6;"><b>• Số thông báo:</b> ${highlightKeywords(r.so_thong_bao, searchTerms)} ${r.ngay_thong_bao ? `(${r.ngay_thong_bao})` : ''}</div>` : ''}
        ${r.han_giai_trinh ? `<div style="font-size:11.5px; color:#b91c1c; font-weight:700;"><b>• Hạn giải trình (+10 ngày):</b> ${highlightKeywords(r.han_giai_trinh, searchTerms)} ${isOd ? '<span class="badge badge-pending" style="font-size:10px; padding:1px 4px;">HẾT HẠN</span>' : ''}</div>` : ''}
        ${r.nnt_giai_trinh ? `<div><b>• Nội dung giải trình:</b> ${highlightKeywords(r.nnt_giai_trinh, searchTerms)}</div>` : ''}
        ${r.de_xuat_xu_ly ? `<div style="color:#b45309;"><b>• Đề xuất xử lý:</b> ${highlightKeywords(r.de_xuat_xu_ly, searchTerms)}</div>` : ''}
        <div style="margin-top:4px;">${formatInvoiceSummaryPills(r)}</div>
      </td>
      <td>
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#eff6ff; color:#1e40af; border-color:#bfdbfe;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Công văn cảnh báo rủi ro">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : `<button class="btn btn-quick-attach" style="margin-bottom:4px;" onclick="triggerQuickUploadCvrr(${r.id}, '${escapeHtml(r.mst||'')}', '${escapeHtml(r.ngay_vb_den||r.ngay_thang_vb||'')}', '${escapeHtml(r.so_ky_hieu_vb||'')}')" title="Đính kèm tệp Công văn rủi ro (PDF)">+ 📎 Đính kèm CVRR</button><br>`}
        ${r.tbgt_pdf_name ? `<a class="badge-pdf" style="background:#f5f3ff; color:#6b21a8; border-color:#ddd6fe;" href="/api/attachment?name=${encodeURIComponent(r.tbgt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Thông báo giải trình">📋 ${highlightKeywords(r.tbgt_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.result_pdf_name ? `<a class="badge-pdf" style="background:#ecfdf5; color:#065f46; border-color:#a7f3d0;" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Văn bản giải trình NNT">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.bblv_pdf_name ? `<a class="badge-pdf" style="background:#f0fdf4; color:#166534; border-color:#bbf7d0;" href="/api/attachment?name=${encodeURIComponent(r.bblv_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Biên bản làm việc">🤝 ${highlightKeywords(r.bblv_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.pkt_pdf_name ? `<a class="badge-pdf" style="background:#faf5ff; color:#581c87; border-color:#e9d5ff;" href="/api/attachment?name=${encodeURIComponent(r.pkt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Phản hồi Phòng Kiểm tra">🏢 ${highlightKeywords(r.pkt_pdf_name, searchTerms)}</a><br>` : ''}
        <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">👁️ Xem</button>
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px; border-color:#3b82f6; color:#1d4ed8; font-weight:700;" onclick="downloadRecordBundleZip(${r.id})" title="Gom trọn bộ file CVRR, TBGT, GTDN, BBLV, PKT tải về file ZIP">📦 Tải ZIP</button>
        </div>
      </td>
    </tr>
  `;
  }).join('');"""

if old_inspect_tbody in js_text:
    js_text = js_text.replace(old_inspect_tbody, new_inspect_tbody, 1)
    print("2D. Da cap nhat executeInspectorSearch")
else:
    print("Warning: old_inspect_tbody khong tim thay")

# E. renderReminderTableRows
old_reminder_tbody = """  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:30px; color:#64748b; font-size:13px;">
      Không có hồ sơ nào thỏa mãn điều kiện lọc.
    </td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((r, idx) => {
    let badgeClass = 'urgency-badge-normal';
    if (r.urgency === 'critical') badgeClass = 'urgency-badge-critical';
    else if (r.urgency === 'warning') badgeClass = 'urgency-badge-warning';
    else if (r.urgency === 'attention') badgeClass = 'urgency-badge-attention';

    const safeMailto = (r.mailto_url || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
    const safeOfficer = (r.can_bo_xu_ly || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
    const safeEmail = (r.officer_email || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
    const safeMst = (r.mst || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");

    return `
      <tr class="${r.is_overdue ? 'row-overdue' : ''}">
        <td style="text-align:center; font-weight:700; color:#64748b;">${idx + 1}</td>
        <td>
          <div style="font-weight:800; color:#0f172a;">👤 ${r.can_bo_xu_ly || 'Chưa phân công'}</div>
          ${r.officer_email ? `<a href="mailto:${r.officer_email}" style="color:#2563eb; font-size:11.5px; font-weight:600; text-decoration:none;">✉️ ${r.officer_email}</a>` : '<span style="color:#dc2626; font-size:11.5px;">Chưa có email</span>'}
        </td>
        <td>
          <code style="color:#0f172a; font-weight:800; font-size:13px;">${r.mst || '-'}</code><br>
          <span style="font-weight:600; color:#1e293b; font-size:12.5px;">${r.ten_cong_ty || 'Chưa cập nhật tên'}</span>
        </td>"""

new_reminder_tbody = """  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:30px; color:#64748b; font-size:13px;">
      Không có hồ sơ nào thỏa mãn điều kiện lọc.
    </td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((r, idx) => {
    let badgeClass = 'urgency-badge-normal';
    if (r.urgency === 'critical') badgeClass = 'urgency-badge-critical';
    else if (r.urgency === 'warning') badgeClass = 'urgency-badge-warning';
    else if (r.urgency === 'attention') badgeClass = 'urgency-badge-attention';

    const safeMailto = (r.mailto_url || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
    const safeOfficer = (r.can_bo_xu_ly || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
    const safeEmail = (r.officer_email || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
    const safeMst = (r.mst || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");

    return `
      <tr class="${r.is_overdue ? 'row-overdue' : ''}">
        <td style="text-align:center; font-weight:700; color:#64748b;">${idx + 1}</td>
        <td>
          <div style="font-weight:800; color:#0f172a;">👤 ${escapeHtml(r.can_bo_xu_ly || 'Chưa phân công')}</div>
          ${r.officer_email ? `<a href="mailto:${escapeHtml(r.officer_email)}" style="color:#2563eb; font-size:11.5px; font-weight:600; text-decoration:none;">✉️ ${escapeHtml(r.officer_email)}</a>` : '<span style="color:#dc2626; font-size:11.5px;">Chưa có email</span>'}
        </td>
        <td style="white-space:nowrap;">
          <code style="color:#0f172a; font-weight:800; font-size:13px;">${escapeHtml(r.mst || '-')}</code>
        </td>
        <td>
          <span style="font-weight:600; color:#1e293b; font-size:12.5px;">${escapeHtml(r.ten_cong_ty || 'Chưa cập nhật tên')}</span>
        </td>"""

if old_reminder_tbody in js_text:
    js_text = js_text.replace(old_reminder_tbody, new_reminder_tbody, 1)
    print("2E. Da cap nhat renderReminderTableRows")
else:
    print("Warning: old_reminder_tbody khong tim thay")

# F. openDsrrModal - doc attachment_name
old_open_modal_res_pdf = """    // File PDF kết quả giải trình (GTDN)
    document.getElementById('md_result_pdf').value = r.result_pdf_name || '';"""

new_open_modal_res_pdf = """    // File Công văn rủi ro ban đầu (CVRR)
    const cvrrVal = r.attachment_name || '';
    if (document.getElementById('md_attachment_name')) document.getElementById('md_attachment_name').value = cvrrVal;
    const boxCvrr = document.getElementById('md_cvrr_attached_box');
    const linkCvrr = document.getElementById('md_cvrr_attached_link');
    if (cvrrVal && boxCvrr && linkCvrr) {
      linkCvrr.innerText = cvrrVal;
      linkCvrr.href = `/api/attachment?name=${encodeURIComponent(cvrrVal)}&officer=${encodeURIComponent(STATE.officerName)}`;
      boxCvrr.style.display = 'flex';
    } else if (boxCvrr) {
      boxCvrr.style.display = 'none';
      if (linkCvrr) { linkCvrr.innerText = ''; linkCvrr.href = '#'; }
    }

    // File PDF kết quả giải trình (GTDN)
    document.getElementById('md_result_pdf').value = r.result_pdf_name || '';"""

if old_open_modal_res_pdf in js_text:
    js_text = js_text.replace(old_open_modal_res_pdf, new_open_modal_res_pdf, 1)
    print("2F. Da cap nhat openDsrrModal")
else:
    print("Warning: old_open_modal_res_pdf khong tim thay")

# G. saveDsrrUpdate - gui attachment_name
old_save_dsrr = """    mst_rui_ro: document.getElementById('md_mst_rr').value,
    ten_cty_rui_ro: document.getElementById('md_ten_cty_rr').value,
    result_pdf_name: document.getElementById('md_result_pdf')?.value || '',"""

new_save_dsrr = """    mst_rui_ro: document.getElementById('md_mst_rr').value,
    ten_cty_rui_ro: document.getElementById('md_ten_cty_rr').value,
    attachment_name: document.getElementById('md_attachment_name')?.value || '',
    result_pdf_name: document.getElementById('md_result_pdf')?.value || '',"""

if old_save_dsrr in js_text:
    js_text = js_text.replace(old_save_dsrr, new_save_dsrr, 1)
    print("2G. Da cap nhat saveDsrrUpdate")
else:
    print("Warning: old_save_dsrr khong tim thay")

# H. Bo sung clearAttachedCvrrPdf, handleUploadCvrrPdf, triggerQuickUploadCvrr, onGlobalCvrrFileSelected
functions_to_add = """
// ==================== QUẢN LÝ ĐÍNH KÈM TỆP CÔNG VĂN RỦI RO (CVRR) ====================

function clearAttachedCvrrPdf() {
  const el = document.getElementById('md_attachment_name');
  if (el) el.value = '';
  const fi = document.getElementById('md_upload_cvrr_pdf');
  if (fi) fi.value = '';
  const box = document.getElementById('md_cvrr_attached_box');
  if (box) box.style.display = 'none';
  const link = document.getElementById('md_cvrr_attached_link');
  if (link) { link.innerText = ''; link.href = '#'; }
}

async function handleUploadCvrrPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang lưu Công văn rủi ro: ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mst = document.getElementById('md_mst')?.value || '';
  const id = Number(document.getElementById('md_id')?.value || 0);
  const rec = STATE.dsrrList.find(x => x.id === id);
  const dateVal = rec?.ngay_vb_den || rec?.ngay_thang_vb || '';
  const soVb = rec?.so_ky_hieu_vb || 'CVRR';

  try {
    const res = await fetch('/api/ingest/pdf', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        filename: file.name,
        file_b64: b64,
        doc_type: 'CVRR',
        mst: mst,
        date: dateVal,
        extra_info: soVb
      })
    });
    const out = await res.json();
    if (out.stored_name) {
      if (document.getElementById('md_attachment_name')) {
        document.getElementById('md_attachment_name').value = out.stored_name;
      }
      const box = document.getElementById('md_cvrr_attached_box');
      const link = document.getElementById('md_cvrr_attached_link');
      if (link) {
        link.innerText = out.stored_name;
        link.href = `/api/attachment?name=${encodeURIComponent(out.stored_name)}&officer=${encodeURIComponent(STATE.officerName)}`;
      }
      if (box) box.style.display = 'flex';

      // Neu co id ho so, cap nhat luon vao CSDL
      if (id) {
        await fetch('/api/dsrr/attach_cvrr', {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({
            id: id,
            attachment_name: out.stored_name,
            officer_name: STATE.officerName
          })
        });
      }

      showToast(`Đã lưu Công văn rủi ro: ${out.stored_name}`, 'success');
      await refreshData();
    } else {
      showToast('Lỗi lưu file Công văn rủi ro!', 'error');
    }
  } catch (err) {
    console.error('Lỗi upload CVRR:', err);
    showToast(`Lỗi: ${err.message}`, 'error');
  }
}

let CURRENT_QUICK_CVRR_TARGET = null;

function triggerQuickUploadCvrr(recId, mst, dateVal, extraInfo) {
  CURRENT_QUICK_CVRR_TARGET = { id: recId, mst: mst, dateVal: dateVal, extraInfo: extraInfo };
  const fi = document.getElementById('globalCvrrFileInput');
  if (fi) {
    fi.value = '';
    fi.click();
  }
}

async function onGlobalCvrrFileSelected(input) {
  if (!input.files || !input.files[0] || !CURRENT_QUICK_CVRR_TARGET) return;
  const file = input.files[0];
  const target = CURRENT_QUICK_CVRR_TARGET;
  CURRENT_QUICK_CVRR_TARGET = null;

  showToast(`Đang tải tệp CVRR cho hồ sơ #${target.id}: ${file.name}...`, 'info');
  try {
    const b64 = await fileToBase64(file);
    const res = await fetch('/api/ingest/pdf', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        filename: file.name,
        file_b64: b64,
        doc_type: 'CVRR',
        mst: target.mst || '',
        date: target.dateVal || '',
        extra_info: target.extraInfo || 'CVRR'
      })
    });
    const out = await res.json();
    if (!out.stored_name) {
      showToast('Không thể lưu file CVRR!', 'error');
      return;
    }

    const attRes = await fetch('/api/dsrr/attach_cvrr', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        id: target.id,
        attachment_name: out.stored_name,
        officer_name: STATE.officerName
      })
    });
    const attData = await attRes.json();
    if (attData.ok) {
      showToast(`Đã đính kèm CVRR thành công: ${out.stored_name}`, 'success');
      await refreshData();
    } else {
      showToast('Đã lưu file nhưng không thể liên kết hồ sơ!', 'warning');
    }
  } catch (err) {
    console.error('Lỗi tải tệp CVRR:', err);
    showToast(`Lỗi đính kèm: ${err.message}`, 'error');
  }
}
"""

if "function triggerQuickUploadCvrr" not in js_text:
    js_text += "\n" + functions_to_add
    print("2H. Da them cac ham CVRR vao app.js")

js_file.write_text(js_text, encoding="utf-8")
print("Hoan tat cap nhat thanh cong!")
