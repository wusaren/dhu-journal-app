"""
业务员API蓝图
用于业务员批量论文检测功能
"""

from flask import Blueprint, request, jsonify, send_file
from flask_security import auth_required
import logging
import os
from datetime import datetime

from models import db, BatchJob, PaperCheckResult
from services.batch_check_service import BatchCheckService
from services.batch_excel_export_service import BatchExcelExportService
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

operator_bp = Blueprint('operator', __name__, url_prefix='/api/operator')


@operator_bp.route('/directories/scan', methods=['POST'])
@auth_required()
def scan_directory():
    """
    扫描目录，返回符合条件的论文文件列表

    请求体:
    {
        "directory_path": "D:/论文批次/2024届"
    }

    返回:
    {
        "success": true,
        "files": [
            {"filename": "01_张三_论文.docx", "student_id": "01", "student_name": "张三", "path": "..."},
            ...
        ],
        "total": 10,
        "message": "共扫描到 10 篇符合格式的论文"
    }
    """
    try:
        data = request.get_json()
        directory_path = data.get('directory_path')
        
        if not directory_path:
            return jsonify({'success': False, 'message': '请提供目录路径'}), 400
        
        service = BatchCheckService()
        result = service.scan_directory(directory_path)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"扫描目录失败: {e}")
        return jsonify({'success': False, 'message': f'扫描目录失败: {str(e)}'}), 500


@operator_bp.route('/batch/start', methods=['POST'])
@auth_required()
def start_batch_check():
    """
    启动批量检测任务
    
    请求体:
    {
        "directory_path": "D:/论文批次/2024届",
        "pass_threshold": 85.0,
        "modules": ["Title", "Abstract", "Keywords", "Content", "TOC", "Figure", "Table", "References", "Formula"]
    }
    
    返回:
    {
        "success": true,
        "batch_id": 1,
        "total_papers": 23,
        "output_dir": "uploads/batch_check/batch_20260412_143000",
        "message": "已启动批量检测任务，共 23 篇论文"
    }
    """
    try:
        data = request.get_json()
        directory_path = data.get('directory_path')
        pass_threshold = data.get('pass_threshold', 85.0)
        modules = data.get('modules')  # 可选，检测模块列表
        
        if not directory_path:
            return jsonify({'success': False, 'message': '请提供论文目录路径'}), 400
        
        service = BatchCheckService()
        result = service.start_batch_check(
            directory_path=directory_path,
            pass_threshold=pass_threshold,
            modules=modules
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': {
                    'batch_id': result['batch_id'],
                    'total_papers': result['total_papers'],
                    'output_dir': result['output_dir']
                },
                'message': result.get('message', '')
            })
        else:
            return jsonify({'success': False, 'message': result.get('message', '')}), 400
            
    except Exception as e:
        logger.error(f"启动批量检测失败: {e}")
        return jsonify({'success': False, 'message': f'启动批量检测失败: {str(e)}'}), 500


