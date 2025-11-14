"""
文件服务
从 app.py 中提取文件相关业务逻辑，保持完全兼容
"""
from models import Journal, Paper, FileUpload, User, db
from services.permission_service import PermissionService
from utils.helpers import get_file_type, generate_timestamp, ensure_upload_directory, format_file_response
from utils.validators import validate_file_upload
from datetime import datetime
import os
import logging
import bcrypt

logger = logging.getLogger(__name__)

class FileService:
    """文件服务类"""
    
    def upload_file(self, file, journal_id=None, user=None):
        """
        文件上传 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
        """
        try:
            logger.info("收到文件上传请求")
            temp_output_dir = "backen/temp_images"
            # 验证文件
            is_valid, error_msg = validate_file_upload(file)
            if not is_valid:
                return {'success': False, 'message': error_msg, 'status_code': 400}

            filename = file.filename
            logger.info(f"文件名: {filename}, 期刊ID: {journal_id}")

            # 保存文件
            from werkzeug.utils import secure_filename
            # secure_filename_str = secure_filename(filename)
            timestamp = generate_timestamp()
            stored_filename = f"{timestamp}_{filename}"
            
            # 确保上传目录存在
            upload_folder = ensure_upload_directory('uploads')
            file_path = os.path.join(upload_folder, stored_filename)
            
            file.save(file_path)
            logger.info(f"文件已保存到: {file_path}")
            
            # 保存到数据库
            try:
                # 获取或创建期刊
                journal = None
                if journal_id and journal_id != '1':
                    # 使用指定的期刊ID
                    journal = Journal.query.get(int(journal_id))
                    if not journal:
                        return {'success': False, 'message': '指定的期刊不存在', 'status_code': 404}
                    
                    # 检查用户是否有权限访问该期刊
                    # if user and not PermissionService.can_edit_journal(user, journal):
                    #     return {'success': False, 'message': '您没有权限上传文件到该期刊', 'status_code': 403}
                else:
                    # 先解析PDF获取期刊信息，然后查找或创建期刊
                    journal = None
                    papers_data = None
                    journal_created = False
                    
                    if get_file_type(filename) == 'pdf':
                        try:
                            from services.pdf_parser import parse_pdf_to_papers
                            logger.info(f"开始预解析PDF文件获取期刊信息: {file_path}")
                            
                            # 预解析PDF获取期刊信息
                            papers_data = parse_pdf_to_papers(file_path, 0,temp_output_dir)
                            logger.info(f"预解析结果: {len(papers_data) if papers_data else 0} 篇论文")
                            
                            if papers_data and papers_data[0].get('issue'):
                                real_issue = papers_data[0]['issue']
                                is_dhu = papers_data[0].get('is_dhu', False)
                                real_title = '东华学报' if is_dhu else '其他期刊'
                                
                                # 基于真实期刊信息查找现有期刊
                                journal = Journal.query.filter_by(title=real_title, issue=real_issue).first()
                                
                                if journal and journal.created_by == user.id:
                                    logger.info(f"找到用户{user.username}创建的现有期刊: {journal.title} - {journal.issue}")
                                elif journal and journal.created_by != user.id:
                                    return{'success': False, 'message': '您无权限上传期刊{journal.title}-{journal.issue}相关论文', 'status_code': 409}
                                else:
                                        # 创建新期刊
                                        journal_created = True
                                        # 使用当前登录用户创建期刊
                                        
                                        # journal_creator = user 
                                        journal_creator_id= user.id if user else 0
                                        journal_creator_name= user.username if user.username else '匿名用户'
                                        # 如果没有登录用户，使用第一个用户
                                        # journal_creator = User.query.first()
                                        # if not journal_creator:
                                        #     password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
                                        #     journal_creator = User(
                                        #         username='admin',
                                        #         password_hash=password_hash.decode('utf-8'),
                                        #         email='admin@example.com',
                                        #         role='admin'
                                        #     )
                                        #     db.session.add(journal_creator)
                                        #     db.session.flush()
                                    
                                        journal = Journal(
                                            title=real_title,
                                            issue=real_issue,
                                            publish_date=datetime.now().date(),
                                            status='draft',
                                            description=f'基于PDF解析自动创建的期刊 - 上传文件: {filename}',
                                            paper_count=0,
                                            created_by=journal_creator_id
                                        )
                                        db.session.add(journal)
                                        db.session.flush()
                                        logger.info(f"用户：{journal_creator_name} 创建新期刊: {journal.title} - {journal.issue}")
                                    
                        except Exception as parse_error:
                            logger.warning(f"PDF预解析失败，使用默认期刊: {str(parse_error)}")
                            journal = None
                            papers_data = None
                    
                    # 如果PDF解析失败或不是PDF文件，使用默认期刊逻辑
                    if not journal:
                        default_journal = Journal.query.filter_by(title='东华学报', status='draft').first()
                        if default_journal:
                            journal = default_journal
                            logger.info(f"使用现有默认期刊: {journal.id}")
                        else:
                            # 创建新期刊记录
                            journal_created = True
                            # 使用当前登录用户创建期刊
                            if user:
                                journal_creator = user
                            else:
                                # 如果没有登录用户，使用第一个用户
                                journal_creator = User.query.first()
                                if not journal_creator:
                                    password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
                                    journal_creator = User(
                                        username='admin',
                                        password_hash=password_hash.decode('utf-8'),
                                        email='admin@example.com',
                                        role='admin'
                                    )
                                    db.session.add(journal_creator)
                                    db.session.flush()
                            
                            journal = Journal(
                                title='东华学报',
                                issue=f'第{Journal.query.count() + 1}期',
                                publish_date=datetime.now().date(),
                                status='draft',
                                description=f'自动创建的期刊 - 上传文件: {filename}',
                                paper_count=0,
                                created_by=journal_creator.id
                            )
                            db.session.add(journal)
                            db.session.flush()
                            logger.info(f"创建新期刊: {journal.id}")
                
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
                        
                        # 如果之前没有预解析或预解析失败，现在进行完整解析
                        if not papers_data:
                            papers_data = parse_pdf_to_papers(file_path, journal.id,temp_output_dir)
                            logger.info(f"完整PDF解析结果: {len(papers_data) if papers_data else 0} 篇论文")
                        
                        # 检查数据库唯一约束冲突
                        if papers_data:
                            for paper_data in papers_data:
                                manuscript_id = paper_data.get('manuscript_id', '')
                                title = paper_data.get('title', '')
                                
                                # 检查稿件号是否已存在
                                if manuscript_id:
                                    existing_manuscript = Paper.query.filter_by(manuscript_id=manuscript_id).first()
                                    if existing_manuscript:
                                        logger.info(f"稿件号 {manuscript_id} 已存在，需要用户确认是否覆盖")
                                        return {
                                            'success': True,
                                            'message': f'稿件号"{manuscript_id}"已存在',
                                            'duplicate': True,
                                            'existing_paper': {
                                                'id': existing_manuscript.id,
                                                'title': existing_manuscript.title,
                                                'manuscript_id': existing_manuscript.manuscript_id,
                                                'authors': existing_manuscript.authors
                                            },
                                            'requires_confirmation': True
                                        }
                                
                                # 检查同期刊内标题是否已存在
                                if title:
                                    existing_title = Paper.query.filter_by(journal_id=journal.id, title=title).first()
                                    if existing_title:
                                        logger.info(f"期刊 {journal.id} 中标题'{title}'已存在，需要用户确认是否覆盖")
                                        return {
                                            'success': True,
                                            'message': f'该期刊中已存在相同标题的论文',
                                            'duplicate': True,
                                            'existing_paper': {
                                                'id': existing_title.id,
                                                'title': existing_title.title,
                                                'manuscript_id': existing_title.manuscript_id,
                                                'authors': existing_title.authors
                                            },
                                            'requires_confirmation': True
                                        }
                        
                        # 保存解析出的真实论文
                        if papers_data:
                            logger.info(f"开始保存 {len(papers_data)} 篇论文到数据库")
                            for paper_data in papers_data:
                                paper = Paper(
                                    journal_id=journal.id,
                                    title=paper_data.get('title', ''),
                                    authors=paper_data.get('authors', ''),
                                    abstract=paper_data.get('abstract', ''),
                                    keywords=paper_data.get('keywords', ''),
                                    doi=paper_data.get('doi', ''),
                                    page_start=paper_data.get('page_start') or 1,
                                    page_end=paper_data.get('page_end') or None,
                                    file_path=file_path,
                                    manuscript_id=paper_data.get('manuscript_id', ''),
                                    pdf_pages=paper_data.get('pdf_pages', 0),
                                    first_author=paper_data.get('first_author', ''),
                                    corresponding=paper_data.get('corresponding', ''),
                                    issue=paper_data.get('issue', journal.issue),
                                    is_dhu=paper_data.get('is_dhu', False),
                                    chinese_title=paper_data.get('chinese_title', ''),
                                    chinese_authors=paper_data.get('chinese_authors', ''),
                                    first_image_url=paper_data.get('first_local_path'),
                                    second_image_url=paper_data.get('second_local_path')
                                )
                                db.session.add(paper)
                            
                            logger.info(f"成功解析出 {len(papers_data)} 篇真实论文")
                            
                            # 从解析的论文中获取真实的issue值，并更新期刊表
                            if papers_data and papers_data[0].get('issue'):
                                real_issue = papers_data[0]['issue']
                                if journal.issue != real_issue:
                                    logger.info(f"更新期刊issue字段: '{journal.issue}' → '{real_issue}'")
                                    journal.issue = real_issue
                            
                            # 更新期刊的论文数量
                            journal.paper_count = Paper.query.filter_by(journal_id=journal.id).count()
                        else:
                            logger.warning("PDF解析未返回论文数据")
                    
                    except Exception as parse_error:
                        logger.error(f"PDF解析失败: {str(parse_error)}")
                        import traceback
                        logger.error(f"详细错误: {traceback.format_exc()}")
                else:
                    logger.info("非PDF文件，跳过论文解析")
                
                # 更新期刊的论文数量
                journal.paper_count = Paper.query.filter_by(journal_id=journal.id).count()
                
                db.session.commit()
                logger.info(f"期刊和文件记录已保存到数据库: 期刊ID={journal.id}, 文件ID={file_upload.id}, 论文数量={journal.paper_count}")
                
                # 检查是否成功解析出论文
                papers_count = Paper.query.filter_by(journal_id=journal.id).count()
                
                # 构建返回数据
                response_data = format_file_response(
                    '文件上传成功，已解析出论文信息' if papers_count > 0 else '文件上传成功，但未能解析出论文信息，请检查PDF文件格式',
                    timestamp, filename, file_path, os.path.getsize(file_path), journal.id,
                    papersCount=papers_count,
                    journalCreated=journal_created,
                    journalInfo={'title': journal.title, 'issue': journal.issue},
                    parsing_status='completed',
                    parsing_progress=100,
                    parsing_success=papers_count > 0
                )
                
                if papers_count == 0:
                    response_data['warning'] = True
                
                return {'success': True, 'data': response_data}
                
            except Exception as db_error:
                logger.error(f"数据库保存失败: {str(db_error)}")
                db.session.rollback()
                return {'success': False, 'message': f'文件上传失败: {str(db_error)}', 'status_code': 500}
        
        except Exception as e:
            logger.error(f"文件上传错误: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return {'success': False, 'message': f'服务器内部错误: {str(e)}', 'status_code': 500}
    
    def upload_file_with_overwrite(self, file, journal_id, overwrite_paper_id=None, user=None):
        """带覆盖选项的文件上传"""
        try:
            # 如果指定了要覆盖的论文ID，先删除现有论文
            if overwrite_paper_id:
                existing_paper = Paper.query.get(overwrite_paper_id)
                if existing_paper:
                    # 检查用户是否有权限删除该论文
                    if user and not PermissionService.can_delete_paper(user, existing_paper):
                        return {'success': False, 'message': '您没有权限删除该论文', 'status_code': 403}
                    
                    # 删除现有论文
                    db.session.delete(existing_paper)
                    db.session.commit()
                    logger.info(f"已删除现有论文 ID: {overwrite_paper_id}")
            
            # 执行正常的上传流程
            return self.upload_file(file, journal_id, user)
            
        except Exception as e:
            logger.error(f"覆盖上传错误: {str(e)}")
            return {'success': False, 'message': f'覆盖上传失败: {str(e)}', 'status_code': 500}
    
    def download_file(self, filename):
        """文件下载"""
        try:
            from flask import send_file
            # 使用绝对路径构建文件路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, 'uploads', filename)
            logger.info(f"尝试下载文件: {file_path}")

            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return {'success': False, 'message': '文件不存在', 'status_code': 404}

            return {'success': True, 'file_path': file_path}
        except Exception as e:
            logger.error(f"文件下载错误: {str(e)}")
            return {'success': False, 'message': f'文件下载失败: {str(e)}', 'status_code': 500}
    
    def preview_file(self, filename):
        """文件预览"""
        try:
            from flask import send_file
            # 使用绝对路径构建文件路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, 'uploads', filename)
            logger.info(f"尝试预览文件: {file_path}")

            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return {'success': False, 'message': '文件不存在', 'status_code': 404}

            # 检查文件类型
            file_type = get_file_type(filename)
            
            return {'success': True, 'file_path': file_path, 'file_type': file_type}
        except Exception as e:
            logger.error(f"文件预览错误: {str(e)}")
            return {'success': False, 'message': f'文件预览失败: {str(e)}', 'status_code': 500}
