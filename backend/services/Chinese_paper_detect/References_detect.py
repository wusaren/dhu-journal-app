#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import logging
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

# 创建logger
logger = logging.getLogger(__name__)

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
=== 论文格式检测系统 - 参考文献检测器 ===

【参考文献检测 (References Detection)】

1. 【结构检测】
   - "参考文献"标题定位
   - 标题与内容之间的空行数（应空2行）
   - 参考文献数量统计
   - 序号格式检测（[1]格式）
   - 序号连续性检测

2. 【格式检测】
   - 标题格式：黑体3号（16pt），加粗，居中，段前0.7cm，段后0cm，单倍行距
   - 内容格式：中文小四宋体（12pt），英文Times New Roman，1.5倍行距
   - [标号]与作者之间空一格
   - 悬挂缩进2字符

3. 【引用检测 (Citation Detection)】
   - 检测正文中的上标引用（run.font.superscript）
   - 对比参考文献序号，找出未被引用的文献
   - 检测引用了不存在的序号
"""

# 需要排除的章节标题关键词（用于正文范围界定）
EXCLUDE_SECTIONS = [
    '摘要', 'Abstract',           # 摘要
    '关键词', 'Keywords',         # 关键词
    '参考文献', 'Reference',      # 参考文献本身
    '附录', 'Appendix',           # 附录
    '致谢', 'Acknowledg',         # 致谢
    '作者简历', 'Resume',         # 作者简历
    'Bibliography',              # 参考文献（英文）
    '参考文献', 'References',     # 参考文献
]

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
    检测run的字体信息，包括中英文字体
    返回: (font_size, font_ascii, font_eastasia, is_bold, is_italic, line_spacing)
    """
    font_size = None
    font_name_ascii = None
    font_name_eastasia = None
    is_bold = None
    is_italic = False
    
    if not run:
        return 12.0, "Times New Roman", "宋体", False, False, 1.0
    
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
    
    # 2. 检测英文字体和中文字体
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
    except Exception as e:
        logger.debug(f"  字体检测异常: {e}")
    
    font_name_ascii = font_name_ascii if font_name_ascii else "Times New Roman"
    font_name_eastasia = font_name_eastasia if font_name_eastasia else "宋体"
    
    # 【新增】如果字体名称仍为空，尝试从段落样式中读取
    if (font_name_eastasia == "宋体" or font_name_eastasia is None) and paragraph and paragraph.style:
        try:
            # 尝试从段落样式中读取中文字体
            if hasattr(paragraph.style.font, 'east_asia'):
                style_font_eastasia = getattr(paragraph.style.font, 'east_asia', None)
                if style_font_eastasia and hasattr(style_font_eastasia, 'name'):
                    style_font_name = style_font_eastasia.name
                    if style_font_name and style_font_name != '宋体':
                        font_name_eastasia = style_font_name
                        logger.debug(f"  [detect_font_for_run] 从段落样式中读取到中文字体: {style_font_name}")
            
            # 备选：直接从样式 font 对象读取（python-docx 较新版本）
            if font_name_eastasia == "宋体" and hasattr(paragraph.style.font, 'name'):
                style_font_name = paragraph.style.font.name
                if style_font_name and style_font_name != '宋体':
                    font_name_eastasia = style_font_name
                    logger.debug(f"  [detect_font_for_run] 从段落样式中读取到字体: {style_font_name}")
        except Exception as e:
            logger.debug(f"  [detect_font_for_run] 从段落样式读取字体异常: {e}")
    
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
    line_spacing = 1.0
    try:
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
        elif paragraph and paragraph.style and paragraph.style.paragraph_format.line_spacing:
            line_spacing = float(paragraph.style.paragraph_format.line_spacing)
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

def pt_to_chars(pt_value, font_size_pt=12):
    """将pt值转换为字符数"""
    if pt_value == 0:
        return 0
    return round(pt_value / font_size_pt, 1)

def cm_to_pt(cm_value):
    """厘米转换为pt"""
    return cm_value * 28.35

# ---------- 参考文献结构检测 ----------
def is_reference_entry(para, text, debug=False):
    """
    判断段落是否为参考文献条目
    
    参考文献条目特征：
    - 以 [数字] 开头：如 [1]、[2]、[10]（手动编号）
    - 有自动编号属性，且内容不为空（Word自动生成的编号）
    
    返回: (bool, extracted_number)
    """
    # 1. 先检查文本是否以 [数字] 开头（手动编号）
    match = re.match(r'^\[(\d+(?:\.\d+)?)\]\s*(.*)', text)
    if match:
        return True, int(match.group(1))
    
    # 2. 检查是否有自动编号（Word自动生成的编号）
    # 自动编号存储在 para._element.pPr.numPr 中
    try:
        numPr = para._element.pPr.numPr
        if numPr is not None:
            # 有自动编号，只要内容不为空就认为是参考文献
            # 短的参考文献也是有效的（如只有作者和年份的情况）
            if text and text.strip():
                if debug:
                    logger.debug(f"    [is_reference_entry] 检测到自动编号且内容非空 → 参考文献")
                return True, None  # None 表示有编号但无法提取数字
            
            if debug:
                logger.debug(f"    [is_reference_entry] 自动编号但内容为空 → 跳过")
            return False, None
    except AttributeError:
        pass
    
    return False, None

