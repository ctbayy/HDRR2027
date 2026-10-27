import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('app/static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

start_marker = '  // 3. Render Biểu đồ thanh ngang phân bổ Cán bộ'
end_marker = 'function renderKpiFilters() {'

idx1 = js.find(start_marker)
idx2 = js.find(end_marker)

assert idx1 != -1 and idx2 != -1, f"Markers not found: {idx1}, {idx2}"

fixed_code = '''  // 3. Render Biểu đồ thanh ngang phân bổ Cán bộ
  const barsWrap = document.getElementById('dashOfficerBars');
  if (barsWrap) {
    const officers = Object.keys(officerMap).sort((a, b) => officerMap[b].total - officerMap[a].total);
    if (officers.length === 0) {
      barsWrap.innerHTML = `<div style="text-align:center; padding:30px; color:#64748b;">Chưa có dữ liệu phân công cán bộ thuế.</div>`;
    } else {
      barsWrap.innerHTML = officers.map(o => {
        const item = officerMap[o];
        const isMe = o.toLowerCase() === (STATE.officerName || '').toLowerCase();
        const oTotal = item.total || 1;
        const pDone = Math.round((item.done / oTotal) * 100);
        const doingInTime = Math.max(0, item.doing - item.overdue);
        const pDoing = Math.round((doingInTime / oTotal) * 100);
        const pOverdue = Math.round((item.overdue / oTotal) * 100);
        const pPending = Math.max(0, 100 - pDone - pDoing - pOverdue);

        return `
          <div class="officer-bar-item" data-officer="${encodeURIComponent(o)}" onclick="actionFilterOfficerDsrr(decodeURIComponent(this.dataset.officer))" style="cursor:pointer;" title="Bấm để xem danh sách hồ sơ của ${o}">
            <div class="officer-bar-meta">
              <div class="officer-bar-name">
                <span>👤 <b>${o}</b></span>
                ${isMe ? '<span class="badge" style="background:#2563eb; color:#fff; font-size:10px;">Bạn</span>' : ''}
                <span class="badge ${pDone === 100 ? 'badge-done' : (pDone > 0 ? 'badge-doing' : 'badge-pending')}" style="font-size:10.5px; padding:1px 6px;">
                  ${pDone}% hoàn thành
                </span>
              </div>
              <div class="officer-bar-stat-tags">
                <span class="stat-pill stat-pill-total" title="Tổng số hồ sơ">Tổng: <b>${item.total}</b></span>
                <span class="stat-pill stat-pill-done" title="Đã hoàn thành">🟢 <b>${item.done}</b> xong</span>
                <span class="stat-pill stat-pill-doing" title="Đang giải trình trong hạn">🟡 <b>${doingInTime}</b></span>
                ${item.overdue > 0 ? `<span class="stat-pill stat-pill-overdue" title="Quá hạn Thông báo giải trình">⏰ <b>${item.overdue}</b> chậm</span>` : ''}
                <span class="stat-pill stat-pill-pending" title="Chưa xử lý">⚪ <b>${item.pending}</b></span>
              </div>
            </div>
            <div class="bar-stacked-track">
              <div class="bar-seg bar-seg-done" style="width:${pDone}%;" title="Đã xong: ${item.done} hồ sơ (${pDone}%)">
                ${pDone >= 14 ? `<span class="seg-label">${item.done}</span>` : ''}
              </div>
              <div class="bar-seg bar-seg-doing" style="width:${pDoing}%;" title="Đang làm trong hạn: ${doingInTime} hồ sơ (${pDoing}%)">
                ${pDoing >= 14 ? `<span class="seg-label">${doingInTime}</span>` : ''}
              </div>
              <div class="bar-seg bar-seg-overdue" style="width:${pOverdue}%;" title="Quá hạn thông báo: ${item.overdue} hồ sơ (${pOverdue}%)">
                ${pOverdue >= 14 ? `<span class="seg-label">${item.overdue}</span>` : ''}
              </div>
              <div class="bar-seg bar-seg-pending" style="width:${pPending}%;" title="Chưa làm: ${item.pending} hồ sơ (${pPending}%)">
                ${pPending >= 14 ? `<span class="seg-label">${item.pending}</span>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  }
}

function toggleMaxOfficerBars() {
  const card = document.getElementById('cardOfficerBars');
  const btn = document.getElementById('btnToggleMaxOfficerCard');
  if (!card) return;
  const isMax = card.classList.toggle('maximized-card');
  if (btn) {
    btn.innerHTML = isMax ? '✖ Thu gọn' : '⛶ Mở rộng khung';
    btn.className = isMax ? 'btn btn-primary' : 'btn btn-outline';
  }
}

function renderDashboard() {
  const total = STATE.dsrrList.length;
  const countPending = STATE.dsrrList.filter(x => x.tinh_trang_xu_ly === 'Chưa xử lý').length;
  const countDoing = STATE.dsrrList.filter(x => x.tinh_trang_xu_ly === 'Đang xử lý').length;
  const countDone = STATE.dsrrList.filter(x => x.tinh_trang_xu_ly === 'Đã xử lý').length;
  const countHasPdf = STATE.dsrrList.filter(x => x.result_pdf_name || x.attachment_name).length;
  const overdueCount = calculateOverdueCount();
  const donePercent = total > 0 ? Math.round((countDone / total) * 100) : 0;

  // 1. Ngày tháng hôm nay
  const today = new Date();
  const dd = String(today.getDate()).padStart(2, '0');
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const yyyy = today.getFullYear();
  const todayElem = document.getElementById('dashTodayDate');
  if (todayElem) todayElem.innerText = `${dd}/${mm}/${yyyy}`;

  // 2. Cập nhật thẻ chỉ số KPI
  const elTotal = document.getElementById('dashKpiTotal');
  if (elTotal) elTotal.innerText = fmtNum(total);
  const elTotalSub = document.getElementById('dashKpiTotalSub');
  if (elTotalSub) elTotalSub.innerText = `${STATE.thList.length} văn bản cảnh báo tiếp nhận`;

  const elPending = document.getElementById('dashKpiPending');
  if (elPending) elPending.innerText = fmtNum(countPending);
  const elPendingSub = document.getElementById('dashKpiPendingSub');
  if (elPendingSub) {
    const pendingRate = total > 0 ? Math.round((countPending / total) * 100) : 0;
    elPendingSub.innerText = `Chiếm ${pendingRate}% tổng số hồ sơ`;
  }

  const elDoing = document.getElementById('dashKpiDoing');
  if (elDoing) elDoing.innerText = fmtNum(countDoing);
  const elDoingSub = document.getElementById('dashKpiDoingSub');
  if (elDoingSub) {
    const doingRate = total > 0 ? Math.round((countDoing / total) * 100) : 0;
    elDoingSub.innerText = `Chiếm ${doingRate}% đang giải trình`;
  }

  const elDone = document.getElementById('dashKpiDone');
  if (elDone) elDone.innerText = fmtNum(countDone);
  const elDoneRate = document.getElementById('dashKpiDoneRate');
  if (elDoneRate) elDoneRate.innerText = `Tỷ lệ hoàn thành: ${donePercent}%`;

  const elOverdue = document.getElementById('dashKpiOverdue');
  if (elOverdue) elOverdue.innerText = fmtNum(overdueCount);
  const elOverdueBadge = document.getElementById('dashOverdueBadge');
  if (elOverdueBadge) elOverdueBadge.innerText = `${overdueCount} hồ sơ quá hạn TB`;

  const elHasPdf = document.getElementById('dashKpiHasPdf');
  if (elHasPdf) elHasPdf.innerText = fmtNum(countHasPdf);

  // 3. Render 4 nhóm hóa đơn trên Dashboard
  let ckHd = 0, ckGt = 0, ckVat = 0;
  let dcHd = 0, dcCp = 0, dcKt = 0, dcTndn = 0, dcGtgt = 0;
  let kkkHd = 0, kkkGt = 0, kkkVat = 0;
  let knHd = 0, knGt = 0, knVat = 0;

  STATE.dsrrList.forEach(r => {
    ckHd += Number(r.cam_ket_so_hd || 0); ckGt += Number(r.cam_ket_gia_tri || 0); ckVat += Number(r.cam_ket_thue_gtgt || 0);
    dcHd += Number(r.dieu_chinh_so_hd || 0); dcCp += Number(r.dieu_chinh_giam_chi_phi || 0); dcKt += Number(r.dieu_chinh_giam_khau_tru || 0);
    dcTndn += Number(r.dieu_chinh_thue_tndn || 0); dcGtgt += Number(r.dieu_chinh_thue_gtgt || 0);
    kkkHd += Number(r.khong_kk_so_hd || 0); kkkGt += Number(r.khong_kk_gia_tri || 0); kkkVat += Number(r.khong_kk_thue_gtgt || 0);
    knHd += Number(r.khong_nhan_so_hd || 0); knGt += Number(r.khong_nhan_gia_tri || 0); knVat += Number(r.khong_nhan_thue_gtgt || 0);
  });

  const dashInvStrip = document.getElementById('dashInvoiceGroupStrip');
  if (dashInvStrip) {
    const dcSubExtra = (dcTndn > 0 || dcGtgt > 0)
      ? `<div style="font-size:11px; margin-top:3px; color:#065f46;">Thuế nộp: TNDN <b>${fmtNum(dcTndn)}đ</b> • GTGT <b>${fmtNum(dcGtgt)}đ</b></div>`
      : '';
    dashInvStrip.innerHTML = `
      <div class="inv-box inv-g1">
        <div class="ig-head" style="color:#1d4ed8;">1. Cam kết có mua bán hàng hóa, dịch vụ</div>
        <div class="ig-stat">${fmtNum(ckHd)} hóa đơn</div>
        <div class="ig-sub">Chưa thuế: <b>${fmtNum(ckGt)}đ</b> • Thuế GTGT: <b>${fmtNum(ckVat)}đ</b></div>
      </div>
      <div class="inv-box inv-g2">
        <div class="ig-head" style="color:#059669;">2. Doanh nghiệp tự điều chỉnh giảm thuế</div>
        <div class="ig-stat">${fmtNum(dcHd)} hóa đơn</div>
        <div class="ig-sub">Giảm chi phí: <b>${fmtNum(dcCp)}đ</b> • Giảm khấu trừ: <b>${fmtNum(dcKt)}đ</b></div>
        ${dcSubExtra}
      </div>
      <div class="inv-box inv-g3">
        <div class="ig-head" style="color:#7c3aed;">3. Có nhận hóa đơn nhưng không kê khai thuế</div>
        <div class="ig-stat">${fmtNum(kkkHd)} hóa đơn</div>
        <div class="ig-sub">Chưa thuế: <b>${fmtNum(kkkGt)}đ</b> • Thuế GTGT: <b>${fmtNum(kkkVat)}đ</b></div>
      </div>
      <div class="inv-box inv-g4">
        <div class="ig-head" style="color:#ea580c;">4. Không nhận được hóa đơn, không kê khai</div>
        <div class="ig-stat">${fmtNum(knHd)} hóa đơn</div>
        <div class="ig-sub">Chưa thuế: <b>${fmtNum(knGt)}đ</b> • Thuế GTGT: <b>${fmtNum(knVat)}đ</b></div>
      </div>
    `;
  }

  // 4. Render Bảng Phân công & Tiến độ Cán bộ thuế
  const officerMap = {};
  STATE.dsrrList.forEach(r => {
    const off = r.can_bo_xu_ly || 'Chưa phân công';
    if (!officerMap[off]) {
      officerMap[off] = { total: 0, done: 0, doing: 0, pending: 0, overdue: 0 };
    }
    officerMap[off].total++;
    if (r.tinh_trang_xu_ly === 'Đã xử lý') {
      officerMap[off].done++;
    } else if (r.tinh_trang_xu_ly === 'Đang xử lý') {
      officerMap[off].doing++;
    } else {
      officerMap[off].pending++;
    }

    if (isRecordOverdue(r)) {
      officerMap[off].overdue++;
    }
  });

  // Gọi vẽ biểu đồ trực quan (Donut & Horizontal bars)
  renderDashboardCharts(total, countDone, countDoing, countPending, overdueCount, officerMap);

  // 5. Render Danh sách Hồ sơ Cần chú ý / Gần đây (Full khung 6 cột)
  const tbodyRecent = document.getElementById('tbodyDashRecent');
  if (tbodyRecent) {
    const urgentList = STATE.dsrrList
      .filter(x => x.tinh_trang_xu_ly !== 'Đã xử lý')
      .slice(0, 8);
    const displayList = urgentList.length ? urgentList : STATE.dsrrList.slice(0, 8);

    if (displayList.length === 0) {
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
    }
  }
}

'''

js = js[:idx1] + fixed_code + js[idx2:]

with open('app/static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)

print("app/static/app.js fixed successfully!")
