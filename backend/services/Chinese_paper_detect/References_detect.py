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

# 模块级变量，用于存储当前检测文档的路径
_current_doc_path = None

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

# ---------- 文档默认设置提取函数 ----------

def get_document_default_fonts(doc):
    """
    从文档的默认字符格式中获取字体设置
    
    Word文档的默认字体存储在 styles.xml 的 docDefaults 中
    当用户在文档中未显式设置字体时，会使用这些默认值
    
    返回: {'ascii': str, 'east_asia': str} 或 None
    """
    try:
        # 从文档默认字符格式中读取
        # 路径: w:styles/w:docDefaults/w:rPrDefault/w:rPr/w:rFonts
        # 注意：doc.styles._element 才是 styles.xml 的根元素
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
                logger.debug(f"[文档默认] 从docDefaults读取字体: {result}")
                return result
    except Exception as e:
        logger.debug(f"[文档默认] 从docDefaults读取字体异常: {e}")
    
    return None


def get_theme_fonts(doc_path):
    """
    从Word主题文件中获取默认字体
    
    Word主题文件存储在 word/theme/theme1.xml 中
    包含文档的主题字体方案（majorFont/minorFont）
    
    返回: {'ascii': str, 'east_asia': str} 或 None
    """
    import zipfile
    
    try:
        if not os.path.isfile(doc_path):
            return None
            
        with zipfile.ZipFile(doc_path, 'r') as z:
            try:
                theme_xml = z.read('word/theme/theme1.xml')
            except KeyError:
                # 主题文件不存在
                return None
            
            from lxml import etree
            theme = etree.fromstring(theme_xml)
            
            # 定义命名空间
            ns = {
                'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            }
            
            # 读取 minorFont (正文字体，通常是宋体/Times New Roman)
            minor_font = theme.xpath('//a:minorFont', namespaces=ns)
            if minor_font:
                mf = minor_font[0]
                result = {}
                
                # ea = eastAsia (中文字体)
                ea_font = mf.get('{http://schemas.openxmlformats.org/drawingml/2006/main}ea')
                # latin = 拉丁字体
                latin_font = mf.get('{http://schemas.openxmlformats.org/drawingml/2006/main}latin')
                
                if ea_font:
                    result['east_asia'] = ea_font
                if latin_font:
                    result['ascii'] = latin_font
                
                if result:
                    logger.debug(f"[主题字体] 从theme1.xml读取字体: {result}")
                    return result
    except Exception as e:
        logger.debug(f"[主题字体] 从theme1.xml读取字体异常: {e}")
    
    return None


def get_document_default_indent(doc):
    """
    从文档的默认段落格式中获取缩进设置
    
    Word文档的默认段落格式存储在 styles.xml 的 docDefaults 中
    当用户在文档中未显式设置缩进时，会使用这些默认值
    
    返回: {'first_line_indent': float, 'left_indent': float, 'right_indent': float} 或 None
    """
    try:
        # 从默认段落格式中读取
        # 路径: w:styles/w:docDefaults/w:pPrDefault/w:pPr
        # 注意：doc.styles._element 才是 styles.xml 的根元素
        pPr_defaults = doc.styles._element.xpath(
            '//w:docDefaults/w:pPrDefault/w:pPr'
        )
        if pPr_defaults:
            pPr = pPr_defaults[0]
            ind_nodes = pPr.xpath('.//w:ind', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
            
            if ind_nodes:
                ind = ind_nodes[0]
                result = {}
                
                if ind.get(qn('w:left')):
                    result['left_indent'] = int(ind.get(qn('w:left'))) / 20.0
                
                # 悬挂缩进存储为正值，需要转换为负的首行缩进
                if ind.get(qn('w:hanging')):
                    result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                elif ind.get(qn('w:firstLine')):
                    result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                
                if ind.get(qn('w:right')):
                    result['right_indent'] = int(ind.get(qn('w:right'))) / 20.0
                
                if result:
                    logger.debug(f"[文档默认] 从docDefaults读取缩进: {result}")
                    return result
    except Exception as e:
        logger.debug(f"[文档默认] 从docDefaults读取缩进异常: {e}")
    
    return None


def get_normal_style_indent(doc):
    """
    从Normal（正文）样式中获取缩进设置
    
    Normal样式是Word文档的默认样式，如果用户没有应用任何样式，
    段落会使用Normal样式作为基础。
    
    返回: {'first_line_indent': float, 'left_indent': float, 'right_indent': float} 或 None
    """
    try:
        # 方法1：通过 doc.styles 访问 Normal 样式
        if hasattr(doc, 'styles'):
            try:
                normal_style = doc.styles['Normal']
                if normal_style and hasattr(normal_style, 'element'):
                    ind_nodes = normal_style.element.xpath('.//w:ind')
                    if ind_nodes:
                        ind = ind_nodes[0]
                        result = {}
                        
                        if ind.get(qn('w:left')):
                            result['left_indent'] = int(ind.get(qn('w:left'))) / 20.0
                        if ind.get(qn('w:hanging')):
                            result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                        elif ind.get(qn('w:firstLine')):
                            result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                        if ind.get(qn('w:right')):
                            result['right_indent'] = int(ind.get(qn('w:right'))) / 20.0
                        
                        if result:
                            logger.debug(f"[Normal样式] 从Normal样式读取缩进: {result}")
                            return result
            except Exception as e:
                logger.debug(f"[Normal样式] 访问Normal样式异常: {e}")
        
        # 方法2：直接从XML中查找Normal样式
        try:
            normal_styles = doc.styles._element.xpath(
                '//w:style[@w:styleId="Normal"]//w:ind'
            )
            if normal_styles:
                ind = normal_styles[0]
                result = {}
                
                if ind.get(qn('w:left')):
                    result['left_indent'] = int(ind.get(qn('w:left'))) / 20.0
                if ind.get(qn('w:hanging')):
                    result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                elif ind.get(qn('w:firstLine')):
                    result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                if ind.get(qn('w:right')):
                    result['right_indent'] = int(ind.get(qn('w:right'))) / 20.0
                
                if result:
                    logger.debug(f"[Normal样式] 从XML直接查找Normal样式读取缩进: {result}")
                    return result
        except Exception as e:
            logger.debug(f"[Normal样式] 从XML查找Normal样式异常: {e}")
            
    except Exception as e:
        logger.debug(f"[Normal样式] 获取Normal样式缩进异常: {e}")
    
    return None

# ---------- 字体检测函数 ----------

def get_inherited_style_properties(style, doc, visited_styles=None):
    """
    递归获取样式及其继承链的所有属性
    
    参数:
        style: 当前样式对象
        doc: 文档对象（用于访问样式集合）
        visited_styles: 已访问的样式ID集合（防止循环继承）
    
    返回:
        dict: 包含所有继承属性的字典
    """
    if visited_styles is None:
        visited_styles = set()
    
    # 防止循环继承
    if style and hasattr(style, 'style_id') and style.style_id in visited_styles:
        return {}
    
    if style and hasattr(style, 'style_id'):
        visited_styles.add(style.style_id)
    
    properties = {}
    
    # 如果没有样式，返回空
    if not style:
        return properties
    
    try:
        # 1. 提取字体属性
        if hasattr(style, 'font'):
            font = style.font
            if hasattr(font, 'size') and font.size:
                properties['font_size'] = font.size.pt
            if hasattr(font, 'name') and font.name:
                properties['font_name'] = font.name
            if hasattr(font, 'bold') and font.bold is not None:
                properties['bold'] = font.bold
            if hasattr(font, 'italic') and font.italic is not None:
                properties['italic'] = font.italic
            # 中英文字体
            if hasattr(font, 'east_asia') and font.east_asia and hasattr(font.east_asia, 'name'):
                properties['font_east_asia'] = font.east_asia.name
            if hasattr(font, 'ascii') and font.ascii and hasattr(font.ascii, 'name'):
                properties['font_ascii'] = font.ascii.name
        
        # 2. 提取段落属性
        if hasattr(style, 'paragraph_format'):
            para_fmt = style.paragraph_format
            if hasattr(para_fmt, 'line_spacing') and para_fmt.line_spacing:
                properties['line_spacing'] = para_fmt.line_spacing
                logger.debug(f"[样式继承] 从样式段落格式读取行间距: {para_fmt.line_spacing}")
            if hasattr(para_fmt, 'first_line_indent') and para_fmt.first_line_indent:
                properties['first_line_indent'] = para_fmt.first_line_indent.pt
            if hasattr(para_fmt, 'left_indent') and para_fmt.left_indent:
                properties['left_indent'] = para_fmt.left_indent.pt
            if hasattr(para_fmt, 'right_indent') and para_fmt.right_indent:
                properties['right_indent'] = para_fmt.right_indent.pt
            if hasattr(para_fmt, 'space_before') and para_fmt.space_before:
                properties['space_before'] = para_fmt.space_before.pt
            if hasattr(para_fmt, 'space_after') and para_fmt.space_after:
                properties['space_after'] = para_fmt.space_after.pt
            if hasattr(para_fmt, 'alignment') and para_fmt.alignment is not None:
                properties['alignment'] = para_fmt.alignment

        # 2.5. 尝试从样式XML中提取未暴露的属性
        if hasattr(style, 'element') and style.element is not None:
            try:
                # 2.5.1 字号
                sz_nodes = style.element.xpath('.//w:sz')
                if sz_nodes and sz_nodes[0].get(qn('w:val')):
                    # w:sz的值单位为半磅
                    val = float(sz_nodes[0].get(qn('w:val')))
                    properties.setdefault('font_size', val / 2.0)

                # 2.5.2 字体
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
                    if hansi_font:
                        properties.setdefault('font_name', hansi_font)

                # 2.5.3 缩进
                ind_nodes = style.element.xpath('.//w:ind')
                if ind_nodes:
                    ind = ind_nodes[0]
                    if ind.get(qn('w:left')):
                        properties.setdefault('left_indent', int(ind.get(qn('w:left'))) / 20.0)
                    # 先检查 w:hanging（悬挂缩进），再检查 w:firstLine（首行缩进）
                    if ind.get(qn('w:hanging')):
                        properties.setdefault('first_line_indent', -int(ind.get(qn('w:hanging'))) / 20.0)
                    elif ind.get(qn('w:firstLine')):
                        properties.setdefault('first_line_indent', int(ind.get(qn('w:firstLine'))) / 20.0)
                    if ind.get(qn('w:right')):
                        properties.setdefault('right_indent', int(ind.get(qn('w:right'))) / 20.0)

                # 2.5.4 行间距
                spacing_nodes = style.element.xpath('.//w:spacing')
                if spacing_nodes:
                    spacing = spacing_nodes[0]
                    line_rule = spacing.get(qn('w:lineRule'))
                    if spacing.get(qn('w:line')):
                        line_val = int(spacing.get(qn('w:line')))
                        if line_rule == 'auto':
                            # 自动行间距：line值通常是字体大小的120%作为基准
                            # 例如：12pt字体，单倍行距约14.4pt，存储为1728 twips (14.4*120)
                            # 这里我们简单地将auto模式的值除以240作为近似倍数
                            properties.setdefault('line_spacing', line_val / 240.0)
                            logger.debug(f"[样式继承] 从样式XML读取自动行间距 line={line_val} => {line_val/240.0}")
                        else:
                            # 固定行间距：240 twips = 1.0倍
                            properties.setdefault('line_spacing', line_val / 240.0)
                            logger.debug(f"[样式继承] 从样式XML读取固定行间距 line={line_val} => {line_val/240.0}")
                    if spacing.get(qn('w:before')):
                        properties.setdefault('space_before', int(spacing.get(qn('w:before'))) / 20.0)
                    if spacing.get(qn('w:after')):
                        properties.setdefault('space_after', int(spacing.get(qn('w:after'))) / 20.0)
            except Exception as e:
                logger.debug(f"从样式XML中提取属性异常: {e}")
    
    except Exception as e:
        logger.debug(f"提取样式属性异常: {e}")
    
    # 3. 递归处理父样式
    if hasattr(style, 'base_style') and style.base_style:
        parent_properties = get_inherited_style_properties(style.base_style, doc, visited_styles)
        # 子样式属性覆盖父样式属性
        parent_properties.update(properties)
        properties = parent_properties
    
    return properties

def detect_font_with_inheritance(run, paragraph, doc):
    """
    检测run的字体信息，包含样式继承
    
    返回: (font_size, font_ascii, font_eastasia, is_bold, is_italic, line_spacing, style_based)
    """
    font_size = None
    font_name_ascii = None
    font_name_eastasia = None
    is_bold = None
    is_italic = False
    line_spacing = None
    style_based = False

    # 调试信息收集（用于追踪每一步来源）
    debug_parts = []

    if not run:
        return None, None, None, False, False, None, False

    # 1. 优先使用 run 的直接格式（最精确）
    try:
        if run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)
            debug_parts.append(f"run.font.size={font_size}pt")

        if run.font and run.font.name:
            font_name_ascii = run.font.name
            debug_parts.append(f"run.font.name={font_name_ascii}")

        if hasattr(run.font, 'east_asia') and run.font.east_asia and hasattr(run.font.east_asia, 'name'):
            font_name_eastasia = run.font.east_asia.name
            debug_parts.append(f"run.font.east_asia={font_name_eastasia}")

        if run.font and run.font.bold is not None:
            is_bold = run.font.bold
            debug_parts.append(f"run.font.bold={is_bold}")

        if run.font and run.font.italic is not None:
            is_italic = run.font.italic
            debug_parts.append(f"run.font.italic={is_italic}")
    except Exception:
        debug_parts.append("run.font extraction failed")
    
    # 2. 如果run没有直接设置，检查run的样式
    if font_size is None and hasattr(run, 'style') and run.style:
        inherited_props = get_inherited_style_properties(run.style, doc)
        debug_parts.append(f"run.style inherited: {inherited_props}")
        if 'font_size' in inherited_props:
            font_size = inherited_props['font_size']
            style_based = True
        if 'font_name' in inherited_props and not font_name_ascii:
            font_name_ascii = inherited_props['font_name']
            style_based = True
        if 'font_east_asia' in inherited_props and not font_name_eastasia:
            font_name_eastasia = inherited_props['font_east_asia']
            style_based = True
        if 'bold' in inherited_props and is_bold is None:
            is_bold = inherited_props['bold']
            style_based = True
        if 'italic' in inherited_props and not is_italic:
            is_italic = inherited_props['italic']
            style_based = True
    
    # 3. 如果仍没有，检查段落的样式
    if (font_size is None or not font_name_eastasia) and paragraph and paragraph.style:
        inherited_props = get_inherited_style_properties(paragraph.style, doc)
        debug_parts.append(f"paragraph.style inherited: {inherited_props}")
        if font_size is None and 'font_size' in inherited_props:
            font_size = inherited_props['font_size']
            style_based = True
        if not font_name_ascii and 'font_name' in inherited_props:
            font_name_ascii = inherited_props['font_name']
            style_based = True
        if not font_name_eastasia and 'font_east_asia' in inherited_props:
            font_name_eastasia = inherited_props['font_east_asia']
            style_based = True
        if is_bold is None and 'bold' in inherited_props:
            is_bold = inherited_props['bold']
            style_based = True
        if not is_italic and 'italic' in inherited_props:
            is_italic = inherited_props['italic']
            style_based = True
        
        # 行间距：只有当段落没有直接设置时，才使用样式继承
        if line_spacing is None and 'line_spacing' in inherited_props:
            line_spacing = inherited_props['line_spacing']
            style_based = True

    # 4. 【优先级提升】从run的XML中直接读取字体和大小（直接设置，优先于样式继承）
    xml_font_size = None
    xml_font_ascii = None
    xml_font_eastasia = None
    try:
        if hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                sz_nodes = rpr.xpath('.//w:sz')
                if sz_nodes and sz_nodes[0].get(qn('w:val')):
                    xml_font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                    debug_parts.append(f"xml rPr sz={xml_font_size}pt")

                rfonts = rpr.find(qn('w:rFonts'))
                if rfonts is not None:
                    xml_ascii = rfonts.get(qn('w:ascii'))
                    xml_hansi = rfonts.get(qn('w:hAnsi'))
                    xml_eastasia_val = rfonts.get(qn('w:eastAsia'))

                    if xml_ascii:
                        xml_font_ascii = xml_ascii
                        debug_parts.append(f"xml rFonts ascii={xml_ascii}")
                    if xml_hansi and not xml_font_ascii:
                        xml_font_ascii = xml_hansi
                        debug_parts.append(f"xml rFonts hAnsi={xml_hansi}")
                    if xml_eastasia_val:
                        xml_font_eastasia = xml_eastasia_val
                        debug_parts.append(f"xml rFonts eastAsia={xml_font_eastasia}")
                    xml_eastasia_theme = rfonts.get(qn('w:eastAsiaTheme'))
                    if xml_eastasia_theme:
                        debug_parts.append(f"xml rFonts eastAsiaTheme={xml_eastasia_theme}")
    except Exception as e:
        debug_parts.append(f"xml extraction failed: {e}")

    # 5. 从段落XML中直接读取行间距（直接设置，优先于样式继承）
    direct_line_spacing = None
    if paragraph and hasattr(paragraph, '_element'):
        try:
            pPr = paragraph._element.pPr
            if pPr is not None:
                spacing_nodes = pPr.xpath('.//w:spacing')
                if spacing_nodes:
                    spacing = spacing_nodes[0]
                    line_attr = spacing.get(qn('w:line'))
                    line_rule = spacing.get(qn('w:lineRule'))
                    if line_attr:
                        line_val = float(line_attr)
                        if line_rule == 'auto':
                            direct_line_spacing = line_val / 240.0
                        else:
                            direct_line_spacing = line_val / 240.0
                        logger.debug(f"[XML优先级提升] 从段落XML直接读取行间距 line={line_val} => {direct_line_spacing}")
        except Exception as e:
            logger.debug(f"从段落XML直接读取行间距异常: {e}")

    # 使用直接设置的行间距（优先于样式继承）
    if direct_line_spacing is not None:
        line_spacing = direct_line_spacing
    elif line_spacing is None and paragraph and hasattr(paragraph, 'paragraph_format'):
        try:
            para_fmt = paragraph.paragraph_format
            if hasattr(para_fmt, 'line_spacing') and para_fmt.line_spacing:
                line_spacing = float(para_fmt.line_spacing)
                style_based = True
                logger.debug(f"[段落格式] 从段落格式读取行间距: {line_spacing}")
        except Exception as e:
            logger.debug(f"从段落格式读取行间距异常: {e}")

    # 6. 【段落样式检查 — XML 已在此之前提取，段落样式作为后备】
    # 如果 XML 没有直接提取到字体/大小，则使用段落样式继承作为后备
    if (font_size is None or not font_name_eastasia) and paragraph and paragraph.style:
        inherited_props = get_inherited_style_properties(paragraph.style, doc)
        debug_parts.append(f"paragraph.style fallback: {inherited_props}")
        if font_size is None and 'font_size' in inherited_props:
            font_size = inherited_props['font_size']
            style_based = True
        if not font_name_ascii and 'font_name' in inherited_props:
            font_name_ascii = inherited_props['font_name']
            style_based = True
        if not font_name_eastasia and 'font_east_asia' in inherited_props:
            font_name_eastasia = inherited_props['font_east_asia']
            style_based = True
        if is_bold is None and 'bold' in inherited_props:
            is_bold = inherited_props['bold']
            style_based = True
        if not is_italic and 'italic' in inherited_props:
            is_italic = inherited_props['italic']
            style_based = True
        if line_spacing is None and 'line_spacing' in inherited_props:
            line_spacing = inherited_props['line_spacing']
            style_based = True

    # 7. 【XML 直接设置覆盖段落样式继承】
    # 这是核心改动：XML 中直接存在字体/大小，则优先于样式继承的值
    if xml_font_size is not None:
        font_size = xml_font_size
        style_based = False
        debug_parts.append(f"xml覆盖样式继承: font_size={font_size}")
    if xml_font_ascii and not font_name_ascii:
        font_name_ascii = xml_font_ascii
        style_based = False
        debug_parts.append(f"xml覆盖样式继承: font_ascii={font_name_ascii}")
    if xml_font_eastasia:
        font_name_eastasia = xml_font_eastasia
        style_based = False
        debug_parts.append(f"xml覆盖样式继承: font_eastasia={font_name_eastasia}")

    # 8. 从文档默认设置中获取字体
    # 当用户使用Word默认字体时，字体信息存储在styles.xml的docDefaults中
    if not font_name_ascii or not font_name_eastasia:
        try:
            doc_defaults = get_document_default_fonts(doc)
            if doc_defaults:
                if not font_name_ascii:
                    if 'ascii' in doc_defaults:
                        font_name_ascii = doc_defaults['ascii']
                        debug_parts.append(f"docDefaults字体ascii={font_name_ascii}")
                    elif 'hAnsi' in doc_defaults:
                        font_name_ascii = doc_defaults['hAnsi']
                        debug_parts.append(f"docDefaults字体hAnsi={font_name_ascii}")
                if not font_name_eastasia:
                    if 'east_asia' in doc_defaults:
                        font_name_eastasia = doc_defaults['east_asia']
                        debug_parts.append(f"docDefaults字体eastAsia={font_name_eastasia}")
        except Exception as e:
            debug_parts.append(f"docDefaults字体提取异常: {e}")
    
    # 9. 从主题文件中获取字体
    # Word主题文件存储默认字体方案，如果docDefaults也没有，就从主题文件读取
    if not font_name_ascii or not font_name_eastasia:
        try:
            # 获取文档路径
            doc_path = None
            if doc and hasattr(doc, '_part') and hasattr(doc._part, 'package'):
                # 尝试从doc对象获取路径
                pass
            
            # 如果doc_path可用，尝试读取主题字体
            if doc_path:
                theme_fonts = get_theme_fonts(doc_path)
                if theme_fonts:
                    if not font_name_ascii:
                        font_name_ascii = theme_fonts.get('ascii')
                        if font_name_ascii:
                            debug_parts.append(f"theme字体ascii={font_name_ascii}")
                    if not font_name_eastasia:
                        font_name_eastasia = theme_fonts.get('east_asia')
                        if font_name_eastasia:
                            debug_parts.append(f"theme字体eastAsia={font_name_eastasia}")
        except Exception as e:
            debug_parts.append(f"theme字体提取异常: {e}")
    
    # 不再设置默认值，让调用方处理 None 的情况
    # 但需要把空字符串视为未检测到（避免 None/'' 导致检查逻辑不一致）
    if font_name_ascii is not None and str(font_name_ascii).strip() == "":
        font_name_ascii = None
    if font_name_eastasia is not None and str(font_name_eastasia).strip() == "":
        font_name_eastasia = None

    is_bold = bool(is_bold) if is_bold is not None else False
    is_italic = bool(is_italic)

    if debug_parts:
        logger.debug(
            f"[字体检测 debug] font_size={font_size} ascii={font_name_ascii} "
            f"eastasia={font_name_eastasia} bold={is_bold} italic={is_italic} "
            f"line_spacing={line_spacing} style_based={style_based} -> "
            + "; ".join(debug_parts)
        )

    return font_size, font_name_ascii, font_name_eastasia, is_bold, is_italic, line_spacing, style_based

def detect_font_for_run(run, paragraph=None, doc=None):
    """
    检测run的字体信息，包括中英文字体（增强版：支持样式继承）
    返回: (font_size, font_ascii, font_eastasia, is_bold, is_italic, line_spacing, style_based)
    style_based: 是否有格式从样式继承（行间距等）
    """
    # 如果外部传入doc则优先使用
    if doc is None:
        if paragraph and hasattr(paragraph, '_document'):
            doc = paragraph._document
        elif hasattr(run, '_parent') and hasattr(run._parent, '_document'):
            doc = run._parent._document

    if doc:
        return detect_font_with_inheritance(run, paragraph, doc)
    else:
        # 后备方案：使用原有逻辑
        return detect_font_for_run_legacy(run, paragraph)

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
    """检测段落对齐方式（增强版：支持样式继承）"""
    # 获取文档对象
    doc = None
    if hasattr(paragraph, '_document'):
        doc = paragraph._document
    
    if doc:
        props, style_based = detect_paragraph_format_with_inheritance(paragraph, doc)
        if 'alignment' in props:
            return int(props['alignment'])
    else:
        # 后备方案：使用原有逻辑
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
    """检测段落缩进（返回pt值）（增强版：支持样式继承）
    
    返回: (first_line_indent, left_indent, right_indent, style_based)
    style_based: 是否从样式继承格式
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 获取文档对象
    doc = None
    if hasattr(paragraph, '_document'):
        doc = paragraph._document
    
    if doc:
        props, style_based = detect_paragraph_format_with_inheritance(paragraph, doc)
        first_line_indent = props.get('first_line_indent')
        left_indent = props.get('left_indent')
        right_indent = props.get('right_indent')
        
        # 调试日志
        logger.debug(f"[缩进调试] 使用样式继承检测，最终结果: first_line_indent={first_line_indent}, left_indent={left_indent}, right_indent={right_indent}, style_based={style_based}")
        
        return first_line_indent, left_indent, right_indent, style_based
    else:
        # 后备方案：使用原有逻辑 + XML直接读取
        logger.debug(f"[缩进调试] 使用后备方案检测")
        style_based = False
        
        # 首先尝试从段落XML直接读取（即使没有doc对象）
        xml_first_line = None
        xml_left = None
        xml_right = None
        
        try:
            if hasattr(paragraph, '_element') and paragraph._element.pPr is not None:
                pPr = paragraph._element.pPr
                logger.debug(f"[缩进调试] 尝试从段落XML读取缩进")
                
                # 缩进
                ind_nodes = pPr.xpath('.//w:ind')
                if ind_nodes:
                    ind = ind_nodes[0]
                    logger.debug(f"[缩进调试] 找到XML缩进节点: {ind.attrib}")
                    if ind.get(qn('w:left')):
                        xml_left = int(ind.get(qn('w:left'))) / 20.0
                        logger.debug(f"[缩进调试] XML左缩进: {xml_left}pt")
                    # 先检查 w:hanging（悬挂缩进），再检查 w:firstLine（首行缩进）
                    # 悬挂缩进存储为正值，需要转换为负的首行缩进
                    if ind.get(qn('w:hanging')):
                        xml_first_line = -int(ind.get(qn('w:hanging'))) / 20.0
                        logger.debug(f"[缩进调试] XML悬挂缩进(转为首行): {xml_first_line}pt")
                    elif ind.get(qn('w:firstLine')):
                        xml_first_line = int(ind.get(qn('w:firstLine'))) / 20.0
                        logger.debug(f"[缩进调试] XML首行缩进: {xml_first_line}pt")
                    if ind.get(qn('w:right')):
                        xml_right = int(ind.get(qn('w:right'))) / 20.0
                        logger.debug(f"[缩进调试] XML右缩进: {xml_right}pt")
                else:
                    logger.debug(f"[缩进调试] 未找到XML缩进节点")
        except Exception as e:
            logger.debug(f"[缩进调试] 从XML读取缩进异常: {e}")
        
        # 尝试从样式继承链递归读取（即使没有doc对象）
        style_inherited_first = None
        style_inherited_left = None
        style_inherited_right = None
        
        try:
            if paragraph.style:
                logger.debug(f"[缩进调试] 尝试从样式继承读取缩进")
                inherited_props = get_inherited_style_properties_fallback(paragraph.style)
                style_inherited_first = inherited_props.get('first_line_indent')
                style_inherited_left = inherited_props.get('left_indent')
                style_inherited_right = inherited_props.get('right_indent')
                if style_inherited_first is not None or style_inherited_left is not None or style_inherited_right is not None:
                    logger.debug(f"[缩进调试] 样式继承结果: first={style_inherited_first}, left={style_inherited_left}, right={style_inherited_right}")
                else:
                    logger.debug(f"[缩进调试] 样式继承未找到缩进信息")
        except Exception as e:
            logger.debug(f"[缩进调试] 样式继承异常: {e}")
        
        # 新增：尝试从文档默认设置获取缩进（即使doc对象不可用）
        default_first = None
        default_left = None
        default_right = None
        
        # 尝试通过段落获取文档对象
        doc_for_default = None
        if hasattr(paragraph, '_document'):
            doc_for_default = paragraph._document
        
        if doc_for_default is None:
            # 尝试从段落所属的文档树中获取
            try:
                if hasattr(paragraph, '_element') and hasattr(paragraph._element, 'getparent'):
                    parent = paragraph._element.getparent()
                    while parent is not None:
                        if hasattr(parent, 'tag') and 'document' in str(parent.tag).lower():
                            # 找到文档元素，尝试获取文档对象
                            # 需要重新打开文档来获取样式
                            pass
                        parent = hasattr(parent, 'getparent') and parent.getparent()
            except Exception:
                pass
        
        if doc_for_default is None:
            # 无法获取文档对象时，尝试从主题文件直接读取
            # 这个信息对所有段落都是相同的，属于文档级别设置
            try:
                # 尝试从 Normal 样式中获取（通过段落自身的样式）
                if paragraph.style:
                    normal_indent = get_normal_style_indent_from_style(paragraph.style)
                    if normal_indent:
                        default_first = normal_indent.get('first_line_indent')
                        default_left = normal_indent.get('left_indent')
                        default_right = normal_indent.get('right_indent')
                        if default_first is not None or default_left is not None or default_right is not None:
                            logger.debug(f"[缩进调试] 从Normal样式读取默认缩进: first={default_first}, left={default_left}, right={default_right}")
            except Exception as e:
                logger.debug(f"[缩进调试] 从Normal样式读取默认缩进异常: {e}")
        
        # 新增：尝试从编号列表（numbering）获取缩进
        num_first = None
        num_left = None
        num_right = None
        
        try:
            has_element = hasattr(paragraph, '_element')
            has_pPr = has_element and paragraph._element.pPr is not None
            logger.debug(f"[编号列表-debug] has_element={has_element}, has_pPr={has_pPr}")
            
            if has_element and paragraph._element.pPr is not None:
                pPr = paragraph._element.pPr
                numPr_nodes = pPr.xpath('.//w:numPr')
                logger.debug(f"[编号列表-debug] numPr_nodes count={len(numPr_nodes)}")
                if numPr_nodes:
                    numPr = numPr_nodes[0]
                    # numPr 节点结构：<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>
                    # 属性在子元素中，不是在 numPr 本身
                    ilvl_node = numPr.find(qn('w:ilvl'))
                    numId_node = numPr.find(qn('w:numId'))
                    
                    if ilvl_node is not None:
                        ilvl = ilvl_node.get(qn('w:val'))
                    else:
                        ilvl = None
                    
                    if numId_node is not None:
                        numId = numId_node.get(qn('w:val'))
                    else:
                        numId = None
                    
                    logger.debug(f"[编号列表] 段落有numPr，子元素 ilvl={ilvl}, numId={numId}")
                    if numId:
                        logger.debug(f"[编号列表] 段落使用编号，numId={numId}, ilvl={ilvl}")
                        # 尝试从编号列表 XML 中读取缩进
                        # 先打印 document 的可用属性
                        if hasattr(paragraph, '_document'):
                            doc_attrs = [a for a in dir(paragraph._document) if not a.startswith('__')]
                            logger.debug(f"[编号列表] document属性: {doc_attrs[:15]}")
                        num_indent = get_numbering_indent_from_paragraph(paragraph)
                        if num_indent:
                            num_first = num_indent.get('first_line_indent')
                            num_left = num_indent.get('left_indent')
                            num_right = num_indent.get('right_indent')
                            if num_first is not None or num_left is not None:
                                logger.debug(f"[编号列表] 从编号XML读取缩进: first={num_first}, left={num_left}, right={num_right}")
                        else:
                            logger.debug(f"[编号列表] 未能从编号XML读取缩进")
                else:
                    logger.debug(f"[编号列表] 段落没有numPr节点（可能使用主题编号或无编号）")
            else:
                logger.debug(f"[编号列表] 段落没有pPr元素")
        except Exception as e:
            logger.debug(f"[编号列表] 从编号列表读取缩进异常: {e}")
        
        try:
            fmt = paragraph.paragraph_format
            
            # 先尝试从样式中获取缩进信息（包括样式继承）
            style_first_line = None
            style_left = None
            style_right = None
            
            # 1. 直接样式
            try:
                if paragraph.style:
                    style_fmt = paragraph.style.paragraph_format
                    if style_fmt:
                        style_first_line = style_fmt.first_line_indent.pt if style_fmt.first_line_indent else None
                        style_left = style_fmt.left_indent.pt if style_fmt.left_indent else None
                        style_right = style_fmt.right_indent.pt if style_fmt.right_indent else None
            except Exception:
                pass
            
            # 2. 样式继承追溯（与字体/行距保持一致）
            try:
                if paragraph.style:
                    # 尝试进行样式继承追溯，即使没有完整的doc对象
                    inherited_props = get_inherited_style_properties(paragraph.style, None)  # 传递None作为doc
                    if 'first_line_indent' in inherited_props and style_first_line is None:
                        style_first_line = inherited_props['first_line_indent']
                        logger.debug(f"[缩进调试] 从样式继承获取首行缩进: {style_first_line}")
                    if 'left_indent' in inherited_props and style_left is None:
                        style_left = inherited_props['left_indent']
                        logger.debug(f"[缩进调试] 从样式继承获取左缩进: {style_left}")
                    if 'right_indent' in inherited_props and style_right is None:
                        style_right = inherited_props['right_indent']
                        logger.debug(f"[缩进调试] 从样式继承获取右缩进: {style_right}")
            except Exception as e:
                logger.debug(f"[缩进调试] 样式继承追溯异常: {e}")
            
            # 检查段落格式的直接属性
            try:
                direct_first_line = fmt.first_line_indent.pt if fmt.first_line_indent else None
            except Exception as e:
                logger.debug(f"读取首行缩进异常: {e}")
                direct_first_line = None
            
            try:
                direct_left = fmt.left_indent.pt if fmt.left_indent else None
            except Exception as e:
                logger.debug(f"读取左缩进异常: {e}")
                direct_left = None
            
            try:
                direct_right = fmt.right_indent.pt if fmt.right_indent else None
            except Exception as e:
                logger.debug(f"读取右缩进异常: {e}")
                direct_right = None
            
            # 调试日志：区分"手动设0"和"提取不到"
            style_name = paragraph.style.name if paragraph.style else "无样式"
            logger.debug(f"[缩进调试] 段落样式: {style_name}")
            logger.debug(f"[缩进调试] 直接格式: direct_first={direct_first_line}, direct_left={direct_left}, direct_right={direct_right}")
            logger.debug(f"[缩进调试] 样式格式: style_first={style_first_line}, style_left={style_left}, style_right={style_right}")
            logger.debug(f"[缩进调试] XML格式: xml_first={xml_first_line}, xml_left={xml_left}, xml_right={xml_right}")
            logger.debug(f"[缩进调试] 样式继承: inherited_first={style_inherited_first}, inherited_left={style_inherited_left}, inherited_right={style_inherited_right}")
            logger.debug(f"[缩进调试] 默认设置: default_first={default_first}, default_left={default_left}, default_right={default_right}")
            logger.debug(f"[缩进调试] 编号列表: num_first={num_first}, num_left={num_left}, num_right={num_right}")
            
            # 优先级：直接格式 > 编号列表 > XML直接设置 > 样式继承 > 样式格式 > 默认设置
            # 编号列表优先于XML直接设置，因为对于自动编号的段落，编号定义的缩进才是实际渲染的缩进
            first_from_style = False
            left_from_style = False
            
            if direct_first_line is not None:
                first_line_indent = direct_first_line
                first_from_style = False
                logger.debug(f"[缩进调试] 使用直接格式首行缩进: {first_line_indent}")
            elif num_first is not None:
                first_line_indent = num_first
                first_from_style = True
                logger.debug(f"[缩进调试] 使用编号列表首行缩进: {first_line_indent}")
            elif xml_first_line is not None:
                first_line_indent = xml_first_line
                first_from_style = False
                logger.debug(f"[缩进调试] 使用XML首行缩进: {first_line_indent}")
            elif style_inherited_first is not None:
                first_line_indent = style_inherited_first
                first_from_style = True
                logger.debug(f"[缩进调试] 使用样式继承首行缩进: {first_line_indent}")
            elif style_first_line is not None:
                first_line_indent = style_first_line
                first_from_style = True
            elif default_first is not None:
                first_line_indent = default_first
                first_from_style = True
                logger.debug(f"[缩进调试] 使用默认设置首行缩进: {first_line_indent}")
            else:
                first_line_indent = None  # 读不到值，返回 None
                first_from_style = False
                
            if direct_left is not None:
                left_indent = direct_left
                left_from_style = False
                logger.debug(f"[缩进调试] 使用直接格式左缩进: {left_indent}")
            elif num_left is not None:
                left_indent = num_left
                left_from_style = True
                logger.debug(f"[缩进调试] 使用编号列表左缩进: {left_indent}")
            elif xml_left is not None:
                left_indent = xml_left
                left_from_style = False
                logger.debug(f"[缩进调试] 使用XML左缩进: {left_indent}")
            elif style_inherited_left is not None:
                left_indent = style_inherited_left
                left_from_style = True
                logger.debug(f"[缩进调试] 使用样式继承左缩进: {left_indent}")
            elif style_left is not None:
                left_indent = style_left
                left_from_style = True
            elif default_left is not None:
                left_indent = default_left
                left_from_style = True
                logger.debug(f"[缩进调试] 使用默认设置左缩进: {left_indent}")
            else:
                left_indent = None  # 读不到值，返回 None
                left_from_style = False
            
            # 只要任何一个值来自样式，就设置 style_based = True
            style_based = first_from_style or left_from_style
                
            if xml_right is not None:
                right_indent = xml_right
                logger.debug(f"[缩进调试] 使用XML右缩进: {right_indent}")
            elif direct_right is not None:
                right_indent = direct_right
            elif style_inherited_right is not None:
                right_indent = style_inherited_right
                logger.debug(f"[缩进调试] 使用样式继承右缩进: {right_indent}")
            elif style_right is not None:
                right_indent = style_right
            elif default_right is not None:
                right_indent = default_right
                logger.debug(f"[缩进调试] 使用默认设置右缩进: {right_indent}")
            else:
                right_indent = None  # 读不到值，返回 None
            
            # 调试日志
            logger.debug(f"[缩进调试] 最终结果: first_line_indent={first_line_indent}, left_indent={left_indent}, right_indent={right_indent}, style_based={style_based}")
            
            return first_line_indent, left_indent, right_indent, style_based
        except Exception as e:
            logger.debug(f"[缩进调试] 后备方案异常: {e}")
            return None, None, None, False

def pt_to_chars(pt_value, font_size_pt=12):
    """将pt值转换为字符数"""
    if pt_value == 0:
        return 0
    return round(pt_value / font_size_pt, 1)

def cm_to_pt(cm_value):
    """厘米转换为pt"""
    return cm_value * 28.35

def get_inherited_style_properties_fallback(style, visited_styles=None):
    """
    后备方案的样式继承检测（不需要doc对象）
    递归获取样式及其继承链的缩进属性
    """
    if visited_styles is None:
        visited_styles = set()
    
    # 防止循环继承
    if style and hasattr(style, 'style_id') and style.style_id in visited_styles:
        return {}
    
    if style and hasattr(style, 'style_id'):
        visited_styles.add(style.style_id)
    
    properties = {}
    
    # 如果没有样式，返回空
    if not style:
        return properties
    
    try:
        # 1. 提取段落属性（只处理缩进）
        if hasattr(style, 'paragraph_format'):
            para_fmt = style.paragraph_format
            if hasattr(para_fmt, 'first_line_indent') and para_fmt.first_line_indent:
                properties['first_line_indent'] = para_fmt.first_line_indent.pt
            if hasattr(para_fmt, 'left_indent') and para_fmt.left_indent:
                properties['left_indent'] = para_fmt.left_indent.pt
            if hasattr(para_fmt, 'right_indent') and para_fmt.right_indent:
                properties['right_indent'] = para_fmt.right_indent.pt
            if hasattr(para_fmt, 'line_spacing') and para_fmt.line_spacing:
                properties['line_spacing'] = para_fmt.line_spacing
        
        # 2. 从样式XML中提取缩进属性
        if hasattr(style, 'element') and style.element is not None:
            try:
                # 缩进
                ind_nodes = style.element.xpath('.//w:ind')
                if ind_nodes:
                    ind = ind_nodes[0]
                    if ind.get(qn('w:left')):
                        properties.setdefault('left_indent', int(ind.get(qn('w:left'))) / 20.0)
                    # 先检查 w:hanging（悬挂缩进），再检查 w:firstLine（首行缩进）
                    if ind.get(qn('w:hanging')):
                        properties.setdefault('first_line_indent', -int(ind.get(qn('w:hanging'))) / 20.0)
                    elif ind.get(qn('w:firstLine')):
                        properties.setdefault('first_line_indent', int(ind.get(qn('w:firstLine'))) / 20.0)
                    if ind.get(qn('w:right')):
                        properties.setdefault('right_indent', int(ind.get(qn('w:right'))) / 20.0)
                
                # 行间距
                spacing_nodes = style.element.xpath('.//w:spacing')
                if spacing_nodes:
                    spacing = spacing_nodes[0]
                    if spacing.get(qn('w:line')):
                        line_val = int(spacing.get(qn('w:line')))
                        properties.setdefault('line_spacing', line_val / 240.0)
            except Exception as e:
                logger.debug(f"从样式XML中提取属性异常: {e}")
    
    except Exception as e:
        logger.debug(f"提取样式属性异常: {e}")
    
    # 3. 递归处理父样式
    if hasattr(style, 'base_style') and style.base_style:
        parent_properties = get_inherited_style_properties_fallback(style.base_style, visited_styles)
        # 子样式属性覆盖父样式属性
        parent_properties.update(properties)
        properties = parent_properties
    
    return properties


def get_normal_style_indent_from_style(style):
    """
    从样式对象中提取 Normal 样式的缩进设置（不需要 doc 对象）
    
    如果传入的样式是 Normal 或其子类，提取缩进信息
    如果不是 Normal，则递归检查父样式
    
    参数:
        style: 样式对象
        visited: 已访问的样式集合（防止循环）
    
    返回: {'first_line_indent': float, 'left_indent': float, 'right_indent': float} 或 None
    """
    if style is None:
        return None
    
    try:
        # 获取样式名称或 ID
        style_name = getattr(style, 'name', None) or getattr(style, 'style_id', None)
        if style_name:
            style_name = str(style_name)
        
        # 检查是否是 Normal 样式
        if style_name and ('Normal' in style_name or '正文' in style_name):
            result = {}
            
            # 从样式 XML 中提取缩进
            if hasattr(style, 'element') and style.element is not None:
                ind_nodes = style.element.xpath('.//w:ind')
                if ind_nodes:
                    ind = ind_nodes[0]
                    if ind.get(qn('w:left')):
                        result['left_indent'] = int(ind.get(qn('w:left'))) / 20.0
                    if ind.get(qn('w:hanging')):
                        result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                    elif ind.get(qn('w:firstLine')):
                        result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                    if ind.get(qn('w:right')):
                        result['right_indent'] = int(ind.get(qn('w:right'))) / 20.0
                    
                    if result:
                        logger.debug(f"[Normal样式] 从样式XML直接提取到缩进: {result}")
                        return result
            
            # 从 paragraph_format 属性中提取
            if hasattr(style, 'paragraph_format') and style.paragraph_format:
                pf = style.paragraph_format
                result = {}
                if hasattr(pf, 'first_line_indent') and pf.first_line_indent:
                    result['first_line_indent'] = float(pf.first_line_indent.pt)
                if hasattr(pf, 'left_indent') and pf.left_indent:
                    result['left_indent'] = float(pf.left_indent.pt)
                if hasattr(pf, 'right_indent') and pf.right_indent:
                    result['right_indent'] = float(pf.right_indent.pt)
                if result:
                    logger.debug(f"[Normal样式] 从paragraph_format提取到缩进: {result}")
                    return result
        
        # 递归检查父样式
        if hasattr(style, 'base_style') and style.base_style:
            return get_normal_style_indent_from_style(style.base_style)
        
    except Exception as e:
        logger.debug(f"[Normal样式] 从样式提取缩进异常: {e}")
    
    return None


def get_numbering_indent_from_paragraph(paragraph):
    """
    从段落中提取编号列表的缩进信息
    
    Word 的自动编号缩进定义在 numbering.xml 中，需要从以下位置读取：
    1. 段落中的 w:numPr (numId 和 ilvl)
    2. 文档 numbering.xml 中的 w:abstractNum 或 w:num
    
    参数:
        paragraph: 段落对象
    
    返回: {'first_line_indent': float, 'left_indent': float, 'right_indent': float} 或 None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    result = {'first_line_indent': None, 'left_indent': None, 'right_indent': None}
    
    try:
        # 获取段落的 XML 元素
        if not hasattr(paragraph, '_element') or paragraph._element is None:
            logger.debug(f"[编号列表] 段落没有 _element 属性")
            return None
        
        pPr = paragraph._element.pPr
        if pPr is None:
            logger.debug(f"[编号列表] 段落没有 pPr 元素")
            return None
        
        # 查找 w:numPr
        numPr_nodes = pPr.xpath('.//w:numPr')
        if not numPr_nodes:
            logger.debug(f"[编号列表] 段落没有 numPr")
            return None
        
        numPr = numPr_nodes[0]
        # numPr 节点结构：<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>
        ilvl_node = numPr.find(qn('w:ilvl'))
        numId_node = numPr.find(qn('w:numId'))
        
        if ilvl_node is not None:
            ilvl = ilvl_node.get(qn('w:val'))
        else:
            ilvl = None
        
        if numId_node is not None:
            numId = numId_node.get(qn('w:val'))
        else:
            numId = None
        
        if not numId:
            logger.debug(f"[编号列表] 段落没有 numId")
            return None
        
        logger.debug(f"[编号列表] 找到编号: numId={numId}, ilvl={ilvl}")
        
        # 尝试从文档获取 numbering
        numbering_xml_bytes = None
        
        # 方法1: 通过 _document.part 获取
        if hasattr(paragraph, '_document'):
            doc = paragraph._document
            if hasattr(doc, 'part'):
                try:
                    numbering_part = doc.part.part_related_by(
                        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering'
                    )
                    if numbering_part:
                        numbering_xml_bytes = numbering_part.blob
                        logger.debug(f"[编号列表] 从 doc.part.part_related_by 获取成功")
                except Exception as e:
                    logger.debug(f"[编号列表] part_related_by 失败: {e}")
            
            # 方法2: 通过 _element 向上遍历获取
            if numbering_xml_bytes is None:
                try:
                    elem = paragraph._element
                    for _ in range(10):
                        if hasattr(elem, 'getparent'):
                            parent = elem.getparent()
                            if parent is None:
                                break
                            # 检查是否是 w:document 或 body
                            if hasattr(parent, 'tag') and parent.tag.endswith('}document'):
                                if hasattr(parent, 'getparent'):
                                    pkg = parent.getparent()
                                    if pkg is not None and hasattr(pkg, 'iter_parts'):
                                        for part in pkg.iter_parts():
                                            if 'numbering' in str(part.name).lower():
                                                numbering_xml_bytes = part.blob
                                                logger.debug(f"[编号列表] 从 iter_parts 获取成功")
                                                break
                                break
                            elem = parent
                except Exception as e:
                    logger.debug(f"[编号列表] 遍历获取失败: {e}")
        
        # 方法3: 直接从 _current_doc_path 读取 numbering.xml
        if numbering_xml_bytes is None:
            global _current_doc_path
            if _current_doc_path and os.path.isfile(_current_doc_path):
                try:
                    import zipfile
                    with zipfile.ZipFile(_current_doc_path, 'r') as zf:
                        if 'word/numbering.xml' in zf.namelist():
                            numbering_xml_bytes = zf.read('word/numbering.xml')
                            logger.debug(f"[编号列表] 从 _current_doc_path 读取成功: {_current_doc_path}")
                except Exception as e:
                    logger.debug(f"[编号列表] 从 _current_doc_path 读取失败: {e}")
        
        if numbering_xml_bytes:
            return parse_numbering_xml(numbering_xml_bytes, numId, ilvl)
        
        logger.debug(f"[编号列表] 无法获取 numbering.xml")
        return None
        
    except Exception as e:
        logger.debug(f"[编号列表] 从段落提取编号缩进异常: {e}")
    
    return None


def get_numbering_indent_from_zip(paragraph):
    """
    直接从 Word 文档的 zip 包中读取 numbering.xml
    
    参数:
        paragraph: 段落对象
    
    返回: {'first_line_indent': float, 'left_indent': float, 'right_indent': float} 或 None
    """
    import logging
    logger = logging.getLogger(__name__)
    import zipfile
    from io import BytesIO
    
    try:
        # 获取段落的 numId 和 ilvl
        if not hasattr(paragraph, '_element') or paragraph._element is None:
            return None
        
        pPr = paragraph._element.pPr
        if pPr is None:
            return None
        
        numPr_nodes = pPr.xpath('.//w:numPr')
        if not numPr_nodes:
            return None
        
        numPr = numPr_nodes[0]
        # numPr 节点结构：<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>
        ilvl_node = numPr.find(qn('w:ilvl'))
        numId_node = numPr.find(qn('w:numId'))
        
        if ilvl_node is not None:
            ilvl = ilvl_node.get(qn('w:val'))
        else:
            ilvl = None
        
        if numId_node is not None:
            numId = numId_node.get(qn('w:val'))
        else:
            numId = None
        
        if not numId:
            return None
        
        # 获取文档路径
        doc_path = None
        if hasattr(paragraph, '_document') and hasattr(paragraph._document, '_part'):
            try:
                doc_path = paragraph._document._part.package.pcloc
            except Exception:
                pass
        
        # 尝试从 _document 属性获取
        if doc_path is None:
            try:
                if hasattr(paragraph, '_element'):
                    elem = paragraph._element
                    # 尝试获取文档的 zip 文件路径
                    if hasattr(elem, 'getparent'):
                        parent = elem.getparent()
                        for _ in range(5):  # 最多向上5层
                            if parent is None:
                                break
                            if hasattr(parent, 'part') and hasattr(parent.part, 'package'):
                                try:
                                    pkg = parent.part.package
                                    if hasattr(pkg, '_zip_path'):
                                        doc_path = pkg._zip_path
                                        break
                                except Exception:
                                    pass
                            if hasattr(parent, 'getparent'):
                                parent = parent.getparent()
                            else:
                                break
            except Exception as e:
                logger.debug(f"[编号列表] 尝试获取文档路径异常: {e}")
        
        if doc_path is None:
            # 尝试从 doc.element 获取
            try:
                if hasattr(paragraph, '_document') and hasattr(paragraph._document, '_element'):
                    doc_elem = paragraph._document._element
                    if hasattr(doc_elem, 'getparent') and hasattr(doc_elem.getparent(), 'part'):
                        pkg = doc_elem.getparent().part.package
                        if hasattr(pkg, '_zip_path'):
                            doc_path = pkg._zip_path
            except Exception:
                pass
        
        if doc_path is None:
            logger.debug(f"[编号列表] 无法获取文档路径")
            return None
        
        # 打开 zip 文件
        if not zipfile.is_zipfile(doc_path):
            logger.debug(f"[编号列表] 文档路径不是有效的 zip 文件: {doc_path}")
            return None
        
        with zipfile.ZipFile(doc_path, 'r') as zf:
            if 'word/numbering.xml' in zf.namelist():
                numbering_xml = zf.read('word/numbering.xml')
                return parse_numbering_xml(numbering_xml, numId, ilvl)
            else:
                logger.debug(f"[编号列表] zip 中没有 numbering.xml")
    
    except Exception as e:
        logger.debug(f"[编号列表] 从zip读取编号缩进异常: {e}")
    
    return None


def parse_numbering_xml(numbering_xml_content, numId, ilvl):
    """
    解析 numbering.xml 并提取指定 numId 的缩进信息
    
    参数:
        numbering_xml_content: numbering.xml 的内容（bytes 或 str）
        numId: 编号 ID
        ilvl: 级别索引
    
    返回: {'first_line_indent': float, 'left_indent': float, 'right_indent': float} 或 None
    """
    import logging
    logger = logging.getLogger(__name__)
    import xml.etree.ElementTree as ET
    
    result = {'first_line_indent': None, 'left_indent': None, 'right_indent': None}
    
    try:
        if isinstance(numbering_xml_content, bytes):
            numbering_xml_content = numbering_xml_content.decode('utf-8')
        
        root = ET.fromstring(numbering_xml_content)
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # 查找 w:num 匹配 numId
        numId_int = int(numId)
        ilvl_int = int(ilvl) if ilvl else 0
        
        # 查找对应的 w:num
        num_node = None
        for num in root.findall('.//w:num', ns):
            if num.get(qn('w:numId')) == str(numId_int):
                num_node = num
                break
        
        if num_node is None:
            # 直接在根目录下查找
            for num in root.findall('w:num', ns):
                if num.get(qn('w:numId')) == str(numId_int):
                    num_node = num
                    break
        
        if num_node is None:
            logger.debug(f"[编号列表] 未找到 numId={numId} 的 w:num")
            return None
        
        # 获取 abstractNumId（它是子元素，不是属性）
        abstractNumId = None
        abstractNumId_node = num_node.find(qn('w:abstractNumId'))
        if abstractNumId_node is not None:
            abstractNumId = abstractNumId_node.get(qn('w:val'))
        
        if not abstractNumId:
            logger.debug(f"[编号列表] numId={numId} 没有 abstractNumId")
            return None
        
        # 查找对应的 w:abstractNum
        abstractNumId_int = int(abstractNumId)
        abstractNum_node = None
        
        for absNum in root.findall('.//w:abstractNum', ns):
            if absNum.get(qn('w:abstractNumId')) == str(abstractNumId_int):
                abstractNum_node = absNum
                break
        
        if abstractNum_node is None:
            for absNum in root.findall('w:abstractNum', ns):
                if absNum.get(qn('w:abstractNumId')) == str(abstractNumId_int):
                    abstractNum_node = absNum
                    break
        
        if abstractNum_node is None:
            logger.debug(f"[编号列表] 未找到 abstractNumId={abstractNumId} 的 w:abstractNum")
            return None
        
        # 从对应级别获取缩进
        # w:lvl 索引从 0 开始
        lvl_nodes = abstractNum_node.findall(f'w:lvl', ns)
        if ilvl_int < len(lvl_nodes):
            lvl = lvl_nodes[ilvl_int]
            
            # 获取 pPr (段落属性)
            pPr = lvl.find('w:pPr', ns)
            if pPr is not None:
                ind = pPr.find('w:ind', ns)
                if ind is not None:
                    if ind.get(qn('w:left')):
                        result['left_indent'] = int(ind.get(qn('w:left'))) / 20.0
                        logger.debug(f"[编号列表] 从abstractNum读取左缩进: {result['left_indent']}")
                    
                    # firstLineChars 可能是相对字符数
                    if ind.get(qn('w:firstLineChars')):
                        firstLineChars = int(ind.get(qn('w:firstLineChars')))
                        # firstLineChars 是 1/10 字符数，需要乘以字体大小
                        # 默认字体大小约为 12pt，所以首行缩进约为 firstLineChars/10 * 12 / 20 英寸 -> pt
                        # 简化处理：firstLineChars * 1.2 / 20 = firstLineChars * 0.06
                        # 但更常见的是 firstLineChars 是 0-100 的值，表示百分比
                        result['first_line_indent'] = firstLineChars  # 保留原始值，稍后转换
                        logger.debug(f"[编号列表] 从abstractNum读取firstLineChars: {firstLineChars}")
                    
                    if ind.get(qn('w:firstLine')):
                        result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                        logger.debug(f"[编号列表] 从abstractNum读取首行缩进: {result['first_line_indent']}")
                    
                    if ind.get(qn('w:hanging')):
                        result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                        logger.debug(f"[编号列表] 从abstractNum读取悬挂缩进: {result['first_line_indent']}")
                    
                    if ind.get(qn('w:right')):
                        result['right_indent'] = int(ind.get(qn('w:right'))) / 20.0
            
            logger.debug(f"[编号列表] 从abstractNum({abstractNumId}) lvl({ilvl_int}) 读取缩进: {result}")
        
        # 检查是否所有值都是 None
        if all(v is None for v in result.values()):
            logger.debug(f"[编号列表] 从编号XML读取的所有缩进值都是None")
            return None
        
        return result
    
    except Exception as e:
        logger.debug(f"[编号列表] 解析numbering.xml异常: {e}")
    
    return None


def detect_paragraph_format_with_inheritance(paragraph, doc):
    """
    检测段落格式，包含样式继承
    
    参数:
        paragraph: 段落对象
        doc: 文档对象（用于访问样式集合）
    
    返回:
        (dict, bool): (属性字典, 是否从样式继承)
    """
    properties = {}
    style_based = False
    
    # 1. 从段落XML直接读取（最高优先级 - 直接设置）
    try:
        if hasattr(paragraph, '_element') and paragraph._element.pPr is not None:
            pPr = paragraph._element.pPr
            logger.debug(f"[段落格式] 开始检查段落XML缩进")
            
            # 1.1 缩进
            ind_nodes = pPr.xpath('.//w:ind')
            if ind_nodes:
                ind = ind_nodes[0]
                logger.debug(f"[段落格式] 找到缩进节点: {ind.attrib}")
                if ind.get(qn('w:left')):
                    properties['left_indent'] = int(ind.get(qn('w:left'))) / 20.0
                    logger.debug(f"[段落直接XML] 读取左缩进: {int(ind.get(qn('w:left')))} twips => {properties['left_indent']}pt")
                # 先检查 w:hanging（悬挂缩进），再检查 w:firstLine（首行缩进）
                if ind.get(qn('w:hanging')):
                    properties['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                    logger.debug(f"[段落直接XML] 读取悬挂缩进(转为首行): {int(ind.get(qn('w:hanging')))} twips => {properties['first_line_indent']}pt")
                elif ind.get(qn('w:firstLine')):
                    properties['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                    logger.debug(f"[段落直接XML] 读取首行缩进: {int(ind.get(qn('w:firstLine')))} twips => {properties['first_line_indent']}pt")
                if ind.get(qn('w:right')):
                    properties['right_indent'] = int(ind.get(qn('w:right'))) / 20.0
                    logger.debug(f"[段落直接XML] 读取右缩进: {int(ind.get(qn('w:right')))} twips => {properties['right_indent']}pt")
            else:
                logger.debug(f"[段落格式] 未找到缩进节点")
            
            # 1.2 行间距
            spacing_nodes = pPr.xpath('.//w:spacing')
            if spacing_nodes:
                spacing = spacing_nodes[0]
                line_rule = spacing.get(qn('w:lineRule'))
                if spacing.get(qn('w:line')):
                    line_val = int(spacing.get(qn('w:line')))
                    if line_rule == 'auto':
                        properties['line_spacing'] = line_val / 240.0
                    else:
                        properties['line_spacing'] = line_val / 240.0
                    logger.debug(f"[段落直接XML] 读取行间距: {line_val} twips => {properties['line_spacing']}倍")
            
            # 1.3 对齐方式
            jc_nodes = pPr.xpath('.//w:jc')
            if jc_nodes:
                val = jc_nodes[0].get(qn('w:val'))
                if val:
                    alignment_map = {'left': 0, 'center': 1, 'right': 2, 'both': 3}
                    properties['alignment'] = alignment_map.get(val, 0)
            
            # 1.4 段前段后间距
            if spacing_nodes:
                spacing = spacing_nodes[0]
                if spacing.get(qn('w:before')):
                    properties['space_before'] = int(spacing.get(qn('w:before'))) / 20.0
                if spacing.get(qn('w:after')):
                    properties['space_after'] = int(spacing.get(qn('w:after'))) / 20.0
        else:
            logger.debug(f"[段落格式] 段落没有pPr或_element")
    except Exception as e:
        logger.debug(f"从段落XML直接读取格式异常: {e}")
    
    # 2. 样式继承（只有当直接格式没有设置时才使用）
    if paragraph.style:
        inherited_props = get_inherited_style_properties(paragraph.style, doc)
        for key in ['first_line_indent', 'left_indent', 'right_indent', 'line_spacing', 'alignment', 'space_before', 'space_after']:
            if key not in properties and key in inherited_props:
                properties[key] = inherited_props[key]
                style_based = True
    
    # 3. 从文档默认段落格式中获取缩进（新增层级）
    # 当用户使用Word默认格式时，缩进信息可能存储在styles.xml的docDefaults中
    if 'first_line_indent' not in properties or 'left_indent' not in properties:
        try:
            default_indent = get_document_default_indent(doc)
            if default_indent:
                if 'first_line_indent' not in properties and 'first_line_indent' in default_indent:
                    properties['first_line_indent'] = default_indent['first_line_indent']
                    style_based = True
                    logger.debug(f"[段落默认] 从docDefaults读取首行缩进: {properties['first_line_indent']}pt")
                if 'left_indent' not in properties and 'left_indent' in default_indent:
                    properties['left_indent'] = default_indent['left_indent']
                    style_based = True
                    logger.debug(f"[段落默认] 从docDefaults读取左缩进: {properties['left_indent']}pt")
                if 'right_indent' not in properties and 'right_indent' in default_indent:
                    properties['right_indent'] = default_indent['right_indent']
                    style_based = True
                    logger.debug(f"[段落默认] 从docDefaults读取右缩进: {properties['right_indent']}pt")
        except Exception as e:
            logger.debug(f"[段落默认] 从docDefaults读取缩进异常: {e}")
    
    # 4. 从Normal样式中获取缩进（新增层级）
    # Normal样式是Word的默认样式，如果段落没有应用任何样式，会使用Normal样式
    if 'first_line_indent' not in properties or 'left_indent' not in properties:
        try:
            normal_indent = get_normal_style_indent(doc)
            if normal_indent:
                if 'first_line_indent' not in properties and 'first_line_indent' in normal_indent:
                    properties['first_line_indent'] = normal_indent['first_line_indent']
                    style_based = True
                    logger.debug(f"[Normal样式] 从Normal样式读取首行缩进: {properties['first_line_indent']}pt")
                if 'left_indent' not in properties and 'left_indent' in normal_indent:
                    properties['left_indent'] = normal_indent['left_indent']
                    style_based = True
                    logger.debug(f"[Normal样式] 从Normal样式读取左缩进: {properties['left_indent']}pt")
                if 'right_indent' not in properties and 'right_indent' in normal_indent:
                    properties['right_indent'] = normal_indent['right_indent']
                    style_based = True
                    logger.debug(f"[Normal样式] 从Normal样式读取右缩进: {properties['right_indent']}pt")
        except Exception as e:
            logger.debug(f"[Normal样式] 从Normal样式读取缩进异常: {e}")
    
    return properties, style_based

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
        return False
    
    # 1. 以 [数字] 开头的，是参考文献条目，不是章节标题
    if re.match(r'^\[\d+', text):
        return False
    
    # 2. 以 数字. 开头（阿拉伯数字+点+空格/文字）→ 章节标题
    if re.match(r'^\d+\.\s+\S', text) or re.match(r'^\d+\.\S', text):
        return True
    
    # 3. 以 中文数字、 开头 → 章节标题
    if re.match(r'^[一二三四五六七八九十百千]+\s*、', text):
        return True
    
    # 4. 以 英文单词 开头且较短（可能是标题）→ 可能是章节标题
    words = text.split()
    if words and len(words[0]) < 30:
        if re.match(r'^[A-Z][a-zA-Z]+$', words[0]):
            english_titles = ['Introduction', 'Conclusion', 'References', 'Acknowledgements', 
                            'Abstract', 'Background', 'Methods', 'Results', 'Discussion',
                            'Experiment', 'Conclusion', 'Summary', 'Future', 'Appendix', 
                            'Bibliography', 'Acknowledgments', 'Conclusion']
            if words[0] in english_titles:
                return True
    
    # 5. 中文特殊章节标题列表
    chinese_chapter_titles = [
        '致谢', '谢辞', '感谢',
        '作者简历', '个人简历', '简历', '作者简介',
        '发表论文', '学术成果', '研究成果', '论文发表',
        '在学期间所获得的学术成果', '在学期间发表论文',
        '附录', '附录A', '附录B', '附录一', '附录二',
        '后记',
        '参考资料', '参考文献（续）'
    ]
    
    for title in chinese_chapter_titles:
        if text.strip() == title:
            return True
    
    # 6. 启发式规则：检测复合标题
    if re.match(r'^.{5,40}$', text):
        chapter_keywords = ['致谢', '感谢', '简历', '成果', '论文', '发表', '附录', '后记']
        ref_keywords = ['http', 'https', '[J]', '[M]', '[D]', 'DOI', 'doi.org', 
                       '出版社', 'Journal', 'Proceedings', 'Press', 'University']
        
        has_chapter_kw = any(kw in text for kw in chapter_keywords)
        has_ref_kw = any(kw in text for kw in ref_keywords)
        
        if has_chapter_kw and not has_ref_kw:
            if not re.match(r'^\[', text):
                return True
    
    # 7. 短段落无参考文献特征，可能是标题
    ref_indicators = ['http://', 'https://', '[J]', '[M]', '[D]', '[EB/OL]', 
                     r'\(\d{4}\)', r'\d{4}年', '出版社', 'Journal', 'Proceedings', 
                     'Press', 'University', 'DOI', 'doi.org']
    has_ref_indicator = any(indicator in text for indicator in ref_indicators)
    
    if len(text) < 80 and not has_ref_indicator:
        if re.match(r'^[A-Z0-9\s\-\']+$', text):
            return True
    
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
    header_pattern = structure_rules.get('header_pattern', r'^\\s*参考文献\\s*$')
    expected_blank_lines = structure_rules.get('blank_lines_after_header', 2)
    
    if debug:
        logger.debug(f"\n【参考文献检测】查找标题，正则: {repr(header_pattern)}")
    
    header_para = None
    header_idx = None
    
    # ========== 方案A：从论文中间位置开始查找，跳过目录中的条目 ==========
    search_start = len(doc.paragraphs) // 2
    
    for idx in range(search_start, len(doc.paragraphs)):
        paragraph = doc.paragraphs[idx]
        text = paragraph.text.strip()
        if re.match(header_pattern, text):
            header_para = paragraph
            header_idx = idx
            if debug:
                logger.debug(f"  找到标题在第 {idx} 行: '{text}'")
            break
    
    # 如果后半部分没找到，再尝试从前半部分查找（容错处理）
    if not header_para:
        for idx in range(0, search_start):
            paragraph = doc.paragraphs[idx]
            text = paragraph.text.strip()
            if re.match(header_pattern, text):
                header_para = paragraph
                header_idx = idx
                if debug:
                    logger.debug(f"  找到标题在第 {idx} 行: '{text}'")
                break
    
    if not header_para:
        report['ok'] = False
        error_msg = tpl.get('messages', {}).get('structure_header_error')
        if error_msg:
            report['messages'].append(error_msg)
        else:
            report['messages'].append("未找到'参考文献'标题段落")
        if debug:
            logger.debug(f"  未找到参考文献标题")
        return report
    
    report['header_paragraph'] = header_para
    report['header_paragraph_index'] = header_idx
    
    # 2. 检查标题格式（允许中间有空格，如"参 考 文 献"）
    title_text = header_para.text.strip()
    if re.match(r'^参\s*考\s*文\s*献$', title_text):
        ok_msg = tpl.get('messages', {}).get('structure_header_ok')
        if ok_msg:
            report['messages'].append(ok_msg)
    else:
        report['ok'] = False
        report['messages'].append(f"参考文献标题应为纯'参考文献'，实际为'{title_text}'")
    
    # ============== 步骤3：统计空行数 ==============
    blank_count = 0
    content_start_idx = header_idx + 1
    
    for idx in range(content_start_idx, len(doc.paragraphs)):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
            blank_count += 1
            continue
        
        # 跳过脚注、尾注等特殊内容
        if '[!' in text or 'footnote' in text.lower():
            continue
        
        # 找到第一个非空段落，开始提取参考文献
        break
    
    if debug:
        logger.debug(f"  标题后空行数: {blank_count}")
    
    report['blank_lines_after_header'] = blank_count
    
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
    
    # 提取参考文献
    for idx in range(content_start_idx, len(doc.paragraphs)):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
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
            break
        
        # 判断是否为章节标题（新的一章开始了）
        if is_chapter_title(text, debug=False):
            break
        
        # 判断是否为参考文献条目（支持自动编号）
        is_ref, ref_num = is_reference_entry(para, text, debug=False)
        if is_ref:
            content_paragraphs.append(para)
            content_paragraph_indices.append(idx)
            reference_numbers.append(ref_num if ref_num is not None else -1)
        elif re.search(r'\[\d+\]', text):
            # 包含序号但不是开头（不规范格式）
            content_paragraphs.append(para)
            content_paragraph_indices.append(idx)
            nums = re.findall(r'\[(\d+(?:\.\d+)?)\]', text)
            reference_numbers.extend([int(float(n)) for n in nums])
    
    # 汇总结果
    if debug:
        logger.debug(f"  共提取 {len(content_paragraphs)} 条参考文献")
    
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
def check_reference_header_format(paragraph, tpl, doc=None):
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
    
    actual_size_pt, actual_font_ascii, actual_font_eastasia, actual_bold, actual_italic, actual_line_spacing, _ = detect_font_for_run(main_run, paragraph, doc)
    
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
        if actual_size_pt is None:
            issues.append("无法检测到参考文献标题字体大小格式信息")
        elif not is_style_inherited:
            expected_size_pt = float(format_rules['font_size_pt'])
            actual_size_name = get_font_size(actual_size_pt, tpl)
            expected_size_name = get_font_size(expected_size_pt, tpl)
            logger.debug(f"参考文献标题字体大小: {actual_size_name}（{actual_size_pt}pt）(期望: {expected_size_name}（{expected_size_pt}pt）)")
            if abs(actual_size_pt - expected_size_pt) > 0.5:
                issues.append(f"标题字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）")
    
    # 中文字体检查
    if not should_skip_check('font_name') and 'font_name' in format_rules:
        if actual_font_eastasia is None:
            issues.append("无法检测到参考文献标题中文字体格式信息")
        elif not is_style_inherited:
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
        if actual_line_spacing is None:
            issues.append("无法检测到参考文献标题行间距格式信息")
        else:
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
            
            # 如果仍然没有，报告错误
            if actual_space_before_pt is None:
                issues.append(f"无法检测到标题段前间距格式信息")
            else:
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
            
            # 如果仍然没有，报告错误
            if actual_space_after_pt is None:
                issues.append(f"无法检测到标题段后间距格式信息")
            else:
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
def check_reference_content_format(content_paragraphs, tpl, doc=None):
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
    style_based_detected = False  # 是否检测到从样式继承的格式
    style_based_details = []  # 记录哪些格式是从样式继承的
    ref_format_summary = []  # 汇总所有参考文献的格式信息
    
    for para_idx, paragraph in enumerate(content_paragraphs, 1):
        if not paragraph or not paragraph.runs:
            continue
        
        # 获取参考文献内容（用于汇总显示）
        para_text = paragraph.text.strip()[:80]  # 取前80字符
        
        # 检测段落格式
        first_line_indent, left_indent, right_indent, indent_style_based = detect_paragraph_indent(paragraph)
        actual_alignment = detect_paragraph_alignment(paragraph)
        
        # 记录样式继承信息
        if indent_style_based:
            style_based_detected = True
            style_based_details.append(f"第{para_idx}条（缩进）")
        
        # 检测第一个非空run的格式
        main_run = None
        for run in paragraph.runs:
            if run.text.strip():
                main_run = run
                break
        
        if not main_run:
            continue
        
        actual_size_pt, actual_font_ascii, actual_font_eastasia, actual_bold, actual_italic, actual_line_spacing, font_style_based = detect_font_for_run(main_run, paragraph, doc)
        
        # 记录字体/行间距样式继承信息
        if font_style_based:
            style_based_detected = True
            style_based_details.append(f"第{para_idx}条（行间距）")
        
        # 组合样式继承标记（任一格式来自样式就跳过检查）
        is_style_based = indent_style_based or font_style_based
        
        # 获取模板中的正确值（这就是默认值）
        expected_size_pt = float(format_rules.get('font_size_pt', 12.0))
        expected_line_spacing = float(format_rules.get('line_spacing', 1.5))
        expected_hanging_chars = float(format_rules.get('hanging_indent', 2))
        
        # 如果检测不到，报告错误
        if actual_size_pt is None:
            issues.append(f"第{para_idx}条参考文献无法检测到字体大小格式信息")
        if actual_line_spacing is None:
            issues.append(f"第{para_idx}条参考文献无法检测到行间距格式信息")
        if actual_font_ascii is None:
            issues.append(f"第{para_idx}条参考文献无法检测到英文字体格式信息")
        if actual_font_eastasia is None:
            issues.append(f"第{para_idx}条参考文献无法检测到中文字体格式信息")
        if left_indent is None:
            issues.append(f"第{para_idx}条参考文献无法检测到左缩进格式信息")
        if first_line_indent is None:
            issues.append(f"第{para_idx}条参考文献无法检测到首行缩进格式信息")
        
        # 字体大小和行间距需要所有信息都检测到才进行比较
        all_info_detected = (actual_size_pt is not None and actual_line_spacing is not None 
                            and left_indent is not None and first_line_indent is not None)
        
        if all_info_detected:
            # 收集格式信息用于汇总显示
            font_size_name = get_font_size(actual_size_pt, tpl)
            spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
            # 处理可能的 None 值
            indent_parts = []
            if left_indent is not None:
                indent_parts.append(f"左:{left_indent:.1f}pt")
            if first_line_indent is not None:
                indent_parts.append(f"首行:{first_line_indent:.1f}pt")
            if right_indent is not None:
                indent_parts.append(f"右:{right_indent:.1f}pt")
            
            if indent_parts:
                indent_info = "缩进:" + ",".join(indent_parts)
            else:
                indent_info = "缩进:未检测到"
            
            ref_format_summary.append({
                'idx': para_idx,
                'content': para_text,
                'font_size': font_size_name,
                'font': actual_font_eastasia,
                'line_spacing': spacing_name,
                'indent': indent_info,
                'style_based': is_style_based  # 标记是否为样式继承
            })
            
            # 1. 字体大小检查
            if not should_skip_check('font_size') and 'font_size_pt' in format_rules and actual_size_pt is not None:
                expected_size_pt = float(format_rules['font_size_pt'])
                actual_size_name = get_font_size(actual_size_pt, tpl)
                expected_size_name = get_font_size(expected_size_pt, tpl)
                if abs(actual_size_pt - expected_size_pt) > 0.5:
                    msg = f"第{para_idx}条参考文献字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）"
                    if msg not in issues:
                        issues.append(msg)
        
        # 2. 中文字体检查（无论是否有中文内容都应该检查字体是否正确）- 移到条件块外部
        # if re.search(r'[\u4e00-\u9fff]', main_run.text):
        expected_chinese_font = format_rules.get('chinese_font', '宋体')
        if actual_font_eastasia is None:
            msg = f"第{para_idx}条参考文献无法检测到中文字体格式信息"
            if msg not in issues:
                issues.append(msg)
        elif expected_chinese_font.lower() not in actual_font_eastasia.lower():
            msg = f"第{para_idx}条参考文献中文文字字体应为{expected_chinese_font}，实际为{actual_font_eastasia}"
            if msg not in issues:
                issues.append(msg)
        # </if>  # 原有的条件注释保留但代码已移除条件
        
        # 3. 英文字体检查（无论是否有英文内容都应该检查字体是否正确）- 移到条件块外部
        # if re.search(r'[a-zA-Z]', main_run.text):
        expected_english_font = format_rules.get('english_font', 'Times New Roman')
        if actual_font_ascii is None:
            msg = f"第{para_idx}条参考文献无法检测到英文字体格式信息"
            if msg not in issues:
                issues.append(msg)
        elif expected_english_font.lower() not in actual_font_ascii.lower():
            msg = f"第{para_idx}条参考文献英文文字字体应为{expected_english_font}，实际为{actual_font_ascii}"
            if msg not in issues:
                issues.append(msg)
        # </if>  # 原有的条件注释保留但代码已移除条件
        
        # 字体检查结束后，恢复到原条件块内检查行间距
        if all_info_detected:
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
            # 如果 actual_size_pt 为 None，用默认值 10.5（五号）
            if actual_size_pt is None:
                actual_size_pt = 10.5
            expected_hanging_pt = expected_hanging_chars * actual_size_pt
            
            # 悬挂缩进的判定：
            # 1. left_indent > 1（整体有缩进）
            # 2. first_line_indent < 0（首行向左突出，形成悬挂效果）
            
            # 只有当缩进信息都检测到时，才进行悬挂缩进检查
            if left_indent is not None and first_line_indent is not None:
                if first_line_indent > 0:
                    # 有首行缩进（正数），这不是悬挂缩进，是错误的
                    msg = f"第{para_idx}条参考文献应使用悬挂缩进（首行无缩进，后续行缩进{expected_hanging_chars}字符），当前为首行缩进"
                    if msg not in issues:
                        issues.append(msg)
                elif left_indent > 1 and first_line_indent < 0:
                    # 正确的悬挂缩进：left_indent > 1 且 first_line_indent < 0
                    has_hanging_indent = True
                    # 计算实际悬挂缩进值（取绝对值比较）
                    actual_hanging_pt = abs(first_line_indent)
                    hanging_chars = pt_to_chars(actual_hanging_pt, actual_size_pt)
                    if abs(actual_hanging_pt - expected_hanging_pt) > actual_size_pt * 0.5:
                        msg = f"第{para_idx}条参考文献悬挂缩进应为{expected_hanging_chars}字符，实际约为{hanging_chars}字符"
                        if msg not in issues:
                            issues.append(msg)
                elif left_indent > 1:
                    # 有左缩进但没有悬挂缩进（首行也有缩进）
                    msg = f"第{para_idx}条参考文献应使用悬挂缩进（首行无缩进，后续行缩进{expected_hanging_chars}字符）"
                    if msg not in issues:
                        issues.append(msg)
                elif left_indent == 0 and first_line_indent == 0:
                    # left_indent 为 0，且 first_line_indent 为 0，说明没有设置缩进
                    msg = f"第{para_idx}条参考文献应使用悬挂缩进（首行无缩进，后续行缩进{expected_hanging_chars}字符），当前未设置缩进"
                    if msg not in issues:
                        issues.append(msg)
                # else: 其他情况（如left_indent<0）不报错
        
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
    
    # 输出参考文献格式汇总
    if ref_format_summary:
        logger.debug("\n" + "=" * 80)
        logger.debug("【参考文献格式汇总】")
        logger.debug("=" * 80)
        for ref in ref_format_summary:
            style_tag = " [样式]" if ref['style_based'] else ""
            logger.debug(f"[{ref['idx']:2d}]{style_tag} {ref['content'][:40]}...")
            logger.debug(f"      字体:{ref['font_size']}/{ref['font']} | 行距:{ref['line_spacing']} | {ref['indent']}")
        logger.debug("=" * 80)
    
    # 添加样式继承提醒
    if style_based_detected:
        # 记录样式继承信息到报告中
        report['style_based'] = True
        report['style_based_details'] = list(set(style_based_details))  # 去重
        
        # 如果没有其他格式问题，只添加提醒
        if not issues:
            report['ok'] = True  # 格式通过
            report['messages'].append("注：检测到参考文献格式来自Word样式系统，格式验证通过。如需确保格式正确，请确认样式设置符合论文规范。")
        else:
            # 有格式问题，添加提醒
            report['messages'].append("注：部分参考文献格式来自Word样式系统，可能与直接设置的格式检测结果不一致，建议确认样式设置是否符合论文规范。")
    
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
    
    for run_idx, run in enumerate(paragraph.runs):
        # 检查是否为上标
        if run.font.superscript:
            text = run.text.strip()
            if not text:
                continue
            
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
                        except ValueError:
                            pass
                    # 处理列表: "1,3,5" -> 1,3,5
                    elif ',' in cleaned_text:
                        parts = cleaned_text.split(',')
                        for part in parts:
                            part = part.strip()
                            if part.isdigit():
                                citations.add(int(part))
                        
                # 处理列表: "1,3,5" -> 1,3,5
                elif ',' in cleaned_text and cleaned_text.replace(',', '').isdigit():
                    parts = cleaned_text.split(',')
                    for part in parts:
                        part = part.strip()
                        if part.isdigit():
                            citations.add(int(part))
                        
                # 处理单个数字: "27" -> 27
                elif cleaned_text.isdigit():
                    citations.add(int(cleaned_text))
            
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
                        except ValueError:
                            pass
                            
                # 处理列表: "1,3,5" -> 1,3,5
                elif ',' in text and text.replace(',', '').isdigit():
                    parts = text.split(',')
                    for part in parts:
                        part = part.strip()
                        if part.isdigit():
                            citations.add(int(part))
                        
                # 处理单个数字: "1" -> 1
                elif text.isdigit():
                    citations.add(int(text))
    
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
    # 如果没有提供参考文献标题索引，先查找
    if references_header_idx is None:
        for idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if re.match(r'^参\s*考\s*文\s*献\s*$', text):
                references_header_idx = idx
                break
    
    # 确定正文结束位置
    end_idx = references_header_idx if references_header_idx is not None else len(doc.paragraphs)
    
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
    
    scanned = 0
    for idx in range(len(doc.paragraphs)):
        text = doc.paragraphs[idx].text.strip()
        
        # 跳过空段落
        if not text:
            continue
        
        scanned += 1
        
        # 检查是否在排除列表中
        is_excluded = False
        for keyword in EXCLUDE_SECTIONS:
            if keyword in text:
                is_excluded = True
                break
        
        if is_excluded:
            continue
        
        # 检查是否匹配章节标题
        for pattern in chapter_patterns:
            if re.match(pattern, text):
                start_idx = idx
                break
        
        if start_idx > 0:
            break
    
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
    
    # 1. 获取正文范围
    body_start, body_end = find_body_range(doc, references_header_idx, debug=False)
    
    if debug:
        logger.debug(f"  正文范围: 第 {body_start} 段 到 第 {body_end - 1} 段")
    
    # 2. 提取正文中的所有上标引用
    all_citations = set()
    
    for idx in range(body_start, body_end):
        para = doc.paragraphs[idx]
        text = para.text.strip()
        
        if not text:
            continue
        
        # 检查段落中是否有上标引用
        para_citations = extract_superscript_citations(para, debug=False)
        
        if para_citations:
            all_citations.update(para_citations)
    
    report['total_citations'] = len(all_citations)
    
    if debug:
        logger.debug(f"  检测到 {len(all_citations)} 个上标引用: {sorted(all_citations)}")
    
    # 3. 获取参考文献序号列表（排除自动编号-1）
    # 如果全是自动编号（-1），则生成虚拟序号 1,2,3... 用于比对
    auto_count = sum(1 for num in reference_numbers if num == -1 or num is None)
    if auto_count > 0 and all(num == -1 or num is None for num in reference_numbers):
        # 全是自动编号，生成虚拟序号
        valid_ref_numbers = list(range(1, len(reference_numbers) + 1))
    else:
        # 过滤掉 None 和 -1（自动编号），只保留有实际数字的序号
        valid_ref_numbers = [num for num in reference_numbers if num and num > 0]
    
    report['total_references'] = len(valid_ref_numbers)
    
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
    
    # 找出引用了不存在的序号
    if all_citations and valid_ref_numbers:
        ref_set = set(valid_ref_numbers)
        invalid_refs = all_citations - ref_set
        report['invalid_citations'] = sorted(invalid_refs)
    
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
        logger.debug(f"  引用检测结果: {'通过' if report['ok'] else '失败'}")
    
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
    global _skip_checks_config, _current_doc_path
    _skip_checks_config = skip_checks or []
    _current_doc_path = doc_path  # 保存文档路径供编号列表检测使用
    
    tpl = load_template(template_identifier)
    doc = Document(doc_path)
    
    # 执行各项检查（传入debug参数）
    structure_report = check_references_structure(doc, tpl, debug=debug)
    
    header_format_report = {'ok': True, 'messages': []}
    content_format_report = {'ok': True, 'messages': []}
    citation_report = {'ok': True, 'messages': []}  # 引用检测报告
    
    if structure_report.get('header_paragraph'):
        header_format_report = check_reference_header_format(structure_report['header_paragraph'], tpl, doc)
    
    if structure_report.get('content_paragraphs'):
        content_format_report = check_reference_content_format(structure_report['content_paragraphs'], tpl, doc)
    
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
    
    # 组装报告（调整后）
    # - references_header：参考文献"参考文献"标题的格式检查结果（独立分段）
    # - content_format：参考文献条目的内容格式检查结果
    # - citation：正文引用检查结果（不纳入前端报告，由 service 层合并到 content_format）
    report = {
        'structure': structure_report,
        'references_header': header_format_report,  # 独立分段 → 前端显示为 [标题格式]
        'content_format': content_format_report,
        'citation': citation_report,                 # 内部保留，不在前端独立成段
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

def detect_font_for_run_legacy(run, paragraph=None):
    """
    原有的字体检测函数（作为后备方案）
    检测run的字体信息，包括中英文字体
    返回: (font_size, font_ascii, font_eastasia, is_bold, is_italic, line_spacing, style_based)
    style_based: 是否有格式从样式继承（行间距等）
    """
    font_size = None
    font_name_ascii = None
    font_name_eastasia = None
    is_bold = None
    is_italic = False
    style_based = False  # 新增：是否从样式继承
    
    if not run:
        return None, None, None, False, False, None, False
    
    # 1. 检测字号
    font_size = None
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
    
    # 如果检测不到，返回 None（让调用方用模板值作为默认值）
    
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
    
    # 如果检测不到，返回 None（让调用方用模板值作为默认值）
    
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
    line_spacing = None  # 不再用硬编码默认值
    style_based_spacing = False
    try:
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
        elif paragraph and paragraph.style and paragraph.style.paragraph_format.line_spacing:
            # 从样式中读取到行间距，标记为样式继承
            line_spacing = float(paragraph.style.paragraph_format.line_spacing)
            style_based_spacing = True
            style_based = True
    except Exception:
        pass
    
    # 检查是否从样式继承（字体）
    if paragraph and paragraph.style:
        # 如果字体名称与默认值相同，可能是从样式继承的
        # 需要更深入的检测，这里先简单判断
        pass

    # 清理空字符串，视为未检测到
    if font_name_ascii is not None and str(font_name_ascii).strip() == "":
        font_name_ascii = None
    if font_name_eastasia is not None and str(font_name_eastasia).strip() == "":
        font_name_eastasia = None

    return font_size, font_name_ascii, font_name_eastasia, is_bold, is_italic, line_spacing, style_based or style_based_spacing

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
