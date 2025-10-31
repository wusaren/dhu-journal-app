"""
文件路由
从 app.py 中提取文件相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify, send_file
from services.file_service import FileService

files_bp = Blueprint('files', __name__, url_prefix='/api')

@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """文件上传 - 从 app.py 中提取，保持完全兼容"""
    try:
        if 'file' not in request.files:
            return jsonify({'message': '没有选择文件'}), 400
        
        file = request.files['file']
        journal_id = request.form.get('journalId', '1')
        
        file_service = FileService()
        result = file_service.upload_file(file, journal_id)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        return jsonify({'message': f'文件上传失败: {str(e)}'}), 500

@files_bp.route('/download/<filename>')
def download_file(filename):
    """文件下载 - 从 app.py 中提取，保持完全兼容"""
    file_service = FileService()
    result = file_service.download_file(filename)
    
    if result['success']:
        return send_file(result['file_path'], as_attachment=True)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@files_bp.route('/preview/<filename>')
def preview_file(filename):
    """文件预览 - 从 app.py 中提取，保持完全兼容"""
    file_service = FileService()
    result = file_service.preview_file(filename)
    
    if result['success']:
        file_type = result['file_type']
        if file_type == 'pdf':
            return send_file(result['file_path'], as_attachment=False)
        elif file_type in ['docx', 'xlsx']:
            return send_file(result['file_path'], as_attachment=False)
        else:
            return send_file(result['file_path'], as_attachment=True)
    else:
        return jsonify({'message': result['message']}), result['status_code']





