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
from models import User, Journal, Paper, FileUpload, FormatCheckFile, db

# 导入封装后的模块
from services.auth_service import AuthService
from services.journal_service import JournalService
from services.paper_service import PaperService
from services.file_service import FileService
from services.export_service import ExportService
from services.paper_format_service import PaperFormatService
from services.column_config_service import ColumnConfigService
from services.template_service import TemplateService
from services.template_config_service import TemplateConfigService
from services.tuiwen_template_service import TuiwenTemplateService

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
# 创建logs目录（如果不存在）
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 配置日志：同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8'),
        logging.StreamHandler()  # 输出到控制台
    ]
)
logger = logging.getLogger(__name__)

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
FORMAT_CHECK_FOLDER = 'uploads/format_check'
FORMAT_CHECK_TEMP_FOLDER = 'uploads/format_check/temp'
FORMAT_CHECK_REPORTS_FOLDER = 'uploads/format_check/reports'
FORMAT_CHECK_ANNOTATE_FOLDER = 'uploads/format_check/annotate'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FORMAT_CHECK_FOLDER'] = FORMAT_CHECK_FOLDER
app.config['FORMAT_CHECK_TEMP_FOLDER'] = FORMAT_CHECK_TEMP_FOLDER
app.config['FORMAT_CHECK_REPORTS_FOLDER'] = FORMAT_CHECK_REPORTS_FOLDER
app.config['FORMAT_CHECK_ANNOTATE_FOLDER'] = FORMAT_CHECK_ANNOTATE_FOLDER

