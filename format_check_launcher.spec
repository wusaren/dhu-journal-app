# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 论文格式检测系统一体化启动器

构建命令（在项目根目录执行）：
    pyinstaller format_check_launcher.spec

输出目录：dist\论文格式检测系统\
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# ── 项目根目录（spec 文件所在位置）──
ROOT = os.path.dirname(os.path.abspath(SPEC))  # type: ignore[name-defined]
BACKEND_DIR      = os.path.join(ROOT, 'backend')
SERVICES_DIR     = os.path.join(BACKEND_DIR, 'services')
PAPER_DETECT_DIR = os.path.join(SERVICES_DIR, 'paper_detect')
TEMPLATES_DIR    = os.path.join(SERVICES_DIR, 'paper_detect_templates')

# ─────────────────────────────────────────────
# 数据文件（非 Python 代码，需要显式打包）
# ─────────────────────────────────────────────
datas = []
binaries = []
_spacy_hiddenimports = []

# 1. 仅打包检测所需的非 Python 数据文件
#    Python 源码由 PyInstaller 从 pathex 自动分析并编译，无需在此列出
datas += [
    # (a, b)元组形式，源路径到生成路径
    # 各检测模块的格式模板（JSON）
    (TEMPLATES_DIR, 'services/paper_detect_templates'), 
    # LLM 提示词（Figure/Reference 等模块运行时读取）
    (os.path.join(PAPER_DETECT_DIR, 'prompts.json'), 'paper_detect'),
]

# 2. spaCy 模型数据
# collect_data_files  — meta.json / vocab 等非 Python 资源
# collect_submodules  — __init__.py 及所有子包（必须！）
# collect_binaries    — .pyd / .so 扩展模块

# import spacy  # noqa: F401
# for _pkg in ('spacy', 'en_core_web_sm'):
#     datas    += collect_data_files(_pkg)
#     datas    += copy_metadata(_pkg)
#     _spacy_hiddenimports += collect_submodules(_pkg)

datas    += collect_data_files('en_core_web_sm')
datas    += copy_metadata('en_core_web_sm')
_spacy_hiddenimports += collect_submodules('en_core_web_sm')


# 3. openai / httpx 证书等
# import certifi
# datas += collect_data_files('certifi')


# ─────────────────────────────────────────────
# 隐式导入（PyInstaller 静态分析时可能漏掉的）
# ─────────────────────────────────────────────
hiddenimports = _spacy_hiddenimports + [
    # Flask 相关
    'flask', 'flask_cors', 'werkzeug', 'werkzeug.serving',
    'werkzeug.routing', 'werkzeug.exceptions',
    'jinja2', 'jinja2.ext', 'itsdangerous', 'click',

    # 文档处理
    'docx', 'docx.oxml', 'docx.oxml.ns', 'docx.oxml.shared',
    'lxml', 'lxml.etree', 'lxml._elementpath',
    'PIL', 'PIL.Image',

    # 网络
    'requests', 'urllib3', 'certifi',
    'openai', 'httpx',

    # 工具
    'dotenv', 'json', 'uuid', 'logging',

    # spaCy（可选）
    # 'spacy', 'en_core_web_sm',

    # 客户端 GUI 模块（动态 import，需显式声明）
    'format_check_client',
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog',
    'tkinter.messagebox', 'tkinter.scrolledtext',

    # 检测服务（project-specific）
    # 'services.paper_format_service',
    # 'services.paper_format_detector',
    # 'services.document_annotator',
    # 'services.paper_detect.Title_detect',
    # 'services.paper_detect.Abstract_detect',
    # 'services.paper_detect.Keywords_detect',
    # 'services.paper_detect.Content_detect',
    # 'services.paper_detect.Formula_detect',
    # 'services.paper_detect.Figure_detect',
    # 'services.paper_detect.Figure_content_detect',
    # 'services.paper_detect.Table_detect',
    # 'services.paper_detect.Reference_detect',
    # 'services.paper_detect.Chinese_section_detect',
    # 'services.paper_detect.Classification_detect',
    # 'services.paper_detect.detect_wrappers',
    # 'services.paper_detect.word_report_generator',
]

# ─────────────────────────────────────────────
# 分析
# ─────────────────────────────────────────────
a = Analysis(
    ['format_check_launcher.py'],
    pathex=[ROOT, BACKEND_DIR, SERVICES_DIR],  # 让 PyInstaller 搜索 backend/ 和 services/
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除主 Web 系统的重量级依赖（打包时不需要）
        'torch', 'torchvision', 'torchaudio',
        'transformers', 'sentence_transformers',
        'sklearn', 'scipy', 
        'tensorflow', 'keras',
        'matplotlib', 'pandas',
        'Flask_SQLAlchemy', 'sqlalchemy',
        'Flask_Login', 'Flask_Mail', 'Flask_Principal',
        'redis', 'pymysql',
        'jieba',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir 模式（比 onefile 启动快得多）
    name='论文格式检测系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # 需要安装 upx.exe 到 PATH，可提升压缩率
    console=False,                  # 不显示黑色控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',              # 取消注释并提供 .ico 文件可自定义图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='论文格式检测系统',           # 输出目录名
)
