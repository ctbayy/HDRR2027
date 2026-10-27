/**
 * Hệ thống Quản lý Hóa đơn Rủi ro Nội bộ (HDRR) - V4.1 UI Engine
 * Cập nhật:
 *   1. Đảo thứ tự: Đưa Tiếp nhận TH_Rủi ro lên Bước 1 (Đầu vào bắt buộc).
 *   2. Tự động đồng bộ và kế thừa toàn bộ thông tin từ Bước 1 sang Bước 2 (DSRR 2026) khi có liên quan Phòng QLDN1.
 *   3. Nâng cấp tìm kiếm đa trường chuyên sâu (Deep Search): tìm xuyên suốt nội dung giải trình, số thông báo, kết quả cập nhật, file PDF, số tiền...
 */

let STATE = {
  machineAuth: {},
  officerName: '',
  deptRole: 'PHONG_QLHT',
  thList: [],
  dsrrList: [],
  sharePdfFiles: [],
  statusFilter: 'ALL',
  ownerPin: '',
  adminPin: sessionStorage.getItem('hdrr_admin_token') || '',
  adminToken: sessionStorage.getItem('hdrr_admin_token') || '',
  isAdminAuthenticated: false,
  auditLogs: [],
  auditSearchTimer: null,
  pendingAttachment: { name: '', sha256: '' },
  dsrrSort: { col: 'id', dir: 'desc' },
  inspectSort: { col: 'id', dir: 'desc' },
  inspectActiveTab: 'dsrr'
};

// ==================== TIỆN ÍCH HỖ TRỢ ====================

function fmtNum(n) {
  return Number(n || 0).toLocaleString('vi-VN');
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function parseNum(val) {
  if (typeof val === 'number') return val;
  const clean = String(val || '').replace(/[^0-9.-]/g, '');
  return parseFloat(clean) || 0;
}

function highlightKeywords(text, terms) {
  if (!text || !terms || !terms.length) return text || '';
  let escaped = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  for (const t of terms) {
    if (!t || !t.trim()) continue;
    const cleanT = t.trim();
    const re = new RegExp(`(${cleanT.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    escaped = escaped.replace(re, '<mark class="search-highlight">$1</mark>');
  }
  return escaped;
}

function removeVietnameseTones(str) {
  if (!str) return '';
  str = String(str).toLowerCase();
  str = str.replace(/à|á|ạ|ả|ã|â|ầ|ấ|ậ|ẩ|ẫ|ă|ằ|ắ|ặ|ẳ|ẵ/g, 'a');
  str = str.replace(/è|é|ẹ|ẻ|ẽ|ê|ề|ế|ệ|ể|ễ/g, 'e');
  str = str.replace(/ì|í|ị|ỉ|ĩ/g, 'i');
  str = str.replace(/ò|ó|ọ|ỏ|õ|ô|ồ|ố|ộ|ổ|ỗ|ơ|ờ|ớ|ợ|ở|ỡ/g, 'o');
  str = str.replace(/ù|ú|ụ|ủ|ũ|ư|ừ|ứ|ự|ử|ữ/g, 'u');
  str = str.replace(/ỳ|ý|ỵ|ỷ|ỹ/g, 'y');
  str = str.replace(/đ/g, 'd');
  str = str.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  return str;
}

function isRecordOverdue(r) {
  if (!r || r.tinh_trang_xu_ly === 'Đã xử lý') return false;
  // QUY TẮC MỚI: Chỉ tính chậm nếu theo mốc thời hạn ban hành thông báo giải trình (+10 ngày làm việc).
  // Các hồ sơ còn lại đưa vào trạng thái Chưa xử lý / Đang xử lý.
  if (!r.han_giai_trinh) return false;
  const parts = String(r.han_giai_trinh).trim().split(/[\/\-]/);
  if (parts.length < 3) return false;
  const dHan = new Date(parseInt(parts[2], 10), parseInt(parts[1], 10) - 1, parseInt(parts[0], 10), 23, 59, 59);
  if (isNaN(dHan.getTime())) return false;
  return new Date() > dHan;
}

function calculateOverdueCount() {
  return STATE.dsrrList.filter(isRecordOverdue).length;
}

function sortRecords(records, colKey, dir = 'asc') {
  const mult = dir === 'desc' ? -1 : 1;
  const parseDateMs = (s) => {
    if (!s) return 0;
    const p = String(s).trim().split(/[\/\-]/);
    if (p.length < 3) return 0;
    return new Date(parseInt(p[2], 10), parseInt(p[1], 10) - 1, parseInt(p[0], 10)).getTime() || 0;
  };

  return [...records].sort((a, b) => {
    let valA, valB;
    switch (colKey) {
      case 'id':
        valA = Number(a.id || 0);
        valB = Number(b.id || 0);
        return (valA - valB) * mult;
      case 'mst':
        valA = String(a.mst || '').toLowerCase();
        valB = String(b.mst || '').toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;
      case 'ten_cong_ty':
        valA = String(a.ten_cong_ty || '').toLowerCase();
        valB = String(b.ten_cong_ty || '').toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;
      case 'mst_rr':
        valA = ((a.mst_rui_ro || '') + ' ' + (a.ten_cty_rui_ro || '')).toLowerCase();
        valB = ((b.mst_rui_ro || '') + ' ' + (b.ten_cty_rui_ro || '')).toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;
      case 'tinh_trang': {
        const order = { 'Chưa xử lý': 1, 'Đang xử lý': 2, 'Đã xử lý': 3 };
        const stA = order[a.tinh_trang_xu_ly] || 0;
        const stB = order[b.tinh_trang_xu_ly] || 0;
        if (stA !== stB) return (stA - stB) * mult;
        return (a.can_bo_xu_ly || '').localeCompare(b.can_bo_xu_ly || '', 'vi') * mult;
      }
      case 'han_gt':
        valA = parseDateMs(a.han_giai_trinh) || parseDateMs(a.ngay_vb_den) || 0;
        valB = parseDateMs(b.han_giai_trinh) || parseDateMs(b.ngay_vb_den) || 0;
        return (valA - valB) * mult;
      case 'ngay_vb_den':
        valA = parseDateMs(a.ngay_vb_den) || parseDateMs(a.ngay_thang_vb) || 0;
        valB = parseDateMs(b.ngay_vb_den) || parseDateMs(b.ngay_thang_vb) || 0;
        return (valA - valB) * mult;
      case 'so_tien': {
        const sumA = (Number(a.dieu_chinh_thue_tndn || 0) + Number(a.dieu_chinh_thue_gtgt || 0) +
                      Number(a.cam_ket_gia_tri || 0) + Number(a.cam_ket_thue_gtgt || 0) +
                      Number(a.dieu_chinh_giam_chi_phi || 0) + Number(a.dieu_chinh_giam_khau_tru || 0));
        const sumB = (Number(b.dieu_chinh_thue_tndn || 0) + Number(b.dieu_chinh_thue_gtgt || 0) +
                      Number(b.cam_ket_gia_tri || 0) + Number(b.cam_ket_thue_gtgt || 0) +
                      Number(b.dieu_chinh_giam_chi_phi || 0) + Number(b.dieu_chinh_giam_khau_tru || 0));
        return (sumA - sumB) * mult;
      }
      default:
        valA = String(a[colKey] || '').toLowerCase();
        valB = String(b[colKey] || '').toLowerCase();
        return valA.localeCompare(valB, 'vi', { numeric: true }) * mult;
    }
  });
}

function updateSortIcons(prefix, currentSort) {
  const icons = document.querySelectorAll(`[id^="${prefix}"]`);
  icons.forEach(el => {
    el.innerText = '↕';
    el.classList.remove('active');
  });
  const activeIcon = document.getElementById(`${prefix}${currentSort.col}`);
  if (activeIcon) {
    activeIcon.innerText = currentSort.dir === 'asc' ? '▲' : '▼';
    activeIcon.classList.add('active');
  }
}

function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icons = {
    info: 'ℹ️',
    success: '✅',
    warning: '⚠️',
    error: '❌'
  };
  toast.innerHTML = `<span>${icons[type] || '•'}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const res = String(reader.result || '');
      const idx = res.indexOf(',');
      resolve(idx >= 0 ? res.slice(idx + 1) : res);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function getDeptDisplayName() {
  return STATE.deptRole === 'PHONG_KT'
    ? 'Phòng Kiểm tra'
    : 'Phòng Quản lý Doanh nghiệp 1 / QLHTDN';
}

function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-Officer-Name': encodeURIComponent(STATE.officerName || STATE.machineAuth.matched_officer_name || ''),
    'X-Department': encodeURIComponent(getDeptDisplayName()),
    'X-Admin-Token': STATE.adminToken || '',
    'X-Owner-Pin': STATE.adminToken || STATE.ownerPin || '',
    'X-Admin-Pin': STATE.adminToken || STATE.adminPin || ''
  };
}

function updateCongVanPreview() {
  const kh = (document.getElementById('th_so_kh')?.value || '...').trim();
  const ng = (document.getElementById('th_ngay_vb')?.value || '...').trim();
  const cq = (document.getElementById('th_noi_gui')?.value || '...').trim();
  const prev = document.getElementById('th_cv_preview');
  if (prev) prev.value = `Công văn số ${kh} ngày ${ng} của ${cq}`;
}

// ==================== KHỞI TẠO ỨNG DỤNG ====================

async function initEngine() {
  const today = new Date();
  const dd = String(today.getDate()).padStart(2, '0');
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  document.getElementById('th_ngay_den').value = `${dd}/${mm}/${today.getFullYear()}`;
  updateCongVanPreview();

  try {
    const res = await fetch('/api/bootstrap');
    const data = await res.json();
    STATE.machineAuth = data.machine_identity || {};

    const savedName = localStorage.getItem('cqt_officer_name');
    const savedRole = localStorage.getItem('cqt_dept_role');
    const urlParams = new URLSearchParams(window.location.search);
    const pathName = window.location.pathname.toLowerCase();
    let forcedRole = urlParams.get('role') || '';
    if (pathName.includes('/kiemtra')) forcedRole = 'PHONG_KT';
    if (pathName.includes('/qlhtdn')) forcedRole = 'PHONG_QLHT';

    STATE.officerName = savedName || STATE.machineAuth.matched_officer_name || STATE.machineAuth.account_id || 'Công chức';
    STATE.deptRole = forcedRole || savedRole || 'PHONG_QLHT';

    document.getElementById('officerNameInput').value = STATE.officerName;
    document.getElementById('deptRoleSelect').value = STATE.deptRole;

    document.getElementById('machineIdentityChip').innerHTML =
      `Account máy: <b style="color:#38bdf8;">${STATE.machineAuth.domain_account || 'LOCAL'}</b><br>` +
      `Tên máy: <code>${STATE.machineAuth.workstation || 'Laptop'}</code> • IP: <code>${STATE.machineAuth.client_ip}</code>`;

    applyRoleVisibility();
    renderCornerAuthWidget();
    await refreshData();
    await checkAdminSession();
    renderCornerAuthWidget();
    checkSyncQueueStatus();
    setInterval(checkSyncQueueStatus, 8000);
  } catch (err) {
    showToast('Lỗi khi kết nối máy chủ: ' + err.message, 'error');
  }

  // Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDsrrModal();
      closeOutlookReminderModal();
      closeAdminLoginModal();
      closeChangePasswordModal();
      closeNntEditModal();
      closeNntImportModal();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      const modal = document.getElementById('dsrrModal');
      if (modal && modal.classList.contains('open')) {
        e.preventDefault();
        saveDsrrUpdate();
      }
    }
  });
}

function saveLocalProfile() {
  STATE.officerName = document.getElementById('officerNameInput').value.trim() || STATE.machineAuth.matched_officer_name;
  localStorage.setItem('cqt_officer_name', STATE.officerName);
  renderCornerAuthWidget();
  showToast(`Đã lưu hồ sơ công chức: ${STATE.officerName}`, 'info');
}

function onRoleChanged() {
  STATE.deptRole = document.getElementById('deptRoleSelect').value;
  localStorage.setItem('cqt_dept_role', STATE.deptRole);
  applyRoleVisibility();
  renderDsrrTable();
  renderCornerAuthWidget();
  showToast(`Đã chuyển sang vai trò: ${getDeptDisplayName()}`, 'info');
}

function applyRoleVisibility() {
  const badge = document.getElementById('activeRoleBadge');
  const isKt = STATE.deptRole === 'PHONG_KT';

  if (isKt) {
    badge.className = 'role-ribbon role-kt';
    badge.innerText = '🔍 Chế độ Tra cứu: Phòng Kiểm tra';
    document.getElementById('btnModTh').style.display = 'none';
    document.getElementById('navGroupQlhtLbl').innerText = 'Dữ liệu Kết quả Xử lý';
    switchModule('mod_dashboard', document.getElementById('btnModDashboard'), 'active-mod0');
  } else {
    badge.className = 'role-ribbon role-qlht';
    badge.innerText = '✍️ Chế độ Tiếp nhận & Xử lý: Phòng Quản lý Doanh nghiệp';
    document.getElementById('btnModTh').style.display = 'flex';
    document.getElementById('navGroupQlhtLbl').innerText = 'Nghiệp vụ Quản lý Doanh nghiệp';
    // Đưa Dashboard lên làm màn hình tổng quan mặc định khi vừa vào
    switchModule('mod_dashboard', document.getElementById('btnModDashboard'), 'active-mod0');
  }
}

function switchModule(modId, btn, activeClass) {
  document.querySelectorAll('.module-pane').forEach(el => el.classList.remove('active'));
  document.getElementById(modId).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(el => {
    el.classList.remove('active-mod0', 'active-mod1', 'active-mod2', 'active-mod3', 'active-mod4', 'active-mod5');
  });
  if (btn) btn.classList.add(activeClass || 'active-mod1');

  const titles = {
    mod_dashboard: 'Bảng Điều Khiển Trung Tâm & Tổng Hợp Dữ Liệu Hóa Đơn Rủi Ro',
    mod_th: 'Bước 1: Tiếp nhận Văn bản Cảnh báo Rủi ro',
    mod_dsrr: 'Bước 2: Theo dõi & Cập nhật Kết quả Xử lý Doanh nghiệp',
    mod_inspect: 'Bước 3: Tra cứu Chi tiết & Xem Tài liệu Kết quả (Phòng Kiểm tra)',
    mod_sharepdf: 'Bước 4: Kho Lưu trữ File PDF & Sao lưu Cơ sở dữ liệu',
    mod_admin: 'Bước 5: Quản trị Hệ thống, Tích hợp SAP & Nhật ký Lưu vết'
  };
  document.getElementById('moduleHeaderTitle').innerText = titles[modId] || '';
  if (modId === 'mod_dashboard') renderDashboard();
  if (modId === 'mod_inspect') executeInspectorSearch();

  if (modId === 'mod_admin') {
    loadAdminKpis();
    loadAdminNntList(1);
    loadSapConfigToUi();
  }
}

// ==================== CÁC NÚT THAO TÁC NHANH TRÊN DASHBOARD ====================