# 创建必要的目录
for folder in [UPLOAD_FOLDER, FORMAT_CHECK_FOLDER, FORMAT_CHECK_TEMP_FOLDER, FORMAT_CHECK_REPORTS_FOLDER, FORMAT_CHECK_ANNOTATE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"创建目录: {folder}")

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
# 获取可用列定义
@app.route('/api/export/columns', methods=['GET'])
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
        logger.error(f"获取可用列失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# 保存列配置
@app.route('/api/export/columns/config', methods=['POST'])
def save_column_config():
    """保存期刊的列配置到 JSON 文件"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        columns_config = data.get('columns', [])
        
        if not journal_id:
            return jsonify({'success': False, 'message': '缺少期刊ID'}), 400
        
        if not columns_config:
            return jsonify({'success': False, 'message': '列配置不能为空'}), 400
        
        config_service = ColumnConfigService()
        result = config_service.save_config(journal_id, columns_config)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    
    except Exception as e:
        logger.error(f"保存列配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'保存配置失败: {str(e)}'}), 500

# 获取列配置
@app.route('/api/export/columns/config/<int:journal_id>', methods=['GET'])
def get_column_config(journal_id):
    """从 JSON 文件加载期刊的列配置"""
    try:
        config_service = ColumnConfigService()
        columns_config = config_service.load_config(journal_id)
        
        if columns_config is None:
            return jsonify({
                'success': True,
                'has_config': False,
                'columns': None
            })
        
        return jsonify({
            'success': True,
            'has_config': True,
            'columns': columns_config
        })
    
    except Exception as e:
        logger.error(f"获取列配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取配置失败: {str(e)}'}), 500

# 上传模板文件
@app.route('/api/journal/<int:journal_id>/template', methods=['POST'])
def upload_template(journal_id):
    """上传Excel模板文件并识别表头"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        # 检查文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'message': '只支持Excel文件（.xlsx, .xls）'}), 400
        
        # 保存临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"temp_template_{journal_id}_{timestamp}_{file.filename}"
        temp_path = os.path.join('uploads', temp_filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(temp_path)
        
        # 提取表头
        template_service = TemplateService()
        headers = template_service.extract_headers_from_excel(temp_path)
        
        if not headers:
            return jsonify({'success': False, 'message': '无法从Excel文件中提取表头'}), 400
        
        # 匹配表头
        matched_headers = template_service.match_headers(headers)
        
        return jsonify({
            'success': True,
            'message': '模板上传成功',
            'headers': matched_headers,
            'template_file_path': temp_path
        })
    
    except Exception as e:
        logger.error(f"上传模板错误: {str(e)}")
        return jsonify({'success': False, 'message': f'上传模板失败: {str(e)}'}), 500

# 获取模板表头识别结果
@app.route('/api/journal/<int:journal_id>/template/headers', methods=['GET'])
def get_template_headers(journal_id):
    """获取模板表头识别结果（如果已保存）"""
    try:
        config_service = TemplateConfigService()
        config = config_service.load_config(journal_id)
        
        if not config:
            return jsonify({
                'success': True,
                'has_template': False,
                'headers': [],
                'message': '该期刊没有模板配置'
            })
        
        return jsonify({
            'success': True,
            'has_template': True,
            'headers': config.get('column_mapping', []),
            'template_file_path': config.get('template_file_path')
        })
    
    except Exception as e:
        logger.error(f"获取模板表头错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取模板表头失败: {str(e)}'}), 500

# 保存模板映射配置
@app.route('/api/journal/<int:journal_id>/template/mapping', methods=['PUT'])
def save_template_mapping(journal_id):
    """保存模板表头映射配置"""
    try:
        data = request.get_json()
        template_file_path = data.get('template_file_path')
        column_mapping = data.get('column_mapping', [])
        
        if not template_file_path:
            return jsonify({'success': False, 'message': '缺少模板文件路径'}), 400
        
        if not column_mapping:
            return jsonify({'success': False, 'message': '列映射配置不能为空'}), 400
        
        config_service = TemplateConfigService()
        result = config_service.save_template(journal_id, template_file_path, column_mapping)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    
    except Exception as e:
        logger.error(f"保存模板映射错误: {str(e)}")
        return jsonify({'success': False, 'message': f'保存映射失败: {str(e)}'}), 500

# 获取模板配置
@app.route('/api/journal/<int:journal_id>/template', methods=['GET'])
def get_template(journal_id):
    """获取模板配置"""
    try:
        config_service = TemplateConfigService()
        config = config_service.load_config(journal_id)
        
        if not config:
            return jsonify({
                'success': True,
                'has_template': False,
                'message': '该期刊没有模板配置'
            })
        
        return jsonify({
            'success': True,
            'has_template': True,
            'template_file_path': config.get('template_file_path'),
            'column_mapping': config.get('column_mapping', []),
            'created_at': config.get('created_at'),
            'updated_at': config.get('updated_at')
        })
    
    except Exception as e:
        logger.error(f"获取模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取模板配置失败: {str(e)}'}), 500

# 删除模板
@app.route('/api/journal/<int:journal_id>/template', methods=['DELETE'])
def delete_template(journal_id):
    """删除模板配置"""
    try:
        config_service = TemplateConfigService()
        result = config_service.delete_config(journal_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        logger.error(f"删除模板错误: {str(e)}")
        return jsonify({'success': False, 'message': f'删除模板失败: {str(e)}'}), 500

# 获取系统字段列表
@app.route('/api/template/system-fields', methods=['GET'])
def get_system_fields():
    """获取所有可用的系统字段"""
    try:
        template_service = TemplateService()
        fields = template_service.get_available_system_fields()
        
        return jsonify({
            'success': True,
            'fields': fields
        })
    
    except Exception as e:
        logger.error(f"获取系统字段错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取系统字段失败: {str(e)}'}), 500

# 上传推文模板文件
@app.route('/api/journal/<int:journal_id>/tuiwen-template', methods=['POST'])
def upload_tuiwen_template(journal_id):
    """上传Word推文模板文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        # 检查文件类型
        if not file.filename.endswith(('.docx', '.doc')):
            return jsonify({'success': False, 'message': '只支持Word文件（.docx, .doc）'}), 400
        
        # 保存临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"temp_tuiwen_template_{journal_id}_{timestamp}_{file.filename}"
        temp_path = os.path.join('uploads', temp_filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(temp_path)
        
        return jsonify({
            'success': True,
            'message': '推文模板上传成功',
            'template_file_path': temp_path
        })
    
    except Exception as e:
        logger.error(f"上传推文模板错误: {str(e)}")
        return jsonify({'success': False, 'message': f'上传模板失败: {str(e)}'}), 500

# 保存推文模板配置
@app.route('/api/journal/<int:journal_id>/tuiwen-template', methods=['PUT'])
def save_tuiwen_template(journal_id):
    """保存推文模板字段配置"""
    try:
        data = request.get_json()
        fields = data.get('fields', [])
        
        if not fields:
            return jsonify({'success': False, 'message': '字段配置不能为空'}), 400
        
        config_service = TuiwenTemplateService()
        result = config_service.save_template_config(journal_id, fields)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    
    except Exception as e:
        logger.error(f"保存推文模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'保存配置失败: {str(e)}'}), 500

# 获取推文模板配置
@app.route('/api/journal/<int:journal_id>/tuiwen-template', methods=['GET'])
def get_tuiwen_template(journal_id):
    """获取推文模板配置"""
    try:
        config_service = TuiwenTemplateService()
        config = config_service.load_config(journal_id)
        
        if not config:
            return jsonify({
                'success': True,
                'has_template': False,
                'message': '该期刊没有推文模板配置'
            })
        
        # 新格式：返回字段配置
        if 'fields' in config:
            return jsonify({
                'success': True,
                'has_template': True,
                'fields': config.get('fields', []),
                'created_at': config.get('created_at'),
                'updated_at': config.get('updated_at')
            })
        # 旧格式：兼容处理
        else:
            return jsonify({
                'success': True,
                'has_template': True,
                'template_file_path': config.get('template_file_path'),
                'created_at': config.get('created_at'),
                'updated_at': config.get('updated_at')
            })
    
    except Exception as e:
        logger.error(f"获取推文模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取模板配置失败: {str(e)}'}), 500

# 删除推文模板
@app.route('/api/journal/<int:journal_id>/tuiwen-template', methods=['DELETE'])
def delete_tuiwen_template(journal_id):
    """删除推文模板配置"""
    try:
        config_service = TuiwenTemplateService()
        result = config_service.delete_config(journal_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        logger.error(f"删除推文模板错误: {str(e)}")
        return jsonify({'success': False, 'message': f'删除模板失败: {str(e)}'}), 500

# 生成统计表
@app.route('/api/export/excel', methods=['POST'])
def export_excel():
    """生成统计表Excel - 优先使用模板，否则使用列配置"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        columns_config = data.get('columns', None)  # 接收列配置
        
        if not journal_id:
            return jsonify({'message': '缺少期刊ID'}), 400
        
        export_service = ExportService()
        
        # 优先检查是否有模板配置
        template_config_service = TemplateConfigService()
        template_config = template_config_service.load_config(journal_id)
        
        if template_config and template_config.get('template_file_path') and template_config.get('column_mapping'):
            # 使用模板生成
            logger.info(f"使用模板生成统计表: {template_config.get('template_file_path')}")
            result = export_service.export_excel_with_template(
                journal_id,
                template_config['template_file_path'],
                template_config['column_mapping']
            )
        else:
            # 使用列配置生成
            # 如果没有传入配置，尝试从 JSON 文件加载
            if columns_config is None:
                config_service = ColumnConfigService()
                columns_config = config_service.load_config(journal_id)
                if columns_config:
                    logger.info(f"从配置文件加载了期刊 {journal_id} 的列配置")
            
            result = export_service.export_excel(journal_id, columns_config)
        
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


# ==================== 论文格式检测 API ====================

# 获取所有格式审查文件列表
@app.route('/api/paper-format/files', methods=['GET'])
def get_format_check_files():
    """获取所有格式审查文件列表"""
    try:
        files = FormatCheckFile.query.order_by(FormatCheckFile.created_at.desc()).all()
        
        files_data = []
        for file in files:
            files_data.append({
                'id': file.id,
                'fileId': file.id,
                'title': file.title,
                'submitDate': file.submit_date.strftime('%Y-%m-%d'),
                'tempFilePath': file.temp_file_path,
                'reportPath': file.report_path,
                'annotatedPath': file.annotated_path,
                'checkStatus': file.check_status,
                'totalChecks': file.total_checks,
                'passedChecks': file.passed_checks,
                'failedChecks': file.failed_checks,
                'passRate': file.pass_rate,
                'createdAt': file.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({
            'success': True,
            'data': files_data,
            'message': '获取列表成功'
        })
    
    except Exception as e:
        logger.error(f"获取格式审查文件列表错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取列表失败: {str(e)}'
        }), 500


# 检查标题是否重复
@app.route('/api/paper-format/check-duplicate', methods=['POST'])
def check_duplicate_title():
    """检查论文标题是否重复"""
    try:
        data = request.get_json()
        title = data.get('title')
        
        if not title:
            return jsonify({
                'success': False,
                'message': '标题不能为空'
            }), 400
        
        # 查询是否存在相同标题
        existing_file = FormatCheckFile.query.filter_by(title=title).first()
        
        if existing_file:
            return jsonify({
                'success': True,
                'data': {
                    'exists': True,
                    'file_id': existing_file.id,
                    'submit_date': existing_file.submit_date.strftime('%Y-%m-%d'),
                    'check_status': existing_file.check_status
                },
                'message': '标题已存在'
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'exists': False
                },
                'message': '标题不存在'
            })
    
    except Exception as e:
        logger.error(f"检查标题重复错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'检查失败: {str(e)}'
        }), 500


# 删除格式审查文件记录
@app.route('/api/paper-format/delete/<int:file_id>', methods=['DELETE'])
def delete_format_check_file(file_id):
    """删除格式审查文件记录（覆盖时使用）"""
    try:
        format_check_file = FormatCheckFile.query.get(file_id)
        
        if not format_check_file:
            return jsonify({
                'success': False,
                'message': '文件记录不存在'
            }), 404
        
        # 删除物理文件
        try:
            if os.path.exists(format_check_file.temp_file_path):
                os.remove(format_check_file.temp_file_path)
            if format_check_file.report_path and os.path.exists(format_check_file.report_path):
                os.remove(format_check_file.report_path)
            if format_check_file.annotated_path and os.path.exists(format_check_file.annotated_path):
                os.remove(format_check_file.annotated_path)
        except Exception as e:
            logger.warning(f"删除物理文件失败: {e}")
        
        # 删除数据库记录
        db.session.delete(format_check_file)
        db.session.commit()
        
        logger.info(f"已删除格式审查文件记录: ID={file_id}")
        
        return jsonify({
            'success': True,
            'message': '删除成功'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除文件记录错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        }), 500


# 保存临时文件
@app.route('/api/paper-format/save-temp', methods=['POST'])
def save_temp_file():
    """保存上传的文件到临时目录并插入数据库记录"""
    try:
        # 获取上传的文件
        if 'file' not in request.files:
            return jsonify({
                'success': False, 
                'message': '未上传文件'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False, 
                'message': '文件名为空'
            }), 400
        
        # 检查文件类型
        if not file.filename.endswith('.docx'):
            return jsonify({
                'success': False, 
                'message': '只支持 .docx 格式的文件'
            }), 400
        
        # 获取标题和提交日期
        title = request.form.get('title', file.filename.replace('.docx', ''))
        submit_date_str = request.form.get('submit_date', datetime.now().strftime('%Y-%m-%d'))
        submit_date = datetime.strptime(submit_date_str, '%Y-%m-%d').date()
        
        # 保存临时文件到temp目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"{timestamp}_{secure_filename(file.filename)}"
        temp_path = os.path.join(app.config['FORMAT_CHECK_TEMP_FOLDER'], temp_filename)
        logger.info(f"保存临时文件: {temp_path}")
        file.save(temp_path)
        
        # 插入数据库记录
        format_check_file = FormatCheckFile(
            title=title,
            submit_date=submit_date,
            temp_file_path=temp_path,
            check_status='pending'
        )
        db.session.add(format_check_file)
        db.session.commit()
        
        logger.info(f"格式审查文件记录已创建: ID={format_check_file.id}")
        
        return jsonify({
            'success': True,
            'data': {
                'temp_file_path': temp_path,
                'file_id': format_check_file.id
            },
            'message': '文件保存成功'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存临时文件错误: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'保存失败: {str(e)}'
        }), 500

# 全量检测
@app.route('/api/paper-format/check-all', methods=['POST'])
def check_format_all():
    """执行论文格式全量检测"""
    try:
        # 获取JSON数据
        data = request.get_json()
        temp_file_path = data.get('temp_file_path')
        file_id = data.get('file_id')  # 获取文件ID
        
        if not temp_file_path:
            return jsonify({
                'success': False, 
                'message': '缺少临时文件路径'
            }), 400
        
        # 检查文件是否存在
        if not os.path.exists(temp_file_path):
            return jsonify({
                'success': False, 
                'message': '临时文件不存在'
            }), 404
        
        # 获取参数
        enable_figure_api = data.get('enableFigureApi', False)
        modules = data.get('modules')  # 可选，逗号分隔的模块名称
        
        if modules:
            modules_list = [m.strip() for m in modules.split(',')]
        else:
            modules_list = None
        
        # 执行检测
        paper_format_service = PaperFormatService()
        all_reports_dict = paper_format_service.check_all(
            temp_file_path,
            enable_figure_api=enable_figure_api,
            modules=modules_list
        )
 
        result = paper_format_service.process_report(all_reports_dict)
 
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 自动生成并保存报告
        if result.get('success'):
            report_filename = f"{timestamp}_format_report.txt"
            report_path = os.path.join(app.config['FORMAT_CHECK_REPORTS_FOLDER'], report_filename)
            
            try:
                report_result = paper_format_service.generate_report(result, output_path=report_path)
                if report_result.get('success'):
                    # 将报告信息添加到返回结果中
                    result['data']['report_saved'] = True
                    result['data']['report_filename'] = report_filename
                    result['data']['report_download_url'] = f'/api/paper-format/download-report/{report_filename}'
                    result['data']['report_text'] = report_result['data']['report_text']

                    logger.info(f"检测报告已自动保存: {report_path}")
            except Exception as e:
                logger.warning(f"自动保存报告失败: {e}")
                # 不影响检测结果的返回

        if all_reports_dict['error'] is None:
            # 生成带批注的文档
            try:
                from services.document_annotator import generate_annotated_document
                annotate_filename = f"{timestamp}_annotated.docx"
                annotate_output_dir = app.config['FORMAT_CHECK_ANNOTATE_FOLDER']
                
                # 从result中获取all_reports
                all_reports = all_reports_dict['data']
                # logger.info(f"所有报告信息:{all_reports}")
                
                annotated_path = generate_annotated_document(
                    temp_file_path,
                    all_reports,
                    annotate_output_dir
                )
                
                if annotated_path:
                    result['data']['annotated_saved'] = True
                    result['data']['annotated_filename'] = os.path.basename(annotated_path)
                    result['data']['annotated_download_url'] = f'/api/paper-format/download-annotated/{os.path.basename(annotated_path)}'
                    logger.info(f"批注文档已自动生成: {annotated_path}")
                else:
                    logger.warning("批注文档生成失败")
            except Exception as e:
                logger.warning(f"生成批注文档失败: {e}")
                # 不影响检测结果的返回
        
        # 更新数据库记录
        if file_id and result.get('success'):
            try:
                format_check_file = FormatCheckFile.query.get(file_id)
                if format_check_file:
                    # 更新文件路径
                    if result['data'].get('report_saved'):
                        format_check_file.report_path = os.path.join(
                            app.config['FORMAT_CHECK_REPORTS_FOLDER'], 
                            result['data']['report_filename']
                        )
                    
                    if result['data'].get('annotated_saved'):
                        format_check_file.annotated_path = os.path.join(
                            app.config['FORMAT_CHECK_ANNOTATE_FOLDER'], 
                            result['data']['annotated_filename']
                        )
                    
                    # 更新检测结果摘要
                    if 'summary' in result['data']:
                        summary = result['data']['summary']
                        format_check_file.total_checks = summary.get('total_checks', 0)
                        format_check_file.passed_checks = summary.get('passed_checks', 0)
                        format_check_file.failed_checks = summary.get('failed_checks', 0)
                        format_check_file.pass_rate = summary.get('pass_rate', 0.0)
                    
                    format_check_file.check_status = 'completed'
                    db.session.commit()
                    logger.info(f"数据库记录已更新: ID={file_id}")
            except Exception as e:
                db.session.rollback()
                logger.warning(f"更新数据库记录失败: {e}")
        
        return jsonify(result)
            
    except Exception as e:
        logger.error(f"全量检测错误: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'检测失败: {str(e)}'
        }), 500


# 下载带批注的论文文档
@app.route('/api/paper-format/download-annotated/<filename>')
def download_annotated_document(filename):
    """下载带批注的论文文档"""
    try:
        annotated_path = os.path.join(app.config['FORMAT_CHECK_ANNOTATE_FOLDER'], filename)
        
        if not os.path.exists(annotated_path):
            return jsonify({
                'success': False,
                'message': '批注文件不存在'
            }), 404
        
        logger.info(f"下载批注文档: {annotated_path}")
        return send_file(
            annotated_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        logger.error(f"下载批注文档错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'下载失败: {str(e)}'
        }), 500


# 通过file_id打开原始文档
@app.route('/api/paper-format/open-original/<int:file_id>')
def open_original_document(file_id):
    """通过file_id打开原始文档"""
    try:
        format_check_file = FormatCheckFile.query.get(file_id)
        
        if not format_check_file:
            return jsonify({
                'success': False,
                'message': '文件记录不存在'
            }), 404
        
        if not os.path.exists(format_check_file.temp_file_path):
            return jsonify({
                'success': False,
                'message': '原始文件不存在'
            }), 404
        
        logger.info(f"打开原始文档: {format_check_file.temp_file_path}")
        return send_file(
            format_check_file.temp_file_path,
            as_attachment=True,
            download_name=f"{format_check_file.title}.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        logger.error(f"打开原始文档错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'打开失败: {str(e)}'
        }), 500


# 获取检测报告文本内容
@app.route('/api/paper-format/get-report-text/<int:file_id>')
def get_report_text(file_id):
    """获取检测报告的文本内容"""
    try:
        format_check_file = FormatCheckFile.query.get(file_id)
        
        if not format_check_file:
            return jsonify({
                'success': False,
                'message': '文件记录不存在'
            }), 404
        
        if not format_check_file.report_path or not os.path.exists(format_check_file.report_path):
            return jsonify({
                'success': False,
                'message': '检测报告不存在'
            }), 404
        
        # 读取报告文本内容
        try:
            with open(format_check_file.report_path, 'r', encoding='utf-8') as f:
                report_text = f.read()
            
            logger.info(f"读取检测报告文本: {format_check_file.report_path}")
            return jsonify({
                'success': True,
                'data': {
                    'report_text': report_text
                },
                'message': '读取成功'
            })
        except Exception as e:
            logger.error(f"读取报告文件错误: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'读取报告失败: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"获取报告文本错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取失败: {str(e)}'
        }), 500


# 通过file_id打开检测报告
@app.route('/api/paper-format/open-report/<int:file_id>')
def open_report_by_id(file_id):
    """通过file_id打开检测报告"""
    try:
        format_check_file = FormatCheckFile.query.get(file_id)
        
        if not format_check_file:
            return jsonify({
                'success': False,
                'message': '文件记录不存在'
            }), 404
        
        if not format_check_file.report_path or not os.path.exists(format_check_file.report_path):
            return jsonify({
                'success': False,
                'message': '检测报告不存在'
            }), 404
        
        logger.info(f"打开检测报告: {format_check_file.report_path}")
        return send_file(
            format_check_file.report_path,
            as_attachment=True,
            download_name=f"{format_check_file.title}_report.txt",
            mimetype='text/plain'
        )
    except Exception as e:
        logger.error(f"打开检测报告错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'打开失败: {str(e)}'
        }), 500


# 通过file_id打开批注文档
@app.route('/api/paper-format/open-annotated/<int:file_id>')
def open_annotated_by_id(file_id):
    """通过file_id打开批注文档"""
    try:
        format_check_file = FormatCheckFile.query.get(file_id)
        
        if not format_check_file:
            return jsonify({
                'success': False,
                'message': '文件记录不存在'
            }), 404
        
        if not format_check_file.annotated_path or not os.path.exists(format_check_file.annotated_path):
            return jsonify({
                'success': False,
                'message': '批注文档不存在'
            }), 404
        
        logger.info(f"打开批注文档: {format_check_file.annotated_path}")
        return send_file(
            format_check_file.annotated_path,
            as_attachment=True,
            download_name=f"{format_check_file.title}_annotated.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        logger.error(f"打开批注文档错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'打开失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
