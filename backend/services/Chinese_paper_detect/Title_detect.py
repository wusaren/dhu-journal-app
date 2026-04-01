#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一标题检测器
支持中文标题和英文标题的格式检测
依据模板自动判断检测类型
"""

import os
import sys
import json
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn

# 添加项目根目录到 sys.path 以支持独立运行
if __name__ == "__main__" and __package__ is None:
    file = Path(__file__).resolve()
    parent, root = file.parent, file.parents[1]
    sys.path.append(str(root))
    try:
        sys.path.remove(str(parent))
    except ValueError:
        pass

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
=== 论文格式检测系统 - 统一标题检测器 ===

【统一标题检测 (Unified Title Detection)】

支持：
1. 中文标题检测
   - 位于摘要上方
   - 黑体3号字（16pt）
   - 段前段后0.7厘米
   - 单倍行距
   - 居中对齐
   
2. 英文标题检测
   - 位于摘要上方
   - 三号（16pt）居中
   - 全大写
   - 每行左右两边至少留五个字符空格
   - Times New Roman加粗
   - 段前段后0.7厘米
   - 居中对齐
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


# ---------- 文档默认设置提取函数 ----------

def get_document_default_fonts(doc):
    """
    从文档的默认字符格式中获取字体设置
    
    返回: {'ascii': str, 'east_asia': str} 或 None
    """
    try:
        doc_defaults = doc.styles._element.xpath(
            '//w:docDefaults/w:rPrDefault/w:rPr/w:rFonts'
        )
        if doc_defaults:
            rfonts = doc_defaults[0]
            result = {}
            
            ascii_font = rfonts.get(qn('w:ascii'))
            hansi_font = rfonts.get(qn('w:hAnsi'))
            east_asia_font = rfonts.get(qn('w:eastAsia'))
            
            if ascii_font:
                result['ascii'] = ascii_font
            if hansi_font:
                result['hAnsi'] = hansi_font
            if east_asia_font:
                result['east_asia'] = east_asia_font
            
            if result:
                return result
    except Exception:
        pass
    
    return None


def get_document_default_line_spacing(doc):
    """从文档的默认段落格式中获取行距设置"""
    try:
        pPr_defaults = doc.styles._element.xpath(
            '//w:docDefaults/w:pPrDefault/w:pPr'
        )
        if pPr_defaults:
            pPr = pPr_defaults[0]
            spacing_nodes = pPr.xpath(
                './/w:spacing',
                namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            )
            if spacing_nodes:
                spacing = spacing_nodes[0]
                if spacing.get(qn('w:line')):
                    line_val = int(spacing.get(qn('w:line')))
                    return line_val / 240.0
    except Exception:
        pass
    return None


def get_normal_style_line_spacing(doc):
    """从Normal样式中获取行距设置"""
    try:
        try:
            normal_style = doc.styles['Normal']
            if normal_style and hasattr(normal_style, 'element'):
                spacing_nodes = normal_style.element.xpath('.//w:spacing')
                if spacing_nodes:
                    spacing = spacing_nodes[0]
                    if spacing.get(qn('w:line')):
                        line_val = int(spacing.get(qn('w:line')))
                        return line_val / 240.0
        except Exception:
            pass

        normal_styles = doc.styles._element.xpath('//w:style[@w:styleId="Normal"]//w:spacing')
        if normal_styles:
            spacing = normal_styles[0]
            if spacing.get(qn('w:line')):
                line_val = int(spacing.get(qn('w:line')))
                return line_val / 240.0
    except Exception:
        pass
    return None


def get_inherited_style_properties(style, doc, visited_styles=None):
    """
    递归获取样式及其继承链的所有属性
    
    参数:
        style: 当前样式对象
        doc: 文档对象
        visited_styles: 已访问的样式ID集合（防止循环继承）
    
    返回: dict 包含继承属性
    """
    if visited_styles is None:
        visited_styles = set()
    
    if style and hasattr(style, 'style_id') and style.style_id in visited_styles:
        return {}
    
    if style and hasattr(style, 'style_id'):
        visited_styles.add(style.style_id)
    
    properties = {}
    
    if not style:
        return properties
    
    try:
        # 从样式XML中提取属性
        if hasattr(style, 'element') and style.element is not None:
            # 字体
            rfonts_nodes = style.element.xpath('.//w:rFonts')
            if rfonts_nodes:
                rfonts = rfonts_nodes[0]
                ascii_font = rfonts.get(qn('w:ascii'))
                eastasia_font = rfonts.get(qn('w:eastAsia'))
                hansi_font = rfonts.get(qn('w:hAnsi'))
                if ascii_font:
                    properties.setdefault('font_ascii', ascii_font)
                if eastasia_font:
                    properties.setdefault('font_east_asia', eastasia_font)
                elif hansi_font:
                    properties.setdefault('font_name', hansi_font)
    except Exception:
        pass
    
    # 递归处理父样式
    if hasattr(style, 'base_style') and style.base_style:
        parent_properties = get_inherited_style_properties(style.base_style, doc, visited_styles)
        parent_properties.update(properties)
        properties = parent_properties
    
    return properties


def detect_title_language(tpl):
    """
    检测标题模板的语言类型
    返回: 'chinese' 或 'english'
    """
    # 方法1: 通过模板文件名判断
    tpl_path = resolve_template_path(tpl.get('_template_path', ''))
    if 'English_Title' in tpl_path or 'english_title' in tpl_path.lower():
        return 'english'
    if 'Title' in tpl_path and 'English' not in tpl_path:
        return 'chinese'
    
    # 方法2: 通过模板内容判断
    structure_rules = tpl.get('structure_rules', {})
    must_uppercase = structure_rules.get('must_uppercase', False)
    
    if must_uppercase:
        return 'english'
    
    # 默认返回中文
    return 'chinese'

# ---------- 字体检测函数（支持中英文字体分别检测）----------
def detect_font_for_run(run, paragraph=None, detect_chinese_font=True, doc=None):
    """
    检测run的字体信息，包括中英文字体
    参数:
        run: docx run对象
        paragraph: docx paragraph对象
        detect_chinese_font: 是否检测中文字体
        doc: docx文档对象（用于读取docDefaults）
    返回: (font_size, font_ascii, font_eastasia, is_bold, is_italic, line_spacing)
    """
    font_size = None
    font_name_ascii = None
    font_name_eastasia = None
    is_bold = None
    is_italic = False
    
    if not run:
        return 12.0, "Times New Roman", ("宋体" if detect_chinese_font else None), False, False, 1.0
    
    # 1. 检测字号
    try:
        if run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)
        
        if font_size is None and getattr(run, "style", None) and getattr(run.style, "font", None):
            try:
                if run.style.font.size and hasattr(run.style.font.size, "pt"):
                    font_size = float(run.style.font.size.pt)
            except Exception:
                pass
        
        if font_size is None and paragraph and paragraph.style and getattr(paragraph.style, "font", None):
            try:
                if paragraph.style.font.size and hasattr(paragraph.style.font.size, "pt"):
                    font_size = float(paragraph.style.font.size.pt)
            except Exception:
                pass
        
        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style, "element"):
            sz_nodes = paragraph.style.element.xpath('.//w:sz')
            if sz_nodes and sz_nodes[0].get(qn('w:val')):
                font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
        
        if font_size is None and hasattr(run._element, 'rPr'):
            sz_nodes = run._element.xpath('.//w:sz')
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
                    
                    if detect_chinese_font:
                        if xml_eastasia:
                            font_name_eastasia = xml_eastasia
                        elif xml_hansi and font_name_eastasia is None:
                            font_name_eastasia = xml_hansi
        
        # 从段落样式XML读取字体
        if not font_name_ascii or not font_name_eastasia:
            if paragraph and paragraph.style and hasattr(paragraph.style, 'element'):
                rfonts_list = paragraph.style.element.xpath('.//w:rFonts')
                if rfonts_list:
                    rfonts = rfonts_list[0]
                    xml_ascii_s = rfonts.get(qn('w:ascii'))
                    xml_hansi_s = rfonts.get(qn('w:hAnsi'))
                    xml_eastasia_s = rfonts.get(qn('w:eastAsia'))
                    if not font_name_ascii:
                        if xml_ascii_s:
                            font_name_ascii = xml_ascii_s
                        elif xml_hansi_s:
                            font_name_ascii = xml_hansi_s
                    if detect_chinese_font and not font_name_eastasia:
                        if xml_eastasia_s:
                            font_name_eastasia = xml_eastasia_s
                        elif xml_hansi_s:
                            font_name_eastasia = xml_hansi_s
        
        # 样式继承链追溯：沿 basedOn 链向上读取字体
        if (not font_name_ascii or not font_name_eastasia) and paragraph and paragraph.style and doc:
            try:
                inherited_props = get_inherited_style_properties(paragraph.style, doc)
                if not font_name_ascii and 'font_ascii' in inherited_props:
                    font_name_ascii = inherited_props['font_ascii']
                if detect_chinese_font and not font_name_eastasia:
                    if 'font_east_asia' in inherited_props:
                        font_name_eastasia = inherited_props['font_east_asia']
                    elif 'font_name' in inherited_props:
                        font_name_eastasia = inherited_props['font_name']
            except Exception:
                pass
        
        # docDefaults 兜底
        if not font_name_ascii or not font_name_eastasia:
            if doc:
                doc_defaults = get_document_default_fonts(doc)
                if doc_defaults:
                    if not font_name_ascii:
                        font_name_ascii = doc_defaults.get('ascii') or doc_defaults.get('hAnsi')
                    if detect_chinese_font and not font_name_eastasia:
                        font_name_eastasia = doc_defaults.get('east_asia') or doc_defaults.get('hAnsi')
    except Exception:
        pass
    
    font_name_ascii = font_name_ascii if font_name_ascii else "Times New Roman"
    if detect_chinese_font:
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
    
    # 4. 行间距检测（支持 Normal 样式和 docDefaults 兜底）
    line_spacing = 1.0
    line_spacing_set = False
    try:
        # 优先级1: 段落直接格式
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
            line_spacing_set = True
        # 优先级2: 段落样式
        if not line_spacing_set and paragraph and paragraph.style and paragraph.style.paragraph_format.line_spacing:
            line_spacing = float(paragraph.style.paragraph_format.line_spacing)
            line_spacing_set = True
        # 优先级3: Normal样式和docDefaults — 仅在段落无样式时兜底
        if not line_spacing_set and doc:
            normal_ls = get_normal_style_line_spacing(doc)
            if normal_ls is not None:
                line_spacing = normal_ls
                line_spacing_set = True
            else:
                doc_ls = get_document_default_line_spacing(doc)
                if doc_ls is not None:
                    line_spacing = doc_ls
    except Exception:
        pass

    return font_size, font_name_ascii, font_name_eastasia, is_bold, is_italic, line_spacing

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
            1.25: "1.25倍行距", 1.5: "1.5倍行距", 2.0: "双倍行距"
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

def detect_paragraph_alignment(paragraph):
    """检测段落对齐方式"""
    direct_alignment = paragraph.paragraph_format.alignment
    if direct_alignment is not None:
        return int(direct_alignment)
    
    if paragraph.style:
        try:
            style_alignment = paragraph.style.paragraph_format.alignment
            if style_alignment is not None:
                return int(style_alignment)
        except Exception:
            pass
    
    return WD_PARAGRAPH_ALIGNMENT.LEFT

def detect_paragraph_indent(paragraph):
    """检测段落缩进（返回pt值）"""
    try:
        fmt = paragraph.paragraph_format
        first_line_indent = fmt.first_line_indent.pt if fmt.first_line_indent else 0.0
        left_indent = fmt.left_indent.pt if fmt.left_indent else 0.0
        right_indent = fmt.right_indent.pt if fmt.right_indent else 0.0
        return first_line_indent, left_indent, right_indent
    except Exception:
        return 0.0, 0.0, 0.0

def cm_to_pt(cm_value):
    """将厘米转换为磅（pt）"""
    return float(cm_value) * 28.35

# ---------- 标题检测逻辑 ----------
def find_abstract_start(doc, language='chinese'):
    """
    查找摘要开始位置
    参数:
        doc: Word文档对象
        language: 'chinese' 或 'english'
    返回: 摘要标题的段落索引，如果未找到返回None
    """
    abstract_header_pattern = r'^\s*摘\s要\s*$' if language == 'chinese' else r"^\s*ABSTRACT\s*$"
    match_flags = re.IGNORECASE if language == 'english' else 0
    
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if re.match(abstract_header_pattern, text, match_flags):
            return idx
    return None

def find_title_paragraph(doc, abstract_idx, language='chinese'):
    """
    查找标题段落（位于摘要上方）
    参数:
        doc: Word文档对象
        abstract_idx: 摘要标题的段落索引
        language: 'chinese' 或 'english'
    返回: 标题段落对象和索引，如果未找到返回(None, None)
    """
    if abstract_idx is None or abstract_idx == 0:
        return None, None
    
    # 从摘要上方开始查找，跳过空段落
    for i in range(abstract_idx - 1, -1, -1):
        paragraph = doc.paragraphs[i]
        text = paragraph.text.strip()
        if text:
            # 检查是否包含中文字符（中文标题）或全大写英文（英文标题）
            if language == 'chinese':
                if re.search(r'[\u4e00-\u9fff]', text):
                    return paragraph, i
            else:
                # 英文标题：检查是否全大写（排除纯数字或特殊符号）
                if re.search(r'[A-Z]', text) and text.isupper():
                    return paragraph, i
    
    return None, None

def check_title_structure(doc, tpl, language=None):
    """
    检查标题结构（统一函数，支持中文和英文）
    返回 {'ok': bool, 'messages': [], 'title_paragraph': paragraph, 'title_text': str}
    """
    if language is None:
        language = detect_title_language(tpl)
    
    report = {'ok': True, 'messages': [], 'title_paragraph': None, 'title_text': ''}
    
    structure_rules = tpl.get('structure_rules', {})
    min_length = structure_rules.get('min_length', 5)
    max_length = structure_rules.get('max_length', 200)
    
    # 查找摘要位置
    abstract_idx = find_abstract_start(doc, language)
    
    if abstract_idx is None:
        report['ok'] = False
        error_msg = tpl.get('messages', {}).get('structure_position_error')
        if error_msg:
            report['messages'].append(error_msg)
        else:
            report['messages'].append("未找到摘要，无法确定标题位置")
        return report
    
    # 查找标题段落
    title_para, title_idx = find_title_paragraph(doc, abstract_idx, language)
    
    if not title_para:
        report['ok'] = False
        error_msg = tpl.get('messages', {}).get('structure_position_error')
        if error_msg:
            report['messages'].append(error_msg)
        else:
            report['messages'].append("未找到标题段落")
        return report
    
    report['title_paragraph'] = title_para
    title_text = title_para.text.strip()
    report['title_text'] = title_text
    
    # 检查位置
    ok_msg = tpl.get('messages', {}).get('structure_position_ok')
    if ok_msg:
        report['messages'].append(ok_msg)
    
    # 检查长度
    title_length = len(title_text)
    if title_length < min_length:
        report['ok'] = False
        msg_tpl = tpl.get('messages', {}).get('structure_length_short')
        if msg_tpl:
            try:
                report['messages'].append(msg_tpl.format(min=min_length))
            except:
                report['messages'].append(msg_tpl)
    elif title_length > max_length:
        report['ok'] = False
        msg_tpl = tpl.get('messages', {}).get('structure_length_long')
        if msg_tpl:
            try:
                report['messages'].append(msg_tpl.format(max=max_length))
            except:
                report['messages'].append(msg_tpl)
    else:
        ok_msg = tpl.get('messages', {}).get('structure_length_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    
    # 检查英文标题是否全大写
    if language == 'english':
        structure_rules = tpl.get('structure_rules', {})
        must_uppercase = structure_rules.get('must_uppercase', False)
        if must_uppercase:
            # 检查是否全大写（排除标点符号和空格）
            text_without_punct = re.sub(r'[^\w\s]', '', title_text)
            if text_without_punct and not text_without_punct.isupper():
                report['ok'] = False
                error_msg = tpl.get('messages', {}).get('structure_uppercase_error')
                if error_msg:
                    report['messages'].append(error_msg)
            else:
                ok_msg = tpl.get('messages', {}).get('structure_uppercase_ok')
                if ok_msg:
                    report['messages'].append(ok_msg)
    
    return report

def check_title_format(paragraph, tpl, language=None, doc=None):
    """
    检查标题格式（统一函数，支持中文和英文）
    参数:
        paragraph: 标题段落
        tpl: 模板对象
        language: 'chinese' 或 'english'
        doc: docx文档对象（用于读取样式继承链和docDefaults）
    返回 {'ok': bool, 'messages': []}
    """
    if language is None:
        language = detect_title_language(tpl)
    
    report = {'ok': True, 'messages': []}
    
    if not paragraph or not paragraph.runs:
        report['ok'] = False
        report['messages'].append("标题段落没有文本内容")
        return report
    
    format_rules = tpl.get('format_rules', {}).get('title', {})
    issues = []
    
    # 检测第一个非空run的格式（用于基本格式检查）
    main_run = None
    english_runs = []  # 存储包含英文的run，用于检查英文部分字体
    for run in paragraph.runs:
        if run.text.strip():
            if main_run is None:
                main_run = run
            # 收集包含英文的run
            if language == 'chinese' and re.search(r'[a-zA-Z]', run.text):
                english_runs.append(run)
    
    if not main_run:
        report['ok'] = False
        report['messages'].append("标题段落没有有效文本")
        return report
    
    # 检测实际格式（中文标题需要检测中文字体，英文标题不需要）
    detect_chinese = (language == 'chinese')
    font_result = detect_font_for_run(main_run, paragraph, detect_chinese_font=detect_chinese, doc=doc)
    
    if detect_chinese:
        actual_size_pt, actual_font_ascii, actual_font_eastasia, actual_bold, actual_italic, actual_line_spacing = font_result
    else:
        actual_size_pt, actual_font_ascii, _, actual_bold, actual_italic, actual_line_spacing = font_result
        actual_font_eastasia = None
    
    # 字体大小检查
    if not should_skip_check('font_size') and 'font_size_pt' in format_rules:
        expected_size_pt = float(format_rules['font_size_pt'])
        actual_size_name = get_font_size(actual_size_pt, tpl)
        expected_size_name = get_font_size(expected_size_pt, tpl)
        if abs(actual_size_pt - expected_size_pt) > 0.5:
            issues.append(f"字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）")
    
    # 字体名称检查
    if language == 'chinese':
        # 中文标题：检查中英文字体分别检测
        # 中文标题内的英文单词或字母也应使用黑体，与中文一致
        if re.search(r'[\u4e00-\u9fff]', main_run.text):
            expected_chinese_font = format_rules.get('chinese_font', '黑体')
            if expected_chinese_font.lower() not in (actual_font_eastasia or '').lower():
                issues.append(f"中文字体应为{expected_chinese_font}，实际为{actual_font_eastasia}")
        
        # 检查标题内所有包含英文的run，确保英文部分也使用黑体
        if english_runs:
            expected_english_font = format_rules.get('english_font', '黑体')
            for eng_run in english_runs:
                eng_font_result = detect_font_for_run(eng_run, paragraph, detect_chinese_font=True, doc=doc)
                eng_size, eng_font_ascii, eng_font_eastasia, _, _, _ = eng_font_result
                
                # 检查英文字体是否为黑体（可能通过ASCII或EastAsia字体设置）
                english_font_ok = False
                if expected_english_font.lower() in (eng_font_ascii or '').lower():
                    english_font_ok = True
                elif eng_font_eastasia and expected_english_font.lower() in eng_font_eastasia.lower():
                    english_font_ok = True
                
                if not english_font_ok:
                    issues.append(f"标题内的英文字体应为{expected_english_font}（与中文一致），实际为{eng_font_ascii}")
                    break  # 找到一个错误即可
                
                # 检查英文字号是否与中文一致（三号16pt）
                if not should_skip_check('font_size') and 'font_size_pt' in format_rules:
                    expected_size_pt = float(format_rules['font_size_pt'])
                    if abs(eng_size - expected_size_pt) > 0.5:
                        eng_size_name = get_font_size(eng_size, tpl)
                        expected_size_name = get_font_size(expected_size_pt, tpl)
                        issues.append(f"标题内的英文字号应为{expected_size_name}（{expected_size_pt}pt，与中文一致），实际为{eng_size_name}（{eng_size}pt）")
                        break  # 找到一个错误即可
    else:
        # 英文标题：只检查英文字体
        if not should_skip_check('font_name') and 'english_font' in format_rules:
            expected_font = format_rules.get('english_font', 'Times New Roman')
            if expected_font.lower() not in actual_font_ascii.lower():
                issues.append(f"字体应为{expected_font}，实际为{actual_font_ascii}")
    
    # 加粗检查
    if not should_skip_check('bold') and 'bold' in format_rules:
        expected_bold = bool(format_rules['bold'])
        if actual_bold != expected_bold:
            bold_status = "加粗" if expected_bold else "不加粗"
            actual_status = "加粗" if actual_bold else "不加粗"
            issues.append(f"字体应为{bold_status}，实际为{actual_status}")
    
    # 行间距检查
    if not should_skip_check('spacing') and 'line_spacing' in format_rules:
        expected_line_spacing = float(format_rules['line_spacing'])
        if abs(actual_line_spacing - expected_line_spacing) > 0.1:
            actual_spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
            expected_spacing_name = get_line_spacing_name(expected_line_spacing, tpl)
            issues.append(f"行间距应为{expected_spacing_name}（{expected_line_spacing}倍），实际为{actual_spacing_name}（{actual_line_spacing}倍）")
    
    # 段落对齐检查
    if 'alignment' in format_rules:
        expected_alignment_str = str(format_rules['alignment'])
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        expected_alignment = alignment_map.get(expected_alignment_str, 0)
        
        actual_alignment = detect_paragraph_alignment(paragraph)
        if actual_alignment != expected_alignment:
            actual_alignment_name = get_alignment_name(actual_alignment, tpl)
            expected_alignment_name = get_alignment_name(expected_alignment, tpl)
            issues.append(f"段落应为{expected_alignment_name}，实际为{actual_alignment_name}")
    
    # 段前段后间距检查
    def pt(v): 
        return v.pt if v else 0.0
    
    if 'space_before_cm' in format_rules:
        space_before = paragraph.paragraph_format.space_before
        expected_before_pt = cm_to_pt(format_rules['space_before_cm'])
        actual_before_pt = pt(space_before)
        if abs(actual_before_pt - expected_before_pt) > 2.0:  # 2pt容差
            issues.append(f"段前间距应为{format_rules['space_before_cm']}厘米（约{expected_before_pt:.1f}pt），实际为{actual_before_pt:.1f}pt")
    
    if 'space_after_cm' in format_rules:
        space_after = paragraph.paragraph_format.space_after
        expected_after_pt = cm_to_pt(format_rules['space_after_cm'])
        actual_after_pt = pt(space_after)
        if abs(actual_after_pt - expected_after_pt) > 2.0:  # 2pt容差
            issues.append(f"段后间距应为{format_rules['space_after_cm']}厘米（约{expected_after_pt:.1f}pt），实际为{actual_after_pt:.1f}pt")
    
    # 缩进检查
    if 'first_line_indent' in format_rules or 'left_indent' in format_rules:
        first_line_indent, left_indent, right_indent = detect_paragraph_indent(paragraph)
        
        if 'first_line_indent' in format_rules:
            expected_first_indent = float(format_rules['first_line_indent'])
            if abs(first_line_indent - expected_first_indent) > 1.0:
                issues.append(f"首行缩进应为{expected_first_indent}pt，实际为{first_line_indent:.1f}pt")
        
        if 'left_indent' in format_rules:
            expected_left_indent = float(format_rules['left_indent'])
            if abs(left_indent - expected_left_indent) > 1.0:
                issues.append(f"左缩进应为{expected_left_indent}pt，实际为{left_indent:.1f}pt")
    
    if issues:
        report['ok'] = False
        header = tpl.get('messages', {}).get('format_title_issue_header')
        if header:
            report['messages'].append(header)
        report['messages'].extend(issues)
    else:
        ok_msg = tpl.get('messages', {}).get('format_title_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    
    return report

def check_title_with_template(doc_path, template_identifier, skip_checks=None, language=None):
    """
    主检查函数：检查标题格式（统一函数，支持中文和英文）
    参数:
        doc_path: 文档路径
        template_identifier: 模板标识符
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
        language: 可选，'chinese' 或 'english'，如果不提供则自动检测
    """
    global _skip_checks_config
    _skip_checks_config = skip_checks or []
    
    tpl = load_template(template_identifier)
    # 保存模板路径用于语言检测
    tpl['_template_path'] = template_identifier
    
    if language is None:
        language = detect_title_language(tpl)
    
    doc = Document(doc_path)
    
    # 执行各项检查
    structure_report = check_title_structure(doc, tpl, language)
    
    format_report = {'ok': True, 'messages': []}
    if structure_report.get('title_paragraph'):
        format_report = check_title_format(structure_report['title_paragraph'], tpl, language)
    
    # 组装报告
    report = {
        'structure': structure_report,
        'format': format_report,
        'summary': [],
        'language': language
    }
    
    # 生成总结
    all_ok = (structure_report['ok'] and format_report['ok'])
    summary_tpl = tpl.get('messages', {}).get('summary_overall')
    if summary_tpl:
        try:
            report['summary'].append(summary_tpl.format(ok="通过" if all_ok else "失败"))
        except Exception:
            report['summary'].append(str(summary_tpl))
    
    return report

def check_bilingual_titles(doc_path, chinese_template=None, english_template=None, skip_checks=None):
    """
    同时检测中文和英文标题
    参数:
        doc_path: 文档路径
        chinese_template: 中文标题模板标识符，默认 'Title'
        english_template: 英文标题模板标识符，默认 'English_Title'
        skip_checks: 要跳过的检测项列表
    返回: 包含 'chinese' 和 'english' 子报告的字典
    """
    if chinese_template is None:
        chinese_template = 'Title'
    if english_template is None:
        english_template = 'English_Title'
    
    chinese_report = check_title_with_template(doc_path, chinese_template, skip_checks, 'chinese')
    english_report = check_title_with_template(doc_path, english_template, skip_checks, 'english')
    
    return {
        'chinese': chinese_report,
        'english': english_report,
        'summary': []
    }

# ---------- 报告输出 ----------
def print_title_report(report):
    """打印标题检查报告"""
    print("=== Title Check Report ===")
    
    sections = [
        ('structure', 'STRUCTURE'),
        ('format', 'FORMAT')
    ]
    
    for sec_key, sec_name in sections:
        info = report[sec_key]
        print(f"--- {sec_name} ---")
        print(" OK:", info['ok'])
        for m in info['messages']:
            print("  -", m)
    
    print("--- SUMMARY ---")
    for s in report['summary']:
        print(" ", s)

def print_help():
    print("Usage:")
    print("  python Title_detect.py check <paper.docx> <template.json_or_name>")
    print("  python Title_detect.py check-both <paper.docx> <chinese_template.json> <english_template.json>")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print_help()
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'check':
        if len(sys.argv) != 4:
            print_help()
            sys.exit(1)
        paper_path = sys.argv[2]
        tpl_id = sys.argv[3]
        if not os.path.isfile(paper_path):
            print(f"论文文件不存在: {paper_path}")
            sys.exit(1)
        try:
            print("=== 开始标题格式检查 ===")
            report = check_title_with_template(paper_path, tpl_id)
        except Exception as e:
            print("检查时出错:", e)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        print_title_report(report)
    elif cmd == 'check-both':
        if len(sys.argv) != 5:
            print_help()
            sys.exit(1)
        paper_path = sys.argv[2]
        chinese_tpl = sys.argv[3]
        english_tpl = sys.argv[4]
        if not os.path.isfile(paper_path):
            print(f"论文文件不存在: {paper_path}")
            sys.exit(1)
        try:
            print("=== 开始双语标题格式检查 ===")
            report = check_bilingual_titles(paper_path, chinese_tpl, english_tpl)
            print("=== 双语标题检查报告 ===")
            print("【中文标题】")
            print_title_report(report['chinese'])
            print("【英文标题】")
            print_title_report(report['english'])
        except Exception as e:
            print("检查时出错:", e)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print_help()
        sys.exit(0)

