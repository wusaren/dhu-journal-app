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
from models import User, Role, Journal, Paper, FileUpload, db, roles_users, user_datastore

# 导入封装后的模块
from services.journal_service import JournalService
from services.paper_service import PaperService
from services.file_service import FileService
from services.export_service import ExportService

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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

# 生成推文 - 基于数据权限控制，无需额外权限检查
@app.route('/api/export/tuiwen', methods=['POST'])
@auth_required()
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

# 生成统计表 - 基于数据权限控制，无需额外权限检查
@app.route('/api/export/excel', methods=['POST'])
@auth_required()
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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
