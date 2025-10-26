"""
论文路由
从 app.py 中提取论文相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify
from services.paper_service import PaperService

papers_bp = Blueprint('papers', __name__, url_prefix='/api')

@papers_bp.route('/papers', methods=['GET'])
def get_papers():
    """获取论文列表 - 从 app.py 中提取，保持完全兼容"""
    journal_id = request.args.get('journalId', type=int)
    paper_service = PaperService()
    result = paper_service.get_papers(journal_id)
    
    if result['success']:
        return jsonify(result['data'])
    else:
        return jsonify({'message': result['message']}), result['status_code']

@papers_bp.route('/papers/create', methods=['POST'])
def create_paper():
    """创建论文 - 从 app.py 中提取，保持完全兼容"""
    data = request.get_json()
    paper_service = PaperService()
    result = paper_service.create_paper(data)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@papers_bp.route('/papers/<int:paper_id>', methods=['PUT'])
def update_paper(paper_id):
    """更新论文 - 从 app.py 中提取，保持完全兼容"""
    data = request.get_json()
    paper_service = PaperService()
    result = paper_service.update_paper(paper_id, data)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@papers_bp.route('/papers/<int:paper_id>', methods=['DELETE'])
def delete_paper(paper_id):
    """删除论文 - 从 app.py 中提取，保持完全兼容"""
    paper_service = PaperService()
    result = paper_service.delete_paper(paper_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

