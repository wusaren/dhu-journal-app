import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from werkzeug.utils import secure_filename
from models import Journal, JournalTemplate, db
import logging

logger = logging.getLogger(__name__)

# 系统字段定义（用于模糊匹配）
SYSTEM_FIELD_MAPPINGS = {
    'manuscript_id': {
        'keywords': ['稿件号', '稿件编号', 'manuscript', 'id', '编号'],
        'label': '稿件号'
    },
    'title': {
        'keywords': ['标题', '题目', 'title', '论文标题'],
        'label': '标题'
    },
    'chinese_title': {
        'keywords': ['中文标题', '中文题目', 'chinese title'],
        'label': '中文标题'
    },
    'authors': {
        'keywords': ['作者', 'author', 'authors', '作者列表'],
        'label': '作者'
    },
    'chinese_authors': {
        'keywords': ['中文作者', 'chinese author', 'chinese authors'],
        'label': '中文作者'
    },
    'first_author': {
        'keywords': ['一作', '第一作者', 'first author', 'first'],
        'label': '一作'
    },
    'corresponding': {
        'keywords': ['通讯', '通讯作者', 'corresponding', 'corresponding author'],
        'label': '通讯'
    },
    'doi': {
        'keywords': ['doi', 'DOI'],
        'label': 'DOI'
    },
    'pdf_pages': {
        'keywords': ['页数', 'pages', '页', '总页数'],
        'label': '页数'
    },
    'issue': {
        'keywords': ['刊期', '期', 'issue', '期刊期号'],
        'label': '刊期'
    },
    'is_dhu': {
        'keywords': ['是否东华大学', '东华大学', 'is_dhu', 'dhu'],
        'label': '是否东华大学'
    },
    'page_start': {
        'keywords': ['起始页码', '开始页码', 'start page', 'page start'],
        'label': '起始页码'
    },
    'page_end': {
        'keywords': ['结束页码', '终止页码', 'end page', 'page end'],
        'label': '结束页码'
    },
}

def extract_headers_from_excel(file_path: str) -> List[str]:
    """
    从Excel文件中提取表头（自动跳过空行，查找第一个有内容的行）
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        表头列表
    """
    try:
        wb = load_workbook(file_path, data_only=True)
        ws = wb.active
        
        # 从第一行开始，向下查找第一个有内容的行作为表头
        # 最多查找前10行，避免性能问题
        max_search_rows = min(10, ws.max_row)
        header_row = None
        
        for row_idx in range(1, max_search_rows + 1):
            row = ws[row_idx]
            # 检查这一行是否有内容（至少有一个非空单元格）
            has_content = False
            for cell in row:
                if cell.value and str(cell.value).strip():
                    has_content = True
                    break
            
            if has_content:
                header_row = row_idx
                break
        
        if header_row is None:
            logger.warning(f"Excel文件前{max_search_rows}行都没有内容，无法提取表头")
            return []
        
        # 提取表头行的内容
        headers = []
        for cell in ws[header_row]:
            header = str(cell.value).strip() if cell.value else ''
            if header:
                headers.append(header)
        
        logger.info(f"从Excel文件第{header_row}行提取到 {len(headers)} 个表头: {headers}")
        return headers
    
    except Exception as e:
        logger.error(f"提取Excel表头失败: {str(e)}")
        raise Exception(f"提取Excel表头失败: {str(e)}")

def fuzzy_match_header(header: str) -> Optional[Tuple[str, str]]:
    """
    模糊匹配表头到系统字段
    
    Args:
        header: 表头文本
        
    Returns:
        (system_key, label) 如果匹配成功，否则返回 None
    """
    header_lower = header.lower().strip()
    
    # 精确匹配
    for system_key, field_info in SYSTEM_FIELD_MAPPINGS.items():
        if header == field_info['label']:
            logger.debug(f"精确匹配: '{header}' -> {system_key}")
            return (system_key, field_info['label'])
    
    # 模糊匹配：双向检查（表头包含关键词 或 关键词包含表头）
    best_match = None
    best_score = 0
    
    for system_key, field_info in SYSTEM_FIELD_MAPPINGS.items():
        for keyword in field_info['keywords']:
            keyword_lower = keyword.lower()
            
            # 双向匹配：
            # 1. 表头包含关键词（如"稿件编号"包含"稿件"）
            # 2. 关键词包含表头（如"稿件号"包含"稿件"）
            if keyword_lower in header_lower or header_lower in keyword_lower:
                # 匹配度计算：
                # - 如果完全匹配（表头=关键词），分数最高（1.0）
                # - 否则根据共同部分的长度计算
                if header_lower == keyword_lower:
                    score = 1.0
                else:
                    # 计算共同部分的长度比例
                    common_length = min(len(header_lower), len(keyword_lower))
                    total_length = max(len(header_lower), len(keyword_lower))
                    score = common_length / total_length if total_length > 0 else 0
                
                if score > best_score:
                    best_score = score
                    best_match = (system_key, field_info['label'])
    
    if best_match:
        logger.debug(f"模糊匹配: '{header}' -> {best_match[0]} ({best_match[1]}, 匹配度: {best_score:.2f})")
        return best_match
    
    logger.debug(f"未匹配: '{header}'")
    return None

