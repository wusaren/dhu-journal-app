from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, auth_required, roles_required, hash_password, logout_user,verify_password, current_user
from flask_security.models import fsqla_v3 as fsqla
from flask_cors import CORS
from flask_session import Session
import redis
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import logging
import secrets
from sqlalchemy import text

# 导入配置和模型
from config.config import current_config
from models import User, Role, Journal, Paper, FileUpload, db, roles_users, user_datastore, FormatCheckFile

# 导入封装后的模块
from services.journal_service import JournalService
from services.paper_service import PaperService
from services.file_service import FileService
from services.export_service import ExportService
from services.paper_format_service import PaperFormatService
from services.template_service import TemplateService
from services.template_config_service import TemplateConfigService
from services.tuiwen_template_service import TuiwenTemplateService

# 导入管理蓝图
from blueprints.admin import admin_bp

app = Flask(__name__)

# 加载配置
app.config.from_object(current_config)
#Session 配置
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://localhost:6379')
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1小时

Session(app)
# Flask-Security 配置
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get("SECURITY_PASSWORD_SALT")
if not app.config['SECRET_KEY'] or not app.config['SECURITY_PASSWORD_SALT']:
    logging.warning("SECRET_KEY or SECURITY_PASSWORD_SALT not set in environment; sessions/tokens will be unstable. Set them before production.")    # ...existing code...
    @app.route('/api/login', methods=['POST'])
    def login():
        """使用 Flask-Security 的登录接口"""
        try:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return jsonify({'message': '用户名或密码缺失'}), 400
            
            user = user_datastore.find_user(username=username)
            if not user:
                return jsonify({'message': '用户不存在'}), 404
            
            from flask_security.utils import verify_password, login_user
            if not verify_password(password, user.password):
                return jsonify({'message': '用户名或密码错误'}), 401
            
            # 登录建立 session（可选）
            login_user(user)
            
            # 生成带过期时间的 token（前端可以使用 Bearer <token>）
            s = Serializer(app.config['SECRET_KEY'], expires_in=app.config.get('SECURITY_TOKEN_MAX_AGE', 3600))
            token = s.dumps({'user_id': user.id, 'fs': user.fs_uniquifier}).decode('utf-8')
            
            return jsonify({
                'message': '登录成功',
                'token': token,
                'expires_in': app.config.get('SECURITY_TOKEN_MAX_AGE', 3600),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'email': user.email
                }
            })
        except Exception as e:
            logger.error(f"登录错误: {str(e)}")
            return jsonify({'message': '服务器错误'}), 500
    # ...existing code...
app.config['SECURITY_REGISTERABLE'] = False
app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
app.config['SECURITY_USERNAME_ENABLE'] = True
app.config['SECURITY_USERNAME_REQUIRED'] = True
app.config['SECURITY_PASSWORD_HASH'] = 'bcrypt'
app.config['SECURITY_PASSWORD_SINGLE_HASH'] = False
app.config['SECURITY_TOKEN_AUTHENTICATION_HEADER'] = 'Authorization'
app.config['SECURITY_TOKEN_MAX_AGE'] = 3600  # 1小时

