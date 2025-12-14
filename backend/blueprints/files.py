"""
文件路由
从 app.py 中提取文件相关路由，保持完全兼容
"""
from flask import Blueprint, request, jsonify, send_file
from services.file_service import FileService
from services.mineru_service import MinerUService
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
files_bp = Blueprint('files', __name__, url_prefix='/api')

@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """文件上传 - 从 app.py 中提取，保持完全兼容"""
    try:
        if 'file' not in request.files:
            return jsonify({'message': '没有选择文件'}), 400
        
        file = request.files['file']
        journal_id = request.form.get('journalId', '1')
        
        file_service = FileService()
        result = file_service.upload_file(file, journal_id)
        
        if result['success']:
            # 直接返回data部分，但确保包含所有字段
            data = result['data']
            logger.info(f"返回数据: journalCreated={data.get('journalCreated')}, message={data.get('message', '')[:50]}")
            return jsonify(data)
        else:
            return jsonify({'message': result['message']}), result['status_code']
    
    except Exception as e:
        return jsonify({'message': f'文件上传失败: {str(e)}'}), 500

@files_bp.route('/download/<filename>')
def download_file(filename):
    """文件下载 - 从 app.py 中提取，保持完全兼容"""
    file_service = FileService()
    result = file_service.download_file(filename)
    
    if result['success']:
        return send_file(result['file_path'], as_attachment=True)
    else:
        return jsonify({'message': result['message']}), result['status_code']

@files_bp.route('/preview/<filename>')
def preview_file(filename):
    """文件预览 - 从 app.py 中提取，保持完全兼容"""
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


@files_bp.route('/mineru/status/<batch_id>', methods=['GET'])
def get_mineru_status(batch_id):
    """查询MinerU任务状态"""
    try:
        mineru_service = MinerUService()
        result = mineru_service.get_batch_results(batch_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['results']
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400
    except Exception as e:
        logger.error(f"查询MinerU状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败: {str(e)}'
        }), 500


@files_bp.route('/mineru/download/<batch_id>', methods=['POST'])
def download_mineru_result(batch_id):
    """下载MinerU解析结果"""
    try:
        mineru_service = MinerUService()
        
        # 先查询状态
        query_result = mineru_service.get_batch_results(batch_id)
        if not query_result['success']:
            return jsonify({
                'success': False,
                'message': query_result['message']
            }), 400
        
        results = query_result['results']
        if not results:
            return jsonify({
                'success': False,
                'message': '未找到任务结果'
            }), 404
        
        file_result = results[0]
        if file_result.get('state') != 'done':
            return jsonify({
                'success': False,
                'message': f'任务未完成，当前状态: {file_result.get("state")}',
                'state': file_result.get('state'),
                'progress': file_result.get('extract_progress')
            }), 400
        
        # 下载并解压（使用data_id作为文件夹名）
        zip_url = file_result.get('full_zip_url')
        data_id = file_result.get('data_id')  # 从结果中获取data_id
        extract_result = mineru_service.download_and_extract(zip_url, batch_id, data_id=data_id)
        
        if extract_result['success']:
            return jsonify({
                'success': True,
                'data': {
                    'markdown_path': extract_result['markdown_path'],
                    'json_path': extract_result['json_path'],
                    'docx_path': extract_result.get('docx_path'),
                    'html_path': extract_result.get('html_path'),
                    'extract_dir': extract_result['extract_dir']
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': extract_result['message']
            }), 500
    except Exception as e:
        logger.error(f"下载MinerU结果失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'下载失败: {str(e)}'
        }), 500


