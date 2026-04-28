"""
MinerU API 服务
按照官方文档示例实现，用于将PDF转换为Markdown/JSON等格式
"""
import requests
import time
import os
import logging
import zipfile
import json
from typing import Dict, Any, Optional, List
from config.config import current_config

logger = logging.getLogger(__name__)


class MinerUService:
    """MinerU API服务类 - 按照官方文档示例实现"""
    
    def __init__(self):
        """初始化服务"""
        self.token = current_config.MINERU_TOKEN
        self.base_url = current_config.MINERU_BASE_URL
        self.output_dir = current_config.MINERU_OUTPUT_DIR
        self.enabled = current_config.MINERU_ENABLED
        
        if not self.enabled:
            logger.warning("MinerU服务未启用，请在配置中设置MINERU_ENABLED=True")
        
        if not self.token:
            logger.warning("MinerU Token未配置，请在环境变量中设置MINERU_TOKEN")
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头 - 按照文档格式"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
    
    def apply_upload_url(self, filename: str, data_id: Optional[str] = None, 
                       model_version: str = "vlm", **kwargs) -> Dict[str, Any]:
        """
        申请文件上传链接 - 按照文档示例
        
        参数:
            filename: 文件名
            data_id: 可选的数据ID
            model_version: 模型版本，默认vlm
            **kwargs: 其他可选参数（enable_formula, enable_table, language等）
        
        返回:
            {'success': bool, 'batch_id': str, 'upload_url': str, 'message': str}
        """
        if not self.enabled or not self.token:
            return {
                'success': False,
                'message': 'MinerU服务未启用或Token未配置'
            }
        
        url = f"{self.base_url}/file-urls/batch"
        header = self._get_headers()
        
        # 按照文档示例构建请求数据
        files_config = [{"name": filename}]
        if data_id:
            files_config[0]["data_id"] = data_id
        
        # 添加文件级别的可选参数
        if kwargs.get("is_ocr"):
            files_config[0]["is_ocr"] = kwargs["is_ocr"]
        if kwargs.get("page_ranges"):
            files_config[0]["page_ranges"] = kwargs["page_ranges"]
        
        data = {
            "files": files_config,
            "model_version": model_version
        }
        
        # 添加全局可选参数
        if kwargs.get("enable_formula") is not None:
            data["enable_formula"] = kwargs["enable_formula"]
        if kwargs.get("enable_table") is not None:
            data["enable_table"] = kwargs["enable_table"]
        if kwargs.get("language"):
            data["language"] = kwargs["language"]
        if kwargs.get("extra_formats"):
            data["extra_formats"] = kwargs["extra_formats"]
        if kwargs.get("callback"):
            data["callback"] = kwargs["callback"]
        if kwargs.get("seed"):
            data["seed"] = kwargs["seed"]
        
        try:
            response = requests.post(url, headers=header, json=data, timeout=30)
            logger.info(f"MinerU申请上传链接响应: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"MinerU响应数据: {result}")
                
                if result.get("code") == 0:
                    batch_id = result["data"]["batch_id"]
                    file_urls = result["data"]["file_urls"]
                    upload_url = file_urls[0] if file_urls else None
                    
                    logger.info(f"申请成功 - batch_id: {batch_id}")
                    
                    return {
                        'success': True,
                        'batch_id': batch_id,
                        'upload_url': upload_url,
                        'message': '申请成功'
                    }
                else:
                    error_msg = result.get("msg", "未知错误")
                    logger.error(f"申请失败: {error_msg}")
                    return {
                        'success': False,
                        'batch_id': None,
                        'upload_url': None,
                        'message': error_msg
                    }
            else:
                logger.error(f"请求失败，状态码: {response.status_code}")
                return {
                    'success': False,
                    'batch_id': None,
                    'upload_url': None,
                    'message': f'请求失败，状态码: {response.status_code}'
                }
        except Exception as e:
            logger.error(f"申请上传链接异常: {str(e)}")
            return {
                'success': False,
                'batch_id': None,
                'upload_url': None,
                'message': f'异常: {str(e)}'
            }
    
    def upload_file(self, upload_url: str, file_path: str) -> Dict[str, Any]:
        """
        上传文件到MinerU - 按照文档示例
        
        参数:
            upload_url: 上传URL
            file_path: 本地文件路径
        
        返回:
            {'success': bool, 'message': str}
        
        注意: 按照文档说明，上传文件时，无须设置 Content-Type 请求头
        """
        try:
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'message': f'文件不存在: {file_path}'
                }
            
            # 按照文档说明：上传文件时，无须设置 Content-Type 请求头
            with open(file_path, 'rb') as f:
                res_upload = requests.put(upload_url, data=f, timeout=300)
                
                if res_upload.status_code == 200:
                    logger.info(f"文件上传成功: {os.path.basename(file_path)}")
                    return {
                        'success': True,
                        'message': '文件上传成功'
                    }
                else:
                    logger.error(f"文件上传失败，状态码: {res_upload.status_code}")
                    return {
                        'success': False,
                        'message': f'上传失败，状态码: {res_upload.status_code}'
                    }
        except Exception as e:
            logger.error(f"上传文件异常: {str(e)}")
            return {
                'success': False,
                'message': f'上传异常: {str(e)}'
            }
    
    def get_batch_results(self, batch_id: str) -> Dict[str, Any]:
        """
        查询批量任务结果 - 按照文档示例
        
        参数:
            batch_id: 批量任务ID
        
        返回:
            {'success': bool, 'results': List, 'message': str}
        """
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        header = self._get_headers()
        
        try:
            res = requests.get(url, headers=header, timeout=30)
            
            if res.status_code == 200:
                result = res.json()
                
                if result.get("code") == 0:
                    data = result["data"]
                    extract_results = data.get("extract_result", [])
                    
                    return {
                        'success': True,
                        'results': extract_results,
                        'message': '查询成功'
                    }
                else:
                    error_msg = result.get("msg", "查询失败")
                    return {
                        'success': False,
                        'results': [],
                        'message': error_msg
                    }
            else:
                return {
                    'success': False,
                    'results': [],
                    'message': f'请求失败，状态码: {res.status_code}'
                }
        except Exception as e:
            logger.error(f"查询结果异常: {str(e)}")
            return {
                'success': False,
                'results': [],
                'message': f'查询异常: {str(e)}'
            }
    
    def wait_for_completion(self, batch_id: str, max_wait_time: int = 600, poll_interval: int = 5) -> Dict[str, Any]:
        """
        等待任务完成（轮询）
        
        参数:
            batch_id: 批量任务ID
            max_wait_time: 最大等待时间（秒），默认10分钟
            poll_interval: 轮询间隔（秒），默认5秒
        
        返回:
            任务结果
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed >= max_wait_time:
                return {
                    'success': False,
                    'state': 'timeout',
                    'message': f'等待超时（超过{max_wait_time}秒）'
                }
            
            query_result = self.get_batch_results(batch_id)
            
            if not query_result['success']:
                return query_result
            
            results = query_result['results']
            
            if not results:
                time.sleep(poll_interval)
                continue
            
            file_result = results[0]
            state = file_result.get("state")
            
            if state == "done":
                zip_url = file_result.get("full_zip_url")
                return {
                    'success': True,
                    'state': 'done',
                    'zip_url': zip_url,
                    'data_id': file_result.get("data_id"),
                    'message': '解析完成'
                }
            elif state == "failed":
                return {
                    'success': False,
                    'state': 'failed',
                    'err_msg': file_result.get("err_msg", "解析失败"),
                    'message': f'解析失败: {file_result.get("err_msg", "")}'
                }
            elif state in ["pending", "running", "converting", "waiting-file"]:
                if state == "running" and "extract_progress" in file_result:
                    progress = file_result["extract_progress"]
                    logger.info(
                        f"MinerU解析进度: {progress.get('extracted_pages', 0)}/"
                        f"{progress.get('total_pages', 0)} 页"
                    )
                time.sleep(poll_interval)
            else:
                return {
                    'success': False,
                    'state': 'unknown',
                    'message': f'未知状态: {state}'
                }
    
    def download_and_extract(self, zip_url: str, batch_id: str, data_id: Optional[str] = None) -> Dict[str, Any]:
        """
        下载并解压结果
        
        参数:
            zip_url: 压缩包URL
            batch_id: 批量任务ID（用于压缩包命名）
            data_id: 数据ID（用于文件夹命名，如果提供则使用data_id，否则使用batch_id）
        
        返回:
            {'success': bool, 'markdown_path': str, 'json_path': str, 'message': str}
        """
        try:
            # 下载压缩包（使用batch_id命名）
            zip_filename = f"{batch_id}.zip"
            zip_path = os.path.join(self.output_dir, zip_filename)
            
            logger.info(f"开始下载结果压缩包: {zip_url}")
            response = requests.get(zip_url, timeout=300, stream=True)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(zip_path), exist_ok=True)
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"下载完成: {zip_path}")
            
            # 解压文件（使用data_id作为文件夹名，如果提供了的话）
            folder_name = data_id if data_id else batch_id
            extract_dir = os.path.join(self.output_dir, folder_name)
            
            # 处理重名文件夹：如果文件夹已存在，添加时间戳后缀
            if os.path.exists(extract_dir):
                import time
                timestamp_suffix = int(time.time())
                folder_name = f"{folder_name}_{timestamp_suffix}"
                extract_dir = os.path.join(self.output_dir, folder_name)
                logger.warning(f"文件夹已存在，使用新名称: {extract_dir}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            logger.info(f"解压完成，保存到: {extract_dir}")
            
            # 删除原压缩包
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                    logger.info(f"已删除原压缩包: {zip_path}")
            except Exception as e:
                logger.warning(f"删除压缩包失败: {str(e)}")
            
            # 查找文件
            markdown_path = None
            json_path = None
            model_json_path = None
            content_list_json_path = None
            docx_path = None
            html_path = None
            
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith('_model.json') and not model_json_path:
                        model_json_path = file_path
                    elif file.endswith('_content_list.json') and not content_list_json_path:
                        content_list_json_path = file_path
                    elif file.endswith('.md') and not markdown_path:
                        markdown_path = file_path
                    elif file.endswith('.json') and not json_path:
                        json_path = file_path
                    elif file.endswith('.docx') and not docx_path:
                        docx_path = file_path
                    elif file.endswith('.html') and not html_path:
                        html_path = file_path
            
            return {
                'success': True,
                'markdown_path': markdown_path,
                'json_path': json_path,
                'model_json_path': model_json_path,
                'content_list_json_path': content_list_json_path,
                'docx_path': docx_path,
                'html_path': html_path,
                'zip_path': zip_path,
                'extract_dir': extract_dir,
                'message': '下载和解压成功'
            }
        except Exception as e:
            logger.error(f"下载或解压失败: {str(e)}")
            return {
                'success': False,
                'markdown_path': None,
                'json_path': None,
                'model_json_path': None,
                'content_list_json_path': None,
                'message': f'失败: {str(e)}'
            }
    
    @staticmethod
    def get_default_params() -> Dict[str, Any]:
        """
        获取默认参数（统一管理，所有调用都使用这个）
        
        返回:
            默认参数字典
        """
        return {
            'model_version': 'vlm',      # vlm模型，对中文支持好
            'language': 'ch',            # 中文文档
            'enable_formula': True,      # 开启公式识别（论文通常有公式）
            'enable_table': True,        # 开启表格识别（论文通常有表格）
            'is_ocr': False,             # 默认不开启OCR（普通PDF不需要）
            'wait': False                # 默认异步处理（不阻塞）
        }
    
    def process_local_file(self, file_path: str, data_id: Optional[str] = None, 
                          wait: Optional[bool] = None, **kwargs) -> Dict[str, Any]:
        """
        处理本地文件的完整流程
        
        参数:
            file_path: 本地文件路径
            data_id: 可选的数据ID
            wait: 是否等待完成（False则异步，返回batch_id）
            **kwargs: 其他参数（model_version, is_ocr, enable_formula等）
        
        返回:
            处理结果
        """
        if not self.enabled or not self.token:
            return {
                'success': False,
                'message': 'MinerU服务未启用或Token未配置'
            }
        
        filename = os.path.basename(file_path)
        
        # 获取默认参数并合并用户参数
        default_params = self.get_default_params()
        
        # 如果wait未指定，使用默认值
        if wait is None:
            wait = default_params['wait']
        
        # 合并参数：用户参数 > 默认参数
        final_params = {**default_params, **kwargs}
        final_params['wait'] = wait
        
        # 步骤1: 申请上传链接
        apply_result = self.apply_upload_url(filename, data_id, **final_params)
        if not apply_result['success']:
            return apply_result
        
        batch_id = apply_result['batch_id']
        upload_url = apply_result['upload_url']
        
        # 步骤2: 上传文件
        upload_result = self.upload_file(upload_url, file_path)
        if not upload_result['success']:
            return upload_result
        
        # 如果不需要等待，直接返回batch_id
        if not wait:
            return {
                'success': True,
                'batch_id': batch_id,
                'message': '文件已上传，系统将自动提交解析任务'
            }
        
        # 步骤3: 等待完成
        wait_result = self.wait_for_completion(batch_id)
        if not wait_result['success'] or wait_result.get('state') != 'done':
            return wait_result
        
        # 步骤4: 下载并解压（使用data_id作为文件夹名）
        zip_url = wait_result['zip_url']
        # 从结果中获取data_id，如果没有则使用传入的data_id
        result_data_id = wait_result.get('data_id') or data_id
        extract_result = self.download_and_extract(zip_url, batch_id, data_id=result_data_id)
        
        return extract_result
    
    def parse_markdown_result(self, markdown_path: str) -> Dict[str, Any]:
        """
        解析Markdown结果，使用现有的提取函数
        
        参数:
            markdown_path: Markdown文件路径
        
        返回:
            提取的论文信息
        """
        try:
            with open(markdown_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # 使用现有的提取函数
            from services.pdf_parser import (
                extract_doi,
                extract_issue_info,
                extract_title_authors_with_fontsize,
                extract_citation,
                extract_corresponding,
                normalize_authors_for_display,
                first_author_from_authors
            )
            
            text = markdown_content
            doi = extract_doi(text)
            issue = extract_issue_info(text)
            title, authors_line = extract_title_authors_with_fontsize(text, None)
            authors_display = normalize_authors_for_display(authors_line) if authors_line else ""
            first_author = first_author_from_authors(authors_line) if authors_line else ""
            citation = extract_citation(text)
            corresponding = extract_corresponding(text, authors_display)
            
            # 提取摘要和关键词（简单实现，可以从Markdown结构中提取）
            abstract = ""
            keywords = ""
            
            # 尝试从Markdown中提取摘要（查找## Abstract或**Abstract**等标记）
            lines = markdown_content.split('\n')
            in_abstract = False
            in_keywords = False
            
            for i, line in enumerate(lines):
                if 'abstract' in line.lower() and ('##' in line or '**' in line):
                    in_abstract = True
                    continue
                elif 'keyword' in line.lower() and ('##' in line or '**' in line):
                    in_abstract = False
                    in_keywords = True
                    continue
                elif in_abstract and line.strip():
                    if line.strip().startswith('##') or line.strip().startswith('#'):
                        in_abstract = False
                    else:
                        abstract += line.strip() + ' '
                elif in_keywords and line.strip():
                    if line.strip().startswith('##') or line.strip().startswith('#'):
                        in_keywords = False
                    else:
                        keywords += line.strip() + ' '
            
            return {
                'success': True,
                'title': title,
                'authors': authors_display,
                'first_author': first_author,
                'corresponding': corresponding,
                'doi': doi,
                'issue': issue,
                'citation': citation,
                'abstract': abstract.strip(),
                'keywords': keywords.strip(),
                'full_text': markdown_content
            }
        except Exception as e:
            logger.error(f"解析Markdown结果失败: {str(e)}")
            return {
                'success': False,
                'message': f'解析失败: {str(e)}'
            }
    
    def parse_json_result(self, json_path: str) -> Dict[str, Any]:
        """
        解析JSON结果
        
        参数:
            json_path: JSON文件路径
        
        返回:
            提取的论文信息
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {
                'success': True,
                'title': '',
                'authors': '',
                'doi': '',
                'abstract': '',
                'keywords': '',
                'full_text': ''
            }
            
            # 方式1: 如果JSON有metadata字段
            if 'metadata' in data:
                metadata = data['metadata']
                result['title'] = metadata.get('title', '')
                result['authors'] = metadata.get('authors', '')
                result['doi'] = metadata.get('doi', '')
                result['abstract'] = metadata.get('abstract', '')
                result['keywords'] = metadata.get('keywords', '')
            
            # 方式2: 从段落中提取
            full_text_parts = []
            for page in data.get('pages', []):
                for para in page.get('paragraphs', []):
                    text = para.get('text', '')
                    para_type = para.get('type', '')
                    
                    if para_type == 'title' and not result['title']:
                        result['title'] = text
                    elif para_type == 'author' and not result['authors']:
                        result['authors'] = text
                    elif para_type == 'abstract':
                        result['abstract'] += text + ' '
                    elif para_type == 'keyword':
                        result['keywords'] += text + ' '
                    
                    full_text_parts.append(text)
            
            result['full_text'] = '\n'.join(full_text_parts)
            
            return result
        except Exception as e:
            logger.error(f"解析JSON结果失败: {str(e)}")
            return {
                'success': False,
                'message': f'解析失败: {str(e)}'
            }

