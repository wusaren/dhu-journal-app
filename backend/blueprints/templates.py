"""
模板路由
从 app.py 中提取模板相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify
from services.template_service import TemplateService
import logging

logger = logging.getLogger(__name__)

templates_bp = Blueprint('templates', __name__, url_prefix='/api')

@templates_bp.route('/journal/<int:journal_id>/template', methods=['POST'])
def upload_template(journal_id):
    """上传统计表模板文件"""
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        template_service = TemplateService()
        result = template_service.upload_template(journal_id, file)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'headers': result['data']['headers'],
                'template_id': result['data']['template_id']
            })
        else:
            return jsonify({'success': False, 'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"模板上传错误: {str(e)}")
        return jsonify({'success': False, 'message': f'模板上传失败: {str(e)}'}), 500

@templates_bp.route('/journal/<int:journal_id>/template/headers', methods=['GET'])
def get_template_headers(journal_id):
    """获取模板表头识别结果"""
    try:
        template_service = TemplateService()
        result = template_service.get_template_headers(journal_id)
        
        # 统一返回200状态码，通过success字段区分是否有模板
        return jsonify({
            'success': result['success'],
            'has_template': result['data'].get('has_template', False),
            'headers': result['data'].get('headers', []),
            'template_file_path': result['data'].get('template_file_path'),
            'message': result.get('message', '')
        })
    
    except Exception as e:
        logger.error(f"获取模板表头错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取模板表头失败: {str(e)}'}), 500

@templates_bp.route('/journal/<int:journal_id>/template/mapping', methods=['PUT'])
def save_template_mapping(journal_id):
    """保存表头映射配置"""
    try:
        data = request.get_json()
        column_mapping = data.get('column_mapping')
        
        if not column_mapping:
            return jsonify({'success': False, 'message': '缺少column_mapping参数'}), 400
        
        template_service = TemplateService()
        result = template_service.save_template_mapping(journal_id, column_mapping)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message']
            })
        else:
            return jsonify({'success': False, 'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"保存表头映射配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'保存配置失败: {str(e)}'}), 500

@templates_bp.route('/journal/<int:journal_id>/template', methods=['GET'])
def get_template(journal_id):
    """获取当前模板配置"""
    try:
        template_service = TemplateService()
        result = template_service.get_template(journal_id)
        
        # 统一返回200状态码，通过success字段区分是否有模板
        return jsonify({
            'success': result['success'],
            'has_template': result['data'].get('has_template', False),
            'template': result['data'].get('template'),
            'message': result.get('message', '')
        })
    
    except Exception as e:
        logger.error(f"获取模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取模板配置失败: {str(e)}'}), 500

@templates_bp.route('/journal/<int:journal_id>/template', methods=['DELETE'])
def delete_template(journal_id):
    """删除模板"""
    try:
        template_service = TemplateService()
        result = template_service.delete_template(journal_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message']
            })
        else:
            return jsonify({'success': False, 'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"删除模板错误: {str(e)}")
        return jsonify({'success': False, 'message': f'删除模板失败: {str(e)}'}), 500

@templates_bp.route('/template/system-fields', methods=['GET'])
def get_system_fields():
    """获取所有可用的系统字段列表"""
    try:
        template_service = TemplateService()
        result = template_service.get_system_fields()
        
        if result['success']:
            return jsonify({
                'success': True,
                'fields': result['data']['fields']
            })
        else:
            return jsonify({'success': False, 'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"获取系统字段列表错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取系统字段列表失败: {str(e)}'}), 500

