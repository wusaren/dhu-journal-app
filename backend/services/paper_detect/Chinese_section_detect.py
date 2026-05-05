#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
from pathlib import Path

# 添加项目根目录到 sys.path 以支持独立运行
if __name__ == "__main__" and __package__ is None:
    file = Path(__file__).resolve()
    parent, root = file.parent, file.parents[1]
    sys.path.append(str(root))
    # 尝试将当前目录也加入，以防万一
    try:
        sys.path.remove(str(parent))
    except ValueError:
        pass

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
try:
    # 尝试相对导入（当作为模块导入时）
    from .check_code import get_address_info, get_structured_address_aliyun, get_zipcode_from_deepseek
    from .config_api import (
        AMAP_API_KEY, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET,
        DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
    )
except ImportError as e:
    print('错误：',e)
    # 尝试绝对导入（当直接运行时）
    try:
        from paper_detect.check_code import get_address_info, get_structured_address_aliyun, get_zipcode_from_deepseek
        from paper_detect.config_api import (
            AMAP_API_KEY, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET,
            DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
        )
    except ImportError:
        # 最后尝试同目录导入
        from check_code import get_address_info, get_structured_address_aliyun, get_zipcode_from_deepseek
        from config_api import (
            AMAP_API_KEY, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET,
            DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
        )

# 定义直辖市列表，用于地址格式检测
MUNICIPALITIES = ["北京", "上海", "天津", "重庆"]

"""
=== 论文格式检测系统 - 中文部分检测器 ===

【中文部分检测 (Chinese Section Detection)】

检测参考文献后的中文部分，包括：
1. 中文标题 - 格式要求与英文标题一致
2. 中文作者 - 格式要求与英文作者一致
3. 中文单位 - 格式要求与英文单位一致
4. 中文摘要 - 格式要求与英文摘要一致
5. 中文关键词 - 格式要求与英文关键词一致

特殊要求：
- 英文部分使用 Times New Roman
- 中文部分使用 宋体
- 字体大小、行间距等与英文部分的检测规则一致
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
    检测run的字体信息，包括中英文字体
    返回: (font_size, font_ascii, font_eastasia, is_bold, is_italic)
    """
    font_size = None
    font_name_ascii = None
    font_name_eastasia = None
    is_bold = False
    is_italic = False
    
    if not run:
        return 12.0, "Times New Roman", "宋体", False, False
    
    # 1. 检测字号
    try:
        if run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)
        
        if font_size is None and hasattr(run._element, 'rPr'):
            sz_nodes = run._element.xpath('.//w:sz')
            if sz_nodes and sz_nodes[0].get(qn('w:val')):
                font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
    except Exception:
        pass
    
    font_size = font_size if font_size is not None else 12.0
    
    # 2. 检测英文字体（ASCII）和中文字体（EastAsia）
    try:
        # 优先从run.font.name读取
        if run.font and run.font.name:
            font_name_ascii = run.font.name
        
        # 从XML中读取w:rFonts
        if hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                rfonts = rpr.find(qn('w:rFonts'))
                if rfonts is not None:
                    # 读取各种字体属性
                    xml_ascii = rfonts.get(qn('w:ascii'))
                    xml_hansi = rfonts.get(qn('w:hAnsi'))
                    xml_eastasia = rfonts.get(qn('w:eastAsia'))
                    
                    # ASCII字体（英文）
                    if xml_ascii:
                        font_name_ascii = xml_ascii
                    elif xml_hansi and font_name_ascii is None:
                        font_name_ascii = xml_hansi
                    
                    # EastAsia字体（中文）
                    if xml_eastasia:
                        font_name_eastasia = xml_eastasia
                    elif xml_hansi and font_name_eastasia is None:
                        font_name_eastasia = xml_hansi
    except Exception as e:
        print(f"  字体检测异常: {e}")
    
    font_name_ascii = font_name_ascii if font_name_ascii else "Times New Roman"
    font_name_eastasia = font_name_eastasia if font_name_eastasia else "宋体"
    
    # 4. 检测加粗和斜体
    try:
        if run.font:
            is_bold = run.font.bold if run.font.bold is not None else False
            is_italic = run.font.italic if run.font.italic is not None else False
        
        is_bold = bool(is_bold)
        is_italic = bool(is_italic)
    except Exception:
        pass
    
    return font_size, font_name_ascii, font_name_eastasia, is_bold, is_italic

def get_paragraph_spacing(paragraph):
    """
    获取段落的段前段后间距
    返回: (space_before_lines, space_after_lines)
    """
    space_before = 0.0
    space_after = 0.0
    
    try:
        # 段前间距
        if paragraph.paragraph_format.space_before is not None:
            # 转换为行数（假设1行 = 12pt）
            space_before_pt = paragraph.paragraph_format.space_before.pt
            space_before = round(space_before_pt / 12.0, 1)
        
        # 段后间距
        if paragraph.paragraph_format.space_after is not None:
            space_after_pt = paragraph.paragraph_format.space_after.pt
            space_after = round(space_after_pt / 12.0, 1)
    except Exception:
        pass
    
    return space_before, space_after

def get_font_size(pt_size, tpl=None):
    """获取字体大小的中文名称"""
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
    
    if pt_size in size_map:
        return size_map[pt_size]
    
    closest_size = min(size_map.keys(), key=lambda x: abs(x - pt_size))
    return size_map[closest_size]

# ---------- 对齐检测函数 ----------
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
    
    return 0  # 默认左对齐

# ---------- 中文部分定位 ----------
def find_references_section(doc):
    """查找参考文献部分的位置"""
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        # 参考文献可能的标识：References、参考文献、REFERENCES等
        if re.match(r'^(References|参考文献|REFERENCES)\s*$', text, re.IGNORECASE):
            return idx
    return None

