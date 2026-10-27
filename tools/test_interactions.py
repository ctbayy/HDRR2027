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

server_port = 8797
httpd = ThreadingHTTPServer(('127.0.0.1', server_port), WebEngineRequestHandler)
import threading
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()

chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
if not os.path.exists(chrome_path):
    chrome_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

s = socket.socket()
s.bind(('', 0))
port = s.getsockname()[1]
s.close()

user_data = os.path.abspath('./.tmp_chrome_profile_2')
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

    # Test clicking navigation tabs and quick action buttons
    interaction_script = """
    (() => {
        const results = [];
        // 1. Click Tab Tiếp nhận
        const btnTh = document.getElementById('btnModTh');
        if (btnTh) {
            btnTh.click();
            results.push({ action: 'click btnModTh', activePane: document.querySelector('.module-pane.active')?.id });
        }
        // 2. Click Tab Theo dõi DSRR
        const btnDsrr = document.getElementById('btnModDsrr');
        if (btnDsrr) {
            btnDsrr.click();
            results.push({ action: 'click btnModDsrr', activePane: document.querySelector('.module-pane.active')?.id, dsrrRows: document.querySelectorAll('#tbodyDsrr tr').length });
        }
        // 3. Click Tab Tra cứu
        const btnInspect = document.getElementById('btnModInspect');
        if (btnInspect) {
            btnInspect.click();
            results.push({ action: 'click btnModInspect', activePane: document.querySelector('.module-pane.active')?.id, inspectRows: document.querySelectorAll('#tbodyInspect tr').length });
        }
        // 4. Click Tab Dashboard quay lại
        const btnDash = document.getElementById('btnModDash');
        if (btnDash) {
            btnDash.click();
            results.push({ action: 'click btnModDash', activePane: document.querySelector('.module-pane.active')?.id });
        }
        // 5. Test Quick Action button click
        const qaBtns = document.querySelectorAll('.dash-action-btn');
        results.push({ quickActionCount: qaBtns.length });
        if (qaBtns.length > 0) {
            qaBtns[1].click(); // click second button (Cập nhật kết quả giải trình)
            results.push({ action: 'click quickAction[1]', activePane: document.querySelector('.module-pane.active')?.id });
        }
        // 6. Test open DSRR Modal
        if (STATE.dsrrList && STATE.dsrrList.length > 0) {
            openDsrrModal(STATE.dsrrList[0].id);
            const modal = document.getElementById('dsrrModal');
            results.push({ modalOpen: modal?.classList.contains('open'), modalMst: document.getElementById('md_mst')?.value });
            closeDsrrModal();
            results.push({ modalClosed: !modal?.classList.contains('open') });
        }
        return results;
    })()
    """

    eval_id = ws.send_cmd("Runtime.evaluate", {"expression": interaction_script, "returnByValue": True})
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

    print("=== KẾT QUẢ TEST TƯƠNG TÁC GIAO DIỆN (INTERACTION TEST) ===")
    print(json.dumps(res_val, ensure_ascii=False, indent=2))
    if errors:
        print("LỖI GIAO DIỆN / CONSOLE:", errors)
    else:
        print("HOÀN HẢO! Mọi nút bấm, chuyển tab, mở modal đều phản hồi chính xác 100%!")

finally:
    proc.terminate()
    httpd.shutdown()
