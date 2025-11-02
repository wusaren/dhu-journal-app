"""
通用帮助函数
从 app.py 中提取的通用函数，保持完全兼容
"""
import os
from datetime import datetime

def get_file_type(filename):
    """获取文件类型 - 从 app.py 中提取，保持完全兼容"""
    if '.' in filename:
        ext = filename.split('.')[-1].lower()
        # 只返回允许的文件类型，其他都默认为pdf
        if ext in ['pdf', 'docx', 'xlsx']:
            return ext
        else:
            return 'pdf'  # 默认为pdf类型
    else:
        return 'pdf'  # 默认为pdf类型

def generate_timestamp():
    """生成时间戳"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def ensure_upload_directory(upload_folder='uploads'):
    """确保上传目录存在"""
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder

def format_file_response(message, file_id, filename, file_path, file_size, journal_id, **kwargs):
    """格式化文件上传响应 - 保持与前端兼容的响应格式"""
    response_data = {
        'message': message,
        'fileId': file_id,
        'filename': filename,
        'filePath': file_path,
        'fileSize': file_size,
        'journalId': journal_id
    }
    # 添加额外的参数
    response_data.update(kwargs)
    return response_data









