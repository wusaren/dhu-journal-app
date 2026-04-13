"""
论文格式检测 Server 端
架构：C/S（仅保留检测功能，无用户认证/数据库）

启动方式：
    python format_check_server.py
    默认监听 http://0.0.0.0:5001
"""

import os
import sys
import uuid
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ──────────────────────────────────────────────
# 将 backend 目录加入 sys.path，复用原有检测模块
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
sys.path.insert(0, BACKEND_DIR)

from services.paper_format_service import PaperFormatService

# ──────────────────────────────────────────────
# 目录配置（服务端本地存储，无需数据库）
# ──────────────────────────────────────────────
TEMP_DIR       = os.path.join(BASE_DIR, 'cs_data', 'temp')       # 上传的原始文件
REPORTS_DIR    = os.path.join(BASE_DIR, 'cs_data', 'reports')    # 检测报告 (.txt)
ANNOTATED_DIR  = os.path.join(BASE_DIR, 'cs_data', 'annotated')  # 批注文档 (.docx)
LOG_DIR        = os.path.join(BASE_DIR, 'cs_data', 'logs')

for d in [TEMP_DIR, REPORTS_DIR, ANNOTATED_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# ──────────────────────────────────────────────
# 日志
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, 'server.log'), encoding='utf-8'),
    ]
)
logger = logging.getLogger('format_check_server')

# ──────────────────────────────────────────────
# Flask 应用
# ──────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # 允许跨域（桌面客户端用本地 HTTP 访问）

ALLOWED_EXTENSIONS = {'docx'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ──────────────────────────────────────────────
# 路由
# ──────────────────────────────────────────────

@app.route('/api/ping', methods=['GET'])
def ping():
    """健康检查"""
    return jsonify({'status': 'ok', 'message': 'format-check-server running'})


@app.route('/api/modules', methods=['GET'])
def get_modules():
    """返回可用的检测模块列表"""
    modules = [
        {'key': 'Title',           'name': '英文标题、作者与单位'},
        {'key': 'Abstract',        'name': '英文摘要'},
        {'key': 'Keywords',        'name': '英文关键词'},
        {'key': 'Content',         'name': '正文'},
        {'key': 'Formula',         'name': '公式'},
        {'key': 'Figure',          'name': '图'},
        {'key': 'Table',           'name': '表格'},
        {'key': 'Reference',       'name': '参考文献'},
        {'key': 'Chinese_section', 'name': '中文部分'},
    ]
    return jsonify({'success': True, 'data': modules})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    上传论文 DOCX 文件
    请求：multipart/form-data，字段 file（必填）、title（可选）
    返回：{ success, file_id, filename, title }
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未找到文件字段 file'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': '仅支持 .docx 格式'}), 400

    title = request.form.get('title', '') or os.path.splitext(file.filename)[0]
    file_id = str(uuid.uuid4())
    safe_name = secure_filename(file.filename)
    save_path = os.path.join(TEMP_DIR, f"{file_id}_{safe_name}")

    file.save(save_path)
    logger.info(f"文件已上传: {save_path}  title={title}")

    return jsonify({
        'success': True,
        'file_id': file_id,
        'filename': safe_name,
        'title': title,
        'temp_path': save_path,
    })


@app.route('/api/check', methods=['POST'])
def check_format():
    """
    执行格式检测
    请求 JSON：
    {
        "file_id":   "...",          # upload 接口返回的 file_id
        "temp_path": "...",          # upload 接口返回的 temp_path
        "title":     "...",
        "modules":   ["Title","Abstract",...],   # 空列表 = 全部
        "skip_checks": {},           # 可选，格式同原项目
        "enable_figure_api": false,
        "enable_classification_api": false
    }
    返回：{ success, file_id, result, report_text, report_url, annotated_url }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({'success': False, 'message': '请求体为空'}), 400

    file_id  = data.get('file_id')
    temp_path = data.get('temp_path')
    title    = data.get('title', 'untitled')
    modules  = data.get('modules') or None          # None 表示全部
    skip_checks           = data.get('skip_checks', {})
    enable_figure_api     = data.get('enable_figure_api', False)
    enable_classification = data.get('enable_classification_api', False)

    if not temp_path or not os.path.exists(temp_path):
        return jsonify({'success': False, 'message': f'文件不存在: {temp_path}'}), 404

    logger.info(f"开始检测  file_id={file_id}  modules={modules}")

    try:
        service = PaperFormatService()
        result  = service.check_all(
            docx_path=temp_path,
            enable_figure_api=enable_figure_api,
            enable_classification_api=enable_classification,
            modules=modules,
            reports_dir=REPORTS_DIR,
            annotate_dir=ANNOTATED_DIR,
            skip_checks=skip_checks,
        )
    except Exception as e:
        logger.error(f"检测异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'检测服务异常: {e}'}), 500

    if not result.get('success'):
        return jsonify(result), 500

    # 构建下载 URL（供客户端按需下载）
    report_fn        = result['data'].get('report_filename', '')
    word_report_fn   = result['data'].get('word_report_filename', '')
    annotated_fn     = result['data'].get('annotated_filename', '')

    return jsonify({
        'success':          True,
        'file_id':          file_id,
        'result':           result,
        'report_url':       f'/api/report/{report_fn}'       if report_fn       else None,
        'word_report_url':  f'/api/word-report/{word_report_fn}' if word_report_fn  else None,
        'annotated_url':    f'/api/annotated/{annotated_fn}' if annotated_fn    else None,
        'message':          '检测完成',
    })


@app.route('/api/report/<filename>', methods=['GET'])
def download_report(filename):
    """下载检测报告 (.txt)"""
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'success': False, 'message': '报告文件不存在'}), 404
    return send_file(path, as_attachment=True,
                     download_name=filename, mimetype='text/plain; charset=utf-8')


@app.route('/api/word-report/<filename>', methods=['GET'])
def download_word_report(filename):
    """下载Word格式检测报告 (.docx)"""
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'success': False, 'message': 'Word报告文件不存在'}), 404
    return send_file(
        path, as_attachment=True, download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@app.route('/api/annotated/<filename>', methods=['GET'])
def download_annotated(filename):
    """下载批注文档 (.docx)"""
    path = os.path.join(ANNOTATED_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'success': False, 'message': '批注文档不存在'}), 404
    return send_file(
        path, as_attachment=True, download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"论文格式检测服务器启动  http://0.0.0.0:{port}")
    logger.info(f"数据目录: {os.path.join(BASE_DIR, 'cs_data')}")
    app.run(host='0.0.0.0', port=port, debug=False)