function actionGoToWarningInput() {
  switchModule('mod_th', document.getElementById('btnModTh'), 'active-mod2');
  setTimeout(() => {
    const inp = document.getElementById('th_so_kh');
    if (inp) {
      inp.focus();
      inp.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, 120);
}

function actionGoToDsrrUpdate(filter = '') {
  switchModule('mod_dsrr', document.getElementById('btnModDsrr'), 'active-mod1');
  if (filter) {
    setStatusFilter(filter);
  }
  setTimeout(() => {
    const inp = document.getElementById('filterDsrrInput');
    if (inp) {
      inp.focus();
      inp.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, 120);
}

function actionGoToAttachFile() {
  switchModule('mod_sharepdf', document.getElementById('btnModShare'), 'active-mod2');
}

function actionGoToInspect(query = '') {
  switchModule('mod_inspect', document.getElementById('btnModInspect'), 'active-mod3');
  if (query) {
    const inp = document.getElementById('inspectMstInput');
    if (inp) inp.value = query;
    executeInspectorSearch();
  }
  setTimeout(() => {
    const inp = document.getElementById('inspectMstInput');
    if (inp) {
      inp.focus();
      inp.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, 120);
}

function actionOpenReminder() {
  openOutlookReminderModal();
}

function actionFilterOfficerDsrr(officerName) {
  switchModule('mod_dsrr', document.getElementById('btnModDsrr'), 'active-mod1');
  const sel = document.getElementById('filterOfficerSelect');
  if (sel) {
    sel.value = officerName;
    renderDsrrTable();
  }
}

async function promptChangeSharePath() {
  const cur = document.getElementById('uncPathLabel').innerText;
  const next = prompt(
    'Nhập đường dẫn thư mục mạng LAN (hoặc gõ SIMULATE để dùng thư mục giả lập \\\\qng-pthieu10\\SharePdf trên Laptop):',
    cur || '\\\\qng-pthieu10\\SharePdf'
  );
  if (!next) return;
  const res = await fetch('/api/sharepdf/config', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ share_path: next })
  });
  const out = await res.json();
  showToast(out.message || 'Đã cập nhật đường dẫn', out.ok ? 'success' : 'error');
  await refreshData();
}

async function triggerManualBackup() {
  try {
    const res = await fetch('/api/backup/now', { method: 'POST', headers: getHeaders() });
    const out = await res.json();
    if (out.ok) {
      showToast('Đã tạo bản sao lưu CSDL thành công: ' + out.backup_file, 'success');
    } else {
      showToast('Không thể tạo sao lưu: ' + out.error, 'error');
    }
  } catch (e) {
    showToast('Lỗi khi yêu cầu sao lưu: ' + e.message, 'error');
  }
}

// ==================== TẢI & KẾT XUẤT DỮ LIỆU ====================

async function refreshData() {
  try {
    const res = await fetch('/api/data', { headers: getHeaders() });
    const data = await res.json();
    STATE.thList = data.th_rui_ro || [];
    STATE.dsrrList = data.dsrr_2026 || [];
    STATE.sharePdfFiles = data.sharepdf_files || [];

    const isSim = data.storage_mode === 'VIRTUAL_SIMULATION';
    document.getElementById('pdfCountLabel').innerHTML = isSim
      ? `<span style="color:#fbbf24; font-weight:700;">● Đang giả lập trên Laptop cá nhân</span><br>Ánh xạ: <b>${STATE.sharePdfFiles.length} file PDF</b> sẵn có`
      : `<span style="color:#34d399; font-weight:700;">● Đã kết nối LAN trực tiếp</span><br>Hiện có <b>${STATE.sharePdfFiles.length} file PDF</b> trong SharePdf`;

    const simBanner = document.getElementById('simulationBanner');
    if (simBanner) {
      simBanner.innerHTML = isSim
        ? `<b>💡 Chế độ Giả lập Laptop cá nhân đang bật:</b> Đường link <code>\\\\qng-pthieu10\\SharePdf</code> đang được ánh xạ tự động vào thư mục <code>${data.active_dir}</code> trên máy của bạn (đã tạo sẵn 3 file PDF mẫu để bạn bấm thử Quét & Mở xem ngay). Khi đem vào mạng cơ quan có máy <code>qng-pthieu10</code>, phần mềm sẽ tự nhận ổ mạng thật.`
        : `<b>✅ Đang kết nối trực tiếp ổ mạng nội bộ:</b> <code>${data.active_dir}</code>`;
    }

    const officers = Array.from(new Set(STATE.dsrrList.map(r => r.can_bo_xu_ly).filter(Boolean))).sort();
    const curOff = document.getElementById('filterOfficerSelect')?.value || '';
    if (document.getElementById('filterOfficerSelect')) {
      document.getElementById('filterOfficerSelect').innerHTML =
        `<option value="">-- Tất cả Cán bộ xử lý (${officers.length}) --</option>` +
        officers.map(o => `<option value="${o}" ${o === curOff ? 'selected' : ''}>${o}</option>`).join('');
    }

    const inspectOff = document.getElementById('inspectFilterOfficerSelect');
    if (inspectOff) {
      const curInspectOff = inspectOff.value;
      inspectOff.innerHTML =
        `<option value="">-- Tất cả Cán bộ xử lý (${officers.length}) --</option>` +
        officers.map(o => `<option value="${o}" ${o === curInspectOff ? 'selected' : ''}>${o}</option>`).join('');
    }

    const pdfOpts = `<option value="">-- Chọn file PDF trong \\\\qng-pthieu10\\SharePdf (${STATE.sharePdfFiles.length} file) --</option>` +
      STATE.sharePdfFiles.map(f => `<option value="${f.name}">${f.name} (${f.size_kb} KB)</option>`).join('');
    document.getElementById('selectExistingSharePdf').innerHTML = pdfOpts;
    const mdPickEl = document.getElementById('md_pick_sharepdf');
    if (mdPickEl) mdPickEl.innerHTML = pdfOpts;

    renderDashboard();
    renderKpiFilters();
    renderInvoiceGroupStrip();
    renderDsrrTable();
    renderThTable();
    renderSharePdfTable();
  } catch (err) {
    showToast('Lỗi tải dữ liệu: ' + err.message, 'error');
  }
}

function setStatusFilter(st) {
  STATE.statusFilter = st;
  renderKpiFilters();
  renderDsrrTable();
}

// ==================== BẢNG ĐIỀU KHIỂN TỔNG QUAN (DASHBOARD) ====================

function renderDashboardCharts(total, countDone, countDoing, countPending, overdueCount, officerMap) {
  // 1. Cập nhật Badge Tổng hồ sơ
  const totalBadge = document.getElementById('chartTotalBadge');
  if (totalBadge) totalBadge.innerText = `${fmtNum(total)} hồ sơ`;

  // 2. Tính toán & Vẽ SVG Donut Chart
  const svgDonut = document.getElementById('donutSvg');
  const legendDonut = document.getElementById('donutLegend');
  if (svgDonut && legendDonut) {
    const donePercent = total > 0 ? Math.round((countDone / total) * 100) : 0;
    const doingInTime = Math.max(0, countDoing - overdueCount);
    const pDoing = total > 0 ? Math.round((doingInTime / total) * 100) : 0;
    const pOverdue = total > 0 ? Math.round((overdueCount / total) * 100) : 0;
    const pPending = total > 0 ? Math.max(0, 100 - donePercent - pDoing - pOverdue) : 0;

    const r = 54;
    const cx = 80, cy = 80;
    const C = 2 * Math.PI * r; // ~339.292

    if (total === 0) {
      svgDonut.innerHTML = `
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#e2e8f0" stroke-width="22"></circle>
        <text x="${cx}" y="${cy + 5}" text-anchor="middle" font-size="13" font-weight="700" fill="#94a3b8">Chưa có số liệu</text>
      `;
      legendDonut.innerHTML = `<div style="color:#64748b; font-size:12px;">Hệ thống chưa có hồ sơ rủi ro nào.</div>`;
    } else {
      const segments = [
        { key: 'Đã xử lý', name: 'Đã hoàn thành', count: countDone, pct: donePercent, color: '#10b981', cls: 'legend-dot-done' },
        { key: 'Đang xử lý', name: 'Đang làm (trong hạn)', count: doingInTime, pct: pDoing, color: '#f59e0b', cls: 'legend-dot-doing' },
        { key: 'OVERDUE', name: 'Quá hạn Thông báo (+10 ngày)', count: overdueCount, pct: pOverdue, color: '#ef4444', cls: 'legend-dot-overdue' },
        { key: 'Chưa xử lý', name: 'Chưa xử lý (chưa có TB)', count: countPending, pct: pPending, color: '#94a3b8', cls: 'legend-dot-pending' }
      ];

      let currentOffset = 0;
      let circlesHtml = `
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#f1f5f9" stroke-width="22"></circle>
      `;

      segments.forEach(seg => {
        if (seg.count <= 0) return;
        const segLen = (seg.count / total) * C;
        circlesHtml += `
          <circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
            stroke="${seg.color}" stroke-width="22"
            stroke-dasharray="${segLen} ${C - segLen}"
            stroke-dashoffset="${-currentOffset}"
            transform="rotate(-90 ${cx} ${cy})">
          </circle>
        `;
        currentOffset += segLen;
      });

      circlesHtml += `
        <text x="${cx}" y="${cy - 4}" text-anchor="middle" font-size="22" font-weight="900" fill="#0f172a">${donePercent}%</text>
        <text x="${cx}" y="${cy + 15}" text-anchor="middle" font-size="11" font-weight="700" fill="#64748b">HOÀN THÀNH</text>
      `;

      svgDonut.innerHTML = circlesHtml;

      legendDonut.innerHTML = segments.map(s => `
        <div class="legend-item" onclick="setStatusFilter('${s.key}'); switchModule('mod_dsrr', document.getElementById('btnModDsrr'), 'active-mod1');" style="cursor:pointer;" title="Bấm để lọc theo trạng thái ${s.name}">
          <div class="legend-dot ${s.cls}"></div>
          <div class="legend-info">
            <span class="legend-name">${s.name}</span>
            <span class="legend-val"><b>${fmtNum(s.count)}</b> hồ sơ (${s.pct}%)</span>
          </div>
        </div>
      `).join('');
    }
  }

  // 3. Render Biểu đồ thanh ngang phân bổ Cán bộ
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
    }
  }
}

function renderKpiFilters() {
  const total = STATE.dsrrList.length;
  const countPending = STATE.dsrrList.filter(x => x.tinh_trang_xu_ly === 'Chưa xử lý').length;
  const countDoing = STATE.dsrrList.filter(x => x.tinh_trang_xu_ly === 'Đang xử lý').length;
  const countDone = STATE.dsrrList.filter(x => x.tinh_trang_xu_ly === 'Đã xử lý').length;
  const countHasPdf = STATE.dsrrList.filter(x => x.result_pdf_name || x.attachment_name).length;
  const overdueCount = calculateOverdueCount();

  const cards = [
    { key: 'ALL', cls: 'kpi-all', title: 'Tổng số hồ sơ rủi ro', num: total, desc: 'Bấm xem toàn bộ' },
    { key: 'Chưa xử lý', cls: 'kpi-pending', title: '🔴 Chưa xử lý', num: countPending, desc: 'Cần ban hành thông báo' },
    { key: 'Đang xử lý', cls: 'kpi-doing', title: '🟡 Đang xử lý', num: countDoing, desc: 'Đang theo dõi giải trình' },
    { key: 'OVERDUE', cls: 'kpi-overdue', title: '⏰ Quá hạn Thông báo', num: overdueCount, desc: 'Hết 10 ngày chưa giải trình' },
    { key: 'Đã xử lý', cls: 'kpi-done', title: '🟢 Đã xử lý', num: countDone, desc: 'Đã hoàn tất kết quả' },
    { key: 'HAS_PDF', cls: 'kpi-haspdf', title: '🟣 Có File PDF Kết quả', num: countHasPdf, desc: 'Đã lưu trong thư mục mạng' }
  ];

  document.getElementById('kpiFilterBar').innerHTML = cards.map(c => `
    <div class="kpi-pill ${c.cls} ${STATE.statusFilter === c.key ? 'active-filter' : ''}" onclick="setStatusFilter('${c.key}')">
      <div class="k-title">${c.title}</div>
      <div class="k-num">${fmtNum(c.num)}</div>
      <div class="k-desc">${c.desc}</div>
    </div>
  `).join('');

  const pill = document.getElementById('overdueCountPill');
  if (pill) pill.innerText = overdueCount;
}

function renderInvoiceGroupStrip() {
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

  const dcSubExtra = (dcTndn > 0 || dcGtgt > 0)
    ? `<div style="font-size:11px; margin-top:3px; color:#065f46;">Thuế nộp: TNDN <b>${fmtNum(dcTndn)}đ</b> • GTGT <b>${fmtNum(dcGtgt)}đ</b></div>`
    : '';

  document.getElementById('invoiceGroupStrip').innerHTML = `
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

function statusBadge(st) {
  if (st === 'Đã xử lý') return `<span class="badge badge-done">🟢 Đã xử lý</span>`;
  if (st === 'Đang xử lý') return `<span class="badge badge-doing">🟡 Đang xử lý</span>`;
  return `<span class="badge badge-pending">🔴 Chưa xử lý</span>`;
}

function rowColorClass(st) {
  if (st === 'Đã xử lý') return 'row-done';
  if (st === 'Đang xử lý') return 'row-doing';
  return 'row-pending';
}

function formatInvoiceSummaryPills(r) {
  const pills = [];
  if (Number(r.cam_ket_so_hd) > 0)
    pills.push(`<div class="inv-pill pill-g1">1. Cam kết mua bán: ${r.cam_ket_so_hd} hóa đơn • Tiền hàng: ${fmtNum(r.cam_ket_gia_tri)}đ (Thuế GTGT: ${fmtNum(r.cam_ket_thue_gtgt)}đ)</div>`);
  if (Number(r.dieu_chinh_so_hd) > 0 || Number(r.dieu_chinh_thue_tndn) > 0 || Number(r.dieu_chinh_thue_gtgt) > 0) {
    let tndnGtgtPart = '';
    if (Number(r.dieu_chinh_thue_tndn) > 0 || Number(r.dieu_chinh_thue_gtgt) > 0) {
      tndnGtgtPart = ` • Thuế nộp: TNDN ${fmtNum(r.dieu_chinh_thue_tndn)}đ / GTGT ${fmtNum(r.dieu_chinh_thue_gtgt)}đ`;
    }
    pills.push(`<div class="inv-pill pill-g2">2. Tự điều chỉnh: ${r.dieu_chinh_so_hd || 0} hóa đơn • Giảm chi phí: ${fmtNum(r.dieu_chinh_giam_chi_phi)}đ (Giảm khấu trừ: ${fmtNum(r.dieu_chinh_giam_khau_tru)}đ)${tndnGtgtPart}</div>`);
  }
  if (Number(r.khong_kk_so_hd) > 0)
    pills.push(`<div class="inv-pill pill-g3">3. Không kê khai: ${r.khong_kk_so_hd} hóa đơn • Tiền hàng: ${fmtNum(r.khong_kk_gia_tri)}đ</div>`);
  if (Number(r.khong_nhan_so_hd) > 0)
    pills.push(`<div class="inv-pill pill-g4">4. Không nhận hóa đơn: ${r.khong_nhan_so_hd} hóa đơn • Tiền hàng: ${fmtNum(r.khong_nhan_gia_tri)}đ</div>`);
  return pills.length ? pills.join('') : `<span style="color:#94a3b8; font-size:11.5px;">Chưa phát sinh số liệu hóa đơn</span>`;
}

// ==================== TÌM KIẾM CHI TIẾT & BỘ LỌC ĐA TRƯỜNG ====================

let searchTimer = null;
function debouncedRenderDsrrTable() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(renderDsrrTable, 160);
}

function clearDsrrSearch() {
  const input = document.getElementById('filterDsrrInput');
  if (input) input.value = '';
  const clearBtn = document.getElementById('btnClearDsrrSearch');
  if (clearBtn) clearBtn.style.display = 'none';
  renderDsrrTable();
}

function sortDsrrTable(colKey) {
  if (STATE.dsrrSort.col === colKey) {
    STATE.dsrrSort.dir = STATE.dsrrSort.dir === 'asc' ? 'desc' : 'asc';
  } else {
    STATE.dsrrSort.col = colKey;
    STATE.dsrrSort.dir = (colKey === 'id' || colKey === 'so_tien' || colKey === 'han_gt') ? 'desc' : 'asc';
  }
  updateSortIcons('sort_icon_dsrr_', STATE.dsrrSort);
  renderDsrrTable();
}

function resetDsrrFilters() {
  const input = document.getElementById('filterDsrrInput');
  if (input) input.value = '';
  const clearBtn = document.getElementById('btnClearDsrrSearch');
  if (clearBtn) clearBtn.style.display = 'none';

  const offSelect = document.getElementById('filterOfficerSelect');
  if (offSelect) offSelect.value = '';

  const groupSelect = document.getElementById('filterInvoiceGroupSelect');
  if (groupSelect) groupSelect.value = '';

  const noticeSelect = document.getElementById('filterNoticeSelect');
  if (noticeSelect) noticeSelect.value = '';

  const pdfSelect = document.getElementById('filterPdfSelect');
  if (pdfSelect) pdfSelect.value = '';

  STATE.statusFilter = 'ALL';
  STATE.dsrrSort = { col: 'id', dir: 'desc' };
  updateSortIcons('sort_icon_dsrr_', STATE.dsrrSort);

  renderKpiFilters();
  renderDsrrTable();
  showToast('Đã đặt lại toàn bộ bộ lọc và sắp xếp', 'info');
}

function renderDsrrTable() {
  const rawQ = (document.getElementById('filterDsrrInput')?.value || '').trim();
  const q = rawQ.toLowerCase();
  const clearBtn = document.getElementById('btnClearDsrrSearch');
  if (clearBtn) clearBtn.style.display = rawQ ? 'block' : 'none';

  const offFilter = document.getElementById('filterOfficerSelect')?.value || '';
  const invGroupFilter = document.getElementById('filterInvoiceGroupSelect')?.value || '';
  const noticeFilter = document.getElementById('filterNoticeSelect')?.value || '';
  const pdfFilter = document.getElementById('filterPdfSelect')?.value || '';
  const isKt = STATE.deptRole === 'PHONG_KT';

  const searchTerms = q.split(/\s+/).filter(Boolean);

  const filtered = STATE.dsrrList.filter(r => {
    // 1. Lọc theo thẻ KPI
    if (STATE.statusFilter === 'HAS_PDF' && !(r.result_pdf_name || r.attachment_name)) return false;
    if (STATE.statusFilter === 'OVERDUE' && !isRecordOverdue(r)) return false;
    if (STATE.statusFilter !== 'ALL' && STATE.statusFilter !== 'HAS_PDF' && STATE.statusFilter !== 'OVERDUE' && r.tinh_trang_xu_ly !== STATE.statusFilter) return false;

    // 2. Lọc theo Cán bộ
    if (offFilter && (r.can_bo_xu_ly || '') !== offFilter) return false;

    // 3. Lọc theo Nhóm Hóa đơn
    if (invGroupFilter === 'GROUP_1' && Number(r.cam_ket_so_hd || 0) <= 0) return false;
    if (invGroupFilter === 'GROUP_2' && (Number(r.dieu_chinh_so_hd || 0) <= 0 && Number(r.dieu_chinh_thue_tndn || 0) <= 0 && Number(r.dieu_chinh_thue_gtgt || 0) <= 0)) return false;
    if (invGroupFilter === 'GROUP_3' && Number(r.khong_kk_so_hd || 0) <= 0) return false;
    if (invGroupFilter === 'GROUP_4' && Number(r.khong_nhan_so_hd || 0) <= 0) return false;

    // 4. Lọc theo Thông báo giải trình
    if (noticeFilter === 'HAS_TB' && !(r.so_thong_bao || r.han_giai_trinh)) return false;
    if (noticeFilter === 'NO_TB' && (r.so_thong_bao || r.han_giai_trinh || r.tinh_trang_xu_ly === 'Đã xử lý')) return false;
    if (noticeFilter === 'OVERDUE' && !isRecordOverdue(r)) return false;

    // 5. Lọc theo Trạng thái PDF
    if (pdfFilter === 'HAS_RES_PDF' && !r.result_pdf_name) return false;
    if (pdfFilter === 'HAS_ATT_PDF' && !r.attachment_name) return false;
    if (pdfFilter === 'NO_PDF' && (r.result_pdf_name || r.attachment_name)) return false;

    if (!searchTerms.length) return true;

    // TÌM KIẾM SÂU ĐA TRƯỜNG CHI TIẾT (DEEP MULTI-FIELD SEARCH CẢ CÓ DẤU & KHÔNG DẤU)
    const targetPool = [
      r.mst,
      r.ten_cong_ty,
      r.can_bo_xu_ly,
      r.mst_rui_ro,
      r.ten_cty_rui_ro,
      r.so_ky_hieu_vb,
      r.so_den_vb,
      r.noi_gui,
      r.ngay_thang_vb,
      r.ngay_vb_den,
      r.lien_quan_cong_an,
      r.viec_da_thuc_hien,
      r.so_thong_bao,
      r.ngay_thong_bao,
      r.han_giai_trinh,
      r.viec_tiep_tuc,
      r.ghi_chu,
      r.nnt_giai_trinh,
      r.de_xuat_xu_ly,
      r.ket_qua_kiem_tra_phong_b,
      r.result_pdf_name,
      r.attachment_name,
      r.tinh_trang_xu_ly,
      String(r.cam_ket_gia_tri || ''),
      String(r.dieu_chinh_giam_chi_phi || ''),
      String(r.dieu_chinh_giam_khau_tru || ''),
      String(r.dieu_chinh_thue_tndn || ''),
      String(r.dieu_chinh_thue_gtgt || ''),
      fmtNum(r.cam_ket_gia_tri),
      fmtNum(r.dieu_chinh_giam_chi_phi),
      fmtNum(r.dieu_chinh_giam_khau_tru),
      fmtNum(r.dieu_chinh_thue_tndn),
      fmtNum(r.dieu_chinh_thue_gtgt)
    ].filter(Boolean).join(' ');

    const poolLower = targetPool.toLowerCase();
    const poolUnaccented = removeVietnameseTones(targetPool);

    return searchTerms.every(term => {
      const tLower = term.toLowerCase();
      const tUnaccented = removeVietnameseTones(term);
      return poolLower.includes(tLower) || poolUnaccented.includes(tUnaccented);
    });
  });

  // Sắp xếp dữ liệu theo cột và chiều hiện tại
  const sorted = sortRecords(filtered, STATE.dsrrSort.col, STATE.dsrrSort.dir);
  updateSortIcons('sort_icon_dsrr_', STATE.dsrrSort);

  // Cập nhật nhãn đếm kết quả
  const countBadge = document.getElementById('dsrrSearchCount');
  if (countBadge) {
    if (rawQ || offFilter || invGroupFilter || noticeFilter || pdfFilter || STATE.statusFilter !== 'ALL') {
      countBadge.className = 'badge badge-doing';
      countBadge.innerText = `Tìm thấy ${sorted.length} / ${STATE.dsrrList.length} hồ sơ`;
    } else {
      countBadge.className = 'badge badge-done';
      countBadge.innerText = `Hiển thị ${sorted.length} / ${STATE.dsrrList.length} hồ sơ`;
    }
  }

  const tbody = document.getElementById('tbodyDsrr');
  if (!tbody) return;

  if (sorted.length === 0) {
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
  }).join('');
}

function renderThTable() {
  const q = (document.getElementById('filterThInput')?.value || '').toLowerCase();
  const list = STATE.thList.filter(r =>
    !q ||
    (r.mst || '').toLowerCase().includes(q) ||
    (r.cong_van || '').toLowerCase().includes(q) ||
    (r.mst_lien_quan || '').toLowerCase().includes(q) ||
    (r.ve_viec || '').toLowerCase().includes(q)
  );

  const countBadge = document.getElementById('thCountBadge');
  if (countBadge) {
    countBadge.innerText = `Tổng cộng ${list.length} / ${STATE.thList.length} văn bản`;
  }

  const tbody = document.getElementById('tbodyThRuiRo');
  if (!tbody) return;

  const displayList = list.slice(0, 250);
  tbody.innerHTML = displayList.map(r => `
    <tr>
      <td>#${r.id}</td>
      <td><code style="color:#dc2626; font-weight:900; font-size:13px;">${r.mst}</code></td>
      <td>${r.ve_viec}</td>
      <td><b>${r.cong_van}</b></td>
      <td><b style="color:#059669; font-size:13px;">${r.mst_lien_quan || '-'}</b></td>
      <td>
        ${r.attachment_name ? `<a class="badge-pdf" href="/api/attachment?name=${encodeURIComponent(r.attachment_name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">📄 ${r.attachment_name}</a>` : '<small style="color:#94a3b8;">-</small>'}
      </td>
    </tr>
  `).join('');
}

function renderSharePdfTable() {
  const tbody = document.getElementById('tbodySharePdfFiles');
  if (!tbody) return;
  if (!STATE.sharePdfFiles.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#64748b; padding:25px;">Chưa có file .pdf nào trong thư mục SharePdf.</td></tr>`;
    return;
  }
  tbody.innerHTML = STATE.sharePdfFiles.map((f, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><b style="color:#5b21b6;">📄 ${f.name}</b></td>
      <td><code>${f.unc_full_path}</code></td>
      <td>${f.size_kb} KB</td>
      <td>${f.modified}</td>
      <td>
        <a class="btn btn-purple" style="padding:5px 10px; font-size:11.5px; text-decoration:none;" href="/api/attachment?name=${encodeURIComponent(f.name)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">Mở xem PDF</a>
      </td>
    </tr>
  `).join('');
}

// ==================== BƯỚC 1: TIẾP NHẬN CẢNH BÁO & ĐỒNG BỘ QLDN1 ====================

async function lookupMstLq(val) {
  const hint = document.getElementById('mstLqHint');
  const q = (val || '').trim();
  if (q.length < 8) {
    if (hint) hint.innerText = '';
    return;
  }
  try {
    const res = await fetch(`/api/nnt/lookup?mst=${encodeURIComponent(q)}`, { headers: getHeaders() });
    const info = await res.json();
    if (info.ten_nnt || info.can_bo_quan_ly) {
      if (hint) {
        hint.innerHTML = `✓ Doanh nghiệp thuộc cơ quan thuế quản lý: <b>${info.ten_nnt}</b> • Cán bộ phụ trách: <b>${info.can_bo_quan_ly || 'Phòng Quản lý doanh nghiệp'}</b> (Tự động cập nhật sang Bước 2)`;
      }
      const tenInput = document.getElementById('th_ten_lq');
      if (tenInput && !tenInput.value) tenInput.value = info.ten_nnt || '';
      const cbInput = document.getElementById('th_can_bo_lq');
      if (cbInput && !cbInput.value) cbInput.value = info.can_bo_quan_ly || '';
      document.getElementById('th_co_lq').checked = true;
      toggleQldn1Sync(true);
    } else {
      if (hint) {
        hint.innerText = 'Chưa có trong danh mục doanh nghiệp quản lý (vẫn tự động chuyển sang Bước 2 nếu đánh dấu chọn)';
      }
    }
  } catch (e) {
    console.error(e);
  }
}

function toggleQldn1Sync(checked) {
  const badge = document.getElementById('qldn1SyncStatusBadge');
  if (badge) {
    if (checked) {
      badge.className = 'badge-sync-ready';
      badge.innerText = '✓ Tự động đồng bộ sang Bước 2 (DSRR 2026)';
    } else {
      badge.className = 'badge badge-doing';
      badge.innerText = 'Chỉ lưu TH_Rủi ro (Không tạo DSRR 2026)';
    }
  }
}

async function submitNewWarning() {
  if (STATE.deptRole === 'PHONG_KT') {
    showToast('Chức năng tiếp nhận chỉ dành cho Phòng Quản lý Doanh nghiệp 1 / QLHTDN!', 'warning');
    return;
  }
  const mst_rr = document.getElementById('th_mst_rr').value.trim();
  const so_kh = document.getElementById('th_so_kh').value.trim();
  if (!mst_rr || !so_kh) {
    showToast('Vui lòng nhập tối thiểu Mã số thuế rủi ro và Số ký hiệu văn bản!', 'warning');
    return;
  }

  const coLq = document.getElementById('th_co_lq').checked;
  const payload = {
    mst_rui_ro: mst_rr,
    ten_cty_rui_ro: document.getElementById('th_ten_rr').value,
    ve_viec: document.getElementById('th_ve_viec').value,
    so_ky_hieu_vb: so_kh,
    ngay_thang_vb: document.getElementById('th_ngay_vb').value,
    noi_gui: document.getElementById('th_noi_gui').value,
    so_den_vb: document.getElementById('th_so_den').value,
    ngay_vb_den: document.getElementById('th_ngay_den').value,
    han_xu_ly: document.getElementById('th_han_xl').value,
    mst_lien_quan: document.getElementById('th_mst_lq').value.trim(),
    ten_cong_ty_lien_quan: document.getElementById('th_ten_lq').value.trim(),
    can_bo_xu_ly: document.getElementById('th_can_bo_lq').value.trim() || STATE.officerName,
    lien_quan_cong_an: document.getElementById('th_cong_an').value,
    co_lien_quan_truc_tiep: coLq,
    officer_name: STATE.officerName,
    attachment_name: document.getElementById('th_pdf_name').value || STATE.pendingAttachment.name,
    attachment_sha256: STATE.pendingAttachment.sha256
  };

  const res = await fetch('/api/th/create', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });
  const out = await res.json();
  STATE.pendingAttachment = { name: '', sha256: '' };

  if (out.sync_status === 'QUEUED_LOCAL_PENDING') {
    showToast(out.message || 'CSDL dùng chung đang bận. Đã lưu văn bản vào bộ đệm cá nhân và đang xếp hàng tự động ghi!', 'warning', 6000);
  } else if (out.lien_quan_qldn1) {
    showToast(
      `✅ Đã tiếp nhận văn bản và TỰ ĐỘNG CHUYỂN SANG BƯỚC 2 cho Cán bộ ${out.can_bo_xu_ly || 'phụ trách'}!`,
      'success',
      6000
    );
  } else {
    showToast(out.message || 'Đã lưu tiếp nhận văn bản rủi ro thành công!', 'success');
  }

  // Reset form inputs
  document.getElementById('th_mst_rr').value = '';
  document.getElementById('th_ten_rr').value = '';
  document.getElementById('th_mst_lq').value = '';
  document.getElementById('th_ten_lq').value = '';
  document.getElementById('th_can_bo_lq').value = '';
  document.getElementById('th_pdf_name').value = '';
  document.getElementById('mstLqHint').innerText = '';

  checkSyncQueueStatus();
  await refreshData();
}

async function scanSelectedSharePdf() {
  const chosen = document.getElementById('selectExistingSharePdf').value;
  if (!chosen) {
    showToast('Vui lòng chọn 1 file PDF trong danh sách \\\\qng-pthieu10\\SharePdf!', 'warning');
    return;
  }
  showToast('Đang phân tích bóc tách nội dung PDF...', 'info');
  const res = await fetch(`/api/sharepdf/scan_existing?name=${encodeURIComponent(chosen)}`, { headers: getHeaders() });
  const info = await res.json();
  if (info.error) {
    showToast(info.error, 'error');
    return;
  }
  applyScannedPdfInfo(info);
}

function applyScannedPdfInfo(info) {
  if (info.so_ky_hieu_vb) document.getElementById('th_so_kh').value = info.so_ky_hieu_vb;
  if (info.ngay_thang_vb) document.getElementById('th_ngay_vb').value = info.ngay_thang_vb;
  if (info.noi_gui) document.getElementById('th_noi_gui').value = info.noi_gui;
  if (info.ve_viec) document.getElementById('th_ve_viec').value = info.ve_viec;
  if (info.mst_list && info.mst_list.length > 0) document.getElementById('th_mst_rr').value = info.mst_list[0];
  if (info.mst_list && info.mst_list.length > 1) {
    document.getElementById('th_mst_lq').value = info.mst_list[1];
    lookupMstLq(info.mst_list[1]);
  }
  document.getElementById('th_pdf_name').value = info.stored_name || '';
  updateCongVanPreview();
  STATE.pendingAttachment = { name: info.stored_name || '', sha256: info.sha256 || '' };
  showToast(`Đã bóc tách tự động: Số ${info.so_ky_hieu_vb || '...'} • MST: ${(info.mst_list || []).join(', ')}`, 'success', 4500);
}

async function handleScanPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang quét file ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mstVal = document.getElementById('th_mst_rr')?.value || document.getElementById('th_mst_lq')?.value || '';
  const dateVal = document.getElementById('th_ngay_vb')?.value || '';
  const soKhVal = document.getElementById('th_so_kh')?.value || 'CVRR';
  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      doc_type: 'CVRR',
      mst: mstVal,
      date: dateVal,
      extra_info: soKhVal
    })
  });
  const info = await res.json();
  if (info.error) {
    showToast(info.error, 'error');
    return;
  }
  applyScannedPdfInfo(info);
  await refreshData();
}

async function handleImportExcel7Cols(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang nhập dữ liệu từ file Excel ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const res = await fetch('/api/ingest/excel7col', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ filename: file.name, file_b64: b64 })
  });
  const out = await res.json();
  if (out.error) {
    showToast(out.error, 'error');
    return;
  }
  showToast(`Đã nhập thành công ${out.imported_count} văn bản từ file Excel và tự động chuyển sang Bước 2!`, 'success', 5000);
  await refreshData();
}

// ==================== BƯỚC 2: XỬ LÝ MODAL CẬP NHẬT KẾT QUẢ ====================

function addWorkingDays(startDateStr, workingDays = 10) {
  if (!startDateStr) return '';
  const clean = startDateStr.trim();
  const parts = clean.split(/[\/\-]/);
  if (parts.length < 3) return '';
  let day = parseInt(parts[0], 10);
  let month = parseInt(parts[1], 10) - 1;
  let year = parseInt(parts[2], 10);
  let cur = new Date(year, month, day);
  if (isNaN(cur.getTime())) return '';

  let added = 0;
  while (added < workingDays) {
    cur.setDate(cur.getDate() + 1);
    const dayOfWeek = cur.getDay(); // 0 là Chủ Nhật, 6 là Thứ Bảy
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      added++;
    }
  }
  const dd = String(cur.getDate()).padStart(2, '0');
  const mm = String(cur.getMonth() + 1).padStart(2, '0');
  const yyyy = cur.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

function onNgayThongBaoChanged() {
  const dtVal = document.getElementById('md_ngay_thong_bao')?.value || '';
  const hanEl = document.getElementById('md_han_giai_trinh');
  if (hanEl) {
    hanEl.value = addWorkingDays(dtVal, 10);
  }
}

function onActionTypeChanged() {
  const actionType = document.getElementById('md_action_type')?.value || '';
  const boxOther = document.getElementById('boxActionOther');
  const boxTb = document.getElementById('boxTbDetails');
  const boxMlv = document.getElementById('boxMlvDetails');
  const boxPkt = document.getElementById('boxPktDetails');

  if (boxOther) boxOther.style.display = (actionType === 'Khác') ? 'block' : 'none';
  if (boxTb) boxTb.style.display = (actionType === 'Thông báo giải trình') ? 'block' : 'none';
  if (boxMlv) boxMlv.style.display = (actionType === 'Mời làm việc') ? 'block' : 'none';
  if (boxPkt) boxPkt.style.display = (actionType === 'Chuyển thông tin phòng Kiểm tra') ? 'block' : 'none';
}

function clearAttachedTbgtPdf() {
  const el = document.getElementById('md_tbgt_pdf');
  if (el) el.value = '';
  const fi = document.getElementById('md_upload_tbgt_pdf');
  if (fi) fi.value = '';
  const box = document.getElementById('md_tbgt_attached_box');
  if (box) box.style.display = 'none';
}

function clearAttachedBblvPdf() {
  const el = document.getElementById('md_bblv_pdf');
  if (el) el.value = '';
  const fi = document.getElementById('md_upload_bblv_pdf');
  if (fi) fi.value = '';
  const box = document.getElementById('md_bblv_attached_box');
  if (box) box.style.display = 'none';
}

function clearAttachedPktPdf() {
  const el = document.getElementById('md_pkt_pdf');
  if (el) el.value = '';
  const fi = document.getElementById('md_upload_pkt_pdf');
  if (fi) fi.value = '';
  const box = document.getElementById('md_pkt_attached_box');
  if (box) box.style.display = 'none';
}

function clearAttachedResultPdf() {
  const resPdf = document.getElementById('md_result_pdf');
  if (resPdf) resPdf.value = '';
  const fileInput = document.getElementById('md_upload_result_pdf');
  if (fileInput) fileInput.value = '';
  const box = document.getElementById('md_pdf_attached_box');
  if (box) box.style.display = 'none';
  const link = document.getElementById('md_pdf_attached_link');
  if (link) {
    link.href = '#';
    link.innerText = '';
  }
}

async function openDsrrModal(id) {
  try {
    const res = await fetch(`/api/dsrr/detail?id=${id}`, { headers: getHeaders() });
    const r = await res.json();
    if (!r || !r.id) return;

    const isKt = STATE.deptRole === 'PHONG_KT';
    document.getElementById('modalTitle').innerText =
      `${isKt ? '[Chế độ Xem - Phòng Kiểm tra]' : '[Cập nhật Kết quả - Phòng QLDN1]'} Hồ sơ #${r.id} • MST: ${r.mst || ''} (${r.ten_cong_ty || ''})`;

    document.getElementById('md_id').value = r.id;
    document.getElementById('md_mst').value = r.mst || '';
    document.getElementById('md_ten_cong_ty').value = r.ten_cong_ty || '';
    document.getElementById('md_tinh_trang').value = r.tinh_trang_xu_ly || 'Chưa xử lý';
    document.getElementById('md_can_bo').value = r.can_bo_xu_ly || STATE.officerName;
    document.getElementById('md_mst_rr').value = r.mst_rui_ro || '';
    document.getElementById('md_ten_cty_rr').value = r.ten_cty_rui_ro || '';

    // File Công văn rủi ro ban đầu (CVRR)
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
    document.getElementById('md_result_pdf').value = r.result_pdf_name || '';
    const pdfBox = document.getElementById('md_pdf_attached_box');
    const pdfLink = document.getElementById('md_pdf_attached_link');
    if (r.result_pdf_name) {
      if (pdfLink) {
        pdfLink.innerText = r.result_pdf_name;
        pdfLink.href = `/api/attachment?name=${encodeURIComponent(r.result_pdf_name)}&officer=${encodeURIComponent(STATE.officerName)}`;
      }
      if (pdfBox) pdfBox.style.display = 'block';
    } else {
      if (pdfBox) pdfBox.style.display = 'none';
      if (pdfLink) { pdfLink.innerText = ''; pdfLink.href = '#'; }
    }

    // File Thông báo giải trình (TBGT)
    const tbgtVal = r.tbgt_pdf_name || '';
    if (document.getElementById('md_tbgt_pdf')) document.getElementById('md_tbgt_pdf').value = tbgtVal;
    const boxTbgt = document.getElementById('md_tbgt_attached_box');
    const linkTbgt = document.getElementById('md_tbgt_attached_link');
    if (tbgtVal && boxTbgt && linkTbgt) {
      linkTbgt.innerText = tbgtVal;
      linkTbgt.href = `/api/attachment?name=${encodeURIComponent(tbgtVal)}&officer=${encodeURIComponent(STATE.officerName)}`;
      boxTbgt.style.display = 'block';
    } else if (boxTbgt) {
      boxTbgt.style.display = 'none';
    }

    // File Biên bản làm việc (BBLV)
    const bblvVal = r.bblv_pdf_name || '';
    if (document.getElementById('md_bblv_pdf')) document.getElementById('md_bblv_pdf').value = bblvVal;
    const boxBblv = document.getElementById('md_bblv_attached_box');
    const linkBblv = document.getElementById('md_bblv_attached_link');
    if (bblvVal && boxBblv && linkBblv) {
      linkBblv.innerText = bblvVal;
      linkBblv.href = `/api/attachment?name=${encodeURIComponent(bblvVal)}&officer=${encodeURIComponent(STATE.officerName)}`;
      boxBblv.style.display = 'block';
    } else if (boxBblv) {
      boxBblv.style.display = 'none';
    }

    // File & Nội dung phản hồi Phòng Kiểm tra (PKT)
    const pktVal = r.pkt_pdf_name || '';
    if (document.getElementById('md_pkt_pdf')) document.getElementById('md_pkt_pdf').value = pktVal;
    if (document.getElementById('md_pkt_noi_dung')) {
      document.getElementById('md_pkt_noi_dung').value = r.noi_dung_pkt_phan_hoi || r.ket_qua_kiem_tra_phong_b || '';
    }
    const boxPkt = document.getElementById('md_pkt_attached_box');
    const linkPkt = document.getElementById('md_pkt_attached_link');
    if (pktVal && boxPkt && linkPkt) {
      linkPkt.innerText = pktVal;
      linkPkt.href = `/api/attachment?name=${encodeURIComponent(pktVal)}&officer=${encodeURIComponent(STATE.officerName)}`;
      boxPkt.style.display = 'block';
    } else if (boxPkt) {
      boxPkt.style.display = 'none';
    }

    // Xử lý Action Type và chi tiết thông báo
    let actionType = 'Thông báo giải trình';
    let actionOther = '';
    const vd = (r.viec_da_thuc_hien || '').trim();
    if (r.so_thong_bao || r.ngay_thong_bao) {
      actionType = 'Thông báo giải trình';
    } else if (vd) {
      if (vd.toLowerCase().includes('thông báo') || vd.toLowerCase().includes('thong bao')) {
        actionType = 'Thông báo giải trình';
      } else if (vd.toLowerCase().includes('mời làm việc') || vd.toLowerCase().includes('moi lam viec')) {
        actionType = 'Mời làm việc';
      } else if (vd.toLowerCase().includes('phòng kiểm tra') || vd.toLowerCase().includes('kiểm tra')) {
        actionType = 'Chuyển thông tin phòng Kiểm tra';
      } else if (vd.startsWith('Khác:')) {
        actionType = 'Khác';
        actionOther = vd.replace(/^Khác:\s*/i, '');
      } else {
        actionType = 'Khác';
        actionOther = vd;
      }
    }

    const selAction = document.getElementById('md_action_type');
    if (selAction) selAction.value = actionType;
    const inpOther = document.getElementById('md_action_other');
    if (inpOther) inpOther.value = actionOther;

    const inpSoTb = document.getElementById('md_so_thong_bao');
    if (inpSoTb) inpSoTb.value = r.so_thong_bao || '';

    const inpNgayTb = document.getElementById('md_ngay_thong_bao');
    if (inpNgayTb) inpNgayTb.value = r.ngay_thong_bao || '';

    const inpHanGt = document.getElementById('md_han_giai_trinh');
    if (inpHanGt) {
      inpHanGt.value = r.han_giai_trinh || (r.ngay_thong_bao ? addWorkingDays(r.ngay_thong_bao, 10) : '');
    }

    onActionTypeChanged();

    document.getElementById('md_ghi_chu').value = r.ghi_chu || '';
    document.getElementById('md_nnt_giai_trinh').value = r.nnt_giai_trinh || '';
    document.getElementById('md_de_xuat').value = r.de_xuat_xu_ly || '';
    document.getElementById('md_kq_phong_b').value = r.ket_qua_kiem_tra_phong_b || '';

    // 4 nhóm kết quả hóa đơn
    document.getElementById('md_ck_so').value = r.cam_ket_so_hd || 0;
    document.getElementById('md_ck_gt').value = r.cam_ket_gia_tri || 0;
    document.getElementById('md_ck_vat').value = r.cam_ket_thue_gtgt || 0;
    document.getElementById('md_dc_so').value = r.dieu_chinh_so_hd || 0;
    document.getElementById('md_dc_cp').value = r.dieu_chinh_giam_chi_phi || 0;
    document.getElementById('md_dc_kt').value = r.dieu_chinh_giam_khau_tru || 0;
    document.getElementById('md_dc_tndn').value = r.dieu_chinh_thue_tndn || 0;
    document.getElementById('md_dc_gtgt').value = r.dieu_chinh_thue_gtgt || 0;
    document.getElementById('md_kkk_so').value = r.khong_kk_so_hd || 0;
    document.getElementById('md_kkk_gt').value = r.khong_kk_gia_tri || 0;
    document.getElementById('md_kkk_vat').value = r.khong_kk_thue_gtgt || 0;
    document.getElementById('md_kn_so').value = r.khong_nhan_so_hd || 0;
    document.getElementById('md_kn_gt').value = r.khong_nhan_gia_tri || 0;
    document.getElementById('md_kn_vat').value = r.khong_nhan_thue_gtgt || 0;

    const qlhtIds = [
      'md_ten_cong_ty', 'md_tinh_trang', 'md_can_bo', 'md_mst_rr', 'md_ten_cty_rr',
      'md_upload_result_pdf',
      'md_action_type', 'md_action_other', 'md_so_thong_bao', 'md_ngay_thong_bao',
      'md_ghi_chu', 'md_nnt_giai_trinh', 'md_de_xuat',
      'md_ck_so', 'md_ck_gt', 'md_ck_vat',
      'md_dc_so', 'md_dc_cp', 'md_dc_kt', 'md_dc_tndn', 'md_dc_gtgt',
      'md_kkk_so', 'md_kkk_gt', 'md_kkk_vat', 'md_kn_so', 'md_kn_gt', 'md_kn_vat'
    ];
    qlhtIds.forEach(fid => {
      const el = document.getElementById(fid);
      if (el) el.disabled = isKt;
    });

    document.getElementById('btnSaveDsrrModal').style.display = isKt ? 'none' : 'inline-flex';
    const hintEl = document.getElementById('modalPermissionHint');
    if (hintEl) {
      hintEl.innerHTML = isKt
        ? `<span style="color:#6d28d9; font-weight:700;">Bạn đang ở vai trò Phòng Kiểm tra (Chế độ Tra cứu & Xem hồ sơ).</span>`
        : `Nhấn <code>Ctrl+S</code> để lưu nhanh`;
    }

    document.getElementById('dsrrModal').classList.add('open');
  } catch (err) {
    showToast('Lỗi mở hồ sơ: ' + err.message, 'error');
  }
}

function closeDsrrModal() {
  document.getElementById('dsrrModal').classList.remove('open');
}

async function handleUploadResultPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang lưu văn bản giải trình: ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mst = document.getElementById('md_mst').value || '';
  const dateVal = document.getElementById('md_ngay_thong_bao')?.value || '';
  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      doc_type: 'GTDN',
      mst: mst,
      date: dateVal,
      extra_info: 'GiaiTrinh'
    })
  });
  const out = await res.json();
  if (out.stored_name) {
    document.getElementById('md_result_pdf').value = out.stored_name;
    const pdfBox = document.getElementById('md_pdf_attached_box');
    const pdfLink = document.getElementById('md_pdf_attached_link');
    if (pdfLink) {
      pdfLink.innerText = out.stored_name;
      pdfLink.href = `/api/attachment?name=${encodeURIComponent(out.stored_name)}&officer=${encodeURIComponent(STATE.officerName)}`;
    }
    if (pdfBox) pdfBox.style.display = 'block';
    showToast(`Đã lưu và chuẩn hóa tên file: ${out.stored_name}`, 'success');
    await refreshData();
  } else {
    showToast('Không thể lưu file PDF giải trình!', 'error');
  }
}