def find_chinese_section(doc):
    """
    查找中文部分的起始位置
    返回：{
        'start_index': 起始段落索引,
        'title_index': 中文标题索引,
        'author_index': 中文作者索引,
        'affiliation_index': 中文单位索引,
        'abstract_index': 中文摘要索引,
        'keywords_index': 中文关键词索引
    }
    """
    references_idx = find_references_section(doc)
    
    if references_idx is None:
        return None
    
    result = {
        'start_index': references_idx,
        'title_index': None,
        'author_index': None,
        'affiliation_index': None,
        'abstract_index': None,
        'keywords_index': None
    }
    
    # 从参考文献后开始查找中文部分
    for idx in range(references_idx + 1, len(doc.paragraphs)):
        paragraph = doc.paragraphs[idx]
        text = paragraph.text.strip()
        
        if not text:
            continue
        
        # 判断是否包含中文字符
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        
        if has_chinese and result['title_index'] is None:
            # 第一个包含中文的段落视为中文标题
            result['title_index'] = idx
        elif result['title_index'] is not None and result['author_index'] is None:
            # 标题后的第一个段落视为作者
            if text and len(text) > 0:
                result['author_index'] = idx
        elif result['author_index'] is not None and result['affiliation_index'] is None:
            # 作者后的第一个段落视为单位
            if text and len(text) > 0:
                result['affiliation_index'] = idx
        
        # 查找摘要（包含"摘要"、"摘  要"等）
        if re.search(r'摘\s*要', text):
            result['abstract_index'] = idx
        
        # 查找关键词（包含"关键词"、"关键字"等）
        if re.search(r'关键(词|字)', text):
            result['keywords_index'] = idx
    
    return result

# ---------- 检测函数 ----------
def check_paragraph_full_format(paragraph, section_name, expected_format, tpl, verbose=True):
    """
    完整的段落格式检查（遍历所有run）
    """
    report = {'ok': True, 'messages': []}
    
    if verbose:
        # 只打印一次段落的总体格式
        print(f"  检测Run数量: {len(paragraph.runs)}")
        if paragraph.runs:
            first_run = paragraph.runs[0]
            font_size, font_ascii, font_eastasia, is_bold, is_italic = detect_font_for_run(first_run, paragraph)
            print(f"  段落总体格式 - 中文: {font_eastasia}, 英文: {font_ascii}, 字号: {get_font_size(font_size)}({font_size}pt)")
    
    # 遍历段落中的所有run进行详细检查
    for run in paragraph.runs:
        if not run.text.strip():
            continue  # 跳过空白run
        
        # 1. 检测字体
        font_size, font_ascii, font_eastasia, is_bold, is_italic = detect_font_for_run(run, paragraph)
        
        # 检查run中的中文字符
        if re.search(r'[\u4e00-\u9fff]', run.text):
            expected_chinese_font = expected_format.get('chinese_font', '宋体')
            if font_eastasia != expected_chinese_font:
                msg = f"中文字体应为{expected_chinese_font}（当前：{font_eastasia}）"
                if msg not in report['messages']:
                    report['ok'] = False
                    report['messages'].append(msg)
        
        # 检查run中的英文字符
        if re.search(r'[a-zA-Z]', run.text):
            expected_english_font = expected_format.get('english_font', 'Times New Roman')
            if font_ascii != expected_english_font:
                msg = f"英文字体应为{expected_english_font}（当前：{font_ascii}）"
                if msg not in report['messages']:
                    report['ok'] = False
                    report['messages'].append(msg)
        
        # 检查字号
        expected_size = expected_format.get('font_size_pt', 12)
        if abs(font_size - expected_size) > 0.5:
            msg = f"字号应为{get_font_size(expected_size)}({expected_size}pt)，当前为{get_font_size(font_size)}({font_size}pt)"
            if msg not in report['messages']:
                report['ok'] = False
                report['messages'].append(msg)
        
        # 检查加粗（仅当规则中明确指定时）
        if 'bold' in expected_format:
            expected_bold = expected_format['bold']
            if is_bold != expected_bold:
                if expected_bold:
                    msg = f"{section_name}应加粗"
                else:
                    msg = f"{section_name}不应加粗"
                if msg not in report['messages']:
                    report['ok'] = False
                    report['messages'].append(msg)
        
        # 检查斜体（仅当规则中明确指定时）
        if 'italic' in expected_format:
            expected_italic = expected_format['italic']
            if is_italic != expected_italic:
                # 如果期望是正体，但检测到斜体，并且内容是单个字符，则忽略
                if not expected_italic and len(run.text.strip()) == 1:
                    pass  # 允许单个字母为斜体，跳过报错
                else:
                    if expected_italic:
                        msg = f"{section_name}应为斜体"
                    else:
                        msg = f"{section_name}应为正体（不应为斜体，问题文本：'{run.text}'）"
                    if msg not in report['messages']:
                        report['ok'] = False
                        report['messages'].append(msg)
    
    # 2. 检查对齐方式
    alignment = detect_paragraph_alignment(paragraph)
    alignment_names = {0: '左对齐', 1: '居中对齐', 2: '右对齐', 3: '两端对齐'}
    if verbose:
        print(f"  对齐方式: {alignment_names.get(alignment)}")
    
    expected_alignment = expected_format.get('alignment', 'justify')
    if expected_alignment == 'justify' and alignment != 3:
        report['ok'] = False
        report['messages'].append(f"应两端对齐（当前：{alignment_names.get(alignment)}）")
    elif expected_alignment == 'center' and alignment != 1:
        report['ok'] = False
        report['messages'].append(f"应居中对齐（当前：{alignment_names.get(alignment)}）")
    
    # 3. 检查段前段后间距
    space_before, space_after = get_paragraph_spacing(paragraph)
    if verbose:
        print(f"  段前间距: {space_before}行, 段后间距: {space_after}行")
    
    expected_before = expected_format.get('space_before', 0)
    expected_after = expected_format.get('space_after', 0)
    
    if abs(space_before - expected_before) > 0.2:
        report['ok'] = False
        report['messages'].append(f"段前间距应为{expected_before}行（当前：{space_before}行）")
    
    if abs(space_after - expected_after) > 0.2:
        report['ok'] = False
        report['messages'].append(f"段后间距应为{expected_after}行（当前：{space_after}行）")
    
    # 4. 检查行间距
    if 'line_spacing' in expected_format:
        line_spacing = paragraph.paragraph_format.line_spacing
        expected_spacing = expected_format.get('line_spacing', 1.5)
        
        if line_spacing and verbose:
            actual_spacing = float(line_spacing) if isinstance(line_spacing, (int, float)) else 1.0
            print(f"  行间距: {actual_spacing}倍")
            
            if abs(actual_spacing - expected_spacing) > 0.1:
                report['ok'] = False
                report['messages'].append(f"行间距应为{expected_spacing}倍（当前：{actual_spacing}倍）")
    
    # 5. 检查缩进
    if 'first_line_indent' in expected_format:
        first_line_indent = paragraph.paragraph_format.first_line_indent
        actual_indent = first_line_indent.pt if first_line_indent else 0
        expected_indent = expected_format.get('first_line_indent', 0)
        if verbose:
            print(f"  首行缩进: {actual_indent}pt")
        
        if abs(actual_indent - expected_indent) > 1:
            report['ok'] = False
            report['messages'].append(f"首行缩进应为{expected_indent}pt（当前：{actual_indent}pt）")
    
    if 'left_indent' in expected_format:
        left_indent = paragraph.paragraph_format.left_indent
        actual_indent = left_indent.pt if left_indent else 0
        expected_indent = expected_format.get('left_indent', 0)
        
        if abs(actual_indent - expected_indent) > 1:
            report['ok'] = False
            report['messages'].append(f"左缩进应为{expected_indent}pt（当前：{actual_indent}pt）")
    
    if 'right_indent' in expected_format:
        right_indent = paragraph.paragraph_format.right_indent
        actual_indent = right_indent.pt if right_indent else 0
        expected_indent = expected_format.get('right_indent', 0)
        
        if abs(actual_indent - expected_indent) > 1:
            report['ok'] = False
            report['messages'].append(f"右缩进应为{expected_indent}pt（当前：{actual_indent}pt）")
    
    return report

