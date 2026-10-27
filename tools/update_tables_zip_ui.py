with open('app/static/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update renderDsrrTable action column
old_dsrr_actions = """      <td>
        ${r.result_pdf_name ? `<a class="badge-pdf" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#dbeafe; color:#1e40af; border-color:#93c5fd;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : ''}
        <button class="btn ${isKt ? 'btn-outline' : 'btn-primary'}" style="padding:5px 10px; font-size:12px; margin-top:3px;" onclick="openDsrrModal(${r.id})">
          ${isKt ? '👁️ Xem chi tiết' : '✍️ Cập nhật kết quả'}
        </button>
        ${(!isKt && r.tinh_trang_xu_ly !== 'Đã xử lý') ? `
          <button class="btn btn-warning-subtle" style="padding:4px 8px; font-size:11.5px; margin-top:3px; display:inline-flex; align-items:center; gap:3px;" onclick="openRowOutlookReminder(${r.id})" title="Mở Microsoft Outlook gửi email đôn đốc xử lý hồ sơ này">
            📧 Nhắc cán bộ
          </button>
        ` : ''}
      </td>"""

new_dsrr_actions = """      <td>
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
      </td>"""

assert old_dsrr_actions in code, "old_dsrr_actions not found"
code = code.replace(old_dsrr_actions, new_dsrr_actions, 1)

# 2. Update renderInspectResult action column
old_inspect_actions = """      <td>
        ${r.result_pdf_name ? `<a class="badge-pdf" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#dbeafe; color:#1e40af;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : ''}
        <button class="btn btn-outline" style="padding:4px 9px; font-size:11.5px; margin-top:3px;" onclick="openDsrrModal(${r.id})">👁️ Xem đầy đủ</button>
      </td>"""

new_inspect_actions = """      <td>
        ${r.attachment_name ? `<a class="badge-pdf" style="background:#eff6ff; color:#1e40af; border-color:#bfdbfe;" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Công văn cảnh báo rủi ro">📎 ${highlightKeywords(r.attachment_name, searchTerms)}</a><br>` : ''}
        ${r.tbgt_pdf_name ? `<a class="badge-pdf" style="background:#f5f3ff; color:#6b21a8; border-color:#ddd6fe;" href="/api/attachment?name=${encodeURIComponent(r.tbgt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Thông báo giải trình">📋 ${highlightKeywords(r.tbgt_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.result_pdf_name ? `<a class="badge-pdf" style="background:#ecfdf5; color:#065f46; border-color:#a7f3d0;" href="/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Văn bản giải trình NNT">📄 ${highlightKeywords(r.result_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.bblv_pdf_name ? `<a class="badge-pdf" style="background:#f0fdf4; color:#166534; border-color:#bbf7d0;" href="/api/attachment?name=${encodeURIComponent(r.bblv_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Biên bản làm việc">🤝 ${highlightKeywords(r.bblv_pdf_name, searchTerms)}</a><br>` : ''}
        ${r.pkt_pdf_name ? `<a class="badge-pdf" style="background:#faf5ff; color:#581c87; border-color:#e9d5ff;" href="/api/attachment?name=${encodeURIComponent(r.pkt_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank" title="Phản hồi Phòng Kiểm tra">🏢 ${highlightKeywords(r.pkt_pdf_name, searchTerms)}</a><br>` : ''}
        <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px;" onclick="openDsrrModal(${r.id})">👁️ Xem</button>
          <button class="btn btn-outline" style="padding:4px 8px; font-size:11.5px; border-color:#3b82f6; color:#1d4ed8; font-weight:700;" onclick="downloadRecordBundleZip(${r.id})" title="Gom trọn bộ file CVRR, TBGT, GTDN, BBLV, PKT tải về file ZIP">📦 Tải ZIP</button>
        </div>
      </td>"""

assert old_inspect_actions in code, "old_inspect_actions not found"
code = code.replace(old_inspect_actions, new_inspect_actions, 1)

with open('app/static/app.js', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated table action buttons with ZIP download successfully!")
