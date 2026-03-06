"""
文档批注功能模块
用于为论文格式检测结果添加批注
"""

import os
import shutil
import re
import json
import logging
from pathlib import Path
from docx import Document
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 检测模块执行顺序
DETECTION_ORDER = ['Title', 'Abstract', 'Keywords', 'Content', 'Formula', 'Figure', 'Table', 'TOC', 'Chinese_section']

# 批注关键词配置（支持外部 JSON 覆盖，未找到时使用默认值）
def load_annotation_keyword_config():
    default_cfg = {
        "abstract": {
            "title_keywords": ["Abstract:"],
            "title_regex": r"^\s*Abstract\s*$",  # 备用匹配（独立一行）
            "content_follow_title": True  # Abstract 独立一行时，正文取其后首个非空段落
        },
        "keywords": {
            "title_keywords": ["Keywords:"],
            "title_regex": r"^\s*Keywords\s*$",
            "content_follow_title": True
        }
    }
    candidates = [
        Path(__file__).parent / "annotation_keywords.json",
        Path(__file__).parent / "paper_detect_templates" / "annotation_keywords.json",
        Path(__file__).parent.parent / "services" / "paper_detect_templates" / "annotation_keywords.json",
    ]
    for path in candidates:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 浅合并：只覆盖同级键
                    for k, v in data.items():
                        if isinstance(v, dict) and isinstance(default_cfg.get(k), dict):
                            default_cfg[k].update(v)
                        else:
                            default_cfg[k] = v
        except Exception as e:
            logger.warning(f"读取批注关键词配置失败: {path}: {e}")
    return default_cfg

ANNOTATION_KEYWORDS = load_annotation_keyword_config()


