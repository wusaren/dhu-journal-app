#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文论文图片格式检测器
检测中文论文中图片的格式是否符合要求
"""

import os
import sys
import json
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn

# ---------- 文本规范化 ----------
def normalize_caption_text(text: str) -> str:
    """
    清理Word里常见的不可见字符/特殊空格，避免正则匹配失败。
    - LRM/RLM: \u200e/\u200f
    - Zero-width space/joiner/non-joiner: \u200b/\u200c/\u200d
    - BOM: \ufeff
    - NBSP: \u00a0
    """
    if not text:
        return ""
    # 替换常见不可见字符为空
    text = re.sub(r'[\u200e\u200f\u200b\u200c\u200d\ufeff]', '', text)
    # NBSP 归一成普通空格
    text = text.replace('\u00a0', ' ')
    # 连续空白归一
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# 添加项目根目录到路径，以便导入模块
if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

def should_skip_check(check_name):
    """
    判断是否应该跳过某个检测项
    参数:
        check_name: 检测项名称 (font_size, bold, italic, alignment, spacing, indent)
    返回:
        bool: True表示跳过该检测项，False表示执行该检测项
    """
    global _skip_checks_config
    if _skip_checks_config is None:
        return False
    return check_name in _skip_checks_config

# 全局变量，用于存储当前模块的跳过检测项配置
_skip_checks_config = []

"""
=== 论文格式检测系统 - 中文论文图片检测器 ===

【图片检测 (Figure Detection for Chinese Papers)】

1. 【图片标题格式检测】
   - 中文格式：图X-Y 标题(来源于xxxxxx)（如：图2-1 胶原蛋白化学结构式(来源于xxxxxx)）
   - 英文格式：FigX-Y Title (Origin from xxxx)（如：Fig2-1 The chemical structural formula of collagen (Origin from xxxx)）
   - 标题居中对齐
   - 标题字体：中文为宋体，英文为Times New Roman，五号(10.5pt)
   - 单倍行距
   - 图片编号应连续递增

2. 【图片位置关系检测】
   - 图片应居中对齐
   - 标题位于图片下方
   - 图片与标题间隔合理
   - 图题与正文之间空一行

3. 【图片编号检测】
   - 编号从1开始
   - 编号连续递增（图1-1, 图1-2, 图2-1... 或 Fig1-1, Fig1-2, Fig2-1...）