def match_headers(headers: List[str]) -> List[Dict]:
    """
    匹配表头列表到系统字段
    
    Args:
        headers: 表头列表
        
    Returns:
        匹配结果列表，格式：
        [
            {
                'template_header': '稿件号',
                'system_key': 'manuscript_id',
                'system_label': '稿件号',
                'order': 1,
                'is_custom': False,
                'matched': True
            },
            {
                'template_header': '备注',
                'system_key': None,
                'system_label': None,
                'order': 2,
                'is_custom': True,
                'matched': False
            }
        ]
    """
    matched_headers = []
    
    for idx, header in enumerate(headers):
        match_result = fuzzy_match_header(header)
        
        if match_result:
            system_key, system_label = match_result
            matched_headers.append({
                'template_header': header,
                'system_key': system_key,
                'system_label': system_label,
                'order': idx + 1,
                'is_custom': False,
                'matched': True
            })
        else:
            # 未匹配的表头，作为自定义字段
            matched_headers.append({
                'template_header': header,
                'system_key': None,
                'system_label': None,
                'order': idx + 1,
                'is_custom': True,
                'matched': False
            })
    
    logger.info(f"表头匹配完成: {len([h for h in matched_headers if h['matched']])} 个匹配, {len([h for h in matched_headers if not h['matched']])} 个自定义")
    return matched_headers

def get_available_system_fields() -> List[Dict]:
    """
    获取所有可用的系统字段列表（用于用户添加字段）
    
    Returns:
        系统字段列表
    """
    fields = []
    for system_key, field_info in SYSTEM_FIELD_MAPPINGS.items():
        fields.append({
            'key': system_key,
            'label': field_info['label'],
            'keywords': field_info['keywords']
        })
    return fields