async function handleUploadTbgtPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang lưu Thông báo giải trình: ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mst = document.getElementById('md_mst').value || '';
  const dateVal = document.getElementById('md_ngay_thong_bao')?.value || '';
  const soTb = document.getElementById('md_so_thong_bao')?.value || 'TBGT';
  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      doc_type: 'TBGT',
      mst: mst,
      date: dateVal,
      extra_info: soTb
    })
  });
  const out = await res.json();
  if (out.stored_name) {
    document.getElementById('md_tbgt_pdf').value = out.stored_name;
    const box = document.getElementById('md_tbgt_attached_box');
    const link = document.getElementById('md_tbgt_attached_link');
    if (link) {
      link.innerText = out.stored_name;
      link.href = `/api/attachment?name=${encodeURIComponent(out.stored_name)}&officer=${encodeURIComponent(STATE.officerName)}`;
    }
    if (box) box.style.display = 'block';
    showToast(`Đã lưu Thông báo giải trình: ${out.stored_name}`, 'success');
    await refreshData();
  } else {
    showToast('Lỗi lưu file Thông báo giải trình!', 'error');
  }
}

async function handleUploadBblvPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang lưu Biên bản làm việc: ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mst = document.getElementById('md_mst').value || '';
  const dateVal = document.getElementById('md_ngay_bblv')?.value || '';
  const soBb = document.getElementById('md_so_bblv')?.value || 'BBLV';
  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      doc_type: 'BBLV',
      mst: mst,
      date: dateVal,
      extra_info: soBb
    })
  });
  const out = await res.json();
  if (out.stored_name) {
    document.getElementById('md_bblv_pdf').value = out.stored_name;
    const box = document.getElementById('md_bblv_attached_box');
    const link = document.getElementById('md_bblv_attached_link');
    if (link) {
      link.innerText = out.stored_name;
      link.href = `/api/attachment?name=${encodeURIComponent(out.stored_name)}&officer=${encodeURIComponent(STATE.officerName)}`;
    }
    if (box) box.style.display = 'block';
    showToast(`Đã lưu Biên bản làm việc: ${out.stored_name}`, 'success');
    await refreshData();
  } else {
    showToast('Lỗi lưu file Biên bản làm việc!', 'error');
  }
}

