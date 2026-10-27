with open('app/static/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update onActionTypeChanged
old_action_changed = """function onActionTypeChanged() {
  const actionType = document.getElementById('md_action_type')?.value || '';
  const boxOther = document.getElementById('boxActionOther');
  const boxTb = document.getElementById('boxTbDetails');

  if (boxOther) {
    boxOther.style.display = (actionType === 'Khác') ? 'block' : 'none';
  }
  if (boxTb) {
    boxTb.style.display = (actionType === 'Thông báo giải trình') ? 'block' : 'none';
  }
}"""

new_action_changed = """function onActionTypeChanged() {
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
}"""

assert old_action_changed in code, "old_action_changed not found"
code = code.replace(old_action_changed, new_action_changed, 1)

# 2. Update handleScanPdf in Step 1 (CVRR)
old_handle_scan = """  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      so_ky_hieu: document.getElementById('th_so_kh').value || 'CB'
    })
  });"""

new_handle_scan = """  const mstVal = document.getElementById('th_mst_rr')?.value || document.getElementById('th_mst_lq')?.value || '';
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
  });"""

assert old_handle_scan in code, "old_handle_scan not found"
code = code.replace(old_handle_scan, new_handle_scan, 1)

# 3. Update handleUploadResultPdf and add handleUploadTbgtPdf, handleUploadBblvPdf, handleUploadPktPdf
old_upload_res = """async function handleUploadResultPdf(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  showToast(`Đang tải file lên SharePdf: ${file.name}...`, 'info');
  const b64 = await fileToBase64(file);
  const mst = document.getElementById('md_mst').value || 'KQ';
  const res = await fetch('/api/ingest/pdf', {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      filename: file.name,
      file_b64: b64,
      so_ky_hieu: `KQ_${mst}`
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
    showToast(`Đã lưu file PDF kết quả vào ${out.stored_name}`, 'success');
    await refreshData();
  } else {
    showToast('Không thể lưu file PDF kết quả', 'error');
  }
}"""

new_upload_handlers = """async function handleUploadResultPdf(input) {
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
}"""

assert old_upload_res in code, "old_upload_res not found"
code = code.replace(old_upload_res, new_upload_handlers, 1)

# 4. Update openDsrrModal to bind TBGT, BBLV, PKT
old_open_dsrr_pdf = """    // File PDF kết quả
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
      if (pdfLink) {
        pdfLink.innerText = '';
        pdfLink.href = '#';
      }
    }"""

new_open_dsrr_pdf = """    // File PDF kết quả giải trình (GTDN)
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
    }"""

assert old_open_dsrr_pdf in code, "old_open_dsrr_pdf not found"
code = code.replace(old_open_dsrr_pdf, new_open_dsrr_pdf, 1)

# 5. Update saveDsrrUpdate payload to include tbgt_pdf_name, bblv_pdf_name, pkt_pdf_name, noi_dung_pkt_phan_hoi
old_save_payload_result_pdf = """    result_pdf_name: document.getElementById('md_result_pdf').value,"""
new_save_payload_result_pdf = """    result_pdf_name: document.getElementById('md_result_pdf')?.value || '',
    tbgt_pdf_name: document.getElementById('md_tbgt_pdf')?.value || '',
    bblv_pdf_name: document.getElementById('md_bblv_pdf')?.value || '',
    pkt_pdf_name: document.getElementById('md_pkt_pdf')?.value || '',
    noi_dung_pkt_phan_hoi: document.getElementById('md_pkt_noi_dung')?.value || '',"""

assert old_save_payload_result_pdf in code, "old_save_payload_result_pdf not found"
code = code.replace(old_save_payload_result_pdf, new_save_payload_result_pdf, 1)

# 6. Add downloadRecordBundleZip and downloadAllSharePdfZip
zip_functions = """

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
"""

code += zip_functions

with open('app/static/app.js', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated app.js workflow handlers successfully!")