class TemplateService:
    """模板服务类"""
    
    def upload_template(self, journal_id: int, file) -> Dict:
        """
        上传模板文件并识别表头
        
        Args:
            journal_id: 期刊ID
            file: 上传的文件对象
            
        Returns:
            包含headers和template_id的字典
        """
        try:
            # 检查期刊是否存在
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 检查文件类型
            if not file.filename.endswith(('.xlsx', '.xls')):
                return {'success': False, 'message': '只支持Excel文件（.xlsx, .xls）', 'status_code': 400}
            
            # 保存模板文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"template_{journal_id}_{timestamp}_{secure_filename(file.filename)}"
            template_dir = os.path.join('uploads', 'templates')
            os.makedirs(template_dir, exist_ok=True)
            file_path = os.path.join(template_dir, filename)
            file.save(file_path)
            
            logger.info(f"模板文件已保存: {file_path}")
            
            # 提取表头
            headers = extract_headers_from_excel(file_path)
            if not headers:
                return {'success': False, 'message': '无法从Excel文件中提取表头，请确保文件前10行中有包含表头的行', 'status_code': 400}
            
            # 匹配表头
            matched_headers = match_headers(headers)
            
            # 保存或更新模板记录
            template = JournalTemplate.query.filter_by(journal_id=journal_id).first()
            if template:
                # 更新现有模板
                template.template_file_path = file_path
                template.column_mapping = matched_headers
                template.updated_at = datetime.utcnow()
            else:
                # 创建新模板
                template = JournalTemplate(
                    journal_id=journal_id,
                    template_file_path=file_path,
                    column_mapping=matched_headers
                )
                db.session.add(template)
            
            db.session.commit()
            
            return {
                'success': True,
                'message': '模板上传成功',
                'data': {
                    'headers': matched_headers,
                    'template_id': template.id
                }
            }
        
        except Exception as e:
            logger.error(f"模板上传错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'模板上传失败: {str(e)}', 'status_code': 500}
    
    def get_template_headers(self, journal_id: int) -> Dict:
        """
        获取模板表头识别结果
        
        Args:
            journal_id: 期刊ID
            
        Returns:
            包含headers的字典
        """
        try:
            template = JournalTemplate.query.filter_by(journal_id=journal_id).first()
            if not template:
                # 没有模板是正常状态，返回200但success为False
                return {
                    'success': False,
                    'message': '该期刊尚未上传模板',
                    'status_code': 200,
                    'data': {'has_template': False}
                }
            
            return {
                'success': True,
                'data': {
                    'has_template': True,
                    'headers': template.column_mapping or [],
                    'template_file_path': template.template_file_path
                }
            }
        
        except Exception as e:
            logger.error(f"获取模板表头错误: {str(e)}")
            return {'success': False, 'message': f'获取模板表头失败: {str(e)}', 'status_code': 500}
    
    def save_template_mapping(self, journal_id: int, column_mapping: List[Dict]) -> Dict:
        """
        保存表头映射配置
        
        Args:
            journal_id: 期刊ID
            column_mapping: 表头映射配置列表
            
        Returns:
            操作结果
        """
        try:
            template = JournalTemplate.query.filter_by(journal_id=journal_id).first()
            if not template:
                return {'success': False, 'message': '该期刊尚未上传模板，请先上传模板', 'status_code': 404}
            
            # 更新映射配置
            template.column_mapping = column_mapping
            template.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {
                'success': True,
                'message': '表头映射配置保存成功'
            }
        
        except Exception as e:
            logger.error(f"保存表头映射配置错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'保存配置失败: {str(e)}', 'status_code': 500}
    
    def get_template(self, journal_id: int) -> Dict:
        """
        获取当前模板配置
        
        Args:
            journal_id: 期刊ID
            
        Returns:
            模板配置信息
        """
        try:
            template = JournalTemplate.query.filter_by(journal_id=journal_id).first()
            if not template:
                # 没有模板是正常状态，返回200但success为False
                return {
                    'success': False,
                    'message': '该期刊尚未上传模板',
                    'status_code': 200,
                    'data': {'has_template': False}
                }
            
            return {
                'success': True,
                'data': {
                    'has_template': True,
                    'template': {
                        'id': template.id,
                        'template_file_path': template.template_file_path,
                        'column_mapping': template.column_mapping,
                        'created_at': template.created_at.isoformat() if template.created_at else None,
                        'updated_at': template.updated_at.isoformat() if template.updated_at else None
                    }
                }
            }
        
        except Exception as e:
            logger.error(f"获取模板配置错误: {str(e)}")
            return {'success': False, 'message': f'获取模板配置失败: {str(e)}', 'status_code': 500}
    
    def delete_template(self, journal_id: int) -> Dict:
        """
        删除模板
        
        Args:
            journal_id: 期刊ID
            
        Returns:
            操作结果
        """
        try:
            template = JournalTemplate.query.filter_by(journal_id=journal_id).first()
            if not template:
                return {'success': False, 'message': '该期刊没有模板，无需删除', 'status_code': 404}
            
            # 可选：删除模板文件（如果文件存在）
            template_file_path = template.template_file_path
            if template_file_path and os.path.exists(template_file_path):
                try:
                    os.remove(template_file_path)
                    logger.info(f"已删除模板文件: {template_file_path}")
                except Exception as e:
                    logger.warning(f"删除模板文件失败（继续删除数据库记录）: {str(e)}")
            
            # 删除数据库记录
            db.session.delete(template)
            db.session.commit()
            
            logger.info(f"已删除期刊 {journal_id} 的模板")
            return {
                'success': True,
                'message': '模板删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除模板错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'删除模板失败: {str(e)}', 'status_code': 500}
    
    def get_system_fields(self) -> Dict:
        """
        获取所有可用的系统字段列表
        
        Returns:
            系统字段列表
        """
        try:
            fields = get_available_system_fields()
            return {
                'success': True,
                'data': {'fields': fields}
            }
        except Exception as e:
            logger.error(f"获取系统字段列表错误: {str(e)}")
            return {'success': False, 'message': f'获取系统字段列表失败: {str(e)}', 'status_code': 500}

def copy_cell_style(source_cell, target_cell):
    """
    复制单元格样式（字体、颜色、边框、对齐）
    
    Args:
        source_cell: 源单元格
        target_cell: 目标单元格
    """
    try:
        # 复制字体
        if source_cell.font:
            target_cell.font = Font(
                name=source_cell.font.name,
                size=source_cell.font.size,
                bold=source_cell.font.bold,
                italic=source_cell.font.italic,
                color=source_cell.font.color
            )
        
        # 复制填充（背景色）
        if source_cell.fill and source_cell.fill.fill_type:
            target_cell.fill = PatternFill(
                fill_type=source_cell.fill.fill_type,
                start_color=source_cell.fill.start_color,
                end_color=source_cell.fill.end_color
            )
        
        # 复制边框
        if source_cell.border:
            target_cell.border = Border(
                left=source_cell.border.left,
                right=source_cell.border.right,
                top=source_cell.border.top,
                bottom=source_cell.border.bottom
            )
        
        # 复制对齐
        if source_cell.alignment:
            target_cell.alignment = Alignment(
                horizontal=source_cell.alignment.horizontal,
                vertical=source_cell.alignment.vertical,
                wrap_text=source_cell.alignment.wrap_text
            )
    
    except Exception as e:
        logger.warning(f"复制单元格样式失败: {str(e)}")
        # 如果复制失败，至少设置基本样式
        target_cell.font = Font(name='Arial', size=11)
        target_cell.alignment = Alignment(horizontal='left', vertical='center')