@files_bp.route('/mineru/parse/<batch_id>', methods=['POST'])
def parse_mineru_result(batch_id):
    """解析MinerU结果并提取论文信息"""
    try:
        mineru_service = MinerUService()
        
        # 先下载结果
        query_result = mineru_service.get_batch_results(batch_id)
        if not query_result['success']:
            return jsonify({
                'success': False,
                'message': query_result['message']
            }), 400
        
        results = query_result['results']
        if not results or results[0].get('state') != 'done':
            return jsonify({
                'success': False,
                'message': '任务未完成'
            }), 400
        
        zip_url = results[0].get('full_zip_url')
        data_id = results[0].get('data_id')  # 从结果中获取data_id
        extract_result = mineru_service.download_and_extract(zip_url, batch_id, data_id=data_id)
        
        if not extract_result['success']:
            return jsonify({
                'success': False,
                'message': extract_result['message']
            }), 500
        
        # 解析结果（使用model_json_path，通过parse_pdf_from_mineru_json解析）
        parsed_data = None
        if extract_result.get('model_json_path'):
            # 使用新的JSON解析方法
            from services.pdf_parser import parse_pdf_from_mineru_json
            # 注意：parse_pdf_from_mineru_json需要pdf_path参数，这里暂时返回None
            # 实际解析应该在file_service.py中进行
            parsed_data = None
        elif extract_result.get('json_path'):
            parsed_data = mineru_service.parse_json_result(extract_result['json_path'])
        
        if parsed_data and parsed_data.get('success'):
            return jsonify({
                'success': True,
                'data': parsed_data
            })
        else:
            return jsonify({
                'success': False,
                'message': parsed_data.get('message', '解析失败') if parsed_data else '未找到可解析的文件'
            }), 500
    except Exception as e:
        logger.error(f"解析MinerU结果失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'解析失败: {str(e)}'
        }), 500


def _process_file_with_mineru_internal(file_path: str, data_id: str = None, **kwargs) -> Dict[str, Any]:
    """
    MinerU处理文件的内部函数（统一入口）
    可以被API路由和文件服务调用
    
    参数:
        file_path: 文件路径
        data_id: 数据ID
        **kwargs: 其他参数（wait, model_version等）
    
    返回:
        处理结果字典
    """
    try:
        if not file_path:
            return {'success': False, 'message': '缺少file_path参数'}
        
        # 获取可选参数（如果提供了，则使用，否则使用服务类的默认值）
        wait = kwargs.get('wait')
        model_version = kwargs.get('model_version')
        language = kwargs.get('language')
        enable_formula = kwargs.get('enable_formula')
        enable_table = kwargs.get('enable_table')
        is_ocr = kwargs.get('is_ocr')
        page_ranges = kwargs.get('page_ranges')
        extra_formats = kwargs.get('extra_formats')
        
        # 构建参数字典（只包含用户提供的参数）
        mineru_params = {}
        if wait is not None:
            mineru_params['wait'] = wait
        if model_version:
            mineru_params['model_version'] = model_version
        if language:
            mineru_params['language'] = language
        if enable_formula is not None:
            mineru_params['enable_formula'] = enable_formula
        if enable_table is not None:
            mineru_params['enable_table'] = enable_table
        if is_ocr is not None:
            mineru_params['is_ocr'] = is_ocr
        if page_ranges:
            mineru_params['page_ranges'] = page_ranges
        if extra_formats:
            mineru_params['extra_formats'] = extra_formats
        
        mineru_service = MinerUService()
        result = mineru_service.process_local_file(
            file_path=file_path,
            data_id=data_id,
            **mineru_params  # 统一使用参数传递
        )
        
        # 注意：现在使用model_json_path进行解析，不再使用markdown解析
        # parse_markdown_result方法已废弃，应使用parse_pdf_from_mineru_json
        
        return result
    except Exception as e:
        logger.error(f"MinerU处理文件失败: {str(e)}")
        return {'success': False, 'message': f'处理失败: {str(e)}'}


@files_bp.route('/mineru/process', methods=['POST'])
def process_file_with_mineru():
    """使用MinerU处理文件 - API接口"""
    try:
        if 'file_path' not in request.json:
            return jsonify({'success': False, 'message': '缺少file_path参数'}), 400
        
        file_path = request.json['file_path']
        data_id = request.json.get('data_id')
        
        # 获取所有可选参数
        kwargs = {
            'wait': request.json.get('wait'),
            'model_version': request.json.get('model_version'),
            'language': request.json.get('language'),
            'enable_formula': request.json.get('enable_formula'),
            'enable_table': request.json.get('enable_table'),
            'is_ocr': request.json.get('is_ocr'),
            'page_ranges': request.json.get('page_ranges'),
            'extra_formats': request.json.get('extra_formats')
        }
        
        # 调用内部处理函数（统一入口）
        result = _process_file_with_mineru_internal(file_path, data_id, **kwargs)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400
    except Exception as e:
        logger.error(f"MinerU API调用失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'处理失败: {str(e)}'
        }), 500




























