with open('app/static/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update saveDsrrUpdate response handling
old_dsrr_save = """  const res = await fetch('/api/dsrr/update', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    showToast(`Đã cập nhật thành công kết quả xử lý Hồ sơ #${payload.id}`, 'success');
    closeDsrrModal();
    await refreshData();
  } else {
    showToast('Lỗi cập nhật hồ sơ!', 'error');
  }"""

new_dsrr_save = """  const res = await fetch('/api/dsrr/update', {
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
  }"""

assert old_dsrr_save in code, "old_dsrr_save not found in app.js"
code = code.replace(old_dsrr_save, new_dsrr_save, 1)

# 2. Update th/create response handling
old_th_save = """  const res = await fetch('/api/th/create', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });
  const out = await res.json();
  STATE.pendingAttachment = { name: '', sha256: '' };

  if (out.lien_quan_qldn1) {
    showToast(
      `✅ Đã tiếp nhận văn bản (#${out.th_id}) và TỰ ĐỘNG CHUYỂN SANG BƯỚC 2 (Hồ sơ #${out.dsrr_id}) cho Cán bộ ${out.can_bo_xu_ly || 'phụ trách'}!`,
      'success',
      6000
    );
    // Reset form inputs
    document.getElementById('th_mst_rr').value = '';
    document.getElementById('th_ten_rr').value = '';
    document.getElementById('th_mst_lq').value = '';
    document.getElementById('th_ten_lq').value = '';
    document.getElementById('th_can_bo_lq').value = '';
    document.getElementById('th_pdf_name').value = '';
    document.getElementById('mstLqHint').innerText = '';
  } else {
    showToast(`Đã lưu tiếp nhận văn bản (#${out.th_id})!`, 'success');
  }

  await refreshData();"""

new_th_save = """  const res = await fetch('/api/th/create', {
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
  await refreshData();"""

assert old_th_save in code, "old_th_save not found in app.js"
code = code.replace(old_th_save, new_th_save, 1)

# 3. Add checkSyncQueueStatus & triggerManualSync to app.js
sync_functions = """

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
"""

code += sync_functions

# 4. In initEngine, call checkSyncQueueStatus and set interval
old_init_tail = """    applyRoleVisibility();
    await refreshData();
  } catch (err) {
    showToast('Lỗi khi kết nối máy chủ: ' + err.message, 'error');
  }"""

new_init_tail = """    applyRoleVisibility();
    await refreshData();
    checkSyncQueueStatus();
    setInterval(checkSyncQueueStatus, 8000);
  } catch (err) {
    showToast('Lỗi khi kết nối máy chủ: ' + err.message, 'error');
  }"""

assert old_init_tail in code, "old_init_tail not found in app.js"
code = code.replace(old_init_tail, new_init_tail, 1)

with open('app/static/app.js', 'w', encoding='utf-8') as f:
    f.write(code)

print("Integrated sync queue UI into app.js successfully!")