async function handleUploadPktPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang lưu File phản hồi Phòng KT: ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mst = document.getElementById('md_mst').value || '';
  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      doc_type: 'PKT',
      mst: mst,
      extra_info: 'PhanHoiKT'
    })
  });
  const out = await res.json();
  if (out.stored_name) {
    document.getElementById('md_pkt_pdf').value = out.stored_name;
    const box = document.getElementById('md_pkt_attached_box');
    const link = document.getElementById('md_pkt_attached_link');
    if (link) {
      link.innerText = out.stored_name;
      link.href = `/api/attachment?name=${encodeURIComponent(out.stored_name)}&officer=${encodeURIComponent(STATE.officerName)}`;
    }
    if (box) box.style.display = 'block';
    showToast(`Đã lưu File phản hồi Phòng KT: ${out.stored_name}`, 'success');
    await refreshData();
  } else {
    showToast('Lỗi lưu file phản hồi phòng Kiểm tra!', 'error');
  }
}

async function saveDsrrUpdate() {
  if (STATE.deptRole === 'PHONG_KT') {
    showToast('Chức năng cập nhật kết quả chỉ dành cho Phòng Quản lý Doanh nghiệp 1 / QLHTDN!', 'warning');
    return;
  }

  const actionType = document.getElementById('md_action_type')?.value || 'Thông báo giải trình';
  const actionOther = (document.getElementById('md_action_other')?.value || '').trim();
  const soTb = (document.getElementById('md_so_thong_bao')?.value || '').trim();
  const ngayTb = (document.getElementById('md_ngay_thong_bao')?.value || '').trim();
  let hanGt = (document.getElementById('md_han_giai_trinh')?.value || '').trim();

  if (actionType === 'Thông báo giải trình' && ngayTb && !hanGt) {
    hanGt = addWorkingDays(ngayTb, 10);
  }

  let viecDaThucHien = actionType;
  if (actionType === 'Khác') {
    viecDaThucHien = actionOther ? `Khác: ${actionOther}` : 'Khác';
  } else if (actionType === 'Thông báo giải trình') {
    const details = [];
    if (soTb) details.push(`Số TB: ${soTb}`);
    if (ngayTb) details.push(`Ngày: ${ngayTb}`);
    if (hanGt) details.push(`Hạn GT: ${hanGt}`);
    if (details.length) {
      viecDaThucHien += ` (${details.join(', ')})`;
    }
  }

  const payload = {
    id: Number(document.getElementById('md_id').value),
    officer_name: STATE.officerName,
    ten_cong_ty: document.getElementById('md_ten_cong_ty').value,
    tinh_trang_xu_ly: document.getElementById('md_tinh_trang').value,
    can_bo_xu_ly: document.getElementById('md_can_bo').value,
    mst_rui_ro: document.getElementById('md_mst_rr').value,
    ten_cty_rui_ro: document.getElementById('md_ten_cty_rr').value,
    attachment_name: document.getElementById('md_attachment_name')?.value || '',
    result_pdf_name: document.getElementById('md_result_pdf')?.value || '',
    tbgt_pdf_name: document.getElementById('md_tbgt_pdf')?.value || '',
    bblv_pdf_name: document.getElementById('md_bblv_pdf')?.value || '',
    pkt_pdf_name: document.getElementById('md_pkt_pdf')?.value || '',
    noi_dung_pkt_phan_hoi: document.getElementById('md_pkt_noi_dung')?.value || '',
    viec_da_thuc_hien: viecDaThucHien,
    so_thong_bao: soTb,
    ngay_thong_bao: ngayTb,
    han_giai_trinh: hanGt,
    dieu_chinh_thue_tndn: parseNum(document.getElementById('md_dc_tndn').value),
    dieu_chinh_thue_gtgt: parseNum(document.getElementById('md_dc_gtgt').value),
    ghi_chu: document.getElementById('md_ghi_chu').value,
    nnt_giai_trinh: document.getElementById('md_nnt_giai_trinh').value,
    de_xuat_xu_ly: document.getElementById('md_de_xuat').value,
    ket_qua_kiem_tra_phong_b: document.getElementById('md_kq_phong_b').value,
    cam_ket_so_hd: parseNum(document.getElementById('md_ck_so').value),
    cam_ket_gia_tri: parseNum(document.getElementById('md_ck_gt').value),
    cam_ket_thue_gtgt: parseNum(document.getElementById('md_ck_vat').value),
    dieu_chinh_so_hd: parseNum(document.getElementById('md_dc_so').value),
    dieu_chinh_giam_chi_phi: parseNum(document.getElementById('md_dc_cp').value),
    dieu_chinh_giam_khau_tru: parseNum(document.getElementById('md_dc_kt').value),
    khong_kk_so_hd: parseNum(document.getElementById('md_kkk_so').value),
    khong_kk_gia_tri: parseNum(document.getElementById('md_kkk_gt').value),
    khong_kk_thue_gtgt: parseNum(document.getElementById('md_kkk_vat').value),
    khong_nhan_so_hd: parseNum(document.getElementById('md_kn_so').value),
    khong_nhan_gia_tri: parseNum(document.getElementById('md_kn_gt').value),
    khong_nhan_thue_gtgt: parseNum(document.getElementById('md_kn_vat').value)
  };

  const res = await fetch('/api/dsrr/update', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    const resData = await res.json().catch(() => ({}));
    if (resData.sync_status === 'QUEUED_LOCAL_PENDING') {
      showToast(resData.message || 'CSDL dùng chung đang bận. Đã lưu an toàn vào bộ đệm cá nhân và đang xếp hàng tự động ghi!', 'warning', 6000);
    } else {
      showToast(resData.message || `Đã cập nhật và đồng bộ thành công Hồ sơ #${payload.id}!`, 'success');
    }
    closeDsrrModal();
    checkSyncQueueStatus();
    await refreshData();
  } else {
    showToast('Lỗi cập nhật hồ sơ!', 'error');
  }
}


