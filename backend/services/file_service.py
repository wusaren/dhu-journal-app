"""
文件服务
从 app.py 中提取文件相关业务逻辑，保持完全兼容
"""
from models import Journal, Paper, FileUpload, User, db
from services.permission_service import PermissionService
from utils.helpers import get_file_type, generate_timestamp, ensure_upload_directory, format_file_response
from utils.validators import validate_file_upload
from config.config import current_config
from datetime import datetime
import os
import re
import logging
import bcrypt
import shutil

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
                journal_created = False  # 初始化标志，用于跟踪是否创建了新期刊
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
                    
                    if get_file_type(filename) == 'pdf':
                        # PDF文件将在后续使用MinerU进行解析
                        # 如果启用了MinerU，将在后续正式解析时使用MinerU获取期刊信息
                        # 这里跳过预解析，直接使用默认期刊逻辑
                        logger.info(f"PDF文件，跳过预解析（将在正式解析时使用MinerU）")
                        journal = None
                        papers_data = None
                    
                    # PDF文件在解析前不创建临时期刊，等待解析完成后根据期号匹配或创建
                    # 如果不是PDF文件，才使用默认期刊逻辑
                    if not journal and get_file_type(filename) != 'pdf':
                        default_journal = Journal.query.filter_by(title='东华学报', status='draft').first()
                        if default_journal:
                            journal = default_journal
                            logger.info(f"使用现有默认期刊: {journal.id}")
                        else:
                            # 创建新期刊记录（仅非PDF文件）
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
                # 对于PDF文件，如果还没有期刊（等待解析后确定），journal_id可能为None，稍后会更新
                file_upload = FileUpload(
                    journal_id=journal.id if journal else None,
                    original_filename=filename,
                    stored_filename=stored_filename,
                    file_type=get_file_type(filename),
                    file_size=os.path.getsize(file_path),
                    upload_path=file_path,
                    upload_status='completed'
                )
                db.session.add(file_upload)
                # 先flush获取file_upload.id，以便用于MinerU的data_id
                db.session.flush()
                
                # 使用文件名作为data_id（用于MinerU结果文件夹命名）
                # 处理文件名：移除扩展名，清理特殊字符，确保文件夹名合法
                from werkzeug.utils import secure_filename
                # 获取文件名（不含扩展名）
                file_basename = os.path.splitext(filename)[0]
                # 清理文件名：移除或替换不合法字符
                # Windows文件夹名不允许的字符: < > : " / \ | ? *
                safe_folder_name = re.sub(r'[<>:"/\\|?*]', '_', file_basename)
                # 移除首尾空格和点
                safe_folder_name = safe_folder_name.strip('. ')
                # 如果为空，使用默认名称
                if not safe_folder_name:
                    safe_folder_name = f"file_{file_upload.id}"
                data_id = safe_folder_name
                
                logger.info(f"文件上传记录已创建: file_upload.id={file_upload.id}, 原始文件名={filename}, data_id={data_id}")
                
                # 如果是PDF文件，解析并提取真实的论文信息
                if get_file_type(filename) == 'pdf':
                    logger.info(f"开始解析PDF文件: {file_path}")
                    
                    papers_data = None
                    model_json_path = None
                    
                    # 使用MinerU进行PDF解析（通过API接口调用，统一入口）
                    if current_config.USE_MINERU:
                        try:
                            # 通过调用API的内部处理函数（统一入口）
                            from blueprints.files import _process_file_with_mineru_internal
                            
                            # 调用API的内部处理函数（统一逻辑），等待完成
                            mineru_result = _process_file_with_mineru_internal(
                                file_path=file_path,
                                data_id=data_id,  # 使用文件名作为data_id
                                wait=True  # 同步处理，等待完成
                            )
                            
                            if mineru_result['success']:
                                mineru_batch_id = mineru_result.get('batch_id')
                                model_json_path = mineru_result.get('model_json_path')
                                logger.info(f"MinerU处理完成，batch_id: {mineru_batch_id}, model_json_path: {model_json_path}")
                                
                                if model_json_path and os.path.exists(model_json_path):
                                    # 使用新的JSON解析函数
                                    # 注意：此时journal可能为None（PDF文件在解析前不创建期刊），传入临时值0
                                    from services.pdf_parser import parse_pdf_from_mineru_json
                                    papers_data = parse_pdf_from_mineru_json(
                                        model_json_path=model_json_path,
                                        pdf_path=file_path,
                                        journal_id=journal.id if journal else 0,
                                        output_dir=temp_output_dir
                                    )
                                    logger.info(f"MinerU JSON解析结果: {len(papers_data) if papers_data else 0} 篇论文")
                                else:
                                    logger.warning(f"MinerU处理完成，但未找到model_json_path: {model_json_path}")
                            else:
                                logger.warning(f"MinerU处理失败: {mineru_result.get('message', '未知错误')}")
                        except Exception as mineru_error:
                            logger.error(f"MinerU处理异常: {str(mineru_error)}")
                            import traceback
                            logger.error(f"详细错误: {traceback.format_exc()}")
                    
                    # 如果MinerU未启用或失败，无法继续解析
                    if not papers_data:
                        logger.warning("MinerU未启用或处理失败，无法继续解析")
                        papers_data = []
                    
                    logger.info(f"最终PDF解析结果: {len(papers_data) if papers_data else 0} 篇论文")
                    
                    # 根据解析出的期号自动匹配或创建期刊（简单逻辑：找到就用，找不到就创建）
                    if papers_data and papers_data[0].get('issue'):
                        real_issue = papers_data[0]['issue']
                        journal_title = '东华学报'  # 默认期刊标题
                        
                        # 查找是否存在匹配的期刊（标题+期号）
                        matched_journal = Journal.query.filter(
                            Journal.title == journal_title,
                            Journal.issue == real_issue
                        ).first()
                        
                        if matched_journal:
                            # 如果找到了匹配的期刊，直接使用（不修改任何数据）
                            logger.info(
                                f"根据解析出的期号 '{real_issue}' 找到匹配期刊ID={matched_journal.id}，"
                                f"将论文归入该期刊"
                            )
                            journal = matched_journal
                        else:
                            # 如果没有找到匹配的期刊，创建新期刊
                            if not user:
                                user = User.query.first()
                            if not user:
                                password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
                                user = User(
                                    username='admin',
                                    password_hash=password_hash.decode('utf-8'),
                                    email='admin@example.com',
                                    role='admin'
                                )
                                db.session.add(user)
                                db.session.flush()
                            
                            journal = Journal(
                                title=journal_title,
                                issue=real_issue,
                                publish_date=datetime.now().date(),
                                status='draft',
                                description=f'根据解析出的期号自动创建的期刊',
                                paper_count=0,
                                created_by=user.id
                            )
                            db.session.add(journal)
                            db.session.flush()
                            journal_created = True  # 标记为新创建的期刊
                            logger.info(f"未找到匹配期刊，根据期号 '{real_issue}' 创建新期刊ID={journal.id}")
                    elif not papers_data:
                        # 如果PDF文件解析失败，且没有期刊，使用默认期刊（但不创建新期刊，避免产生"第一期"）
                        if not journal:
                            # 查找现有的默认期刊
                            default_journal = Journal.query.filter_by(title='东华学报', status='draft').first()
                            if default_journal:
                                journal = default_journal
                                logger.info(f"PDF解析失败，使用现有默认期刊ID={journal.id}")
                            else:
                                # 如果没有默认期刊，且用户指定了journal_id，使用指定的期刊
                                if journal_id and journal_id != '1':
                                    journal = Journal.query.get(int(journal_id))
                                    if journal:
                                        logger.info(f"PDF解析失败，使用用户指定的期刊ID={journal.id}")
                                    else:
                                        logger.warning(f"PDF解析失败，且指定的期刊ID={journal_id}不存在")
                                else:
                                    logger.warning(f"PDF解析失败，且没有可用的期刊，文件将无法关联到期刊")
                    
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
                    
                    # 更新文件上传记录的journal_id（如果期刊发生了变化或之前为None）
                    if file_upload.journal_id != journal.id:
                        old_journal_id = file_upload.journal_id
                        file_upload.journal_id = journal.id
                        logger.info(f"更新文件上传记录的journal_id: {old_journal_id} → {journal.id}")
                    
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
                                citation=paper_data.get('citation', ''),
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
                        
                        # 更新期刊的论文数量
                        journal.paper_count = Paper.query.filter_by(journal_id=journal.id).count()
                    else:
                        logger.warning("PDF解析未返回论文数据")
                else:
                    logger.info("非PDF文件，跳过论文解析")
                
                # 更新期刊的论文数量
                journal.paper_count = Paper.query.filter_by(journal_id=journal.id).count()
                
                db.session.commit()
                logger.info(f"期刊和文件记录已保存到数据库: 期刊ID={journal.id}, 文件ID={file_upload.id}, 论文数量={journal.paper_count}")
                
                # 检查是否成功解析出论文
                papers_count = Paper.query.filter_by(journal_id=journal.id).count()
                
                # 构建返回数据
                # 如果创建了新期刊，直接使用简洁的提示信息
                if journal_created and journal:
                    base_message = f"系统已自动创建新期刊：{journal.title} - {journal.issue}"
                    logger.info(f"✓ 提示用户：{base_message}")
                else:
                    base_message = '文件上传成功，已解析出论文信息' if papers_count > 0 else '文件上传成功，但未能解析出论文信息，请检查PDF文件格式'
                    logger.info(f"未创建新期刊，使用默认消息: {base_message}")
                
                # 确保journal不为None
                if not journal:
                    logger.error("期刊为None，无法完成文件上传")
                    return {'success': False, 'message': '文件上传失败：无法确定期刊', 'status_code': 500}
                
                response_data = format_file_response(
                    base_message,
                    timestamp, filename, file_path, os.path.getsize(file_path), journal.id,
                    papersCount=papers_count,
                    journalCreated=journal_created,
                    journalInfo={'title': journal.title, 'issue': journal.issue},
                    parsing_status='completed',
                    parsing_progress=100,
                    parsing_success=papers_count > 0
                )
                
                # 添加调试日志，确认响应数据
                logger.info(f"响应数据 - journalCreated: {response_data.get('journalCreated')}, message: {response_data.get('message', '')[:100]}")
                
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
            # 如果指定了要覆盖的论文ID，先删除现有论文及其MinerU结果文件夹
            if overwrite_paper_id:
                existing_paper = Paper.query.get(overwrite_paper_id)
                if existing_paper:
                    # 检查用户是否有权限删除该论文
                    if user and not PermissionService.can_delete_paper(user, existing_paper):
                        return {'success': False, 'message': '您没有权限删除该论文', 'status_code': 403}
                    
                    # 删除MinerU结果文件夹（如果存在）
                    if existing_paper.file_path:
                        try:
                            # 查找对应的FileUpload记录
                            file_upload = FileUpload.query.filter_by(upload_path=existing_paper.file_path).first()
                            if file_upload:
                                # data_id现在使用文件名（不含扩展名）
                                original_filename = file_upload.original_filename
                                # 获取文件名（不含扩展名）
                                file_basename = os.path.splitext(original_filename)[0]
                                # 清理文件名：移除或替换不合法字符
                                safe_folder_name = re.sub(r'[<>:"/\\|?*]', '_', file_basename)
                                safe_folder_name = safe_folder_name.strip('. ')
                                # MinerU输出目录
                                mineru_output_dir = current_config.MINERU_OUTPUT_DIR
                                # 结果文件夹路径（可能带时间戳后缀）
                                base_folder = os.path.join(mineru_output_dir, safe_folder_name)
                                
                                # 查找匹配的文件夹（可能带时间戳后缀）
                                if os.path.exists(base_folder):
                                    # 精确匹配
                                    shutil.rmtree(base_folder)
                                    logger.info(f"已删除MinerU结果文件夹: {base_folder}")
                                else:
                                    # 查找以该名称开头的文件夹（处理时间戳后缀的情况）
                                    if os.path.exists(mineru_output_dir):
                                        for item in os.listdir(mineru_output_dir):
                                            item_path = os.path.join(mineru_output_dir, item)
                                            if os.path.isdir(item_path) and item.startswith(safe_folder_name + '_'):
                                                shutil.rmtree(item_path)
                                                logger.info(f"已删除MinerU结果文件夹（带时间戳）: {item_path}")
                                                break
                                    logger.info(f"MinerU结果文件夹不存在，跳过删除: {base_folder}")
                        except Exception as e:
                            logger.warning(f"删除MinerU结果文件夹失败: {str(e)}")
                    
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
