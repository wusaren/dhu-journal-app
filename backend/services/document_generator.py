import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional, Dict
import logging

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from openpyxl import Workbook, load_workbook

logger = logging.getLogger(__name__)

# 默认配置文件路径
DEFAULT_CONFIG_FILE = Path(__file__).parent.parent / 'configs' / 'default_stats_columns.json'
DEFAULT_TUIWEN_CONFIG_FILE = Path(__file__).parent.parent / 'configs' / 'default_tuiwen_fields.json'

def load_default_columns_config() -> List[Dict]:
    """
    从JSON文件加载默认列配置
    如果文件不存在或加载失败，返回硬编码的默认配置作为后备
    
    Returns:
        列配置列表，格式: [{'key': 'manuscript_id', 'order': 1}, ...]
    """
    try:
        if DEFAULT_CONFIG_FILE.exists():
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                columns = config_data.get('columns', [])
                if columns:
                    logger.info(f"从配置文件加载了默认列配置: {len(columns)} 列")
                    return columns
        
        logger.warning(f"默认配置文件不存在或为空，使用硬编码默认配置: {DEFAULT_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"加载默认列配置失败: {str(e)}，使用硬编码默认配置")
    
    # 后备硬编码配置
    return [
        {'key': 'manuscript_id', 'order': 1},
        {'key': 'pdf_pages', 'order': 2},
        {'key': 'first_author', 'order': 3},
        {'key': 'corresponding', 'order': 4},
        {'key': 'issue', 'order': 5},
        {'key': 'is_dhu', 'order': 6},
    ]

def load_default_tuiwen_fields_config() -> List[Dict]:
    """
    从JSON文件加载默认推文字段配置
    如果文件不存在或加载失败，返回硬编码的默认配置作为后备
    
    Returns:
        字段配置列表，格式: [{'field': 'title', 'label': '标题', 'order': 1}, ...]
    """
    try:
        if DEFAULT_TUIWEN_CONFIG_FILE.exists():
            with open(DEFAULT_TUIWEN_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                fields = config_data.get('fields', [])
                if fields:
                    logger.info(f"从配置文件加载了默认推文字段配置: {len(fields)} 个字段")
                    return fields
        
        logger.warning(f"默认推文配置文件不存在或为空，使用硬编码默认配置: {DEFAULT_TUIWEN_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"加载默认推文字段配置失败: {str(e)}，使用硬编码默认配置")
    
    # 后备硬编码配置
    return [
        {'field': 'chinese_title', 'label': '中文标题', 'required': False, 'order': 1},
        {'field': 'chinese_authors', 'label': '中文作者', 'required': False, 'order': 2},
        {'field': 'second_image', 'label': '论文配图', 'required': False, 'order': 3},
        {'field': 'title', 'label': '标题', 'required': True, 'order': 4},
        {'field': 'authors', 'label': '作者', 'required': True, 'order': 5},
        {'field': 'doi', 'label': 'DOI', 'required': False, 'order': 6},
        {'field': 'citation', 'label': '引用信息', 'required': True, 'order': 7},
        {'field': 'first_image', 'label': '作者说链接/OSID', 'required': False, 'order': 8},
    ]

def _get(a: Any, key: str):
    """获取对象属性，兼容dict和object - 完全照搬参考代码"""
    if isinstance(a, dict): 
        return a.get(key)
    return getattr(a, key)

def generate_toc_docx(papers: List[Any], journal: Any) -> str:
    """
    生成目录Word文档 - 导出期刊内所有论文
    """
    try:
        # 创建Word文档
        doc = Document()
        
        # 设置样式
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 添加期刊标题
        title_para = doc.add_paragraph()
        title_run = title_para.runs[0] if title_para.runs else title_para.add_run()
        title_run.text = f"{journal.title} - {journal.issue}"
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        
        # 添加空行
        doc.add_paragraph()
        
        # 按页码排序
        items = sorted([a for a in papers if _get(a, 'page_start') is not None], 
                      key=lambda x: _get(x, 'page_start'))
        
        # 添加目录内容
        for i, a in enumerate(items, 1):
            # 论文标题和页码
            doc.add_paragraph(f"{_get(a,'page_start')} {_get(a,'title') or ''}")
            # 作者信息
            doc.add_paragraph(_get(a, 'authors') or '')
            # 空行分隔
            if i < len(items):
                doc.add_paragraph()
        
        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"目录_{journal.issue}_{timestamp}.docx"
        output_path = os.path.join('uploads', filename)
        
        # 确保目录存在
        os.makedirs('uploads', exist_ok=True)
        
        doc.save(output_path)
        logger.info(f"目录文档已生成: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"生成目录文档失败: {str(e)}")
        raise Exception(f"生成目录文档失败: {str(e)}")

def generate_excel_stats(articles, journal, columns_config=None) -> str:
    """
    生成统计表Excel - 导出期刊内所有论文的统计信息
    支持自定义列配置
    
    Args:
        articles: 论文列表
        journal: 期刊对象
        columns_config: 列配置列表，格式: [{'key': 'manuscript_id', 'order': 1}, ...]
                       如果为None，使用默认配置
    """
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = '期刊统计表'
        
        # 如果没有提供列配置，从JSON文件加载默认配置
        if not columns_config:
            columns_config = load_default_columns_config()
        
        # 按order排序
        columns_config = sorted(columns_config, key=lambda x: x.get('order', 999))
        
        # 定义所有可用列的映射（key -> 显示标签和数据获取函数）
        column_definitions = {
            'manuscript_id': {
                'label': '稿件号',
                'get_value': lambda a: _get(a, 'manuscript_id') or ''
            },
            'pdf_pages': {
                'label': '页数',
                'get_value': lambda a: _get(a, 'pdf_pages') or 0
            },
            'first_author': {
                'label': '一作',
                'get_value': lambda a: _get(a, 'first_author') or ''
            },
            'corresponding': {
                'label': '通讯',
                'get_value': lambda a: _get(a, 'corresponding') or ''
            },
            'authors': {
                'label': '作者',
                'get_value': lambda a: _get(a, 'authors') or ''
            },
            'issue': {
                'label': '刊期',
                'get_value': lambda a: _get(a, 'issue') or ''
            },
            'is_dhu': {
                'label': '是否东华大学',
                'get_value': lambda a: '是' if _get(a, 'is_dhu') else '否'
            },
            'title': {
                'label': '标题',
                'get_value': lambda a: _get(a, 'title') or ''
            },
            'chinese_title': {
                'label': '中文标题',
                'get_value': lambda a: _get(a, 'chinese_title') or ''
            },
            'chinese_authors': {
                'label': '中文作者',
                'get_value': lambda a: _get(a, 'chinese_authors') or ''
            },
            'doi': {
                'label': 'DOI',
                'get_value': lambda a: _get(a, 'doi') or ''
            },
            'page_start': {
                'label': '起始页码',
                'get_value': lambda a: _get(a, 'page_start') or ''
            },
            'page_end': {
                'label': '结束页码',
                'get_value': lambda a: _get(a, 'page_end') or ''
            },
        }
        
        # 生成表头（只包含配置中存在的列）
        valid_columns = []
        for col_config in columns_config:
            key = col_config.get('key')
            if key in column_definitions:
                valid_columns.append({
                    'key': key,
                    'label': column_definitions[key]['label'],
                    'get_value': column_definitions[key]['get_value']
                })
        
        headers = [col['label'] for col in valid_columns]
        ws.append(headers)
        
        # 添加所有论文数据
        r = 2  # 从第2行开始（第1行是表头）
        for a in articles:
            col_idx = 1
            for col in valid_columns:
                value = col['get_value'](a)
                ws.cell(row=r, column=col_idx, value=value)
                col_idx += 1
            r += 1

        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"统计表_{journal.issue}_{timestamp}.xlsx"
        output_path = os.path.join('uploads', filename)
        
        os.makedirs('uploads', exist_ok=True)
        wb.save(output_path)
        
        logger.info(f"统计表已生成: {output_path}")
        logger.info(f"使用的列配置: {[col['key'] for col in valid_columns]}")
        
        # 记录生成的数据用于调试
        debug_data = []
        for a in articles:
            row_data = {}
            for col in valid_columns:
                row_data[col['label']] = col['get_value'](a)
            debug_data.append(row_data)
        logger.info(f"生成的数据（前3条）: {debug_data[:3]}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"生成统计表Excel失败: {str(e)}")
        raise Exception(f"生成统计表Excel失败: {str(e)}")

def generate_excel_stats_from_template(articles, journal, template_file_path: str, column_mapping: List[Dict]) -> str:
    """
    基于模板生成统计表Excel
    
    Args:
        articles: 论文列表
        journal: 期刊对象
        template_file_path: 模板文件路径
        column_mapping: 列映射配置，格式: [
            {'template_header': '稿件号', 'system_key': 'manuscript_id', 'order': 1, 'is_custom': False},
            ...
        ]
    """
    try:
        from services.template_service import TemplateService
        
        # 加载模板文件
        wb = load_workbook(template_file_path)
        ws = wb.active
        
        # 找到表头行（第一个有内容的行）
        template_service = TemplateService()
        headers = template_service.extract_headers_from_excel(template_file_path)
        
        if not headers:
            raise Exception("无法从模板文件中提取表头")
        
        # 找到表头行号
        header_row = None
        for row_idx in range(1, min(10, ws.max_row + 1)):
            row = ws[row_idx]
            has_content = False
            for cell in row:
                if cell.value and str(cell.value).strip():
                    has_content = True
                    break
            if has_content:
                header_row = row_idx
                break
        
        if header_row is None:
            raise Exception("无法找到表头行")
        
        # 按 order 排序 column_mapping
        column_mapping = sorted(column_mapping, key=lambda x: x.get('order', 999))

        # 需要保留的表头集合
        mapped_headers = set()
        for mapping in column_mapping:
            template_header = mapping.get('template_header')
            if template_header:
                mapped_headers.add(str(template_header).strip())

        # 删除模板中不在映射里的列，避免表头残留
        columns_to_remove = []
        for col_idx, cell in enumerate(ws[header_row], start=1):
            header_text = str(cell.value).strip() if cell.value else ''
            if header_text and header_text not in mapped_headers:
                columns_to_remove.append(col_idx)
        for col_idx in sorted(columns_to_remove, reverse=True):
            ws.delete_cols(col_idx)

        # 删除后重新建立表头映射，并记录最后一个有内容的列
        header_to_col = {}
        last_content_col = 0
        for col_idx, cell in enumerate(ws[header_row], start=1):
            header_text = str(cell.value).strip() if cell.value else ''
            if header_text:
                header_to_col[header_text] = col_idx
                last_content_col = col_idx  # 更新最后一个有内容的列
        
        # 清理最后一列之后的空列（避免表头最右端出现多余的空格和边框）
        max_col = ws.max_column
        if max_col > last_content_col:
            # 删除最后一列之后的所有空列
            cols_to_remove = list(range(last_content_col + 1, max_col + 1))
            for col_idx in sorted(cols_to_remove, reverse=True):
                ws.delete_cols(col_idx)
            logger.info(f"清理了 {len(cols_to_remove)} 个空列（从第 {last_content_col + 1} 列到第 {max_col} 列）")

        # 保存原始表头样式（用于新列）
        # 使用识别到的第一个字段的样式
        source_header_cell = None
        for cell in ws[header_row]:
            if cell.value and str(cell.value).strip():
                source_header_cell = cell
                break
        
        # 检查 column_mapping 中是否有模板文件中不存在的字段，如果有则添加
        # 从最后一个有内容的列之后开始添加，避免中间有空列
        next_col = last_content_col + 1
        for mapping in column_mapping:
            template_header = mapping.get('template_header')
            if template_header and template_header not in header_to_col:
                # 在表头行添加新列
                cell = ws.cell(row=header_row, column=next_col)
                cell.value = template_header
                # 复制表头行的样式（如果有）
                if source_header_cell:
                    try:
                        if source_header_cell.font:
                            from openpyxl.styles import Font
                            cell.font = Font(
                                name=source_header_cell.font.name,
                                size=source_header_cell.font.size,
                                bold=source_header_cell.font.bold,
                                color=source_header_cell.font.color
                            )
                        if source_header_cell.fill:
                            from openpyxl.styles import PatternFill
                            cell.fill = PatternFill(
                                start_color=source_header_cell.fill.start_color,
                                end_color=source_header_cell.fill.end_color,
                                fill_type=source_header_cell.fill.fill_type
                            )
                        if source_header_cell.alignment:
                            from openpyxl.styles import Alignment
                            cell.alignment = Alignment(
                                horizontal=source_header_cell.alignment.horizontal,
                                vertical=source_header_cell.alignment.vertical
                            )
                        # 复制边框样式，直接复制第一个识别到的字段的边框样式
                        if source_header_cell.border:
                            from openpyxl.styles import Border
                            from copy import deepcopy
                            source_border = source_header_cell.border
                            cell.border = Border(
                                left=deepcopy(source_border.left) if source_border.left else None,
                                right=deepcopy(source_border.right) if source_border.right else None,
                                top=deepcopy(source_border.top) if source_border.top else None,
                                bottom=deepcopy(source_border.bottom) if source_border.bottom else None
                            )
                    except Exception as e:
                        logger.warning(f"复制表头样式失败: {str(e)}")
                header_to_col[template_header] = next_col
                next_col += 1
                logger.info(f"添加新列到模板: {template_header} (列 {header_to_col[template_header]})")
        
        # 添加完所有新列后，再次清理最后一列之后的空列
        final_last_col = 0
        for col_idx, cell in enumerate(ws[header_row], start=1):
            header_text = str(cell.value).strip() if cell.value else ''
            if header_text:
                final_last_col = col_idx
        final_max_col = ws.max_column
        if final_max_col > final_last_col:
            cols_to_remove = list(range(final_last_col + 1, final_max_col + 1))
            for col_idx in sorted(cols_to_remove, reverse=True):
                ws.delete_cols(col_idx)
            logger.info(f"最终清理了 {len(cols_to_remove)} 个空列（从第 {final_last_col + 1} 列到第 {final_max_col} 列）")
        
        # 删除表头行之后的所有数据行（保留表头）
        data_start_row = header_row + 1
        if ws.max_row >= data_start_row:
            ws.delete_rows(data_start_row, ws.max_row - header_row)
        
        # 定义所有可用列的映射
        column_definitions = {
            'manuscript_id': lambda a: _get(a, 'manuscript_id') or '',
            'pdf_pages': lambda a: _get(a, 'pdf_pages') or 0,
            'first_author': lambda a: _get(a, 'first_author') or '',
            'corresponding': lambda a: _get(a, 'corresponding') or '',
            'authors': lambda a: _get(a, 'authors') or '',
            'issue': lambda a: _get(a, 'issue') or '',
            'is_dhu': lambda a: '是' if _get(a, 'is_dhu') else '否',
            'title': lambda a: _get(a, 'title') or '',
            'chinese_title': lambda a: _get(a, 'chinese_title') or '',
            'chinese_authors': lambda a: _get(a, 'chinese_authors') or '',
            'doi': lambda a: _get(a, 'doi') or '',
            'page_start': lambda a: _get(a, 'page_start') or '',
            'page_end': lambda a: _get(a, 'page_end') or '',
        }
        
        # 填充数据
        for article_idx, article in enumerate(articles, start=0):
            row_num = data_start_row + article_idx
            
            for mapping in column_mapping:
                template_header = mapping.get('template_header')
                system_key = mapping.get('system_key')
                col_idx = header_to_col.get(template_header)
                
                if col_idx:
                    cell = ws.cell(row=row_num, column=col_idx)
                    
                    if system_key and system_key in column_definitions:
                        value = column_definitions[system_key](article)
                        cell.value = value
                    elif mapping.get('is_custom', False):
                        cell.value = ''
                    # 数据行保持默认格式，不复制表头样式
        
        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"统计表_{journal.issue}_{timestamp}.xlsx"
        output_path = os.path.join('uploads', filename)
        
        os.makedirs('uploads', exist_ok=True)
        wb.save(output_path)
        
        logger.info(f"基于模板生成统计表: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"基于模板生成统计表Excel失败: {str(e)}")
        raise Exception(f"基于模板生成统计表Excel失败: {str(e)}")

def get_local_image_path(image_path: str, temp_dir: str, mineru_folder: str = None) -> Optional[str]:
    """
    获取本地图片路径，支持以下查找策略（按优先级）：
    1. 如果传入了 mineru_folder，直接拼接 mineru_output/{mineru_folder}/{image_path}
    2. 如果图片路径是绝对路径且存在，直接返回
    3. 如果是相对路径，尝试多个可能的查找位置（保留原有兼容逻辑）

    返回: 本地图片路径，如果图片不存在则返回None
    """
    try:
        if not image_path:
            return None

        # 策略1：使用 mineru_folder 直接拼接（最优路径）
        if mineru_folder and image_path:
            current_file = os.path.abspath(__file__)
            backend_dir = os.path.dirname(os.path.dirname(current_file))
            direct_path = os.path.join(backend_dir, 'mineru_output', mineru_folder, image_path)
            if os.path.exists(direct_path):
                logger.info(f"本地图片存在（mineru_folder路径）: {direct_path}")
                return direct_path

        # 策略2：直接使用原始路径（绝对路径）
        if os.path.exists(image_path):
            logger.info(f"本地图片存在（原始路径）: {image_path}")
            return image_path

        # 策略3：相对路径查找（兼容旧数据）
        if not os.path.isabs(image_path):
            current_file = os.path.abspath(__file__)
            backend_dir = os.path.dirname(os.path.dirname(current_file))

            mineru_extra = []
            if 'images' in image_path:
                mineru_extra = [
                    os.path.join(root, image_path)
                    for root, _, files in os.walk(os.path.join(backend_dir, 'mineru_output'))
                    for f in files if f == os.path.basename(image_path)
                ]

            possible_paths = [
                os.path.join(backend_dir, image_path),
                os.path.join(os.getcwd(), image_path),
                os.path.join(backend_dir, 'images', os.path.basename(image_path)) if 'images' in image_path else None,
                os.path.join(backend_dir, image_path.replace('images\\', 'images\\').replace('images/', 'images/')) if 'images' in image_path else None,
                os.path.join(backend_dir, 'mineru_output', image_path),
                *mineru_extra,
            ]
            possible_paths = [p for p in possible_paths if p]

            for possible_path in possible_paths:
                if os.path.exists(possible_path):
                    logger.info(f"本地图片存在（查找路径）: {possible_path} (原始路径: {image_path})")
                    return possible_path

        logger.warning(f"本地图片不存在: {image_path}, mineru_folder={mineru_folder}")
        return None

    except Exception as e:
        logger.error(f"检查本地图片时出错: {str(e)}, 图片路径: {image_path}")
        return None

def generate_citation(paper) -> str:
    """
    生成Citation格式的引用信息
    
    格式: GUAN Y, GUO F R, LIANG K, et al. Title[J]. Journal of Donghua University (English Edition), 2025, 42(5): 449-456.
    
    Args:
        paper: Paper对象或字典，包含authors, chinese_authors, title, issue, page_start, page_end等字段
    
    Returns:
        Citation字符串
    """
    try:
        # 获取字段
        if hasattr(paper, 'authors'):
            authors_en = paper.authors
            chinese_authors = getattr(paper, 'chinese_authors', '') or ''
            title = paper.title
            issue = getattr(paper, 'issue', '') or ''
            page_start = getattr(paper, 'page_start', None)
            page_end = getattr(paper, 'page_end', None)
        else:
            authors_en = paper.get('authors', '')
            chinese_authors = paper.get('chinese_authors', '') or ''
            title = paper.get('title', '')
            issue = paper.get('issue', '') or ''
            page_start = paper.get('page_start')
            page_end = paper.get('page_end')
        
        # 1. 处理作者部分
        def format_author_name(en_name: str, cn_name: str) -> str:
            """
            格式化作者名称为Citation格式
            格式: 姓全大写 + 空格 + 名的首字母
            
            Args:
                en_name: 英文名，如 "HUANG Jiacui"
                cn_name: 中文名，如 "黄家淬"
            
            Returns:
                格式化后的名称，如 "HUANG J C" 或 "HUANG J"
            """
            if not en_name or not cn_name:
                return en_name.upper() if en_name else ''
            
            # 统计中文字符数（去掉标点、空格等）
            cn_char_count = len(re.findall(r'[\u4e00-\u9fff]', cn_name))
            
            # 按空格分割英文名
            parts = en_name.strip().split()
            if not parts:
                return en_name.upper()
            
            # 第一个词是姓
            surname = parts[0].upper()
            
            # 剩余的词是名
            given_names = parts[1:] if len(parts) > 1 else []
            
            if not given_names:
                return surname
            
            # 根据中文名字符数判断
            if cn_char_count == 2:
                # 2个字的名字：只取名的首字母
                given_name_initials = given_names[0][0].upper() if given_names[0] else ''
            elif cn_char_count >= 3:
                # 3个字或更多：如果英文名只有一个词，按音节拆分为两部分
                # 如果英文名有多个词，取每个词的首字母
                if len(given_names) == 1:
                    # 单个词：拆分为两部分，每部分取首字母
                    # 例如 "Jiacui" -> "Jia" + "cui" -> "J C"
                    # "Mingbo" -> "Ming" + "bo" -> "M B"
                    given_name = given_names[0]
                    if len(given_name) >= 6:
                        # 长度>=6：拆分为前半部分和后半部分
                        mid = len(given_name) // 2
                        # 前半部分取首字母
                        first_part = given_name[0].upper()
                        # 后半部分取首字母
                        second_part = given_name[mid].upper()
                        given_name_initials = f"{first_part} {second_part}"
                    elif len(given_name) >= 4:
                        # 长度4-5：拆分为前2-3个字符和后2个字符
                        split_point = len(given_name) - 2
                        first_part = given_name[0].upper()
                        second_part = given_name[split_point].upper()
                        given_name_initials = f"{first_part} {second_part}"
                    else:
                        # 短名字：取前两个字符的首字母
                        initials = [given_name[0].upper()]
                        if len(given_name) > 1:
                            initials.append(given_name[1].upper())
                        given_name_initials = ' '.join(initials)
                else:
                    # 多个词：取每个词的首字母
                    given_name_initials = ' '.join([name[0].upper() for name in given_names if name])
            else:
                # 其他情况：取第一个词的首字母
                given_name_initials = given_names[0][0].upper() if given_names[0] else ''
            
            return f"{surname} {given_name_initials}".strip()
        
        # 分割作者列表
        if ',' in authors_en:
            authors_en_list = [a.strip() for a in authors_en.split(',') if a.strip()]
        else:
            authors_en_list = [authors_en.strip()] if authors_en.strip() else []
        
        if ',' in chinese_authors:
            chinese_authors_list = [a.strip() for a in chinese_authors.split(',') if a.strip()]
        else:
            chinese_authors_list = [chinese_authors.strip()] if chinese_authors.strip() else []
        
        # 格式化每个作者
        formatted_authors = []
        for i, en_author in enumerate(authors_en_list):
            cn_author = chinese_authors_list[i] if i < len(chinese_authors_list) else ''
            formatted_author = format_author_name(en_author, cn_author)
            if formatted_author:
                formatted_authors.append(formatted_author)
        
        # 根据作者数量决定是否加 et al.
        if len(formatted_authors) > 3:
            authors_part = ', '.join(formatted_authors[:3]) + ', et al.'
        else:
            authors_part = ', '.join(formatted_authors)
        
        # 2. 标题部分（去掉末尾的点号，因为后面会跟 [J]）
        title_part = title.strip() if title else ''
        if title_part and title_part.endswith('.'):
            title_part = title_part[:-1].strip()
        
        # 3. 解析issue获取年份、卷号、期号
        year = ''
        volume = ''
        issue_num = ''
        if issue:
            # 格式: "2025, 42(3)"
            match = re.match(r'(\d{4}),\s*(\d+)\(([^)]+)\)', issue)
            if match:
                year = match.group(1)
                volume = match.group(2)
                issue_num = match.group(3)
        
        # 4. 页码范围
        pages_part = ''
        if page_start and page_end:
            pages_part = f"{page_start}-{page_end}"
        elif page_start:
            pages_part = str(page_start)
        
        # 5. 组装Citation
        citation_parts = []
        
        # 作者部分
        if authors_part:
            citation_parts.append(authors_part)
        
        # 标题部分（不添加点号，后面直接跟 [J]）
        if title_part:
            citation_parts.append(title_part)
        
        # 期刊信息部分
        # [J]. 后面没有逗号，直接跟期刊名称
        journal_info_parts = ['[J]. Journal of Donghua University (English Edition)']
        
        if year:
            journal_info_parts.append(year)
        
        # 卷期号和页码范围合并为一个元素，避免中间出现逗号
        volume_issue_pages = ''
        if volume and issue_num:
            volume_issue_pages = f"{volume}({issue_num})"
        elif volume:
            volume_issue_pages = str(volume)
        
        # 如果有页码范围，在卷期号后面直接加冒号和页码范围（不添加逗号）
        if pages_part:
            if volume_issue_pages:
                volume_issue_pages = f"{volume_issue_pages}: {pages_part}"
            else:
                volume_issue_pages = f": {pages_part}"
        
        if volume_issue_pages:
            journal_info_parts.append(volume_issue_pages)
        
        journal_info = ', '.join(journal_info_parts)
        citation_parts.append(journal_info)
        
        # 组合所有部分：作者和标题之间用点号+空格，标题和[J]之间用空格
        if len(citation_parts) == 1:
            citation = citation_parts[0]
        elif len(citation_parts) == 2:
            # 只有作者和期刊信息
            citation = f"{citation_parts[0]}. {citation_parts[1]}"
        else:
            # 作者、标题、期刊信息
            citation = f"{citation_parts[0]}. {citation_parts[1]} {citation_parts[2]}"
        
        if not citation.endswith('.'):
            citation += '.'
        
        return citation
        
    except Exception as e:
        logger.error(f"生成Citation时出错: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return ''

def add_citation_to_word_paragraph(para, citation_text: str, font_size: int = 11, prefix: str = None, prefix_format: Dict = None):
    """
    将citation添加到Word段落，并设置期刊名称部分为斜体
    
    Args:
        para: Word段落对象
        citation_text: Citation文本
        font_size: 字体大小
        prefix: 前缀文本（如果为None，则使用默认的"Citation: "）
        prefix_format: 前缀格式配置
    """
    from docx.shared import RGBColor, Pt
    
    try:
        # 期刊名称（需要斜体的部分）
        journal_name_main = "Journal of Donghua University"
        journal_name_edition = "(English Edition)"
        journal_name_full = f"{journal_name_main} {journal_name_edition}"
        
        # 查找期刊名称在citation中的位置
        journal_start = citation_text.find(journal_name_main)
        
        # 确定使用的前缀
        citation_prefix = prefix if prefix else "Citation: "
        prefix_font_size = prefix_format.get('font_size', font_size) if prefix_format else font_size
        
        if journal_start == -1:
            # 如果找不到期刊名称，直接添加整个citation
            # 先添加前缀
            if citation_prefix:
                prefix_run = para.add_run(citation_prefix)
                prefix_run.font.size = Pt(prefix_font_size)
                # 应用前缀格式
                if prefix_format:
                    if prefix_format.get('font_name'):
                        prefix_run.font.name = prefix_format['font_name']
                    if prefix_format.get('font_color'):
                        try:
                            color = prefix_format['font_color']
                            if color.startswith('#'):
                                r = int(color[1:3], 16)
                                g = int(color[3:5], 16)
                                b = int(color[5:7], 16)
                                prefix_run.font.color.rgb = RGBColor(r, g, b)
                        except:
                            pass
                    if prefix_format.get('font_bold'):
                        prefix_run.font.bold = True
            
            run = para.add_run(citation_text)
            run.font.size = Pt(font_size)
        else:
            # 添加前缀
            if citation_prefix:
                prefix_run = para.add_run(citation_prefix)
                prefix_run.font.size = Pt(prefix_font_size)
                # 应用前缀格式
                if prefix_format:
                    if prefix_format.get('font_name'):
                        prefix_run.font.name = prefix_format['font_name']
                    if prefix_format.get('font_color'):
                        try:
                            color = prefix_format['font_color']
                            if color.startswith('#'):
                                r = int(color[1:3], 16)
                                g = int(color[3:5], 16)
                                b = int(color[5:7], 16)
                                prefix_run.font.color.rgb = RGBColor(r, g, b)
                        except:
                            pass
                    if prefix_format.get('font_bold'):
                        prefix_run.font.bold = True
            
            # 添加期刊名称之前的部分
            before_journal = citation_text[:journal_start]
            if before_journal:
                before_run = para.add_run(before_journal)
                before_run.font.size = Pt(font_size)
            
            # 添加期刊名称（斜体）
            journal_run = para.add_run(journal_name_main)
            journal_run.font.size = Pt(font_size)
            journal_run.font.italic = True
            
            # 添加 " (English Edition)"，其中括号不斜体
            # 先添加空格和左括号（不斜体）
            space_paren_run = para.add_run(" (")
            space_paren_run.font.size = Pt(font_size)
            space_paren_run.font.italic = False
            
            # 添加 "English Edition"（斜体）
            edition_run = para.add_run("English Edition")
            edition_run.font.size = Pt(font_size)
            edition_run.font.italic = True
            
            # 添加右括号（不斜体）
            close_paren_run = para.add_run(")")
            close_paren_run.font.size = Pt(font_size)
            close_paren_run.font.italic = False
            
            # 添加期刊名称之后的部分
            after_journal = citation_text[journal_start + len(journal_name_full):]
            if after_journal:
                after_run = para.add_run(after_journal)
                after_run.font.size = Pt(font_size)
    
    except Exception as e:
        logger.error(f"添加citation到Word段落失败: {str(e)}")
        # 如果出错，简单添加整个citation
        run = para.runs[0] if para.runs else para.add_run()
        run.text = f"Citation: {citation_text}"
        run.font.size = Pt(font_size)

def apply_field_format_to_paragraph(para, field_config: Dict, value: str, paper_idx: int = 1) -> Dict:
    """
    统一的字段格式应用函数，用于预览和最终生成
    
    Args:
        para: Word段落对象
        field_config: 字段配置，包含 prefix, format, prefix_format 等
        value: 字段值
        paper_idx: 论文编号（用于title字段）
    
    Returns:
        文本预览数据字典
    """
    from docx.shared import RGBColor, Pt
    
    field_key = field_config.get('field') or field_config.get('key')
    field_label = field_config.get('label', '')
    prefix = field_config.get('prefix', '')
    format_config = field_config.get('format', {})
    prefix_format_config = field_config.get('prefix_format', {})
    
    # 准备文本预览数据
    preview_item = {
        'prefix': prefix,
        'prefix_style': {
            'font_name': prefix_format_config.get('font_name', ''),
            'font_size': prefix_format_config.get('font_size', 12),
            'font_color': prefix_format_config.get('font_color', '#000000')
        },
        'content': str(value),
        'content_style': {
            'font_name': format_config.get('font_name', ''),
            'font_size': format_config.get('font_size', 12),
            'font_color': format_config.get('font_color', '#000000')
        },
        'is_citation': field_key == 'citation'
    }
    
    # 特殊处理citation字段
    if field_key == 'citation':
        font_size = format_config.get('font_size', 11)
        # 使用配置中的prefix，如果没有则使用默认的"Citation: "
        citation_prefix = prefix if prefix else None
        add_citation_to_word_paragraph(para, value, font_size=font_size, prefix=citation_prefix, prefix_format=prefix_format_config)
        preview_item['content_style']['font_style'] = 'italic'
        # 更新预览数据中的prefix信息
        preview_item['prefix'] = citation_prefix if citation_prefix else 'Citation: '
        preview_item['prefix_style'] = {
            'font_name': prefix_format_config.get('font_name', ''),
            'font_size': prefix_format_config.get('font_size', font_size),
            'font_color': prefix_format_config.get('font_color', '#000000')
        }
        return preview_item
    
    # 处理其他字段：应用prefix和format
    # 如果有prefix，先添加prefix
    if prefix:
        prefix_run = para.add_run(prefix)
        # 应用prefix格式
        if prefix_format_config.get('font_name'):
            prefix_run.font.name = prefix_format_config['font_name']
        if prefix_format_config.get('font_size'):
            prefix_run.font.size = Pt(prefix_format_config['font_size'])
        if prefix_format_config.get('font_color'):
            try:
                color = prefix_format_config['font_color']
                if color.startswith('#'):
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    prefix_run.font.color.rgb = RGBColor(r, g, b)
            except:
                pass
        # 处理bold属性（用于title字段的论文编号）
        if prefix_format_config.get('font_bold') or (field_key in ['chinese_title', 'title'] and not field_config.get('prefix')):
            prefix_run.font.bold = True
    
    # 添加字段内容
    content_run = para.add_run(str(value))
    # 应用字段格式
    if format_config.get('font_name'):
        content_run.font.name = format_config['font_name']
    if format_config.get('font_size'):
        content_run.font.size = Pt(format_config['font_size'])
    if format_config.get('font_color'):
        try:
            color = format_config['font_color']
            if color.startswith('#'):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                content_run.font.color.rgb = RGBColor(r, g, b)
        except:
            pass
    # 处理bold属性（用于title字段）
    if format_config.get('font_bold') or (field_key in ['chinese_title', 'title'] and not format_config.get('font_bold') is False):
        # 如果配置了font_bold，或者title字段没有明确设置为False，则使用bold
        # 但这里我们优先使用配置的值
        if format_config.get('font_bold'):
            content_run.font.bold = True
        elif field_key in ['chinese_title', 'title']:
            # title字段默认bold（如果没有配置）
            content_run.font.bold = True
    
    return preview_item

def generate_tuiwen_content(papers, journal):
    """
    生成秀米推文内容 - Word文档格式
    使用默认字段配置（从JSON文件加载或硬编码后备）
    """
    try:
        # 从JSON文件加载默认字段配置
        default_fields = load_default_tuiwen_fields_config()
        
        # 使用 generate_tuiwen_from_fields 函数生成推文
        return generate_tuiwen_from_fields(papers, journal, default_fields)
        
    except Exception as e:
        logger.error(f"使用默认配置生成推文失败: {str(e)}，尝试使用原始硬编码方式")
        # 如果使用配置方式失败，回退到原始硬编码方式
        return _generate_tuiwen_content_legacy(papers, journal)

def _generate_tuiwen_content_legacy(papers, journal):
    """生成秀米推文内容 - 原始硬编码方式（作为后备）"""
    try:
        # 创建临时目录用于存储下载的图片
        temp_dir = os.path.join('temp_images', datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(temp_dir, exist_ok=True)
        
        # 创建Word文档
        doc = Document()
        
        # 设置样式
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 获取当前日期
        current_date = datetime.now().strftime('%Y年%m月%d日')
        issue = journal.issue
        
        # 转换期刊号格式：从"2025,42(3)"转换为"2025年第42卷第3期"
        def convert_issue_format(issue_str):
            """
            将期刊号格式从"2025,42(3)"转换为"2025年第42卷第3期"
            支持多种可能的格式：
            - "2025,42(3)" -> "2025年第42卷第3期"
            - "2025,42(3-4)" -> "2025年第42卷第3-4期"
            - "2025,42(3,4)" -> "2025年第42卷第3-4期"
            """
            try:
                # 匹配格式：年份,卷号(期号)
                match = re.match(r'(\d{4}),\s*(\d+)\(([^)]+)\)', issue_str)
                if match:
                    year = match.group(1)  # 年份
                    volume = match.group(2)  # 卷号
                    issue_num = match.group(3)  # 期号
                    
                    # 处理期号中的特殊字符
                    issue_num = issue_num.replace(',', '-')  # 将逗号替换为连字符
                    
                    return f"{year}年第{volume}卷第{issue_num}期"
                else:
                    # 如果格式不匹配，返回原格式
                    logger.warning(f"无法解析期刊号格式: {issue_str}")
                    return issue_str
            except Exception as e:
                logger.error(f"转换期刊号格式失败: {str(e)}")
                return issue_str
        
        # 转换期刊号格式
        issue_info = convert_issue_format(issue)
        
        # 添加期刊标题
        title_para = doc.add_paragraph()
        title_run = title_para.runs[0] if title_para.runs else title_para.add_run()
        title_run.text = "东华大学学报"
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        title_run.font.color.rgb = None  # 黑色
        
        # 添加期刊号
        issue_para = doc.add_paragraph()
        issue_run = issue_para.runs[0] if issue_para.runs else issue_para.add_run()
        issue_run.text = issue_info
        issue_run.font.size = Pt(12)
        
        # 添加分隔线
        doc.add_paragraph("─" * 30)  # 使用字符作为分隔线
        
        # 添加编辑信息
        editor_para = doc.add_paragraph()
        editor_run = editor_para.runs[0] if editor_para.runs else editor_para.add_run()
        editor_run.text = f"本期责编: 编辑部 | {current_date}"
        editor_run.font.size = Pt(10)
        editor_run.font.italic = True
        
        # 添加空行
        doc.add_paragraph()
        
        # 添加论文内容
        for i, paper in enumerate(papers, 1):
            # 处理数据库Paper对象或字典
            if hasattr(paper, 'title'):
                # 数据库对象
                title = paper.title
                authors = paper.authors
                chinese_title = getattr(paper, 'chinese_title', '') or ''
                chinese_authors = getattr(paper, 'chinese_authors', '') or ''
                doi = paper.doi or ''
                page_start = paper.page_start
                page_end = paper.page_end
                # 获取图片URL
                first_image_url = getattr(paper, 'first_image_url', '') or ''
                second_image_url = getattr(paper, 'second_image_url', '') or ''
                mineru_folder = getattr(paper, 'mineru_folder', '') or ''
                # 使用数据库中的citation字段
                citation = getattr(paper, 'citation', '') or ''

            # 添加中文标题（如果有）
            if chinese_title:
                chinese_title_para = doc.add_paragraph()
                chinese_title_run = chinese_title_para.runs[0] if chinese_title_para.runs else chinese_title_para.add_run()
                chinese_title_run.text = f"{i}. {chinese_title}"
                chinese_title_run.font.size = Pt(12)
                chinese_title_run.font.bold = True
            
            # 添加中文作者（如果有）
            if chinese_authors:
                chinese_authors_para = doc.add_paragraph()
                chinese_authors_run = chinese_authors_para.runs[0] if chinese_authors_para.runs else chinese_authors_para.add_run()
                chinese_authors_run.text = chinese_authors
                chinese_authors_run.font.size = Pt(11)
            
            # 添加第二张图片（在中文标题和中文作者下面）
            if second_image_url:
                try:
                    logger.info(f"开始处理第二张图片: {second_image_url}")
                    # 获取本地图片路径
                    local_image_path = get_local_image_path(second_image_url, temp_dir, mineru_folder)
                    logger.info(f"本地图片路径检查结果: {local_image_path}, 文件存在: {os.path.exists(local_image_path) if local_image_path else False}")
                    
                    if local_image_path and os.path.exists(local_image_path):
                        # 添加图片描述
                        # image_desc_para = doc.add_paragraph()
                        # image_desc_run = image_desc_para.runs[0] if image_desc_para.runs else image_desc_para.add_run()
                        # image_desc_run.text = "论文配图:"
                        # image_desc_run.font.size = Pt(10)
                        # image_desc_run.font.italic = True
                        
                        # 插入图片到Word文档 - 添加异常处理
                        try:
                            logger.info(f"尝试插入图片到Word: {local_image_path}")
                            doc.add_picture(local_image_path, width=Pt(300))  # 设置图片宽度为300磅
                            logger.info(f"✅ 为论文 {i} 成功插入第二张图片: {second_image_url}")
                        except Exception as picture_error:
                            logger.error(f"❌ 插入图片到Word失败: {str(picture_error)}")
                            # 如果插入失败，添加图片路径作为替代
                            url_para = doc.add_paragraph()
                            url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                            url_run.text = f"图片路径: {second_image_url}"
                            url_run.font.size = Pt(9)
                    else:
                        logger.warning(f"❌ 无法找到第二张图片: {second_image_url}")
                except Exception as img_error:
                    logger.error(f"❌ 处理第二张图片失败: {str(img_error)}")
            
            # 添加论文标题
            paper_title_para = doc.add_paragraph()
            paper_title_run = paper_title_para.runs[0] if paper_title_para.runs else paper_title_para.add_run()
            paper_title_run.text = title
            paper_title_run.font.size = Pt(12)
            paper_title_run.font.bold = True
            
            # 添加作者信息（去掉"作者："前缀）
            doc.add_paragraph(authors)
            
            # 添加DOI信息（保留"DOI："前缀）
            if doi:
                doc.add_paragraph(f"DOI: {doi}")
            
            # 添加引用信息（添加"Citation:"前缀，调整字体大小，期刊名称斜体）
            citation_para = doc.add_paragraph()
            add_citation_to_word_paragraph(citation_para, citation, font_size=11)
            
            # 在论文版块最后添加"作者说链接/OSID"文字和第一张图片
            # 添加分隔线
            doc.add_paragraph("─" * 20)
            
            # 添加"作者说链接/OSID"文字
            osid_para = doc.add_paragraph()
            osid_run = osid_para.runs[0] if osid_para.runs else osid_para.add_run()
            osid_run.text = "作者说链接/OSID"
            osid_run.font.size = Pt(10)
            osid_run.font.bold = True
            
            # 添加第一张图片（QRcode）
            if first_image_url:
                try:
                    logger.info(f"开始处理第一张图片(QRcode): {first_image_url}")
                    # 获取本地图片路径
                    local_image_path = get_local_image_path(first_image_url, temp_dir, mineru_folder)
                    logger.info(f"本地图片路径检查结果: {local_image_path}, 文件存在: {os.path.exists(local_image_path) if local_image_path else False}")
                    
                    if local_image_path and os.path.exists(local_image_path):
                        # 插入图片到Word文档 - 添加异常处理
                        try:
                            logger.info(f"尝试插入第一张图片到Word: {local_image_path}")
                            doc.add_picture(local_image_path, width=Pt(100))  # 设置较小的宽度用于二维码
                            logger.info(f"✅ 为论文 {i} 成功插入第一张图片(QRcode): {first_image_url}")
                        except Exception as picture_error:
                            logger.error(f"❌ 插入第一张图片到Word失败: {str(picture_error)}")
                            # 如果插入失败，添加图片路径作为替代
                            url_para = doc.add_paragraph()
                            url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                            url_run.text = f"二维码路径: {first_image_url}"
                            url_run.font.size = Pt(9)
                    else:
                        logger.warning(f"❌ 无法找到第一张图片(QRcode): {first_image_url}")
                except Exception as qrcode_error:
                    logger.error(f"❌ 处理第一张图片(QRcode)失败: {str(qrcode_error)}")
            
            # 添加空行分隔
            doc.add_paragraph()
        
        # 添加页脚信息
        doc.add_paragraph("─" * 30)  # 分隔线
        footer_para = doc.add_paragraph()
        footer_run = footer_para.runs[0] if footer_para.runs else footer_para.add_run()
        footer_run.text = "感谢您的阅读！欢迎引用本文内容"
        footer_run.font.size = Pt(10)
        
        copyright_para = doc.add_paragraph()
        copyright_run = copyright_para.runs[0] if copyright_para.runs else copyright_para.add_run()
        copyright_run.text = "© 2025 东华大学学报 版权所有"
        copyright_run.font.size = Pt(9)
        
        # 保存Word文档
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"推文_{journal.issue}_{timestamp}.docx"
        output_path = os.path.join('uploads', filename)
        
        # 确保目录存在
        os.makedirs('uploads', exist_ok=True)
        
        doc.save(output_path)
        logger.info(f"推文Word文档已生成: {output_path}")
        
        # 返回文件路径
        return output_path
    
    except Exception as e:
        logger.error(f"生成推文Word文档失败: {str(e)}")
        raise Exception(f"生成推文Word文档失败: {str(e)}")

def generate_tuiwen_from_fields(papers, journal, fields_config: List[Dict]) -> str:
    """
    根据字段配置生成推文内容
    
    Args:
        papers: 论文列表
        journal: 期刊对象
        fields_config: 字段配置列表，格式: [{'key': 'title', 'label': '标题', 'order': 1}, ...]
    """
    try:
        # 创建Word文档
        doc = Document()
        
        # 设置样式
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 获取当前日期
        current_date = datetime.now().strftime('%Y年%m月%d日')
        issue = journal.issue
        
        # 转换期刊号格式
        def convert_issue_format(issue_str):
            try:
                match = re.match(r'(\d{4}),\s*(\d+)\(([^)]+)\)', issue_str)
                if match:
                    year = match.group(1)
                    volume = match.group(2)
                    issue_num = match.group(3).replace(',', '-')
                    return f"{year}年第{volume}卷第{issue_num}期"
                return issue_str
            except:
                return issue_str
        
        issue_info = convert_issue_format(issue)
        
        # 添加期刊标题
        title_para = doc.add_paragraph()
        title_run = title_para.runs[0] if title_para.runs else title_para.add_run()
        title_run.text = journal.title or "东华大学学报"
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        
        # 添加期刊号
        issue_para = doc.add_paragraph()
        issue_run = issue_para.runs[0] if issue_para.runs else issue_para.add_run()
        issue_run.text = issue_info
        issue_run.font.size = Pt(12)
        
        # 添加分隔线
        doc.add_paragraph("─" * 30)
        
        # 添加编辑信息
        editor_para = doc.add_paragraph()
        editor_run = editor_para.runs[0] if editor_para.runs else editor_para.add_run()
        editor_run.text = f"本期责编: 编辑部 | {current_date}"
        editor_run.font.size = Pt(10)
        editor_run.font.italic = True
        
        # 添加空行
        doc.add_paragraph()
        
        # 创建临时目录用于存储图片（在整个函数中共享）
        temp_dir = os.path.join('temp_images', datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(temp_dir, exist_ok=True)
        
        # 按配置的字段顺序生成每篇论文的内容
        for paper_idx, paper in enumerate(papers, 1):
            # 处理数据库Paper对象或字典
            if hasattr(paper, 'title'):
                title = paper.title
                authors = paper.authors
                chinese_title = getattr(paper, 'chinese_title', '') or ''
                chinese_authors = getattr(paper, 'chinese_authors', '') or ''
                doi = paper.doi or ''
                page_start = paper.page_start
                page_end = paper.page_end
                # 使用数据库中的citation字段
                citation = getattr(paper, 'citation', '') or ''
                # 获取图片URL
                first_image_url = getattr(paper, 'first_image_url', '') or ''
                second_image_url = getattr(paper, 'second_image_url', '') or ''
                mineru_folder = getattr(paper, 'mineru_folder', '') or ''
            else:
                title = paper.get('title', '')
                authors = paper.get('authors', '')
                chinese_title = paper.get('chinese_title', '') or ''
                chinese_authors = paper.get('chinese_authors', '') or ''
                doi = paper.get('doi', '')
                page_start = paper.get('page_start')
                page_end = paper.get('page_end')
                # 使用数据库中的citation字段
                citation = paper.get('citation', '') or ''
                # 获取图片URL
                first_image_url = paper.get('first_image_url', '') or ''
                second_image_url = paper.get('second_image_url', '') or ''
                mineru_folder = paper.get('mineru_folder', '') or ''
            
            # 记录图片路径信息，便于排查
            logger.info(f"论文 {paper_idx} 图片路径: first_image_url={first_image_url}, second_image_url={second_image_url}")
            logger.info(f"论文 {paper_idx} 基本信息: title={title[:50] if title else ''}, page_start={page_start}, page_end={page_end}")
            
            # 字段值映射（图片字段映射到数据库字段名）
            field_values = {
                'chinese_title': chinese_title,
                'chinese_authors': chinese_authors,
                'title': title,
                'authors': authors,
                'doi': doi,
                'citation': citation,
                'page_start': str(page_start) if page_start else '',
                'page_end': str(page_end) if page_end else '',
                'second_image': second_image_url,  # 映射到数据库 second_image_url
                'first_image': first_image_url,   # 映射到数据库 first_image_url
            }
            
            # 按配置的字段顺序添加内容
            for field_config in sorted(fields_config, key=lambda x: x.get('order', 999)):
                field_key = field_config.get('field') or field_config.get('key')  # 支持两种格式
                field_label = field_config.get('label', '')
                
                if field_key in field_values:
                    value = field_values[field_key]
                    
                    # 处理图片字段
                    if field_key == 'second_image' and value:
                        try:
                            local_image_path = get_local_image_path(value, temp_dir, mineru_folder)
                            if local_image_path and os.path.exists(local_image_path):
                                try:
                                    doc.add_picture(local_image_path, width=Pt(300))
                                    logger.info(f"✅ 为论文 {paper_idx} 成功插入第二张图片")
                                except Exception as picture_error:
                                    logger.error(f"❌ 插入第二张图片失败: {str(picture_error)}")
                                    url_para = doc.add_paragraph()
                                    url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                                    url_run.text = f"图片路径: {value}"
                                    url_run.font.size = Pt(9)
                        except Exception as img_error:
                            logger.error(f"❌ 处理第二张图片失败: {str(img_error)}")
                    
                    elif field_key == 'first_image' and value:
                        # 添加分隔线
                        doc.add_paragraph("─" * 20)
                        # 添加"作者说链接/OSID"文字
                        osid_para = doc.add_paragraph()
                        osid_run = osid_para.runs[0] if osid_para.runs else osid_para.add_run()
                        osid_run.text = "作者说链接/OSID"
                        osid_run.font.size = Pt(10)
                        osid_run.font.bold = True
                        # 插入图片
                        try:
                            local_image_path = get_local_image_path(value, temp_dir, mineru_folder)
                            if local_image_path and os.path.exists(local_image_path):
                                try:
                                    doc.add_picture(local_image_path, width=Pt(100))
                                    logger.info(f"✅ 为论文 {paper_idx} 成功插入第一张图片(QRcode)")
                                except Exception as picture_error:
                                    logger.error(f"❌ 插入第一张图片失败: {str(picture_error)}")
                                    url_para = doc.add_paragraph()
                                    url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                                    url_run.text = f"二维码路径: {value}"
                                    url_run.font.size = Pt(9)
                        except Exception as img_error:
                            logger.error(f"❌ 处理第一张图片失败: {str(img_error)}")
                    
                    # 处理文本字段（使用统一的格式应用函数）
                    elif value and field_key not in ['first_image', 'second_image']:
                        para = doc.add_paragraph()

                        # 中文标题：始终使用动态序号；英文标题：始终不带序号
                        if field_key in ['chinese_title', 'title']:
                            field_config_with_idx = field_config.copy()
                            # 中文标题才加序号，英文标题不加
                            if field_key == 'chinese_title':
                                field_config_with_idx['prefix'] = f"{paper_idx}. "
                            else:
                                field_config_with_idx['prefix'] = ''
                            if not field_config_with_idx.get('prefix_format'):
                                field_config_with_idx['prefix_format'] = {}
                            if 'font_size' not in field_config_with_idx['prefix_format']:
                                field_config_with_idx['prefix_format']['font_size'] = 12
                            apply_field_format_to_paragraph(para, field_config_with_idx, value, paper_idx)
                        else:
                            # 作者字段（authors）：强制去掉 prefix（如用户配置的"作者："）
                            field_config_clean = field_config.copy()
                            if field_key == 'authors':
                                field_config_clean['prefix'] = ''
                            if not field_config_clean.get('prefix_format'):
                                field_config_clean['prefix_format'] = {}
                            apply_field_format_to_paragraph(para, field_config_clean, value, paper_idx)

            # 添加空行分隔
            doc.add_paragraph()
        
        # 添加页脚信息
        doc.add_paragraph("─" * 30)
        footer_para = doc.add_paragraph()
        footer_run = footer_para.runs[0] if footer_para.runs else footer_para.add_run()
        footer_run.text = "感谢您的阅读！欢迎引用本文内容"
        footer_run.font.size = Pt(10)
        
        copyright_para = doc.add_paragraph()
        copyright_run = copyright_para.runs[0] if copyright_para.runs else copyright_para.add_run()
        copyright_run.text = "© 2025 东华大学学报 版权所有"
        copyright_run.font.size = Pt(9)
        
        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"推文_{journal.issue}_{timestamp}.docx"
        output_path = os.path.join('uploads', filename)
        
        os.makedirs('uploads', exist_ok=True)
        doc.save(output_path)
        
        logger.info(f"根据字段配置生成推文: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"根据字段配置生成推文失败: {str(e)}")
        raise Exception(f"根据字段配置生成推文失败: {str(e)}")

def generate_tuiwen_preview_from_config(fields_config: List[Dict], source_data: Dict, return_text_preview: bool = False) -> str:
    """
    根据字段配置和源数据生成推文预览（与最终生成保持一致）
    
    Args:
        fields_config: 字段配置列表，格式: [{'field': 'title', 'label': '标题', 'order': 1}, ...]
        source_data: 源数据（论文数据字典）
        return_text_preview: 是否返回文本预览数据
    
    Returns:
        如果 return_text_preview=True，返回 (preview_path, text_preview_data)
        否则返回 preview_path
    """
    try:
        from docx.shared import RGBColor, Pt
        from docx.oxml.ns import qn
        
        # 创建Word文档
        doc = Document()
        
        # 设置样式
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 获取当前日期（用于编辑信息）
        current_date = datetime.now().strftime('%Y年%m月%d日')
        
        # 模拟期刊信息（预览使用默认值）
        journal_title = "东华大学学报"
        journal_issue = "2024, 41(1)"  # 默认期刊号
        
        # 转换期刊号格式（与最终生成保持一致）
        def convert_issue_format(issue_str):
            try:
                match = re.match(r'(\d{4}),\s*(\d+)\(([^)]+)\)', issue_str)
                if match:
                    year = match.group(1)
                    volume = match.group(2)
                    issue_num = match.group(3).replace(',', '-')
                    return f"{year}年第{volume}卷第{issue_num}期"
                return issue_str
            except:
                return issue_str
        
        issue_info = convert_issue_format(journal_issue)
        
        # 添加期刊标题（与最终生成保持一致）
        title_para = doc.add_paragraph()
        title_run = title_para.runs[0] if title_para.runs else title_para.add_run()
        title_run.text = journal_title
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        
        # 添加期刊号
        issue_para = doc.add_paragraph()
        issue_run = issue_para.runs[0] if issue_para.runs else issue_para.add_run()
        issue_run.text = issue_info
        issue_run.font.size = Pt(12)
        
        # 添加分隔线
        doc.add_paragraph("─" * 30)
        
        # 添加编辑信息
        editor_para = doc.add_paragraph()
        editor_run = editor_para.runs[0] if editor_para.runs else editor_para.add_run()
        editor_run.text = f"本期责编: 编辑部 | {current_date}"
        editor_run.font.size = Pt(10)
        editor_run.font.italic = True
        
        # 添加空行
        doc.add_paragraph()
        
        # 准备字段值映射（图片字段映射到数据库字段名）
        field_values = {
            'title': source_data.get('title', ''),
            'chinese_title': source_data.get('chinese_title', '') or '',
            'authors': source_data.get('authors', ''),
            'chinese_authors': source_data.get('chinese_authors', '') or '',
            'doi': source_data.get('doi', ''),
            'citation': source_data.get('citation', ''),
            'page_start': str(source_data.get('page_start', '')) if source_data.get('page_start') else '',
            'page_end': str(source_data.get('page_end', '')) if source_data.get('page_end') else '',
            'second_image': source_data.get('second_image_url', '') or '',  # 映射到数据库 second_image_url
            'first_image': source_data.get('first_image_url', '') or '',     # 映射到数据库 first_image_url
        }
        mineru_folder = source_data.get('mineru_folder', '') or ''
        
        # 使用数据库中的citation字段（如果为空则为空字符串）
        if not field_values.get('citation'):
            field_values['citation'] = ''
        
        # 按order排序字段
        sorted_fields = sorted(fields_config, key=lambda x: x.get('order', 999))
        
        # 文本预览数据
        text_preview_data = []
        
        # 创建临时目录用于存储图片
        temp_dir = os.path.join('temp_images', datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(temp_dir, exist_ok=True)
        
        # 论文编号（预览只显示一篇，编号为1）
        paper_idx = 1
        
        # 遍历字段配置，生成内容（与最终生成保持一致的格式）
        for field_config in sorted_fields:
            field_key = field_config.get('field') or field_config.get('key')  # 支持两种格式
            field_label = field_config.get('label', '')
            
            if field_key not in field_values:
                continue
            
            value = field_values[field_key]
            
            # 处理图片字段
            if field_key == 'second_image' and value:
                try:
                    local_image_path = get_local_image_path(value, temp_dir, mineru_folder)
                    if local_image_path and os.path.exists(local_image_path):
                        try:
                            doc.add_picture(local_image_path, width=Pt(300))
                            logger.info(f"✅ 预览中成功插入第二张图片")
                            # 文本预览中标记图片
                            text_preview_data.append({
                                'prefix': '',
                                'prefix_style': {},
                                'content': '[论文配图]',
                                'content_style': {'font_size': 11},
                                'is_citation': False,
                                'is_image': True
                            })
                        except Exception as picture_error:
                            logger.error(f"❌ 预览中插入第二张图片失败: {str(picture_error)}")
                            url_para = doc.add_paragraph()
                            url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                            url_run.text = f"图片路径: {value}"
                            url_run.font.size = Pt(9)
                except Exception as img_error:
                    logger.error(f"❌ 预览中处理第二张图片失败: {str(img_error)}")
            
            elif field_key == 'first_image' and value:
                # 添加分隔线
                doc.add_paragraph("─" * 20)
                # 添加"作者说链接/OSID"文字
                osid_para = doc.add_paragraph()
                osid_run = osid_para.runs[0] if osid_para.runs else osid_para.add_run()
                osid_run.text = "作者说链接/OSID"
                osid_run.font.size = Pt(10)
                osid_run.font.bold = True
                # 插入图片
                try:
                    local_image_path = get_local_image_path(value, temp_dir, mineru_folder)
                    if local_image_path and os.path.exists(local_image_path):
                        try:
                            doc.add_picture(local_image_path, width=Pt(100))
                            logger.info(f"✅ 预览中成功插入第一张图片(QRcode)")
                            # 文本预览中标记图片
                            text_preview_data.append({
                                'prefix': '作者说链接/OSID: ',
                                'prefix_style': {'font_size': 10, 'font_bold': True},
                                'content': '[二维码]',
                                'content_style': {'font_size': 11},
                                'is_citation': False,
                                'is_image': True
                            })
                        except Exception as picture_error:
                            logger.error(f"❌ 预览中插入第一张图片失败: {str(picture_error)}")
                            url_para = doc.add_paragraph()
                            url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                            url_run.text = f"二维码路径: {value}"
                            url_run.font.size = Pt(9)
                except Exception as img_error:
                    logger.error(f"❌ 预览中处理第一张图片失败: {str(img_error)}")
            
            # 处理文本字段（使用统一的格式应用函数，与最终生成保持一致）
            elif value and field_key not in ['first_image', 'second_image']:
                para = doc.add_paragraph()

                # 中文标题：始终使用动态序号；英文标题：始终不带序号
                if field_key in ['chinese_title', 'title']:
                    field_config_with_idx = field_config.copy()
                    # 中文标题才加序号，英文标题不加
                    if field_key == 'chinese_title':
                        field_config_with_idx['prefix'] = f"{paper_idx}. "
                    else:
                        field_config_with_idx['prefix'] = ''
                    if not field_config_with_idx.get('prefix_format'):
                        field_config_with_idx['prefix_format'] = {}
                    if 'font_size' not in field_config_with_idx['prefix_format']:
                        field_config_with_idx['prefix_format']['font_size'] = 12
                    preview_item = apply_field_format_to_paragraph(para, field_config_with_idx, value, paper_idx)
                else:
                    # 作者字段（authors）：强制去掉 prefix（如用户配置的"作者："）
                    field_config_clean = field_config.copy()
                    if field_key == 'authors':
                        field_config_clean['prefix'] = ''
                    if not field_config_clean.get('prefix_format'):
                        field_config_clean['prefix_format'] = {}
                    preview_item = apply_field_format_to_paragraph(para, field_config_clean, value, paper_idx)
                
                # 添加到文本预览数据
                text_preview_data.append(preview_item)
        
        # 添加空行分隔
        doc.add_paragraph()
        
        # 添加页脚信息（与最终生成保持一致）
        doc.add_paragraph("─" * 30)
        footer_para = doc.add_paragraph()
        footer_run = footer_para.runs[0] if footer_para.runs else footer_para.add_run()
        footer_run.text = "感谢您的阅读！欢迎引用本文内容"
        footer_run.font.size = Pt(10)
        
        copyright_para = doc.add_paragraph()
        copyright_run = copyright_para.runs[0] if copyright_para.runs else copyright_para.add_run()
        copyright_run.text = "© 2025 东华大学学报 版权所有"
        copyright_run.font.size = Pt(9)
        
        # 保存预览文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        preview_filename = f"tuiwen_preview_{timestamp}.docx"
        preview_dir = os.path.join('temp_images', datetime.now().strftime('%Y%m%d'))
        os.makedirs(preview_dir, exist_ok=True)
        preview_path = os.path.join(preview_dir, preview_filename)
        
        doc.save(preview_path)
        logger.info(f"预览文档已保存: {preview_path}")
        
        if return_text_preview:
            return preview_path, text_preview_data
        else:
            return preview_path
        
    except Exception as e:
        logger.error(f"生成推文预览失败: {str(e)}")
        raise Exception(f"生成推文预览失败: {str(e)}")