// ==================== BƯỚC 3: TRA CỨU TOÀN DIỆN CÔNG VĂN & HỒ SƠ RỦI RO ====================

let inspectSearchTimer = null;
function debouncedInspectorSearch() {
  clearTimeout(inspectSearchTimer);
  inspectSearchTimer = setTimeout(executeInspectorSearch, 180);
}

function clearInspectSearch() {
  const input = document.getElementById('inspectMstInput');
  if (input) input.value = '';
  const clearBtn = document.getElementById('btnClearInspectSearch');
  if (clearBtn) clearBtn.style.display = 'none';
  if (STATE.inspectActiveTab === 'th') {
    renderInspectThTable();
  } else {
    executeInspectorSearch();
  }
}

function switchInspectTab(tab) {
  STATE.inspectActiveTab = tab;
  const btnDsrr = document.getElementById('tabBtnInspectDsrr');
  const btnTh = document.getElementById('tabBtnInspectTh');
  const wrapDsrr = document.getElementById('wrapInspectDsrr');
  const wrapTh = document.getElementById('wrapInspectTh');

  if (tab === 'th') {
    if (btnDsrr) { btnDsrr.className = 'btn btn-outline'; }
    if (btnTh) { btnTh.className = 'btn btn-purple'; }
    if (wrapDsrr) wrapDsrr.style.display = 'none';
    if (wrapTh) wrapTh.style.display = 'block';
    renderInspectThTable();
  } else {
    if (btnDsrr) { btnDsrr.className = 'btn btn-purple'; }
    if (btnTh) { btnTh.className = 'btn btn-outline'; }
    if (wrapDsrr) wrapDsrr.style.display = 'block';
    if (wrapTh) wrapTh.style.display = 'none';
    executeInspectorSearch();
  }
}

function sortInspectTable(colKey) {
  if (STATE.inspectSort.col === colKey) {
    STATE.inspectSort.dir = STATE.inspectSort.dir === 'asc' ? 'desc' : 'asc';
  } else {
    STATE.inspectSort.col = colKey;
    STATE.inspectSort.dir = (colKey === 'id' || colKey === 'han_gt' || colKey === 'ngay_vb_den') ? 'desc' : 'asc';
  }
  updateSortIcons('sort_icon_inspect_', STATE.inspectSort);
  executeInspectorSearch();
}

function resetInspectFilters() {
  const input = document.getElementById('inspectMstInput');
  if (input) input.value = '';
  const clearBtn = document.getElementById('btnClearInspectSearch');
  if (clearBtn) clearBtn.style.display = 'none';

  const stSelect = document.getElementById('inspectFilterStatusSelect');
  if (stSelect) stSelect.value = '';

  const offSelect = document.getElementById('inspectFilterOfficerSelect');
  if (offSelect) offSelect.value = '';

  const grpSelect = document.getElementById('inspectFilterInvoiceGroupSelect');
  if (grpSelect) grpSelect.value = '';

  const pdfSelect = document.getElementById('inspectFilterPdfSelect');
  if (pdfSelect) pdfSelect.value = '';

  STATE.inspectSort = { col: 'id', dir: 'desc' };
  updateSortIcons('sort_icon_inspect_', STATE.inspectSort);

  if (STATE.inspectActiveTab === 'th') {
    renderInspectThTable();
  } else {
    executeInspectorSearch();
  }
  showToast('Đã đặt lại toàn bộ bộ lọc tra cứu', 'info');
}

function renderInspectThTable() {
  const rawQ = (document.getElementById('inspectMstInput')?.value || '').trim();
  const searchTerms = rawQ.toLowerCase().split(/\s+/).filter(Boolean);
  const clearBtn = document.getElementById('btnClearInspectSearch');
  if (clearBtn) clearBtn.style.display = rawQ ? 'block' : 'none';

  const filtered = STATE.thList.filter(r => {
    if (!searchTerms.length) return true;
    const targetPool = [
      r.mst,
      r.cong_van,
      r.mst_lien_quan,
      r.ve_viec,
      r.co_quan_chuyen_den,
      r.file_pdf
    ].filter(Boolean).join(' ');

    const poolLower = targetPool.toLowerCase();
    const poolUnaccented = removeVietnameseTones(targetPool);

    return searchTerms.every(term => {
      const tLower = term.toLowerCase();
      const tUnaccented = removeVietnameseTones(term);
      return poolLower.includes(tLower) || poolUnaccented.includes(tUnaccented);
    });
  });

  const tbody = document.getElementById('tbodyInspectTh');
  const badge = document.getElementById('inspectCountBadge');
  if (badge) {
    badge.className = 'badge badge-done';
    badge.innerText = `Tìm thấy ${filtered.length} / ${STATE.thList.length} công văn cảnh báo`;
  }
  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:35px; color:#64748b;">
      🔍 Không tìm thấy công văn cảnh báo nào khớp với từ khóa "<b>${rawQ}</b>".
    </td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((r, idx) => `
    <tr>
      <td style="text-align:center; font-weight:700; color:#64748b;">#${r.id || idx + 1}</td>
      <td>
        <code style="color:#dc2626; font-weight:900; font-size:13px;">${highlightKeywords(r.mst || '-', searchTerms)}</code>
      </td>
      <td>
        <div style="font-weight:700; color:#0f172a;">${highlightKeywords(r.ve_viec || '-', searchTerms)}</div>
        ${r.co_quan_chuyen_den ? `<small style="color:#64748b;">Nơi gửi: ${highlightKeywords(r.co_quan_chuyen_den, searchTerms)}</small>` : ''}
      </td>
      <td>
        <b style="color:#1e40af;">${highlightKeywords(r.cong_van || '-', searchTerms)}</b>
      </td>
      <td>
        <code style="color:#0f172a; font-weight:800; font-size:12.5px;">${highlightKeywords(r.mst_lien_quan || 'Toàn cục / Chưa gắn', searchTerms)}</code>
      </td>
      <td>
        ${r.file_pdf ? `<a class="badge-pdf" style="background:#dbeafe; color:#1e40af;" href="/api/attachment?name=${encodeURIComponent(r.file_pdf)}&officer=${encodeURIComponent(STATE.officerName)}" target="_blank">📎 ${highlightKeywords(r.file_pdf, searchTerms)}</a>` : '<span style="color:#94a3b8; font-size:11.5px;">Chưa đính kèm file</span>'}
      </td>
    </tr>
  `).join('');
}

async function executeInspectorSearch() {
  if (STATE.inspectActiveTab === 'th') {
    renderInspectThTable();
    return;
  }

  const rawQ = (document.getElementById('inspectMstInput')?.value || '').trim();
  const clearBtn = document.getElementById('btnClearInspectSearch');
  if (clearBtn) clearBtn.style.display = rawQ ? 'block' : 'none';

  const statusFilter = document.getElementById('inspectFilterStatusSelect')?.value || '';
  const offFilter = document.getElementById('inspectFilterOfficerSelect')?.value || '';
  const grpFilter = document.getElementById('inspectFilterInvoiceGroupSelect')?.value || '';
  const pdfFilter = document.getElementById('inspectFilterPdfSelect')?.value || '';

  const searchTerms = rawQ.toLowerCase().split(/\s+/).filter(Boolean);

  // Mở full toàn bộ danh sách DSRR (không giới hạn 150 hồ sơ)
  const filtered = STATE.dsrrList.filter(r => {
    // 1. Trạng thái
    if (statusFilter === 'OVERDUE' && !isRecordOverdue(r)) return false;
    if (statusFilter && statusFilter !== 'OVERDUE' && r.tinh_trang_xu_ly !== statusFilter) return false;

    // 2. Cán bộ xử lý
    if (offFilter && (r.can_bo_xu_ly || '') !== offFilter) return false;

    // 3. 4 Nhóm hóa đơn
    if (grpFilter === 'GROUP_1' && Number(r.cam_ket_so_hd || 0) <= 0) return false;
    if (grpFilter === 'GROUP_2' && (Number(r.dieu_chinh_so_hd || 0) <= 0 && Number(r.dieu_chinh_thue_tndn || 0) <= 0 && Number(r.dieu_chinh_thue_gtgt || 0) <= 0)) return false;
    if (grpFilter === 'GROUP_3' && Number(r.khong_kk_so_hd || 0) <= 0) return false;
    if (grpFilter === 'GROUP_4' && Number(r.khong_nhan_so_hd || 0) <= 0) return false;

    // 4. File PDF
    if (pdfFilter === 'HAS_RES_PDF' && !r.result_pdf_name) return false;
    if (pdfFilter === 'HAS_ATT_PDF' && !r.attachment_name) return false;
    if (pdfFilter === 'NO_PDF' && (r.result_pdf_name || r.attachment_name)) return false;

    if (!searchTerms.length) return true;

    // Tìm kiếm sâu đa trường với unaccented tiếng Việt
    const targetPool = [
      r.mst,
      r.ten_cong_ty,
      r.can_bo_xu_ly,
      r.mst_rui_ro,
      r.ten_cty_rui_ro,
      r.so_ky_hieu_vb,
      r.so_den_vb,
      r.noi_gui,
      r.ngay_thang_vb,
      r.ngay_vb_den,
      r.viec_da_thuc_hien,
      r.so_thong_bao,
      r.ngay_thong_bao,
      r.han_giai_trinh,
      r.viec_tiep_tuc,
      r.ghi_chu,
      r.nnt_giai_trinh,
      r.de_xuat_xu_ly,
      r.ket_qua_kiem_tra_phong_b,
      r.result_pdf_name,
      r.attachment_name,
      r.tinh_trang_xu_ly,
      String(r.cam_ket_gia_tri || ''),
      String(r.dieu_chinh_thue_tndn || ''),
      String(r.dieu_chinh_thue_gtgt || ''),
      fmtNum(r.cam_ket_gia_tri),
      fmtNum(r.dieu_chinh_thue_tndn),
      fmtNum(r.dieu_chinh_thue_gtgt)
    ].filter(Boolean).join(' ');

    const poolLower = targetPool.toLowerCase();
    const poolUnaccented = removeVietnameseTones(targetPool);

    return searchTerms.every(term => {
      const tLower = term.toLowerCase();
      const tUnaccented = removeVietnameseTones(term);
      return poolLower.includes(tLower) || poolUnaccented.includes(tUnaccented);
    });
  });

  const sorted = sortRecords(filtered, STATE.inspectSort.col, STATE.inspectSort.dir);
  updateSortIcons('sort_icon_inspect_', STATE.inspectSort);

  const tbody = document.getElementById('tbodyInspectResult');
  const badge = document.getElementById('inspectCountBadge');
  if (badge) {
    if (rawQ || statusFilter || offFilter || grpFilter || pdfFilter) {
      badge.className = 'badge badge-doing';
      badge.innerText = `Tìm thấy ${sorted.length} / ${STATE.dsrrList.length} hồ sơ`;
    } else {
      badge.className = 'badge badge-done';
      badge.innerText = `Hiển thị toàn bộ ${sorted.length} hồ sơ`;
    }
  }
  if (!tbody) return;

  if (sorted.length === 0) {
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
  }).join('');
}

function exportStandardExcel() {
  showToast('Đang kết xuất file Excel chuẩn 2 sheet...', 'info');
  window.open(`/api/export/excel?officer=${encodeURIComponent(STATE.officerName)}`, '_blank');
}

function unlockOwnerAudit() {
  openAdminModule();
}