def check_chinese_title(doc, chinese_section, tpl):
    """检测中文标题格式"""
    report = {'ok': True, 'messages': []}
    
    if chinese_section is None or chinese_section['title_index'] is None:
        report['ok'] = False
        report['messages'].append("未找到中文标题")
        return report
    
    title_para = doc.paragraphs[chinese_section['title_index']]
    title_text = title_para.text.strip()
    print(f"检测中文标题段落: '{title_text[:50]}...'")
    
    expected_format = tpl.get('format_rules', {}).get('title', {})
    return check_paragraph_full_format(title_para, "中文标题", expected_format, tpl)

def parse_chinese_authors(author_text):
    """
    解析中文作者的单位编号
    例如：刘影1，惠明明1，卜凡兴1*，罗维1*
    返回：[{'name': '刘影', 'affs': [1], 'corresponding': False}, ...]
    """
    authors = []
    
    # 用中英文逗号、分号分隔作者
    parts = re.split(r'[,，;；]+', author_text)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # 检测通讯作者标记（* 或 ☆）
        corresponding = bool(re.search(r'[*☆✉]', part))
        
        # 移除标记
        part_clean = re.sub(r'[*☆✉]+', '', part).strip()
        
        # 提取单位编号（数字在末尾，可能多个如"1,2"）
        match = re.search(r'(\d+(?:[,，]\d+)*)\s*$', part_clean)
        affs = []
        name = part_clean
        
        if match:
            # 提取编号
            aff_str = match.group(1)
            affs = [int(x) for x in re.findall(r'\d+', aff_str)]
            # 去掉编号，得到姓名
            name = part_clean[:match.start()].strip()
        
        authors.append({
            'name': name,
            'affs': affs,
            'corresponding': corresponding,
            'raw': part
        })
    
    return authors

def check_chinese_author(doc, chinese_section, tpl):
    """检测中文作者格式和内容"""
    report = {'ok': True, 'messages': []}
    
    if chinese_section is None or chinese_section['author_index'] is None:
        report['ok'] = False
        report['messages'].append("未找到中文作者")
        return report
    
    author_para = doc.paragraphs[chinese_section['author_index']]
    author_text = author_para.text.strip()
    print(f"检测中文作者段落: '{author_text[:50]}...'")
    
    # 1. 检测格式
    expected_format = tpl.get('format_rules', {}).get('author', {})
    format_result = check_paragraph_full_format(author_para, "中文作者", expected_format, tpl)
    report['ok'] = format_result['ok']
    report['messages'].extend(format_result['messages'])
    
    # 2. 解析作者和单位编号
    authors = parse_chinese_authors(author_text)
    print(f"  解析到 {len(authors)} 个作者")
    
    # 3. 检查作者单位编号规则
    if authors:
        # 收集所有使用的单位编号
        used_affs = set()
        for author in authors:
            used_affs.update(author['affs'])
        
        print(f"  使用的单位编号: {sorted(used_affs) if used_affs else '无'}")
        
        # 规则：如果所有作者来自同一单位，应该省略编号
        if len(used_affs) == 1 and len(used_affs) > 0:
            single_aff_id = list(used_affs)[0]
            report['ok'] = False
            report['messages'].append(
                f"所有作者来自同一单位（编号{single_aff_id}），应该省略作者姓名后的单位编号"
            )
            print(f"  作者单位检查: ✗ 所有作者都标注了单位{single_aff_id}，应省略编号")
        elif len(used_affs) == 0:
            # 没有单位编号（可能是正确的，如果只有一个单位）
            print(f"  作者单位检查: ✓ 作者未标注单位编号")
        else:
            print(f"  作者单位检查: ✓ 作者来自{len(used_affs)}个不同单位")
    
    return report