def create_document_copy(original_path: str, output_dir: str) -> Optional[str]:
    """
    创建文档副本
    
    参数：
        original_path: 原始文档路径
        output_dir: 输出目录
    
    返回：
        副本文件路径
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # annotate_filename = f"{timestamp}_annotated.docx"
        base_name = os.path.splitext(os.path.basename(original_path))[0].split('_')[-1]
        copy_filename = f"{timestamp}_{base_name}_annotated.docx"
        copy_path = os.path.join(output_dir, copy_filename)
        
        shutil.copy(original_path, copy_path)
        logger.info(f"文档副本已创建: {copy_path}")
        return copy_path
    except Exception as e:
        logger.error(f"创建文档副本失败: {e}")
        return None


def find_paragraph_by_keyword(doc, keyword, case_sensitive=False):
    """
    通过关键字查找段落
    
    参数：
        doc: Document对象
        keyword: 关键字
        case_sensitive: 是否区分大小写
    
    返回：
        匹配的段落对象，未找到返回None
    """
    for paragraph in doc.paragraphs:
        if not paragraph.text:
            continue
        
        text = paragraph.text if case_sensitive else paragraph.text.lower()
        search_key = keyword if case_sensitive else keyword.lower()
        
        if search_key in text:
            return paragraph
    
    return None


def find_title_by_abstract(doc, language='chinese'):
    """
    根据摘要位置查找标题段落（位于摘要上方）
    
    参数：
        doc: Document对象
        language: 'chinese' 或 'english'
    
    返回：
        标题段落对象，未找到返回None
    """
    # 先找到摘要位置
    abstract_keywords = ['摘 要', '摘要'] if language == 'chinese' else ['Abstract', 'ABSTRACT']
    abstract_idx = None
    
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        
        # 检查是否匹配摘要标题
        if language == 'chinese':
            if re.match(r'^\s*摘\s要\s*$', text) or text == '摘要':
                abstract_idx = idx
                break
        else:
            if re.match(r'^\s*Abstract\s*$', text, re.IGNORECASE):
                abstract_idx = idx
                break
    
    if abstract_idx is None or abstract_idx == 0:
        return None
    
    # 从摘要上方开始查找标题
    for i in range(abstract_idx - 1, -1, -1):
        paragraph = doc.paragraphs[i]
        text = paragraph.text.strip()
        if text:
            # 检查是否包含中文字符（中文标题）或全大写英文（英文标题）
            if language == 'chinese':
                if re.search(r'[\u4e00-\u9fff]', text):
                    return paragraph
            else:
                # 英文标题：检查是否全大写（排除纯数字或特殊符号）
                if re.search(r'[A-Z]', text) and text.isupper():
                    return paragraph
    
    return None


def find_paragraph_by_regex(doc, pattern, flags=0):
    """通过正则表达式查找段落"""
    regex = re.compile(pattern, flags)
    for paragraph in doc.paragraphs:
        if paragraph.text and regex.search(paragraph.text):
            return paragraph
    return None


def find_paragraph_by_index(doc, index, skip_empty=True):
    """
    通过索引查找段落
    
    参数：
        doc: Document对象
        index: 段落索引
        skip_empty: 是否跳过空段落（默认True，兼容旧逻辑）
    
    返回：
        段落对象，索引无效返回None
    """
    try:
        if not skip_empty:
            # 不跳过空行，直接返回
            if 0 <= index < len(doc.paragraphs):
                return doc.paragraphs[index]
        else:
            # 跳过空行，找到第N个非空段落
            non_empty_count = 0
            for paragraph in doc.paragraphs:
                if paragraph.text and paragraph.text.strip():
                    if non_empty_count == index:
                        return paragraph
                    non_empty_count += 1
    except Exception:
        pass
    
    return None


def find_paragraph_by_text(doc, text_fragment, threshold=0.7):
    """
    通过文本片段查找段落（模糊匹配）
    
    参数：
        doc: Document对象
        text_fragment: 文本片段
        threshold: 相似度阈值（0-1）
    
    返回：
        最匹配的段落对象，未找到返回None
    """
    best_match = None
    best_score = 0
    
    search_text = text_fragment.lower().strip()
    if len(search_text) < 5:
        # 文本太短，使用精确匹配
        for paragraph in doc.paragraphs:
            if search_text in paragraph.text.lower():
                return paragraph
        return None
    
    for paragraph in doc.paragraphs:
        if not paragraph.text or len(paragraph.text.strip()) < 5:
            continue
        
        para_text = paragraph.text.lower().strip()
        
        # 简单的相似度计算：检查搜索文本是否在段落中
        if search_text in para_text:
            score = len(search_text) / len(para_text)
            if score > best_score:
                best_score = score
                best_match = paragraph
    
    if best_score >= threshold:
        return best_match
    
    return None


def find_content_paragraph_by_number(doc, para_number, hierarchy_report):
    """
    根据段落编号定位具体的正文段落
    
    参数：
        doc: Document对象
        para_number: 段落编号（1-based，如"正文段落 1"中的1）
        hierarchy_report: 标题层级报告（包含标题段落索引信息）
    
    返回：
        对应的段落对象，未找到返回None
    """
    # 获取所有标题段落的索引
    title_paragraph_indices = set()
    introduction_index = None
    
    if hierarchy_report and hierarchy_report.get('titles'):
        for title_info in hierarchy_report['titles']:
            if 'paragraph_index' in title_info:
                idx = title_info['paragraph_index']
                title_paragraph_indices.add(idx)
                # 找到Introduction段落索引
                if title_info['level'] == 0 and title_info['text'] == 'Introduction':
                    introduction_index = idx
    
    # 如果没有找到Introduction，尝试用关键字查找
    if introduction_index is None:
        for i, para in enumerate(doc.paragraphs):
            if 'Introduction' in para.text:
                introduction_index = i
                break
    
    if introduction_index is None:
        return None
    
    # 从Introduction之后开始查找正文段落
    content_paragraph_count = 0
    
    for i in range(introduction_index + 1, len(doc.paragraphs)):
        paragraph = doc.paragraphs[i]
        
        # 排除标题段落
        if i in title_paragraph_indices:
            continue
        
        # 检查是否为有效正文段落（与Content_detect.py逻辑一致）
        text = paragraph.text.strip() if paragraph.text else ""
        if not text or len(text) <= 20:
            continue
        
        # 排除表格标题、图片标题等
        text_lower = text.lower()
        if (text_lower.startswith('table ') or 
            text_lower.startswith('figure ') or 
            text_lower.startswith('fig.') or
            text_lower.startswith('图 ') or 
            text_lower.startswith('表 ') or
            re.match(r'^(表|图|Table|Figure)\s*\d+', text, re.IGNORECASE)):
            continue
        
        # 排除居中对齐的短段落（可能是标题或表格标题）
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        alignment = paragraph.alignment
        if alignment is not None and alignment == WD_PARAGRAPH_ALIGNMENT.CENTER and len(text) < 80:
            continue
        
        # 这是有效的正文段落
        content_paragraph_count += 1
        
        # 找到目标段落
        if content_paragraph_count == para_number:
            return paragraph
    
    return None


def add_comment_to_paragraph(doc, paragraph, comment_text, author="论文检测系统", initials="PDS"):
    """
    为段落添加批注（覆盖整个段落）
    
    参数：
        doc: Document对象
        paragraph: 段落对象
        comment_text: 批注内容
        author: 批注作者
        initials: 批注作者缩写
    
    返回：
        成功返回True，失败返回False
    """
    try:
        # 确保段落有run
        if not paragraph.runs:
            # 如果段落没有run，添加一个
            paragraph.add_run("")
        
        # 策略：为了让批注覆盖整个段落，我们选择所有的runs
        # 如果段落有多个runs，收集它们；如果只有一个run，就用那个
        runs_to_annotate = paragraph.runs if len(paragraph.runs) > 1 else paragraph.runs[0]
        
        # 添加批注
        doc.add_comment(runs=runs_to_annotate, text=comment_text, author=author, initials=initials)
        return True
    except Exception as e:
        # 如果出错，尝试备用方案：只使用第一个run
        try:
            run = paragraph.runs[0]
            doc.add_comment(runs=run, text=comment_text, author=author, initials=initials)
            print(f"  ⚠ 批注仅覆盖部分文本（备用方案）")
            return True
        except Exception as e2:
            print(f"  ✗ 添加批注失败: {e2}")
            return False


def extract_paragraph_number_from_message(message):
    """
    从错误消息中提取段落编号
    例如："正文段落 1 字体大小..." -> 返回 1
    """
    match = re.search(r'正文段落\s*(\d+)', message)
    if match:
        return int(match.group(1))
    
    match = re.search(r'段落\s*(\d+)', message)
    if match:
        return int(match.group(1))
    
    return None


def group_messages_by_paragraph(messages):
    """
    将消息按段落分组
    
    返回：
        {段落编号: [消息列表], None: [无段落编号的消息]}
    """
    grouped = {}
    
    for msg in messages:
        para_num = extract_paragraph_number_from_message(msg)
        if para_num not in grouped:
            grouped[para_num] = []
        grouped[para_num].append(msg)
    
    return grouped


def group_messages_by_title(messages, titles):
    """
    将标题格式/大小写消息按标题文本分组
    
    参数：
        messages: 消息列表
        titles: 标题信息列表
    
    返回：
        {标题文本: [消息列表]}
    """
    import re
    grouped = {}
    
    for msg in messages:
        # 从消息中提取标题文本
        # 消息格式：标题 'xxx' 字体大小应为...
        # 或：一级标题 'xxx' 大小写不正确...
        title_match = re.search(r"标题\s+'([^']+)'", msg)
        if title_match:
            title_text = title_match.group(1)
            if title_text not in grouped:
                grouped[title_text] = []
            grouped[title_text].append(msg)
        else:
            # 消息头（如"标题格式问题："）或无法提取标题的消息，归到None
            if None not in grouped:
                grouped[None] = []
            grouped[None].append(msg)
    
    # 移除None键（这些是消息头）
    if None in grouped:
        del grouped[None]
    
    return grouped


def parse_issues_from_reports(all_reports):
    """
    从报告中提取问题列表和定位信息
    
    参数：
        all_reports: {模块名: 报告字典} 的字典
    
    返回：
        问题列表 [{
            'module': 模块名,
            'section': 检测项名称,
            'messages': 问题消息列表,
            'locate_method': 定位方法（'keyword', 'index', 'text', 'paragraph_object'），
            'locate_data': 定位数据（关键字、索引、文本片段、段落对象）
        }]
    """
    issues = []
    
    logger.info(f"parse_issues_from_reports: 开始处理，all_reports 键: {list(all_reports.keys())}")
    logger.info(f"parse_issues_from_reports: DETECTION_ORDER: {DETECTION_ORDER}")
    
    for module_name in DETECTION_ORDER:
        if module_name not in all_reports:
            logger.debug(f"parse_issues_from_reports: 跳过模块 {module_name}（不在 all_reports 中）")
            continue
        
        report = all_reports[module_name]
        logger.info(f"parse_issues_from_reports: 处理模块 {module_name}, report 类型: {type(report)}")
        
        # 跳过错误报告
        if report.get('error', False):
            logger.warning(f"parse_issues_from_reports: 跳过模块 {module_name}（有错误标记）")
            continue
        
        # 为不同模块设计定位策略
        if module_name == 'Title':
            logger.info(f"parse_issues_from_reports: 开始处理 Title 模块，report keys: {list(report.keys()) if isinstance(report, dict) else 'not a dict'}")
            
            # 检查是否是中文检测器的双语结构（包含 'chinese' 和 'english' 键）
            if isinstance(report, dict) and ('chinese' in report or 'english' in report):
                logger.info("parse_issues_from_reports: 检测到中文检测器的双语 Title 结构")
                # 处理中文标题
                if 'chinese' in report and isinstance(report['chinese'], dict):
                    chinese_report = report['chinese']
                    logger.info(f"parse_issues_from_reports: 处理中文标题，keys: {list(chinese_report.keys())}")
                    # 从 structure 中获取标题文本用于定位
                    structure_report = chinese_report.get('structure', {})
                    title_text = structure_report.get('title_text', '')
                    
                    # 处理 structure 和 format
                    for sub_key in ['structure', 'format']:
                        if sub_key in chinese_report and isinstance(chinese_report[sub_key], dict):
                            sub_report = chinese_report[sub_key]
                            if not sub_report.get('ok', False):
                                messages = sub_report.get('messages', [])
                                if messages:
                                    # 使用基于摘要位置的定位方法（避免定位到封面标题）
                                    issues.append({
                                        'module': module_name,
                                        'section': f'chinese_{sub_key}',
                                        'messages': messages,
                                        'locate_method': 'title_by_abstract',
                                        'locate_data': 'chinese'
                                    })
                                    logger.info(f"parse_issues_from_reports: Title 模块添加中文标题问题 - section: chinese_{sub_key}, 使用摘要位置定位, 消息数: {len(messages)}")
                
                # 处理英文标题（如果有）
                if 'english' in report and isinstance(report['english'], dict):
                    english_report = report['english']
                    logger.info(f"parse_issues_from_reports: 处理英文标题，keys: {list(english_report.keys())}")
                    # 从 structure 中获取标题文本用于定位
                    structure_report = english_report.get('structure', {})
                    title_text = structure_report.get('title_text', '')
                    
                    # 处理 structure 和 format
                    for sub_key in ['structure', 'format']:
                        if sub_key in english_report and isinstance(english_report[sub_key], dict):
                            sub_report = english_report[sub_key]
                            if not sub_report.get('ok', False):
                                messages = sub_report.get('messages', [])
                                if messages:
                                    # 使用基于摘要位置的定位方法（避免定位到封面标题）
                                    issues.append({
                                        'module': module_name,
                                        'section': f'english_{sub_key}',
                                        'messages': messages,
                                        'locate_method': 'title_by_abstract',
                                        'locate_data': 'english'
                                    })
                                    logger.info(f"parse_issues_from_reports: Title 模块添加英文标题问题 - section: english_{sub_key}, 使用摘要位置定位, 消息数: {len(messages)}")
            else:
                # 处理英文检测器的单语结构（title, authors, affiliations, format）
                logger.info("parse_issues_from_reports: 使用英文检测器的单语 Title 结构")
                # 从 extracted 中获取标题文本用于定位
                extracted = report.get('extracted', {})
                title_text = extracted.get('title', '') if isinstance(extracted, dict) else ''
                
                # Title模块：使用关键字定位
                title_issue_count = 0
                for section_key, section_value in report.items():
                    if section_key in ['summary', 'extracted', 'details']:
                        logger.debug(f"parse_issues_from_reports: Title 模块跳过 section {section_key}（在排除列表中）")
                        continue
                    
                    logger.debug(f"parse_issues_from_reports: Title 模块检查 section {section_key}, 类型: {type(section_value)}, ok: {section_value.get('ok') if isinstance(section_value, dict) else 'N/A'}")
                    
                    if isinstance(section_value, dict) and not section_value.get('ok', False):
                        messages = section_value.get('messages', [])
                        logger.debug(f"parse_issues_from_reports: Title 模块 section {section_key} 有 {len(messages)} 条消息")
                        if not messages:
                            logger.debug(f"parse_issues_from_reports: Title 模块 section {section_key} 没有消息，跳过")
                            continue
                    
                    # 根据section类型确定定位方法
                    if 'title' in section_key.lower():
                        # 使用基于摘要位置的定位方法（避免定位到封面标题）
                        # 对于英文检测器，默认使用英文摘要
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': 'title_by_abstract',
                            'locate_data': 'english'  # 英文检测器默认使用英文摘要
                        })
                        title_issue_count += 1
                        logger.info(f"parse_issues_from_reports: Title 模块添加问题 - section: {section_key}, 使用摘要位置定位, 消息数: {len(messages)}")
                    elif 'author' in section_key.lower():
                        locate_method = 'index'
                        locate_data = 1  # 作者通常是第二个段落
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
                    elif 'affiliation' in section_key.lower():
                        locate_method = 'keyword'
                        locate_data = 'College'  # 单位通常包含College关键字
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
                    elif 'format' in section_key.lower():
                        # Title模块的格式消息优先使用结构化字段
                        structured_title_msgs = section_value.get('title_messages', [])
                        structured_author_msgs = section_value.get('author_messages', [])
                        structured_affiliation_msgs = section_value.get('affiliation_messages', [])
                        
                        use_structured = any(structured_title_msgs) or any(structured_author_msgs) or any(structured_affiliation_msgs)
                        
                        if use_structured:
                            if structured_title_msgs and any('问题' in msg or '错误' in msg for msg in structured_title_msgs):
                                # 使用基于摘要位置的定位方法（避免定位到封面标题）
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_title',
                                    'messages': structured_title_msgs,
                                    'locate_method': 'title_by_abstract',
                                    'locate_data': 'english'  # 英文检测器默认使用英文摘要
                                })
                                logger.info(f"parse_issues_from_reports: Title 模块 format_title 使用摘要位置定位")
                            
                            if structured_author_msgs and any('问题' in msg or '错误' in msg for msg in structured_author_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_authors',
                                    'messages': structured_author_msgs,
                                    'locate_method': 'index',
                                    'locate_data': 1
                                })
                            
                            affiliation_msgs = structured_affiliation_msgs
                        else:
                            # format问题需要按消息内容分组（兼容旧格式）
                            title_msgs = []
                            author_msgs = []
                            affiliation_msgs = []
                            current_group = None  # 跟踪当前消息组
                            
                            for msg in messages:
                                # 跳过独立批注标记的消息
                                if msg.startswith('__COMMENT_PARA_'):
                                    affiliation_msgs.append(msg)
                                    continue
                                    
                                msg_lower = msg.lower()
                                msg_stripped = msg.strip()
                                
                                # 判断是否是标题行（非子项）
                                is_header = not msg_stripped.startswith('- ')
                                
                                if is_header:
                                    # 这是一个标题行，确定它属于哪个组
                                    if '标题格式' in msg or 'title' in msg_lower:
                                        current_group = 'title'
                                        title_msgs.append(msg)
                                    elif '作者格式' in msg or 'author' in msg_lower:
                                        current_group = 'author'
                                        author_msgs.append(msg)
                                    elif '单位格式' in msg or '单位段落' in msg or 'affiliation' in msg_lower:
                                        current_group = 'affiliation'
                                        affiliation_msgs.append(msg)
                                    else:
                                        # 默认归类到标题
                                        current_group = 'title'
                                        title_msgs.append(msg)
                                else:
                                    # 这是子项，归入当前组
                                    if current_group == 'title':
                                        title_msgs.append(msg)
                                    elif current_group == 'author':
                                        author_msgs.append(msg)
                                    elif current_group == 'affiliation':
                                        affiliation_msgs.append(msg)
                                    else:
                                        # 如果没有当前组，默认归类到标题
                                        title_msgs.append(msg)
                            
                            # 为每组消息创建独立的issue（只添加包含问题的组）
                            # 判断是否有实际问题：检查消息中是否包含"问题"或"错误"关键字
                            if title_msgs and any('问题' in msg or '错误' in msg for msg in title_msgs):
                                # 使用基于摘要位置的定位方法（避免定位到封面标题）
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_title',
                                    'messages': title_msgs,
                                    'locate_method': 'title_by_abstract',
                                    'locate_data': 'english'  # 英文检测器默认使用英文摘要
                                })
                                logger.info(f"parse_issues_from_reports: Title 模块 format_title 使用摘要位置定位")
                            
                            if author_msgs and any('问题' in msg or '错误' in msg for msg in author_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_authors',
                                    'messages': author_msgs,
                                    'locate_method': 'index',
                                    'locate_data': 1
                                })
                        
                        if structured_affiliation_msgs or not use_structured:
                            # 分组单位消息：按段落和问题类型
                            # 1. 提取独立批注标记的消息 (__COMMENT_PARA_X__)
                            # 2. 其他消息按段落分组
                            comment_issues = {}  # {para_idx: [messages]}
                            affiliation_by_para = {}
                            general_affiliation_msgs = []
                            current_para_idx = None
                            
                            for msg in affiliation_msgs:
                                # 检查是否是独立批注标记
                                comment_match = re.match(r'__COMMENT_PARA_(\d+)__(.+)', msg)
                                if comment_match:
                                    para_num = int(comment_match.group(1))
                                    # para_num 现在是doc.paragraphs中的实际1-based索引
                                    para_idx = para_num - 1  # 转换为0-based索引用于定位
                                    comment_msg = comment_match.group(2)
                                    
                                    if para_idx not in comment_issues:
                                        comment_issues[para_idx] = []
                                    comment_issues[para_idx].append(comment_msg)
                                    continue
                                
                                msg_stripped = msg.strip()
                                is_header = not msg_stripped.startswith('- ')
                                
                                if is_header:
                                    # 标题行，尝试提取段落编号
                                    para_match = re.search(r'第(\d+)段', msg)
                                    if para_match:
                                        # 这个编号现在是实际的1-based索引（包括空行）
                                        para_num = int(para_match.group(1))
                                        current_para_idx = para_num - 1  # 转换为0-based
                                        if current_para_idx not in affiliation_by_para:
                                            affiliation_by_para[current_para_idx] = []
                                        affiliation_by_para[current_para_idx].append(msg)
                                    else:
                                        current_para_idx = None
                                        # 跳过总结性的标题（如"单位编号格式错误（共 3 处）"）
                                        if '共' not in msg and '处' not in msg:
                                            general_affiliation_msgs.append(msg)
                                else:
                                    # 子项，归入当前段落
                                    if current_para_idx is not None:
                                        affiliation_by_para[current_para_idx].append(msg)
                                    else:
                                        general_affiliation_msgs.append(msg)
                            
                            # 为每个段落的独立问题创建批注
                            for para_idx, comment_msgs in comment_issues.items():
                                # 每两条消息一组（错误描述+建议修改）
                                for i in range(0, len(comment_msgs), 2):
                                    issue_msgs = comment_msgs[i:i+2]
                                    issue_type = 'numbering' if '编号' in issue_msgs[0] else 'other'
                                    issues.append({
                                        'module': module_name,
                                        'section': section_key + f'_affiliation_para{para_idx+1}_{issue_type}',
                                        'messages': issue_msgs,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                            
                            # 为每个单位段落的其他问题创建批注（段后间距等）
                            # 只添加包含实际问题的段落
                            for para_idx, msgs in affiliation_by_para.items():
                                if any('问题' in msg or '错误' in msg for msg in msgs):
                                    issues.append({
                                        'module': module_name,
                                        'section': section_key + f'_affiliation_para{para_idx+1}_format',
                                        'messages': msgs,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                            
                            # 通用单位消息（只添加包含实际问题的消息）
                            if general_affiliation_msgs and any('问题' in msg or '错误' in msg for msg in general_affiliation_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_affiliations',
                                    'messages': general_affiliation_msgs,
                                    'locate_method': 'keyword',
                                    'locate_data': 'College'
                                })
                    else:
                        # 其他section默认定位到第一个段落
                        locate_method = 'index'
                        locate_data = 0
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
        
        elif module_name == 'Abstract':
            # Abstract模块：使用关键字定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details']:
                    continue
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if messages:
                        # 根据section类型决定定位策略
                        if section_key == 'structure':
                            # structure批注放在Abstract标题段落
                            locate_method = 'abstract_title'
                        else:
                            # paragraphs和format批注放在内容段落
                            locate_method = 'abstract_content'
                        
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': 'Abstract'
                        })
        
        elif module_name == 'Keywords':
            # Keywords模块：使用关键字定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details']:
                    continue
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if messages:
                        # 区分Keywords和CLC、Footnote
                        if 'clc' in section_key.lower():
                            locate_data = 'CLC number'
                            locate_method = 'keyword'
                        elif 'footnote' in section_key.lower():
                            # 脚注问题：定位到CLC行（脚注引用通常在这一行）
                            # 因为Word脚注在文档底部，无法直接定位，所以定位到引用位置
                            locate_data = 'CLC number'
                            locate_method = 'keyword'
                        elif section_key == 'structure':
                            # structure批注放在Keywords标题段落
                            locate_data = 'Keywords'
                            locate_method = 'keywords_title'
                        else:
                            # paragraphs和format批注放在内容段落
                            locate_data = 'Keywords'
                            locate_method = 'keywords_content'
                        
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
        
        elif module_name == 'Content':
            # Content模块：需要识别具体的正文段落
            logger.info(f"parse_issues_from_reports: 开始处理 Content 模块，report keys: {list(report.keys()) if isinstance(report, dict) else 'not a dict'}")
            
            # 检查是否是中文检测器的结构（包含 'structure' 和 'format' 键）
            if isinstance(report, dict) and 'structure' in report:
                logger.info("parse_issues_from_reports: 检测到中文检测器的 Content 结构")
                structure_report = report.get('structure', {})
                format_report = report.get('format', {})
                
                # 从 structure 中获取 titles（中文检测器可能将 titles 放在 structure 中）
                titles = structure_report.get('titles', [])
                logger.info(f"parse_issues_from_reports: Content 模块从 structure 获取 titles count: {len(titles)}")
                
                # 处理 format section
                if isinstance(format_report, dict) and not format_report.get('ok', False):
                    messages = format_report.get('messages', [])
                    logger.info(f"parse_issues_from_reports: Content 模块 format section 有 {len(messages)} 条消息")
                    
                    if messages:
                        # 中文检测器的消息格式是：标题"{text}"... 或 "  - 标题"{text}"..."
                        # 需要提取标题文本并匹配到对应的标题段落
                        title_issues = {}  # {title_text: [messages]}
                        
                        for msg in messages:
                            # 跳过 header 消息（如 "正文标题格式问题："）
                            if msg.strip().endswith('：') or msg.strip().endswith(':'):
                                continue
                            # 移除 "  - " 前缀
                            clean_msg = msg.strip()
                            if clean_msg.startswith('- '):
                                clean_msg = clean_msg[2:].strip()
                            
                            # 提取标题文本（支持中文双引号 "" 和英文引号 "'）
                            # 消息格式：标题"xxx"段前应为... 或 标题'xxx'段前应为...
                            # 中文双引号：左引号 " (U+201C)，右引号 " (U+201D)
                            # 使用字符类匹配所有可能的引号
                            title_match = re.search(r'标题[\u201C\u201D"\']([^\u201C\u201D"\']+)[\u201C\u201D"\']', clean_msg)
                            
                            if title_match:
                                title_text = title_match.group(1)
                                if title_text not in title_issues:
                                    title_issues[title_text] = []
                                title_issues[title_text].append(clean_msg)
                            else:
                                # 如果正则匹配失败，记录日志以便调试
                                logger.debug(f"parse_issues_from_reports: Content 模块无法提取标题文本，消息: {clean_msg[:50]}")
                        
                        logger.info(f"parse_issues_from_reports: Content 模块 format 提取到 {len(title_issues)} 个标题的问题")
                        logger.debug(f"parse_issues_from_reports: Content 模块提取的标题列表: {list(title_issues.keys())[:5]}...")  # 只显示前5个
                        logger.debug(f"parse_issues_from_reports: Content 模块 titles 列表中的标题: {[t.get('text', '')[:20] for t in titles[:5]]}...")  # 只显示前5个
                        
                        # 为每个标题创建批注
                        for title_text, title_messages in title_issues.items():
                            # 在 titles 列表中查找对应的标题
                            title_info = None
                            for t in titles:
                                title_in_report = t.get('text', '')
                                # 匹配标题文本（可能包含编号，所以使用包含匹配）
                                # 先尝试精确匹配，再尝试包含匹配
                                if title_in_report == title_text:
                                    title_info = t
                                    break
                                elif title_text in title_in_report or title_in_report in title_text:
                                    title_info = t
                                    break
                            
                            if title_info:
                                # 尝试多种方式获取段落索引
                                para_idx = (title_info.get('paragraph_index') or 
                                          title_info.get('para_idx') or
                                          title_info.get('index'))
                                
                                if para_idx is not None:
                                    clean_title = re.sub(r'[^\w]', '_', title_text[:20])
                                    issues.append({
                                        'module': module_name,
                                        'section': f'format_{clean_title}',
                                        'messages': title_messages,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                                    logger.info(f"parse_issues_from_reports: Content 模块添加标题格式问题 - title: {title_text}, para_idx: {para_idx}, 消息数: {len(title_messages)}")
                                else:
                                    # 如果没有索引，尝试用文本定位
                                    clean_title = re.sub(r'[^\w]', '_', title_text[:20])
                                    issues.append({
                                        'module': module_name,
                                        'section': f'format_{clean_title}',
                                        'messages': title_messages,
                                        'locate_method': 'text',
                                        'locate_data': title_text
                                    })
                                    logger.info(f"parse_issues_from_reports: Content 模块添加标题格式问题（文本定位，无索引） - title: {title_text}, 消息数: {len(title_messages)}")
                            elif title_text:
                                # 如果完全找不到匹配的标题，仍然尝试用文本定位
                                clean_title = re.sub(r'[^\w]', '_', title_text[:20])
                                issues.append({
                                    'module': module_name,
                                    'section': f'format_{clean_title}',
                                    'messages': title_messages,
                                    'locate_method': 'text',
                                    'locate_data': title_text
                                })
                                logger.warning(f"parse_issues_from_reports: Content 模块添加标题格式问题（文本定位，未在titles中找到） - title: {title_text}, 消息数: {len(title_messages)}")
                
                # 处理 structure section（如果有问题）
                if isinstance(structure_report, dict) and not structure_report.get('ok', False):
                    structure_messages = structure_report.get('messages', [])
                    if structure_messages:
                        # structure 问题通常定位到 Introduction
                        issues.append({
                            'module': module_name,
                            'section': 'structure',
                            'messages': structure_messages,
                            'locate_method': 'keyword',
                            'locate_data': 'Introduction'
                        })
                        logger.info(f"parse_issues_from_reports: Content 模块添加 structure 问题，消息数: {len(structure_messages)}")
                
                continue  # 跳过后续的英文检测器结构处理
            
            # 英文检测器的结构处理（原有逻辑）
            hierarchy_report = report.get('hierarchy', {})
            titles = report.get('titles', [])  # 获取标题信息用于定位
            logger.info(f"parse_issues_from_reports: Content 模块使用英文检测器结构，hierarchy keys: {list(hierarchy_report.keys()) if isinstance(hierarchy_report, dict) else 'not a dict'}, titles count: {len(titles)}")
            
            content_issue_count = 0
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details', 'hierarchy', 'titles']:
                    logger.debug(f"parse_issues_from_reports: Content 模块跳过 section {section_key}（在排除列表中）")
                    continue
                
                logger.info(f"parse_issues_from_reports: Content 模块检查 section {section_key}, 类型: {type(section_value)}, ok: {section_value.get('ok') if isinstance(section_value, dict) else 'N/A'}")
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    logger.info(f"parse_issues_from_reports: Content 模块 section {section_key} 有 {len(messages)} 条消息")
                    if not messages:
                        logger.debug(f"parse_issues_from_reports: Content 模块 section {section_key} 没有消息，跳过")
                        continue
                    
                    # 特殊处理content_format：按段落分组
                    if section_key == 'content_format':
                        logger.info(f"parse_issues_from_reports: Content 模块处理 content_format，消息数: {len(messages)}")
                        # 将消息按段落编号分组
                        grouped_messages = group_messages_by_paragraph(messages)
                        logger.info(f"parse_issues_from_reports: Content 模块 content_format 分组后: {list(grouped_messages.keys())}")
                        
                        # 为每个段落创建独立的批注issue
                        for para_num, para_messages in grouped_messages.items():
                            if para_num is not None:
                                # 有段落编号，需要定位到具体的正文段落
                                # 使用特殊的定位方法：content_paragraph
                                issues.append({
                                    'module': module_name,
                                    'section': f'{section_key}_para{para_num}',
                                    'messages': para_messages,
                                    'locate_method': 'content_paragraph',
                                    'locate_data': para_num,  # 段落编号（1-based）
                                    'extra': {
                                        'hierarchy_report': hierarchy_report  # 传递标题信息
                                    }
                                })
                                content_issue_count += 1
                                logger.info(f"parse_issues_from_reports: Content 模块添加问题 - section: {section_key}_para{para_num}, 消息数: {len(para_messages)}")
                            else:
                                logger.debug(f"parse_issues_from_reports: Content 模块 content_format 忽略无段落编号的消息: {para_messages[:1] if para_messages else 'empty'}")
                            # 忽略没有段落编号的消息（如标题行）
                    
                    elif section_key in ['format', 'case']:
                        logger.info(f"parse_issues_from_reports: Content 模块处理 {section_key}，消息数: {len(messages)}")
                        # 标题format和case问题：按标题分组定位
                        # 从messages中提取标题名称，定位到具体标题段落
                        grouped_title_messages = group_messages_by_title(messages, titles)
                        logger.info(f"parse_issues_from_reports: Content 模块 {section_key} 分组后标题数: {len(grouped_title_messages)}")
                        
                        for title_text, title_messages in grouped_title_messages.items():
                            if title_text and title_messages:
                                # 在titles列表中查找对应的标题
                                title_info = next((t for t in titles if t.get('text') == title_text), None)
                                if title_info and 'paragraph_index' in title_info:
                                    # 直接使用paragraph_index定位，更准确
                                    para_idx = title_info.get('paragraph_index')
                                    # 为每个标题创建单独的批注，使用唯一的section名称
                                    clean_title = re.sub(r'[^\w]', '_', title_text[:20])  # 清理标题用作section名称
                                    issues.append({
                                        'module': module_name,
                                        'section': f'{section_key}_{clean_title}',
                                        'messages': title_messages,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                                    content_issue_count += 1
                                    logger.info(f"parse_issues_from_reports: Content 模块添加问题 - section: {section_key}_{clean_title}, 消息数: {len(title_messages)}, para_idx: {para_idx}")
                                elif title_text:
                                    # 如果没有索引，尝试用完整标题文本（包括编号）定位
                                    full_title_text = title_info.get('full_text', title_text) if title_info else title_text
                                    clean_title = re.sub(r'[^\w]', '_', title_text[:20])
                                    issues.append({
                                        'module': module_name,
                                        'section': f'{section_key}_{clean_title}',
                                        'messages': title_messages,
                                        'locate_method': 'text',
                                        'locate_data': full_title_text
                                    })
                                    content_issue_count += 1
                                    logger.info(f"parse_issues_from_reports: Content 模块添加问题 - section: {section_key}_{clean_title}, 消息数: {len(title_messages)}, 使用文本定位")
                    else:
                        logger.info(f"parse_issues_from_reports: Content 模块处理其他 section {section_key}，消息数: {len(messages)}")
                        # 其他section（如hierarchy）使用Introduction定位
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': 'keyword',
                            'locate_data': 'Introduction'
                        })
                        content_issue_count += 1
                        logger.info(f"parse_issues_from_reports: Content 模块添加问题 - section: {section_key}, 消息数: {len(messages)}")
            
            logger.info(f"parse_issues_from_reports: Content 模块总共添加了 {content_issue_count} 个问题")
        
        elif module_name == 'Formula':
            # Formula模块：使用 chinese_annotation_engine 的 formula_adapter 处理
            # 这样可以正确区分：单独公式问题（在对应公式处）+ 连续性问题（在章节第一个公式处）
            from services.chinese_annotation_engine import formula_adapter
            formula_issues = formula_adapter({'Formula': report})
            for issue in formula_issues:
                # 将 Issue dataclass 转换为字典
                issues.append({
                    'module': issue.module,
                    'section': issue.section,
                    'messages': issue.messages,
                    'locate_method': issue.locate_method,
                    'locate_data': issue.locate_data,
                    'extra': issue.extra or {}
                })
        
        elif module_name == 'TOC':
            # TOC模块：处理目录/图录/表录的格式问题
            logger.info(f"parse_issues_from_reports: 开始处理 TOC 模块，report keys: {list(report.keys()) if isinstance(report, dict) else 'not a dict'}")
            
            # 处理 structure section
            structure_report = report.get('structure', {})
            if isinstance(structure_report, dict) and not structure_report.get('ok', False):
                structure_messages = structure_report.get('messages', [])
                if structure_messages:
                    # structure 问题定位到第一个找到的标题（目录、图录或表录）
                    titles = structure_report.get('titles', [])
                    if titles:
                        # 使用第一个标题的段落索引
                        first_title = titles[0]
                        # 优先使用 index（TOC 检测器返回的是 index，是 doc.paragraphs 的实际索引，包括空行）
                        para_idx = first_title.get('index') or first_title.get('paragraph_index') or first_title.get('para_idx')
                        if para_idx is not None:
                            issues.append({
                                'module': module_name,
                                'section': 'structure',
                                'messages': structure_messages,
                                'locate_method': 'index',
                                'locate_data': para_idx
                            })
                            logger.info(f"parse_issues_from_reports: TOC 模块添加 structure 问题，para_idx: {para_idx}, 消息数: {len(structure_messages)}")
                        else:
                            # 如果没有索引，使用关键字定位（目录、图录或表录）
                            title_type = first_title.get('title_type', '目录')
                            issues.append({
                                'module': module_name,
                                'section': 'structure',
                                'messages': structure_messages,
                                'locate_method': 'keyword',
                                'locate_data': title_type
                            })
                            logger.info(f"parse_issues_from_reports: TOC 模块添加 structure 问题（关键字定位），title_type: {title_type}, 消息数: {len(structure_messages)}")
            
            # 处理 format section（是一个列表）
            format_reports = report.get('format', [])
            if isinstance(format_reports, list):
                logger.info(f"parse_issues_from_reports: TOC 模块 format 列表长度: {len(format_reports)}")
                for fr in format_reports:
                    title_type = fr.get('title_type', '未知')
                    format_report = fr.get('report', {})
                    
                    if isinstance(format_report, dict) and not format_report.get('ok', False):
                        format_messages = format_report.get('messages', [])
                        # 过滤掉 header 消息（如 "目录格式问题："）
                        filtered_messages = []
                        for msg in format_messages:
                            # 跳过以 "：" 或 ":" 结尾的 header 消息
                            if not (msg.strip().endswith('：') or msg.strip().endswith(':')):
                                filtered_messages.append(msg)
                        
                        if filtered_messages:
                            # 从 structure 中查找对应标题的段落索引
                            titles = structure_report.get('titles', [])
                            title_info = None
                            for t in titles:
                                if t.get('title_type') == title_type:
                                    title_info = t
                                    break
                            
                            if title_info:
                                # 优先使用 index（TOC 检测器返回的是 index，是 doc.paragraphs 的实际索引，包括空行）
                                para_idx = title_info.get('index') or title_info.get('paragraph_index') or title_info.get('para_idx')
                                if para_idx is not None:
                                    issues.append({
                                        'module': module_name,
                                        'section': f'format_{title_type}',
                                        'messages': filtered_messages,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                                    logger.info(f"parse_issues_from_reports: TOC 模块添加格式问题 - title_type: {title_type}, para_idx: {para_idx}, 消息数: {len(filtered_messages)}")
                                else:
                                    # 使用关键字定位
                                    issues.append({
                                        'module': module_name,
                                        'section': f'format_{title_type}',
                                        'messages': filtered_messages,
                                        'locate_method': 'keyword',
                                        'locate_data': title_type
                                    })
                                    logger.info(f"parse_issues_from_reports: TOC 模块添加格式问题（关键字定位） - title_type: {title_type}, 消息数: {len(filtered_messages)}")
                            else:
                                # 如果找不到标题信息，使用关键字定位
                                issues.append({
                                    'module': module_name,
                                    'section': f'format_{title_type}',
                                    'messages': filtered_messages,
                                    'locate_method': 'keyword',
                                    'locate_data': title_type
                                })
                                logger.info(f"parse_issues_from_reports: TOC 模块添加格式问题（关键字定位，未找到标题） - title_type: {title_type}, 消息数: {len(filtered_messages)}")
        
        elif module_name == 'Table':
            # Table模块：定位到表格标题段落
            # 1. 处理numbering问题（表格编号连续性）- 按章节分别定位
            numbering_report = report.get('numbering', {})
            if isinstance(numbering_report, dict) and not numbering_report.get('ok', False):
                messages = numbering_report.get('messages', [])
                if messages:
                    # 获取所有表格及其章节信息
                    tables_report = report.get('tables', [])
                    chapter_first_table = {}  # 记录每个章节的第一个表格
                    
                    for table_item in tables_report:
                        chapter = table_item.get('chapter')
                        captions = table_item.get('captions', {})
                        cn_caption = captions.get('cn', {})
                        para_idx = cn_caption.get('paragraph_index')
                        
                        if chapter is not None and para_idx is not None:
                            if chapter not in chapter_first_table:
                                chapter_first_table[chapter] = para_idx
                    
                    # 按章节分别添加连续性问题
                    import re
                    for msg in messages:
                        # 提取章节号：支持 "第2章" 格式
                        ch_match = re.search(r'第(\d+)章', msg)
                        if ch_match:
                            ch = int(ch_match.group(1))
                            para_idx = chapter_first_table.get(ch)
                            
                            if para_idx is not None:
                                issues.append({
                                    'module': module_name,
                                    'section': f'第{ch}章编号连续性',
                                    'messages': [f"[编号问题] {msg}"],
                                    'locate_method': 'index',
                                    'locate_data': para_idx
                                })
                            else:
                                # 没找到对应章节的表格，使用关键词定位
                                issues.append({
                                    'module': module_name,
                                    'section': f'第{ch}章编号连续性',
                                    'messages': [f"[编号问题] {msg}"],
                                    'locate_method': 'keyword',
                                    'locate_data': '表'
                                })
                        else:
                            # 无法提取章节号，默认用关键词
                            issues.append({
                                'module': module_name,
                                'section': '编号连续性',
                                'messages': [f"[编号问题] {msg}"],
                                'locate_method': 'keyword',
                                'locate_data': '表'
                            })
            
            # 2. 处理每个表格的问题
            tables_report = report.get('tables', [])
            for i, table_report in enumerate(tables_report):
                caption_info = table_report.get('caption', {})
                caption_text = caption_info.get('text', f'Table {i+1}')
                
                # 检查标题格式
                caption_format = table_report.get('caption_format', {})
                if isinstance(caption_format, dict) and not caption_format.get('ok', False):
                    messages = caption_format.get('messages', [])
                    if messages:
                        issues.append({
                            'module': module_name,
                            'section': f'table{i+1}_caption',
                            'messages': messages,
                            'locate_method': 'keyword',
                            'locate_data': caption_text[:20]
                        })
                
                # 检查表格样式
                table_style = table_report.get('table_style', {})
                if isinstance(table_style, dict) and not table_style.get('ok', False):
                    messages = table_style.get('messages', [])
                    if messages:
                        issues.append({
                            'module': module_name,
                            'section': f'table{i+1}_style',
                            'messages': messages,
                            'locate_method': 'keyword',
                            'locate_data': caption_text[:20]
                        })
                
                # 检查表格对齐
                table_alignment = table_report.get('table_alignment', {})
                if isinstance(table_alignment, dict) and not table_alignment.get('ok', False):
                    messages = table_alignment.get('messages', [])
                    if messages:
                        issues.append({
                            'module': module_name,
                            'section': f'table{i+1}_alignment',
                            'messages': messages,
                            'locate_method': 'keyword',
                            'locate_data': caption_text[:20]
                        })
        
        elif module_name == 'Figure':
            # Figure模块：定位到图片标题段落（类似Table模块）
            # 1. 处理numbering问题（图片编号连续性）
            numbering_report = report.get('numbering', {})
            if isinstance(numbering_report, dict) and not numbering_report.get('ok', False):
                messages = numbering_report.get('messages', [])
                if messages:
                    # 定位到第一个图片标题
                    # 优先从 figures 列表中获取第一个有标题的图片
                    figures = report.get('figures', [])
                    first_caption_info = None
                    for fig_report in figures:
                        if fig_report.get('has_caption', False):
                            first_caption_info = fig_report.get('caption_info')
                            if first_caption_info:
                                break
                    
                    if first_caption_info:
                        # 优先使用段落索引
                        caption_para_idx = first_caption_info.get('paragraph_index')
                        if caption_para_idx is not None:
                            issues.append({
                                'module': module_name,
                                'section': 'numbering',
                                'messages': messages,
                                'locate_method': 'index',
                                'locate_data': caption_para_idx
                            })
                            logger.info(f"parse_issues_from_reports: Figure 模块添加编号问题，para_idx: {caption_para_idx}, 消息数: {len(messages)}")
                        else:
                            # 使用文本定位
                            caption_text = first_caption_info.get('full_text', 'Fig.')
                            issues.append({
                                'module': module_name,
                                'section': 'numbering',
                                'messages': messages,
                                'locate_method': 'text',
                                'locate_data': caption_text
                            })
                            logger.info(f"parse_issues_from_reports: Figure 模块添加编号问题（文本定位），消息数: {len(messages)}")
                    else:
                        # 备选方案：从 captions 列表获取
                        captions = report.get('captions', [])
                        if captions:
                            first_caption = captions[0]
                            caption_text = first_caption.get('full_text', 'Fig.')
                            issues.append({
                                'module': module_name,
                                'section': 'numbering',
                                'messages': messages,
                                'locate_method': 'text',
                                'locate_data': caption_text
                            })
                            logger.info(f"parse_issues_from_reports: Figure 模块添加编号问题（从captions列表，文本定位），消息数: {len(messages)}")
            
            # 2. 处理每张图片的问题（支持新的报告结构）
            figures = report.get('figures', [])
            for fig_report in figures:
                fig_idx = fig_report.get('figure_index', 0)
                para_idx = fig_report.get('paragraph_index', 0)
                
                # 获取标题信息（如果有）
                has_caption = fig_report.get('has_caption', False)
                caption_info = fig_report.get('caption_info') if has_caption else None
                
                # 标题相关的问题 → 批注在标题段落
                caption_messages = []
                format_check = fig_report.get('format_check', {})
                if isinstance(format_check, dict) and not format_check.get('ok', False):
                    caption_messages.extend(format_check.get('messages', []))
                
                if caption_messages and has_caption:
                    # 批注在标题上
                    # 优先使用段落索引定位（更准确）
                    caption_para_idx = caption_info.get('paragraph_index')
                    if caption_para_idx is not None:
                        issues.append({
                            'module': module_name,
                            'section': f'figure{fig_idx}_caption',
                            'messages': caption_messages,
                            'locate_method': 'index',
                            'locate_data': caption_para_idx
                        })
                        logger.info(f"parse_issues_from_reports: Figure 模块添加标题格式问题 - figure{fig_idx}, para_idx: {caption_para_idx}, 消息数: {len(caption_messages)}")
                    else:
                        # 如果没有段落索引，使用文本定位（比关键字定位更准确）
                        caption_text = caption_info.get('full_text', f'Fig.{caption_info.get("number", fig_idx)}')
                        issues.append({
                            'module': module_name,
                            'section': f'figure{fig_idx}_caption',
                            'messages': caption_messages,
                            'locate_method': 'text',
                            'locate_data': caption_text
                        })
                        logger.info(f"parse_issues_from_reports: Figure 模块添加标题格式问题（文本定位） - figure{fig_idx}, 消息数: {len(caption_messages)}")
                
                # 图片本身的问题 → 批注在图片段落
                picture_messages = []
                
                # 图片对齐等问题
                picture_check = fig_report.get('picture_check', {})
                if isinstance(picture_check, dict) and not picture_check.get('ok', False):
                    picture_messages.extend(picture_check.get('messages', []))
                
                # 图表内容问题
                content_check = fig_report.get('content_check', {})
                if isinstance(content_check, dict) and not content_check.get('ok', False):
                    if content_check.get('is_chart', False):
                        picture_messages.extend(content_check.get('messages', []))
                
                if picture_messages:
                    # 批注在图片段落（使用段落索引）
                    issues.append({
                        'module': module_name,
                        'section': f'figure{fig_idx}_picture',
                        'messages': picture_messages,
                        'locate_method': 'index',
                        'locate_data': para_idx
                    })
    
        elif module_name == 'Chinese_section':
            # 为中文部分的每个子项添加精确定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'affiliations_detail'] or not isinstance(section_value, dict) or section_value.get('ok', True):
                    continue

                messages = section_value.get('messages', [])
                if not messages:
                    continue

                locate_method = 'keyword'
                locate_data = ''

                if section_key == 'chinese_title_format':
                    # 从报告的 'details' 中获取标题文本用于定位
                    title_text = report.get('details', {}).get('title_text', '')
                    locate_data = title_text[:30] if title_text else '用于高效电催化析氢反应'
                elif section_key == 'chinese_author_format':
                    locate_data = '刘   影'
                elif section_key == 'chinese_affiliation_format':
                    locate_data = '东华大学'
                elif section_key == 'chinese_abstract_format':
                    locate_data = '摘   要'
                elif section_key == 'chinese_keywords_format':
                    locate_data = '关键词'

                if locate_data:
                    issues.append({
                        'module': module_name,
                        'section': section_key,
                        'messages': messages,
                        'locate_method': locate_method,
                        'locate_data': locate_data
                    })

    # 单独处理分类号不一致的批注
    if 'Classification' in all_reports:
        class_report = all_reports['Classification']
        if class_report.get('match_status') == '不一致':
            messages = [
                f"API建议分类号与原文不一致。",
                f"原文分类号: {class_report.get('original_clc', 'N/A')}",
                f"API建议分类号: {class_report.get('code', 'N/A')} (原始: {class_report.get('raw_code', 'N/A')})",
                "请根据API提供的分类理由进行核对。"
            ]
            issues.append({
                'module': 'Classification',
                'section': 'mismatch',
                'messages': messages,
                'locate_method': 'keyword',
                'locate_data': 'CLC number'
            })

    logger.info(f"parse_issues_from_reports: 总共识别出 {len(issues)} 个问题")
    return issues


def add_all_comments(doc_path, copy_path, issues_list):
    """
    在文档副本上添加所有批注
    
    参数：
        doc_path: 原始文档路径（用于对比）
        copy_path: 副本文档路径
        issues_list: 问题列表
    
    返回：
        成功添加的批注数量
    """
    try:
        doc = Document(copy_path)
        comment_count = 0
        
        print(f"\n正在添加批注...")
        print(f"  共有 {len(issues_list)} 个问题需要批注")
        
        for issue in issues_list:
            module_name = issue['module']
            section_name = issue['section']
            messages = issue['messages']
            locate_method = issue['locate_method']
            locate_data = issue['locate_data']
            extra = issue.get('extra', {})
            
            # 根据定位方法查找段落
            paragraph = None
            if locate_method == 'keyword' and locate_data:
                paragraph = find_paragraph_by_keyword(doc, locate_data)
            elif locate_method == 'abstract_title':
                cfg = ANNOTATION_KEYWORDS.get("abstract", {})
                for kw in cfg.get("title_keywords", []):
                    paragraph = find_paragraph_by_keyword(doc, kw)
                    if paragraph:
                        break
                if not paragraph and cfg.get("title_regex"):
                    paragraph = find_paragraph_by_regex(doc, cfg["title_regex"], re.IGNORECASE)
            elif locate_method == 'abstract_content':
                cfg = ANNOTATION_KEYWORDS.get("abstract", {})
                # 先通过标题关键词/正则定位标题
                title_para = None
                for kw in cfg.get("title_keywords", []):
                    title_para = find_paragraph_by_keyword(doc, kw)
                    if title_para:
                        break
                if not title_para and cfg.get("title_regex"):
                    title_para = find_paragraph_by_regex(doc, cfg["title_regex"], re.IGNORECASE)
                # 若找到标题且需要取标题后的正文
                if title_para and cfg.get("content_follow_title", True):
                    for i, para in enumerate(doc.paragraphs):
                        if para is title_para:
                            for j in range(i + 1, min(i + 3, len(doc.paragraphs))):
                                if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
                                    paragraph = doc.paragraphs[j]
                                    break
                            break
                # 若标题未找到，直接按关键词再次尝试正文匹配
                if not paragraph:
                    for kw in cfg.get("title_keywords", []):
                        paragraph = find_paragraph_by_keyword(doc, kw)
                        if paragraph:
                            break
                    if not paragraph and cfg.get("title_regex"):
                        paragraph = find_paragraph_by_regex(doc, cfg["title_regex"], re.IGNORECASE)
            elif locate_method == 'keywords_title':
                cfg = ANNOTATION_KEYWORDS.get("keywords", {})
                for kw in cfg.get("title_keywords", []):
                    paragraph = find_paragraph_by_keyword(doc, kw)
                    if paragraph:
                        break
                if not paragraph and cfg.get("title_regex"):
                    paragraph = find_paragraph_by_regex(doc, cfg["title_regex"], re.IGNORECASE)
            elif locate_method == 'keywords_content':
                cfg = ANNOTATION_KEYWORDS.get("keywords", {})
                title_para = None
                for kw in cfg.get("title_keywords", []):
                    title_para = find_paragraph_by_keyword(doc, kw)
                    if title_para:
                        break
                if not title_para and cfg.get("title_regex"):
                    title_para = find_paragraph_by_regex(doc, cfg["title_regex"], re.IGNORECASE)
                if title_para and cfg.get("content_follow_title", True):
                    for i, para in enumerate(doc.paragraphs):
                        if para is title_para:
                            for j in range(i + 1, min(i + 3, len(doc.paragraphs))):
                                if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
                                    paragraph = doc.paragraphs[j]
                                    break
                            break
                if not paragraph:
                    for kw in cfg.get("title_keywords", []):
                        paragraph = find_paragraph_by_keyword(doc, kw)
                        if paragraph:
                            break
                    if not paragraph and cfg.get("title_regex"):
                        paragraph = find_paragraph_by_regex(doc, cfg["title_regex"], re.IGNORECASE)
            elif locate_method == 'index':
                # 判断是否需要跳过空行
                # 单位段落、Content标题格式批注、TOC格式批注、Figure批注和Title批注都不应该跳过空行（使用实际索引）
                skip_empty = ('affiliation_para' not in section_name and 
                             'Content-format' not in f"{module_name}-{section_name}" and 
                             'Content-case' not in f"{module_name}-{section_name}" and
                             module_name != 'TOC' and 
                             module_name != 'Figure' and
                             module_name != 'Title')  # TOC、Figure 和 Title 模块不跳过空行，确保准确定位到标题所在行
                paragraph = find_paragraph_by_index(doc, locate_data, skip_empty=skip_empty)
            elif locate_method == 'text':
                paragraph = find_paragraph_by_text(doc, locate_data)
            elif locate_method == 'paragraph_object':
                paragraph = locate_data  # 直接使用paragraph对象
            elif locate_method == 'content_paragraph':
                # 定位到具体的正文段落
                hierarchy_report = extra.get('hierarchy_report', {})
                paragraph = find_content_paragraph_by_number(doc, locate_data, hierarchy_report)
            elif locate_method == 'formula_number':
                # 通过公式编号定位（如 "(2)"）
                paragraph = find_paragraph_by_keyword(doc, locate_data)
            elif locate_method == 'title_by_abstract':
                # 根据摘要位置定位标题（避免定位到封面标题）
                language = locate_data if isinstance(locate_data, str) else 'chinese'
                paragraph = find_title_by_abstract(doc, language)
                if not paragraph:
                    logger.warning(f"无法通过摘要位置定位标题（语言: {language}），尝试使用文本定位")
                    # 如果找不到，尝试使用文本定位作为备选
                    # 这里可以从报告中获取标题文本，但为了简化，我们使用关键字定位
                    if language == 'chinese':
                        # 尝试查找包含中文的段落（可能是标题）
                        for para in doc.paragraphs:
                            if para.text and re.search(r'[\u4e00-\u9fff]', para.text):
                                # 检查是否在摘要之前
                                para_idx = None
                                abstract_idx = None
                                for idx, p in enumerate(doc.paragraphs):
                                    if p is para:
                                        para_idx = idx
                                    if p.text and ('摘 要' in p.text or '摘要' in p.text):
                                        abstract_idx = idx
                                        break
                                if para_idx is not None and abstract_idx is not None and para_idx < abstract_idx:
                                    paragraph = para
                                    break
                    else:
                        # 英文标题：查找全大写的段落
                        for para in doc.paragraphs:
                            if para.text and para.text.strip():
                                text = para.text.strip()
                                if re.search(r'[A-Z]', text) and text.isupper():
                                    # 检查是否在 Abstract 之前
                                    para_idx = None
                                    abstract_idx = None
                                    for idx, p in enumerate(doc.paragraphs):
                                        if p is para:
                                            para_idx = idx
                                        if p.text and re.match(r'^\s*Abstract\s*$', p.text, re.IGNORECASE):
                                            abstract_idx = idx
                                            break
                                    if para_idx is not None and abstract_idx is not None and para_idx < abstract_idx:
                                        paragraph = para
                                        break
            
            if paragraph:
                # 构建批注内容
                comment_text = f"[{module_name}-{section_name}]\n"
                for msg in messages:
                    comment_text += f"• {msg}\n"
                
                # 添加批注
                if add_comment_to_paragraph(doc, paragraph, comment_text.strip()):
                    comment_count += 1
                    print(f"  ✓ 已添加批注: {module_name}-{section_name}")
            else:
                print(f"  ✗ 无法定位段落: {module_name}-{section_name} (方法:{locate_method}, 数据:{locate_data})")
        
        # 保存文档
        doc.save(copy_path)
        print(f"\n✓ 成功添加 {comment_count} 个批注")
        print(f"✓ 批注文档已保存: {copy_path}")
        
        return comment_count
    
    except Exception as e:
        print(f"\n✗ 添加批注过程出错: {e}")
        return 0


def generate_annotated_document(docx_path: str, all_reports: Dict[str, Any], output_dir: str) -> Optional[str]:
    """
    生成带批注的文档
    
    参数：
        docx_path: 原始文档路径
        all_reports: 所有检测报告
        output_dir: 输出目录
    
    返回：
        批注文档的路径，失败返回None
    """
    try:
        # 创建文档副本
        copy_path = create_document_copy(docx_path, output_dir)
        if not copy_path:
            return None
        
        # 从报告中提取问题
        issues_list = parse_issues_from_reports(all_reports)
        logger.info(f"共识别出 {len(issues_list)} 个问题")
        
        # 添加批注
        if issues_list:
            comment_count = add_all_comments(docx_path, copy_path, issues_list)
            if comment_count > 0:
                logger.info(f"批注添加完成！共添加 {comment_count} 个批注")
                return copy_path
            else:
                logger.warning("未能添加任何批注")
                return copy_path
        else:
            logger.info("未发现问题，无需添加批注")
            return copy_path
    
    except Exception as e:
        logger.error(f"生成批注文档失败: {e}")
        return None

