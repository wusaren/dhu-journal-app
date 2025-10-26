"""
导出路由
从 app.py 中提取导出相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify
from services.export_service import ExportService

exports_bp = Blueprint('exports', __name__, url_prefix='/api')

@exports_bp.route('/export/toc', methods=['POST'])
def export_toc():
    """生成目录 - 从 app.py 中提取，保持完全兼容"""
    data = request.get_json()
    journal_id = data.get('journalId')
    
    if not journal_id:
        return jsonify({'message': '缺少期刊ID'}), 400
    
    export_service = ExportService()
    result = export_service.export_toc(journal_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@exports_bp.route('/export/tuiwen', methods=['POST'])
def export_tuiwen():
    """生成推文 - 从 app.py 中提取，保持完全兼容"""
    data = request.get_json()
    journal_id = data.get('journalId')
    
    if not journal_id:
        return jsonify({'message': '缺少期刊ID'}), 400
    
    export_service = ExportService()
    result = export_service.export_tuiwen(journal_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@exports_bp.route('/export/excel', methods=['POST'])
def export_excel():
    """生成统计表 - 从 app.py 中提取，保持完全兼容"""
    data = request.get_json()
    journal_id = data.get('journalId')
    
    if not journal_id:
        return jsonify({'message': '缺少期刊ID'}), 400
    
    export_service = ExportService()
    result = export_service.export_excel(journal_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