def check_chinese_affiliation(doc, chinese_section, authors_data, tpl):
    """检测中文单位格式和内容"""
    report = {'ok': True, 'messages': [], 'affiliations_detail': []}
    
    if chinese_section is None or chinese_section['affiliation_index'] is None:
        report['ok'] = False
        report['messages'].append("未找到中文单位")
        return report
    
    affiliation_start_idx = chinese_section['affiliation_index']
    
    # 1. 查找并解析所有单位段落
    print(f"  从段落 {affiliation_start_idx} 开始查找单位...")
    affiliation_paragraphs = []
    doc_affiliations = {}  # {编号: 单位文本}
    stop_keywords = ['摘要', '关键词', '关键字', 'Abstract', 'Keywords']
    
    for idx in range(affiliation_start_idx, min(affiliation_start_idx + 20, len(doc.paragraphs))):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
            continue
        
        # 遇到摘要或关键词，停止
        if any(keyword in text for keyword in stop_keywords):
            print(f"  段落 {idx}: 遇到停止关键词 '{text[:30]}...' - 停止查找")
            break
        
        # 判断是否为单位段落
        # 支持半角和全角标点：. 。 、 ． ， 以及编号后直接跟中文（无分隔符）
        # 匹配：1. 或 1． 或 1、 或 1 或直接 1中文
        has_number_match = re.match(r'^\s*(\d+)[\.\。\、\．\，\s:-]*(.+)$', text)
        has_institution_keyword = bool(re.search(r'(大学|学院|研究院|研究所|中心|实验室|University|College|Institute)', text))
        
        # 方法1：以数字编号开头（如"1. 某某大学" 或 "1．某某大学"）
        if has_number_match:
            aff_number = int(has_number_match.group(1))
            aff_text = has_number_match.group(2).strip()
            doc_affiliations[aff_number] = aff_text
            affiliation_paragraphs.append({'para': para, 'text': text, 'has_number': True, 'number': aff_number, 'idx': idx})
            print(f"  段落 {idx}: 识别为单位（编号{aff_number}） - '{text[:40]}...'")
        # 方法2：第一个单位段落（可能没有编号）
        elif idx == affiliation_start_idx:
            affiliation_paragraphs.append({'para': para, 'text': text, 'has_number': False, 'number': None, 'idx': idx})
            print(f"  段落 {idx}: 识别为单位（首个段落，无编号） - '{text[:40]}...'")
        # 方法3：包含单位关键字
        elif has_institution_keyword:
            affiliation_paragraphs.append({'para': para, 'text': text, 'has_number': False, 'number': None, 'idx': idx})
            print(f"  段落 {idx}: 识别为单位（包含关键字，无编号） - '{text[:40]}...'")
        else:
            # 不是单位段落，但继续查找（可能后面还有单位段落）
            print(f"  段落 {idx}: 不是单位段落 '{text[:30]}...' - 继续查找")
    
    if not affiliation_paragraphs:
        report['ok'] = False
        report['messages'].append("未找到中文单位段落")
        return report
    
    print(f"  总共找到 {len(affiliation_paragraphs)} 个单位段落")
    print(f"  文档中的单位编号: {sorted(doc_affiliations.keys()) if doc_affiliations else '无'}")
    
    # 2. 检测第一个单位段落的格式
    first_affiliation = affiliation_paragraphs[0]
    print(f"检测中文单位段落: '{first_affiliation['text'][:50]}...'")
    
    expected_format = tpl.get('format_rules', {}).get('affiliation', {})
    format_result = check_paragraph_full_format(first_affiliation['para'], "中文单位", expected_format, tpl)
    report['ok'] = format_result['ok']
    report['messages'].extend(format_result['messages'])
    
    # 3. 检测单位引用完整性
    if authors_data:
        # 从作者数据中提取使用的单位编号
        used_affs = set()
        for author in authors_data:
            used_affs.update(author['affs'])
        
        # 检查作者引用的编号是否都在文档中定义
        if used_affs and doc_affiliations:
            missing_affs = [aff_id for aff_id in used_affs if aff_id not in doc_affiliations]
            if missing_affs:
                report['ok'] = False
                report['messages'].append(f"作者引用了不存在的单位编号: {missing_affs}")
                print(f"  单位引用检查: ✗ 编号{missing_affs}在单位列表中不存在")
            else:
                print(f"  单位引用检查: ✓ 所有引用的编号都存在")
    
    # 4. API地址审核与邮编验证
    amap_enabled = bool(AMAP_API_KEY)
    aliyun_enabled = all([ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET])
    deepseek_enabled = bool(DEEPSEEK_API_KEY)

    if not any([amap_enabled, aliyun_enabled, deepseek_enabled]):
        print("  所有API均未配置，跳过地址审核与邮编验证。")
    else:
        print("  正在使用API进行地址审核与邮编验证...")
        for aff_idx, aff_para in enumerate(affiliation_paragraphs, 1):
            text = aff_para['text']

            # a. 提取单位名称和邮编
            # 支持编号后直接跟中文或有分隔符的格式
            match = re.search(r'^(?:\d+[．.]\s*)?(.+?)(?=\s*[，,])', text)
            if not match:
                continue
            raw_unit_name = match.group(1)
            unit_name = "".join(raw_unit_name.split())
            
            # 支持任意位数的邮编（作者可能写错）
            zip_match = re.search(r'(\d{4,})', text)
            doc_zipcode = zip_match.group(1) if zip_match else None

            # b. 阶段一：高德地图地址审核
            address_ok = False
            if amap_enabled:
                address_info = get_address_info(unit_name, AMAP_API_KEY)
                if not address_info['is_exact_match']:
                    msg = f"单位名称 '{unit_name}' 可能有误。{address_info['message']}"
                    if msg not in report['messages']:
                        report['ok'] = False
                        report['messages'].append(msg)
                else:
                    address_ok = True
            else:
                print("  高德地图API未配置，跳过地址审核。")
                address_ok = True

            # c. 阶段二 & 三：邮编查询（两种方式）
            # 邮编检测独立进行，不依赖地址审核结果
            if deepseek_enabled and doc_zipcode:
                # 方式1：直接文档地址检测
                # 移除邮编，只保留地址部分，避免干扰模型识别
                full_address_text = ' '.join(text.split())
                # 移除邮编（4位及以上的数字）
                direct_address = re.sub(r'\d{4,}', '', full_address_text).strip()
                direct_zipcode = None
                
                if direct_address:
                    print(f"  邮编检测 (文档地址):")
                    print(f"    检测地址: {direct_address}")
                    zip_info_direct = get_zipcode_from_deepseek(direct_address, DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL)
                    if zip_info_direct['status'] == 'ok':
                        direct_zipcode = zip_info_direct['zipcode']
                        print(f"    API检测邮编: {direct_zipcode}")
                    else:
                        print(f"    API调用失败: {zip_info_direct.get('message', '未知错误')}")
                
                # 方式2：结构化地址检测（如果启用了阿里云）
                struct_zipcode = None
                formatted_address = None
                
                if aliyun_enabled:
                    full_address_text = ' '.join(text.split())
                    struct_info = get_structured_address_aliyun(full_address_text, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET)

                    if struct_info['status'] == 'ok' and struct_info['structured_address']:
                        zip_info = get_zipcode_from_deepseek(struct_info['structured_address'], DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL)
                        if zip_info['status'] == 'ok':
                            struct_zipcode = zip_info['zipcode']
                            # 解析结构化地址为连贯的自然语言格式
                            address_parts = []
                            struct_addr = struct_info['structured_address']
                            
                            # 提取各个部分
                            prov_match = re.search(r'prov=([^\s]+)', struct_addr)
                            city_match = re.search(r'city=([^\s]+)', struct_addr)
                            district_match = re.search(r'district=([^\s]+)', struct_addr)
                            town_match = re.search(r'town=([^\s]+)', struct_addr)
                            road_match = re.search(r'road=([^\s]+)', struct_addr)
                            poi_match = re.search(r'poi=([^\s]+)', struct_addr)
                            
                            if prov_match:
                                address_parts.append(prov_match.group(1))
                            if city_match:
                                address_parts.append(city_match.group(1))
                            if district_match:
                                address_parts.append(district_match.group(1))
                            if town_match:
                                address_parts.append(town_match.group(1))
                            if road_match:
                                address_parts.append(road_match.group(1))
                            if poi_match:
                                address_parts.append(poi_match.group(1))
                            
                            formatted_address = '，'.join(address_parts) if address_parts else struct_addr
                            
                            print(f"  邮编检测 (结构化地址):")
                            print(f"    检测地址: {formatted_address}")
                            print(f"    API检测邮编: {struct_zipcode}")
                
                # 使用结构化地址的结果作为主要检测结果（如果有的话），否则使用文档地址的结果
                api_zipcode = struct_zipcode if struct_zipcode else direct_zipcode
                detected_address = formatted_address if formatted_address else direct_address
                
                # 保存单位详细信息
                aff_detail = {
                    'number': aff_para.get('number', aff_idx),
                    'unit_name': unit_name,
                    'direct_address': direct_address,
                    'direct_zipcode': direct_zipcode,
                    'structured_address': formatted_address,
                    'structured_zipcode': struct_zipcode,
                    'api_zipcode': api_zipcode,
                    'doc_zipcode': doc_zipcode,
                    'match': api_zipcode == doc_zipcode if api_zipcode else None
                }
                report['affiliations_detail'].append(aff_detail)
                
                if api_zipcode and api_zipcode != doc_zipcode:
                    msg = f"单位 '{unit_name}' 的邮编可能不正确。文档邮编: {doc_zipcode}, API建议邮编: {api_zipcode}"
                    if msg not in report['messages']:
                        report['ok'] = False
                        report['messages'].append(msg)
                    print(f"    ✗ 邮编不匹配 - 文档邮编: {doc_zipcode}")
                elif api_zipcode:
                    print(f"    ✓ 邮编验证通过 - 文档邮编: {doc_zipcode}")
            else:
                if not aliyun_enabled: print("  阿里云API未配置，跳过邮编验证。")
                if not deepseek_enabled: print("  DeepSeek API未配置，跳过邮编验证。")

    # 5. 检测地址格式
    for aff_para in affiliation_paragraphs:
        text = aff_para['text']
        # 匹配地址和邮编，例如 "上海 201620" 或 "江苏 南通 226019"
        match = re.search(r'([\u4e00-\u9fa5\s]+)(\d{6})', text)
        if match:
            address_part = match.group(1).strip()
            # 地址格式规则检查
            if ' ' in address_part:
                # 如果包含空格，检查第一部分是否为直辖市
                parts = address_part.split()
                if parts[0] in MUNICIPALITIES:
                    msg = f"单位地址 '{address_part}' 格式错误，直辖市名称后不应有空格和下级区划（应直接写 '{parts[0]}'）"
                    if msg not in report['messages']:
                        report['ok'] = False
                        report['messages'].append(msg)
            else:
                # 如果不包含空格，那它必须是直辖市
                if address_part not in MUNICIPALITIES:
                    msg = f"单位地址 '{address_part}' 不是直辖市，应在其前加上省份名并用空格隔开（例如：'江苏 南通'）"
                    if msg not in report['messages']:
                        report['ok'] = False
                        report['messages'].append(msg)

    # 6. 检测单位编号规则
    affiliation_rules = tpl.get('check_rules', {}).get('affiliation_rules', {})
    
    # 规则：只有一个单位时，不应使用编号
    if affiliation_rules.get('check_single_affiliation', True):
        # 统计单位数量
        affiliation_count = len(affiliation_paragraphs)
        
        # 检查是否使用了编号
        has_any_number = any(aff['has_number'] for aff in affiliation_paragraphs)
        
        if affiliation_count == 1 and has_any_number:
            # 只有一个单位但使用了编号（支持全角和半角标点）
            match = re.match(r'^\s*(\d+)[\.\。\、\．\，\s:-]', first_affiliation['text'])
            if match:
                number = match.group(1)
                report['ok'] = False
                report['messages'].append(f"只有一个单位时，不应使用编号{number}（应直接写单位名称，去掉'{number}．'或'{number}. '）")
                print(f"  单位唯一性检查: ✗ 检测到编号{number}，但只有1个单位")
        elif affiliation_count == 1 and not has_any_number:
            print(f"  单位唯一性检查: ✓ 只有1个单位，未使用编号")
        elif affiliation_count > 1:
            print(f"  单位唯一性检查: ✓ 检测到{affiliation_count}个单位")
    
    return report

