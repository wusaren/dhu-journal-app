"""
论文格式检测 客户端（Tkinter GUI）
架构：C/S，通过 HTTP 与 format_check_server.py 通信

Python 内置：tkinter

使用方法：
    1. 先启动服务端：python format_check_server.py
    2. 再启动本客户端：python format_check_client.py
"""

import os
import sys
import threading
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
from pathlib import Path

# ────────────────────────────────────────────
# 配置
# ────────────────────────────────────────────
DEFAULT_SERVER = 'http://127.0.0.1:5001'

# 检测模块定义（key → 显示名）
MODULES = [
    ('Title',           '标题格式检测'),
    ('Abstract',        '摘要格式检测'),
    ('Keywords',        '关键词格式检测'),
    ('Content',         '正文格式检测'),
    ('Formula',         '公式格式检测'),
    ('Figure',          '图片格式检测'),
    ('Table',           '表格格式检测'),
    ('Reference',       '参考文献检测'),
    ('Chinese_section', '中文部分检测'),
]

# 各模块可跳过的子检测项定义
# 普通模块：通用格式类跳过项
_COMMON_SKIP = [
    ('font_size',  '字体大小',  '跳过字体大小检测'),
    ('bold',       '加粗',      '跳过文字加粗检测'),
    ('italic',     '斜体',      '跳过文字斜体检测'),
    ('alignment',  '对齐',      '跳过段落对齐检测'),
    ('spacing',    '行距',      '跳过行距检测'),
    ('indent',     '缩进',      '跳过首行缩进检测'),
]
# 中文部分：专有跳过项
_CHINESE_SKIP = [
    ('address_zipcode', '地址审核与邮编检测', '跳过中文单位的地址审核与邮编验证'),
]

# Reference 暂无可跳过的子项
MODULE_SKIP_OPTIONS: dict[str, list] = {
    key: (
        [] if key == 'Reference'
        else _CHINESE_SKIP if key == 'Chinese_section'
        else _COMMON_SKIP
    )
    for key, _ in MODULES
}


# ────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────
def save_bytes_dialog(data: bytes, default_name: str, filetypes: list) -> str | None:
    """弹出另存为对话框并保存 bytes"""
    path = filedialog.asksaveasfilename(
        defaultextension=os.path.splitext(default_name)[1],
        initialfile=default_name,
        filetypes=filetypes,
    )
    if path:
        with open(path, 'wb') as f:
            f.write(data)
        return path
    return None


