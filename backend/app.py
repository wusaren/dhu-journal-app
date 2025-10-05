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
    return filename.split('.')[-1].lower() if '.' in filename else 'unknown'

def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员用户
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
            admin_user = User(
                username='admin',
                password_hash=password_hash.decode('utf-8'),
                email='admin@example.com',
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            logger.info("默认管理员用户已创建")

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
        
        if not username or not password:
            return jsonify({'message': '用户名和密码不能为空'}), 400
        
        user = User.query.filter_by(username=username).first()
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return jsonify({'message': '用户名或密码错误'}), 401
        
        access_token = create_access_token(identity=user.id)
        return jsonify({
            'message': '登录成功',
            'access_token': access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role
            }
        })
    
    except Exception as e:
        logger.error(f"登录错误: {str(e)}")
        return jsonify({'message': f'登录失败: {str(e)}'}), 500

# 获取期刊列表
@app.route('/api/journals', methods=['GET'])
def get_journals():
    try:
        journals = Journal.query.all()
        journal_list = []
        
        for journal in journals:
            papers = Paper.query.filter_by(journal_id=journal.id).all()
            journal_list.append({
                'id': journal.id,
                'title': journal.title,
                'issue': journal.issue,
                'publishDate': journal.publish_date.isoformat() if journal.publish_date else None,
                'status': journal.status,
                'description': journal.description,
                'paperCount': len(papers),
                'createdAt': journal.created_at.isoformat() if journal.created_at else None
            })
        
        return jsonify(journal_list)
    
    except Exception as e:
        logger.error(f"获取期刊列表错误: {str(e)}")
        return jsonify({'message': f'获取期刊列表失败: {str(e)}'}), 500