"""

# ---------- 模板加载 ----------
def resolve_template_path(identifier):
    """解析模板路径，支持文件路径和模板名称"""
    if os.path.isfile(identifier):
        return identifier
    
    current_dir = Path(__file__).parent
    candidates = [
        os.path.join("templates", identifier + ".json"),
        os.path.join("Chinese_paper_detect_templates", identifier + ".json"),
        os.path.join("services", "Chinese_paper_detect_templates", identifier + ".json"),
        str(current_dir.parent / "Chinese_paper_detect_templates" / (identifier + ".json")),
        str(current_dir / ".." / "Chinese_paper_detect_templates" / (identifier + ".json")),
    ]
    
    for candidate in candidates:
        abs_path = os.path.abspath(candidate)
        if os.path.isfile(abs_path):
            return abs_path
        if os.path.isfile(candidate):
            return candidate
    
    raise FileNotFoundError(f"Template not found: '{identifier}' (tried file path and {candidates})")

def load_template(identifier):
    """加载JSON模板文件"""
    tpl_path = resolve_template_path(identifier)
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = json.load(f)
    return tpl

# ---------- 字体检测函数 ----------
def detect_font_for_run(run, paragraph=None):
    """
    更健壮的字体检测函数，同时检查直接格式和段落样式，支持中英文字体分别检测。
    返回 (font_size_pt, font_name_ascii, font_name_eastasia, is_bold, is_italic, line_spacing)
    """
    font_size = None
    font_name_ascii = None
    font_name_eastasia = None
    is_bold = None
    is_italic = False
    line_spacing = 1.0
    
    if not run:
        return 12.0, "Times New Roman", "宋体", False, False, 1.0
    
    # 1. 检测字号
    try:
        if run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)
        
        if font_size is None and run and hasattr(run._element, 'rPr'):
            sz_nodes = run._element.xpath('.//w:sz')
            if sz_nodes and sz_nodes[0].get(qn('w:val')):
                font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
        
        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style.font, 'size') and hasattr(paragraph.style.font.size, 'pt'):
            font_size = float(paragraph.style.font.size.pt)
            
        if font_size is None and paragraph and hasattr(paragraph.style, 'element'):
            sz_nodes = paragraph.style.element.xpath('.//w:sz')
            if sz_nodes and sz_nodes[0].get(qn('w:val')):
                font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
    except Exception:
        pass
    
    font_size = font_size if font_size is not None else 12.0
    
    # 2. 检测英文字体（ASCII）和中文字体（EastAsia）
    try:
        if run.font and run.font.name:
            font_name_ascii = run.font.name
        
        if hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                rfonts = rpr.find(qn('w:rFonts'))
                if rfonts is not None:
                    xml_ascii = rfonts.get(qn('w:ascii'))
                    xml_hansi = rfonts.get(qn('w:hAnsi'))
                    xml_eastasia = rfonts.get(qn('w:eastAsia'))
                    
                    if xml_ascii:
                        font_name_ascii = xml_ascii
                    elif xml_hansi and font_name_ascii is None:
                        font_name_ascii = xml_hansi
                    
                    if xml_eastasia:
                        font_name_eastasia = xml_eastasia
                    elif xml_hansi and font_name_eastasia is None:
                        font_name_eastasia = xml_hansi
    except Exception:
        pass
    
    font_name_ascii = font_name_ascii if font_name_ascii else "Times New Roman"
    font_name_eastasia = font_name_eastasia if font_name_eastasia else "宋体"
    
    # 3. 检测加粗和斜体
    try:
        if run.font:
            if run.font.bold is not None:
                is_bold = run.font.bold
            if run.font.italic is not None:
                is_italic = run.font.italic
        
        if is_bold is None and getattr(run, "style", None) and getattr(run.style, "font", None):
            try:
                if run.style.font.bold is not None:
                    is_bold = run.style.font.bold
            except Exception:
                pass
        
        if is_bold is None and paragraph and paragraph.style and getattr(paragraph.style, "font", None):
            try:
                if paragraph.style.font.bold is not None:
                    is_bold = paragraph.style.font.bold
            except Exception:
                pass
        
        if is_bold is None and hasattr(run._element, 'rPr'):
            try:
                b_nodes = run._element.xpath('.//w:b')
                if b_nodes:
                    is_bold = True
            except Exception:
                pass
        
        is_bold = bool(is_bold) if is_bold is not None else False
        is_italic = bool(is_italic)
    except Exception:
        pass
    
    # 4. 行间距检测
    try:
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
        elif paragraph and paragraph.style and paragraph.style.paragraph_format.line_spacing:
            line_spacing = float(paragraph.style.paragraph_format.line_spacing)
    except Exception:
        pass
    
    return font_size, font_name_ascii, font_name_eastasia, is_bold, is_italic, line_spacing

def get_font_size(pt_size, tpl=None):
    """获取字体大小的中文名称"""
    if tpl and 'check_rules' in tpl and 'font_size_mapping' in tpl['check_rules']:
        size_config = tpl['check_rules']['font_size_mapping']
        size_map = {}
        for key, value in size_config.items():
            try:
                size_map[float(key)] = value
            except (ValueError, TypeError):
                continue
    else:
        size_map = {
            9: "小五", 10.5: "五号", 12: "小四", 14: "四号",
            16: "三号", 18: "小二", 22: "二号", 24: "小一", 26: "一号"
        }
    
    if not size_map:
        return f"{pt_size}pt"
    
    closest_size = min(size_map.keys(), key=lambda x: abs(x - pt_size))
    return size_map[closest_size]

def get_line_spacing_name(spacing, tpl=None):
    """行间距转换为中文描述"""
    if tpl and 'check_rules' in tpl and 'line_spacing_mapping' in tpl['check_rules']:
        spacing_config = tpl['check_rules']['line_spacing_mapping']
        spacing_map = {}
        for key, value in spacing_config.items():
            try:
                spacing_map[float(key)] = value
            except (ValueError, TypeError):
                continue
    else:
        spacing_map = {
            1.0: "单倍行距", 1.15: "1.15倍行距", 
            1.25: "1.25倍行距", 1.5: "1.5倍行距", 2.0: "双倍行距"
        }
    
    if not spacing_map:
        return f"{spacing}倍行距"
    
    closest_spacing = min(spacing_map.keys(), key=lambda x: abs(x - spacing))
    return spacing_map[closest_spacing]

# ---------- 段落对齐检测函数 ----------
def detect_paragraph_alignment(paragraph):
    """
    改进的段落对齐检测，按照明确的优先级处理直接格式和样式格式
    """
    # 优先级1: 检查直接格式
    direct_alignment = paragraph.paragraph_format.alignment
    if direct_alignment is not None:
        return int(direct_alignment)
    
    # 优先级2: 如果直接格式为None，检查样式格式（包括继承链）
    if paragraph.style:
        try:
            style_alignment = paragraph.style.paragraph_format.alignment
            if style_alignment is not None:
                return int(style_alignment)
            
            # 如果当前样式没有对齐设置，检查样式继承链
            current_style = paragraph.style
            visited = set()
            
            while current_style and current_style.style_id not in visited:
                visited.add(current_style.style_id)
                
                if current_style.element.pPr is not None:
                    pPr = current_style.element.pPr
                    jc_elements = pPr.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
                    if jc_elements:
                        val = jc_elements[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                        if val == 'center':
                            return 1
                        elif val == 'right':
                            return 2
                        elif val == 'both':
                            return 3
                        elif val == 'left':
                            return 0
                
                # 获取基础样式
                try:
                    if current_style.element.pPr is not None:
                        basedOn = current_style.element.pPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}basedOn')
                        if basedOn is None:
                            basedOn = current_style.element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}basedOn')
                        
                        if basedOn is not None:
                            base_id = basedOn.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            found = False
                            for s in paragraph.part.document.styles:
                                if s.style_id == base_id:
                                    current_style = s
                                    found = True
                                    break
                            if not found:
                                break
                        else:
                            break
                    else:
                        break
                except Exception:
                    break
        except Exception:
            pass
    
    return 0  # 默认左对齐

# ---------- 图片检测核心函数 ----------
def has_picture_object(paragraph):
    """
    检测段落是否包含图片对象
    支持现代格式(w:drawing)、旧格式(w:pict)和VML格式(v:imagedata)
    """
    try:
        para_xml = paragraph._element
        
        namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'v': 'urn:schemas-microsoft-com:vml',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'
        }
        
        # 检查现代Word格式的图片（w:drawing）
        drawings = para_xml.xpath('.//w:drawing', namespaces=namespaces)
        if drawings:
            return True
        
        # 检查旧格式的图片（w:pict）
        pictures = para_xml.xpath('.//w:pict', namespaces=namespaces)
        if pictures:
            return True
        
        # 检查VML格式的图片（v:imagedata）
        imagedata = para_xml.xpath('.//v:imagedata', namespaces=namespaces)
        if imagedata:
            return True
        
        # 检查图片元素（a:blip）
        blips = para_xml.xpath('.//a:blip', namespaces=namespaces)
        if blips:
            return True
            
    except Exception:
        try:
            for elem in para_xml.iter():
                tag = elem.tag
                if any(keyword in tag.lower() for keyword in ['drawing', 'pict', 'imagedata', 'blip']):
                    return True
        except Exception:
            pass
    
    return False

def find_abstract_position(doc, tpl=None):
    """
    查找文档中"摘要"字段的位置
    优先使用 Abstract_detect 模块的方法，如果无法导入则使用备用方法
    返回：摘要段落的索引，如果未找到则返回None
    """
    # 尝试使用 Abstract_detect 模块的方法（更准确，支持模板配置）
    try:
        # 尝试导入 Abstract_detect 模块（同目录下的模块）
        check_abstract_structure = None
        
        # 方法1: 尝试相对导入（适用于作为包的一部分）
        try:
            from .Abstract_detect import check_abstract_structure
        except (ImportError, ValueError, AttributeError):
            # 方法2: 尝试绝对导入（添加当前目录到路径）
            current_dir = Path(__file__).parent
            if str(current_dir) not in sys.path:
                sys.path.insert(0, str(current_dir))
            try:
                import Abstract_detect
                check_abstract_structure = Abstract_detect.check_abstract_structure
            except ImportError:
                # 方法3: 尝试从 services 包导入
                try:
                    from services.Chinese_paper_detect.Abstract_detect import check_abstract_structure
                except ImportError:
                    pass
        
        if check_abstract_structure and tpl:
            # 使用 Abstract_detect 的方法查找摘要
            structure_report = check_abstract_structure(doc, tpl)
            if structure_report.get('title_paragraph_index') is not None:
                return structure_report['title_paragraph_index']
    except Exception as e:
        # 如果使用 Abstract_detect 方法失败，使用备用方法
        pass
    
    # 备用方法：简单的关键词匹配（向后兼容）
    abstract_keywords = ['摘要', 'Abstract', 'ABSTRACT', 'abstract']
    
    for idx, paragraph in enumerate(doc.paragraphs):
        text = normalize_caption_text(paragraph.text).strip()
        if not text:
            continue
        
        # 检查是否完全匹配或作为独立词出现（前后有空格或标点）
        for keyword in abstract_keywords:
            # 完全匹配
            if text == keyword:
                return idx
            # 作为独立词出现（前后有空格、标点或行首/行尾）
            pattern = rf'^\s*{re.escape(keyword)}\s*[：:。.，,；;]?\s*$'
            # 对于英文关键词使用IGNORECASE，对于中文不使用
            if keyword == '摘要':
                if re.match(pattern, text):
                    return idx
            else:
                if re.match(pattern, text, re.IGNORECASE):
                    return idx
    
    return None

def find_picture_captions(doc, tpl):
    """
    识别文档中的图片标题（支持中英文两种格式）
    返回：图片标题段落列表，每个元素包含段落对象、编号、标题文本、语言类型
    """
    # 中文圖題：同時支持「图」「圖」，連接符支持 - — －，圖後與數字前後空格均可選
    connector_chars = r'[-—－]'
    caption_pattern_chinese = tpl.get('figure_detection_rules', {}).get(
        'caption_pattern_chinese',
        fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
    )
    caption_pattern_english = tpl.get('figure_detection_rules', {}).get('caption_pattern_english', r'^\s*Fig\s(\d+)-(\d+)\s+(.+)$')
    captions = []
    
    for idx, paragraph in enumerate(doc.paragraphs):
        text = normalize_caption_text(paragraph.text)
        if not text:
            continue
        
        # 先尝试匹配中文格式
        match = re.match(caption_pattern_chinese, text)
        # 如果模板模式不匹配，尝试更灵活的模式（图/圖后空格可选，连接符可为- — －，两侧空格可选）
        if not match:
            flexible_pattern = fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
            match = re.match(flexible_pattern, text)
        # 如果还不匹配，尝试更宽松的模式（数字和标题之间空格可选，但至少需要一个字符）
        if not match:
            very_flexible_pattern = fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
            match = re.match(very_flexible_pattern, text)
            if match and not match.group(3).strip():
                match = None  # 确保标题部分不为空
        if match:
            chapter_num = int(match.group(1))
            figure_num = int(match.group(2))
            figure_title = match.group(3).strip()
            if figure_title:
                captions.append({
                    'paragraph': paragraph,
                    'paragraph_index': idx,
                    'chapter': chapter_num,
                    'number': figure_num,
                    'title': figure_title,
                    'full_text': text,
                    'language': 'chinese',
                    'full_number': f"{chapter_num}-{figure_num}"
                })
                continue
        
        # 再尝试匹配英文格式
        match = re.match(caption_pattern_english, text, re.IGNORECASE)
        if match:
            chapter_num = int(match.group(1))
            figure_num = int(match.group(2))
            figure_title = match.group(3).strip()
            if figure_title:
                captions.append({
                    'paragraph': paragraph,
                    'paragraph_index': idx,
                    'chapter': chapter_num,
                    'number': figure_num,
                    'title': figure_title,
                    'full_text': text,
                    'language': 'english',
                    'full_number': f"{chapter_num}-{figure_num}"
                })
    
    return captions

def find_picture_before_caption(doc, caption_info):
    """
    在标题上方查找对应的图片
    返回：包含图片的段落对象或None
    """
    caption_idx = caption_info['paragraph_index']
    max_distance = 2  # 最多向上查找2个段落
    
    for i in range(caption_idx - 1, max(0, caption_idx - max_distance - 1), -1):
        if i < 0 or i >= len(doc.paragraphs):
            continue
        
        paragraph = doc.paragraphs[i]
        if has_picture_object(paragraph):
            return paragraph
    
    return None

def check_blank_line_after_caption(doc, caption_info, tpl):
    """
    检查图题与正文之间的空行数
    返回: {'ok': bool, 'message': str}
    """
    structure_rules = tpl.get('figure_detection_rules', {}).get('position_relationship', {})
    expected_blank_lines = structure_rules.get('blank_line_after_caption', 1)
    
    caption_idx = caption_info['paragraph_index']
    
    # 从标题后开始查找，跳过空段落
    blank_count = 0
    first_content_idx = None
    
    for i in range(caption_idx + 1, len(doc.paragraphs)):
        para = doc.paragraphs[i]
        text = para.text.strip() if para.text else ''
        
        # 跳过图片段落
        if has_picture_object(para):
            continue
        
        if not text:
            blank_count += 1
        else:
            first_content_idx = i
            break
    
    # 如果找到了内容，检查空行数
    if first_content_idx is not None:
        if blank_count == expected_blank_lines:
            msg_tpl = tpl.get('messages', {}).get('blank_line_after_caption_ok', '图题与正文之间空行正确')
            return {'ok': True, 'message': msg_tpl}
        else:
            msg_tpl = tpl.get('messages', {}).get('blank_line_after_caption_error', '图题与正文之间应空一行，实际为空{actual}行')
            return {'ok': False, 'message': msg_tpl.format(actual=blank_count)}
    else:
        # 没有找到内容，可能是文档末尾
        return {'ok': True, 'message': '图题后没有找到正文内容'}

def check_picture_alignment(picture_paragraph):
    """
    检查图片段落的对齐方式
    返回：(is_centered, actual_alignment)
    """
    if not picture_paragraph:
        return False, None
    
    actual_alignment = detect_paragraph_alignment(picture_paragraph)
    is_centered = (actual_alignment == 1)
    
    return is_centered, actual_alignment

def check_figure_reference(doc, caption_info, pic_index, tpl):
    """
    检查图片是否在文档中被引用
    在图片上方和下方的一定范围内查找引用文本
    支持中文引用格式：如图X-Y所示、见图X-Y、如图X-Y、图X-Y所示等
    支持英文引用格式：As shown in Fig X-Y、See Fig X-Y、Fig X-Y shows等
    
    参数:
        doc: Word文档对象
        caption_info: 图片标题信息（包含full_number、language等）
        pic_index: 图片段落索引
        tpl: 模板配置
    
    返回: {'ok': bool, 'messages': [], 'reference_found': bool, 'reference_text': str}
    """
    report = {'ok': True, 'messages': [], 'reference_found': False, 'reference_text': ''}
    
    if not caption_info:
        # 如果没有标题信息，无法检测引用
        report['ok'] = False
        report['messages'].append('无法检测引用：图片缺少标题信息')
        return report
    
    full_number = caption_info.get('full_number', '')
    language = caption_info.get('language', 'chinese')
    
    if not full_number:
        report['ok'] = False
        report['messages'].append('无法检测引用：图片编号信息缺失')
        return report
    
    # 解析编号（格式：chapter-figure）
    parts = full_number.split('-')
    if len(parts) != 2:
        report['ok'] = False
        report['messages'].append(f'无法检测引用：图片编号格式错误（{full_number}）')
        return report
    
    chapter_num = parts[0]
    figure_num = parts[1]
    
    # 构建引用模式
    connector_chars = r'[-—－]'
    
    if language == 'chinese':
        # 中文引用模式：如图X-Y所示、见图X-Y、如图X-Y、图X-Y所示、图X-Y等
        reference_patterns = [
            fr'如图\s*{chapter_num}\s*{connector_chars}\s*{figure_num}\s*所示',
            fr'见图\s*{chapter_num}\s*{connector_chars}\s*{figure_num}',
            fr'如图\s*{chapter_num}\s*{connector_chars}\s*{figure_num}',
            fr'图\s*{chapter_num}\s*{connector_chars}\s*{figure_num}\s*所示',
            fr'图\s*{chapter_num}\s*{connector_chars}\s*{figure_num}',
            fr'[图圖]\s*{chapter_num}\s*{connector_chars}\s*{figure_num}',
        ]
    else:
        # 英文引用模式：As shown in Fig X-Y、See Fig X-Y、Fig X-Y shows等（英文通常只用"-"）
        reference_patterns = [
            fr'As\s+shown\s+in\s+Fig\s+{chapter_num}\s*-\s*{figure_num}',
            fr'See\s+Fig\s+{chapter_num}\s*-\s*{figure_num}',
            fr'Fig\s+{chapter_num}\s*-\s*{figure_num}\s+shows',
            fr'Fig\s+{chapter_num}\s*-\s*{figure_num}',
            fr'Figure\s+{chapter_num}\s*-\s*{figure_num}',
            fr'as\s+shown\s+in\s+fig\s+{chapter_num}\s*-\s*{figure_num}',
            fr'see\s+fig\s+{chapter_num}\s*-\s*{figure_num}',
        ]
    
    # 搜索范围：图片上方和下方各10个段落
    search_range = 10
    start_idx = max(0, pic_index - search_range)
    end_idx = min(len(doc.paragraphs), pic_index + search_range + 1)
    
    # 在指定范围内查找引用
    for i in range(start_idx, end_idx):
        if i == pic_index:
            continue  # 跳过图片段落本身
        
        para = doc.paragraphs[i]
        text = normalize_caption_text(para.text)
        
        if not text:
            continue
        
        # 尝试匹配各种引用模式
        for pattern in reference_patterns:
            match = re.search(pattern, text, re.IGNORECASE if language == 'english' else 0)
            if match:
                report['reference_found'] = True
                report['reference_text'] = match.group(0)
                report['ok'] = True
                msg_tpl = tpl.get('messages', {}).get('figure_reference_ok', '图片引用检测通过')
                report['messages'].append(f"{msg_tpl}（找到引用：{match.group(0)}）")
                return report
    
    # 未找到引用
    report['ok'] = False
    report['reference_found'] = False
    msg_tpl = tpl.get('messages', {}).get('figure_reference_error', '图片未被引用')
    if language == 'chinese':
        expected_ref = f"如图{full_number}所示"
    else:
        expected_ref = f"As shown in Fig {full_number}"
    report['messages'].append(f"{msg_tpl}（期望格式：{expected_ref}）")
    
    return report

def check_caption_format(caption_info, tpl):
    """
    检查图片标题的格式（支持中英文）
    返回：{'ok': bool, 'messages': []}
    """
    report = {'ok': True, 'messages': []}
    
    paragraph = caption_info['paragraph']
    expected_format = tpl.get('format_rules', {}).get('caption', {})
    language = caption_info.get('language', 'chinese')
    
    # 获取主要的文本run
    main_run = next((r for r in paragraph.runs if r.text.strip()), None)
    if not main_run:
        report['ok'] = False
        report['messages'].append('图片标题没有可供检查的文本内容')
        return report
    
    # 检测格式
    actual_size, actual_font_ascii, actual_font_eastasia, actual_bold, actual_italic, actual_line_spacing = detect_font_for_run(main_run, paragraph)
    
    # 检查字体大小
    if not should_skip_check('font_size'):
        expected_size = expected_format.get('font_size_pt', 10.5)
        if abs(actual_size - expected_size) > 0.5:
            report['ok'] = False
            expected_size_name = get_font_size(expected_size, tpl)
            actual_size_name = get_font_size(actual_size, tpl)
            msg = tpl.get('messages', {}).get('caption_font_size_error', '图片标题字体大小应为五号(10.5pt)')
            report['messages'].append(f"{msg}（期望：{expected_size_name}，实际：{actual_size_name}）")
    
    # 检查字体名称（根据语言类型）
    if not should_skip_check('font_name'):
        if language == 'chinese':
            expected_font = expected_format.get('font_name_chinese', '宋体')
            if expected_font.lower() not in (actual_font_eastasia or '').lower():
                report['ok'] = False
                msg = tpl.get('messages', {}).get('caption_font_name_error_chinese', '图片标题中文字体应为宋体')
                report['messages'].append(f"{msg}（当前：{actual_font_eastasia}）")
        else:
            expected_font = expected_format.get('font_name_english', 'Times New Roman')
            if expected_font.lower() not in (actual_font_ascii or '').lower():
                report['ok'] = False
                msg = tpl.get('messages', {}).get('caption_font_name_error_english', '图片标题英文字体应为Times New Roman')
                report['messages'].append(f"{msg}（当前：{actual_font_ascii}）")
    
    # 检查加粗
    if not should_skip_check('bold') and 'bold' in expected_format:
        expected_bold = expected_format.get('bold', False)
        if actual_bold != expected_bold:
            report['ok'] = False
            msg = '图片标题应加粗' if expected_bold else '图片标题应为不加粗'
            report['messages'].append(f"{msg}（当前：{'加粗' if actual_bold else '不加粗'}）")
    
    # 检查斜体
    if not should_skip_check('italic') and 'italic' in expected_format:
        expected_italic = expected_format.get('italic', False)
        if actual_italic != expected_italic:
            report['ok'] = False
            msg = '图片标题应为斜体' if expected_italic else '图片标题应为正体'
            report['messages'].append(f"{msg}（当前：{'斜体' if actual_italic else '正体'}）")
    
    # 检查行距
    if not should_skip_check('spacing') and 'line_spacing' in expected_format:
        expected_line_spacing = float(expected_format.get('line_spacing', 1.0))
        if abs(actual_line_spacing - expected_line_spacing) > 0.1:
            report['ok'] = False
            actual_spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
            expected_spacing_name = get_line_spacing_name(expected_line_spacing, tpl)
            msg = tpl.get('messages', {}).get('caption_line_spacing_error', '图片标题行距应为单倍行距（1.0倍）')
            report['messages'].append(f"{msg}（期望：{expected_spacing_name}，实际：{actual_spacing_name}）")
    
    # 检查对齐方式
    if not should_skip_check('alignment') and expected_format.get('alignment') == 'center':
        actual_alignment = detect_paragraph_alignment(paragraph)
        alignment_names = {
            0: '左对齐',
            1: '居中对齐',
            2: '右对齐',
            3: '两端对齐'
        }
        actual_alignment_name = alignment_names.get(actual_alignment, f'未知对齐方式({actual_alignment})')
        
        if actual_alignment != 1:
            report['ok'] = False
            msg = tpl.get('messages', {}).get('caption_alignment_error', '图片标题应居中对齐')
            report['messages'].append(f"{msg}（当前：{actual_alignment_name}）")
    
    return report

def check_figure_numbering(captions, tpl):
    """
    检查图片编号的连续性（支持X-Y格式）
    只检查每个章节内编号的连续性，不要求从1-1开始
    返回：{'ok': bool, 'messages': []}
    """
    report = {'ok': True, 'messages': []}
    
    if not captions:
        return report
    
    # 按章节和编号排序
    numbers = sorted([(c['chapter'], c['number']) for c in captions])
    
    # 检查重复
    seen = set()
    for chapter, num in numbers:
        key = (chapter, num)
        if key in seen:
            report['ok'] = False
            report['messages'].append(f"图片编号重复：{chapter}-{num}")
        seen.add(key)
    
    # 检查每个章节内的连续性
    # 按章节分组
    chapter_numbers = {}
    for chapter, num in numbers:
        if chapter not in chapter_numbers:
            chapter_numbers[chapter] = []
        chapter_numbers[chapter].append(num)
    
    # 检查每个章节内编号是否连续（从该章节的第一个编号开始连续递增）
    for chapter in sorted(chapter_numbers.keys()):
        nums = sorted(chapter_numbers[chapter])
        if not nums:
            continue
        
        # 检查是否从该章节的第一个编号连续递增（例如：3-1, 3-2, 3-3...）
        expected_start = nums[0]
        expected_set = set(range(expected_start, expected_start + len(nums)))
        actual_set = set(nums)
        missing_nums = sorted(expected_set - actual_set)
        
        if missing_nums:
            report['ok'] = False
            report['messages'].append(f"章节{chapter}的图片编号不连续，缺失编号：{', '.join(map(str, missing_nums))}")
    
    return report

def check_doc_with_template(doc_path, template_identifier="Figure", enable_content_check=True, api_key=None,skip_checks=None):
    """
    使用指定的模板检测文档中的图片格式
    
    参数:
        doc_path: Word文档路径
        template_identifier: 模板标识符（文件路径或模板名称），默认为 "Figure"
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
        enable_content_check: 是否启用图片内容智能检测（需要API密钥）
        api_key: 硅基流动API密钥（启用内容检测时需要）
    
    返回:
        检测报告字典
    """
    global _skip_checks_config
    _skip_checks_config = skip_checks or []
    
    # 加载模板
    tpl = load_template(template_identifier)
    
    # 加载文档
    doc = Document(doc_path)
     # 如果启用内容检测，导入相关模块
    content_detector = None
    if enable_content_check:
        try:
            # 尝试绝对导入
            try:
                from .Figure_content_detect import FigureContentDetector
            except ImportError:
                # 如果失败，尝试相对导入
                from Chinese_paper_detect.Figure_content_detect import FigureContentDetector
            
            # 初始化检测器（会自动从配置文件读取，或使用传入的api_key）
            content_detector = FigureContentDetector(api_key=api_key)
            print(f"✓ 图片内容智能检测已启用")
            if content_detector.save_images:
                print(f"  图片将保存到: {content_detector.image_dir}/ 目录")
            else:
                print(f"  使用临时文件（分析后自动删除）")
        except ValueError as e:
            print(f"警告: {e}")
            print("  将跳过内容检测")
        except ImportError as e:
            print(f"警告: 无法加载图片内容检测模块: {e}")
            print("  将跳过内容检测")
    # 初始化报告
    report = {
        'overall': {'ok': True, 'messages': []},
        'figures': [],
        'numbering': {'ok': True, 'messages': []},
        'summary': {}
    }
    
    # 0. 查找"摘要"位置，只检测摘要之后的图片（优先使用 Abstract_detect 模块的方法）
    abstract_index = find_abstract_position(doc, tpl)
    if abstract_index is not None:
        print(f"✓ 找到摘要位置：段落索引 {abstract_index}，将只检测该位置之后的图片")
    else:
        print(f"⚠ 未找到摘要字段，将检测文档中的所有图片")
    
    # 1. 找出所有包含图片的段落（按文档顺序），但只保留摘要之后的图片
    picture_paragraphs = []
    for idx, paragraph in enumerate(doc.paragraphs):
        if has_picture_object(paragraph):
            # 如果找到了摘要位置，只收集摘要之后的图片
            if abstract_index is None or idx > abstract_index:
                picture_paragraphs.append({
                    'paragraph': paragraph,
                    'paragraph_index': idx
                })
            else:
                # 摘要之前的图片被忽略
                print(f"  忽略摘要之前的图片（段落索引 {idx}）")
    
    if not picture_paragraphs:
        report['overall']['ok'] = False
        report['overall']['messages'].append('文档中未找到任何图片')
        report['summary']['figure_count'] = 0
        return report
    
    report['summary']['figure_count'] = len(picture_paragraphs)
    
    # 2. 对每张图片进行检查
    # 中文圖題：同時支持「图」「圖」，連接符支持 - — －，圖後與數字前後空格均可選
    connector_chars = r'[-—－]'
    caption_pattern_chinese = tpl.get('figure_detection_rules', {}).get(
        'caption_pattern_chinese',
        # 编号与标题之间允许无空格（例如：图 3-10不同编码方式...）
        fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
    )
    caption_pattern_english = tpl.get('figure_detection_rules', {}).get('caption_pattern_english', r'^\s*Fig\s(\d+)-(\d+)\s+(.+)$')
    figure_numbers = []
    
    for fig_idx, pic_info in enumerate(picture_paragraphs, start=1):
        picture_para = pic_info['paragraph']
        pic_index = pic_info['paragraph_index']
        
        figure_report = {
            'figure_index': fig_idx,
            'paragraph_index': pic_index,
            'has_caption': False,
            'caption_info': None,
            'format_check': {'ok': True, 'messages': []},
            'position_check': {'ok': True, 'messages': []},
            'picture_check': {'ok': True, 'messages': []},
            'blank_line_check': {'ok': True, 'messages': []},
            'reference_check': {'ok': True, 'messages': []},
            'content_check': {'ok': True, 'messages': []}
        }
        
        # 2.1 检查是否有标题（先向下查找，再向上查找）
        caption_found = None
        max_distance = 3  # 查找范围扩大到3个段落
        
        # 先向下查找（标题通常在图片下方）
        for i in range(pic_index + 1, min(pic_index + max_distance + 1, len(doc.paragraphs))):
            caption_para = doc.paragraphs[i]
            text = normalize_caption_text(caption_para.text)
            if not text:
                continue
            
            # 尝试匹配中文格式
            match = re.match(caption_pattern_chinese, text)
            # 如果模板模式不匹配，尝试更灵活的模式（图/圖后空格可选，连接符可为- — －，两侧空格可选）
            if not match:
                flexible_pattern = fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
                match = re.match(flexible_pattern, text)
            # 如果还不匹配，尝试更宽松的模式（数字和标题之间空格可选，但至少需要一个字符）
            if not match:
                very_flexible_pattern = fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
                match = re.match(very_flexible_pattern, text)
                if match and not match.group(3).strip():
                    match = None  # 确保标题部分不为空
            if match:
                chapter_num = int(match.group(1))
                figure_num = int(match.group(2))
                figure_title = match.group(3).strip()
                if figure_title:
                    caption_found = {
                        'paragraph': caption_para,
                        'paragraph_index': i,
                        'chapter': chapter_num,
                        'number': figure_num,
                        'title': figure_title,
                        'full_text': text,
                        'language': 'chinese',
                        'full_number': f"{chapter_num}-{figure_num}"
                    }
                    figure_numbers.append((chapter_num, figure_num))
                    break
            
            # 尝试匹配英文格式
            match = re.match(caption_pattern_english, text, re.IGNORECASE)
            if match:
                chapter_num = int(match.group(1))
                figure_num = int(match.group(2))
                figure_title = match.group(3).strip()
                if figure_title:
                    caption_found = {
                        'paragraph': caption_para,
                        'paragraph_index': i,
                        'chapter': chapter_num,
                        'number': figure_num,
                        'title': figure_title,
                        'full_text': text,
                        'language': 'english',
                        'full_number': f"{chapter_num}-{figure_num}"
                    }
                    figure_numbers.append((chapter_num, figure_num))
                    break
        
        # 如果向下查找没找到，向上查找（某些中文格式标题在图片上方）
        if not caption_found:
            for i in range(pic_index - 1, max(-1, pic_index - max_distance - 1), -1):
                if i < 0:
                    break
                caption_para = doc.paragraphs[i]
                text = normalize_caption_text(caption_para.text)
                if not text:
                    continue
                
                # 只尝试匹配中文格式（英文格式通常在下方）
                match = re.match(caption_pattern_chinese, text)
                # 如果模板模式不匹配，尝试更灵活的模式（图后可选空格）
                if not match:
                    flexible_pattern = fr'^\s*[图圖]\s*(\d+)\s*{connector_chars}\s*(\d+)\s*(.+)$'
                    match = re.match(flexible_pattern, text)
                if match:
                    chapter_num = int(match.group(1))
                    figure_num = int(match.group(2))
                    figure_title = match.group(3).strip()
                    if figure_title:
                        caption_found = {
                            'paragraph': caption_para,
                            'paragraph_index': i,
                            'chapter': chapter_num,
                            'number': figure_num,
                            'title': figure_title,
                            'full_text': text,
                            'language': 'chinese',
                            'full_number': f"{chapter_num}-{figure_num}"
                        }
                        figure_numbers.append((chapter_num, figure_num))
                        break
        
        if caption_found:
            figure_report['has_caption'] = True
            figure_report['caption_info'] = caption_found
            
            # 2.2 检查标题格式
            format_result = check_caption_format(caption_found, tpl)
            figure_report['format_check'] = format_result
            if not format_result['ok']:
                report['overall']['ok'] = False
            
            # 2.3 检查图题与正文之间的空行
            if tpl.get('check_rules', {}).get('blank_line_after_caption_check', True):
                blank_line_result = check_blank_line_after_caption(doc, caption_found, tpl)
                figure_report['blank_line_check']['ok'] = blank_line_result['ok']
                if blank_line_result.get('message'):
                    figure_report['blank_line_check']['messages'].append(blank_line_result['message'])
                if not blank_line_result['ok']:
                    report['overall']['ok'] = False
            
            # 2.4 检查图片引用（只有在有标题时才执行）
            if tpl.get('check_rules', {}).get('figure_reference_check', True):
                reference_result = check_figure_reference(doc, caption_found, pic_index, tpl)
                figure_report['reference_check'] = reference_result
                if not reference_result['ok']:
                    report['overall']['ok'] = False
            else:
                # 如果引用检测被禁用，设置一个标记
                figure_report['reference_check'] = {
                    'ok': True,
                    'messages': ['引用检测已禁用'],
                    'reference_found': False,
                    'reference_text': '',
                    'disabled': True
                }
        else:
            # 没有标题
            figure_report['has_caption'] = False
            figure_report['format_check']['ok'] = False
            lang = 'chinese'  # 默认中文
            pattern_msg = tpl.get('messages', {}).get('caption_pattern_error_chinese', '图片标题格式应为：图X-Y 标题(来源于xxxxxx)')
            figure_report['format_check']['messages'].append(f"❌ 图片缺少标题（应为：{pattern_msg}）")
            report['overall']['ok'] = False
            # 没有标题时，无法检测引用
            figure_report['reference_check']['ok'] = False
            figure_report['reference_check']['messages'].append('无法检测引用：图片缺少标题')
        
        # 2.5 检查图片对齐
        if tpl.get('check_rules', {}).get('picture_alignment_check', True):
            is_centered, alignment = check_picture_alignment(picture_para)
            if not is_centered:
                alignment_names = {0: '左对齐', 1: '居中对齐', 2: '右对齐', 3: '两端对齐'}
                alignment_name = alignment_names.get(alignment, f'未知({alignment})')
                figure_report['picture_check']['ok'] = False
                figure_report['picture_check']['messages'].append(
                    f"图片应居中对齐（当前：{alignment_name}）"
                )
                report['overall']['ok'] = False
        
        # 2.6 检查图片内容（如果启用了内容检测）
        if content_detector and enable_content_check:
            try:
                # 获取图片编号用于文件命名
                figure_number = None
                if caption_found:
                    figure_number = int(f"{caption_found['chapter']}{caption_found['number']}")
                elif fig_idx:
                    figure_number = fig_idx
                
                print(f"    [图片 {fig_idx}] 开始内容检测...")
                content_result = content_detector.detect_figure_content(
                    picture_para, 
                    doc_path, 
                    figure_number=figure_number
                )
                
                # 将内容检测结果添加到报告
                figure_report['content_check'] = {
                    'ok': content_result.get('ok', True),
                    'messages': content_result.get('messages', []),
                    'is_chart': content_result.get('is_chart', False),
                    'details': content_result.get('details', {})
                }
                
                # 如果内容检测失败，更新总体状态
                if not content_result.get('ok', True):
                    report['overall']['ok'] = False
                    
            except Exception as e:
                print(f"    [图片 {fig_idx}] 内容检测失败: {e}")
                figure_report['content_check'] = {
                    'ok': False,
                    'messages': [f'内容检测失败: {str(e)}'],
                    'is_chart': False,
                    'details': {}
                }
                report['overall']['ok'] = False
        
        report['figures'].append(figure_report)
    
    # 3. 检查编号连续性
    if figure_numbers:
        numbering_result = check_figure_numbering(
            [{'chapter': ch, 'number': num} for ch, num in figure_numbers],
            tpl
        )
        report['numbering'] = numbering_result
        if not numbering_result['ok']:
            report['overall']['ok'] = False
    
    # 兼容处理：生成旧格式的captions列表
    report['captions'] = []
    for fig_report in report['figures']:
        if fig_report['has_caption']:
            report['captions'].append({
                'number': fig_report['caption_info']['full_number'],
                'title': fig_report['caption_info']['title'],
                'full_text': fig_report['caption_info']['full_text'],
                'format_check': fig_report['format_check'],
                'position_check': fig_report.get('position_check', {'ok': True, 'messages': []}),
                'blank_line_check': fig_report.get('blank_line_check', {'ok': True, 'messages': []})
            })
    
    return report

# ---------- 命令行接口 ----------
def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description='检测中文论文图片格式')
    parser.add_argument('doc_path', help='Word文档路径')
    parser.add_argument('-t', '--template', default='Figure', help='模板标识符（默认: Figure）')
    parser.add_argument('--skip', nargs='+', help='跳过的检测项，如: --skip font_size bold')
    
    args = parser.parse_args()
    
    skip_checks = args.skip if args.skip else None
    result = check_doc_with_template(args.doc_path, args.template, skip_checks)
    
    print("=" * 80)
    print("【图片 检测报告】")
    print("=" * 80)
    print()
    
    # 总结
    print("  [Overall]", "✓ 通过" if result['overall']['ok'] else "✗ 失败")
    for msg in result['overall']['messages']:
        print(f"    • {msg}")
    print()
    
    # 编号检查
    if result['numbering']['messages']:
        print("  [Numbering]", "✓ 通过" if result['numbering']['ok'] else "✗ 失败")
        for msg in result['numbering']['messages']:
            print(f"    • {msg}")
        print()
    
    # 各图片详细检查
    if result.get('figures'):
        print("  [Figures]")
        for fig_report in result['figures']:
            fig_idx = fig_report['figure_index']
            
            if fig_report['has_caption']:
                caption = fig_report['caption_info']
                print(f"    第 {fig_idx} 张图片: {caption['full_number']} {caption['title']}")
            else:
                print(f"    第 {fig_idx} 张图片: (无标题)")
            
            # 格式检查
            if not fig_report['format_check']['ok']:
                print(f"      格式问题：")
                for msg in fig_report['format_check']['messages']:
                    print(f"        - {msg}")
            
            # 空行检查
            if not fig_report['blank_line_check']['ok']:
                print(f"      空行问题：")
                for msg in fig_report['blank_line_check']['messages']:
                    print(f"        - {msg}")
            
            # 引用检查（总是显示）
            if 'reference_check' in fig_report:
                ref_check = fig_report['reference_check']
                if ref_check.get('disabled', False):
                    # 引用检测被禁用
                    print(f"      引用检查: ⚠ 已禁用")
                elif not ref_check['ok']:
                    # 引用检测失败
                    print(f"      引用检查: ✗")
                    for msg in ref_check['messages']:
                        print(f"        • {msg}")
                else:
                    # 引用检测通过
                    print(f"      引用检查: ✓ 通过")
                    # 显示找到的引用信息
                    if ref_check.get('reference_text'):
                        print(f"        • 找到引用：{ref_check['reference_text']}")
                    # 显示其他消息
                    for msg in ref_check['messages']:
                        if msg and '找到引用' not in msg:  # 避免重复显示
                            print(f"        • {msg}")
            else:
                # 如果没有引用检查字段，说明可能没有标题或检测未执行
                print(f"      引用检查: ⚠ 未执行（图片缺少标题）")
            
            # 图片对齐检查
            if not fig_report['picture_check']['ok']:
                print(f"      图片问题：")
                for msg in fig_report['picture_check']['messages']:
                    print(f"        - {msg}")
            
            # 内容检测（如果执行了）
            if 'content_check' in fig_report:
                content_check = fig_report['content_check']
                if content_check.get('is_chart', False):
                    # 是图表，显示检测结果
                    if not content_check['ok']:
                        print(f"      内容规范: ✗")
                        for msg in content_check['messages']:
                            print(f"        • {msg}")
                    else:
                        print(f"      内容规范: ✓ 通过")
                        for msg in content_check['messages']:
                            if msg and '✅' in msg:  # 只显示成功消息
                                print(f"        • {msg}")
                else:
                    # 不是图表，显示类型信息
                    chart_type = content_check.get('details', {}).get('is_chart_check', {}).get('chart_type', '非图表')
                    print(f"      内容检测: 图片类型为 {chart_type}，跳过图表规范检测")
            
            print()
    
    print("=" * 80)

if __name__ == '__main__':
    main()

