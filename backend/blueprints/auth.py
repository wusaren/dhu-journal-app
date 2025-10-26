"""
认证路由
从 app.py 中提取认证相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录 - 从 app.py 中提取，保持完全兼容"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        auth_service = AuthService()
        result = auth_service.login(username, password)
        
        if result['success']:
            return jsonify({
                'message': result['message'],
                'access_token': result['access_token'],
                'user': result['user']
            })
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        return jsonify({'message': f'登录失败: {str(e)}'}), 500

