#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
from pathlib import Path

# 添加项目根目录到路径，以便导入模块
if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn


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
=== 论文格式检测系统 - 图片检测器 ===

【图片检测 (Figure Detection)】

1. 【图片标题格式检测】
   - 图片标题格式：Fig. 编号 标题文字（如：Fig. 1 Material structure）
   - 注意：Fig. 后必须有空格
   - 标题居中对齐
   - 标题字体：Times New Roman，五号(10.5pt)
   - 图片编号应连续递增

2. 【图片位置关系检测】
   - 图片应居中对齐
   - 标题位于图片下方
   - 图片与标题间隔合理

3. 【图片编号检测】
   - 编号从1开始
   - 编号连续递增（Fig. 1, Fig. 2, Fig. 3...）

4. 【技术特性】
   - 支持图片标题的智能识别
   - 验证图片编号的连续性
   - 检测图片对象的存在性
   - 分析图片和标题的对齐方式
"""

# ---------- 模板加载 ----------
def resolve_template_path(identifier):
    """解析模板路径，支持文件路径和模板名称"""
    if os.path.isfile(identifier):
        return identifier
    candidate = os.path.join("templates", identifier + ".json")
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(f"Template not found: '{identifier}' (tried file path and {candidate})")

def load_template(identifier):
    """加载JSON模板文件"""
    tpl_path = resolve_template_path(identifier)
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = json.load(f)
    return tpl

# ---------- 字体检测函数 ----------
def detect_font_for_run(run, paragraph=None):
    """
    更健壮的字体检测函数，同时检查直接格式和段落样式。
    返回 (font_size_pt, font_name, is_bold, is_italic, candidates_dict)
    """
    font_source = run.font if run else (paragraph.style.font if paragraph else None)
    if not font_source:
        return 12.0, "Unknown", False, False, {}

    font_name = font_source.name if font_source.name else "Times New Roman"

    font_size = None
    try:
        if run and run.font and run.font.size and hasattr(run.font.size, 'pt'):
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

    # 加粗检测 - 优先直接格式，直接格式为None时使用样式格式
    if run and run.font and run.font.bold is not None:
        is_bold = run.font.bold
    elif paragraph and paragraph.style and paragraph.style.font and paragraph.style.font.bold is not None:
        is_bold = paragraph.style.font.bold
    else:
        is_bold = False
    
    # 斜体检测 - 优先直接格式，直接格式为None时使用样式格式
    if run and run.font and run.font.italic is not None:
        is_italic = run.font.italic
    elif paragraph and paragraph.style and paragraph.style.font and paragraph.style.font.italic is not None:
        is_italic = paragraph.style.font.italic
    else:
        is_italic = False
    
    # 确保返回明确的布尔值
    is_bold = bool(is_bold)
    is_italic = bool(is_italic)

    return font_size, font_name, is_bold, is_italic, {}

def get_font_size(pt_size, tpl=None):
    """获取字体大小的中文名称"""
    # 从模板读取字体大小映射，提供默认值以保持向后兼容
    if tpl and 'check_rules' in tpl and 'font_size_mapping' in tpl['check_rules']:
        size_config = tpl['check_rules']['font_size_mapping']
        # 将字符串键转换为浮点数
        size_map = {}
        for key, value in size_config.items():
            try:
                size_map[float(key)] = value
            except (ValueError, TypeError):
                continue
    else:
        # 默认的字体大小映射（向后兼容）
        size_map = {
            9: "小五",
            10.5: "五号",
            12: "小四",
            14: "四号",
            16: "三号",
            18: "小二",
            22: "二号",
            24: "小一",
            26: "一号"
        }
    
    if not size_map:
        return f"{pt_size}pt"
    
    closest_size = min(size_map.keys(), key=lambda x: abs(x - pt_size))
    return size_map[closest_size]

# ---------- 段落对齐检测函数 ----------
def get_style_alignment(doc, style_id):
    """从文档的styles.xml中查找并返回指定样式的对齐方式。"""
    try:
        styles = doc.styles.element
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        style_path = f".//w:style[@w:styleId='{style_id}']//w:jc"
        jc_element = styles.find(style_path, ns)
        if jc_element is not None:
            val = jc_element.get(ns['w'] + 'val')
            mapping = {'left': 0, 'center': 1, 'right': 2, 'both': 3, 'justify': 3}
            return mapping.get(val)
    except Exception:
        return None
    return None

def detect_paragraph_alignment(paragraph):
    """
    改进的段落对齐检测，按照明确的优先级处理直接格式和样式格式
    
    检测逻辑：
    1. 如果直接格式不为None，直接使用直接格式结果
    2. 如果直接格式为None，检查样式格式（包括继承链）
    3. 默认为左对齐
    """
    
    # 优先级1: 检查直接格式
    direct_alignment = paragraph.paragraph_format.alignment
    if direct_alignment is not None:
        # 如果有直接格式设置，直接使用
        return int(direct_alignment)
    
    # 优先级2: 如果直接格式为None，检查样式格式（包括继承链）
    if paragraph.style:
        try:
            # 先检查当前样式
            style_alignment = paragraph.style.paragraph_format.alignment
            if style_alignment is not None:
                return int(style_alignment)
            
            # 如果当前样式没有对齐设置，检查样式继承链
            current_style = paragraph.style
            visited = set()  # 避免循环
            
            while current_style and current_style.style_id not in visited:
                visited.add(current_style.style_id)
                
                # 检查 XML 中的对齐设置
                if current_style.element.pPr is not None:
                    pPr = current_style.element.pPr
                    jc_elements = pPr.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
                    if jc_elements:
                        val = jc_elements[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                        if val == 'center':
                            return 1  # CENTER
                        elif val == 'right':
                            return 2  # RIGHT
                        elif val == 'both':
                            return 3  # JUSTIFY
                        elif val == 'left':
                            return 0  # LEFT
                
                # 获取基础样式
                try:
                    if current_style.element.pPr is not None:
                        basedOn = current_style.element.pPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}basedOn')
                        if basedOn is None:
                            # 在 pPr 外查找
                            basedOn = current_style.element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}basedOn')
                        
                        if basedOn is not None:
                            base_id = basedOn.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            # 在样式集合中查找
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
            
    # 默认值: 左对齐
    return 0  # WD_PARAGRAPH_ALIGNMENT.LEFT

# ---------- 图片检测核心函数 ----------

def has_picture_object(paragraph):
    """
    检测段落是否包含图片对象
    支持现代格式(w:drawing)、旧格式(w:pict)和VML格式(v:imagedata)
    返回：True/False
    """
    try:
        para_xml = paragraph._element
        
        # 定义命名空间
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
        
        # 检查VML格式的图片（v:imagedata）- 这是最常见的格式
        imagedata = para_xml.xpath('.//v:imagedata', namespaces=namespaces)
        if imagedata:
            return True
        
        # 检查图片元素（a:blip）
        blips = para_xml.xpath('.//a:blip', namespaces=namespaces)
        if blips:
            return True
            
    except Exception as e:
        # 如果xpath失败，尝试直接遍历元素
        try:
            for elem in para_xml.iter():
                tag = elem.tag
                if any(keyword in tag.lower() for keyword in ['drawing', 'pict', 'imagedata', 'blip']):
                    return True
        except Exception:
            pass
    
    return False

def find_picture_captions(doc, tpl):
    """
    识别文档中的图片标题
    返回：图片标题段落列表，每个元素包含段落对象、编号、标题文本
    """
    caption_pattern = tpl.get('figure_detection_rules', {}).get('caption_pattern', r'^\s*Fig\.?\s*(\d+)[.:\s]*(.*)$')
    captions = []
    
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        match = re.match(caption_pattern, text, re.IGNORECASE)
        if match:
            figure_num = int(match.group(1))
            figure_title = match.group(2).strip()
            # 只有当标题不为空时才认为是有效的标题
            if figure_title:
                captions.append({
                    'paragraph': paragraph,
                    'paragraph_index': idx,
                    'number': figure_num,
                    'title': figure_title,
                    'full_text': text
                })
    
    return captions

def find_picture_before_caption(doc, caption_info):
    """
    在标题上方或下方查找对应的图片
    返回：包含图片的段落对象或None
    """
    caption_idx = caption_info['paragraph_index']
    max_distance = 2  # 最多查找2个段落
    
    # 优先在标题前的几个段落中查找图片
    for i in range(caption_idx - 1, max(0, caption_idx - max_distance - 1), -1):
        if i < 0 or i >= len(doc.paragraphs):
            continue
        
        paragraph = doc.paragraphs[i]
        if has_picture_object(paragraph):
            return paragraph
    
    # 如果上方没找到，尝试在标题下方查找（如Fig.1的情况）
    for i in range(caption_idx + 1, min(len(doc.paragraphs), caption_idx + max_distance + 1)):
        if i < 0 or i >= len(doc.paragraphs):
            continue
        
        paragraph = doc.paragraphs[i]
        if has_picture_object(paragraph):
            return paragraph
    
    return None

def check_picture_alignment(picture_paragraph):
    """
    检查图片段落的对齐方式
    返回：(is_centered, actual_alignment)
    """
    if not picture_paragraph:
        return False, None
    
    actual_alignment = detect_paragraph_alignment(picture_paragraph)
    # 居中对齐的值为1
    is_centered = (actual_alignment == 1)
    
    return is_centered, actual_alignment

def check_caption_format(caption_info, tpl):
    """
    检查图片标题的格式
    返回：{'ok': bool, 'errors': []}
    """
    report = {'ok': True, 'errors': []}
    
    paragraph = caption_info['paragraph']
    expected_format = tpl.get('format_rules', {}).get('caption', {})
    caption_text = caption_info.get('full_text', '')
    
    # 获取主要的文本run
    main_run = next((r for r in paragraph.runs if r.text.strip()), None)
    if not main_run:
        report['ok'] = False
        report['errors'].append({
            'type': 'error',
            'page_number': 'N/A',
            'description': '图片标题没有可供检查的文本内容',
            'suggestion': '建议：检查图片标题格式',
            'text_snippet': caption_text[:150] + ('...' if len(caption_text) > 150 else '')
        })
        return report
    
    
    # 检查加粗
    if not should_skip_check('bold') and 'bold' in expected_format:
        expected_bold = expected_format.get('bold', False)
        actual_size, actual_font, actual_bold, actual_italic, _ = detect_font_for_run(main_run, paragraph)
        if actual_bold != expected_bold:
            report['ok'] = False
            msg = tpl.get('messages', {}).get('caption_bold_error', '图片标题应为不加粗')
            if expected_bold:
                msg = '图片标题应加粗'
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"{msg}（当前：{'加粗' if actual_bold else '不加粗'}）",
                'suggestion': f"建议：将图片标题设置为{'加粗' if expected_bold else '不加粗'}",
                'text_snippet': caption_text[:150] + ('...' if len(caption_text) > 150 else '')
            })
    
    # 检查斜体
    if not should_skip_check('italic') and 'italic' in expected_format:
        expected_italic = expected_format.get('italic', False)
        actual_size, actual_font, actual_bold, actual_italic, _ = detect_font_for_run(main_run, paragraph)
        if actual_italic != expected_italic:
            report['ok'] = False
            msg = tpl.get('messages', {}).get('caption_italic_error', '图片标题应为正体')
            if expected_italic:
                msg = '图片标题应为斜体'
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"{msg}（当前：{'斜体' if actual_italic else '正体'}）",
                'suggestion': f"建议：将图片标题设置为{'斜体' if expected_italic else '正体'}",
                'text_snippet': caption_text[:150] + ('...' if len(caption_text) > 150 else '')
            })
    
    # 检查对齐方式
    if not should_skip_check('alignment') and expected_format.get('alignment') == 'center':
        actual_alignment = detect_paragraph_alignment(paragraph)
        
        # 对齐方式名称映射
        alignment_names = {
            0: '左对齐',
            1: '居中对齐',
            2: '右对齐',
            3: '两端对齐'
        }
        actual_alignment_name = alignment_names.get(actual_alignment, f'未知对齐方式({actual_alignment})')
        
        # 居中对齐的值为1
        if actual_alignment != 1:
            report['ok'] = False
            msg = tpl.get('messages', {}).get('caption_alignment_error', '图片标题应居中对齐')
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"{msg}（当前：{actual_alignment_name}）",
                'suggestion': '建议：将图片标题设置为居中对齐',
                'text_snippet': caption_text[:150] + ('...' if len(caption_text) > 150 else '')
            })
    
    # 检查字体大小
    if not should_skip_check('font_size'):
        expected_size = expected_format.get('font_size_pt', 10.5)
        actual_size, actual_font, _, _, _ = detect_font_for_run(main_run, paragraph)
        if abs(actual_size - expected_size) > 0.5:
            report['ok'] = False
            expected_size_name = get_font_size(expected_size, tpl)
            actual_size_name = get_font_size(actual_size, tpl)
            msg = tpl.get('messages', {}).get('caption_font_size_error', '图片标题字体大小不正确')
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"{msg}（期望：{expected_size_name}，实际：{actual_size_name}）",
                'suggestion': f"建议：将字体大小调整为{expected_size_name}",
                'text_snippet': caption_text[:150] + ('...' if len(caption_text) > 150 else '')
            })
    
    # 检查字体名称
    if not should_skip_check('font_name'):
        expected_font = expected_format.get('font_name', 'Times New Roman')
        actual_size, actual_font, _, _, _ = detect_font_for_run(main_run, paragraph)
        if actual_font and actual_font != expected_font:
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"图片标题字体应为{expected_font}（当前：{actual_font}）",
                'suggestion': f"建议：将字体设置为{expected_font}",
                'text_snippet': caption_text[:150] + ('...' if len(caption_text) > 150 else '')
            })
    
    return report

def check_figure_numbering(captions, tpl):
    """
    检查图片编号的连续性
    返回：{'ok': bool, 'messages': []}
    """
    report = {'ok': True, 'messages': []}
    
    if not captions:
        return report
    
    numbers = sorted([c['number'] for c in captions])
    
    # 检查是否从1开始
    if tpl.get('check_rules', {}).get('caption_numbering_check', True):
        expected_start = tpl.get('check_rules', {}).get('numbering_start', 1)
        if numbers[0] != expected_start:
            report['ok'] = False
            msg_template = tpl.get('messages', {}).get('caption_numbering_start_error', '图片编号应从{start}开始，实际从{actual}开始')
            report['messages'].append(msg_template.format(start=expected_start, actual=numbers[0]))
    
    # 检查是否连续
    if tpl.get('check_rules', {}).get('caption_sequential_check', True):
        expected_sequence = list(range(numbers[0], numbers[0] + len(numbers)))
        if numbers != expected_sequence:
            report['ok'] = False
            msg_template = tpl.get('messages', {}).get('caption_numbering_error', '图片编号不连续')
            report['messages'].append(msg_template.format(numbers=', '.join(map(str, numbers))))
    
    return report

def check_figure_reference(doc, figure_number, figure_paragraph_index, caption_paragraph=None, search_range=3):
    """
    检查图片是否在前文中被引用
    
    参数:
        doc: Document对象
        figure_number: 图片编号（int）
        figure_paragraph_index: 图片所在段落的索引
        caption_paragraph: 图片标题段落对象（用于获取标题文本）
        search_range: 向前搜索的非空段落数量（默认3）
    
    返回:
        {'ok': bool, 'errors': []}
    """
    # 定义引用模式（不区分大小写）
    patterns = [
        r'\bFig\.?\s*' + str(figure_number) + r'\b',  # Fig. 1 或 Fig.1
        r'\bFigure\s+' + str(figure_number) + r'\b',  # Figure 1
        r'\b图\s*' + str(figure_number) + r'\b',      # 图1 或 图 1
    ]
    
    # 向前搜索非空段落
    non_empty_count = 0
    for i in range(figure_paragraph_index - 1, -1, -1):
        if i < 0 or i >= len(doc.paragraphs):
            continue
        
        paragraph_text = doc.paragraphs[i].text
        
        # 跳过空段落
        if not paragraph_text.strip():
            continue
        
        # 计数非空段落
        non_empty_count += 1
        
        # 检查是否匹配任何引用模式
        for pattern in patterns:
            if re.search(pattern, paragraph_text, re.IGNORECASE):
                # 找到引用，返回成功
                return {'ok': True, 'errors': []}
        
        # 如果已经检查了足够的非空段落，停止搜索
        if non_empty_count >= search_range:
            break
    
    # 没有找到引用，返回错误
    suggestion = f'建议：在图片Fig. {figure_number}出现前添加引用，如"如Fig. {figure_number}所示"或"见Fig. {figure_number}"'
    
    # 使用标题文本作为text_snippet，用于run_all_detections.py定位批注
    caption_text = caption_paragraph.text.strip() if caption_paragraph else f'Fig. {figure_number}'
    
    return {
        'ok': False,
        'errors': [{
            'type': 'warning',
            'page_number': 'N/A',
            'description': f'图片在文档中出现前未找到引用',
            'suggestion': suggestion,
            'text_snippet': caption_text[:50]  # 使用标题文本作为定位关键字
        }]
    }

def check_doc_with_template(doc_path, template_identifier, enable_content_check=True, api_key=None, skip_checks=None):
    """
    使用指定的模板检测文档中的图片格式
    
    参数:
        doc_path: Word文档路径
        template_identifier: 模板标识符（文件路径或模板名称）
        enable_content_check: 是否启用图片内容智能检测（需要API密钥）
        api_key: 硅基流动API密钥（启用内容检测时需要）
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
    
    返回:
        {'ok': bool, 'errors': []}
    """
    # 设置全局跳过检测项配置
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
                from paper_detect.Figure_content_detect import FigureContentDetector
            except ImportError:
                # 如果失败，尝试相对导入
                from .Figure_content_detect import FigureContentDetector
            
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
    report = {'ok': True, 'errors': []}
    
    # 0. 找到Introduction的位置，跳过之前的图片（如OSID标识等非论文图片）
    intro_start_idx = 0
    intro_keywords = ['introduction', '引言', '0 introduction', '1 introduction']
    for idx, para in enumerate(doc.paragraphs):
        text_lower = para.text.strip().lower()
        if any(keyword in text_lower for keyword in intro_keywords):
            intro_start_idx = idx
            print(f"  找到Introduction在段落 {idx}")
            break
    
    # 1. 找出所有包含图片的段落（按文档顺序），跳过Introduction之前的
    # 注意：有些Fig的图片在标题段落本身（如Fig.1），有些在标题上方的空段落中
    picture_paragraphs = []
    caption_pattern = tpl.get('figure_detection_rules', {}).get('caption_pattern', r'^\s*Fig\.?\s*(\d+)[.:\s]*(.*)$')
    
    for idx, paragraph in enumerate(doc.paragraphs):
        # 跳过Introduction之前的段落
        if idx < intro_start_idx:
            continue
            
        if has_picture_object(paragraph):
            picture_paragraphs.append({
                'paragraph': paragraph,
                'paragraph_index': idx
            })
    
    print(f"  识别到 {len(picture_paragraphs)} 张图片（Introduction之后）")
    
    if not picture_paragraphs:
        report['ok'] = False
        report['errors'].append({
            'type': 'error',
            'page_number': 'N/A',
            'description': '文档中未找到任何图片',
            'suggestion': '建议：确保文档中包含图片对象',
            'text_snippet': 'N/A'
        })
        return report
    
    # 2. 对每张图片进行检查
    caption_pattern = tpl.get('figure_detection_rules', {}).get('caption_pattern', r'^\s*Fig\.\s+(\d+)\s+(.+)$')
    figure_numbers = []
    checked_figure_numbers = set()  # 记录已检测的编号，避免分图重复检测
    
    for fig_idx, pic_info in enumerate(picture_paragraphs, start=1):
        picture_para = pic_info['paragraph']
        pic_index = pic_info['paragraph_index']
        
        # 2.1 检查是否有标题
        # 首先检查图片段落本身是否就是标题段落（如Fig.1的情况）
        caption_found = None
        pic_text = picture_para.text.strip()
        match = re.match(caption_pattern, pic_text, re.IGNORECASE)
        picture_and_caption_in_same_para = False  # 标记图片和标题是否在同一段落
        
        if match:
            # 图片就在标题段落中 - 这是格式错误
            figure_num = int(match.group(1))
            
            # 检查是否是分图（编号已被检测过），如果是则跳过
            if figure_num in checked_figure_numbers:
                continue
            
            figure_title = match.group(2).strip()
            caption_found = {
                'paragraph': picture_para,
                'number': figure_num,
                'title': figure_title,
                'full_text': pic_text
            }
            figure_numbers.append(figure_num)
            checked_figure_numbers.add(figure_num)
            picture_and_caption_in_same_para = True
            
            # 报告格式错误：图片和标题应该分段
            report['ok'] = False
            report['errors'].append({
                'type': 'error',
                'page_number': f"段落{pic_index + 1}",
                'description': f"Fig.{figure_num} - 图片和标题在同一段落，应分为两段",
                'suggestion': '建议：将图片段落和标题段落分开，图片单独一段，标题单独一段',
                'text_snippet': pic_text[:60] if len(pic_text) > 60 else pic_text
            })
        else:
            # 图片不在标题段落，向下查找标题（1-2个段落内）
            for i in range(pic_index + 1, min(pic_index + 3, len(doc.paragraphs))):
                caption_para = doc.paragraphs[i]
                match = re.match(caption_pattern, caption_para.text.strip(), re.IGNORECASE)
                if match:
                    figure_num = int(match.group(1))
                    
                    # 检查是否是分图（编号已被检测过），如果是则跳过
                    if figure_num in checked_figure_numbers:
                        caption_found = None  # 重置为None，表示跳过
                        break
                    
                    figure_title = match.group(2).strip()
                    caption_found = {
                        'paragraph': caption_para,
                        'number': figure_num,
                        'title': figure_title,
                        'full_text': caption_para.text.strip()
                    }
                    figure_numbers.append(figure_num)
                    checked_figure_numbers.add(figure_num)
                    break
        
        # 如果是分图已被跳过，caption_found会是None，直接continue
        if not caption_found:
            continue
        
        if caption_found:
            # 2.2 检查标题格式（只在图片和标题分开时检查）
            if not picture_and_caption_in_same_para:
                format_result = check_caption_format(caption_found, tpl)
                if not format_result['ok']:
                    report['ok'] = False
                    # 为每个error添加图片编号前缀
                    for error in format_result['errors']:
                        error['description'] = f"Fig.{caption_found['number']} - {error['description']}"
                        report['errors'].append(error)
        else:
            # 没有标题
            report['ok'] = False
            report['errors'].append({
                'type': 'error',
                'page_number': f"段落{pic_index + 1}",
                'description': f"第{fig_idx}张图片缺少标题（应为：Fig. 编号 标题文字）",
                'suggestion': '建议：在图片下方添加标题，格式为"Fig. 编号 标题文字"',
                'text_snippet': 'N/A'
            })
        
        # 2.3 检查图片对齐（只在图片和标题分开时检查）
        if not picture_and_caption_in_same_para and tpl.get('check_rules', {}).get('picture_alignment_check', True):
            is_centered, alignment = check_picture_alignment(picture_para)
            if not is_centered:
                alignment_names = {0: '左对齐', 1: '居中对齐', 2: '右对齐', 3: '两端对齐'}
                alignment_name = alignment_names.get(alignment, f'未知({alignment})')
                report['ok'] = False
                fig_prefix = f"Fig.{caption_found['number']}" if caption_found else f"第{fig_idx}张图片"
                report['errors'].append({
                    'type': 'warning',
                    'page_number': f"段落{pic_index + 1}",
                    'description': f"{fig_prefix} - 图片应居中对齐（当前：{alignment_name}）",
                    'suggestion': '建议：将图片段落设置为居中对齐',
                    'text_snippet': 'N/A'
                })
        
        # 2.4 检查图片内容（如果启用）- 只在图片和标题分开时检查
        if not picture_and_caption_in_same_para and content_detector:
            print(f"  正在检测第 {fig_idx} 张图片的内容规范性...")
            fig_num = caption_found['number'] if caption_found else fig_idx
            content_result = content_detector.detect_figure_content(
                picture_para, 
                doc_path, 
                figure_number=fig_num
            )
            
            if not content_result['ok']:
                report['ok'] = False
                # 为内容检测的errors添加图片编号前缀
                for error in content_result.get('errors', []):
                    error['description'] = f"Fig.{fig_num} - {error['description']}"
                    report['errors'].append(error)
        
        # 2.5 检查图片引用（新增）- 只在图片和标题分开时检查
        if not picture_and_caption_in_same_para and caption_found and tpl.get('check_rules', {}).get('figure_reference_check', True):
            reference_result = check_figure_reference(
                doc, 
                caption_found['number'],
                pic_index,
                caption_paragraph=caption_found['paragraph'],  # 传递标题段落用于添加批注
                search_range=tpl.get('check_rules', {}).get('reference_search_range', 2)
            )
            if not reference_result['ok']:
                report['ok'] = False
                # 为引用检测的errors添加图片编号前缀
                for error in reference_result.get('errors', []):
                    error['description'] = f"Fig.{caption_found['number']} - {error['description']}"
                    report['errors'].append(error)
    
    # 3. 检查编号连续性（只对有标题的图片）
    if figure_numbers:
        numbers_sorted = sorted(figure_numbers)
        expected_start = tpl.get('check_rules', {}).get('numbering_start', 1)
        
        if numbers_sorted[0] != expected_start:
            report['ok'] = False
            report['errors'].append({
                'type': 'error',
                'page_number': 'N/A',
                'description': f"图片编号应从{expected_start}开始，实际从{numbers_sorted[0]}开始",
                'suggestion': f"建议：将第一张图片的编号改为{expected_start}",
                'text_snippet': f"发现编号：{', '.join(map(str, numbers_sorted))}"
            })
        
        # 去重后检查连续性（允许分图的情况，如Fig.13a和Fig.13b会有相同编号）
        numbers_unique = sorted(set(numbers_sorted))
        expected_sequence = list(range(numbers_unique[0], numbers_unique[0] + len(numbers_unique)))
        if numbers_unique != expected_sequence:
            report['ok'] = False
            report['errors'].append({
                'type': 'error',
                'page_number': 'N/A',
                'description': f"图片编号不连续，发现编号：{', '.join(map(str, numbers_unique))}",
                'suggestion': '建议：确保图片编号连续递增',
                'text_snippet': f"期望编号：{', '.join(map(str, expected_sequence))}"
            })
    
    return report



# ---------- 报告生成 ----------

def print_report(report, tpl):
    """打印格式化的检测报告"""
    print("=" * 60)
    print("图片格式检测报告")
    print("=" * 60)
    print()
    
    # 总结
    print("【检查总结】")
    result_text = "通过" if report['overall']['ok'] else "发现问题"
    msg_template = tpl.get('messages', {}).get('summary_overall', '图片格式检查结果: {ok}')
    print(f"  {msg_template.format(ok=result_text)}")
    
    count_msg = tpl.get('messages', {}).get('figure_count', '检测到 {count} 个图片')
    print(f"  {count_msg.format(count=report['summary'].get('figure_count', 0))}")
    
    print()
    
    # 编号检查（如果有标题的图片）
    has_captions = any(fig['has_caption'] for fig in report.get('figures', []))
    if has_captions and report['numbering']['messages']:
        print("【图片编号检查】")
        for msg in report['numbering']['messages']:
            print(f"  ✗ {msg}")
        print()
    
    # 按图片顺序显示详细检查
    if report.get('figures'):
        print("【各图片详细检查】")
        print()
        
        for fig_report in report['figures']:
            fig_idx = fig_report['figure_index']
            
            # 显示图片标题
            if fig_report['has_caption']:
                caption = fig_report['caption_info']
                print(f"  第 {fig_idx} 张图片: Fig.{caption['number']} {caption['title']}")
            else:
                print(f"  第 {fig_idx} 张图片: (无标题)")
            
            # 所有问题
            all_issues = []
            
            # 1. 标题问题
            if not fig_report['has_caption']:
                all_issues.append("❌ 缺少标题")
            elif not fig_report['format_check']['ok']:
                all_issues.append("标题格式问题：")
                for msg in fig_report['format_check']['messages']:
                    all_issues.append(f"  - {msg}")
            else:
                all_issues.append("✓ 标题格式正确")
            
            # 2. 图片本身的问题
            if not fig_report['picture_check']['ok']:
                all_issues.append("图片问题：")
                for msg in fig_report['picture_check']['messages']:
                    all_issues.append(f"  - {msg}")
            else:
                if fig_report['has_caption']:  # 只有有标题的才显示图片OK
                    all_issues.append("✓ 图片位置正确")
            
            # 3. 内容检查（如果有）
            if 'content_check' in fig_report:
                content_check = fig_report['content_check']
                if content_check.get('is_chart', False):
                    if content_check['ok']:
                        all_issues.append("✓ 图表内容符合规范")
                    else:
                        all_issues.append("图表内容问题：")
                        for msg in content_check['messages']:
                            all_issues.append(f"  - {msg}")
                else:
                    all_issues.append(f"ℹ 图片类型: {content_check.get('messages', ['非图表'])[0]}")
            
            # 显示所有问题
            for issue in all_issues:
                if issue.startswith("  -"):
                    print(f"    {issue}")
                else:
                    print(f"    {issue}")
            
            print()
    
    print("=" * 60)

# ---------- 命令行接口 ----------

def main():
    """命令行入口"""
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n使用方法：")
        print("  python Figure_detect.py check <docx文件路径> <模板标识符> [--no-api]")
        print("\n参数说明：")
        print("  --no-api    不调用API检测图片内容（只检测格式）")
        print("\n示例：")
        print("  python Figure_detect.py check template/test.docx Figure")
        print("  python Figure_detect.py check template/test.docx Figure --no-api")
        print("\n注意：图片标题格式为 Fig. 编号 标题（Fig.后必须有空格）")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        if len(sys.argv) < 4:
            print("错误：check命令至少需要2个参数")
            print("使用方法：python Figure_detect.py check <docx文件路径> <模板标识符> [--no-api]")
            sys.exit(1)
        
        doc_path = sys.argv[2]
        template_id = sys.argv[3]
        
        # 检查是否有 --no-api 参数
        enable_api = True
        if len(sys.argv) >= 5 and sys.argv[4] == '--no-api':
            enable_api = False
            print("注意：已禁用API内容检测，只检测图片格式")
        elif len(sys.argv) >= 5:
            print(f"警告：未知参数 '{sys.argv[4]}'，将忽略")
        
        # 检查文件是否存在
        if not os.path.isfile(doc_path):
            print(f"错误：文件不存在: {doc_path}")
            sys.exit(1)
        
        try:
            # 执行检测（根据命令行参数决定是否启用内容检测）
            report = check_doc_with_template(
                doc_path, 
                template_id,
                enable_content_check=enable_api
            )
            
            # 加载模板用于打印
            tpl = load_template(template_id)
            
            # 打印报告
            print_report(report, tpl)
            
            # 保存完整的API响应到JSON文件（只在启用API检测时）
            if enable_api and report.get('figures'):
                import json
                from pathlib import Path
                
                output_dir = Path('api_results')
                output_dir.mkdir(exist_ok=True)
                
                doc_name = Path(doc_path).stem
                output_file = output_dir / f'{doc_name}_api_response.json'
                
                # 提取API响应
                api_responses = {}
                for fig_report in report['figures']:
                    if 'content_check' in fig_report and fig_report['content_check']:
                        fig_idx = fig_report['figure_index']
                        content_check = fig_report['content_check']
                        
                        # 确定图片标识
                        if fig_report['has_caption']:
                            fig_key = f"Fig.{fig_report['caption_info']['number']}"
                        else:
                            fig_key = f"图片{fig_idx}"
                        
                        api_responses[fig_key] = {
                            'image_path': content_check.get('image_path'),
                            'is_chart': content_check.get('is_chart'),
                            'ok': content_check.get('ok'),
                            'messages': content_check.get('messages'),
                            'api_details': content_check.get('details')
                        }
                
                if api_responses:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(api_responses, f, ensure_ascii=False, indent=2)
                    print(f"\n✓ API响应已保存到: {output_file}")
            
        except Exception as e:
            print(f"检测过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print(f"未知命令: {command}")
        print("支持的命令: check")
        sys.exit(1)

if __name__ == '__main__':
    main()

