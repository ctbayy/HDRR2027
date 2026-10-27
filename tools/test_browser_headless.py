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

server_port = 8798
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

user_data = os.path.abspath('./.tmp_chrome_profile')
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

    # Wait for initial data load
    time.sleep(2.0)

    # Evaluate UI elements
    js_test = """
    (() => {
        return {
            dsrrCount: STATE.dsrrList ? STATE.dsrrList.length : -1,
            thCount: STATE.thList ? STATE.thList.length : -1,
            officerName: STATE.officerName,
            dashTotal: document.getElementById('dashTotalRecs')?.innerText,
            dashDone: document.getElementById('dashCountDone')?.innerText,
            dashDoing: document.getElementById('dashCountDoing')?.innerText,
            dashPending: document.getElementById('dashCountPending')?.innerText,
            dashOverdue: document.getElementById('dashCountOverdue')?.innerText,
            recentRows: document.querySelectorAll('#tbodyDashRecent tr').length,
            quickActions: Array.from(document.querySelectorAll('.dash-action-btn')).map(b => b.innerText.trim().replace(/\\n/g, ' ')),
            tabs: Array.from(document.querySelectorAll('.nav-tab')).map(t => ({ id: t.dataset.tab, active: t.classList.contains('active') }))
        };
    })()
    """
    eval_id = ws.send_cmd("Runtime.evaluate", {"expression": js_test, "returnByValue": True})
    
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

    print("=== TRẠNG THÁI GIAO DIỆN CHROME SAU KHI TẢI DỮ LIỆU ===")
    print(json.dumps(res_val, ensure_ascii=False, indent=2))
    if errors:
        print("LỖI CONSOLE:", errors)
    else:
        print("TẤT CẢ TỐT, KHÔNG CÓ LỖI CONSOLE NÀO!")

    # Take screenshot
    shot_id = ws.send_cmd("Page.captureScreenshot", {"format": "png"})
    while True:
        m = ws.recv_msg(timeout=2.0)
        if not m: break
        if m.get('id') == shot_id:
            img_b64 = m.get('result', {}).get('data')
            if img_b64:
                with open("C:/Users/ctbay/.gemini/antigravity/brain/a99ad211-bc3f-4545-a15f-d5d6e1436e4d/dashboard_live_verified.png", "wb") as f:
                    f.write(base64.b64decode(img_b64))
                print("Đã chụp ảnh màn hình dashboard_live_verified.png thành công!")
            break

finally:
    proc.terminate()
    httpd.shutdown()