def check_chinese_abstract(doc, chinese_section, tpl):
    """检测中文摘要格式"""
    report = {'ok': True, 'messages': []}
    
    if chinese_section is None or chinese_section['abstract_index'] is None:
        report['ok'] = False
        report['messages'].append("未找到中文摘要")
        return report
    
    abstract_para = doc.paragraphs[chinese_section['abstract_index']]
    abstract_text = abstract_para.text.strip()
    print(f"检测中文摘要段落: '{abstract_text[:50]}...'")
    
    expected_format = tpl.get('format_rules', {}).get('abstract', {})
    
    # 1. 检查标题和间距
    label_match = re.search(r'^(摘(\s*)要)\s*[:：]?', abstract_text)
    if not label_match:
        report['ok'] = False
        report['messages'].append("未找到“摘要”标题，或标题格式不正确")
        # 如果连标题都找不到，后续检查无意义
        return report
    
    # 检查“摘要”两个字之间的空格
    space_between = label_match.group(2)
    if len(space_between) != 3:
        report['ok'] = False
        report['messages'].append(f"“摘要”二字之间应有3个空格（当前有{len(space_between)}个）")

    # 2. 逐个Run检查格式
    label_text_with_colon = label_match.group(0)
    label_end_pos = len(label_text_with_colon)
    current_text_pos = 0

    for run in abstract_para.runs:
        if not run.text.strip():
            current_text_pos += len(run.text)
            continue
            
        font_size, font_ascii, font_eastasia, is_bold, is_italic = detect_font_for_run(run, abstract_para)
        
        # 判断当前run是否属于标题部分
        is_label_part = current_text_pos < label_end_pos

        if is_label_part:
            # 标题部分应加粗
            if not is_bold:
                report['ok'] = False
                report['messages'].append(f"摘要标题“{run.text}”部分应加粗")
        else:
            # 正文部分不应加粗
            if is_bold:
                report['ok'] = False
                report['messages'].append(f"摘要正文“{run.text}”部分不应加粗")
            
            # 检查正文字体
            expected_chinese_font = expected_format.get('chinese_font', '宋体')
            if re.search(r'[\u4e00-\u9fff]', run.text) and font_eastasia != expected_chinese_font:
                msg = f"中文字体应为{expected_chinese_font}（当前：{font_eastasia}）"
                if msg not in report['messages']:
                    report['ok'] = False; report['messages'].append(msg)

            expected_english_font = expected_format.get('english_font', 'Times New Roman')
            if re.search(r'[a-zA-Z]', run.text) and font_ascii != expected_english_font:
                msg = f"英文字体应为{expected_english_font}（当前：{font_ascii}）"
                if msg not in report['messages']:
                    report['ok'] = False; report['messages'].append(msg)
            
            # 检查正文字号
            expected_size = expected_format.get('font_size_pt', 12)
            if abs(font_size - expected_size) > 0.5:
                msg = f"字号应为{get_font_size(expected_size)}({expected_size}pt)，当前为{get_font_size(font_size)}({font_size}pt)"
                if msg not in report['messages']:
                    report['ok'] = False; report['messages'].append(msg)

        current_text_pos += len(run.text)
        
    # 3. 检查段落级格式（如对齐、段间距、缩进等），但跳过bold/italic检查，因为前面已处理
    format_rules_for_paragraph = expected_format.copy()
    format_rules_for_paragraph.pop('bold', None)
    format_rules_for_paragraph.pop('italic', None)
    paragraph_format_report = check_paragraph_full_format(abstract_para, "中文摘要", format_rules_for_paragraph, tpl, verbose=False)
    if not paragraph_format_report['ok']:
        report['ok'] = False
        # 合并错误消息，避免重复
        for msg in paragraph_format_report['messages']:
            if msg not in report['messages']:
                report['messages'].append(msg)

    return report