# 初始化扩展
db.init_app(app)
CORS(app, 
     supports_credentials=True, 
     origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

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
# 新增：用户配置目录（用于用户模板、用户配置文件等，和 uploads 分离）
USER_CONFIG_FOLDER = 'user_configs'

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FORMAT_CHECK_FOLDER'] = FORMAT_CHECK_FOLDER
app.config['FORMAT_CHECK_TEMP_FOLDER'] = FORMAT_CHECK_TEMP_FOLDER
app.config['FORMAT_CHECK_REPORTS_FOLDER'] = FORMAT_CHECK_REPORTS_FOLDER
app.config['FORMAT_CHECK_ANNOTATE_FOLDER'] = FORMAT_CHECK_ANNOTATE_FOLDER
app.config['USER_CONFIG_FOLDER'] = USER_CONFIG_FOLDER

# 创建必要的目录
for folder in [UPLOAD_FOLDER, FORMAT_CHECK_FOLDER, FORMAT_CHECK_TEMP_FOLDER, FORMAT_CHECK_REPORTS_FOLDER, FORMAT_CHECK_ANNOTATE_FOLDER, USER_CONFIG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"创建目录: {folder}")

# 设置 Flask-Security
security = Security(app, user_datastore)
app.register_blueprint(admin_bp)
from utils.config_loader import UserConfig

def create_default_users():
    """创建默认用户"""
    # 加载用户配置
    user_config = UserConfig()
    
    # 首先创建角色
    for role_config in user_config.get_roles():
        role_name = role_config['name']
        role = user_datastore.find_role(role_name)
        if not role:
            role = user_datastore.create_role(
                name=role_name,
                description=role_config.get('description', '')
            )
    
    db.session.commit()
    
    # 创建用户并分配角色
    for user_config_data in user_config.get_users():
        username = user_config_data['username']
        user = user_datastore.find_user(username=username)
        
        if not user:
            # 创建用户
            user = user_datastore.create_user(
                username=username,
                email=user_config_data['email'],
                password=hash_password(user_config_data['password']),
                fs_uniquifier=secrets.token_hex(16),
                active=user_config_data.get('active', True)
            )
            
            # 分配角色
            roles = user_config_data.get('roles', [])
            for role_name in roles:
                role = user_datastore.find_role(role_name)
                if role:
                    user_datastore.add_role_to_user(user, role)
            
            logger.info(f"用户 {username} 已创建")
    
    db.session.commit()
    logger.info("所有默认用户已创建完成")
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
# 新增：返回当前登录用户信息（基于 session）
@app.route('/api/me', methods=['GET'])
@auth_required()
def get_current_user():
    try:
        user = current_user
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': getattr(user, 'email', None),
                'role': getattr(user, 'role', None)
            }
        })
    except Exception as e:
        logger.error(f"获取当前用户失败: {e}")
        return jsonify({'message': '无法获取当前用户'}), 500
def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        create_default_users()
        # # 创建默认角色
        # admin_role = user_datastore.find_or_create_role(name='admin', description='管理员')
        # editor_role = user_datastore.find_or_create_role(name='editor', description='编辑')
        # viewer_role = user_datastore.find_or_create_role(name='managing editor', description='总编')
        
        # # 创建默认管理员用户
        # admin_user = user_datastore.find_user(username='admin')
        # if not admin_user:
        #     admin_user = user_datastore.create_user(
        #         username='admin',
        #         email='admin@example.com',
        #         password=hash_password('admin123'),
        #         fs_uniquifier=secrets.token_hex(16),
        #         active=True
        #     )
        #     user_datastore.add_role_to_user(admin_user, admin_role)
        #     db.session.commit()
        #     logger.info("默认管理员用户已创建")

# 根路由
@app.route('/')
def index():
    return jsonify({
        'status': 'ok', 
        'message': '期刊管理系统 API 服务运行正常',
        'version': '1.0.0',
        'endpoints': {
            'health': '/api/health',
            'login': '/api/login',
            'logout': '/api/logout',
            'journals': '/api/journals',
            'papers': '/api/papers',
            'upload': '/api/upload'
        }
    })

# 健康检查
@app.route('/api/health')
def health_check():
    return jsonify({'status': 'ok', 'message': '期刊管理系统运行正常'})



