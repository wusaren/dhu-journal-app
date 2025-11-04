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
from services.paper_format_service import PaperFormatService

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
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FORMAT_CHECK_FOLDER'] = FORMAT_CHECK_FOLDER
app.config['FORMAT_CHECK_TEMP_FOLDER'] = FORMAT_CHECK_TEMP_FOLDER
app.config['FORMAT_CHECK_REPORTS_FOLDER'] = FORMAT_CHECK_REPORTS_FOLDER

# 创建必要的目录
for folder in [UPLOAD_FOLDER, FORMAT_CHECK_FOLDER, FORMAT_CHECK_TEMP_FOLDER, FORMAT_CHECK_REPORTS_FOLDER]:
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

# 生成统计表
@app.route('/api/export/excel', methods=['POST'])
def export_excel():
    """生成统计表Excel - 支持自定义列配置"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        columns_config = data.get('columns', None)  # 接收列配置
        
        if not journal_id:
            return jsonify({'message': '缺少期刊ID'}), 400
        
        export_service = ExportService()
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

# 获取可用的检测模块
@app.route('/api/paper-format/modules', methods=['GET'])
def get_format_modules():
    """获取所有可用的论文格式检测模块"""
    try:
        paper_format_service = PaperFormatService()
        modules = paper_format_service.get_available_modules()
        
        # 获取每个模块的详细信息
        modules_info = []
        for module_name in modules:
            info = paper_format_service.get_module_info(module_name)
            modules_info.append(info)
        
        return jsonify({
            'success': True,
            'data': {
                'modules': modules_info,
                'total': len(modules_info)
            }
        })
    
    except Exception as e:
        logger.error(f"获取检测模块列表错误: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'获取检测模块列表失败: {str(e)}'
        }), 500


# 检测单个模块
@app.route('/api/paper-format/check/<module_name>', methods=['POST'])
def check_format_module(module_name):
    """检测论文格式（单个模块）"""
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
        
        # 保存临时文件到temp目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"{timestamp}_{secure_filename(file.filename)}"
        temp_path = os.path.join(app.config['FORMAT_CHECK_TEMP_FOLDER'], temp_filename)
        logger.info(f"保存临时文件: {temp_path}")
        file.save(temp_path)
        
    
        # 执行检测
        paper_format_service = PaperFormatService()
        
        # 根据模块名称调用相应的检测方法
        if module_name.lower() == 'title':
            result = paper_format_service.check_title(temp_path)
        elif module_name.lower() == 'abstract':
            result = paper_format_service.check_abstract(temp_path)
        elif module_name.lower() == 'keywords':
            result = paper_format_service.check_keywords(temp_path)
        elif module_name.lower() == 'content':
            result = paper_format_service.check_content(temp_path)
        elif module_name.lower() == 'figure':
            enable_api = request.form.get('enableApi', 'false').lower() == 'true'
            result = paper_format_service.check_figure(temp_path, enable_content_check=enable_api)
        elif module_name.lower() == 'formula':
            result = paper_format_service.check_formula(temp_path)
        elif module_name.lower() == 'table':
            result = paper_format_service.check_table(temp_path)
        else:
            return jsonify({
                'success': False, 
                'message': f'未知的检测模块: {module_name}'
            }), 400
        
        return jsonify(result)
  
    
    except Exception as e:
        logger.error(f"单模块检测错误: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'检测失败: {str(e)}'
        }), 500


# 全量检测
@app.route('/api/paper-format/check-all', methods=['POST'])
def check_format_all():
    """执行论文格式全量检测"""
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
        
        # 保存临时文件到temp目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"{timestamp}_{secure_filename(file.filename)}"
        temp_path = os.path.join(app.config['FORMAT_CHECK_TEMP_FOLDER'], temp_filename)
        logger.info(f"保存临时文件: {temp_path}")
        file.save(temp_path)
        
       
        # 获取参数
        enable_figure_api = request.form.get('enableFigureApi', 'false').lower() == 'true'
        modules = request.form.get('modules')  # 可选，逗号分隔的模块名称
        
        if modules:
            modules_list = [m.strip() for m in modules.split(',')]
        else:
            modules_list = None
        
        # 执行检测
        paper_format_service = PaperFormatService()
        result = paper_format_service.check_all(
            temp_path,
            enable_figure_api=enable_figure_api,
            modules=modules_list
        )
        
        return jsonify(result)
        
    
    except Exception as e:
        logger.error(f"全量检测错误: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'检测失败: {str(e)}'
        }), 500


# 生成检测报告
@app.route('/api/paper-format/generate-report', methods=['POST'])
def generate_format_report():
    """生成论文格式检测报告"""
    try:
        data = request.get_json()
        check_results = data.get('checkResults')
        
        if not check_results:
            return jsonify({
                'success': False, 
                'message': '缺少检测结果数据'
            }), 400
        
        # 生成报告文件名，保存到reports目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{timestamp}_format_report.txt"
        report_path = os.path.join(app.config['FORMAT_CHECK_REPORTS_FOLDER'], report_filename)
        logger.info(f"生成报告文件: {report_path}")
        
        # 生成报告
        paper_format_service = PaperFormatService()
        result = paper_format_service.generate_report(check_results, output_path=report_path)
        
        if result['success']:
            # 返回报告文本和下载链接
            return jsonify({
                'success': True,
                'data': {
                    'report_text': result['data']['report_text'],
                    'download_url': f'/api/paper-format/download-report/{report_filename}'
                },
                'message': '报告生成成功'
            })
        else:
            return jsonify(result), result.get('status_code', 500)
    
    except Exception as e:
        logger.error(f"生成报告错误: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'生成报告失败: {str(e)}'
        }), 500


# 下载格式检测报告
@app.route('/api/paper-format/download-report/<filename>')
def download_format_report(filename):
    """下载论文格式检测报告"""
    try:
        report_path = os.path.join(app.config['FORMAT_CHECK_REPORTS_FOLDER'], filename)
        
        if not os.path.exists(report_path):
            return jsonify({
                'success': False,
                'message': '报告文件不存在'
            }), 404
        
        logger.info(f"下载报告: {report_path}")
        return send_file(
            report_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        logger.error(f"下载报告错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'下载失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
