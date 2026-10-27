with open('app/static/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

target = '<button class="btn btn-outline" onclick="refreshData()">'
replacement = '''<div id="syncQueueBadge" class="sync-badge sync-badge-clean" onclick="triggerManualSync()" title="Trạng thái hàng chờ ghi CSDL dùng chung. Bấm để kích hoạt đồng bộ ngay.">
        <span class="sync-dot"></span>
        <span id="syncQueueText">CSDL Dùng Chung: Đồng bộ</span>
      </div>
      <button class="btn btn-outline" onclick="refreshData()">'''

if target in c:
    c = c.replace(target, replacement, 1)
    with open('app/static/index.html', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Updated index.html successfully!")
else:
    print("Target not found in index.html!")