def check_chinese_keywords(doc, chinese_section, tpl):
    """检测中文关键词格式和内容"""
    report = {'ok': True, 'messages': []}
    
    if chinese_section is None or chinese_section['keywords_index'] is None:
        report['ok'] = False
        report['messages'].append("未找到中文关键词")
        return report
    
    keywords_para = doc.paragraphs[chinese_section['keywords_index']]
    keywords_text = keywords_para.text.strip()
    print(f"检测中文关键词段落: '{keywords_text[:50]}...'")
    
    expected_format = tpl.get('format_rules', {}).get('keywords', {})
    
    # 1. 检查标题格式
    label_match = re.search(r'^(关键(?:词|字))\s*[:：]?', keywords_text)
    if not label_match:
        report['ok'] = False
        report['messages'].append("未找到“关键词”标题，或标题格式不正确")
        return report

    label_text_with_colon = label_match.group(0)
    label_end_pos = len(label_text_with_colon)
    current_text_pos = 0

    for run in keywords_para.runs:
        if not run.text.strip():
            current_text_pos += len(run.text)
            continue
            
        font_size, font_ascii, font_eastasia, is_bold, is_italic = detect_font_for_run(run, keywords_para)
        
        is_label_part = current_text_pos < label_end_pos

        if is_label_part:
            if not is_bold:
                report['ok'] = False
                report['messages'].append(f"关键词标题“{run.text}”部分应加粗")
        else:
            if is_bold:
                report['ok'] = False
                report['messages'].append(f"关键词内容“{run.text}”部分不应加粗")
            
            # 检查字体和字号
            expected_chinese_font = expected_format.get('chinese_font', '宋体')
            if re.search(r'[\u4e00-\u9fff]', run.text) and font_eastasia != expected_chinese_font:
                msg = f"中文字体应为{expected_chinese_font}（当前：{font_eastasia}）"
                if msg not in report['messages']:
                    report['ok'] = False; report['messages'].append(msg)

            expected_english_font = expected_format.get('english_font', 'Times New Roman')
            if re.search(r'[a-zA-Z]', run.text) and font_ascii != expected_english_font:
                msg = f"英文字体应为{expected_english_font}（当前：{font_ascii}）"
                if msg not in report['messages']:
                    report['ok'] = False; report['messages'].append(msg)

            expected_size = expected_format.get('font_size_pt', 12)
            if abs(font_size - expected_size) > 0.5:
                msg = f"字号应为{get_font_size(expected_size)}({expected_size}pt)，当前为{get_font_size(font_size)}({font_size}pt)"
                if msg not in report['messages']:
                    report['ok'] = False; report['messages'].append(msg)
                    
        current_text_pos += len(run.text)

    # 2. 检查段落级格式（如对齐、段间距、缩进等），但跳过bold/italic检查，因为前面已处理
    format_rules_for_paragraph = expected_format.copy()
    format_rules_for_paragraph.pop('bold', None)
    format_rules_for_paragraph.pop('italic', None)
    paragraph_format_report = check_paragraph_full_format(keywords_para, "中文关键词", format_rules_for_paragraph, tpl, verbose=False)
    if not paragraph_format_report['ok']:
        report['ok'] = False
        # 合并错误消息，避免重复
        for msg in paragraph_format_report['messages']:
            if msg not in report['messages']:
                report['messages'].append(msg)

    # 3. 检测分隔符 (保留原有逻辑)
    keywords_rules = tpl.get('check_rules', {}).get('keywords_rules', {})
    if keywords_rules.get('check_separator', True):
        match = re.search(r'关键(词|字)\s*[:：]\s*(.+)', keywords_text)
        if match:
            keywords_content = match.group(2)
            
            # 查找所有分隔符
            separators = re.findall(r'[，；,;]', keywords_content)
            
            # 期望的分隔符
            expected_separator = keywords_rules.get('separator', '；')
            
            print(f"  关键词分隔符: {separators}")
            
            # 检查是否有不符合要求的分隔符
            for sep in separators:
                if sep != expected_separator:
                    report['ok'] = False
                    report['messages'].append(f"关键词之间应使用“{expected_separator}”分隔（检测到“{sep}”）")
                    break
    
    return report

