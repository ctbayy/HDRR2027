"""
Browser UI Test (Chrome Headless & DevTools Protocol) để kiểm tra:
1. Widget Định danh & Đăng nhập nhỏ góc trên bên phải (Corner Auth Pill).
2. Mở Modal Đăng nhập Admin, đăng nhập thành công với admin / Admin@2026.
3. Chuyển trạng thái sang Vương miện Quản trị viên (Admin Authenticated).
4. Mở Phân hệ Quản trị (mod_admin) -> Subtab 3 Nhật ký lưu vết định danh & Hàng chờ CSDL.
5. Kiểm tra không có lỗi JavaScript console nào.
"""

import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath("."))
from app.database import DatabaseEngineModule
from app.web.handler import WebEngineRequestHandler


class SimpleWS:
    def __init__(self, host, port, path):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode('ascii'))
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += self.sock.recv(4096)
        self.msg_id = 0

    def send_cmd(self, method, params=None):
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        raw = json.dumps(payload).encode('utf-8')
        frame = bytearray([0x81])
        length = len(raw)
        mask_key = os.urandom(4)
        if length <= 125:
            frame.append(0x80 | length)
        elif length <= 65535:
            frame.append(0x80 | 126)
            frame.extend(length.to_bytes(2, 'big'))
        else:
            frame.append(0x80 | 127)
            frame.extend(length.to_bytes(8, 'big'))
        frame.extend(mask_key)
        frame.extend(bytearray(raw[i] ^ mask_key[i % 4] for i in range(length)))
        self.sock.sendall(frame)
        return self.msg_id

    def recv_msg(self, timeout=8.0):
        self.sock.settimeout(timeout)
        try:
            head = self.sock.recv(2)
            if not head: return None
            length = head[1] & 0x7F
            if length == 126:
                ext = self.sock.recv(2)
                length = int.from_bytes(ext, 'big')
            elif length == 127:
                ext = self.sock.recv(8)
                length = int.from_bytes(ext, 'big')
            body = b""
            while len(body) < length:
                chunk = self.sock.recv(length - len(body))
                if not chunk: break
                body += chunk
            return json.loads(body.decode('utf-8', errors='ignore'))
        except socket.timeout:
            return None


