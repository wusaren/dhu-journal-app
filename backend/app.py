from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from flask_cors import CORS
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import logging
import bcrypt

# 导入配置和模型
from config import current_config
from models import User, Journal, Paper, FileUpload, db

# 导入封装后的模块
from services.auth_service import AuthService
from services.journal_service import JournalService
from services.paper_service import PaperService
from services.file_service import FileService
from services.export_service import ExportService

app = Flask(__name__)

# 加载配置
app.config.from_object(current_config)

# JWT配置
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

# 初始化扩展
db.init_app(app)
jwt = JWTManager(app)
CORS(app)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_file_type(filename):
    """获取文件类型"""
    if '.' in filename:
        ext = filename.split('.')[-1].lower()
        # 只返回允许的文件类型，其他都默认为pdf
        if ext in ['pdf', 'docx', 'xlsx']:
            return ext
        else:
            return 'pdf'  # 默认为pdf类型
    else:
        return 'pdf'  # 默认为pdf类型

def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员用户
        auth_service = AuthService()
        auth_service.create_default_admin()

# 健康检查
@app.route('/api/health')
def health_check():
    return jsonify({'status': 'ok', 'message': '期刊管理系统运行正常'})

# 用户认证
@app.route('/api/login', methods=['POST'])
def login():
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
        logger.error(f"登录错误: {str(e)}")
        return jsonify({'message': f'登录失败: {str(e)}'}), 500

# 获取期刊列表
@app.route('/api/journals', methods=['GET'])
def get_journals():
    try:
        journal_service = JournalService()
        result = journal_service.get_all_journals()
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"获取期刊列表错误: {str(e)}")
        return jsonify({'message': f'获取期刊列表失败: {str(e)}'}), 500

# 创建期刊
@app.route('/api/journals/create', methods=['POST'])
def create_journal():
    try:
        data = request.get_json()
        journal_service = JournalService()
        result = journal_service.create_journal(data)
        
        if result['success']:
            return jsonify(result)
        else:
            # 如果有额外的字段（如duplicate），也要包含在响应中
            response_data = {'message': result['message']}
            if 'duplicate' in result:
                response_data['duplicate'] = result['duplicate']
            return jsonify(response_data), result['status_code']
    
    except Exception as e:
        logger.error(f"创建期刊错误: {str(e)}")
        return jsonify({'message': f'创建期刊失败: {str(e)}'}), 500

# 文件上传
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'message': '没有选择文件'}), 400
        
        file = request.files['file']
        journal_id = request.form.get('journalId', '1')
        
        if file.filename == '':
            return jsonify({'message': '没有选择文件'}), 400
        
        file_service = FileService()
        result = file_service.upload_file(file, journal_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"文件上传错误: {str(e)}")
        return jsonify({'message': f'文件上传失败: {str(e)}'}), 500

# 覆盖上传文件
@app.route('/api/upload/overwrite', methods=['POST'])
def upload_file_overwrite():
    """带覆盖选项的文件上传"""
    try:
        if 'file' not in request.files:
            return jsonify({'message': '没有选择文件'}), 400
        
        file = request.files['file']
        journal_id = request.form.get('journalId', '1')
        overwrite_paper_id = request.form.get('overwritePaperId')
        
        if file.filename == '':
            return jsonify({'message': '没有选择文件'}), 400
        
        file_service = FileService()
        result = file_service.upload_file_with_overwrite(file, journal_id, overwrite_paper_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"覆盖上传错误: {str(e)}")
        return jsonify({'message': f'覆盖上传失败: {str(e)}'}), 500

# 生成目录
@app.route('/api/export/toc', methods=['POST'])
def export_toc():
    """生成目录Word文档"""
    try:
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
    
    except Exception as e:
        logger.error(f"目录生成错误: {str(e)}")
        return jsonify({'message': f'目录生成失败: {str(e)}'}), 500
# 生成推文
@app.route('/api/export/tuiwen', methods=['POST'])
def export_tuiwen():
    """生成推文Word文档"""
    try:
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
    
    except Exception as e:
        logger.error(f"推文生成错误: {str(e)}")
        return jsonify({'message': f'推文生成失败: {str(e)}'}), 500
# 生成统计表
@app.route('/api/export/excel', methods=['POST'])
def export_excel():
    """生成统计表Excel"""
    try:
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
    
    except Exception as e:
        logger.error(f"统计表生成错误: {str(e)}")
        return jsonify({'message': f'统计表生成失败: {str(e)}'}), 500

# 获取论文列表
@app.route('/api/papers', methods=['GET'])
def get_papers():
    """获取论文列表"""
    try:
        journal_id = request.args.get('journalId', type=int)
        paper_service = PaperService()
        result = paper_service.get_papers(journal_id)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"获取论文列表错误: {str(e)}")
        return jsonify({'message': f'获取论文列表失败: {str(e)}'}), 500

# 创建论文
@app.route('/api/papers/create', methods=['POST'])
def create_paper():
    """创建论文"""
    try:
        data = request.get_json()
        paper_service = PaperService()
        result = paper_service.create_paper(data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"创建论文错误: {str(e)}")
        return jsonify({'message': f'创建论文失败: {str(e)}'}), 500

# 更新论文
@app.route('/api/papers/<int:paper_id>', methods=['PUT'])
def update_paper(paper_id):
    """更新论文"""
    try:
        data = request.get_json()
        paper_service = PaperService()
        result = paper_service.update_paper(paper_id, data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"更新论文错误: {str(e)}")
        return jsonify({'message': f'更新论文失败: {str(e)}'}), 500

# 删除论文
@app.route('/api/papers/<int:paper_id>', methods=['DELETE'])
def delete_paper(paper_id):
    """删除论文"""
    try:
        paper_service = PaperService()
        result = paper_service.delete_paper(paper_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"删除论文错误: {str(e)}")
        return jsonify({'message': f'删除论文失败: {str(e)}'}), 500

# 删除期刊
@app.route('/api/journals/<int:journal_id>', methods=['DELETE'])
def delete_journal(journal_id):
    """删除期刊（如果期刊下存在论文则不允许删除）"""
    try:
        journal_service = JournalService()
        result = journal_service.delete_journal(journal_id)
        
        if result['success']:
            return jsonify(result)
        else:
            # 如果有额外的字段（如papers_count、duplicate），也要包含在响应中
            response_data = {'message': result['message']}
            if 'papers_count' in result:
                response_data['papers_count'] = result['papers_count']
            if 'duplicate' in result:
                response_data['duplicate'] = result['duplicate']
            return jsonify(response_data), result['status_code']
    
    except Exception as e:
        logger.error(f"删除期刊错误: {str(e)}")
        return jsonify({'message': f'删除期刊失败: {str(e)}'}), 500

# 文件下载
@app.route('/api/download/<filename>')
def download_file(filename):
    """文件下载接口"""
    try:
        file_service = FileService()
        result = file_service.download_file(filename)
        
        if result['success']:
            return send_file(result['file_path'], as_attachment=True)
        else:
            return jsonify({'message': result['message']}), result['status_code']

    except Exception as e:
        logger.error(f"文件下载错误: {str(e)}")
        return jsonify({'message': f'文件下载失败: {str(e)}'}), 500

# 文件预览
@app.route('/api/preview/<filename>')
def preview_file(filename):
    """文件预览接口 - 不强制下载，在浏览器中预览"""
    try:
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

    except Exception as e:
        logger.error(f"文件预览错误: {str(e)}")
        return jsonify({'message': f'文件预览失败: {str(e)}'}), 500


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