# 用户认证 - 使用 Flask-Security
@app.route('/api/login', methods=['POST'])
def login():
    """使用 Flask-Security 的登录接口"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'message': '用户名和密码不能为空'}), 400
        
        # 使用 Flask-Security 验证用户
        user = user_datastore.find_user(username=username)
        if not user:
            return jsonify({'message': '用户不存在'}), 404
        
        # 使用 Flask-Security 的密码验证
        from flask_security.utils import verify_password
        if not verify_password(password, user.password):
            return jsonify({'message': '用户名或密码错误'}), 401
        
        # 生成访问令牌
        from flask_security import login_user
        login_user(user)
        
        return jsonify({
            'message': '登录成功',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'email': user.email
            }
        })
    
    except Exception as e:
        logger.error(f"登录错误: {str(e)}")
        return jsonify({'message': f'登录失败: {str(e)}'}), 500
    
# 用户登出
@app.route('/api/logout', methods=['POST'])
@auth_required()
def logout():
    """用户登出"""
    try:
        logout_user()
        return jsonify({'message': '登出成功'})
    except Exception as e:
        logger.error(f"登出错误: {str(e)}")
        return jsonify({'message': f'登出失败: {str(e)}'}), 500

# 修改密码
@app.route('/api/change-password', methods=['POST'])
@auth_required()
def change_password():
    """修改用户密码"""
    try:
        data = request.get_json()
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')
        
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': '当前密码和新密码不能为空'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '新密码长度不能少于6位'}), 400
        
        # 验证当前密码
        from flask_security.utils import verify_password
        if not verify_password(current_password, current_user.password):
            return jsonify({'success': False, 'message': '当前密码错误'}), 401
        
        # 更新数据库中的密码
        current_user.password = hash_password(new_password)
        db.session.commit()
        
        # 更新JSON配置文件中的密码
        try:
            import json
            user_config_path = 'config/users.json'
            with open(user_config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            
            # 找到当前用户并更新密码
            for user in user_config['users']:
                if user['username'] == current_user.username:
                    user['password'] = new_password
                    break
            
            # 写回配置文件
            with open(user_config_path, 'w', encoding='utf-8') as f:
                json.dump(user_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"用户 {current_user.username} 的密码已更新")
            
        except Exception as e:
            logger.warning(f"更新用户配置文件失败: {e}")
            # 数据库更新成功，配置文件更新失败不影响主要功能
        
        return jsonify({
            'success': True,
            'message': '密码修改成功'
        })
    
    except Exception as e:
        logger.error(f"修改密码错误: {str(e)}")
        return jsonify({'success': False, 'message': f'密码修改失败: {str(e)}'}), 500

# 获取期刊列表
@app.route('/api/journals', methods=['GET'])
@auth_required()
def get_journals():
    try:
        journal_service = JournalService()
        result = journal_service.get_all_journals(current_user)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"获取期刊列表错误: {str(e)}")
        return jsonify({'message': f'获取期刊列表失败: {str(e)}'}), 500

# 创建期刊 
@app.route('/api/journals/create', methods=['POST'])
@auth_required()
def create_journal():
    try:
        data = request.get_json()
        journal_service = JournalService()
        result = journal_service.create_journal(data, current_user)
        
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

# 文件上传 - 临时移除权限检查进行调试
@app.route('/api/upload', methods=['POST'])
@auth_required()
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'message': '没有选择文件'}), 400
        
        file = request.files['file']
        journal_id = request.form.get('journalId', '1')
        
        if file.filename == '':
            return jsonify({'message': '没有选择文件'}), 400
        
        # 手动获取管理员用户（临时解决方案）
        # from models import User
        # admin_user = User.query.filter_by(username='admin').first()
        
        file_service = FileService()
        result = file_service.upload_file(file, journal_id, current_user)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"文件上传错误: {str(e)}")
        return jsonify({'message': f'文件上传失败: {str(e)}'}), 500

# 覆盖上传文件
@app.route('/api/upload/overwrite', methods=['POST'])
@auth_required()
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
        result = file_service.upload_file_with_overwrite(file, journal_id, overwrite_paper_id, current_user)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"覆盖上传错误: {str(e)}")
        return jsonify({'message': f'覆盖上传失败: {str(e)}'}), 500

# 生成目录 - 基于数据权限控制，无需额外权限检查
@app.route('/api/export/toc', methods=['POST'])
@auth_required()
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

# 生成推文 - 基于数据权限控制，支持用户模板配置
@app.route('/api/export/tuiwen', methods=['POST'])
@auth_required()
def export_tuiwen():
    """生成推文Word文档 - 优先使用用户模板，否则使用默认格式"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        
        if not journal_id:
            return jsonify({'message': '缺少期刊ID'}), 400
        
        export_service = ExportService()
        
        # 优先检查用户级别的推文模板配置
        # user_id = current_user.id
        # tuiwen_template_service = TuiwenTemplateService()
        # user_tuiwen_template_config = tuiwen_template_service.load_user_config(user_id)
        
        if user_tuiwen_template_config and user_tuiwen_template_config.get('fields'):
            # 使用用户模板生成
            logger.info(f"使用用户推文模板生成: {len(user_tuiwen_template_config.get('fields', []))} 个字段")
            result = export_service.export_tuiwen(journal_id, user_id)
        else:
            # 没有用户模板配置，使用默认格式生成
            logger.info("用户没有推文模板配置，使用默认格式生成推文")
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

# 上传统计表模板文件
@app.route('/api/upload/stats-format', methods=['POST'])
@auth_required()
def upload_template():
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

        # 保存临时文件到用户配置目录（以 user_id 为单位）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        try:
            uid = getattr(current_user, 'id', None)
        except Exception:
            uid = None
        uid_str = str(uid) if uid else 'anon'
        safe_name = secure_filename(file.filename)
        user_dir = os.path.join(app.config['USER_CONFIG_FOLDER'], f'user_{uid_str}')
        os.makedirs(user_dir, exist_ok=True)
        temp_filename = f"template_user_{uid_str}_{timestamp}_{safe_name}"
        temp_path = os.path.join(user_dir, temp_filename)
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