# 文件上传
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        logger.info("收到文件上传请求")
        
        if 'file' not in request.files:
            logger.error("没有找到文件")
            return jsonify({'message': '没有选择文件'}), 400
        
        file = request.files['file']
        journal_id = request.form.get('journalId', '1')
        
        logger.info(f"文件名: {file.filename}, 期刊ID: {journal_id}")
        
        if file.filename == '':
            return jsonify({'message': '没有选择文件'}), 400
        
        # 保存文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stored_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
        
        # 确保目录存在
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        file.save(file_path)
        logger.info(f"文件已保存到: {file_path}")
        
        # 保存到数据库
        try:
            # 检查是否已存在相同文件名的期刊（去重）
            existing_journal = Journal.query.filter_by(description=f'上传文件: {filename}').first()
            if existing_journal:
                logger.info(f"文件 {filename} 已存在，使用现有期刊: {existing_journal.id}")
                journal = existing_journal
            else:
                # 获取第一个用户ID，如果没有则创建默认用户
                first_user = User.query.first()
                if not first_user:
                    password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
                    first_user = User(
                        username='admin',
                        password_hash=password_hash.decode('utf-8'),
                        email='admin@example.com',
                        role='admin'
                    )
                    db.session.add(first_user)
                    db.session.flush()
                
                # 创建新期刊记录
                journal = Journal(
                    title='东华学报',
                    issue=f'第{Journal.query.count() + 1}期',
                    publish_date=datetime.now().date(),
                    status='draft',
                    description=f'上传文件: {filename}',
                    created_by=first_user.id
                )
                db.session.add(journal)
                db.session.flush()  # 获取期刊ID
            
            # 创建文件上传记录
            file_upload = FileUpload(
                journal_id=journal.id,
                original_filename=filename,
                stored_filename=stored_filename,
                file_type=get_file_type(filename),
                file_size=os.path.getsize(file_path),
                upload_path=file_path,
                upload_status='completed'
            )
            db.session.add(file_upload)
            
            # 如果是PDF文件，解析并提取真实的论文信息
            if get_file_type(filename) == 'pdf':
                logger.info(f"开始解析PDF文件: {file_path}")
                try:
                    from services.pdf_parser import parse_pdf_to_papers
                    
                    # 检查是否已有论文数据（去重）
                    existing_papers = Paper.query.filter_by(journal_id=journal.id).count()
                    if existing_papers > 0:
                        logger.info(f"期刊 {journal.id} 已有 {existing_papers} 篇论文，跳过重复解析")
                    else:
                        papers_data = parse_pdf_to_papers(file_path, journal.id)
                        
                        # 保存解析出的真实论文
                        for paper_data in papers_data:
                            paper = Paper(
                                journal_id=journal.id,
                                title=paper_data.get('title', ''),
                                authors=paper_data.get('authors', ''),
                                abstract=paper_data.get('abstract', ''),
                                keywords=paper_data.get('keywords', ''),
                                doi=paper_data.get('doi', ''),
                                page_start=paper_data.get('page_start'),
                                page_end=paper_data.get('page_end'),
                                file_path=file_path,
                                # 统计表字段
                                manuscript_id=paper_data.get('manuscript_id', ''),
                                pdf_pages=paper_data.get('pdf_pages', 0),
                                first_author=paper_data.get('first_author', ''),
                                corresponding=paper_data.get('corresponding', ''),
                                issue=paper_data.get('issue', journal.issue),
                                is_dhu=paper_data.get('is_dhu', False)
                            )
                            db.session.add(paper)
                        
                        logger.info(f"成功解析出 {len(papers_data)} 篇真实论文")
                    
                except Exception as parse_error:
                    logger.error(f"PDF解析失败: {str(parse_error)}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")
                    # 即使解析失败，也继续保存文件记录
            else:
                logger.info("非PDF文件，跳过论文解析")
            
            db.session.commit()
            logger.info(f"期刊和文件记录已保存到数据库: 期刊ID={journal.id}, 文件ID={file_upload.id}")
            
        except Exception as db_error:
            logger.error(f"数据库保存失败: {str(db_error)}")
            db.session.rollback()
            # 即使数据库保存失败，文件上传也算成功
        
        return jsonify({
            'message': '文件上传成功',
            'fileId': timestamp,  # 使用时间戳作为ID
            'filename': filename,
            'filePath': file_path,
            'fileSize': os.path.getsize(file_path),
            'journalId': journal.id if 'journal' in locals() else None
        })
    
    except Exception as e:
        logger.error(f"文件上传错误: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({'message': f'服务器内部错误: {str(e)}'}), 500

# 生成目录
@app.route('/api/export/toc', methods=['POST'])
def export_toc():
    """生成目录Word文档"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        
        if not journal_id:
            return jsonify({'message': '缺少期刊ID'}), 400
        
        # 获取期刊信息
        journal = Journal.query.get(journal_id)
        if not journal:
            return jsonify({'message': '期刊不存在'}), 404
        
        # 获取论文信息
        papers = Paper.query.filter_by(journal_id=journal_id).all()
        
        # 如果没有论文数据，返回错误
        if not papers:
            return jsonify({'message': '该期刊没有论文数据，无法生成目录'}), 400
        
        # 生成目录文档
        from services.document_generator import generate_toc_docx
        output_path = generate_toc_docx(papers, journal)
        
        return jsonify({
            'message': '目录生成成功',
            'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
            'filePath': output_path
        })
    
    except Exception as e:
        logger.error(f"目录生成错误: {str(e)}")
        return jsonify({'message': f'目录生成失败: {str(e)}'}), 500

# 生成统计表
@app.route('/api/export/excel', methods=['POST'])
def export_excel():
    """生成统计表Excel"""
    try:
        data = request.get_json()
        journal_id = data.get('journalId')
        
        if not journal_id:
            return jsonify({'message': '缺少期刊ID'}), 400
        
        # 获取期刊信息
        journal = Journal.query.get(journal_id)
        if not journal:
            return jsonify({'message': '期刊不存在'}), 404
        
        # 获取论文信息
        papers = Paper.query.filter_by(journal_id=journal_id).all()
        
        logger.info(f"期刊 {journal_id} 找到 {len(papers)} 篇论文")
        
        # 如果没有论文数据，返回错误
        if not papers:
            return jsonify({'message': '该期刊没有论文数据，请先上传并解析PDF文件'}), 400
        
        # 直接使用数据库中的字段
        articles = []
        for paper in papers:
            article = {
                'manuscript_id': paper.manuscript_id or '',
                'pdf_pages': paper.pdf_pages or 0,
                'first_author': paper.first_author or '',
                'corresponding': paper.corresponding or '',
                'issue': paper.issue or journal.issue,
                'is_dhu': paper.is_dhu or False
            }
            articles.append(article)
            
            # 调试信息
            logger.info(f"论文数据: manuscript_id={article['manuscript_id']}, pdf_pages={article['pdf_pages']}, first_author={article['first_author']}, corresponding={article['corresponding']}, issue={article['issue']}, is_dhu={article['is_dhu']}")
        
        # 生成统计表Excel
        from services.document_generator import generate_excel_stats
        output_path = generate_excel_stats(articles, journal)
        
        return jsonify({
            'message': '统计表生成成功',
            'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
            'filePath': output_path
        })
    
    except Exception as e:
        logger.error(f"统计表生成错误: {str(e)}")
        return jsonify({'message': f'统计表生成失败: {str(e)}'}), 500

# 文件下载
@app.route('/api/download/<filename>')
def download_file(filename):
    """文件下载接口"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        logger.info(f"尝试下载文件: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return jsonify({'message': '文件不存在'}), 404
        
        return send_file(file_path, as_attachment=True)
    
    except Exception as e:
        logger.error(f"文件下载错误: {str(e)}")
        return jsonify({'message': f'文件下载失败: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