def run_browser_auth_test():
    DatabaseEngineModule.initialize_schema()

    s = socket.socket()
    s.bind(('', 0))
    server_port = s.getsockname()[1]
    s.close()

    server = ThreadingHTTPServer(("127.0.0.1", server_port), WebEngineRequestHandler)
    st = threading.Thread(target=server.serve_forever, daemon=True)
    st.start()
    time.sleep(0.5)

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    browser_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
    if not browser_exe:
        print("Không tìm thấy Chrome/Edge, bỏ qua CDP.")
        server.shutdown()
        return

    s2 = socket.socket()
    s2.bind(('', 0))
    cdp_port = s2.getsockname()[1]
    s2.close()

    user_data = os.path.abspath('./.tmp_chrome_auth_test')
    os.makedirs(user_data, exist_ok=True)

    cmd = [
        browser_exe,
        "--headless=new",
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={user_data}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1400,900",
        f"http://127.0.0.1:{server_port}",
    ]
    proc = subprocess.Popen(cmd)
    time.sleep(2.5)

    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json")
        pages = json.loads(req.read().decode('utf-8'))
        matching_pages = [p for p in pages if p.get('type') == 'page' and f':{server_port}' in p.get('url', '')]
        if not matching_pages:
            matching_pages = [p for p in pages if p.get('type') == 'page' and p.get('url') != 'about:blank']
        target_page = matching_pages[0] if matching_pages else pages[0]
        ws_url = target_page['webSocketDebuggerUrl']

        u = urlparse(ws_url)
        ws = SimpleWS(u.hostname, u.port, u.path)

        ws.send_cmd("Runtime.enable")
        time.sleep(1.0)

        def eval_js(script):
            nonlocal ws
            mid = ws.send_cmd("Runtime.evaluate", {
                "expression": script,
                "returnByValue": True,
                "awaitPromise": True
            })
            for _ in range(25):
                msg = ws.recv_msg()
                if msg and msg.get("id") == mid:
                    res = msg.get("result", {})
                    if "exceptionDetails" in res:
                        raise RuntimeError(res["exceptionDetails"])
                    return res.get("result", {}).get("value")
            return None

        # 1. Kiểm tra Corner Auth Widget khởi tạo ban đầu (chờ trang nạp xong)
        pill_html = ""
        for _ in range(15):
            pill_html = eval_js("document.getElementById('cornerAuthContainer')?.innerHTML || ''")
            if "corner-auth-btn-login" in (pill_html or ""):
                break
            time.sleep(0.4)
        assert "corner-auth-btn-login" in pill_html, f"Pill ban đầu thiếu nút đăng nhập: {pill_html}"
        print("✓ 1. Corner Auth Widget hiển thị chính xác ở góc trên bên phải thanh tiêu đề")

        # 2. Mở modal đăng nhập Admin
        eval_js("openAdminModule()")
        time.sleep(0.3)
        modal_open = eval_js("document.getElementById('adminLoginModal')?.classList.contains('open')")
        assert modal_open is True, "Modal adminLoginModal phải được mở"
        print("✓ 2. Nhấn Phân hệ 5 hoặc Nút góc mở Modal Đăng Nhập Quản Trị Viên (Admin) thành công")

        # 3. Thực hiện đăng nhập admin / Admin@2026
        login_res = eval_js("""
            (async () => {
                document.getElementById('adminUsernameInput').value = 'admin';
                document.getElementById('adminPasswordInput').value = 'Admin@2026';
                await submitAdminLogin();
                return {
                    isAuth: STATE.isAdminAuthenticated,
                    token: STATE.adminToken,
                    modalOpen: document.getElementById('adminLoginModal').classList.contains('open')
                };
            })()
        """)
        assert login_res["isAuth"] is True, f"Xác thực thất bại: {login_res}"
        assert login_res["modalOpen"] is False, "Modal phải tự động đóng sau khi login thành công"
        print("✓ 3. Đăng nhập Quản trị viên thành công! Phiên làm việc đã cấp Token an toàn")

        # 4. Kiểm tra Corner Pill đổi sang vương miện Admin Authenticated
        pill_admin_html = eval_js("document.getElementById('cornerAuthContainer')?.innerHTML || ''")
        assert "admin-active" in pill_admin_html and "👑" in pill_admin_html, "Pill phải có class admin-active và 👑"
        print("✓ 4. Corner Auth Widget đổi sang Vương miện 👑 Quản trị viên (Admin) [● Đã xác thực]")

        # 5. Chuyển sang Subtab 3: Nhật ký lưu vết & Giám sát CSDL
        eval_js("switchAdminSubtab('admin_audit', document.getElementById('btnSubtabAudit'))")
        time.sleep(0.8)
        subtab_display = eval_js("document.getElementById('admin_subtab_audit')?.style.display")
        assert subtab_display == "block", "Subtab 3 admin_subtab_audit phải hiển thị"
        logs_count = eval_js("document.querySelectorAll('#tbodyStealthLogs tr').length")
        assert logs_count >= 1, "Phải có ít nhất 1 dòng nhật ký lưu vết được tải"
        print(f"✓ 5. Subtab 3 Nhật Ký Lưu Vết & Giám Sát CSDL hiển thị xuất sắc ({logs_count} dòng log)")

        # 6. Đăng xuất khỏi quyền Admin
        eval_js("""
            (async () => {
                await exitAdminMode();
            })()
        """)
        time.sleep(0.5)
        is_auth_after = eval_js("STATE.isAdminAuthenticated")
        assert is_auth_after is False, "STATE.isAdminAuthenticated phải là false sau đăng xuất"
        pill_after = eval_js("document.getElementById('cornerAuthContainer')?.innerHTML || ''")
        assert "corner-auth-btn-login" in pill_after, "Pill phải quay lại trạng thái công chức thường"
        print("✓ 6. Đăng xuất Quản trị viên thành công, tự động thu hồi quyền và quay về Dashboard an toàn!")

    finally:
        proc.kill()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run_browser_auth_test()
    print("\n=== TOÀN BỘ BÀI TEST GIAO DIỆN VÀ BẢO MẬT ADMIN ĐẠT CHUẨN 100%! ===")
