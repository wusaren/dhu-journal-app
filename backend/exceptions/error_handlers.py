"""
全局异常处理器
为后续封装做准备，暂时不影响现有功能
"""
from flask import jsonify
import logging

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """注册全局异常处理器 - 暂时不启用，保持现有错误处理方式"""
    
    # 这些处理器暂时不启用，保持现有的错误处理方式
    # 等所有模块封装完成后再启用
    
    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({'message': '资源不存在'}), 404
    
    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error(f"内部服务器错误: {str(e)}")
        return jsonify({'message': '服务器内部错误'}), 500