def check_chinese_section_with_template(docx_path, template_identifier):
    """
    中文部分检测的主函数
    """
    print(f"--- 开始中文部分检测 ---")
    tpl = load_template(template_identifier)
    doc = Document(docx_path)
    
    all_reports = {}
    
    # 1. 定位中文部分
    chinese_section = find_chinese_section(doc)
    if not chinese_section:
        print("文档中未找到中文部分，跳过检测")
        return {"summary": ["未找到中文部分"]}
    
    # 2. 依次检测各个部分
    # 检测标题
    title_report = check_chinese_title(doc, chinese_section, tpl)
    all_reports['chinese_title_format'] = title_report
    
    # 检测作者
    authors_data = []
    if chinese_section.get('author_index') is not None:
        author_text = doc.paragraphs[chinese_section['author_index']].text.strip()
        authors_data = parse_chinese_authors(author_text)
    author_report = check_chinese_author(doc, chinese_section, tpl)
    all_reports['chinese_author_format'] = author_report
    
    # 检测单位
    affiliation_report = check_chinese_affiliation(doc, chinese_section, authors_data, tpl)
    all_reports['chinese_affiliation_format'] = affiliation_report
    
    # 检测摘要
    abstract_report = check_chinese_abstract(doc, chinese_section, tpl)
    all_reports['chinese_abstract_format'] = abstract_report
    
    # 检测关键词
    keywords_report = check_chinese_keywords(doc, chinese_section, tpl)
    all_reports['chinese_keywords_format'] = keywords_report
    
    # 3. 生成总结
    summary = []
    for section, report in all_reports.items():
        if not report.get('ok', True):
            section_name = section
            messages = report.get('messages', [])
            if messages:
                summary.append(f"{section_name} 检测失败:")
                for msg in messages:
                    summary.append(f"  • {msg}")
    all_reports['summary'] = summary if summary else ["中文部分格式基本符合要求"]
    
    print(f"--- 中文部分检测完成 ---")
    return all_reports

