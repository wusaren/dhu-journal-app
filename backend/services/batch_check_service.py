"""
批量论文检测服务
用于业务员批量检测论文目录下的所有论文
"""

import os
import re
import json
import logging
import shutil
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from models import db, BatchJob, PaperCheckResult
from services.paper_format_service import ChinesePaperFormatService

logger = logging.getLogger(__name__)

# 文件名匹配模式：学号_学生_论文（已去除.docx后缀）
# 例如：01_张三_论文.docx 或 2021001_张三_论文.docx
FILENAME_PATTERN = re.compile(r'^([^_\s]+)_([^_\s].*?)_(.+)$')


class BatchCheckService:
    """批量论文检测服务"""
    
    def __init__(self):
        self.chinese_service = ChinesePaperFormatService()
        # 批量检测输出基础目录
        self.batch_output_base = 'uploads/batch_check'
        os.makedirs(self.batch_output_base, exist_ok=True)
    
    def parse_filename(self, filename: str) -> Optional[Dict[str, str]]:
        """
        解析文件名，提取学号和姓名
        格式：学号_学生_论文.docx

        Returns:
            {'student_id': '01', 'student_name': '张三'} 或 None
        """
        # 检查文件扩展名（不区分大小写）
        if not filename.lower().endswith('.docx'):
            logger.debug(f"文件扩展名不是.docx: {filename}")
            return None

        # 去除.docx后缀（不区分大小写）
        name_without_ext = filename[:-5] if filename.lower().endswith('.docx') else filename

        logger.debug(f"正在匹配文件名: {name_without_ext}")

        match = FILENAME_PATTERN.match(name_without_ext)
        if match:
            student_id = match.group(1)  # 学号
            student_name = match.group(2)  # 学生姓名
            paper_title = match.group(3)  # 论文标题（可选）
            # 清理姓名中的多余下划线，保留空格
            student_name = student_name.replace('_', ' ').strip()
            return {
                'student_id': student_id,
                'student_name': student_name
            }
        return None
    
    def scan_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        扫描目录，返回符合条件的文件列表
        
        Args:
            directory_path: 要扫描的目录路径
            
        Returns:
            {
                'success': bool,
                'files': [{'filename': str, 'student_id': str, 'student_name': str, 'path': str}, ...],
                'total': int,
                'message': str
            }
        """
        try:
            if not os.path.exists(directory_path):
                return {
                    'success': False,
                    'message': f'目录不存在: {directory_path}'
                }
            
            if not os.path.isdir(directory_path):
                return {
                    'success': False,
                    'message': f'路径不是目录: {directory_path}'
                }
            
            files = []
            for filename in os.listdir(directory_path):
                # 只处理.docx文件
                if not filename.lower().endswith('.docx'):
                    continue
                
                file_path = os.path.join(directory_path, filename)
                if not os.path.isfile(file_path):
                    continue
                
                # 解析文件名
                parsed = self.parse_filename(filename)
                if parsed:
                    files.append({
                        'filename': filename,
                        'student_id': parsed['student_id'],
                        'student_name': parsed['student_name'],
                        'path': file_path
                    })
            
            return {
                'success': True,
                'files': files,
                'total': len(files),
                'message': f'共扫描到 {len(files)} 篇符合格式的论文'
            }
            
        except Exception as e:
            logger.error(f"扫描目录失败: {e}")
            return {
                'success': False,
                'message': f'扫描目录失败: {str(e)}'
            }
    
    def create_batch_output_dir(self) -> str:
        """创建批次输出目录"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        batch_dir = os.path.join(self.batch_output_base, f'batch_{timestamp}')
        os.makedirs(batch_dir, exist_ok=True)
        return batch_dir
    
    def start_batch_check(self, directory_path: str, pass_threshold: float = 85.0,
                          modules: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        启动批量检测任务
        
        Args:
            directory_path: 论文目录
            pass_threshold: 自动通过阈值
            modules: 要检测的模块列表
            
        Returns:
            {'success': bool, 'batch_id': int, 'message': str}
        """
        try:
            # 扫描目录
            scan_result = self.scan_directory(directory_path)
            if not scan_result['success']:
                return {'success': False, 'message': scan_result['message']}
            
            files = scan_result['files']
            if not files:
                return {'success': False, 'message': '目录中没有找到符合格式的论文文件'}
            
            # 创建批次输出目录
            output_dir = self.create_batch_output_dir()
            
            # 创建批次记录
            batch_job = BatchJob(
                directory_path=directory_path,
                output_path=output_dir,
                total_papers=len(files),
                processed=0,
                passed=0,
                failed=0,
                status='running',
                pass_threshold=pass_threshold,
                started_at=datetime.now()
            )
            db.session.add(batch_job)
            db.session.commit()
            
            # 为每篇论文创建检测结果记录
            for file_info in files:
                student_dir = f"{file_info['student_id']}_{file_info['student_name']}"
                student_dir = self._sanitize_filename(student_dir)
                student_output_dir = os.path.join(output_dir, student_dir)
                os.makedirs(student_output_dir, exist_ok=True)
                
                paper_result = PaperCheckResult(
                    batch_job_id=batch_job.id,
                    student_id=file_info['student_id'],
                    student_name=file_info['student_name'],
                    original_filename=file_info['filename'],
                    original_path=file_info['path'],
                    check_status='pending',
                    review_status='pending'
                )
                db.session.add(paper_result)
            
            db.session.commit()
            
            # 在后台线程中执行检测
            thread = threading.Thread(
                target=self._run_batch_check,
                args=(batch_job.id, modules),
                daemon=True
            )
            thread.start()
            
            return {
                'success': True,
                'batch_id': batch_job.id,
                'total_papers': len(files),
                'output_dir': output_dir,
                'message': f'已启动批量检测任务，共 {len(files)} 篇论文'
            }

        except Exception as e:
            logger.error(f"启动批量检测失败: {e}")
            return {'success': False, 'message': f'启动批量检测失败: {str(e)}'}

    def start_batch_check_from_files(self, files: List[Dict[str, str]], temp_dir: str,
                                     pass_threshold: float = 85.0,
                                     modules: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        从上传的文件列表启动批量检测任务

        Args:
            files: 文件信息列表 [{'filename': str, 'student_id': str, 'student_name': str, 'path': str}, ...]
            temp_dir: 临时目录路径
            pass_threshold: 自动通过阈值
            modules: 要检测的模块列表

        Returns:
            {'success': bool, 'batch_id': int, 'message': str}
        """
        try:
            if not files:
                return {'success': False, 'message': '没有论文文件'}

            # 创建批次输出目录
            output_dir = self.create_batch_output_dir()

            # 创建批次记录
            batch_job = BatchJob(
                directory_path=temp_dir,  # 使用临时目录作为源目录
                output_path=output_dir,
                total_papers=len(files),
                processed=0,
                passed=0,
                failed=0,
                status='running',
                pass_threshold=pass_threshold,
                started_at=datetime.now()
            )
            db.session.add(batch_job)
            db.session.commit()

            # 为每篇论文创建检测结果记录
            for file_info in files:
                student_dir = f"{file_info['student_id']}_{file_info['student_name']}"
                student_dir = self._sanitize_filename(student_dir)
                student_output_dir = os.path.join(output_dir, student_dir)
                os.makedirs(student_output_dir, exist_ok=True)

                paper_result = PaperCheckResult(
                    batch_job_id=batch_job.id,
                    student_id=file_info['student_id'],
                    student_name=file_info['student_name'],
                    original_filename=file_info['filename'],
                    original_path=file_info['path'],
                    check_status='pending',
                    review_status='pending'
                )
                db.session.add(paper_result)

            db.session.commit()

            # 在后台线程中执行检测
            thread = threading.Thread(
                target=self._run_batch_check,
                args=(batch_job.id, modules),
                daemon=True
            )
            thread.start()

            return {
                'success': True,
                'batch_id': batch_job.id,
                'total_papers': len(files),
                'output_dir': output_dir,
                'message': f'已启动批量检测任务，共 {len(files)} 篇论文'
            }

        except Exception as e:
            logger.error(f"启动批量检测失败: {e}")
            return {'success': False, 'message': f'启动批量检测失败: {str(e)}'}

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename
    
    def _run_batch_check(self, batch_job_id: int, modules: Optional[List[str]] = None):
        """后台执行批量检测"""
        # 延迟导入app以避免循环依赖
        import app as flask_app_instance

        # 在应用上下文中运行
        with flask_app_instance.app.app_context():
            try:
                batch_job = BatchJob.query.get(batch_job_id)
                if not batch_job:
                    logger.error(f"批次任务不存在: {batch_job_id}")
                    return

                papers = PaperCheckResult.query.filter_by(batch_job_id=batch_job_id).all()
                total = len(papers)
                processed = 0
                passed = 0
                failed = 0

                for paper in papers:
                    try:
                        # 处理单篇论文
                        result = self.process_single_paper(
                            batch_job, paper, modules
                        )

                        if result['success']:
                            passed += 1
                        else:
                            failed += 1

                        processed += 1

                        # 更新批次进度
                        batch_job.processed = processed
                        batch_job.passed = passed
                        batch_job.failed = failed
                        db.session.commit()

                    except Exception as e:
                        logger.error(f"处理论文失败: {paper.original_filename}, 错误: {e}")
                        paper.check_status = 'failed'
                        paper.error_message = str(e)
                        paper.completed_at = datetime.now()
                        failed += 1
                        processed += 1

                        batch_job.processed = processed
                        batch_job.passed = passed
                        batch_job.failed = failed
                        db.session.commit()

                # 标记批次完成
                batch_job.status = 'completed'
                batch_job.completed_at = datetime.now()
                db.session.commit()

                logger.info(f"批次任务 {batch_job_id} 完成: 总计{total}, 通过{passed}, 失败{failed}")

                # 生成汇总文件
                self._generate_batch_summary(batch_job)

            except Exception as e:
                logger.error(f"批量检测执行失败: {e}")
                try:
                    batch_job = BatchJob.query.get(batch_job_id)
                    if batch_job:
                        batch_job.status = 'failed'
                        db.session.commit()
                except Exception as inner_e:
                    logger.error(f"更新批次状态失败: {inner_e}")
    
    def process_single_paper(self, batch_job: BatchJob, paper: PaperCheckResult,
                             modules: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        处理单篇论文的检测
        
        Args:
            batch_job: 批次任务
            paper: 论文检测结果记录
            modules: 要检测的模块
            
        Returns:
            {'success': bool, 'pass_rate': float, 'message': str}
        """
        try:
            original_path = paper.original_path
            if not os.path.exists(original_path):
                raise FileNotFoundError(f"文件不存在: {original_path}")
            
            # 创建学生输出目录
            student_dir = f"{paper.student_id}_{paper.student_name}"
            student_dir = self._sanitize_filename(student_dir)
            student_output_dir = os.path.join(batch_job.output_path, student_dir)
            os.makedirs(student_output_dir, exist_ok=True)
            
            # 设置输出路径
            base_name = paper.original_filename[:-5]  # 去除.docx
            annotated_filename = f"{base_name}_检测报告.docx"
            report_filename = f"{base_name}_检查报告.txt"
            details_filename = f"{base_name}_result.json"
            
            annotated_path = os.path.join(student_output_dir, annotated_filename)
            report_path = os.path.join(student_output_dir, report_filename)
            details_path = os.path.join(student_output_dir, details_filename)
            
            # 调用检测服务
            result = self.chinese_service.check_all(
                docx_path=original_path,
                reports_dir=student_output_dir,
                annotate_dir=student_output_dir,
                modules=modules
            )
            
            if result.get('success'):
                data = result.get('data', {})
                summary = data.get('summary', {})
                
                pass_rate = summary.get('pass_rate', 0.0)
                
                # 复制报告文件到学生目录后删除原始文件
                if data.get('report_saved') and data.get('report_filename'):
                    src_report = os.path.join(student_output_dir, data['report_filename'])
                    if os.path.exists(src_report):
                        if src_report != report_path:
                            shutil.copy(src_report, report_path)
                        os.remove(src_report)  # 删除原始文件

                # 复制批注文档到学生目录后删除原始文件
                if data.get('annotated_saved') and data.get('annotated_filename'):
                    src_annotated = os.path.join(student_output_dir, data['annotated_filename'])
                    if os.path.exists(src_annotated):
                        if src_annotated != annotated_path:
                            shutil.copy(src_annotated, annotated_path)
                        os.remove(src_annotated)  # 删除原始文件
                
                # 保存详细结果JSON
                if 'results' in data:
                    with open(details_path, 'w', encoding='utf-8') as f:
                        json.dump(data['results'], f, ensure_ascii=False, indent=2)
                
                # 根据通过率设置审核状态
                if pass_rate >= batch_job.pass_threshold:
                    review_status = 'reviewed'  # 通过
                else:
                    review_status = 'needs_revision'  # 需修改
                
                # 更新论文检测结果
                paper.check_status = 'completed'
                paper.review_status = review_status
                paper.pass_rate = pass_rate
                paper.report_path = report_path
                paper.annotated_path = annotated_path
                paper.details_json = summary
                paper.completed_at = datetime.now()
                
                return {
                    'success': True,
                    'pass_rate': pass_rate,
                    'review_status': review_status
                }
            else:
                raise Exception(result.get('message', '检测失败'))
                
        except Exception as e:
            logger.error(f"处理论文失败: {paper.original_filename}, 错误: {e}")
            paper.check_status = 'failed'
            paper.error_message = str(e)
            paper.completed_at = datetime.now()
            return {'success': False, 'message': str(e)}
    
    def _generate_batch_summary(self, batch_job: BatchJob):
        """生成批次汇总文件"""
        try:
            summary_path = os.path.join(batch_job.output_path, 'batch_summary.txt')
            
            papers = PaperCheckResult.query.filter_by(batch_job_id=batch_job.id).all()
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(f"批量检测批次汇总\n")
                f.write(f"{'='*50}\n\n")
                f.write(f"批次ID: {batch_job.id}\n")
                f.write(f"执行时间: {batch_job.started_at.strftime('%Y-%m-%d %H:%M:%S') if batch_job.started_at else 'N/A'}\n")
                f.write(f"完成时间: {batch_job.completed_at.strftime('%Y-%m-%d %H:%M:%S') if batch_job.completed_at else 'N/A'}\n")
                f.write(f"源目录: {batch_job.directory_path}\n")
                f.write(f"输出目录: {batch_job.output_path}\n")
                f.write(f"自动通过阈值: {batch_job.pass_threshold}%\n\n")
                f.write(f"检测统计:\n")
                f.write(f"  总论文数: {batch_job.total_papers}\n")
                f.write(f"  已处理: {batch_job.processed}\n")
                f.write(f"  通过: {batch_job.passed}\n")
                f.write(f"  失败: {batch_job.failed}\n\n")
                f.write(f"论文详情:\n")
                f.write(f"{'-'*50}\n")
                
                for paper in papers:
                    status_text = {
                        'pending': '待处理',
                        'completed': '已完成',
                        'failed': '失败'
                    }.get(paper.check_status, paper.check_status)
                    
                    review_text = {
                        'pending': '待审核',
                        'reviewed': '已通过',
                        'needs_revision': '需修改'
                    }.get(paper.review_status, paper.review_status)
                    
                    f.write(f"\n学号: {paper.student_id}\n")
                    f.write(f"姓名: {paper.student_name}\n")
                    f.write(f"文件名: {paper.original_filename}\n")
                    f.write(f"检测状态: {status_text}\n")
                    f.write(f"审核状态: {review_text}\n")
                    f.write(f"通过率: {paper.pass_rate:.1f}%\n" if paper.pass_rate else "通过率: N/A\n")
                    if paper.error_message:
                        f.write(f"错误信息: {paper.error_message}\n")
            
            # 保存元数据JSON
            metadata_path = os.path.join(batch_job.output_path, 'metadata.json')
            metadata = {
                'batch_id': batch_job.id,
                'created_at': batch_job.started_at.isoformat() if batch_job.started_at else None,
                'completed_at': batch_job.completed_at.isoformat() if batch_job.completed_at else None,
                'directory_path': batch_job.directory_path,
                'output_path': batch_job.output_path,
                'pass_threshold': batch_job.pass_threshold,
                'total_papers': batch_job.total_papers,
                'processed': batch_job.processed,
                'passed': batch_job.passed,
                'failed': batch_job.failed,
                'papers': [
                    {
                        'student_id': p.student_id,
                        'student_name': p.student_name,
                        'filename': p.original_filename,
                        'check_status': p.check_status,
                        'review_status': p.review_status,
                        'pass_rate': p.pass_rate
                    }
                    for p in papers
                ]
            }
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"批次汇总已生成: {summary_path}")
            
        except Exception as e:
            logger.error(f"生成批次汇总失败: {e}")
    
    def get_batch_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取批次任务列表"""
        try:
            jobs = BatchJob.query.order_by(BatchJob.created_at.desc()).limit(limit).all()
            return [self._job_to_dict(job) for job in jobs]
        except Exception as e:
            logger.error(f"获取批次列表失败: {e}")
            return []
    
    def get_batch_job_detail(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """获取批次任务详情"""
        try:
            batch_job = BatchJob.query.get(batch_id)
            if not batch_job:
                return None
            
            papers = PaperCheckResult.query.filter_by(batch_job_id=batch_id).order_by(
                PaperCheckResult.student_id.asc()
            ).all()
            
            return {
                **self._job_to_dict(batch_job),
                'papers': [self._paper_to_dict(p) for p in papers]
            }
        except Exception as e:
            logger.error(f"获取批次详情失败: {e}")
            return None
    
    def get_batch_progress(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """获取批次任务进度"""
        try:
            batch_job = BatchJob.query.get(batch_id)
            if not batch_job:
                return None
            
            progress_percent = 0
            if batch_job.total_papers > 0:
                progress_percent = round(batch_job.processed / batch_job.total_papers * 100, 1)
            
            # 获取当前正在处理的论文
            current_paper = None
            if batch_job.status == 'running':
                # 找到第一个未完成的论文
                pending = PaperCheckResult.query.filter_by(
                    batch_job_id=batch_id,
                    check_status='pending'
                ).first()
                if pending:
                    current_paper = pending.original_filename
            
            return {
                'batch_id': batch_id,
                'status': batch_job.status,
                'total_papers': batch_job.total_papers,
                'processed': batch_job.processed,
                'passed': batch_job.passed,
                'failed': batch_job.failed,
                'progress_percent': progress_percent,
                'current_paper': current_paper,
                'started_at': batch_job.started_at.isoformat() if batch_job.started_at else None,
                'completed_at': batch_job.completed_at.isoformat() if batch_job.completed_at else None
            }
        except Exception as e:
            logger.error(f"获取批次进度失败: {e}")
            return None
    
    def cancel_batch_job(self, batch_id: int) -> Dict[str, Any]:
        """取消批次任务"""
        try:
            batch_job = BatchJob.query.get(batch_id)
            if not batch_job:
                return {'success': False, 'message': '批次任务不存在'}
            
            if batch_job.status not in ['pending', 'running']:
                return {'success': False, 'message': f'任务状态为 {batch_job.status}，无法取消'}
            
            batch_job.status = 'cancelled'
            batch_job.completed_at = datetime.now()
            db.session.commit()
            
            return {'success': True, 'message': '任务已取消'}
            
        except Exception as e:
            logger.error(f"取消批次任务失败: {e}")
            return {'success': False, 'message': f'取消失败: {str(e)}'}

    def delete_batch_job(self, batch_id: int) -> Dict[str, Any]:
        """删除批次任务及其关联数据"""
        try:
            batch_job = BatchJob.query.get(batch_id)
            if not batch_job:
                return {'success': False, 'message': '批次任务不存在'}

            output_path = batch_job.output_path

            PaperCheckResult.query.filter_by(batch_job_id=batch_id).delete()
            db.session.delete(batch_job)
            db.session.commit()

            if output_path and os.path.exists(output_path):
                try:
                    shutil.rmtree(output_path)
                except Exception as e:
                    logger.warning(f"删除输出目录失败: {output_path}, {e}")

            return {'success': True, 'message': '批次任务已删除'}

        except Exception as e:
            logger.error(f"删除批次任务失败: {e}")
            db.session.rollback()
            return {'success': False, 'message': f'删除失败: {str(e)}'}
    
    def _job_to_dict(self, job: BatchJob) -> Dict[str, Any]:
        """转换批次任务为字典"""
        return {
            'id': job.id,
            'directory_path': job.directory_path,
            'output_path': job.output_path,
            'total_papers': job.total_papers,
            'processed': job.processed,
            'passed': job.passed,
            'failed': job.failed,
            'status': job.status,
            'pass_threshold': job.pass_threshold,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'created_at': job.created_at.isoformat() if job.created_at else None
        }
    
    def _paper_to_dict(self, paper: PaperCheckResult) -> Dict[str, Any]:
        """转换论文检测结果为字典"""
        return {
            'id': paper.id,
            'student_id': paper.student_id,
            'student_name': paper.student_name,
            'original_filename': paper.original_filename,
            'original_path': paper.original_path,
            'annotated_path': paper.annotated_path,
            'report_path': paper.report_path,
            'check_status': paper.check_status,
            'review_status': paper.review_status,
            'pass_rate': paper.pass_rate,
            'error_message': paper.error_message,
            'created_at': paper.created_at.isoformat() if paper.created_at else None,
            'completed_at': paper.completed_at.isoformat() if paper.completed_at else None
        }