@operator_bp.route('/batch/jobs', methods=['GET'])
@auth_required()
def get_batch_jobs():
    """
    获取批量任务列表
    
    查询参数:
    - limit: 返回数量，默认50
    
    返回:
    {
        "success": true,
        "jobs": [
            {
                "id": 1,
                "directory_path": "D:/论文批次/2024届",
                "output_path": "uploads/batch_check/batch_20260412_143000",
                "total_papers": 23,
                "processed": 23,
                "passed": 20,
                "failed": 1,
                "status": "completed",
                "pass_threshold": 85.0,
                "started_at": "2026-04-12T14:30:00",
                "completed_at": "2026-04-12T14:35:00",
                "created_at": "2026-04-12T14:30:00"
            },
            ...
        ]
    }
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        
        service = BatchCheckService()
        jobs = service.get_batch_jobs(limit=limit)

        return jsonify({
            'success': True,
            'data': {
                'jobs': jobs
            }
        })
        
    except Exception as e:
        logger.error(f"获取批次列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取批次列表失败: {str(e)}'}), 500


@operator_bp.route('/batch/jobs/<int:job_id>', methods=['GET', 'DELETE'])
@auth_required()
def get_or_delete_batch_job(job_id):
    """
    获取批次任务详情（含论文列表）或删除批次任务
    
    GET 返回:
    {
        "success": true,
        "job": { ... }
    }
    
    DELETE 返回:
    {
        "success": true,
        "message": "批次任务已删除"
    }
    """
    try:
        service = BatchCheckService()

        if request.method == 'DELETE':
            result = service.delete_batch_job(job_id)
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 400

        job = service.get_batch_job_detail(job_id)
        
        if not job:
            return jsonify({'success': False, 'message': '批次任务不存在'}), 404
        
        return jsonify({
            'success': True,
            'job': job
        })
        
    except Exception as e:
        logger.error(f"获取批次详情失败: {e}")
        return jsonify({'success': False, 'message': f'获取批次详情失败: {str(e)}'}), 500


@operator_bp.route('/batch/jobs/<int:job_id>/progress', methods=['GET'])
@auth_required()
def get_batch_progress(job_id):
    """
    获取批次任务进度（用于轮询）
    
    返回:
    {
        "success": true,
        "progress": {
            "batch_id": 1,
            "status": "running",
            "total_papers": 23,
            "processed": 15,
            "passed": 12,
            "failed": 1,
            "progress_percent": 65.2,
            "current_paper": "论文_2021016_李明.docx",
            "started_at": "2026-04-12T14:30:00"
        }
    }
    """
    try:
        service = BatchCheckService()
        progress = service.get_batch_progress(job_id)
        
        if not progress:
            return jsonify({'success': False, 'message': '批次任务不存在'}), 404
        
        return jsonify({
            'success': True,
            'progress': progress
        })
        
    except Exception as e:
        logger.error(f"获取批次进度失败: {e}")
        return jsonify({'success': False, 'message': f'获取批次进度失败: {str(e)}'}), 500


@operator_bp.route('/batch/jobs/<int:job_id>/cancel', methods=['POST'])
@auth_required()
def cancel_batch_job(job_id):
    """
    取消批次任务
    
    返回:
    {
        "success": true,
        "message": "任务已取消"
    }
    """
    try:
        service = BatchCheckService()
        result = service.cancel_batch_job(job_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"取消批次任务失败: {e}")
        return jsonify({'success': False, 'message': f'取消批次任务失败: {str(e)}'}), 500


@operator_bp.route('/batch/export-excel/<int:batch_id>', methods=['GET'])
@auth_required()
def export_batch_excel(batch_id):
    """
    导出批次Excel汇总表
    
    返回Excel文件下载
    """
    try:
        service = BatchExcelExportService()
        result = service.export_batch_excel(batch_id)
        
        if not result['success']:
            return jsonify(result), 400
        
        file_path = result['file_path']
        filename = result['filename']
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'Excel文件不存在'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"导出Excel失败: {e}")
        return jsonify({'success': False, 'message': f'导出Excel失败: {str(e)}'}), 500


@operator_bp.route('/batch/summary/<int:batch_id>', methods=['GET'])
@auth_required()
def get_batch_summary(batch_id):
    """
    获取批次汇总信息
    
    返回:
    {
        "success": true,
        "summary": {
            "batch_id": 1,
            "total_papers": 23,
            "processed": 23,
            "passed": 20,
            "failed": 1,
            "reviewed_count": 20,
            "needs_revision_count": 2,
            "pending_count": 0,
            "avg_pass_rate": 78.5,
            "status": "completed",
            "pass_threshold": 85.0
        }
    }
    """
    try:
        service = BatchExcelExportService()
        summary = service.get_batch_summary(batch_id)
        
        if not summary:
            return jsonify({'success': False, 'message': '批次任务不存在'}), 404
        
        return jsonify({
            'success': True,
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"获取批次汇总失败: {e}")
        return jsonify({'success': False, 'message': f'获取批次汇总失败: {str(e)}'}), 500


@operator_bp.route('/batch/papers/<int:paper_id>', methods=['GET'])
@auth_required()
def get_paper_detail(paper_id):
    """
    获取单篇论文检测详情
    
    返回:
    {
        "success": true,
        "paper": {
            "id": 1,
            "student_id": "2021001",
            "student_name": "张三",
            "original_filename": "论文_2021001_张三.docx",
            "original_path": "D:/论文批次/2024届/论文_2021001_张三.docx",
            "annotated_path": "uploads/batch_check/batch_20260412_143000/2021001_张三/论文_2021001_张三_检测报告.docx",
            "report_path": "uploads/batch_check/batch_20260412_143000/2021001_张三/论文_2021001_张三_检查报告.txt",
            "check_status": "completed",
            "review_status": "reviewed",
            "pass_rate": 92.5,
            "details_json": {...},
            "completed_at": "2026-04-12T14:35:00"
        }
    }
    """
    try:
        paper = PaperCheckResult.query.get(paper_id)
        
        if not paper:
            return jsonify({'success': False, 'message': '论文记录不存在'}), 404
        
        return jsonify({
            'success': True,
            'paper': {
                'id': paper.id,
                'batch_job_id': paper.batch_job_id,
                'student_id': paper.student_id,
                'student_name': paper.student_name,
                'original_filename': paper.original_filename,
                'original_path': paper.original_path,
                'annotated_path': paper.annotated_path,
                'report_path': paper.report_path,
                'check_status': paper.check_status,
                'review_status': paper.review_status,
                'pass_rate': paper.pass_rate,
                'details_json': paper.details_json,
                'error_message': paper.error_message,
                'created_at': paper.created_at.isoformat() if paper.created_at else None,
                'completed_at': paper.completed_at.isoformat() if paper.completed_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"获取论文详情失败: {e}")
        return jsonify({'success': False, 'message': f'获取论文详情失败: {str(e)}'}), 500


@operator_bp.route('/batch/papers/<int:paper_id>/open-original', methods=['GET'])
@auth_required()
def open_paper_original(paper_id):
    """打开原始论文文档"""
    try:
        paper = PaperCheckResult.query.get(paper_id)
        
        if not paper:
            return jsonify({'success': False, 'message': '论文记录不存在'}), 404
        
        if not paper.original_path or not os.path.exists(paper.original_path):
            return jsonify({'success': False, 'message': '原始文件不存在'}), 404
        
        return send_file(
            paper.original_path,
            as_attachment=True,
            download_name=paper.original_filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        logger.error(f"打开原始文档失败: {e}")
        return jsonify({'success': False, 'message': f'打开原始文档失败: {str(e)}'}), 500


@operator_bp.route('/batch/papers/<int:paper_id>/open-report', methods=['GET'])
@auth_required()
def open_paper_report(paper_id):
    """打开检测报告"""
    try:
        paper = PaperCheckResult.query.get(paper_id)
        
        if not paper:
            return jsonify({'success': False, 'message': '论文记录不存在'}), 404
        
        if not paper.report_path or not os.path.exists(paper.report_path):
            return jsonify({'success': False, 'message': '检测报告不存在'}), 404
        
        filename = f"{paper.student_id}_{paper.student_name}_检查报告.txt"
        return send_file(
            paper.report_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
        
    except Exception as e:
        logger.error(f"打开检测报告失败: {e}")
        return jsonify({'success': False, 'message': f'打开检测报告失败: {str(e)}'}), 500


@operator_bp.route('/batch/papers/<int:paper_id>/open-annotated', methods=['GET'])
@auth_required()
def open_paper_annotated(paper_id):
    """打开批注文档"""
    try:
        paper = PaperCheckResult.query.get(paper_id)
        
        if not paper:
            return jsonify({'success': False, 'message': '论文记录不存在'}), 404
        
        if not paper.annotated_path or not os.path.exists(paper.annotated_path):
            return jsonify({'success': False, 'message': '批注文档不存在'}), 404
        
        filename = f"{paper.student_id}_{paper.student_name}_检测报告.docx"
        return send_file(
            paper.annotated_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"打开批注文档失败: {e}")
        return jsonify({'success': False, 'message': f'打开批注文档失败: {str(e)}'}), 500


@operator_bp.route('/batch/upload-and-check', methods=['POST'])
@auth_required()
def upload_folder_and_check():
    """
    上传论文文件夹并可选启动批量检测

    请求格式：multipart/form-data
    - files: 多个文件
    - pass_threshold: 自动通过阈值（可选，默认85）
    - modules: 检测模块列表（可选）
    - auto_start: 是否自动启动检测（可选，默认false）

    返回:
    {
        "success": true,
        "batch_id": int or null,
        "files": [...],
        "temp_dir": str,
        "total": int,
        "message": str
    }
    """
    try:
        files = request.files.getlist('files')

        if not files or len(files) == 0:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400

        # 获取参数
        pass_threshold = request.form.get('pass_threshold', type=float, default=85.0)
        modules_str = request.form.get('modules', '')
        modules = [m.strip() for m in modules_str.split(',') if m.strip()] if modules_str else None
        auto_start = request.form.get('auto_start', 'false').lower() == 'true'

        # 过滤只保留docx文件
        docx_files = []
        for f in files:
            if f.filename and f.filename.lower().endswith('.docx'):
                docx_files.append(f)

        if not docx_files:
            return jsonify({'success': False, 'message': '没有找到.docx文件'}), 400

        # 创建临时目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_dir = os.path.join('uploads/batch_check', 'temp', f'upload_{timestamp}')
        os.makedirs(temp_dir, exist_ok=True)

        # 解析并保存文件
        batch_service = BatchCheckService()
        saved_files = []

        for f in docx_files:
            # 解析文件名获取学号和姓名（只使用文件名，不包含路径）
            # 移除可能存在的文件夹路径部分
            original_filename = os.path.basename(f.filename)
            parsed = batch_service.parse_filename(original_filename)
            if parsed:
                # 保存文件 - 只使用文件名，不保留路径结构
                safe_filename = secure_filename(original_filename)
                file_path = os.path.join(temp_dir, safe_filename)
                f.save(file_path)

                saved_files.append({
                    'filename': original_filename,
                    'student_id': parsed['student_id'],
                    'student_name': parsed['student_name'],
                    'path': file_path
                })

        if not saved_files:
            # 清理空目录
            try:
                os.rmdir(temp_dir)
            except:
                pass
            return jsonify({'success': False, 'message': '没有找到符合格式的论文文件（格式：论文_学号_姓名.docx）'}), 400

        # 如果需要自动启动批量检测
        batch_id = None
        if auto_start:
            result = batch_service.start_batch_check_from_files(
                files=saved_files,
                temp_dir=temp_dir,
                pass_threshold=pass_threshold,
                modules=modules
            )
            if result['success']:
                batch_id = result['batch_id']

        return jsonify({
            'success': True,
            'data': {
                'batch_id': batch_id,
                'files': saved_files,
                'temp_dir': temp_dir,
                'total': len(saved_files)
            },
            'message': f'成功上传 {len(saved_files)} 篇论文' + (f'，已启动批量检测任务' if batch_id else '')
        })

    except Exception as e:
        logger.error(f"上传文件夹失败: {e}")
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


@operator_bp.route('/batch/start-from-upload', methods=['POST'])
@auth_required()
def start_batch_check_from_upload():
    """
    从已上传的文件启动批量检测

    请求体:
    {
        "files": [{"filename": str, "student_id": str, "student_name": str, "path": str}, ...],
        "temp_dir": str,
        "pass_threshold": 85.0,
        "modules": ["Title", "Abstract", ...]
    }

    返回:
    {
        "success": true,
        "batch_id": int,
        "total_papers": int,
        "output_dir": str,
        "message": str
    }
    """
    try:
        data = request.get_json()
        files = data.get('files', [])
        temp_dir = data.get('temp_dir', '')
        pass_threshold = data.get('pass_threshold', 85.0)
        modules = data.get('modules')

        if not files:
            return jsonify({'success': False, 'message': '没有论文文件'}), 400

        service = BatchCheckService()
        result = service.start_batch_check_from_files(
            files=files,
            temp_dir=temp_dir,
            pass_threshold=pass_threshold,
            modules=modules
        )

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"启动批量检测失败: {e}")
        return jsonify({'success': False, 'message': f'启动批量检测失败: {str(e)}'}), 500