# 上传推文模板文件（亦改为用户配置目录）
@app.route('/api/upload/tuiwen-format', methods=['POST'])
def upload_tuiwen_template():
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

        # 保存到用户配置目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        try:
            uid = getattr(current_user, 'id', None)
        except Exception:
            uid = None
        uid_str = str(uid) if uid else 'anon'
        safe_name = secure_filename(file.filename)
        user_dir = os.path.join(app.config['USER_CONFIG_FOLDER'], f'user_{uid_str}')
        os.makedirs(user_dir, exist_ok=True)
        temp_filename = f"tuiwen_user_{uid_str}_{timestamp}_{safe_name}"
        temp_path = os.path.join(user_dir, temp_filename)
        file.save(temp_path)

        return jsonify({
            'success': True,
            'message': '推文模板上传成功',
            'template_file_path': temp_path
        })

    except Exception as e:
        logger.error(f"上传推文模板错误: {str(e)}")
        return jsonify({'success': False, 'message': f'上传模板失败: {str(e)}'}), 500

# 保存用户模板配置
@app.route('/api/user/template', methods=['PUT'])
@auth_required()
def save_user_template():
    """保存用户模板配置"""
    try:
        data = request.get_json()
        print(data)
        template_file_path = data.get('template_file_path')
        column_mapping = data.get('column_mapping', [])
        
        if not template_file_path:
            return jsonify({'success': False, 'message': '缺少模板文件路径'}), 400
        
        if not column_mapping:
            return jsonify({'success': False, 'message': '列映射配置不能为空'}), 400
        
        user_id = current_user.id
        config_service = TemplateConfigService()
        result = config_service.save_user_template(user_id, template_file_path, column_mapping)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    
    except Exception as e:
        logger.error(f"保存用户模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'保存用户模板配置失败: {str(e)}'}), 500

# 获取用户模板配置
@app.route('/api/user/template', methods=['GET'])
@auth_required()
def get_user_template():
    """获取用户模板配置"""
    try:
        user_id = current_user.id
        config_service = TemplateConfigService()
        config = config_service.load_user_config(user_id)
        
        if not config:
            return jsonify({
                'success': True,
                'has_template': False,
                'message': '用户没有模板配置'
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
        logger.error(f"获取用户模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取用户模板配置失败: {str(e)}'}), 500

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


# 保存用户推文模板配置
@app.route('/api/user/tuiwen-template', methods=['POST'])
@auth_required()
def save_user_tuiwen_template():
    """保存用户推文模板字段配置"""
    try:
        data = request.get_json()
        fields = data.get('fields', [])
        
        if not fields:
            return jsonify({'success': False, 'message': '字段配置不能为空'}), 400
        
        user_id = current_user.id
        config_service = TuiwenTemplateService()
        result = config_service.save_user_template_config(user_id, fields)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    
    except Exception as e:
        logger.error(f"保存用户推文模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'保存用户推文模板配置失败: {str(e)}'}), 500

# 获取用户推文模板配置
@app.route('/api/user/tuiwen-template', methods=['GET'])
@auth_required()
def get_user_tuiwen_template():
    """获取用户推文模板配置"""
    try:
        user_id = current_user.id
        config_service = TuiwenTemplateService()
        config = config_service.load_user_config(user_id)
        
        if not config:
            return jsonify({
                'success': True,
                'has_template': False,
                'message': '用户没有推文模板配置'
            })
        
        return jsonify({
            'success': True,
            'has_template': True,
            'fields': config.get('fields', []),
            'created_at': config.get('created_at'),
            'updated_at': config.get('updated_at')
        })
    
    except Exception as e:
        logger.error(f"获取用户推文模板配置错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取用户推文模板配置失败: {str(e)}'}), 500

# 生成统计表
@app.route('/api/export/excel', methods=['POST'])
@auth_required()
def export_excel():
    """生成统计表Excel - 优先使用用户模板，否则使用默认配置（从JSON文件加载）"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        columns_config = data.get('columns', None)  # 接收列配置
        
        if not journal_id:
            return jsonify({'message': '缺少期刊ID'}), 400
        
        export_service = ExportService()
        
        # 检查用户级别的模板配置
        user_id = current_user.id
        template_config_service = TemplateConfigService()
        user_template_config = template_config_service.load_user_config(user_id)
        
        if user_template_config and user_template_config.get('template_file_path') and user_template_config.get('column_mapping'):
            # 使用用户模板生成
            logger.info(f"使用用户模板生成统计表: {user_template_config.get('template_file_path')}")
            result = export_service.export_excel_with_template(journal_id, user_template_config['template_file_path'], user_template_config['column_mapping'])
        else:
            # 没有用户模板配置，使用默认配置（从JSON文件加载）
            logger.info("用户没有模板配置，使用默认配置生成统计表")
            result = export_service.export_excel(journal_id, columns_config=None)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"统计表生成错误: {str(e)}")
        return jsonify({'message': f'统计表生成失败: {str(e)}'}), 500

# 获取论文列表 - 需要认证
@app.route('/api/papers', methods=['GET'])
@auth_required()
def get_papers():
    """获取论文列表"""
    try:
        journal_id = request.args.get('journalId', type=int)
        paper_service = PaperService()
        result = paper_service.get_papers(journal_id, current_user)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"获取论文列表错误: {str(e)}")
        return jsonify({'message': f'获取论文列表失败: {str(e)}'}), 500

# 创建论文 - 需要编辑或管理员权限
@app.route('/api/papers/create', methods=['POST'])
@auth_required()
@roles_required('admin', 'editor')
def create_paper():
    """创建论文"""
    try:
        data = request.get_json()
        paper_service = PaperService()
        # 手动获取管理员用户（临时解决方案）
        # from models import User
        # admin_user = User.query.filter_by(username='admin').first()
        result = paper_service.create_paper(data, current_user)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"创建论文错误: {str(e)}")
        return jsonify({'message': f'创建论文失败: {str(e)}'}), 500

# 更新论文 - 需要编辑或管理员权限
@app.route('/api/papers/<int:paper_id>', methods=['PUT'])
@auth_required()
@roles_required('admin', 'editor')
def update_paper(paper_id):
    """更新论文"""
    try:
        data = request.get_json()
        paper_service = PaperService()
        result = paper_service.update_paper(paper_id, data, current_user)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"更新论文错误: {str(e)}")
        return jsonify({'message': f'更新论文失败: {str(e)}'}), 500

# 删除论文 - 需要管理员权限
@app.route('/api/papers/<int:paper_id>', methods=['DELETE'])
@auth_required()
# @roles_required('admin','editor')
def delete_paper(paper_id):
    """删除论文"""
    try:
        paper_service = PaperService()
        result = paper_service.delete_paper(paper_id, current_user)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        logger.error(f"删除论文错误: {str(e)}")
        return jsonify({'message': f'删除论文失败: {str(e)}'}), 500

# 删除期刊 - 需要管理员权限
@app.route('/api/journals/<int:journal_id>', methods=['DELETE'])
@auth_required()
# @roles_required('admin','editor')
def delete_journal(journal_id):
    """删除期刊（如果期刊下存在论文则不允许删除）"""
    try:
        journal_service = JournalService()
        result = journal_service.delete_journal(journal_id, current_user)
        
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

# 文件下载 - 需要认证
@app.route('/api/download/<filename>')
@auth_required()
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

# 文件预览 - 需要认证
@app.route('/api/preview/<filename>')
@auth_required()
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


# 新增：为期刊分配编辑
@app.route('/api/journals/<int:journal_id>/assign', methods=['POST'])
@auth_required()
# @roles_required('managing_editor')
def assign_journal(journal_id):
    try:
        if not current_user.has_role('managing_editor'):
            return jsonify({'message': '权限不足，只有总编才能分配期刊'}), 403
        data = request.get_json() or {}
        assignee_id = data.get('assignee_id')
        if not assignee_id:
            return jsonify({'message': '缺少 assignee_id'}), 400

        journal = Journal.query.get(journal_id)
        if not journal:
            return jsonify({'message': '期刊不存在'}), 404

        assignee = User.query.get(assignee_id)
        if not assignee:
            return jsonify({'message': '被分配用户不存在'}), 404

        # 确认被分配用户拥有 editor 角色
        role_names = [r.name for r in getattr(assignee, 'roles', [])]
        if 'editor' not in role_names:
            return jsonify({'message': '被分配用户不是 editor 角色'}), 400

        # 将期刊的 created_by 字段更新为被分配用户 id
        try:
            journal.created_by = assignee_id
            db.session.add(journal)
            db.session.commit()
            logger.info(f"期刊 {journal_id} 已分配给用户 {assignee_id} by {current_user.id}")
            return jsonify({'message': '分配成功'})
        except Exception as e:
            db.session.rollback()
            logger.exception("更新 journal.created_by 失败")
            return jsonify({'message': f'分配失败: {str(e)}'}), 500

    except Exception as e:
        logger.exception("分配任务错误")
        return jsonify({'message': f'分配失败: {str(e)}'}), 500
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
