#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
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
=== 论文格式检测系统 - 摘要检测器 ===

【摘要检测 (Abstract Detection)】

1. 【结构检测】
   - Abstract字段后紧接冒号，冒号后紧接摘要内容
   - 摘要不分段（单一段落）
   - 内容长度验证（50-2000字符）

2. 【格式检测】
   - 字体为Times New Roman，加粗，1.5倍行间距
   - 字号为小四(12pt)
   - 无斜体要求，无行前行后间距要求
   - 两端对齐，无缩进（顶格书写）

3. 【技术特性】
   - 支持段落样式和直接格式的混合检测
   - 智能段落对齐检测（处理复杂的样式继承）
   - 完整的结构、段落、格式三维度检测
   - 详细的格式错误诊断和建议
"""

# ---------- 模板加载 ----------
def resolve_template_path(identifier):
    if os.path.isfile(identifier):
        return identifier
    candidate = os.path.join("templates", identifier + ".json")
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(f"Template not found: '{identifier}' (tried file path and {candidate})")

def load_template(identifier):
    tpl_path = resolve_template_path(identifier)
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = json.load(f)
    return tpl

# ---------- 简化的字体检测 ----------
def detect_font_for_run(run, paragraph=None):
    """
    简化的字体检测函数（专用于摘要检测）
    返回 (font_size_pt, font_name, is_bold, is_italic, line_spacing)
    """
    if not run:
        return 12.0, "Unknown", False, False, 1.0
    
    # 1. 字体名称检测
    font_name = "Unknown"
    try:
        if getattr(run.font, 'name', None):
            font_name = run.font.name
        else:
            font_name = "Times New Roman"  # 默认使用学术常用字体
    except Exception:
        font_name = "Times New Roman"
    
    # 2. 字号检测
    font_size = 12.0  # 默认小四
    try:
        if getattr(run.font, 'size', None) and getattr(run.font.size, 'pt', None):
            font_size = float(run.font.size.pt)
        elif hasattr(run._element, 'rPr') and run._element.rPr is not None:
            sz = run._element.rPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
            if sz is not None and sz.get('val'):
                font_size = float(int(sz.get('val'))) / 2.0
    except Exception:
        pass
    
    # 3. 加粗检测 - 优先直接格式，直接格式为None时使用样式格式
    is_bold = False
    try:
        if run and run.font and run.font.bold is not None:
            is_bold = bool(run.font.bold)
        elif paragraph and paragraph.style and paragraph.style.font and paragraph.style.font.bold is not None:
            is_bold = bool(paragraph.style.font.bold)
        elif hasattr(run._element, 'rPr') and run._element.rPr is not None:
            b = run._element.rPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b')
            is_bold = b is not None
    except Exception:
        pass
    
    # 4. 斜体检测 - 优先直接格式，直接格式为None时使用样式格式
    is_italic = False
    try:
        if run and run.font and run.font.italic is not None:
            is_italic = bool(run.font.italic)
        elif paragraph and paragraph.style and paragraph.style.font and paragraph.style.font.italic is not None:
            is_italic = bool(paragraph.style.font.italic)
        elif hasattr(run._element, 'rPr') and run._element.rPr is not None:
            i = run._element.rPr.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}i')
            is_italic = i is not None
    except Exception:
        pass
    
    # 5. 行间距检测
    line_spacing = 1.0  # 默认单倍行距
    try:
        # 优先级1: 检查段落直接格式的行距
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
        # 优先级2: 检查段落样式的行距
        elif paragraph and paragraph.style and paragraph.style.paragraph_format.line_spacing:
            line_spacing = float(paragraph.style.paragraph_format.line_spacing)
    except Exception:
        pass
    
    return font_size, font_name, is_bold, is_italic, line_spacing

def get_font_size(pt_size, tpl=None):
    """字体大小转换为中文字号"""
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
            1.5: "1.5倍行距", 2.0: "双倍行距"
        }
    
    if not spacing_map:
        return f"{spacing}倍行距"
    
    closest_spacing = min(spacing_map.keys(), key=lambda x: abs(x - spacing))
    return spacing_map[closest_spacing]

def get_alignment_name(alignment_value, tpl=None):
    """段落对齐方式转换为中文描述"""
    alignment_map = {
        0: "左对齐", 1: "居中对齐", 2: "右对齐", 3: "两端对齐"
    }
    return alignment_map.get(alignment_value, f"未知对齐({alignment_value})")

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

# ---------- 请将您代码中旧的 detect_paragraph_alignment 函数替换为这个新版本 ----------

def detect_paragraph_alignment(paragraph):
    """
    改进的段落对齐检测，按照明确的优先级处理直接格式和样式格式
    
    检测逻辑：
    1. 如果直接格式不为None，直接使用直接格式结果
    2. 如果直接格式为None，但样式格式为JUSTIFY，归为两端对齐
    3. 如果直接格式不是两端对齐，就不是两端对齐
    4. 如果样式格式不是两端对齐，也不是两端对齐
    5. 最终默认为左对齐
    """
    
    # 优先级1: 检查直接格式
    direct_alignment = paragraph.paragraph_format.alignment
    if direct_alignment is not None:
        # 如果有直接格式设置，直接使用
        return int(direct_alignment)
    
    # 优先级2: 如果直接格式为None，检查样式格式
    if paragraph.style:
        try:
            style_alignment = paragraph.style.paragraph_format.alignment
            if style_alignment is not None:
                # 如果样式有对齐设置，使用样式对齐
                return int(style_alignment)
        except Exception:
            pass
    
    # 优先级3: 检查XML样式定义（处理复杂的样式继承）
    if paragraph.style and paragraph.style.style_id:
        try:
            xml_alignment = get_style_alignment(paragraph.part.document, paragraph.style.style_id)
            if xml_alignment is not None:
                return xml_alignment
        except Exception:
            pass
            
    # 默认值: 左对齐
    return WD_PARAGRAPH_ALIGNMENT.LEFT

def detect_paragraph_indent(paragraph):
    """检测段落缩进"""
    try:
        fmt = paragraph.paragraph_format
        first_line_indent = fmt.first_line_indent.pt if fmt.first_line_indent else 0.0
        left_indent = fmt.left_indent.pt if fmt.left_indent else 0.0
        right_indent = fmt.right_indent.pt if fmt.right_indent else 0.0
        return first_line_indent, left_indent, right_indent
    except Exception:
        return 0.0, 0.0, 0.0

# ---------- 摘要检测逻辑 ----------
def check_abstract_structure(text, tpl):
    """
    检查摘要结构（Abstract:冒号格式）
    返回 {'ok': bool, 'errors': [], 'content': str}
    """
    report = {'ok': True, 'errors': [], 'content': ''}
    
    # 检查Abstract:格式
    structure_rules = tpl.get('structure_rules', {})
    header_pattern = structure_rules.get('header_pattern', r'^\\s*Abstract\\s*:\\s*(.+)$')
    
    # 提取文本片段
    text_snippet = text.strip()[:150]
    if len(text.strip()) > 150:
        text_snippet += '...'
    
    try:
        match = re.match(header_pattern, text.strip(), re.DOTALL | re.IGNORECASE)
        if match:
            report['content'] = match.group(1).strip()
            # 格式正确，不添加错误
        elif re.match(r'^\s*Abstract\s*$', text.strip(), re.IGNORECASE):
            # 检测到错误格式：Abstract单独成行
            report['ok'] = False
            report['errors'].append({
                'type': 'error',
                'page_number': 'N/A',
                'description': "摘要格式错误：'Abstract'后应紧跟冒号和内容",
                'suggestion': "建议：使用正确格式 'Abstract: 摘要内容...'",
                'text_snippet': text_snippet
            })
            # 将文本作为内容（用于后续长度检查，即使格式错误）
            report['content'] = text.strip()
        else:
            report['ok'] = False
            error_msg = tpl.get('messages', {}).get('structure_header_error', '未找到Abstract标题或格式不正确')
            report['errors'].append({
                'type': 'error',
                'page_number': 'N/A',
                'description': error_msg,
                'suggestion': "建议：确保摘要以'Abstract: '开头",
                'text_snippet': text_snippet
            })
    except Exception as e:
        report['ok'] = False
        report['errors'].append({
            'type': 'error',
            'page_number': 'N/A',
            'description': f"摘要格式检查出错: {str(e)}",
            'suggestion': "建议：检查摘要格式是否符合规范",
            'text_snippet': text_snippet
        })
    
    # 检查内容长度
    if report['content']:
        content_length = len(report['content'])
        min_length = structure_rules.get('min_content_length', 50)
        max_length = structure_rules.get('max_content_length', 2000)
        
        if content_length < min_length:
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"摘要内容过短：当前{content_length}字符，最少需要{min_length}字符",
                'suggestion': f"建议：补充摘要内容至至少{min_length}字符",
                'text_snippet': report['content'][:150] + ('...' if len(report['content']) > 150 else '')
            })
        elif content_length > max_length:
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': 'N/A',
                'description': f"摘要内容过长：当前{content_length}字符，最多允许{max_length}字符",
                'suggestion': f"建议：精简摘要内容至{max_length}字符以内",
                'text_snippet': report['content'][:150] + ('...' if len(report['content']) > 150 else '')
            })
    
    return report

def check_abstract_paragraphs(doc, tpl):
    """
    检查摘要是否分段
    返回 {'ok': bool, 'errors': [], 'abstract_paragraph': paragraph, 'para_index': int}
    """
    report = {'ok': True, 'errors': [], 'abstract_paragraph': None, 'para_index': None}
    
    # 方案1：查找包含Abstract:的段落（正确格式）
    abstract_with_colon = []
    abstract_indices = []
    for i, paragraph in enumerate(doc.paragraphs):
        if paragraph.text and re.search(r'\bAbstract\s*:', paragraph.text, re.IGNORECASE):
            abstract_with_colon.append(paragraph)
            abstract_indices.append(i)  # python索引（从0开始）
    
    # 方案2：查找单独的Abstract段落（错误格式）
    abstract_alone = None
    abstract_alone_index = None
    next_paragraph = None
    next_para_index = None
    for i, paragraph in enumerate(doc.paragraphs):
        if paragraph.text and re.match(r'^\s*Abstract\s*$', paragraph.text.strip(), re.IGNORECASE):
            abstract_alone = paragraph
            abstract_alone_index = i  # python索引（从0开始）
            # 查找下一个非空段落作为摘要内容
            for j in range(i+1, min(i+3, len(doc.paragraphs))):
                if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
                    next_paragraph = doc.paragraphs[j]
                    next_para_index = j  # python索引（从0开始）
                    break
            break
    
    if len(abstract_with_colon) == 1:
        # 找到正确格式
        report['abstract_paragraph'] = abstract_with_colon[0]
        report['para_index'] = abstract_indices[0]
        # 格式正确，不添加错误
    elif abstract_alone:
        # 找到错误格式（Abstract单独一行）
        report['ok'] = False
        report['abstract_paragraph'] = next_paragraph  # 返回内容段落用于后续格式检查
        report['para_index'] = next_para_index
        
        text_snippet = 'N/A'
        if next_paragraph:
            text_snippet = next_paragraph.text[:150]
            if len(next_paragraph.text) > 150:
                text_snippet += '...'
        
        report['errors'].append({
            'type': 'error',
            'page_number': f"段落{abstract_alone_index}",
            'description': "摘要格式错误：'Abstract'应与内容在同一段落，格式为'Abstract: 内容'",
            'suggestion': "建议：将'Abstract'标题与摘要内容合并到同一段落，使用'Abstract: 内容'格式",
            'text_snippet': text_snippet
        })
    elif len(abstract_with_colon) > 1:
        report['ok'] = False
        error_msg = tpl.get('messages', {}).get('structure_paragraph_error', '摘要分段错误：摘要应为单一段落')
        report['errors'].append({
            'type': 'error',
            'page_number': 'N/A',
            'description': error_msg,
            'suggestion': "建议：将摘要合并为单一段落",
            'text_snippet': 'N/A'
        })
    else:
        report['ok'] = False
        report['errors'].append({
            'type': 'error',
            'page_number': 'N/A',
            'description': "未找到Abstract段落",
            'suggestion': "建议：添加Abstract段落，格式为'Abstract: 摘要内容'",
            'text_snippet': 'N/A'
        })
    
    return report

def check_abstract_format(paragraph, tpl, para_index=None):
    """
    检查摘要格式（字体、加粗、行间距等）
    返回 {'ok': bool, 'errors': []}
    """
    report = {'ok': True, 'errors': []}
    
    # 提取文本片段
    text_snippet = 'N/A'
    if paragraph and paragraph.text:
        text_snippet = paragraph.text.strip()[:150]
        if len(paragraph.text.strip()) > 150:
            text_snippet += '...'
    
    # 页码信息
    page_number = f"段落{para_index}" if para_index is not None else 'N/A'
    
    if not paragraph or not paragraph.runs:
        report['ok'] = False
        report['errors'].append({
            'type': 'error',
            'page_number': page_number,
            'description': "摘要段落没有文本内容",
            'suggestion': "建议：确保摘要段落包含有效文本",
            'text_snippet': text_snippet
        })
        return report
    
    # 取第一个非空 run
    main_run = None
    for run in paragraph.runs:
        if run.text.strip():
            main_run = run
            break
    
    if not main_run:
        report['ok'] = False
        report['errors'].append({
            'type': 'error',
            'page_number': page_number,
            'description': "摘要段落没有有效文本",
            'suggestion': "建议：确保摘要段落包含有效文本",
            'text_snippet': text_snippet
        })
        return report
    
    # 获取格式规则
    format_rules = tpl.get('format_rules', {}).get('abstract', {})
    
    # 检测实际格式
    actual_size_pt, actual_font_name, actual_bold, actual_italic, actual_line_spacing = detect_font_for_run(main_run, paragraph)
    
    # 字体大小检查
    if not should_skip_check('font_size') and 'font_size_pt' in format_rules:
        expected_size_pt = float(format_rules['font_size_pt'])
        actual_size_name = get_font_size(actual_size_pt, tpl)
        expected_size_name = get_font_size(expected_size_pt, tpl)
        print(f"字体大小: {actual_size_name}（{actual_size_pt}pt）(期望: {expected_size_name}（{expected_size_pt}pt）)")
        if abs(actual_size_pt - expected_size_pt) > 0.5:
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': page_number,
                'description': f"字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）",
                'suggestion': f"建议：调整字体大小为{expected_size_name}（{expected_size_pt}pt）",
                'text_snippet': text_snippet
            })
    
    # 字体名称检查
    if not should_skip_check('font_name') and 'font_name' in format_rules:
        expected_font_name = str(format_rules['font_name'])
        print(f"字体名称: {actual_font_name} (期望: {expected_font_name})")
        if expected_font_name.lower() not in actual_font_name.lower():
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': page_number,
                'description': f"字体应为{expected_font_name}，实际为{actual_font_name}",
                'suggestion': f"建议：将字体设置为{expected_font_name}",
                'text_snippet': text_snippet
            })
    
    # 加粗检查
    if not should_skip_check('bold') and 'bold' in format_rules:
        expected_bold = bool(format_rules['bold'])
        print(f"加粗: {'是' if actual_bold else '否'} (期望: {'是' if expected_bold else '否'})")
        if actual_bold != expected_bold:
            bold_status = "加粗" if expected_bold else "不加粗"
            actual_status = "加粗" if actual_bold else "不加粗"
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': page_number,
                'description': f"字体应为{bold_status}，实际为{actual_status}",
                'suggestion': f"建议：将字体设置为{bold_status}",
                'text_snippet': text_snippet
            })
    
    # 斜体检查
    if not should_skip_check('italic') and 'italic' in format_rules:
        expected_italic = bool(format_rules['italic'])
        print(f"斜体: {'是' if actual_italic else '否'} (期望: {'是' if expected_italic else '否'})")
        if actual_italic != expected_italic:
            italic_status = "斜体" if expected_italic else "正体"
            actual_status = "斜体" if actual_italic else "正体"
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': page_number,
                'description': f"字体应为{italic_status}，实际为{actual_status}",
                'suggestion': f"建议：将字体设置为{italic_status}",
                'text_snippet': text_snippet
            })
    
    # 行间距检查
    if not should_skip_check('spacing') and 'line_spacing' in format_rules:
        expected_line_spacing = float(format_rules['line_spacing'])
        actual_spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
        expected_spacing_name = get_line_spacing_name(expected_line_spacing, tpl)
        print(f"行间距: {actual_spacing_name}（{actual_line_spacing}倍）(期望: {expected_spacing_name}（{expected_line_spacing}倍）)")
        if abs(actual_line_spacing - expected_line_spacing) > 0.1:
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': page_number,
                'description': f"行间距应为{expected_spacing_name}（{expected_line_spacing}倍），实际为{actual_spacing_name}（{actual_line_spacing}倍）",
                'suggestion': f"建议：调整行间距为{expected_spacing_name}（{expected_line_spacing}倍）",
                'text_snippet': text_snippet
            })
    
    # 段落对齐检查
    if 'alignment' in format_rules:
        expected_alignment_str = str(format_rules['alignment'])
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        expected_alignment = alignment_map.get(expected_alignment_str, 0)
        
        actual_alignment = detect_paragraph_alignment(paragraph)
        actual_alignment_name = get_alignment_name(actual_alignment, tpl)
        expected_alignment_name = get_alignment_name(expected_alignment, tpl)
        print(f"段落对齐: {actual_alignment_name} (期望: {expected_alignment_name})")
        if actual_alignment != expected_alignment:
            report['ok'] = False
            report['errors'].append({
                'type': 'warning',
                'page_number': page_number,
                'description': f"段落应为{expected_alignment_name}，实际为{actual_alignment_name}",
                'suggestion': f"建议：将对齐方式设置为{expected_alignment_name}",
                'text_snippet': text_snippet
            })
    
    # 段落缩进检查
    if 'first_line_indent' in format_rules or 'left_indent' in format_rules or 'right_indent' in format_rules:
        first_line_indent, left_indent, right_indent = detect_paragraph_indent(paragraph)
        
        if 'first_line_indent' in format_rules:
            expected_first_indent = float(format_rules['first_line_indent'])
            print(f"首行缩进: {first_line_indent:.1f}pt (期望: {expected_first_indent}pt)")
            if abs(first_line_indent - expected_first_indent) > 1.0:  # 1pt容差
                report['ok'] = False
                report['errors'].append({
                    'type': 'warning',
                    'page_number': page_number,
                    'description': f"首行缩进应为{expected_first_indent}pt，实际为{first_line_indent:.1f}pt",
                    'suggestion': f"建议：调整首行缩进为{expected_first_indent}pt",
                    'text_snippet': text_snippet
                })
        
        if 'left_indent' in format_rules:
            expected_left_indent = float(format_rules['left_indent'])
            print(f"左缩进: {left_indent:.1f}pt (期望: {expected_left_indent}pt)")
            if abs(left_indent - expected_left_indent) > 1.0:
                report['ok'] = False
                report['errors'].append({
                    'type': 'warning',
                    'page_number': page_number,
                    'description': f"左缩进应为{expected_left_indent}pt，实际为{left_indent:.1f}pt",
                    'suggestion': f"建议：调整左缩进为{expected_left_indent}pt",
                    'text_snippet': text_snippet
                })
        
        if 'right_indent' in format_rules:
            expected_right_indent = float(format_rules['right_indent'])
            print(f"右缩进: {right_indent:.1f}pt (期望: {expected_right_indent}pt)")
            if abs(right_indent - expected_right_indent) > 1.0:
                report['ok'] = False
                report['errors'].append({
                    'type': 'warning',
                    'page_number': page_number,
                    'description': f"右缩进应为{expected_right_indent}pt，实际为{right_indent:.1f}pt",
                    'suggestion': f"建议：调整右缩进为{expected_right_indent}pt",
                    'text_snippet': text_snippet
                })
    
    print(f"发现 {len(report['errors'])} 个格式问题")
    print("---")
    
    return report


def check_abstract_with_template(doc_path, template_identifier, skip_checks=None):
    """
    主检查函数：检查摘要格式
    参数:
        doc_path: 文档路径
        template_identifier: 模板标识符
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
    返回包含所有errors的报告
    """
    # 设置全局跳过检测项配置
    global _skip_checks_config
    _skip_checks_config = skip_checks or []
    
    tpl = load_template(template_identifier)
    doc = Document(doc_path)
    
    # 先调用check_abstract_paragraphs来查找摘要（它能处理多种格式）
    paragraphs_report = check_abstract_paragraphs(doc, tpl)
    
    # 根据找到的段落提取文本
    abstract_text = ""
    if paragraphs_report.get('abstract_paragraph'):
        abstract_text = paragraphs_report['abstract_paragraph'].text.strip()
    else:
        # 如果没找到段落，尝试查找单独的Abstract标题
        for i, paragraph in enumerate(doc.paragraphs):
            if paragraph.text and re.match(r'^\s*Abstract\s*$', paragraph.text.strip(), re.IGNORECASE):
                # 找到Abstract单独一行，使用它作为文本（用于结构检查）
                abstract_text = paragraph.text.strip()
                # 如果下一段是内容，也包含它
                for j in range(i+1, min(i+2, len(doc.paragraphs))):
                    if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
                        abstract_text = "Abstract\n" + doc.paragraphs[j].text.strip()
                        break
                break
        
        # 如果还是没找到，最后尝试查找包含Abstract:的段落
        if not abstract_text:
            for paragraph in doc.paragraphs:
                if paragraph.text and re.search(r'\bAbstract\s*:', paragraph.text, re.IGNORECASE):
                    abstract_text = paragraph.text.strip()
                    break
    
    print(f"abstract_text: {abstract_text[:50] if abstract_text else 'Not found'}")
    
    # 如果完全找不到Abstract
    if not abstract_text and not paragraphs_report.get('abstract_paragraph'):
        return {
            'ok': False,
            'errors': [{
                'type': 'error',
                'page_number': 'N/A',
                'description': '未找到Abstract段落',
                'suggestion': "建议：添加Abstract段落，格式为'Abstract: 摘要内容'",
                'text_snippet': 'N/A'
            }],
            'structure': {'ok': False, 'errors': []},
            'paragraphs': {'ok': False, 'errors': []},
            'format': {'ok': False, 'errors': []}
        }
    
    # 执行各项检查
    structure_report = check_abstract_structure(abstract_text, tpl) if abstract_text else {'ok': False, 'errors': []}
    
    if paragraphs_report['abstract_paragraph']:
        para_index = paragraphs_report.get('para_index')
        format_report = check_abstract_format(paragraphs_report['abstract_paragraph'], tpl, para_index)
    else:
        format_report = {'ok': False, 'errors': []}
    
    # 合并所有errors
    all_errors = []
    all_errors.extend(structure_report.get('errors', []))
    all_errors.extend(paragraphs_report.get('errors', []))
    all_errors.extend(format_report.get('errors', []))
    
    # 组装最终报告
    report = {
        'ok': (structure_report['ok'] and paragraphs_report['ok'] and format_report['ok']),
        'errors': all_errors,  # 统一的errors数组
        'structure': structure_report,
        'paragraphs': paragraphs_report,
        'format': format_report
    }
    
    return report

# ---------- 报告输出 ----------
def print_abstract_report(report):
    """打印摘要检查报告"""
    print("=== Abstract Check Report ===")
    
    # 打印总体状态
    print("--- OVERALL ---")
    print(" OK:", report.get('ok', False))
    
    # 打印所有错误
    if 'errors' in report and report['errors']:
        print("--- ERRORS ---")
        for error in report['errors']:
            print(f"  [{error.get('type', 'unknown').upper()}] {error.get('page_number', 'N/A')}")
            print(f"    描述: {error.get('description', '')}")
            print(f"    建议: {error.get('suggestion', '')}")
            if error.get('text_snippet') and error.get('text_snippet') != 'N/A':
                print(f"    片段: {error.get('text_snippet', '')[:100]}...")
    else:
        print("--- NO ERRORS ---")
        print("  摘要检查通过")
    
    # 打印详细的子检查状态（可选）
    sections = [
        ('structure', 'STRUCTURE'),
        ('paragraphs', 'PARAGRAPHS'), 
        ('format', 'FORMAT')
    ]
    
    print("\n--- DETAILED CHECKS ---")
    for sec_key, sec_name in sections:
        if sec_key in report:
            info = report[sec_key]
            print(f"{sec_name}: {'✓' if info.get('ok', False) else '✗'}")
            if 'errors' in info and info['errors']:
                print(f"  {len(info['errors'])} 个问题")

def print_help():
    print("Usage:")
    print("  python Abstract_detect.py check <paper.docx> <template.json_or_name>")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print_help()
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'check':
        paper_path = sys.argv[2]
        tpl_id = sys.argv[3]
        if not os.path.isfile(paper_path):
            print(f"论文文件不存在: {paper_path}")
            sys.exit(1)
        try:
            print("=== 开始摘要格式检查 ===")
            report = check_abstract_with_template(paper_path, tpl_id)
        except Exception as e:
            print("检查时出错:", e)
            sys.exit(1)
        print_abstract_report(report)
    else:
        print_help()
        sys.exit(0)
'''
python paper_detect\Abstract_detect.py check template\test_abstract.docx templates\Abstract.json                               
'''