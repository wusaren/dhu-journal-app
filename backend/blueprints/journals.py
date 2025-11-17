"""
期刊路由
从 app.py 中提取期刊相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.journal_service import JournalService

journals_bp = Blueprint('journals', __name__, url_prefix='/api')

@journals_bp.route('/journals', methods=['GET'])
def get_journals():
    """获取期刊列表 - 从 app.py 中提取，保持完全兼容"""
    journal_service = JournalService()
    result = journal_service.get_all_journals()
    
    if result['success']:
        return jsonify(result['data'])
    else:
        return jsonify({'message': result['message']}), result['status_code']

@journals_bp.route('/journals/create', methods=['POST'])
def create_journal():
    """创建期刊 - 从 app.py 中提取，保持完全兼容"""
    data = request.get_json()
    journal_service = JournalService()
    result = journal_service.create_journal(data)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@journals_bp.route('/journals/<int:journal_id>', methods=['DELETE'])
def delete_journal(journal_id):
    """删除期刊 - 从 app.py 中提取，保持完全兼容"""
    journal_service = JournalService()
    result = journal_service.delete_journal(journal_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'message': result['message']}), result['status_code']

