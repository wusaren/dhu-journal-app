"""
论文格式检测系统 —— 一体化启动器（极简版）

[为什么需要这个文件？]
format_check_server.py  独立进程 / Flask 服务
format_check_client.py  独立进程 / Tkinter GUI
两者各有 'if __name__ == "__main__"'，PyInstaller 只支持一个打包入口。
本文件仅做两件事：
  1. 在后台线程启动 format_check_server 中现有的 Flask app
  2. 直接打开 format_check_client 的 GUI 界面（主线程）

运行方式（开发）：python format_check_launcher.py
打包方式：         双击 build_exe.bat
"""

import os
import sys
import time
import threading

# ──────────────────────────────────────────────
# 路径修复（PyInstaller 打包后的兼容处理）
# ──────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    APP_DIR      = os.path.dirname(sys.executable)  # exe 旁边目录（可写）
    INTERNAL_DIR = sys._MEIPASS                      # type: ignore[attr-defined]
else:
    APP_DIR      = os.path.dirname(os.path.abspath(__file__))
    INTERNAL_DIR = APP_DIR

for _p in [os.path.join(INTERNAL_DIR, 'backend'), INTERNAL_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ──────────────────────────────────────────────
# 运行时数据目录（必须在可写位置）
# ──────────────────────────────────────────────
TEMP_DIR  = os.path.join(APP_DIR, 'cs_data', 'temp')
REPORTS   = os.path.join(APP_DIR, 'cs_data', 'reports')
ANNOTATED = os.path.join(APP_DIR, 'cs_data', 'annotated')
LOGS      = os.path.join(APP_DIR, 'cs_data', 'logs')
for _d in [TEMP_DIR, REPORTS, ANNOTATED, LOGS]:
    os.makedirs(_d, exist_ok=True)

SERVER_PORT = 5001
SERVER_URL  = f'http://127.0.0.1:{SERVER_PORT}'


# ══════════════════════════════════════════════
# 后台服务
# ══════════════════════════════════════════════

def start_server():
    """导入 format_check_server 中已有的 Flask app，覆盖数据目录后启动。"""
    import format_check_server as srv
    # 覆盖数据目录为可写路径（打包后 _MEIPASS 是只读）
    srv.TEMP_DIR      = TEMP_DIR
    srv.REPORTS_DIR   = REPORTS
    srv.ANNOTATED_DIR = ANNOTATED
    srv.LOG_DIR       = LOGS

    # 重新将日志 FileHandler 指向可写目录。
    # server.py 在 import 时已用 _MEIPASS 路径注册了 FileHandler，需替换。
    import logging
    _root = logging.getLogger()
    for _h in list(_root.handlers):
        if isinstance(_h, logging.FileHandler):
            _h.close()
            _root.removeHandler(_h)
    _fh = logging.FileHandler(os.path.join(LOGS, 'server.log'), encoding='utf-8')
    _fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    _root.addHandler(_fh)

    from werkzeug.serving import make_server
    server = make_server('127.0.0.1', SERVER_PORT, srv.app)
    server.serve_forever()


def wait_server_ready(timeout: float = 30.0) -> bool:
    """轮询等待服务就绪"""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'{SERVER_URL}/api/ping', timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


# ══════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════

def main():
    # 1. 后台线程启动 Flask
    threading.Thread(target=start_server, daemon=True).start()

    # 2. 等待服务就绪（通常 < 1s，无需任何过渡窗口）
    if not wait_server_ready(timeout=30):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            '启动失败',
            f'格式检测服务无法在端口 {SERVER_PORT} 启动。\n'
            '请检查该端口是否已被其他程序占用。'
        )
        root.destroy()
        return

    # 3. 直接打开客户端界面（无过渡窗口）
    import format_check_client as fcc
    fcc.DEFAULT_SERVER = SERVER_URL
    gui = fcc.FormatCheckApp()
    gui._server_var.set(SERVER_URL)
    gui._server_entry.config(state='readonly')
    gui.mainloop()


if __name__ == '__main__':
    main()
