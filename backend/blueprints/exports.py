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
    """生成统计表 - 支持自定义列配置"""
    data = request.get_json()
    journal_id = data.get('journalId')
    columns_config = data.get('columns', None)  # 接收列配置
    
    if not journal_id:
        return jsonify({'message': '缺少期刊ID'}), 400
    
    export_service = ExportService()
    result = export_service.export_excel(journal_id, columns_config)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@exports_bp.route('/export/columns', methods=['GET'])
def get_available_columns():
    """获取所有可用的统计表列定义"""
    try:
        # 定义所有可用的列
        available_columns = [
            {'key': 'manuscript_id', 'label': '稿件号', 'category': '基本信息'},
            {'key': 'pdf_pages', 'label': '页数', 'category': '基本信息'},
            {'key': 'first_author', 'label': '一作', 'category': '作者信息'},
            {'key': 'corresponding', 'label': '通讯', 'category': '作者信息'},
            {'key': 'authors', 'label': '作者', 'category': '作者信息'},
            {'key': 'issue', 'label': '刊期', 'category': '基本信息'},
            {'key': 'is_dhu', 'label': '是否东华大学', 'category': '基本信息'},
            {'key': 'title', 'label': '标题', 'category': '论文信息'},
            {'key': 'chinese_title', 'label': '中文标题', 'category': '论文信息'},
            {'key': 'chinese_authors', 'label': '中文作者', 'category': '作者信息'},
            {'key': 'doi', 'label': 'DOI', 'category': '论文信息'},
            {'key': 'page_start', 'label': '起始页码', 'category': '基本信息'},
            {'key': 'page_end', 'label': '结束页码', 'category': '基本信息'},
        ]
        
        return jsonify({
            'success': True,
            'columns': available_columns
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取可用列失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500