async function loadStealthLogs() {
  try {
    const res = await fetch('/api/stealth/logs', { headers: getHeaders() });
    if (res.status === 403 || res.status === 401) {
      showToast('Yêu cầu quyền Quản trị viên để truy cập nhật ký lưu vết!', 'error');
      return;
    }
    if (!res.ok) return;
    const data = await res.json();
    STATE.auditLogs = data.logs || [];

    const totalEl = document.getElementById('adminKpiTotalLogs');
    if (totalEl) totalEl.innerText = STATE.auditLogs.length.toLocaleString('vi-VN');

    try {
      const qRes = await fetch('/api/sync/status', { headers: getHeaders() });
      if (qRes.ok) {
        const qData = await qRes.json();
        const qStatusEl = document.getElementById('adminKpiSyncQueueStatus');
        const qDetailEl = document.getElementById('adminKpiSyncQueueDetail');
        if (qStatusEl) qStatusEl.innerText = `${qData.pending_count || 0} chờ`;
        if (qDetailEl) {
          qDetailEl.innerText = qData.pending_count > 0 
            ? 'Đang chờ ghi bổ sung vào CSDL trung tâm' 
            : 'CSDL trung tâm đã cập nhật toàn bộ';
        }
      }
    } catch (e) {}

    renderStealthLogsTable(STATE.auditLogs);
  } catch (err) {
    console.error('Lỗi khi tải nhật ký lưu vết:', err);
  }
}

function renderStealthLogsTable(logs) {
  const tbody = document.getElementById('tbodyStealthLogs');
  if (!tbody) return;
  if (!logs || logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:24px; color:#94a3b8;">Không có sự kiện lưu vết phù hợp.</td></tr>`;
    return;
  }
  tbody.innerHTML = logs.map(l => {
    const ev = (l.event_type || '').toUpperCase();
    let badgeClass = 'badge-pending';
    if (ev.includes('LOGIN') || ev.includes('AUTH')) badgeClass = 'badge-doing';
    else if (ev.includes('CREATE') || ev.includes('SAVE') || ev.includes('IMPORT') || ev.includes('SYNC')) badgeClass = 'badge-done';
    else if (ev.includes('DELETE') || ev.includes('FAIL') || ev.includes('ERR')) badgeClass = 'badge-overdue';

    return `
      <tr>
        <td><code style="color:#64748b;">#${l.id}</code></td>
        <td><span style="font-size:11.5px; font-weight:700; color:#334155;">${escapeHtml(l.timestamp || '')}</span></td>
        <td><code>${escapeHtml(l.client_ip || '')}</code></td>
        <td><b style="color:#1e40af;">${escapeHtml(l.officer_name || '')}</b></td>
        <td><span style="font-size:11px; color:#475569;">${escapeHtml(l.department || '')}</span></td>
        <td><span class="badge ${badgeClass}">${escapeHtml(l.event_type || '')}</span></td>
        <td><span style="font-size:11.5px; color:#475569;">${escapeHtml(l.target_module || '')}</span></td>
        <td><code>${escapeHtml(l.target_mst || '-')}</code></td>
        <td style="font-size:12px; color:#1e293b;">${escapeHtml(l.event_detail || '')}</td>
      </tr>
    `;
  }).join('');
}

function debouncedFilterAdminAudit() {
  clearTimeout(STATE.auditSearchTimer);
  STATE.auditSearchTimer = setTimeout(filterAdminAuditList, 250);
}

function filterAdminAuditList() {
  const q = (document.getElementById('adminAuditSearchInput')?.value || '').trim().toLowerCase();
  const eventFilter = (document.getElementById('adminAuditEventFilter')?.value || '').trim().toUpperCase();

  const filtered = (STATE.auditLogs || []).filter(l => {
    const ev = (l.event_type || '').toUpperCase();
    const matchEvent = !eventFilter || ev.includes(eventFilter);
    if (!matchEvent) return false;
    if (!q) return true;
    const fullStr = `${l.timestamp} ${l.client_ip} ${l.officer_name} ${l.department} ${l.event_type} ${l.target_module} ${l.target_mst} ${l.event_detail}`.toLowerCase();
    return fullStr.includes(q);
  });

  renderStealthLogsTable(filtered);
}

