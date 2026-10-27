import sys
import os
import time
import subprocess
import json
import urllib.request
import socket
import base64

sys.path.insert(0, os.path.abspath('.'))

from http.server import ThreadingHTTPServer
from app.web.handler import WebEngineRequestHandler
from app.database import DatabaseEngineModule

DatabaseEngineModule.initialize_schema()

server_port = 8796
httpd = ThreadingHTTPServer(('127.0.0.1', server_port), WebEngineRequestHandler)
import threading
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()

# Test 1: Test GET /api/dsrr/bundle_zip?id=1
req = urllib.request.urlopen(f'http://127.0.0.1:{server_port}/api/dsrr/bundle_zip?id=1')
assert req.status == 200
assert 'application/zip' in req.headers.get('Content-Type')
zip_data = req.read()
import zipfile
import io
with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zf:
    print("Bundle ZIP file list for Record #1:", zf.namelist())
    assert any('00_Thong_Tin_Ho_So_Rui_Ro' in name for name in zf.namelist())
print("=> Đạt yêu cầu HTTP GET /api/dsrr/bundle_zip?id=1 thành công!")

# Test 2: Chrome Headless interaction with the new modal sub-boxes
chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
if not os.path.exists(chrome_path):
    chrome_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

s = socket.socket()
s.bind(('', 0))
port = s.getsockname()[1]
s.close()

user_data = os.path.abspath('./.tmp_chrome_modal_test')
os.makedirs(user_data, exist_ok=True)

cmd = [
    chrome_path,
    '--headless=new',
    f'--remote-debugging-port={port}',
    f'--user-data-dir={user_data}',
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1400,900',
    f'http://127.0.0.1:{server_port}'
]

proc = subprocess.Popen(cmd)
time.sleep(2.0)

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

    def recv_msg(self, timeout=5.0):
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

try:
    req = urllib.request.urlopen(f'http://127.0.0.1:{port}/json')
    pages = json.loads(req.read().decode('utf-8'))
    target_page = [p for p in pages if p.get('type') == 'page'][0]
    ws_url = target_page['webSocketDebuggerUrl']

    from urllib.parse import urlparse
    u = urlparse(ws_url)
    ws = SimpleWS(u.hostname, u.port, u.path)

    ws.send_cmd("Runtime.enable")
    ws.send_cmd("Console.enable")

    time.sleep(2.0)

    test_js = """
    (async () => {
        const out = {};
        // Open modal
        await openDsrrModal(1);
        const modal = document.getElementById('dsrrModal');
        out.modalOpen = modal ? modal.classList.contains('open') : false;

        const sel = document.getElementById('md_action_type');
        
        // 1. Select 'Mời làm việc'
        sel.value = 'Mời làm việc';
        onActionTypeChanged();
        out.boxMlvDisplay = document.getElementById('boxMlvDetails')?.style.display;
        out.boxTbDisplayAfterMlv = document.getElementById('boxTbDetails')?.style.display;

        // 2. Select 'Chuyển thông tin phòng Kiểm tra'
        sel.value = 'Chuyển thông tin phòng Kiểm tra';
        onActionTypeChanged();
        out.boxPktDisplay = document.getElementById('boxPktDetails')?.style.display;
        out.boxMlvDisplayAfterPkt = document.getElementById('boxMlvDetails')?.style.display;

        // 3. Select 'Thông báo giải trình'
        sel.value = 'Thông báo giải trình';
        onActionTypeChanged();
        out.boxTbDisplay = document.getElementById('boxTbDetails')?.style.display;
        out.boxPktDisplayAfterTb = document.getElementById('boxPktDetails')?.style.display;

        // Close modal
        closeDsrrModal();
        out.modalClosed = !modal.classList.contains('open');

        return out;
    })()
    """

    eval_id = ws.send_cmd("Runtime.evaluate", {"expression": test_js, "returnByValue": True, "awaitPromise": True})
    start = time.time()
    res_val = None
    errors = []
    while time.time() - start < 4:
        msg = ws.recv_msg(timeout=1.0)
        if not msg: continue
        if msg.get('id') == eval_id:
            res_val = msg.get('result', {}).get('result', {}).get('value')
        if msg.get('method') == 'Runtime.exceptionThrown':
            errors.append(msg['params'])
        if msg.get('method') == 'Console.messageAdded' and msg['params']['message']['level'] == 'error':
            errors.append(msg['params']['message']['text'])

    print("=== KẾT QUẢ KIỂM THỬ GIAO DIỆN CHROME THỰC TẾ ===")
    print(json.dumps(res_val, ensure_ascii=False, indent=2))
    assert res_val.get('modalOpen') is True
    assert res_val.get('boxMlvDisplay') == 'block'
    assert res_val.get('boxPktDisplay') == 'block'
    assert res_val.get('boxTbDisplay') == 'block'
    assert res_val.get('modalClosed') is True
    if errors:
        print("LỖI CONSOLE:", errors)
        assert len(errors) == 0
    else:
        print("TUYỆT VỜI! Tất cả sub-boxes Mời làm việc, Chuyển kiểm tra và Thông báo giải trình hoạt động chính xác 100%!")

finally:
    proc.terminate()
    httpd.shutdown()
    import shutil
    shutil.rmtree(user_data, ignore_errors=True)