def is_chapter_title(text, debug=False):
    """
    判断段落是否为章节标题（用于判断参考文献结束）
    
    章节标题特征（不是参考文献）：
    - 以 数字. 开头：如 1. 引言、2.3 方法
    - 以 中文数字、 开头：如 一、概述、二、实验
    - 以 英文单词 开头（如纯英文标题）：如 Introduction、Conclusion
    - 纯数字无括号开头：如 1 引言
    
    参考文献条目特征（不会被判断为章节标题）：
    - [1]、[2] - 方括号开头
    
    返回: bool
    """
    # 跳过空行
    if not text:
        if debug:
            logger.debug(f"    [is_chapter_title] 空行 → False")
        return False
    
    # 0. 调试：显示原始文本
    if debug:
        logger.debug(f"    [is_chapter_title] 检查: {repr(text)[:60]}")
    
    # 1. 以 [数字] 开头的，是参考文献条目，不是章节标题
    if re.match(r'^\[\d+', text):
        if debug:
            logger.debug(f"    [is_chapter_title] 以'['数字'开头 → 参考文献条目 → False")
        return False
    
    # 2. 以 数字. 开头（阿拉伯数字+点+空格/文字）→ 章节标题
    # 如: "1. 引言", "2.3 实验方法", "10 结论"
    if re.match(r'^\d+\.\s+\S', text) or re.match(r'^\d+\.\S', text):
        if debug:
            logger.debug(f"    [is_chapter_title] 匹配'数字.' → 章节标题 → True")
        return True
    
    # 3. 以 中文数字、 开头 → 章节标题
    # 如: "一、概述", "二、实验"
    if re.match(r'^[一二三四五六七八九十百千]+\s*、', text):
        if debug:
            logger.debug(f"    [is_chapter_title] 匹配'中文数字、' → 章节标题 → True")
        return True
    
    # 4. 以 英文单词 开头且较短（可能是标题）→ 可能是章节标题
    # 排除明显是句子的情况
    words = text.split()
    if words and len(words[0]) < 30:
        # 检查是否全英文单词（不是参考文献的作者-年份格式）
        if re.match(r'^[A-Z][a-zA-Z]+$', words[0]):
            # 常见英文章节标题
            english_titles = ['Introduction', 'Conclusion', 'References', 'Acknowledgements', 
                            'Abstract', 'Background', 'Methods', 'Results', 'Discussion',
                            'Experiment', 'Conclusion', 'Summary', 'Future', 'Appendix', 
                            'Bibliography', 'Acknowledgments', 'Conclusion']
            if words[0] in english_titles:
                if debug:
                    logger.debug(f"    [is_chapter_title] 匹配英文标题'{words[0]}' → 章节标题 → True")
                return True
    
    # 5. 中文特殊章节标题列表（没有数字编号的章节标题）
    # 如: "致谢"、"作者简历"、"简历及在学期间所获得的学术成果" 等
    chinese_chapter_titles = [
        '致谢', '谢辞', '感谢',
        '作者简历', '个人简历', '简历', '作者简介',
        '发表论文', '学术成果', '研究成果', '论文发表',
        '在学期间所获得的学术成果', '在学期间发表论文',
        '附录', '附录A', '附录B', '附录一', '附录二',
        '后记',
        '参考资料', '参考文献（续）'
    ]
    
    # 检查是否匹配任何已知的中文章节标题
    for title in chinese_chapter_titles:
        if text.strip() == title:
            if debug:
                logger.debug(f"    [is_chapter_title] 匹配已知中文章节标题'{title}' → 章节标题 → True")
            return True
    
    # 6. 启发式规则：检测"简历及..."、"发表论文及..."这类复合标题
    # 这类标题通常以"及"结尾，且包含"简历"、"论文"、"成果"等关键词
    if re.match(r'^.{5,40}$', text):  # 标题长度在5-40字符之间
        # 检查是否包含章节标题关键词（但不是参考文献特征）
        chapter_keywords = ['致谢', '感谢', '简历', '成果', '论文', '发表', '附录', '后记']
        ref_keywords = ['http', 'https', '[J]', '[M]', '[D]', 'DOI', 'doi.org', 
                       '出版社', 'Journal', 'Proceedings', 'Press', 'University']
        
        has_chapter_kw = any(kw in text for kw in chapter_keywords)
        has_ref_kw = any(kw in text for kw in ref_keywords)
        
        # 如果包含章节关键词但不包含参考文献关键词，且没有数字编号，可能是章节标题
        if has_chapter_kw and not has_ref_kw:
            # 进一步检查：不以 [数字] 开头
            if not re.match(r'^\[', text):
                if debug:
                    logger.debug(f"    [is_chapter_title] 短段落+章节关键词+无参考文献特征 → 可能标题 → True")
                return True
    
    # 7. 如果段落很短（<50字符）且没有包含典型参考文献特征，可能是标题
    # 典型参考文献特征：包含 https://、http://、[J]、[M]、年份(2020)等
    ref_indicators = ['http://', 'https://', '[J]', '[M]', '[D]', '[EB/OL]', 
                     r'\(\d{4}\)', r'\d{4}年', '出版社', 'Journal', 'Proceedings', 
                     'Press', 'University', 'DOI', 'doi.org']
    has_ref_indicator = any(indicator in text for indicator in ref_indicators)
    
    if len(text) < 80 and not has_ref_indicator:
        # 短段落且没有参考文献特征，可能是标题
        if re.match(r'^[A-Z0-9\s\-\']+$', text):
            if debug:
                logger.debug(f"    [is_chapter_title] 短段落无参考文献特征 → 可能标题 → True")
            return True
    
    if debug:
        logger.debug(f"    [is_chapter_title] 不匹配任何章节标题特征 → False")
    return False

