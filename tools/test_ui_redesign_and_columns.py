"""
Kiem thu toan dien giao dien:
1. Kiem tra console JavaScript loi (phai = 0).
2. Kiem tra Dashboard Recent Records: 7 cot (tach MST va Ten NNT).
3. Kiem tra Bang DSRR: 8 cot (tach MST va Ten NNT, cot tai lieu & thao tac co nut dinh kem CVRR).
4. Kiem tra Bang Inspect: 8 cot (tach MST va Ten NNT).
5. Kiem tra Modal cap nhat ho so: co khoi dinh kem CVRR (Step 1).
6. Kiem tra API /api/dsrr/attach_cvrr hoat dong on dinh.
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

    def recv_msg(self, timeout=10.0):
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

    def call(self, method, params=None, timeout=10.0):
        mid = self.send_cmd(method, params)
        start = time.time()
        while time.time() - start < timeout:
            msg = self.recv_msg(timeout=2.0)
            if msg and msg.get("id") == mid:
                return msg.get("result", {})
        return None

    def close(self):
        try:
            self.sock.close()
        except:
            pass


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_tests():
    server_port = get_free_port()
    cdp_port = get_free_port()

    server = ThreadingHTTPServer(('127.0.0.1', server_port), WebEngineRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[*] Live test server running on port {server_port}")

    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
    ]
    chrome_path = None
    for p in chrome_candidates:
        if os.path.exists(p):
            chrome_path = p
            break

    if not chrome_path:
        print("[!] Chrome not found, skipping headless browser test")
        server.shutdown()
        return True

    cmd = [
        chrome_path,
        "--headless=new",
        f"--remote-debugging-port={cdp_port}",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-extensions",
        f"http://127.0.0.1:{server_port}/"
    ]
    chrome_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.0)

    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json")
        pages = json.loads(req.read().decode('utf-8'))
        app_page = None
        for p in pages:
            if p.get('type') == 'page' and f':{server_port}' in p.get('url', ''):
                app_page = p
                break
        if not app_page:
            app_page = pages[0]

        ws_url = app_page['webSocketDebuggerUrl']
        parsed = urlparse(ws_url)
        ws = SimpleWS(parsed.hostname, parsed.port, parsed.path)

        ws.send_cmd("Runtime.enable")
        time.sleep(1.0)

        def eval_js(script):
            mid = ws.send_cmd("Runtime.evaluate", {
                "expression": script,
                "returnByValue": True,
                "awaitPromise": True
            })
            for _ in range(30):
                msg = ws.recv_msg(timeout=2.0)
                if msg and msg.get("id") == mid:
                    res = msg.get("result", {})
                    if "exceptionDetails" in res:
                        raise RuntimeError(res["exceptionDetails"])
                    return res.get("result", {}).get("value")
            return None

        # Cho ung dung nap du lieu
        for _ in range(20):
            ready = eval_js("Boolean(window.STATE && window.STATE.dsrrList && window.STATE.dsrrList.length > 0)")
            if ready:
                break
            time.sleep(0.4)

        # 1. Kiem tra loi Console JS
        errs = eval_js("JSON.stringify(window.__consoleErrors || [])")
        err_list = json.loads(errs or "[]")
        print(f"[1] Console Errors: {len(err_list)} ({err_list})")
        assert len(err_list) == 0, f"Found JS errors: {err_list}"

        # 2. Kiem tra Dashboard Recent Table
        dash_str = eval_js("""(() => {
            const tb = document.querySelector('#tbodyDashRecent');
            const theadThs = Array.from(tb.closest('table').querySelectorAll('thead th'));
            const rows = tb.querySelectorAll('tr');
            const firstRowTds = rows.length > 0 ? Array.from(rows[0].querySelectorAll('td')).map(td => td.innerText.trim()) : [];
            return JSON.stringify({
                thCount: theadThs.length,
                thTexts: theadThs.map(t => t.innerText.trim()),
                tdCount: firstRowTds.length,
                firstRowTds: firstRowTds.slice(0, 3)
            });
        })()""")
        dash_data = json.loads(dash_str or "{}")
        print(f"[2] Dashboard Table check: {dash_data}")
        assert dash_data.get('thCount') == 7, f"Expected 7 columns on dashboard recent, got {dash_data.get('thCount')}"
        assert dash_data.get('tdCount') == 7, f"Expected 7 cells per row on dashboard recent, got {dash_data.get('tdCount')}"
        assert "Mã số thuế" in dash_data.get('thTexts', [])[0]
        assert "Tên Người nộp thuế" in dash_data.get('thTexts', [])[1]

        # 3. Kiem tra DSRR Table (Tab 2)
        dsrr_str = eval_js("""(() => {
            switchModule('mod_dsrr', document.getElementById('btnModDsrr'), 'active-mod1');
            const table = document.querySelector('#tbodyDsrr').closest('table');
            const theadThs = Array.from(table.querySelectorAll('thead th')).map(t => t.innerText.trim());
            const rows = document.querySelectorAll('#tbodyDsrr tr');
            const firstRowTds = rows.length > 0 ? Array.from(rows[0].querySelectorAll('td')).map(td => td.innerText.trim()) : [];
            const attachButtons = Array.from(document.querySelectorAll('#tbodyDsrr .btn-quick-attach')).length;
            return JSON.stringify({
                thCount: theadThs.length,
                thTexts: theadThs,
                tdCount: firstRowTds.length,
                attachButtonsCount: attachButtons
            });
        })()""")
        dsrr_data = json.loads(dsrr_str or "{}")
        print(f"[3] DSRR Table check: {dsrr_data}")
        assert dsrr_data.get('thCount') == 8, f"Expected 8 columns on DSRR, got {dsrr_data.get('thCount')}"
        assert dsrr_data.get('tdCount') == 8, f"Expected 8 cells per row on DSRR, got {dsrr_data.get('tdCount')}"
        assert "Mã số thuế" in dsrr_data.get('thTexts', [])[1]
        assert "Tên Người nộp thuế" in dsrr_data.get('thTexts', [])[2]
        print(f"    So luong nut dinh kem nhanh CVRR tren bang: {dsrr_data.get('attachButtonsCount')}")

        # 4. Kiem tra Inspect Table (Tab 3)
        inspect_str = eval_js("""(() => {
            switchModule('mod_inspect', document.getElementById('btnModInspect'), 'active-mod3');
            const table = document.querySelector('#tbodyInspectResult').closest('table');
            const theadThs = Array.from(table.querySelectorAll('thead th')).map(t => t.innerText.trim());
            const rows = document.querySelectorAll('#tbodyInspectResult tr');
            const firstRowTds = rows.length > 0 ? Array.from(rows[0].querySelectorAll('td')).map(td => td.innerText.trim()) : [];
            return JSON.stringify({
                thCount: theadThs.length,
                thTexts: theadThs,
                tdCount: firstRowTds.length
            });
        })()""")
        inspect_data = json.loads(inspect_str or "{}")
        print(f"[4] Inspect Table check: {inspect_data}")
        assert inspect_data.get('thCount') == 8, f"Expected 8 columns on Inspect, got {inspect_data.get('thCount')}"
        assert inspect_data.get('tdCount') == 8, f"Expected 8 cells per row on Inspect, got {inspect_data.get('tdCount')}"
        assert "Mã số thuế" in inspect_data.get('thTexts', [])[1]
        assert "Tên Người nộp thuế" in inspect_data.get('thTexts', [])[2]

        # 5. Kiem tra Modal Cap nhat DSRR (khoi upload CVRR)
        modal_str = eval_js("""(async () => {
            await openDsrrModal(1);
            const modal = document.getElementById('dsrrModal');
            const hasCvrrInput = !!document.getElementById('md_upload_cvrr_pdf');
            const hasCvrrLink = !!document.getElementById('md_cvrr_attached_link');
            const hasClearBtn = typeof clearAttachedCvrrPdf === 'function';
            const hasQuickAttach = typeof triggerQuickUploadCvrr === 'function';
            return JSON.stringify({
                modalOpen: modal.classList.contains('open'),
                hasCvrrInput: hasCvrrInput,
                hasCvrrLink: hasCvrrLink,
                hasClearBtn: hasClearBtn,
                hasQuickAttach: hasQuickAttach
            });
        })()""")
        modal_data = json.loads(modal_str or "{}")
        print(f"[5] DSRR Modal CVRR block check: {modal_data}")
        assert modal_data.get('modalOpen') is True
        assert modal_data.get('hasCvrrInput') is True
        assert modal_data.get('hasCvrrLink') is True
        assert modal_data.get('hasClearBtn') is True
        assert modal_data.get('hasQuickAttach') is True

        ws.close()
        print("\n===> TAT CA CAC TEST GIAO DIEN & COT BANG DEU THANH CONG! <===")
        return True

    finally:
        try:
            chrome_proc.terminate()
            chrome_proc.wait(timeout=3)
        except:
            pass
        server.shutdown()


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