# ────────────────────────────────────────────
# 主界面
# ────────────────────────────────────────────
class FormatCheckApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('论文格式检测系统')
        self.geometry('1080x760')
        self.minsize(980, 760)
        self.resizable(True, True)
        self.configure(bg='#f5f5f5')

        # 运行时状态
        self._file_path: str | None = None
        self._upload_info: dict | None = None   # 上传成功后的服务端信息
        self._check_result: dict | None = None  # 检测结果
        self._report_url: str | None = None
        self._annotated_url: str | None = None

        # 模块勾选变量
        self._module_vars: dict[str, tk.BooleanVar] = {}
        # 跳过子项：{模块key: [check_key, ...]}
        self._skip_checks: dict[str, list] = {}

        self._build_ui()

    # ────────────────────────────────────────
    # UI 构建
    # ────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=10, pady=4)

        # ── 顶栏：服务器地址 ──────────────────
        top_frame = tk.Frame(self, bg='#f5f5f5')
        top_frame.pack(fill='x', **pad)

        tk.Label(top_frame, text='服务器：', bg='#f5f5f5').pack(side='left')
        self._server_var = tk.StringVar(value=DEFAULT_SERVER)
        self._server_entry = tk.Entry(top_frame, textvariable=self._server_var, width=32)
        self._server_entry.pack(side='left', padx=(0, 6))
        tk.Button(top_frame, text='测试连接', command=self._ping_server,
                  relief='groove').pack(side='left')

        ttk.Separator(self, orient='horizontal').pack(fill='x', padx=10, pady=2)

        # ── 第一步：选择文件 ──────────────────
        step1 = tk.LabelFrame(self, text=' 选择论文文件 (.docx) ', bg='#f5f5f5',
                               font=('微软雅黑', 9, 'bold'))
        step1.pack(fill='x', **pad)

        file_row = tk.Frame(step1, bg='#f5f5f5')
        file_row.pack(fill='x', padx=8, pady=6)

        self._file_label = tk.Label(file_row, text='未选择文件', fg='#888',
                                     bg='#f5f5f5', anchor='w', width=55)
        self._file_label.pack(side='left')
        tk.Button(file_row, text='浏览…', command=self._select_file,
                  width=8, relief='groove').pack(side='left', padx=(6, 0))

        title_row = tk.Frame(step1, bg='#f5f5f5')
        title_row.pack(fill='x', padx=8, pady=(0, 8))
        tk.Label(title_row, text='论文标题：', bg='#f5f5f5').pack(side='left')
        self._title_var = tk.StringVar()
        tk.Entry(title_row, textvariable=self._title_var, width=50).pack(side='left')

        # ── 第二步：选择检测模块 ──────────────
        step2 = tk.LabelFrame(self, text=' 选择检测模块 ', bg='#f5f5f5',
                               font=('微软雅黑', 9, 'bold'))
        step2.pack(fill='x', **pad)

        mod_frame = tk.Frame(step2, bg='#f5f5f5')
        mod_frame.pack(fill='x', padx=8, pady=6)

        # 每行：[勾选框]  模块名  [跳过子项…]
        # 5列布局，每模块占一列
        self._skip_btns: dict[str, tk.Button] = {}
        for idx, (key, name) in enumerate(MODULES):
            var = tk.BooleanVar(value=True)
            self._module_vars[key] = var
            row, col = divmod(idx, 5)
            cell = tk.Frame(mod_frame, bg='#f5f5f5')
            cell.grid(row=row, column=col, sticky='w', padx=4, pady=2)
            tk.Checkbutton(cell, text=name, variable=var, bg='#f5f5f5',
                           command=lambda k=key: self._on_module_toggle(k)
                           ).pack(side='left')
            _has_skip = bool(MODULE_SKIP_OPTIONS.get(key))
            skip_btn = tk.Button(
                cell, text='跳过…', relief='groove', font=('微软雅黑', 7),
                padx=3, pady=1,
                state='normal' if _has_skip else 'disabled',
                command=lambda k=key: self._open_skip_dialog(k)
            )
            skip_btn.pack(side='left', padx=(2, 0))
            self._skip_btns[key] = skip_btn

        btn_row = tk.Frame(step2, bg='#f5f5f5')
        btn_row.pack(fill='x', padx=8, pady=(0, 8))
        tk.Button(btn_row, text='全选', command=self._select_all_modules,
                  width=6, relief='groove').pack(side='left', padx=(0, 4))
        tk.Button(btn_row, text='清空', command=self._clear_all_modules,
                  width=6, relief='groove').pack(side='left')

        # 高级选项
        adv_frame = tk.Frame(step2, bg='#f5f5f5')
        adv_frame.pack(fill='x', padx=8, pady=(0, 6))
        self._figure_api_var = tk.BooleanVar(value=False)
        self._cls_api_var    = tk.BooleanVar(value=False)
        self._figure_api_check = tk.Checkbutton(
            adv_frame,
            text='启用图片内容 API 检测',
            variable=self._figure_api_var,
            bg='#f5f5f5'
        )
        self._figure_api_check.pack(side='left', padx=(0, 12))
        self._cls_api_check = tk.Checkbutton(
            adv_frame,
            text='启用摘要分类号 API 检测',
            variable=self._cls_api_var,
            bg='#f5f5f5'
        )
        self._cls_api_check.pack(side='left')
        self._sync_api_options_state()

        # ── 第三步：执行检测 ──────────────────
        step3 = tk.Frame(self, bg='#f5f5f5')
        step3.pack(fill='x', padx=10, pady=4)

        self._run_btn = tk.Button(step3, text='▶  开始检测', command=self._start_check,
                                   bg='#1976D2', fg='white', font=('微软雅黑', 10, 'bold'),
                                   relief='flat', padx=10, pady=0, cursor='hand2')
        self._run_btn.pack(side='left')

        self._progress = ttk.Progressbar(step3, mode='indeterminate', length=200)
        self._progress.pack(side='left', padx=14)

        self._status_var = tk.StringVar(value='就绪')
        tk.Label(step3, textvariable=self._status_var, bg='#f5f5f5', fg='#555').pack(side='left')

        ttk.Separator(self, orient='horizontal').pack(fill='x', padx=10, pady=4)

        # ── 第四步：结果展示 ──────────────────
        result_frame = tk.LabelFrame(self, text=' 检测结果 ', bg='#f5f5f5',
                                      font=('微软雅黑', 9, 'bold'))
        result_frame.pack(fill='both', expand=True, **pad)

        # 结果区左右分栏
        paned = tk.PanedWindow(result_frame, orient='horizontal', bg='#f5f5f5', sashwidth=4)
        paned.pack(fill='both', expand=True, padx=4, pady=2)

        # 左：模块摘要树
        left_f = tk.Frame(paned, bg='#f5f5f5')
        paned.add(left_f, minsize=220)

        tk.Label(left_f, text='模块通过情况', bg='#f5f5f5', font=('微软雅黑', 9)).pack(anchor='w')
        self._tree = ttk.Treeview(left_f, columns=('status',), height=14, selectmode='browse')
        self._tree.heading('#0', text='模块')
        self._tree.heading('status', text='状态')
        self._tree.column('#0', width=160)
        self._tree.column('status', width=60, anchor='center')
        self._tree.pack(fill='both', expand=True)
        self._tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        # 右：详情文本
        right_f = tk.Frame(paned, bg='#f5f5f5')
        paned.add(right_f, minsize=380)

        tk.Label(right_f, text='详情', bg='#f5f5f5', font=('微软雅黑', 9)).pack(anchor='w')
        self._detail_text = scrolledtext.ScrolledText(
            right_f, wrap='word', font=('Consolas', 9), state='disabled', height=14
        )
        self._detail_text.pack(fill='both', expand=True)

        # ── 底部：下载按钮 ────────────────────
        btn_bar = tk.Frame(self, bg='#f5f5f5')
        btn_bar.pack(fill='x', padx=10, pady=(0, 10))

        # self._dl_report_btn = tk.Button(
        #     btn_bar, text='📄 下载检测报告 (.txt)',
        #     command=self._download_report, state='disabled',
        #     relief='groove', padx=10, pady=4,
        # )
        # self._dl_report_btn.pack(side='left', padx=(0, 6))
     
        self._dl_word_report_btn = tk.Button(
            btn_bar, text='📘 下载检测报告 (.docx)',
            command=self._download_word_report, state='disabled',
            relief='groove', padx=10, pady=4,
        )
        self._dl_word_report_btn.pack(side='left', padx=(0, 10))

        self._dl_annotated_btn = tk.Button(
            btn_bar, text='✏  下载批注文档 (.docx)',
            command=self._download_annotated, state='disabled',
            relief='groove', padx=10, pady=4,
        )
        self._dl_annotated_btn.pack(side='left')

        self._summary_label = tk.Label(
            btn_bar, text='', bg='#f5f5f5', fg='#333',
            font=('微软雅黑', 9)
        )
        self._summary_label.pack(side='right')

    # ────────────────────────────────────────
    # 模块选择辅助
    # ────────────────────────────────────────
    def _select_all_modules(self):
        for key, v in self._module_vars.items():
            v.set(True)
            if MODULE_SKIP_OPTIONS.get(key):  # 无跳过项的模块（如 Reference）保持禁用
                self._skip_btns[key].config(state='normal')
        self._sync_api_options_state()

    def _clear_all_modules(self):
        for key, v in self._module_vars.items():
            v.set(False)
            self._skip_checks.pop(key, None)
            self._skip_btns[key].config(state='disabled', text='跳过…')
        self._sync_api_options_state()

    def _on_module_toggle(self, key: str):
        """模块勾选/取消时同步跳过子项按钮状态"""
        enabled = self._module_vars[key].get()
        has_skip = bool(MODULE_SKIP_OPTIONS.get(key))
        if enabled and has_skip:
            self._skip_btns[key].config(state='normal')
        else:
            self._skip_checks.pop(key, None)
            self._skip_btns[key].config(state='disabled', text='跳过…')
        self._sync_api_options_state()

    def _sync_api_options_state(self):
        """根据模块勾选状态同步 API 检测选项的可用性"""
        figure_enabled = self._module_vars.get('Figure', tk.BooleanVar(value=False)).get()
        abstract_enabled = self._module_vars.get('Abstract', tk.BooleanVar(value=False)).get()

        if figure_enabled:
            self._figure_api_check.config(state='normal')
        else:
            self._figure_api_var.set(False)
            self._figure_api_check.config(state='disabled')

        if abstract_enabled:
            self._cls_api_check.config(state='normal')
        else:
            self._cls_api_var.set(False)
            self._cls_api_check.config(state='disabled')

    def _open_skip_dialog(self, module_key: str):
        """弹出跳过子项选择对话框"""
        options = MODULE_SKIP_OPTIONS.get(module_key, [])
        if not options:
            messagebox.showinfo('提示', f'模块 {module_key} 暂无可跳过的子项')
            return

        module_name = dict(MODULES).get(module_key, module_key)
        current = self._skip_checks.get(module_key, [])

        dlg = tk.Toplevel(self)
        dlg.title(f'跳过子项 — {module_name}')
        dlg.geometry('380x320')
        dlg.resizable(False, False)
        dlg.grab_set()  # 模态
        dlg.configure(bg='#f5f5f5')

        tk.Label(
            dlg,
            text=f'为「{module_name}」选择需要跳过的检测项：',
            bg='#f5f5f5', wraplength=340, justify='left',
            font=('微软雅黑', 9),
        ).pack(padx=14, pady=(12, 6), anchor='w')

        ttk.Separator(dlg, orient='horizontal').pack(fill='x', padx=10)

        check_vars: dict[str, tk.BooleanVar] = {}

        def _confirm():
            selected = [val for val, v in check_vars.items() if v.get()]
            if selected:
                self._skip_checks[module_key] = selected
                self._skip_btns[module_key].config(
                    text=f'跳过({len(selected)})', fg='#c0392b'
                )
            else:
                self._skip_checks.pop(module_key, None)
                self._skip_btns[module_key].config(text='跳过…', fg='black')
            dlg.destroy()

        def _clear_all():
            for v in check_vars.values():
                v.set(False)

        # 底部按钮行：先 pack side='bottom'，确保不被 canvas 遮挡
        btn_f = tk.Frame(dlg, bg='#f5f5f5')
        btn_f.pack(side='bottom', fill='x', padx=10, pady=(4, 10))
        tk.Button(btn_f, text='清空', command=_clear_all,
                  width=7, relief='groove').pack(side='left')
        tk.Button(btn_f, text='取消', command=dlg.destroy,
                  width=7, relief='groove').pack(side='right', padx=(4, 0))
        tk.Button(btn_f, text='确定', command=_confirm,
                  width=7, bg='#1976D2', fg='white', relief='flat').pack(side='right')

        # 滚动区域（子项较多时可滚动）——必须在按钮行之后 pack
        scroll_frame = tk.Frame(dlg, bg='#f5f5f5')
        scroll_frame.pack(fill='both', expand=True, padx=10, pady=6)

        canvas = tk.Canvas(scroll_frame, bg='#f5f5f5', highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_frame, orient='vertical', command=canvas.yview)
        inner = tk.Frame(canvas, bg='#f5f5f5')
        inner.bind('<Configure>',
                   lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        for val, label, desc in options:
            v = tk.BooleanVar(value=(val in current))
            check_vars[val] = v
            row_f = tk.Frame(inner, bg='#f5f5f5')
            row_f.pack(fill='x', padx=6, pady=4)
            tk.Checkbutton(row_f, text=label, variable=v,
                           bg='#f5f5f5', font=('微软雅黑', 9)).pack(side='left')
            tk.Label(row_f, text=f'（{desc}）', fg='#888',
                     bg='#f5f5f5', font=('微软雅黑', 8)).pack(side='left', padx=(4, 0))

    # ────────────────────────────────────────
    # 文件选择
    # ────────────────────────────────────────
    def _select_file(self):
        path = filedialog.askopenfilename(
            title='选择论文文件',
            filetypes=[('Word 文档', '*.docx'), ('所有文件', '*.*')]
        )
        if path:
            self._file_path = path
            short = Path(path).name
            self._file_label.config(text=short, fg='#222')
            self._title_var.set(os.path.splitext(short)[0])
            self._reset_results()

    # ────────────────────────────────────────
    # 服务器连通测试
    # ────────────────────────────────────────
    def _ping_server(self):
        server = self._server_var.get().rstrip('/')
        try:
            r = requests.get(f'{server}/api/ping', timeout=4)
            if r.ok and r.json().get('status') == 'ok':
                messagebox.showinfo('连接成功', f'服务器响应正常\n{server}')
            else:
                messagebox.showwarning('异常', f'服务器响应异常：{r.text[:200]}')
        except Exception as e:
            messagebox.showerror('连接失败', f'无法连接服务器：{e}')

    # ────────────────────────────────────────
    # 开始检测（异步）
    # ────────────────────────────────────────
    def _start_check(self):
        if not self._file_path:
            messagebox.showwarning('提示', '请先选择论文文件')
            return
        selected = [k for k, v in self._module_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning('提示', '请至少选择一个检测模块')
            return

        self._reset_results()
        self._run_btn.config(state='disabled')
        self._progress.start(10)
        self._status_var.set('正在上传并检测，请稍候…')

        threading.Thread(
            target=self._run_check,
            args=(self._file_path, selected,),
            daemon=True,
        ).start()

    def _run_check(self, file_path: str, modules: list):
        server = self._server_var.get().rstrip('/')
        title  = self._title_var.get() or Path(file_path).stem
        try:
            # 1. 上传文件
            with open(file_path, 'rb') as fp:
                resp = requests.post(
                    f'{server}/api/upload',
                    files={'file': (Path(file_path).name, fp,
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},
                    data={'title': title},
                    timeout=60,
                )
            upload_data = resp.json()
            if not upload_data.get('success'):
                raise RuntimeError(f'上传失败：{upload_data.get("message")}')

            # 2. 检测
            payload = {
                'file_id':   upload_data['file_id'],
                'temp_path': upload_data['temp_path'],
                'title':     title,
                'modules':   modules,
                'enable_figure_api':          self._figure_api_var.get(),
                'enable_classification_api':  self._cls_api_var.get(),
                'skip_checks': self._skip_checks,
            }
            resp2 = requests.post(
                f'{server}/api/check',
                json=payload,
                timeout=300,
            )
            result = resp2.json()
            if not result.get('success'):
                raise RuntimeError(f'检测失败：{result.get("message")}')

        except Exception as e:
            self.after(0, self._on_check_error, str(e))
            return

        self.after(0, self._on_check_done, server, result)

    # ────────────────────────────────────────
    # 检测结果回调（在主线程执行）
    # ────────────────────────────────────────
    def _on_check_done(self, server: str, result: dict):
        self._progress.stop()
        self._run_btn.config(state='normal')
        self._status_var.set('检测完成 ✓')
        self._check_result = result

        # 设置下载 URL
        self._report_url    = server + result.get('report_url', '')    if result.get('report_url') else None
        self._word_report_url = server + result.get('word_report_url', '') if result.get('word_report_url') else None
        self._annotated_url = server + result.get('annotated_url', '') if result.get('annotated_url') else None

        # 填充树
        self._fill_tree(result)

        # 激活下载按钮
        # if self._report_url:
        #     self._dl_report_btn.config(state='normal')
        if self._word_report_url:
            self._dl_word_report_btn.config(state='normal')
        if self._annotated_url:
            self._dl_annotated_btn.config(state='normal')

        # 摘要信息
        summary = result.get('result', {}).get('data', {}).get('summary', {})
        if summary:
            total   = summary.get('total_checks', 0)
            passed  = summary.get('passed_checks', 0)
            failed  = summary.get('failed_checks', 0)
            rate    = summary.get('pass_rate', 0)
            self._summary_label.config(
                text=f'总计 {total} 项  通过 {passed}  失败 {failed}  通过率 {rate:.1f}%'
            )

    def _on_check_error(self, msg: str):
        self._progress.stop()
        self._run_btn.config(state='normal')
        self._status_var.set('检测失败 ✗')
        messagebox.showerror('检测失败', msg)

    # ────────────────────────────────────────
    # 填充树形结果
    # ────────────────────────────────────────
    def _fill_tree(self, full_result: dict):
        self._tree.delete(*self._tree.get_children())
        modules_data: dict = full_result.get('result', {}).get('data', {}).get('results', {})

        for key, name in MODULES:
            if key not in modules_data:
                continue
            mod = modules_data[key]
            ok   = _module_ok(mod)
            tag  = 'pass' if ok else 'fail'
            icon = '✓' if ok else '✗'
            node = self._tree.insert('', 'end', iid=key, text=name, values=(icon,), tags=(tag,))

            checks: dict = mod.get('checks', {})
            errors: list = mod.get('errors', [])

            if checks:
                # 旧格式：展开 checks 子项
                for check_name, check_val in checks.items():
                    if not isinstance(check_val, dict):
                        continue
                    c_ok   = check_val.get('ok', False)
                    c_icon = '✓' if c_ok else '✗'
                    c_tag  = 'pass' if c_ok else 'fail'
                    self._tree.insert(node, 'end', text=f'  {check_name}',
                                       values=(c_icon,), tags=(c_tag,))
            elif errors:
                # 新格式：展开 errors 条目
                for i, err in enumerate(errors, 1):
                    err_id = err.get('error_id', f'问题{i}')
                    is_err = err.get('type') == 'error'
                    c_icon = '✗' if is_err else '⚠'
                    c_tag  = 'fail' if is_err else 'warn'
                    self._tree.insert(node, 'end', text=f'  {err_id}',
                                       values=(c_icon,), tags=(c_tag,))

        self._tree.tag_configure('pass', foreground='#2e7d32')
        self._tree.tag_configure('fail', foreground='#c62828')
        self._tree.tag_configure('warn', foreground='#e65100')

    # ────────────────────────────────────────
    # 树选中 → 右侧详情
    # ────────────────────────────────────────
    def _on_tree_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        # 只响应顶层模块节点
        parent = self._tree.parent(iid)
        if parent:
            iid = parent  # 点击子项也显示父模块详情

        modules_data = self._check_result.get('result', {}).get('data', {}).get('results', {})
        mod = modules_data.get(iid)
        if not mod:
            return
        text = _format_module_detail(iid, mod)
        self._detail_text.config(state='normal')
        self._detail_text.delete('1.0', 'end')
        self._detail_text.insert('1.0', text)
        self._detail_text.config(state='disabled')

    # ────────────────────────────────────────
    # 下载
    # ────────────────────────────────────────
    def _download_report(self):
        if not self._report_url:
            return
        try:
            r = requests.get(self._report_url, timeout=30)
            r.raise_for_status()
            path = save_bytes_dialog(r.content, 'format_report.txt',
                                     [('文本文件', '*.txt'), ('所有文件', '*.*')])
            if path:
                messagebox.showinfo('保存成功', f'检测报告已保存：\n{path}')
        except Exception as e:
            messagebox.showerror('下载失败', str(e))

    def _download_word_report(self):
        if not self._word_report_url:
            return
        try:
            r = requests.get(self._word_report_url, timeout=30)
            r.raise_for_status()
            path = save_bytes_dialog(
                r.content, 'format_report.docx',
                [('Word 文档', '*.docx'), ('所有文件', '*.*')]
            )
            if path:
                messagebox.showinfo('保存成功', f'Word检测报告已保存：\n{path}')
        except Exception as e:
            messagebox.showerror('下载失败', str(e))

    def _download_annotated(self):
        if not self._annotated_url:
            return
        try:
            r = requests.get(self._annotated_url, timeout=30)
            r.raise_for_status()
            path = save_bytes_dialog(
                r.content, 'annotated.docx',
                [('Word 文档', '*.docx'), ('所有文件', '*.*')]
            )
            if path:
                messagebox.showinfo('保存成功', f'批注文档已保存：\n{path}')
        except Exception as e:
            messagebox.showerror('下载失败', str(e))

    # ────────────────────────────────────────
    # 重置结果区
    # ────────────────────────────────────────
    def _reset_results(self):
        self._check_result  = None
        self._report_url    = None
        self._word_report_url = None
        self._annotated_url = None
        self._tree.delete(*self._tree.get_children())
        self._detail_text.config(state='normal')
        self._detail_text.delete('1.0', 'end')
        self._detail_text.config(state='disabled')
        # self._dl_report_btn.config(state='disabled')
        self._dl_word_report_btn.config(state='disabled')
        self._dl_annotated_btn.config(state='disabled')
        self._summary_label.config(text='')


# ────────────────────────────────────────────
# 辅助：格式化模块详情文字
# ────────────────────────────────────────────
def _module_ok(mod: dict) -> bool:
    """判断模块是否整体通过（兼容新格式 ok+errors 和旧格式 checks）"""
    checks = mod.get('checks', {})
    if checks:
        return all(
            v.get('ok', True) for v in checks.values()
            if isinstance(v, dict) and 'ok' in v
        )
    # 新格式：直接使用 ok 字段
    if 'ok' in mod:
        return bool(mod['ok'])
    return True


def _format_module_detail(module_key: str, mod: dict) -> str:
    lines = []
    cn_name = {
        'Title': '英文标题、作者与单位', 'Abstract': '英文摘要',
        'Keywords': '英文关键词', 'Content': '正文',
        'Formula': '公式', 'Figure': '图',
        'Table': '表格', 'Reference': '参考文献',
        'Chinese_section': '中文部分',
    }.get(module_key, module_key)

    sep = '=' * 60
    lines.append(sep)
    lines.append(f'模块：{cn_name}')
    lines.append(sep)

    checks: dict = mod.get('checks', {})
    errors: list = mod.get('errors', [])

    if checks:
        # 旧格式：展示 checks 字典
        for name, val in checks.items():
            if not isinstance(val, dict):
                continue
            ok     = val.get('ok', False)
            symbol = '✓ 通过' if ok else '✗ 未通过'
            lines.append(f'\n[{name}]  {symbol}')
            for msg in val.get('messages', []):
                lines.append(f'  • {msg}')
    elif errors:
        # 新格式：结构化展示 errors 列表
        for i, err in enumerate(errors, 1):
            err_id   = err.get('error_id', f'问题{i}')
            err_type = err.get('type', 'warning').upper()
            lines.append(f'\n[{err_id}]  {err_type}')
            page = str(err.get('page_number', ''))
            if page and page != 'N/A':
                lines.append(f'  📍 页码：{page}')
            if err.get('description'):
                lines.append(f'  描述：{err["description"]}')
            suggestion = str(err.get('suggestion', ''))
            if suggestion and suggestion != 'N/A':
                lines.append(f'  💡 建议：{suggestion}')
            snippet = str(err.get('text_snippet', ''))
            if snippet and snippet != 'N/A' and len(snippet) > 3:
                if len(snippet) > 120:
                    snippet = snippet[:120] + '...'
                lines.append(f'  📄 {snippet}')
    else:
        lines.append('\n✓ 全部检测通过')

    # 额外：summary
    summary = mod.get('summary', [])
    if summary:
        lines.append('\n── 摘要 ──')
        for s in summary:
            if isinstance(s, str):
                lines.append(s)

    return '\n'.join(lines)


# ────────────────────────────────────────────
# 入口
# ────────────────────────────────────────────
if __name__ == '__main__':
    app = FormatCheckApp()
    app.mainloop()
