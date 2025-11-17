"""
数据验证函数
从 app.py 中提取的验证逻辑，保持完全兼容
"""
def validate_journal_data(data):
    """验证期刊数据 - 从 app.py 中提取"""
    required_fields = ['issue', 'title', 'publish_date', 'status']
    for field in required_fields:
        if not data.get(field):
            return False, f'缺少必填字段: {field}'
    return True, None

def validate_paper_data(data):
    """验证论文数据 - 从 app.py 中提取"""
    required_fields = ['journal_id', 'title', 'authors', 'first_author', 'page_start', 'manuscript_id']
    for field in required_fields:
        if not data.get(field):
            return False, f'缺少必填字段: {field}'
    return True, None

def validate_file_upload(file):
    """验证文件上传 - 从 app.py 中提取"""
    if not file or file.filename == '':
        return False, '没有选择文件'
    
    # 检查文件类型
    from utils.helpers import get_file_type
    file_type = get_file_type(file.filename)
    if file_type not in ['pdf', 'docx', 'xlsx']:
        return False, '不支持的文件类型'
    
    return True, None