function exportAuditLogsCsv() {
  if (!STATE.auditLogs || STATE.auditLogs.length === 0) {
    showToast('Không có dữ liệu nhật ký để xuất!', 'warning');
    return;
  }
  const headers = ['ID', 'Thời điểm', 'IP Máy trạm', 'Account/Công chức', 'Phòng ban', 'Hành động', 'Phân hệ', 'MST', 'Chi tiết'];
  const rows = STATE.auditLogs.map(l => [
    l.id,
    `"${(l.timestamp || '').replace(/"/g, '""')}"`,
    `"${(l.client_ip || '').replace(/"/g, '""')}"`,
    `"${(l.officer_name || '').replace(/"/g, '""')}"`,
    `"${(l.department || '').replace(/"/g, '""')}"`,
    `"${(l.event_type || '').replace(/"/g, '""')}"`,
    `"${(l.target_module || '').replace(/"/g, '""')}"`,
    `"${(l.target_mst || '').replace(/"/g, '""')}"`,
    `"${(l.event_detail || '').replace(/"/g, '""')}"`,
  ]);
  const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `NhatKy_LuuVet_HeThong_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Đã xuất file CSV nhật ký hệ thống thành công!', 'success');
}

// ==================== BƯỚC 2+: CHỨC NĂNG NHẮC VIỆC QUA OUTLOOK ====================

let reminderCache = {
  records: [],
  officersSummary: [],
  activePreview: null
};

// (calculateOverdueCount is defined at the top utility section)

function openOutlookReminderModal() {
  const modal = document.getElementById('outlookReminderModal');
  if (!modal) return;
  modal.classList.add('open');
  loadOverdueReminders();
}

function closeOutlookReminderModal() {
  const modal = document.getElementById('outlookReminderModal');
  if (modal) modal.classList.remove('open');
  const previewBox = document.getElementById('emailPreviewBox');
  if (previewBox) previewBox.style.display = 'none';
}

async function loadOverdueReminders() {
  const mode = document.getElementById('reminderFilterMode')?.value || 'OVERDUE_ONLY';
  const officerFilter = document.getElementById('reminderOfficerSelect')?.value || '';

  try {
    const res = await fetch(`/api/reminders/list?mode=${mode}&officer=${encodeURIComponent(officerFilter)}`, {
      headers: getHeaders()
    });
    const data = await res.json();
    reminderCache.records = data.records || [];
    reminderCache.officersSummary = data.officers_summary || [];

    // Cập nhật số liệu KPI tóm tắt trong modal
    const overdueBadge = document.getElementById('modalOverdueBadge');
    if (overdueBadge) overdueBadge.innerText = `${data.overdue_count} hồ sơ thỏa điều kiện đôn đốc`;

    const statOverdue = document.getElementById('statOverdueCount');
    if (statOverdue) statOverdue.innerText = data.overdue_count;

    const statPending = document.getElementById('statTotalPending');
    if (statPending) statPending.innerText = data.total_pending;

    const statOfficer = document.getElementById('statOfficerCount');
    if (statOfficer) statOfficer.innerText = data.officers_summary.length;

    // Cập nhật danh sách Cán bộ nếu chưa chọn lọc
    const offSelect = document.getElementById('reminderOfficerSelect');
    if (offSelect && !officerFilter) {
      const curVal = offSelect.value;
      let opts = '<option value="">-- Tất cả cán bộ --</option>';
      data.officers_summary.forEach(o => {
        opts += `<option value="${o.officer_name}" ${o.officer_name === curVal ? 'selected' : ''}>${o.officer_name} (${o.overdue_count} hồ sơ chậm)</option>`;
      });
      offSelect.innerHTML = opts;
    }

    renderReminderTableRows(data.records);
  } catch (err) {
    showToast('Lỗi tải danh sách đôn đốc: ' + err.message, 'error');
  }
}

function renderReminderTableRows(records) {
  const tbody = document.getElementById('tbodyReminderRows');
  if (!tbody) return;

  const rawQ = (document.getElementById('filterReminderTableInput')?.value || '').trim().toLowerCase();
  const filtered = records.filter(r => {
    if (!rawQ) return true;
    const pool = [
      r.mst,
      r.ten_cong_ty,
      r.can_bo_xu_ly,
      r.officer_email,
      r.mst_rui_ro,
      r.ten_cty_rui_ro,
      r.so_ky_hieu_vb
    ].filter(Boolean).join(' ').toLowerCase();
    return pool.includes(rawQ);
  });

  if (!filtered.length) {
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

    const safeMailto = (r.mailto_url || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const safeOfficer = (r.can_bo_xu_ly || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const safeEmail = (r.officer_email || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const safeMst = (r.mst || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");

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
        </td>
        <td>
          <code style="color:#dc2626; font-weight:700;">${r.mst_rui_ro || '-'}</code><br>
          <span style="font-size:11.5px; color:#475569;">${r.ten_cty_rui_ro || ''}</span>
        </td>
        <td>
          <div style="font-size:12px; color:#0f172a;">Ngày đến: <b>${r.ngay_vb_den || '-'}</b></div>
          <div style="margin-top:4px;"><span class="${badgeClass}">${r.urgency_label || `${r.days_elapsed} ngày`}</span></div>
          ${r.so_thong_bao ? `<div style="font-size:11px; color:#5b21b6; margin-top:2px;">Số TB: <b>${r.so_thong_bao}</b> ${r.ngay_thong_bao ? `(${r.ngay_thong_bao})` : ''}</div>` : ''}
          ${r.han_giai_trinh ? `<div style="font-size:11px; color:#b91c1c; font-weight:700; margin-top:1px;">Hạn GT (+10 ngày): ${r.han_giai_trinh}</div>` : ''}
          ${r.han_xu_ly && r.han_xu_ly !== r.han_giai_trinh ? `<div style="font-size:11px; color:#dc2626; margin-top:2px;">Hạn xử lý: ${r.han_xu_ly}</div>` : ''}
        </td>
        <td style="font-size:12px;">
          <div>${statusBadge(r.tinh_trang_xu_ly)}</div>
          ${r.viec_da_thuc_hien ? `<div style="color:#475569; margin-top:3px; max-height:45px; overflow:hidden;">• ${r.viec_da_thuc_hien}</div>` : ''}
          ${r.ghi_chu ? `<div style="color:#64748b; font-size:11px; margin-top:2px;">• ${r.ghi_chu}</div>` : ''}
        </td>
        <td style="text-align:center;">
          <div style="display:flex; flex-direction:column; gap:4px; align-items:center;">
            <button class="btn btn-primary" style="padding:4px 8px; font-size:11.5px; width:100%; display:inline-flex; align-items:center; justify-content:center; gap:4px;" onclick="triggerOutlookMailto('${safeMailto}', ${r.id}, '${safeOfficer}', '${safeEmail}', '${safeMst}')" title="Mở trực tiếp ứng dụng Microsoft Outlook">
              📧 Mở Outlook
            </button>
            <div style="display:flex; gap:4px; width:100%;">
              <button class="btn btn-outline" style="padding:3px 6px; font-size:11px; flex:1;" onclick="previewEmailRecord(${r.id})" title="Xem trước nội dung email">
                👁️ Xem mẫu
              </button>
              <button class="btn btn-outline" style="padding:3px 6px; font-size:11px; flex:1;" onclick="copyRecordEmailBody(${r.id})" title="Sao chép nội dung email vào bộ nhớ tạm">
                📋 Sao chép
              </button>
            </div>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function filterReminderTableRows() {
  renderReminderTableRows(reminderCache.records);
}

async function triggerOutlookMailto(mailtoUrl, recId, officerName, officerEmail, mst) {
  if (!officerEmail) {
    showToast('Cán bộ này chưa có địa chỉ email trong danh mục! Bạn có thể xem trước và sao chép nội dung email.', 'warning');
    previewEmailRecord(recId);
    return;
  }

  // 1. Ghi nhận log ngầm hành động đôn đốc nhắc việc
  try {
    fetch('/api/reminders/log', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        record_id: recId,
        target_officer: officerName,
        target_email: officerEmail,
        mst: mst
      })
    });
  } catch (e) {
    // Không chặn thao tác người dùng nếu log lỗi
  }

  // 2. Kích hoạt liên kết mailto để mở Microsoft Outlook trên Windows
  const link = document.createElement('a');
  link.href = mailtoUrl;
  link.target = '_blank';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  showToast(`Đã mở Microsoft Outlook gửi email đôn đốc đến ${officerName} (${officerEmail})!`, 'success', 5000);
}

function previewEmailRecord(recId) {
  const rec = reminderCache.records.find(r => r.id === recId);
  if (!rec) return;

  const previewBox = document.getElementById('emailPreviewBox');
  if (!previewBox) return;

  document.getElementById('previewToEmail').innerText = rec.officer_email || '(Chưa có email - Đề nghị liên hệ trực tiếp)';
  document.getElementById('previewSubject').innerText = rec.email_subject || '';
  document.getElementById('previewBody').innerText = rec.email_body || '';

  const btnOpen = document.getElementById('btnPreviewOpenOutlook');
  if (btnOpen) {
    btnOpen.onclick = () => triggerOutlookMailto(rec.mailto_url, rec.id, rec.can_bo_xu_ly, rec.officer_email, rec.mst);
  }

  const btnCopy = document.getElementById('btnPreviewCopy');
  if (btnCopy) {
    btnCopy.onclick = () => copyRecordEmailBody(rec.id);
  }

  previewBox.style.display = 'block';
  previewBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function copyRecordEmailBody(recId) {
  const rec = reminderCache.records.find(r => r.id === recId);
  if (!rec) return;
  copyTextToClipboard(rec.email_body, `Đã sao chép nội dung email đôn đốc hồ sơ MST ${rec.mst} vào bộ nhớ tạm!`);
}

function copyTextToClipboard(text, successMsg = 'Đã sao chép vào bộ nhớ tạm!') {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(successMsg, 'success');
    }).catch(() => {
      fallbackCopyText(text, successMsg);
    });
  } else {
    fallbackCopyText(text, successMsg);
  }
}

function fallbackCopyText(text, successMsg) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast(successMsg, 'success');
  } catch (err) {
    showToast('Không thể tự động sao chép. Vui lòng copy thủ công.', 'warning');
  }
  document.body.removeChild(ta);
}

async function openRowOutlookReminder(recordId) {
  try {
    showToast('Đang tạo mẫu email nhắc việc qua Outlook...', 'info', 2000);
    const res = await fetch(`/api/reminders/single?id=${recordId}`, { headers: getHeaders() });
    if (!res.ok) {
      showToast('Không tìm thấy thông tin hồ sơ!', 'error');
      return;
    }
    const mailData = await res.json();
    if (!mailData.email) {
      showToast('Cán bộ phụ trách hồ sơ này chưa có địa chỉ email. Mở màn hình đôn đốc để xem nội dung.', 'warning');
      openOutlookReminderModal();
      return;
    }

    // Mở Outlook trực tiếp
    triggerOutlookMailto(mailData.mailto_url, recordId, mailData.officer_name || '', mailData.email, mailData.mst || '');
  } catch (err) {
    showToast('Lỗi khi mở Outlook: ' + err.message, 'error');
  }
}

async function sendOfficerSummaryOutlook() {
  const selectedOfficer = document.getElementById('reminderOfficerSelect')?.value;
  if (!selectedOfficer) {
    showToast('Vui lòng chọn 1 Cán bộ phụ trách trong ô lọc để tạo email đôn đốc tổng hợp!', 'warning', 4000);
    return;
  }

  const mode = document.getElementById('reminderFilterMode')?.value || 'OVERDUE_ONLY';

  try {
    showToast(`Đang tổng hợp các hồ sơ của cán bộ ${selectedOfficer}...`, 'info', 2000);
    const res = await fetch(`/api/reminders/officer_summary?officer=${encodeURIComponent(selectedOfficer)}&mode=${mode}`, {
      headers: getHeaders()
    });
    const summaryMail = await res.json();

    if (!summaryMail.email) {
      showToast(`Cán bộ ${selectedOfficer} chưa có email trong danh mục!`, 'warning');
    }

    // Hiển thị nội dung xem trước
    const previewBox = document.getElementById('emailPreviewBox');
    if (previewBox) {
      document.getElementById('previewToEmail').innerText = summaryMail.email || '(Chưa rõ email)';
      document.getElementById('previewSubject').innerText = summaryMail.subject;
      document.getElementById('previewBody').innerText = summaryMail.full_body;

      const btnOpen = document.getElementById('btnPreviewOpenOutlook');
      if (btnOpen) {
        btnOpen.onclick = () => triggerOutlookMailto(summaryMail.mailto_url, 0, selectedOfficer, summaryMail.email, '');
      }

      const btnCopy = document.getElementById('btnPreviewCopy');
      if (btnCopy) {
        btnCopy.onclick = () => copyTextToClipboard(summaryMail.full_body, `Đã sao chép email tổng hợp cho cán bộ ${selectedOfficer}!`);
      }

      previewBox.style.display = 'block';
      previewBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Kích hoạt mở Outlook
    if (summaryMail.mailto_url) {
      triggerOutlookMailto(summaryMail.mailto_url, 0, selectedOfficer, summaryMail.email, '');
    }
  } catch (err) {
    showToast('Lỗi tạo email tổng hợp: ' + err.message, 'error');
  }
}

// ==================== BƯỚC 5: PHÂN HỆ CẤU HÌNH QUẢN TRỊ ADMIN & ĐỒNG BỘ SAP ====================

let adminState = {
  currentPage: 1,
  pageSize: 50,
  totalPages: 1,
  totalRecords: 0,
  currentRecords: [],
  officersList: [],
  selectedImportB64: null,
  searchTimer: null
};

// ==================== QUẢN LÝ QUYỀN ADMIN, ĐỊNH DANH GÓC & BẢO MẬT ====================

function renderCornerAuthWidget() {
  const container = document.getElementById('cornerAuthContainer');
  if (!container) return;

  if (STATE.isAdminAuthenticated && STATE.adminToken) {
    container.innerHTML = `
      <div class="corner-auth-pill admin-active" title="Phiên Quản trị viên đang kích hoạt">
        <div class="corner-auth-avatar">👑</div>
        <div class="corner-auth-details">
          <span class="corner-auth-name">Quản trị viên (Admin)</span>
          <span class="corner-auth-role" style="color:#059669; font-weight:700;">● Đã xác thực</span>
        </div>
        <div class="corner-auth-actions">
          <button class="corner-auth-action-btn" onclick="openChangePasswordModal()" title="Đổi mật khẩu Quản trị">🔑 Đổi MK</button>
          <button class="corner-auth-action-btn btn-logout" onclick="exitAdminMode()" title="Đăng xuất khỏi quyền Quản trị">🚪 Đăng xuất</button>
        </div>
      </div>
    `;
  } else {
    const displayName = STATE.officerName || STATE.machineAuth.matched_officer_name || 'Công chức';
    const roleName = STATE.deptRole === 'PHONG_KT' ? 'Phòng Kiểm tra' : 'Cán bộ Quản lý';
    container.innerHTML = `
      <div class="corner-auth-pill" title="Hồ sơ công chức nội bộ">
        <div class="corner-auth-avatar">👤</div>
        <div class="corner-auth-details">
          <span class="corner-auth-name">${escapeHtml(displayName)}</span>
          <span class="corner-auth-role">${escapeHtml(roleName)}</span>
        </div>
        <button class="corner-auth-btn-login" onclick="openAdminLoginModal()" title="Đăng nhập tài khoản Quản trị viên">🔑 Đăng nhập Admin</button>
      </div>
    `;
  }
}

async function checkAdminSession() {
  const token = sessionStorage.getItem('hdrr_admin_token');
  if (!token) {
    STATE.isAdminAuthenticated = false;
    STATE.adminToken = '';
    return;
  }
  try {
    const res = await fetch('/api/admin/check_auth', {
      headers: { 'X-Admin-Token': token }
    });
    if (res.ok) {
      const data = await res.json();
      if (data.authenticated) {
        STATE.isAdminAuthenticated = true;
        STATE.adminToken = token;
        STATE.adminPin = token;
      } else {
        STATE.isAdminAuthenticated = false;
        STATE.adminToken = '';
        STATE.adminPin = '';
        sessionStorage.removeItem('hdrr_admin_token');
      }
    }
  } catch (e) {
    console.warn('Lỗi kiểm tra phiên admin:', e);
  }
}

function openAdminModule(btn) {
  if (STATE.isAdminAuthenticated && STATE.adminToken) {
    switchModule('mod_admin', btn || document.getElementById('btnModAdmin'), 'active-mod5');
    return;
  }
  openAdminLoginModal();
}

function openAdminLoginModal() {
  const modal = document.getElementById('adminLoginModal');
  if (!modal) return;
  modal.classList.add('open');
  const err = document.getElementById('adminLoginError');
  if (err) err.style.display = 'none';
  const pass = document.getElementById('adminPasswordInput');
  if (pass) {
    pass.value = '';
    setTimeout(() => pass.focus(), 150);
  }
}

function closeAdminLoginModal() {
  const modal = document.getElementById('adminLoginModal');
  if (modal) modal.classList.remove('open');
}

async function submitAdminLogin() {
  const userInp = document.getElementById('adminUsernameInput');
  const passInp = document.getElementById('adminPasswordInput');
  const errDiv = document.getElementById('adminLoginError');
  const username = (userInp?.value || '').trim();
  const password = (passInp?.value || '').trim();

  if (!username || !password) {
    if (errDiv) {
      errDiv.innerText = 'Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu!';
      errDiv.style.display = 'block';
    }
    return;
  }

  try {
    const res = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (res.ok && data.success && data.token) {
      STATE.adminToken = data.token;
      STATE.adminPin = data.token;
      STATE.isAdminAuthenticated = true;
      sessionStorage.setItem('hdrr_admin_token', data.token);
      closeAdminLoginModal();
      renderCornerAuthWidget();
      showToast('Đăng nhập Quản trị viên thành công! Đã kích hoạt quyền quản trị.', 'success');
      switchModule('mod_admin', document.getElementById('btnModAdmin'), 'active-mod5');
    } else {
      if (errDiv) {
        errDiv.innerText = data.error || 'Tên đăng nhập hoặc mật khẩu không chính xác!';
        errDiv.style.display = 'block';
      }
      if (passInp) {
        passInp.select();
        passInp.focus();
      }
    }
  } catch (err) {
    if (errDiv) {
      errDiv.innerText = 'Lỗi kết nối máy chủ: ' + err.message;
      errDiv.style.display = 'block';
    }
  }
}

function openChangePasswordModal() {
  const modal = document.getElementById('adminChangePassModal');
  if (!modal) return;
  modal.classList.add('open');
  const err = document.getElementById('adminChangePassError');
  if (err) err.style.display = 'none';
  const oldInp = document.getElementById('adminOldPassInput');
  const newInp = document.getElementById('adminNewPassInput');
  const confInp = document.getElementById('adminConfirmPassInput');
  if (oldInp) oldInp.value = '';
  if (newInp) newInp.value = '';
  if (confInp) confInp.value = '';
  setTimeout(() => oldInp?.focus(), 150);
}

function closeChangePasswordModal() {
  const modal = document.getElementById('adminChangePassModal');
  if (modal) modal.classList.remove('open');
}

async function submitChangeAdminPassword() {
  const oldPass = (document.getElementById('adminOldPassInput')?.value || '').trim();
  const newPass = (document.getElementById('adminNewPassInput')?.value || '').trim();
  const confPass = (document.getElementById('adminConfirmPassInput')?.value || '').trim();
  const errDiv = document.getElementById('adminChangePassError');

  if (!oldPass || !newPass) {
    if (errDiv) {
      errDiv.innerText = 'Vui lòng nhập mật khẩu hiện tại và mật khẩu mới!';
      errDiv.style.display = 'block';
    }
    return;
  }

  if (newPass.length < 4) {
    if (errDiv) {
      errDiv.innerText = 'Mật khẩu mới phải có tối thiểu 4 ký tự!';
      errDiv.style.display = 'block';
    }
    return;
  }

  if (newPass !== confPass) {
    if (errDiv) {
      errDiv.innerText = 'Xác nhận mật khẩu mới không khớp!';
      errDiv.style.display = 'block';
    }
    return;
  }

  try {
    const res = await fetch('/api/admin/change_password', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ old_password: oldPass, new_password: newPass })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      closeChangePasswordModal();
      showToast(data.message || 'Đổi mật khẩu Admin thành công!', 'success');
    } else {
      if (errDiv) {
        errDiv.innerText = data.error || 'Đổi mật khẩu thất bại!';
        errDiv.style.display = 'block';
      }
    }
  } catch (err) {
    if (errDiv) {
      errDiv.innerText = 'Lỗi kết nối máy chủ: ' + err.message;
      errDiv.style.display = 'block';
    }
  }
}

async function exitAdminMode() {
  if (STATE.adminToken) {
    try {
      await fetch('/api/admin/logout', {
        method: 'POST',
        headers: { 'X-Admin-Token': STATE.adminToken }
      });
    } catch (e) {}
  }
  STATE.adminToken = '';
  STATE.adminPin = '';
  STATE.isAdminAuthenticated = false;
  sessionStorage.removeItem('hdrr_admin_token');
  renderCornerAuthWidget();
  showToast('Đã đăng xuất khỏi tài khoản Quản trị viên', 'info');
  switchModule('mod_dashboard', document.getElementById('btnModDashboard'), 'active-mod0');
}

function switchAdminSubtab(tabKey, btn) {
  const tabNnt = document.getElementById('admin_subtab_nnt');
  const tabSap = document.getElementById('admin_subtab_sap');
  const tabAudit = document.getElementById('admin_subtab_audit');

  document.querySelectorAll('.admin-subtab-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  if (tabNnt) tabNnt.style.display = 'none';
  if (tabSap) tabSap.style.display = 'none';
  if (tabAudit) tabAudit.style.display = 'none';

  if (tabKey === 'admin_nnt') {
    if (tabNnt) tabNnt.style.display = 'block';
    loadAdminKpis();
    loadAdminNntList(1);
  } else if (tabKey === 'admin_sap') {
    if (tabSap) tabSap.style.display = 'block';
    loadSapConfig();
  } else if (tabKey === 'admin_audit') {
    if (tabAudit) tabAudit.style.display = 'block';
    loadStealthLogs();
  }
}

// 2. Quản lý Danh mục NNT & Cán bộ Quản lý (Tab 1)
async function loadAdminKpis() {
  try {
    const res = await fetch('/api/admin/kpis', { headers: getHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('adminKpiTotalNnt').innerText = fmtNum(data.total_nnt);
    document.getElementById('adminKpiWithEmail').innerText = fmtNum(data.with_email);
    document.getElementById('adminKpiWithoutEmail').innerText = fmtNum(data.without_email);
    document.getElementById('adminKpiOfficers').innerText = fmtNum(data.distinct_officers);
  } catch (err) {
    console.error('Lỗi tải KPI Admin:', err);
  }
}

async function loadAdminNntList(page = 1) {
  adminState.currentPage = Math.max(1, page);
  const rawQ = (document.getElementById('adminNntSearchInput')?.value || '').trim();
  const offFilter = document.getElementById('adminNntOfficerFilter')?.value || '';

  const clearBtn = document.getElementById('btnClearAdminNntSearch');
  if (clearBtn) clearBtn.style.display = rawQ ? 'block' : 'none';

  try {
    const res = await fetch(
      `/api/admin/nnt/list?page=${adminState.currentPage}&limit=${adminState.pageSize}&search=${encodeURIComponent(rawQ)}&officer=${encodeURIComponent(offFilter)}`,
      { headers: getHeaders() }
    );
    if (!res.ok) {
      if (res.status === 403) openAdminLoginModal();
      return;
    }
    const data = await res.json();
    adminState.totalRecords = data.total_records;
    adminState.totalPages = data.total_pages;
    adminState.currentRecords = data.records || [];
    adminState.officersList = data.officers || [];

    // Cập nhật dropdown lọc Cán bộ
    const offSelect = document.getElementById('adminNntOfficerFilter');
    if (offSelect && !offFilter) {
      const curVal = offSelect.value;
      offSelect.innerHTML =
        '<option value="">-- Tất cả cán bộ quản lý --</option>' +
        data.officers.map(o => `<option value="${o}" ${o === curVal ? 'selected' : ''}>${o}</option>`).join('');
    }

    renderAdminNntRows(data.records);

    // Cập nhật thanh phân trang
    const startIdx = (adminState.currentPage - 1) * adminState.pageSize + 1;
    const endIdx = Math.min(adminState.totalRecords, startIdx + data.records.length - 1);
    document.getElementById('adminNntPaginationInfo').innerText =
      adminState.totalRecords > 0
        ? `Hiển thị ${fmtNum(startIdx)} - ${fmtNum(endIdx)} trong tổng số ${fmtNum(adminState.totalRecords)} doanh nghiệp`
        : 'Không có dữ liệu';
    document.getElementById('adminNntPageIndicator').innerText = `Trang ${adminState.currentPage} / ${adminState.totalPages}`;
    document.getElementById('btnAdminPrevPage').disabled = adminState.currentPage <= 1;
    document.getElementById('btnAdminNextPage').disabled = adminState.currentPage >= adminState.totalPages;
  } catch (err) {
    showToast('Lỗi tải danh mục doanh nghiệp: ' + err.message, 'error');
  }
}

function renderAdminNntRows(records) {
  const tbody = document.getElementById('tbodyAdminNnt');
  if (!tbody) return;

  if (!records || !records.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:35px; color:#64748b; font-size:13px;">
      🔍 Không tìm thấy người nộp thuế nào phù hợp với điều kiện tìm kiếm.
    </td></tr>`;
    return;
  }

  const startIdx = (adminState.currentPage - 1) * adminState.pageSize;
  tbody.innerHTML = records.map((r, idx) => {
    const hasEmail = Boolean(r.email_cbql);
    return `
      <tr>
        <td style="text-align:center; font-weight:700; color:#64748b;">${startIdx + idx + 1}</td>
        <td><code style="font-weight:900; color:#0f172a; font-size:13px;">${r.mst}</code></td>
        <td style="font-weight:600; color:#1e293b;">${r.ten_nnt || '<i style="color:#94a3b8;">(Chưa cập nhật tên)</i>'}</td>
        <td>
          <div style="font-weight:700; color:#0f172a;">👤 ${r.can_bo_quan_ly || '<span style="color:#ef4444;">Chưa phân công</span>'}</div>
        </td>
        <td>
          ${hasEmail 
            ? `<a href="mailto:${r.email_cbql}" style="color:#2563eb; font-weight:600; text-decoration:none;">✉️ ${r.email_cbql}</a>` 
            : `<span class="badge" style="background:#fee2e2; color:#b91c1c; font-size:11px;">Thiếu email</span>`}
        </td>
        <td style="color:#475569; font-size:12px;">${r.dia_chi || '-'}</td>
        <td style="text-align:center;">
          <div style="display:flex; gap:4px; justify-content:center;">
            <button class="btn btn-outline" style="padding:3px 7px; font-size:11px;" onclick="openEditNntModal('${r.mst}')" title="Chỉnh sửa thông tin doanh nghiệp và cán bộ quản lý">✏️ Sửa</button>
            <button class="btn btn-outline" style="padding:3px 7px; font-size:11px; color:#dc2626; border-color:#fca5a5;" onclick="deleteNntRecord('${r.mst}')" title="Xóa khỏi danh mục">🗑️</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function debouncedSearchAdminNnt() {
  clearTimeout(adminState.searchTimer);
  adminState.searchTimer = setTimeout(() => {
    loadAdminNntList(1);
  }, 200);
}

function clearAdminNntSearch() {
  const inp = document.getElementById('adminNntSearchInput');
  if (inp) inp.value = '';
  document.getElementById('btnClearAdminNntSearch').style.display = 'none';
  loadAdminNntList(1);
}

function changeAdminNntPage(delta) {
  const newPage = adminState.currentPage + delta;
  if (newPage >= 1 && newPage <= adminState.totalPages) {
    loadAdminNntList(newPage);
  }
}

function openAddNntModal() {
  document.getElementById('nntEditModalTitle').innerText = 'Thêm Mới Người Nộp Thuế & Phân Công Cán Bộ Quản Lý';
  const mstInp = document.getElementById('mdNntMst');
  mstInp.value = '';
  mstInp.readOnly = false;
  mstInp.style.background = '#fff';
  document.getElementById('mdNntTen').value = '';
  document.getElementById('mdNntCbql').value = '';
  document.getElementById('mdNntEmail').value = '';
  document.getElementById('mdNntDiaChi').value = '';
  document.getElementById('nntEditModal').classList.add('open');
  setTimeout(() => mstInp.focus(), 150);
}

function openEditNntModal(mst) {
  const r = adminState.currentRecords.find(x => x.mst === mst);
  if (!r) return;
  document.getElementById('nntEditModalTitle').innerText = `Chỉnh Sửa Doanh Nghiệp - Mã số thuế: ${mst}`;
  const mstInp = document.getElementById('mdNntMst');
  mstInp.value = r.mst;
  mstInp.readOnly = true;
  mstInp.style.background = '#e2e8f0';
  document.getElementById('mdNntTen').value = r.ten_nnt || '';
  document.getElementById('mdNntCbql').value = r.can_bo_quan_ly || '';
  document.getElementById('mdNntEmail').value = r.email_cbql || '';
  document.getElementById('mdNntDiaChi').value = r.dia_chi || '';
  document.getElementById('nntEditModal').classList.add('open');
}

function closeNntEditModal() {
  document.getElementById('nntEditModal').classList.remove('open');
}

function autoSuggestOfficerEmail(officerName) {
  const emailInp = document.getElementById('mdNntEmail');
  if (!emailInp || emailInp.value.trim()) return;
  const match = adminState.currentRecords.find(
    r => (r.can_bo_quan_ly || '').toLowerCase() === officerName.trim().toLowerCase() && r.email_cbql
  );
  if (match) {
    emailInp.value = match.email_cbql;
  }
}

async function saveNntRecord() {
  const mst = (document.getElementById('mdNntMst')?.value || '').trim();
  const ten = (document.getElementById('mdNntTen')?.value || '').trim();
  const cb = (document.getElementById('mdNntCbql')?.value || '').trim();
  const em = (document.getElementById('mdNntEmail')?.value || '').trim();
  const dc = (document.getElementById('mdNntDiaChi')?.value || '').trim();

  if (!mst) {
    showToast('Vui lòng nhập Mã số thuế!', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/admin/nnt/save', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ mst, ten_nnt: ten, can_bo_quan_ly: cb, email_cbql: em, dia_chi: dc })
    });
    if (!res.ok) {
      showToast('Lỗi lưu thông tin doanh nghiệp!', 'error');
      return;
    }
    showToast(`Đã lưu thành công Doanh nghiệp - MST ${mst}!`, 'success');
    closeNntEditModal();
    loadAdminKpis();
    loadAdminNntList(adminState.currentPage);
  } catch (err) {
    showToast('Lỗi lưu thông tin doanh nghiệp: ' + err.message, 'error');
  }
}

async function deleteNntRecord(mst) {
  if (!confirm(`Bạn có chắc chắn muốn xóa Doanh nghiệp - Mã số thuế ${mst} khỏi danh mục?`)) return;
  try {
    const res = await fetch('/api/admin/nnt/delete', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ mst })
    });
    if (!res.ok) {
      showToast('Lỗi xóa doanh nghiệp!', 'error');
      return;
    }
    showToast(`Đã xóa thành công Doanh nghiệp - MST ${mst}!`, 'info');
    loadAdminKpis();
    loadAdminNntList(adminState.currentPage);
  } catch (err) {
    showToast('Lỗi xóa doanh nghiệp: ' + err.message, 'error');
  }
}

function exportAdminNntExcel() {
  showToast('Đang kết xuất danh mục doanh nghiệp ra file Excel...', 'info');
  window.open(`/api/admin/nnt/export?pin=${encodeURIComponent(STATE.adminPin)}`, '_blank');
}

function downloadNntTemplate() {
  window.open('/api/admin/nnt/template', '_blank');
}

// 3. Import File Excel Danh mục NNT
function openImportNntModal() {
  adminState.selectedImportB64 = null;
  const fileInp = document.getElementById('excelImportFileInput');
  if (fileInp) fileInp.value = '';
  const alertBox = document.getElementById('importExcelPreviewAlert');
  if (alertBox) alertBox.style.display = 'none';
  const btn = document.getElementById('btnExecuteNntImport');
  if (btn) btn.disabled = true;
  document.getElementById('nntImportModal').classList.add('open');
}

function closeNntImportModal() {
  document.getElementById('nntImportModal').classList.remove('open');
}

async function handleAdminExcelSelected(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  const alertBox = document.getElementById('importExcelPreviewAlert');
  const btn = document.getElementById('btnExecuteNntImport');

  try {
    adminState.selectedImportB64 = await fileToBase64(file);
    alertBox.style.display = 'block';
    alertBox.style.background = '#eff6ff';
    alertBox.style.color = '#1e40af';
    alertBox.style.border = '1px solid #93c5fd';
    alertBox.innerHTML = `📄 <b>Đã chọn file:</b> ${file.name} (${Math.round(file.size / 1024)} KB). Sẵn sàng nạp dữ liệu.`;
    btn.disabled = false;
  } catch (err) {
    showToast('Lỗi đọc file Excel: ' + err.message, 'error');
  }
}

async function executeNntExcelImport() {
  if (!adminState.selectedImportB64) {
    showToast('Vui lòng chọn file Excel!', 'warning');
    return;
  }

  const mode = document.querySelector('input[name="nntImportMode"]:checked')?.value || 'upsert';
  if (mode === 'replace') {
    const ok = confirm('⚠️ CẢNH BÁO QUAN TRỌNG:\nBạn đang chọn chế độ "GHI ĐÈ TOÀN BỘ". Toàn bộ danh mục doanh nghiệp hiện có sẽ bị xóa và thay thế bằng file Excel này.\n\nBạn có chắc chắn muốn thực hiện?');
    if (!ok) return;
  }

  const btn = document.getElementById('btnExecuteNntImport');
  btn.disabled = true;
  btn.innerText = '⏳ Đang nạp dữ liệu Excel...';

  try {
    const res = await fetch('/api/admin/nnt/import', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        file_b64: adminState.selectedImportB64,
        mode: mode
      })
    });
    const data = await res.json();

    if (!res.ok) {
      showToast('Lỗi nạp Excel: ' + (data.error || 'Thao tác thất bại'), 'error', 6000);
      btn.disabled = false;
      btn.innerText = '🚀 Bắt Đầu Nạp Dữ Liệu';
      return;
    }

    showToast(data.message, 'success', 6000);
    closeNntImportModal();
    loadAdminKpis();
    loadAdminNntList(1);
    refreshData(); // Cập nhật lại toàn bộ ứng dụng chính
  } catch (err) {
    showToast('Lỗi nạp Excel: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = '🚀 Bắt Đầu Nạp Dữ Liệu';
  }
}

// 4. Slot Tự Động Hóa Ứng Dụng SAP (Tab 2)
async function loadSapConfigToUi() {
  try {
    const res = await fetch('/api/admin/sap/config', { headers: getHeaders() });
    if (!res.ok) return;
    const cfg = await res.json();

    document.getElementById('sapSystemId').value = cfg.sap_system_id || 'PRD_TMS';
    document.getElementById('sapClient').value = cfg.sap_client || '100';
    document.getElementById('sapTcode').value = cfg.sap_tcode || 'Z_QLNNT_CBQL';
    document.getElementById('sapScriptType').value = cfg.script_type || 'simulation_test';
    document.getElementById('sapExternalPath').value = cfg.external_script_path || '';
    document.getElementById('sapAutoIngest').checked = Boolean(cfg.auto_ingest_to_db);
    document.getElementById('sapIngestMode').value = cfg.ingest_mode || 'upsert';
    document.getElementById('sapCustomScriptCode').value = cfg.custom_script_code || '';

    const badge = document.getElementById('sapLastSyncBadge');
    if (badge) {
      if (cfg.last_sync_status === 'THÀNH_CÔNG') {
        badge.className = 'badge badge-done';
        badge.innerText = `Thành công (${cfg.last_sync_time || '-'})`;
      } else if (cfg.last_sync_status === 'LỖI') {
        badge.className = 'badge badge-pending';
        badge.innerText = `Lỗi (${cfg.last_sync_time || '-'})`;
      } else {
        badge.className = 'badge';
        badge.innerText = 'Chưa chạy';
      }
    }

    onSapScriptTypeChanged();
  } catch (err) {
    console.error('Lỗi tải cấu hình SAP:', err);
  }
}

function onSapScriptTypeChanged() {
  const type = document.getElementById('sapScriptType')?.value;
  const extBox = document.getElementById('sapExternalFileBox');
  const codeBox = document.getElementById('sapCodeEditorBox');

  if (type === 'external_file') {
    if (extBox) extBox.style.display = 'block';
    if (codeBox) codeBox.style.display = 'none';
  } else if (type === 'simulation_test') {
    if (extBox) extBox.style.display = 'none';
    if (codeBox) codeBox.style.display = 'block';
  } else {
    if (extBox) extBox.style.display = 'none';
    if (codeBox) codeBox.style.display = 'block';
  }
}

const SAMPLE_PYTHON_TEMPLATE = `# ==============================================================================
# KỊCH BẢN TỰ ĐỘNG HÓA SAP GUI SCRIPTING (PYTHON WIN32COM)
# Nhiệm vụ: Tự động kết nối phiên SAP đang mở, chạy T-Code tra cứu
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
        application = sap_gui_auto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
        logs.append(f"[SAP-INFO] Đã kết nối Session: {session.Info.SystemName} / Client {session.Info.Client}")
        
        # Mở T-Code tra cứu danh bạ phân công NNT & CBQL
        tcode = "/nZ_QLNNT_CBQL"
        session.findById("wnd[0]/tbar[0]/okcd").text = tcode
        session.findById("wnd[0]").sendVKey(0)
        
        # Thực thi tìm kiếm (F8 / Execute)
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        logs.append("[SAP-INFO] Trích xuất thành công danh bạ từ SAP Grid.")
    except Exception as e:
        logs.append(f"[SAP-ERROR] Lỗi thực thi SAP GUI Scripting: {e}")
        
    print(json.dumps({"status": "success", "logs": logs, "records": records}, ensure_ascii=False))

if __name__ == "__main__":
    run_sap_extraction()
`;

const SAMPLE_VBS_TEMPLATE = `' ==============================================================================
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

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nSE16N"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtGD-TAB").text = "ZTAX_NNT_CBQL"
session.findById("wnd[0]/tbar[1]/btn[8]").press
`;

function loadSapSamplePython() {
  document.getElementById('sapScriptType').value = 'inline_python';
  document.getElementById('sapCustomScriptCode').value = SAMPLE_PYTHON_TEMPLATE;
  onSapScriptTypeChanged();
  showToast('Đã nạp mẫu Python SAP GUI Scripting!', 'info');
}

function loadSapSampleVbs() {
  document.getElementById('sapScriptType').value = 'inline_vbs';
  document.getElementById('sapCustomScriptCode').value = SAMPLE_VBS_TEMPLATE;
  onSapScriptTypeChanged();
  showToast('Đã nạp mẫu VBScript SAP GUI Script Recorder!', 'info');
}

function clearSapScriptCode() {
  document.getElementById('sapCustomScriptCode').value = '';
}

async function saveSapConfig() {
  const payload = {
    sap_system_id: document.getElementById('sapSystemId')?.value.trim(),
    sap_client: document.getElementById('sapClient')?.value.trim(),
    sap_tcode: document.getElementById('sapTcode')?.value.trim(),
    script_type: document.getElementById('sapScriptType')?.value,
    external_script_path: document.getElementById('sapExternalPath')?.value.trim(),
    auto_ingest_to_db: document.getElementById('sapAutoIngest')?.checked,
    ingest_mode: document.getElementById('sapIngestMode')?.value,
    custom_script_code: document.getElementById('sapCustomScriptCode')?.value
  };

  try {
    const res = await fetch('/api/admin/sap/config', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      showToast('Lỗi lưu cấu hình SAP!', 'error');
      return;
    }
    showToast('Đã lưu cấu hình kết nối SAP thành công!', 'success');
  } catch (err) {
    showToast('Lỗi lưu cấu hình SAP: ' + err.message, 'error');
  }
}

async function runSapSyncNow() {
  const btn = document.getElementById('btnRunSapSync');
  const consoleBox = document.getElementById('sapConsoleOutput');
  const badge = document.getElementById('sapLastSyncBadge');

  btn.disabled = true;
  btn.innerText = '⏳ Đang kết nối SAP & chạy kịch bản...';
  consoleBox.innerText = `[${new Date().toLocaleTimeString()}] Đang khởi tạo môi trường kịch bản SAP...\n`;

  const override_config = {
    sap_system_id: document.getElementById('sapSystemId')?.value.trim(),
    sap_client: document.getElementById('sapClient')?.value.trim(),
    sap_tcode: document.getElementById('sapTcode')?.value.trim(),
    script_type: document.getElementById('sapScriptType')?.value,
    external_script_path: document.getElementById('sapExternalPath')?.value.trim(),
    auto_ingest_to_db: document.getElementById('sapAutoIngest')?.checked,
    ingest_mode: document.getElementById('sapIngestMode')?.value,
    custom_script_code: document.getElementById('sapCustomScriptCode')?.value
  };

  try {
    const res = await fetch('/api/admin/sap/run', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ override_config })
    });
    const result = await res.json();

    if (result.logs && result.logs.length) {
      consoleBox.innerText = result.logs.join('\n');
    }

    if (result.status === 'success') {
      badge.className = 'badge badge-done';
      badge.innerText = `Thành công (${new Date().toLocaleTimeString()})`;
      showToast(result.message, 'success', 6000);
      loadAdminKpis();
      loadAdminNntList(1);
      refreshData(); // Đồng bộ toàn bộ dữ liệu ứng dụng ngay lập tức
    } else {
      badge.className = 'badge badge-pending';
      badge.innerText = `Lỗi (${new Date().toLocaleTimeString()})`;
      showToast('Đồng bộ SAP gặp lỗi: ' + result.message, 'error', 6000);
    }
  } catch (err) {
    consoleBox.innerText += `\n[LỖI HTTP] Không thể giao tiếp với máy chủ: ${err.message}`;
    showToast('Lỗi kích hoạt SAP: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = '🚀 Kích Hoạt Chạy Script SAP Đồng Bộ Ngay';
  }
}

function clearSapConsole() {
  document.getElementById('sapConsoleOutput').innerText = '(Nhật ký đã xóa. Sẵn sàng cho lần chạy tiếp theo...)';
}

window.addEventListener('DOMContentLoaded', initEngine);


// ==================== BỘ ĐỆM GHI CÁ NHÂN & HÀNG CHỜ ĐỒNG BỘ CSDL DÙNG CHUNG ====================

async function checkSyncQueueStatus() {
  try {
    const res = await fetch('/api/sync/status', { headers: getHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const badge = document.getElementById('syncQueueBadge');
    const textEl = document.getElementById('syncQueueText');
    if (!badge || !textEl) return;

    const userPending = data.user_pending || 0;
    const totalPending = data.total_system_pending || 0;

    if (userPending > 0) {
      badge.className = 'sync-badge sync-badge-pending';
      textEl.innerText = `Chờ ghi CSDL (${userPending})`;
      badge.title = `Có ${userPending} bản ghi đang nằm trong bộ đệm cá nhân chờ CSDL rảnh để tự động ghi. Bấm để thử ghi ngay!`;
    } else if (totalPending > 0) {
      badge.className = 'sync-badge sync-badge-pending';
      textEl.innerText = `CSDL đang bận (${totalPending} chờ)`;
      badge.title = `Hệ thống có ${totalPending} bản ghi đang chờ ghi. Bấm để kích hoạt đồng bộ!`;
    } else {
      badge.className = 'sync-badge sync-badge-clean';
      textEl.innerText = 'CSDL Dùng Chung: Đồng bộ';
      badge.title = 'CSDL dùng chung đã đồng bộ 100%. Bộ đệm cá nhân đã xóa sạch nhẹ máy. Bấm để kiểm tra lại.';
    }
  } catch (e) {}
}

async function triggerManualSync() {
  const textEl = document.getElementById('syncQueueText');
  if (textEl) textEl.innerText = 'Đang kiểm tra CSDL...';
  try {
    const res = await fetch('/api/sync/flush', { method: 'POST', headers: getHeaders() });
    const data = await res.json();
    if (data.total_pending === 0) {
      showToast('CSDL dùng chung đã rảnh và đồng bộ 100%!', 'success');
    } else {
      showToast(`Đang xếp hàng ${data.total_pending} bản ghi. Đang tự động thử lại...`, 'warning');
    }
  } catch (err) {
    showToast('Không thể kết nối trạm máy chủ: ' + err.message, 'error');
  } finally {
    checkSyncQueueStatus();
    refreshData();
  }
}


// ==================== TẢI TRỌN BỘ DỮ LIỆU DẠNG FILE ZIP ====================

function downloadRecordBundleZip(id) {
  if (!id) {
    showToast('Vui lòng chọn một hồ sơ cụ thể để tải trọn bộ!', 'warning');
    return;
  }
  showToast('Đang gom trọn bộ công văn, thông báo, biên bản & giải trình...', 'info', 4000);
  window.location.href = `/api/dsrr/bundle_zip?id=${encodeURIComponent(id)}`;
}

function downloadAllSharePdfZip() {
  showToast('Đang nén toàn bộ kho tài liệu PDF SharePdf...', 'info', 5000);
  window.location.href = '/api/sharepdf/download_all_zip';
}


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