if __name__ == '__main__':
    # 用于独立测试
    if len(sys.argv) > 2 and sys.argv[1] == 'check':
        docx_file = sys.argv[2]
        report = check_chinese_section_with_template(docx_file, 'Chinese_section')
        
        # 使用与主报告类似的格式打印
        print("\n" + "="*60)
        print("中文部分检测报告 (独立运行)")
        print("="*60)
        
        module_cn_names = {
            'chinese_title_format': '中文标题',
            'chinese_author_format': '中文作者',
            'chinese_affiliation_format': '中文单位',
            'chinese_abstract_format': '中文摘要',
            'chinese_keywords_format': '中文关键词',
        }

        # 先显示单位检测的详细信息（如果有的话）
        affiliation_rep = report.get('chinese_affiliation_format', {})
        if affiliation_rep:
            print(f"\n  ┌─────────────────────────────────────────────────────┐")
            print(f"  │ 【中文单位检测详情】                                │")
            print(f"  └─────────────────────────────────────────────────────┘")
            
            # 显示所有单位的详细信息
            affiliations_detail = affiliation_rep.get('affiliations_detail', [])
            if affiliations_detail:
                for aff in affiliations_detail:
                    print(f"\n    单位 {aff['number']}: {aff['unit_name']}")
                    
                    # 显示文档地址检测结果
                    if aff.get('direct_address'):
                        print(f"      【文档地址检测】")
                        print(f"        检测地址: {aff['direct_address']}")
                        if aff.get('direct_zipcode'):
                            print(f"        API检测邮编: {aff['direct_zipcode']}")
                    
                    # 显示结构化地址检测结果
                    if aff.get('structured_address'):
                        print(f"      【结构化地址检测】")
                        print(f"        检测地址: {aff['structured_address']}")
                        if aff.get('structured_zipcode'):
                            print(f"        API检测邮编: {aff['structured_zipcode']}")
                    
                    # 显示最终结果
                    print(f"      文档邮编: {aff['doc_zipcode']}")
                    if aff.get('api_zipcode'):
                        if aff['match']:
                            print(f"      ✓ 邮编验证通过")
                        else:
                            print(f"      ✗ 邮编不匹配")
        
        print()
        
        for section, rep in report.items():
            if section == 'summary' or section == 'chinese_affiliation_format': continue
            
            section_name = module_cn_names.get(section, section)
            status = '✓ 通过' if rep.get('ok') else '✗ 失败'
            print(f"\n  [{section_name}] {status}")
            
            if not rep.get('ok'):
                for msg in rep.get('messages', []):
                    # 检查是否是"最相关的结果"消息
                    if '最相关的' in msg and '结果是' in msg:
                        # 提取最相关的结果部分
                        parts = msg.split('最相关的')
                        if len(parts) == 2:
                            prefix = parts[0] + '最相关的'
                            results_part = parts[1]
                            print(f"    • {prefix}")
                            print(f"      ┌─────────────────────────────────────┐")
                            # 分割结果并逐个显示
                            if '结果是：' in results_part:
                                results_text = results_part.split('结果是：')[1]
                                results_list = [r.strip() for r in results_text.split(',')]
                                for i, result in enumerate(results_list, 1):
                                    if result:
                                        print(f"      │ {i}. {result}")
                            print(f"      └─────────────────────────────────────┘")
                        else:
                            print(f"    • {msg}")
                    else:
                        print(f"    • {msg}")
        
        # 最后显示单位检测的格式问题
        if affiliation_rep and not affiliation_rep.get('ok'):
            print(f"\n  [中文单位] ✗ 失败")
            for msg in affiliation_rep.get('messages', []):
                if '总共找到' not in msg and '文档中的单位编号' not in msg and '识别为单位' not in msg and '邮编' not in msg and '检测地址' not in msg and '✓' not in msg and '✗' not in msg:
                    # 检查是否是"最相关的结果"消息
                    if '最相关的' in msg and '结果是' in msg:
                        # 提取最相关的结果部分
                        parts = msg.split('最相关的')
                        if len(parts) == 2:
                            prefix = parts[0] + '最相关的'
                            results_part = parts[1]
                            print(f"    • {prefix}")
                            print(f"      ┌─────────────────────────────────────┐")
                            # 分割结果并逐个显示
                            if '结果是：' in results_part:
                                results_text = results_part.split('结果是：')[1]
                                results_list = [r.strip() for r in results_text.split(',')]
                                for i, result in enumerate(results_list, 1):
                                    if result:
                                        print(f"      │ {i}. {result}")
                            print(f"      └─────────────────────────────────────┘")
                        else:
                            print(f"    • {msg}")
                    else:
                        print(f"    • {msg}")
        
        print("\n" + "="*60)
    else:
        print("使用方法: python Chinese_section_detect.py check <docx文件路径>")