def check_references_structure(doc, tpl, debug=False):
    """
    检查参考文献结构
    返回 {'ok': bool, 'messages': [], 'header_paragraph': paragraph, 'content_paragraphs': [paragraphs]}
    
    参数:
        doc: Word文档对象
        tpl: 模板配置
        debug: 是否输出详细调试日志（默认False，设为True可查看定位过程）
    """
    report = {'ok': True, 'messages': [], 'header_paragraph': None, 'content_paragraphs': [], 'blank_lines_after_header': 0}
    
    structure_rules = tpl.get('structure_rules', {})
    header_pattern = structure_rules.get('header_pattern', r'^\\s*参考文献\\s*$')
    expected_blank_lines = structure_rules.get('blank_lines_after_header', 2)
    
    # ============== 步骤1：查找"参考文献"标题 ==============
    if debug:
        logger.debug("\n" + "=" * 80)
        logger.debug("【参考文献定位调试 - 步骤1：查找标题】")
        logger.debug(f"使用的正则: {repr(header_pattern)}")
        logger.debug("-" * 80)
    
    header_para = None
    header_idx = None
    
    # ========== 方案A：从论文中间位置开始查找，跳过目录中的条目 ==========
    # 参考文献只可能在论文后半部分（通常在正文最后一个章节之后）
    search_start = len(doc.paragraphs) // 2
    
    if debug:
        logger.debug(f"  从段落 {search_start} 开始查找（共 {len(doc.paragraphs)} 个段落）")
    
    for idx in range(search_start, len(doc.paragraphs)):
        paragraph = doc.paragraphs[idx]
        text = paragraph.text.strip()
        if debug:
            logger.debug(f"  [{idx}] 检查段落: {repr(text)[:50]}")
        if re.match(header_pattern, text):
            header_para = paragraph
            header_idx = idx
            if debug:
                logger.debug(f"  ✓ 找到标题在第 {idx} 行: '{text}'")
            break
    
    # 如果后半部分没找到，再尝试从前半部分查找（容错处理）
    if not header_para:
        if debug:
            logger.debug(f"  ⚠ 后半部分未找到，尝试从前半部分查找...")
        for idx in range(0, search_start):
            paragraph = doc.paragraphs[idx]
            text = paragraph.text.strip()
            if debug:
                logger.debug(f"  [{idx}] 检查段落: {repr(text)[:50]}")
            if re.match(header_pattern, text):
                header_para = paragraph
                header_idx = idx
                if debug:
                    logger.debug(f"  ✓ 找到标题在第 {idx} 行: '{text}'")
                break
    
    if not header_para:
        report['ok'] = False
        error_msg = tpl.get('messages', {}).get('structure_header_error')
        if error_msg:
            report['messages'].append(error_msg)
        else:
            report['messages'].append("未找到'参考文献'标题段落")
        if debug:
            logger.debug(f"\n❌ 未找到参考文献标题！")
        return report
    
    report['header_paragraph'] = header_para
    report['header_paragraph_index'] = header_idx
    
    if debug:
        logger.debug(f"\n【参考文献定位调试 - 步骤2：检查标题格式】")
        logger.debug(f"  标题文本: '{header_para.text.strip()}'")
    
    # 2. 检查标题格式（允许中间有空格，如"参 考 文 献"）
    title_text = header_para.text.strip()
    # 使用正则匹配：匹配纯"参考文献"或中间有空格的情况
    if re.match(r'^参\s*考\s*文\s*献$', title_text):
        ok_msg = tpl.get('messages', {}).get('structure_header_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    else:
        report['ok'] = False
        report['messages'].append(f"参考文献标题应为纯'参考文献'，实际为'{title_text}'")
    
    # ============== 步骤3：统计空行数 ==============
    if debug:
        logger.debug(f"\n【参考文献定位调试 - 步骤3：统计标题与内容之间的空行】")
    
    blank_count = 0
    content_start_idx = header_idx + 1
    
    for idx in range(content_start_idx, len(doc.paragraphs)):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
            blank_count += 1
            if debug:
                logger.debug(f"  [{idx}] 空行 ({blank_count})")
            continue
        
        # 跳过脚注、尾注等特殊内容
        if '[!' in text or 'footnote' in text.lower():
            if debug:
                logger.debug(f"  [{idx}] 跳过脚注/尾注: {text[:30]}")
            continue
        
        # 找到参考文献内容开始
        if debug:
            logger.debug(f"  [{idx}] 开始参考文献内容: {repr(text)[:50]}")
        break
    
    report['blank_lines_after_header'] = blank_count
    
    if debug:
        logger.debug(f"\n【参考文献定位调试 - 步骤4：提取参考文献内容】")
        logger.debug(f"期望空行数: {expected_blank_lines}, 实际空行数: {blank_count}")
        logger.debug("-" * 80)
    
    if blank_count >= expected_blank_lines:
        ok_msg = tpl.get('messages', {}).get('structure_blank_after_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    else:
        report['ok'] = False
        error_msg = tpl.get('messages', {}).get('structure_blank_after_error')
        if error_msg:
            report['messages'].append(error_msg)
    
    # ============== 步骤4：提取参考文献内容段落 ==============
    content_paragraphs = []
    content_paragraph_indices = []  # 新增：记录段落索引
    reference_numbers = []
    
    # 调试信息
    debug_info = []
    
    if debug:
        logger.debug(f"\n开始扫描参考文献内容（从第 {content_start_idx} 段开始）...")
        logger.debug(f"判断规则：")
        logger.debug(f"  - 以 [数字] 开头 → 参考文献条目")
        logger.debug(f"  - 以 数字. 开头 → 章节标题（停止）")
        logger.debug(f"  - 以 中文数字、 开头 → 章节标题（停止）")
        logger.debug(f"  - 附录/致谢 等关键词 → 停止")
        logger.debug("-" * 80)
    
    for idx in range(content_start_idx, len(doc.paragraphs)):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
            if debug:
                logger.debug(f"  [{idx}] 跳过空行")
            continue
        
        # 停止关键词列表（附录、致谢等）
        stop_keywords = ['附录', '致谢', '攻读学位期间', '作者简历', 'Bibliography']
        
        # 检查是否遇到停止关键词
        hit_stop_keyword = None
        for keyword in stop_keywords:
            if keyword in text:
                hit_stop_keyword = keyword
                break
        
        if hit_stop_keyword:
            if debug:
                logger.debug(f"  [{idx}] ⏹ 遇到停止关键词 '{hit_stop_keyword}'，停止提取")
            debug_info.append(f"[{idx}] 遇到'{hit_stop_keyword}'，停止提取")
            break
        
        # 判断是否为章节标题（新的一章开始了）
        if is_chapter_title(text, debug=debug):
            if debug:
                logger.debug(f"  [{idx}] ⏹ 检测到章节标题，停止提取: {text[:40]}...")
            debug_info.append(f"[{idx}] 检测到章节标题，停止提取: {text[:30]}...")
            break
        
        # 判断是否为参考文献条目（支持自动编号）
        is_ref, ref_num = is_reference_entry(para, text, debug=debug)
        if is_ref:
            content_paragraphs.append(para)
            content_paragraph_indices.append(idx)  # 新增：记录段落索引
            reference_numbers.append(ref_num if ref_num is not None else -1)  # -1 表示自动编号
            if debug:
                num_str = f"[{ref_num}]" if ref_num is not None else "[自动编号]"
                logger.debug(f"  [{idx}] ✓ 提取参考文献{num_str}: {text[:50]}...")
            debug_info.append(f"[{idx}] 提取参考文献: {text[:40]}...")
        elif re.search(r'\[\d+\]', text):
            # 包含序号但不是开头（不规范格式）
            content_paragraphs.append(para)
            content_paragraph_indices.append(idx)  # 新增：记录段落索引
            nums = re.findall(r'\[(\d+(?:\.\d+)?)\]', text)
            reference_numbers.extend([int(float(n)) for n in nums])
            if debug:
                logger.debug(f"  [{idx}] ? 提取不规范参考文献: {text[:50]}... (序号: {nums})")
            debug_info.append(f"[{idx}] 提取不规范参考文献: {text[:40]}...")
        else:
            # 既不是参考文献也不是章节标题，跳过
            if debug:
                logger.debug(f"  [{idx}] ✗ 既不是参考文献也不是章节标题，跳过: {text[:50]}...")
    
    # ============== 打印调试汇总 ==============
    if debug:
        logger.debug("\n" + "=" * 80)
        logger.debug("【参考文献提取调试汇总】")
        logger.debug("=" * 80)
        for info in debug_info:
            logger.debug(info)
        logger.debug(f"\n共提取 {len(content_paragraphs)} 条参考文献")
        logger.debug(f"提取的序号: {reference_numbers}")
        if reference_numbers:
            if list(range(1, max(reference_numbers) + 1)) == reference_numbers:
                logger.debug("✓ 序号连续")
            else:
                missing = set(range(1, max(reference_numbers) + 1)) - set(reference_numbers)
                logger.debug(f"✗ 缺失序号: {sorted(missing)}")
        logger.debug("=" * 80 + "\n")
    
    report['content_paragraphs'] = content_paragraphs
    report['content_paragraph_indices'] = content_paragraph_indices  # 添加段落索引
    report['reference_numbers'] = reference_numbers
    
    # 5. 检测参考文献数量
    ref_count = len(content_paragraphs)
    min_count = structure_rules.get('min_references_count', 1)
    max_count = structure_rules.get('max_references_count', 200)
    
    if ref_count == 0:
        report['ok'] = False
        msg = tpl.get('messages', {}).get('structure_count_none')
        if msg:
            report['messages'].append(msg)
    elif ref_count < min_count:
        report['ok'] = False
        report['messages'].append(f"参考文献数量过少（{ref_count}条），建议至少{min_count}条")
    elif ref_count > max_count:
        report['ok'] = False
        report['messages'].append(f"参考文献数量过多（{ref_count}条），超过{max_count}条上限")
    else:
        ok_msg = tpl.get('messages', {}).get('structure_count_ok')
        if ok_msg:
            try:
                report['messages'].append(ok_msg.format(count=ref_count))
            except:
                report['messages'].append(ok_msg)
    
    # 6. 检测序号格式和连续性
    if reference_numbers:
        # 过滤掉 None 和 -1（自动编号），只检查有实际数字的序号
        valid_numbers = [n for n in reference_numbers if n and n > 0]
        auto_numbers_count = sum(1 for n in reference_numbers if n == -1)
        
        # 检查序号格式
        first_ref = content_paragraphs[0].text.strip() if content_paragraphs else ""
        if re.match(r'^\[\d+\]', first_ref):
            ok_msg = tpl.get('messages', {}).get('structure_number_ok')
            if ok_msg:
                report['messages'].append(ok_msg)
        elif valid_numbers:
            # 有有效序号但文本开头不是 [数字]，可能是自动编号
            ok_msg = tpl.get('messages', {}).get('structure_number_ok')
            if ok_msg:
                report['messages'].append(ok_msg + "（自动编号）")
        elif auto_numbers_count > 0:
            # 全是自动编号，无法检查序号格式
            report['messages'].append(f"检测到{auto_numbers_count}条自动编号参考文献")
        else:
            # 没有序号
            report['messages'].append("未检测到参考文献序号")
        
        # 检查序号连续性（只对有实际数字的序号）
        if len(valid_numbers) >= 2:
            expected_seq = list(range(1, max(valid_numbers) + 1))
            missing = set(expected_seq) - set(valid_numbers)
            
            if not missing:
                ok_msg = tpl.get('messages', {}).get('structure_sequence_ok')
                if ok_msg:
                    report['messages'].append(ok_msg)
            else:
                report['ok'] = False
                missing_str = ', '.join([str(m) for m in sorted(missing)[:5]])
                if len(missing) > 5:
                    missing_str += f'等{len(missing)}个'
                error_msg = tpl.get('messages', {}).get('structure_sequence_error')
                if error_msg:
                    try:
                        report['messages'].append(error_msg.format(missing=missing_str))
                    except:
                        report['messages'].append(error_msg)
        elif len(valid_numbers) == 1:
            # 只有1个有效序号，无法检查连续性
            report['messages'].append("仅检测到1条参考文献，无法检查序号连续性")
        # elif auto_numbers_count > 0:
        #     # 全是自动编号，无法检查连续性 → 整句删除，不提示
    
    return report

# ---------- 参考文献标题格式检测 ----------
def check_reference_header_format(paragraph, tpl):
    """检查参考文献标题格式"""
    report = {'ok': True, 'messages': []}
    
    if not paragraph or not paragraph.runs:
        report['ok'] = False
        report['messages'].append("参考文献标题段落没有文本内容")
        return report
    
    format_rules = tpl.get('format_rules', {}).get('header', {})
    
    # 检测第一个非空run的格式
    main_run = None
    for run in paragraph.runs:
        if run.text.strip():
            main_run = run
            break
    
    if not main_run:
        report['ok'] = False
        report['messages'].append("参考文献标题段落没有有效文本")
        return report
    
    actual_size_pt, actual_font_ascii, actual_font_eastasia, actual_bold, actual_italic, actual_line_spacing = detect_font_for_run(main_run, paragraph)
    
    issues = []
    
    # 【新增】判断是否是样式继承（没有直接设置字体，从段落样式继承）
    is_style_inherited = False
    if main_run and hasattr(main_run, 'font') and main_run.font and main_run.font.name is None:
        if paragraph and paragraph.style:
            try:
                # 检查段落样式是否有字体设置
                if hasattr(paragraph.style, 'font'):
                    style_font = paragraph.style.font
                    # 如果样式有字体设置，认为是样式继承
                    if hasattr(style_font, 'name') or hasattr(style_font, 'east_asia'):
                        is_style_inherited = True
                        logger.debug(f"  [check_reference_header_format] 检测到标题为样式继承，跳过字体格式检查")
            except Exception:
                pass
    
    # 字体大小检查
    if not should_skip_check('font_size') and 'font_size_pt' in format_rules:
        # 【新增】样式继承时跳过字体大小检查
        if is_style_inherited:
            logger.debug(f"参考文献标题字体大小: 样式继承，跳过检查")
        else:
            expected_size_pt = float(format_rules['font_size_pt'])
            actual_size_name = get_font_size(actual_size_pt, tpl)
            expected_size_name = get_font_size(expected_size_pt, tpl)
            logger.debug(f"参考文献标题字体大小: {actual_size_name}（{actual_size_pt}pt）(期望: {expected_size_name}（{expected_size_pt}pt）)")
            if abs(actual_size_pt - expected_size_pt) > 0.5:
                issues.append(f"标题字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）")
    
    # 中文字体检查
    if not should_skip_check('font_name') and 'font_name' in format_rules:
        # 【新增】样式继承时跳过字体检查
        if is_style_inherited:
            logger.debug(f"参考文献标题中文字体: 样式继承，跳过检查")
        else:
            expected_font_name = str(format_rules['font_name'])
            logger.debug(f"参考文献标题中文字体: {actual_font_eastasia} (期望: {expected_font_name})")
            if expected_font_name.lower() not in actual_font_eastasia.lower():
                issues.append(f"标题中文字体应为{expected_font_name}，实际为{actual_font_eastasia}")
    
    # 加粗检查
    if not should_skip_check('bold') and 'bold' in format_rules:
        expected_bold = bool(format_rules['bold'])
        logger.debug(f"参考文献标题加粗: {'是' if actual_bold else '否'} (期望: {'是' if expected_bold else '否'})")
        if actual_bold != expected_bold:
            bold_status = "加粗" if expected_bold else "不加粗"
            actual_status = "加粗" if actual_bold else "不加粗"
            issues.append(f"标题字体应为{bold_status}，实际为{actual_status}")
    
    # 行间距检查
    if not should_skip_check('spacing') and 'line_spacing' in format_rules:
        expected_line_spacing = float(format_rules['line_spacing'])
        actual_spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
        expected_spacing_name = get_line_spacing_name(expected_line_spacing, tpl)
        logger.debug(f"参考文献标题行间距: {actual_spacing_name}（{actual_line_spacing}倍）(期望: {expected_spacing_name}（{expected_line_spacing}倍）)")
        if abs(actual_line_spacing - expected_line_spacing) > 0.1:
            issues.append(f"标题行间距应为{expected_spacing_name}（{expected_line_spacing}倍），实际为{actual_spacing_name}（{actual_line_spacing}倍）")
    
    # 段落对齐检查
    if 'alignment' in format_rules:
        expected_alignment_str = str(format_rules['alignment'])
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        expected_alignment = alignment_map.get(expected_alignment_str, 0)
        
        actual_alignment = detect_paragraph_alignment(paragraph)
        actual_alignment_name = get_alignment_name(actual_alignment, tpl)
        expected_alignment_name = get_alignment_name(expected_alignment, tpl)
        logger.debug(f"参考文献标题对齐: {actual_alignment_name} (期望: {expected_alignment_name})")
        if actual_alignment != expected_alignment:
            issues.append(f"标题应为{expected_alignment_name}，实际为{actual_alignment_name}")
    
    # 段前间距检查
    if 'space_before_cm' in format_rules:
        expected_space_before_cm = float(format_rules['space_before_cm'])
        expected_space_before_pt = cm_to_pt(expected_space_before_cm)
        
        try:
            actual_space_before = paragraph.paragraph_format.space_before
            actual_space_before_pt = actual_space_before.pt if actual_space_before else None
            
            # 【新增】如果段落直接设置没有值，尝试从样式继承读取
            if actual_space_before_pt is None and paragraph.style:
                try:
                    if hasattr(paragraph.style.paragraph_format, 'space_before'):
                        style_space_before = paragraph.style.paragraph_format.space_before
                        if style_space_before:
                            actual_space_before_pt = style_space_before.pt
                            logger.debug(f"  [check_references_header_format] 从段落样式读取到段前间距: {actual_space_before_pt:.1f}pt")
                except Exception as e:
                    logger.debug(f"  [check_references_header_format] 从段落样式读取段前间距异常: {e}")
            
            # 如果仍然没有，默认值为0
            if actual_space_before_pt is None:
                actual_space_before_pt = 0
                
            logger.debug(f"参考文献标题段前间距: {actual_space_before_pt:.1f}pt (期望: {expected_space_before_pt:.1f}pt ≈ {expected_space_before_cm}cm)")
            if abs(actual_space_before_pt - expected_space_before_pt) > 5:  # 容差5pt
                issues.append(f"标题段前间距应为{expected_space_before_cm}厘米，实际约为{actual_space_before_pt / 28.35:.2f}厘米")
        except Exception as e:
            logger.debug(f"  段前间距检测异常: {e}")
    
    # 段后间距检查
    if 'space_after_cm' in format_rules:
        expected_space_after_cm = float(format_rules['space_after_cm'])
        expected_space_after_pt = cm_to_pt(expected_space_after_cm)
        
        try:
            actual_space_after = paragraph.paragraph_format.space_after
            actual_space_after_pt = actual_space_after.pt if actual_space_after else None
            
            # 【新增】如果段落直接设置没有值，尝试从样式继承读取
            if actual_space_after_pt is None and paragraph.style:
                try:
                    if hasattr(paragraph.style.paragraph_format, 'space_after'):
                        style_space_after = paragraph.style.paragraph_format.space_after
                        if style_space_after:
                            actual_space_after_pt = style_space_after.pt
                            logger.debug(f"  [check_references_header_format] 从段落样式读取到段后间距: {actual_space_after_pt:.1f}pt")
                except Exception as e:
                    logger.debug(f"  [check_references_header_format] 从段落样式读取段后间距异常: {e}")
            
            # 如果仍然没有，默认值为0
            if actual_space_after_pt is None:
                actual_space_after_pt = 0
                
            logger.debug(f"参考文献标题段后间距: {actual_space_after_pt:.1f}pt (期望: {expected_space_after_pt:.1f}pt ≈ {expected_space_after_cm}cm)")
            if abs(actual_space_after_pt - expected_space_after_pt) > 5:  # 容差5pt
                issues.append(f"标题段后间距应为{expected_space_after_cm}厘米，实际约为{actual_space_after_pt / 28.35:.2f}厘米")
        except Exception as e:
            logger.debug(f"  段后间距检测异常: {e}")
    
    logger.debug(f"参考文献标题格式检查发现 {len(issues)} 个问题")
    logger.debug("---")
    
    if issues:
        report['ok'] = False
        header = tpl.get('messages', {}).get('format_header_issue_header')
        if header:
            report['messages'].append(header)
        report['messages'].extend([f"  - {i}" for i in issues])
    else:
        ok_msg = tpl.get('messages', {}).get('format_header_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    
    return report

# ---------- 参考文献内容格式检测 ----------
def check_reference_content_format(content_paragraphs, tpl):
    """检查参考文献内容格式"""
    report = {'ok': True, 'messages': []}
    
    if not content_paragraphs:
        report['ok'] = False
        report['messages'].append("参考文献内容段落为空")
        return report
    
    format_rules = tpl.get('format_rules', {}).get('content', {})
    number_rules = tpl.get('format_rules', {}).get('number', {})
    issues = []
    
    # 检查每个参考文献段落
    for para_idx, paragraph in enumerate(content_paragraphs, 1):
        if not paragraph or not paragraph.runs:
            continue
        
        # 检测段落格式
        first_line_indent, left_indent, right_indent = detect_paragraph_indent(paragraph)
        actual_alignment = detect_paragraph_alignment(paragraph)
        
        # 检测第一个非空run的格式
        main_run = None
        for run in paragraph.runs:
            if run.text.strip():
                main_run = run
                break
        
        if not main_run:
            continue
        
        actual_size_pt, actual_font_ascii, actual_font_eastasia, actual_bold, actual_italic, actual_line_spacing = detect_font_for_run(main_run, paragraph)
        
        # 1. 字体大小检查
        if not should_skip_check('font_size') and 'font_size_pt' in format_rules:
            expected_size_pt = float(format_rules['font_size_pt'])
            actual_size_name = get_font_size(actual_size_pt, tpl)
            expected_size_name = get_font_size(expected_size_pt, tpl)
            if abs(actual_size_pt - expected_size_pt) > 0.5:
                msg = f"第{para_idx}条参考文献字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）"
                if msg not in issues:
                    issues.append(msg)
        
        # 2. 中文字体检查
        if re.search(r'[\u4e00-\u9fff]', main_run.text):
            expected_chinese_font = format_rules.get('chinese_font', '宋体')
            if expected_chinese_font.lower() not in actual_font_eastasia.lower():
                msg = f"第{para_idx}条参考文献中文文字字体应为{expected_chinese_font}，实际为{actual_font_eastasia}"
                if msg not in issues:
                    issues.append(msg)
        
        # 3. 英文字体检查
        if re.search(r'[a-zA-Z]', main_run.text):
            expected_english_font = format_rules.get('english_font', 'Times New Roman')
            if expected_english_font.lower() not in actual_font_ascii.lower():
                msg = f"第{para_idx}条参考文献英文文字字体应为{expected_english_font}，实际为{actual_font_ascii}"
                if msg not in issues:
                    issues.append(msg)
        
        # 4. 行间距检查
        if not should_skip_check('spacing') and 'line_spacing' in format_rules:
            expected_line_spacing = float(format_rules['line_spacing'])
            if abs(actual_line_spacing - expected_line_spacing) > 0.1:
                actual_spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
                expected_spacing_name = get_line_spacing_name(expected_line_spacing, tpl)
                msg = f"第{para_idx}条参考文献行间距应为{expected_spacing_name}（{expected_line_spacing}倍），实际为{actual_spacing_name}（{actual_line_spacing}倍）"
                if msg not in issues:
                    issues.append(msg)
        
        # 5. 悬挂缩进检查（首行应为0，后续行有缩进）
        if 'hanging_indent' in format_rules:
            expected_hanging_chars = float(format_rules['hanging_indent'])
            expected_hanging_pt = expected_hanging_chars * actual_size_pt
            
            # 悬挂缩进：首行缩进为0，左缩进等于悬挂缩进值
            if left_indent > 1:  # 有左缩进
                hanging_chars = pt_to_chars(left_indent, actual_size_pt)
                if abs(left_indent - expected_hanging_pt) > actual_size_pt * 0.5:
                    msg = f"第{para_idx}条参考文献悬挂缩进应为{expected_hanging_chars}字符，实际约为{hanging_chars}字符"
                    if msg not in issues:
                        issues.append(msg)
            else:
                msg = f"第{para_idx}条参考文献应使用悬挂缩进（首行无缩进，后续行缩进{expected_hanging_chars}字符）"
                if msg not in issues:
                    issues.append(msg)
        
        # 6. [标号]与作者之间空一格检查
        para_text = paragraph.text.strip()
        number_author_match = re.match(r'^\[(\d+)\]\s+', para_text)
        if number_author_match:
            space_after_number = len(number_author_match.group(0)) - len(f"[{number_author_match.group(1)}]")
            if space_after_number != 1:
                msg = f"第{para_idx}条参考文献[标号]与作者之间应空一格（当前空{space_after_number}格）"
                if msg not in issues:
                    issues.append(msg)
        else:
            # 检查是否包含序号但格式不正确
            if re.search(r'\[\d+\]', para_text):
                msg = f"第{para_idx}条参考文献序号格式不正确，应为'[序号] 作者'格式"
                if msg not in issues:
                    issues.append(msg)
    
    logger.debug(f"参考文献内容格式检查发现 {len(issues)} 个问题")
    logger.debug("---")
    
    if issues:
        report['ok'] = False
        header = tpl.get('messages', {}).get('format_content_issue_header')
        if header:
            report['messages'].append(header)
        report['messages'].extend([f"  - {i}" for i in issues])
    else:
        ok_msg = tpl.get('messages', {}).get('format_content_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    
    return report


# ==================== 引用检测模块 ====================

def extract_superscript_citations(paragraph, debug=False):
    """
    从段落中提取上标引用序号
    
    参数:
        paragraph: 段落对象
        debug: 是否输出调试日志
    
    返回:
        list: 提取到的引用序号列表（去重）
    """
    citations = set()
    
    if debug:
        para_text = paragraph.text.strip()[:60] if paragraph.text.strip() else "(空段落)"
        logger.debug(f"\n--- 检查段落: {para_text}... ---")
        logger.debug(f"    段落共有 {len(paragraph.runs)} 个 run")
    
    for run_idx, run in enumerate(paragraph.runs):
        if debug:
            # 输出 run 的详细信息
            run_text = run.text if run.text else "(空)"
            superscript = run.font.superscript
            subscript = run.font.subscript
            logger.debug(f"    Run[{run_idx}]: text='{run_text[:30]}...' | superscript={superscript}, subscript={subscript}")
        
        # 检查是否为上标
        if run.font.superscript:
            text = run.text.strip()
            if not text:
                continue
            
            if debug:
                logger.debug(f"    ★ 检测到上标文本: '{text}'")
            
            # 解析上标内容
            # 支持格式：
            # - 纯数字: "1" -> 1
            # - 带方括号: "[27]" -> 27, "[1-3]" -> 1,2,3, "[1,3,5]" -> 1,3,5
            # - 范围: "1-3" -> 1,2,3
            # - 列表: "1,3,5" -> 1,3,5
            
            # 先去除方括号
            cleaned_text = text.strip('[]')
            
            # 处理带方括号的格式: [27], [1-3], [1,3,5]
            if text.startswith('[') and text.endswith(']'):
                # 处理范围: "1-3" -> 1,2,3
                if '-' in cleaned_text and cleaned_text.replace('-', '').replace(',', '').isdigit():
                    parts = cleaned_text.split('-')
                    if len(parts) == 2:
                        try:
                            start = int(parts[0])
                            end = int(parts[1])
                            for i in range(start, end + 1):
                                citations.add(i)
                            if debug:
                                logger.debug(f"    → 解析为带方括号范围: {text} -> {list(range(start, end + 1))}")
                        except ValueError:
                            pass
                    # 处理列表: "1,3,5" -> 1,3,5
                    elif ',' in cleaned_text:
                        parts = cleaned_text.split(',')
                        for part in parts:
                            part = part.strip()
                            if part.isdigit():
                                citations.add(int(part))
                        if debug:
                            logger.debug(f"    → 解析为带方括号列表: {text} -> {list(citations)}")
                        
                # 处理列表: "1,3,5" -> 1,3,5
                elif ',' in cleaned_text and cleaned_text.replace(',', '').isdigit():
                    parts = cleaned_text.split(',')
                    for part in parts:
                        part = part.strip()
                        if part.isdigit():
                            citations.add(int(part))
                    if debug:
                        logger.debug(f"    → 解析为带方括号列表: {text} -> {list(citations)}")
                        
                # 处理单个数字: "27" -> 27
                elif cleaned_text.isdigit():
                    citations.add(int(cleaned_text))
                    if debug:
                        logger.debug(f"    → 解析为带方括号数字: {text} -> {cleaned_text}")
                else:
                    if debug:
                        logger.debug(f"    → 无法解析的带方括号文本: '{text}'")
            
            # 处理不带方括号的格式（原有逻辑）
            else:
                # 处理范围: "1-3" -> 1,2,3
                if '-' in text and text.replace('-', '').isdigit():
                    parts = text.split('-')
                    if len(parts) == 2:
                        try:
                            start = int(parts[0])
                            end = int(parts[1])
                            for i in range(start, end + 1):
                                citations.add(i)
                            if debug:
                                logger.debug(f"    → 解析为范围: {text} -> {list(range(start, end + 1))}")
                        except ValueError:
                            pass
                            
                # 处理列表: "1,3,5" -> 1,3,5
                elif ',' in text and text.replace(',', '').isdigit():
                    parts = text.split(',')
                    for part in parts:
                        part = part.strip()
                        if part.isdigit():
                            citations.add(int(part))
                    if debug:
                        logger.debug(f"    → 解析为列表: {text} -> {list(citations)}")
                        
                # 处理单个数字: "1" -> 1
                elif text.isdigit():
                    citations.add(int(text))
                    if debug:
                        logger.debug(f"    → 解析为单个数字: {text}")
                else:
                    if debug:
                        logger.debug(f"    → 无法解析的上标文本: '{text}'")
    
    if debug:
        logger.debug(f"    本段落提取到的引用: {sorted(citations) if citations else '无'}")
    
    return list(citations)


def find_body_range(doc, references_header_idx, debug=False):
    """
    查找正文范围：从文档开头到"参考文献"标题之前
    
    参数:
        doc: Word文档对象
        references_header_idx: 参考文献标题的段落索引（如果为None则自动查找）
        debug: 是否输出调试日志
    
    返回:
        tuple: (正文起始段落索引, 正文结束段落索引)
    """
    if debug:
        logger.debug("\n" + "=" * 80)
        logger.debug("【正文范围定位】")
        logger.debug(f"文档共有 {len(doc.paragraphs)} 个段落")
        logger.debug("=" * 80)
    
    # 如果没有提供参考文献标题索引，先查找
    if references_header_idx is None:
        # 查找参考文献标题
        if debug:
            logger.debug("未提供参考文献标题索引，开始自动查找...")
        
        for idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if re.match(r'^参\s*考\s*文\s*献\s*$', text):
                references_header_idx = idx
                if debug:
                    logger.debug(f"✓ 找到参考文献标题在第 {idx} 段: '{text}'")
                break
        else:
            if debug:
                logger.debug("✗ 未找到参考文献标题")
    
    # 确定正文结束位置
    end_idx = references_header_idx if references_header_idx is not None else len(doc.paragraphs)
    
    if debug:
        logger.debug(f"\n正文结束位置: 第 {end_idx - 1} 段 (参考文献标题在第 {references_header_idx} 段)")
    
    # 确定正文起始位置
    # 跳过摘要、关键词等前面的内容，从第一个章节标题开始
    start_idx = 0
    
    # 常见的第一章标题模式
    chapter_patterns = [
        r'^第[一二三四五六七八九十百]+[章节篇部]\s*',  # 第一章、第二节等
        r'^[1-9]\s*[\.、]\s*\S',                      # 1. xxx
        r'^引言$',
        r'^绪论$',
        r'^Introduction$',
    ]
    
    if debug:
        logger.debug("\n开始查找正文起始位置...")
        logger.debug(f"将排除的章节关键词: {EXCLUDE_SECTIONS}")
        logger.debug("章节标题匹配模式:")
        for p in chapter_patterns:
            logger.debug(f"  - {p}")
    
    scanned = 0
    for idx in range(len(doc.paragraphs)):
        text = doc.paragraphs[idx].text.strip()
        
        # 跳过空段落
        if not text:
            continue
        
        scanned += 1
        if debug and scanned <= 20:  # 只显示前20个检查的段落
            # 检查是否在排除列表中
            is_excluded = False
            excluded_by = None
            for keyword in EXCLUDE_SECTIONS:
                if keyword in text:
                    is_excluded = True
                    excluded_by = keyword
                    break
            
            if is_excluded:
                logger.debug(f"  段落[{idx}] ✗ 跳过 (包含排除关键词 '{excluded_by}'): {text[:40]}...")
            else:
                # 检查是否匹配章节标题
                matched = False
                for pattern in chapter_patterns:
                    if re.match(pattern, text):
                        matched = True
                        break
                
                if matched:
                    logger.debug(f"  段落[{idx}] ✓ 识别为章节标题: {text[:40]}...")
                else:
                    logger.debug(f"  段落[{idx}] 继续检查: {text[:40]}...")
        
        # 跳过摘要、关键词
        is_exclude = False
        for keyword in EXCLUDE_SECTIONS:
            if keyword in text:
                is_exclude = True
                break
        
        if is_exclude:
            continue
        
        # 检查是否为章节标题
        for pattern in chapter_patterns:
            if re.match(pattern, text):
                start_idx = idx
                if debug:
                    logger.debug(f"\n✓ 正文从第 {idx} 段开始: '{text[:50]}...'")
                break
        
        if start_idx > 0:
            break
    else:
        if debug:
            logger.debug(f"\n未找到匹配的章节标题，正文从第 0 段开始")
            logger.debug(f"已扫描 {scanned} 个非空段落")
    
    if debug:
        logger.debug(f"\n最终确定正文范围: 第 {start_idx} 段 到 第 {end_idx - 1} 段")
        logger.debug(f"正文共包含 {end_idx - start_idx} 个段落")
    
    return start_idx, end_idx


def check_citations(doc, reference_numbers, references_header_idx=None, content_paragraphs=None, debug=False):
    """
    检测引用情况：检查参考文献是否被正文引用
    
    参数:
        doc: Word文档对象
        reference_numbers: 参考文献序号列表（从结构检测获取）
        references_header_idx: 参考文献标题段落索引（用于确定正文范围）
        content_paragraphs: 参考文献内容段落列表（用于显示具体内容）
        debug: 是否输出调试日志
    
    返回:
        dict: 引用检测报告
    """
    report = {
        'ok': True,
        'messages': [],
        'total_citations': 0,        # 正文总共引用的次数
        'total_references': 0,       # 参考文献总条数
        'unreferenced': [],          # 未被引用的文献序号
        'unreferenced_details': [],  # 未被引用的文献详情（包含序号和内容）
        'invalid_citations': [],     # 引用了不存在的序号
        'cited_count': 0,            # 被引用的文献数量
    }
    
    # 内容段落列表，用于显示未被引用文献的具体内容
    if content_paragraphs is None:
        content_paragraphs = []
    
    if debug:
        logger.debug("\n" + "=" * 80)
        logger.debug("【引用检测】开始分析...")
        logger.debug("=" * 80)
    
    # 1. 获取正文范围
    body_start, body_end = find_body_range(doc, references_header_idx, debug=debug)
    
    if debug:
        logger.debug(f"正文范围: 第 {body_start} 段 到 第 {body_end - 1} 段")
    
    # 2. 提取正文中的所有上标引用
    all_citations = set()
    
    if debug:
        logger.debug("\n--- 提取正文中的上标引用 ---")
    
    for idx in range(body_start, body_end):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
            continue
        
        # 检查段落中是否有上标引用
        para_citations = extract_superscript_citations(para, debug=debug)
        
        if para_citations:
            all_citations.update(para_citations)
            if debug:
                logger.debug(f"  段落 {idx}: 检测到上标引用 {para_citations}, 内容: {text[:40]}...")
    
    report['total_citations'] = len(all_citations)
    
    if debug:
        logger.debug(f"\n正文中共检测到 {len(all_citations)} 个上标引用")
        logger.debug(f"引用的序号: {sorted(all_citations)}")
    
    # 3. 获取参考文献序号列表（排除自动编号-1）
    # 如果全是自动编号（-1），则生成虚拟序号 1,2,3... 用于比对
    auto_count = sum(1 for num in reference_numbers if num == -1 or num is None)
    if auto_count > 0 and all(num == -1 or num is None for num in reference_numbers):
        # 全是自动编号，生成虚拟序号
        valid_ref_numbers = list(range(1, len(reference_numbers) + 1))
        if debug:
            logger.debug(f"参考文献全部为自动编号，生成虚拟序号: {valid_ref_numbers}")
    else:
        # 过滤掉 None 和 -1（自动编号），只保留有实际数字的序号
        valid_ref_numbers = [num for num in reference_numbers if num and num > 0]
    
    report['total_references'] = len(valid_ref_numbers)
    
    if debug:
        logger.debug(f"\n参考文献共 {len(valid_ref_numbers)} 条")
        logger.debug(f"参考文献序号: {valid_ref_numbers}")
    
    # 4. 比对分析
    
    # 找出未被引用的文献
    if valid_ref_numbers:
        ref_set = set(valid_ref_numbers)
        unreferenced = ref_set - all_citations
        report['unreferenced'] = sorted(unreferenced)
        
        # 构建序号到内容的映射（只对自动编号有效）
        # 如果是自动编号，序号是虚拟的 1,2,3...，内容对应 content_paragraphs 的顺序
        is_auto_numbered = (len(reference_numbers) > 0 and all(num == -1 or num is None for num in reference_numbers))
        
        # 记录未被引用文献的详情
        for idx, ref_num in enumerate(valid_ref_numbers):
            if ref_num in unreferenced:
                # 获取文献内容
                if is_auto_numbered:
                    # 自动编号：序号是虚拟的，内容按索引获取
                    ref_idx = ref_num - 1  # 虚拟序号从1开始
                else:
                    # 手动编号：需要找到对应实际序号的位置
                    try:
                        ref_idx = reference_numbers.index(ref_num)
                    except ValueError:
                        ref_idx = None
                
                if ref_idx is not None and ref_idx < len(content_paragraphs):
                    content = content_paragraphs[ref_idx].text.strip()[:80]  # 截取前80字符
                else:
                    content = "(无法获取内容)"
                
                report['unreferenced_details'].append({
                    'number': ref_num,
                    'content': content
                })
        
        if debug:
            if unreferenced:
                logger.debug(f"\n未被引用的文献: {report['unreferenced']}")
                for detail in report['unreferenced_details']:
                    logger.debug(f"  [{detail['number']}] {detail['content']}...")
            else:
                logger.debug("\n所有文献都被引用了")
    
    # 找出引用了不存在的序号
    if all_citations and valid_ref_numbers:
        ref_set = set(valid_ref_numbers)
        invalid_refs = all_citations - ref_set
        report['invalid_citations'] = sorted(invalid_refs)
        
        if debug:
            if invalid_refs:
                logger.debug(f"引用了不存在的序号: {report['invalid_citations']}")
            else:
                logger.debug("没有引用不存在的序号")
    
    # 5. 生成报告消息
    if report['unreferenced']:
        report['ok'] = False
        if len(report['unreferenced']) <= 10:
            # 构建详细消息，包含序号和内容
            details = []
            for detail in report['unreferenced_details']:
                details.append(f"[{detail['number']}] {detail['content']}...")
            msg = f"检测到 {len(report['unreferenced'])} 条文献未被正文引用:\n" + "\n".join(f"  {d}" for d in details)
        else:
            msg = f"检测到 {len(report['unreferenced'])} 条文献未被正文引用"
        report['messages'].append(msg)
    
    if report['invalid_citations']:
        report['ok'] = False
        if len(report['invalid_citations']) <= 10:
            msg = f"正文引用了 {len(report['invalid_citations'])} 个不存在的序号: {report['invalid_citations']}"
        else:
            msg = f"正文引用了 {len(report['invalid_citations'])} 个不存在的序号"
        report['messages'].append(msg)
    
    if not report['unreferenced'] and not report['invalid_citations']:
        if report['total_citations'] > 0:
            report['messages'].append(f"引用检测通过，共引用 {report['total_citations']} 次")
        else:
            report['ok'] = False
            report['messages'].append("未在正文中检测到任何引用")
    
    if debug:
        logger.debug("\n--- 引用检测结果 ---")
        logger.debug(f"状态: {'通过' if report['ok'] else '失败'}")
        for msg in report['messages']:
            logger.debug(f"  - {msg}")
    
    return report


# ---------- 主检测函数 ----------
def check_references_with_template(doc_path, template_identifier, skip_checks=None, debug=False):
    """
    主检查函数：检查参考文献格式
    参数:
        doc_path: 文档路径
        template_identifier: 模板标识符
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
        debug: 是否输出详细调试日志（默认False）
    """
    # 设置全局跳过检测项配置
    global _skip_checks_config
    _skip_checks_config = skip_checks or []
    
    tpl = load_template(template_identifier)
    doc = Document(doc_path)
    
    # 执行各项检查（传入debug参数）
    structure_report = check_references_structure(doc, tpl, debug=debug)
    
    header_format_report = {'ok': True, 'messages': []}
    content_format_report = {'ok': True, 'messages': []}
    citation_report = {'ok': True, 'messages': []}  # 引用检测报告
    
    if structure_report.get('header_paragraph'):
        header_format_report = check_reference_header_format(structure_report['header_paragraph'], tpl)
    
    if structure_report.get('content_paragraphs'):
        content_format_report = check_reference_content_format(structure_report['content_paragraphs'], tpl)
    
    # 引用检测
    if structure_report.get('header_paragraph') is not None:
        # 获取参考文献标题的索引
        ref_header_idx = None
        for idx, para in enumerate(doc.paragraphs):
            if para == structure_report.get('header_paragraph'):
                ref_header_idx = idx
                break
        
        # 获取参考文献序号列表和内容段落
        reference_numbers = structure_report.get('reference_numbers', [])
        content_paragraphs = structure_report.get('content_paragraphs', [])
        
        # 执行引用检测
        citation_report = check_citations(
            doc, 
            reference_numbers, 
            references_header_idx=ref_header_idx,
            content_paragraphs=content_paragraphs,
            debug=debug
        )
    
    # 组装报告
    report = {
        'structure': structure_report,
        'header_format': header_format_report,
        'content_format': content_format_report,
        'citation': citation_report,  # 添加引用检测结果
        'summary': []
    }
    
    # 生成总结
    all_ok = (structure_report['ok'] and header_format_report['ok'] and content_format_report['ok'] and citation_report['ok'])
    summary_tpl = tpl.get('messages', {}).get('summary_overall')
    if summary_tpl:
        try:
            report['summary'].append(summary_tpl.format(ok="通过" if all_ok else "失败"))
        except Exception:
            report['summary'].append(str(summary_tpl))
    
    return report

# ---------- 报告输出 ----------
def print_references_report(report):
    """打印参考文献检查报告"""
    print("=== 参考文献检查报告 ===")
    
    sections = [
        ('structure', '结构检测'),
        ('header_format', '标题格式'),
        ('content_format', '内容格式'),
        ('citation', '引用检测')
    ]
    
    for sec_key, sec_name in sections:
        info = report.get(sec_key, {})
        print(f"--- {sec_name} ---")
        print(" 状态:", "✓ 通过" if info.get('ok', False) else "✗ 失败")
        for m in info.get('messages', []):
            print("  -", m)
        
        # 额外显示引用检测的详细统计信息
        if sec_key == 'citation':
            if info.get('total_citations'):
                print(f"  总引用次数: {info.get('total_citations')}")
            if info.get('total_references'):
                print(f"  参考文献总数: {info.get('total_references')}")
            if info.get('unreferenced'):
                print(f"  未被引用的文献: {info.get('unreferenced')}")
            if info.get('invalid_citations'):
                print(f"  无效引用: {info.get('invalid_citations')}")
    
    print("--- 总结 ---")
    for s in report.get('summary', []):
        print(" ", s)

def debug_help():
    print("使用方法:")
    print("  python References_detect.py check <paper.docx> <template>")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == 'check' and len(sys.argv) == 4:
        paper_path = sys.argv[2]
        tpl_id = sys.argv[3]
        if not os.path.isfile(paper_path):
            print(f"论文文件不存在: {paper_path}")
            sys.exit(1)
        try:
            print("=== 开始参考文献格式检查 ===")
            report = check_references_with_template(paper_path, tpl_id)
        except Exception as e:
            print("检查时出错:", e)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        print_references_report(report)
    else:
        debug_help()
        sys.exit(0)
