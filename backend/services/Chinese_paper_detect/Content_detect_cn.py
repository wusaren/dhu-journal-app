#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn

# 跳过检测项配置
_skip_checks_config = []


def should_skip_check(check_name):
    global _skip_checks_config
    if _skip_checks_config is None:
        return False
    return check_name in _skip_checks_config


# ---------- 模板加载 ----------
def resolve_template_path(identifier):
    """
    解析模板路径：
    1) 绝对或相对路径直接存在则返回；
    2) 与当前文件同级的 templates 目录：../Chinese_paper_detect_templates/<id>.json；
    3) 兼容此前从项目根目录调用的相对路径。
    """
    # 1) 直接文件路径
    if os.path.isfile(identifier):
        return identifier

    # 2) 基于当前文件位置的 templates 目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_dir, "..", "Chinese_paper_detect_templates", identifier + ".json")
    candidate = os.path.normpath(candidate)
    if os.path.isfile(candidate):
        return candidate

    # 3) 旧的项目根目录相对路径（向后兼容）
    legacy = os.path.join("backend", "services", "Chinese_paper_detect_templates", identifier + ".json")
    if os.path.isfile(legacy):
        return legacy

    raise FileNotFoundError(f"Template not found: '{identifier}' (tried {candidate} and {legacy})")


def load_template(identifier):
    tpl_path = resolve_template_path(identifier)
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = json.load(f)
    return tpl


# ---------- 工具函数 ----------
def chinese_numeral_to_int(text):
    """将常见中文数字（到两位数）转换为整数"""
    numerals = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9}
    units = {'十': 10, '百': 100}
    total = 0
    tmp = 0
    for ch in text:
        if ch in numerals:
            tmp = numerals[ch]
        elif ch in units:
            unit = units[ch]
            tmp = 1 if tmp == 0 else tmp
            total += tmp * unit
            tmp = 0
        else:
            return None
    total += tmp
    if total == 0 and '十' in text:
        total = 10
    return total if total > 0 else None


def get_style_from_doc(doc, style_name):
    """从文档的样式定义中获取样式对象"""
    if not doc or not style_name:
        return None
    try:
        # 尝试从文档的样式集合中获取样式
        if hasattr(doc, 'styles'):
            for style in doc.styles:
                if style.name == style_name:
                    return style
    except Exception:
        pass
    return None

def get_style_inheritance_chain(style, doc=None):
    """获取样式的继承链（包括basedOn）"""
    chain = [style]
    if not style or not doc:
        return chain
    
    visited = {id(style)}
    current = style
    
    try:
        # 从文档的样式集合中查找样式
        doc_styles = {}
        if hasattr(doc, 'styles'):
            for s in doc.styles:
                if hasattr(s, 'style_id'):
                    doc_styles[s.style_id] = s
                if hasattr(s, 'name'):
                    doc_styles[s.name] = s
        
        # 遍历继承链
        max_depth = 10  # 防止无限循环
        depth = 0
        while current and depth < max_depth:
            depth += 1
            try:
                if hasattr(current, 'element'):
                    based_on = current.element.get(qn('w:basedOn'))
                    if based_on:
                        # 尝试从文档样式集合中查找基样式
                        next_style = doc_styles.get(based_on)
                        if next_style and id(next_style) not in visited:
                            visited.add(id(next_style))
                            chain.append(next_style)
                            current = next_style
                        else:
                            break
                    else:
                        break
                else:
                    break
            except Exception:
                break
    except Exception:
        pass
    
    return chain


# ---------- 文档默认设置提取函数 ----------

def get_document_default_line_spacing(doc):
    """
    从文档的默认段落格式中获取行距设置
    
    返回: float (行距倍数) 或 None
    """
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
                line_rule = spacing.get(qn('w:lineRule'))
                if spacing.get(qn('w:line')):
                    line_val = int(spacing.get(qn('w:line')))
                    return line_val / 240.0
    except Exception:
        pass
    
    return None


def get_document_default_indent(doc):
    """
    从文档的默认段落格式中获取缩进设置
    
    返回: {'first_line_indent': float(pt)} 或 None
    """
    try:
        pPr_defaults = doc.styles._element.xpath(
            '//w:docDefaults/w:pPrDefault/w:pPr'
        )
        if pPr_defaults:
            pPr = pPr_defaults[0]
            ind_nodes = pPr.xpath(
                './/w:ind',
                namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            )
            if ind_nodes:
                ind = ind_nodes[0]
                result = {}
                
                if ind.get(qn('w:hanging')):
                    result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                elif ind.get(qn('w:firstLine')):
                    result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                
                return result if result else None
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
                    line_rule = spacing.get(qn('w:lineRule'))
                    if spacing.get(qn('w:line')):
                        line_val = int(spacing.get(qn('w:line')))
                        return line_val / 240.0
        except Exception:
            pass
        
        normal_styles = doc.styles._element.xpath('//w:style[@w:styleId="Normal"]//w:spacing')
        if normal_styles:
            spacing = normal_styles[0]
            line_rule = spacing.get(qn('w:lineRule'))
            if spacing.get(qn('w:line')):
                line_val = int(spacing.get(qn('w:line')))
                return line_val / 240.0
    except Exception:
        pass
    
    return None


def get_normal_style_indent(doc):
    """从Normal样式中获取缩进设置"""
    try:
        try:
            normal_style = doc.styles['Normal']
            if normal_style and hasattr(normal_style, 'element'):
                ind_nodes = normal_style.element.xpath('.//w:ind')
                if ind_nodes:
                    ind = ind_nodes[0]
                    result = {}
                    if ind.get(qn('w:hanging')):
                        result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
                    elif ind.get(qn('w:firstLine')):
                        result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
                    return result if result else None
        except Exception:
            pass
        
        normal_styles = doc.styles._element.xpath('//w:style[@w:styleId="Normal"]//w:ind')
        if normal_styles:
            ind = normal_styles[0]
            result = {}
            if ind.get(qn('w:hanging')):
                result['first_line_indent'] = -int(ind.get(qn('w:hanging'))) / 20.0
            elif ind.get(qn('w:firstLine')):
                result['first_line_indent'] = int(ind.get(qn('w:firstLine'))) / 20.0
            return result if result else None
    except Exception:
        pass
    
    return None


def detect_font_for_run(run, paragraph=None, doc=None, debug=False):
    """
    检测run的字体、字号、加粗、斜体、行距
    - 字号：优先run直接格式，其次run XML，段落样式字体，段落样式XML，样式继承链
    - 字体：优先EastAsia，其次ascii/hAnsi/name；段落样式同样兜底
    - debug: 是否输出调试信息
    """
    debug_log = [] if debug else None
    # -------- 字号检测 --------
    font_size = None
    try:
        # 1) run 直接格式
        if run and run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)
            if debug_log is not None:
                debug_log.append(f"字号检测路径1（run直接格式）: {font_size}pt")

        # 2) run 绑定的字符样式（例如"标题一"作为字符样式）
        if font_size is None and run and getattr(run, "style", None) and getattr(run.style, "font", None):
            try:
                if run.style.font.size and hasattr(run.style.font.size, "pt"):
                    font_size = float(run.style.font.size.pt)
                    if debug_log is not None:
                        debug_log.append(f"字号检测路径2（run字符样式）: {font_size}pt")
            except Exception:
                if debug_log is not None:
                    debug_log.append("字号检测路径2（run字符样式）: 失败")
        
        # 2.5) run 字符样式的 XML（检查字符样式的XML中是否有字号）
        if font_size is None and run and getattr(run, "style", None) and hasattr(run.style, "element"):
            try:
                sz_nodes = run.style.element.xpath('.//w:sz')
                if sz_nodes:
                    if qn('w:val') in sz_nodes[0].attrib:
                        font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                        if debug_log is not None:
                            debug_log.append(f"字号检测路径2.5（run字符样式XML attrib）: {font_size}pt")
                    elif sz_nodes[0].get(qn('w:val')):
                        font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                        if debug_log is not None:
                            debug_log.append(f"字号检测路径2.5（run字符样式XML get）: {font_size}pt")
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径2.5（run字符样式XML）: 异常 - {str(e)}")

        # 3) run 的 XML（使用xpath和attrib方法）
        if font_size is None and run and hasattr(run._element, 'rPr'):
            try:
                sz_nodes = run._element.xpath('.//w:sz')
                if sz_nodes:
                    # 优先使用attrib方法
                    if qn('w:val') in sz_nodes[0].attrib:
                        font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                        if debug_log is not None:
                            debug_log.append(f"字号检测路径3（run XML attrib）: {font_size}pt")
                    elif sz_nodes[0].get(qn('w:val')):
                        font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                        if debug_log is not None:
                            debug_log.append(f"字号检测路径3（run XML get）: {font_size}pt")
                elif debug_log is not None:
                    debug_log.append("字号检测路径3（run XML）: 未找到w:sz节点")
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径3（run XML）: 异常 - {str(e)}")

        # 4) 段落样式字体
        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style.font, 'size') and hasattr(paragraph.style.font.size, 'pt'):
            font_size = float(paragraph.style.font.size.pt)
            if debug_log is not None:
                debug_log.append(f"字号检测路径4（段落样式font.size）: {font_size}pt")

        # 4.5) 段落XML中的直接格式（pPr中的rPr）- 对于toc样式，字号可能在这里
        if font_size is None and paragraph and hasattr(paragraph, '_element'):
            try:
                pPr_nodes = paragraph._element.xpath('.//w:pPr')
                if pPr_nodes:
                    found_sz = False
                    for pPr in pPr_nodes:
                        rPr_nodes = pPr.xpath('.//w:rPr')
                        if rPr_nodes:
                            for rPr in rPr_nodes:
                                sz_nodes = rPr.xpath('.//w:sz')
                                if sz_nodes:
                                    found_sz = True
                                    try:
                                        if qn('w:val') in sz_nodes[0].attrib:
                                            font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                                            if debug_log is not None:
                                                debug_log.append(f"字号检测路径4.5（段落XML pPr中的rPr attrib）: {font_size}pt")
                                        elif sz_nodes[0].get(qn('w:val')):
                                            font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                                            if debug_log is not None:
                                                debug_log.append(f"字号检测路径4.5（段落XML pPr中的rPr get）: {font_size}pt")
                                        if font_size:
                                            break
                                    except Exception as e:
                                        if debug_log is not None:
                                            debug_log.append(f"字号检测路径4.5（段落XML pPr中的rPr）: 异常 - {str(e)}")
                            if font_size:
                                break
                    if debug_log is not None and not found_sz and font_size is None:
                        debug_log.append("字号检测路径4.5（段落XML pPr中的rPr）: 未找到w:sz节点")
                elif debug_log is not None:
                    debug_log.append("字号检测路径4.5（段落XML）: 未找到w:pPr节点")
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径4.5（段落XML）: 异常 - {str(e)}")

        # 5) 段落样式 XML（适配样式集里的"标题一"等，使用xpath和attrib方法）
        if font_size is None and paragraph and hasattr(paragraph.style, 'element'):
            try:
                sz_nodes = paragraph.style.element.xpath('.//w:sz')
                if sz_nodes:
                    # 优先使用attrib方法
                    if qn('w:val') in sz_nodes[0].attrib:
                        font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                        if debug_log is not None:
                            debug_log.append(f"字号检测路径5（段落样式XML attrib）: {font_size}pt")
                    elif sz_nodes[0].get(qn('w:val')):
                        font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                        if debug_log is not None:
                            debug_log.append(f"字号检测路径5（段落样式XML get）: {font_size}pt")
                elif debug_log is not None:
                    style_name = getattr(paragraph.style, 'name', '未知')
                    debug_log.append(f"字号检测路径5（段落样式XML，样式名: {style_name}）: 未找到w:sz节点")
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径5（段落样式XML）: 异常 - {str(e)}")

        # 5.5) 段落样式XML的简化检测（借鉴Abstract_detect.py的方法）
        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style, "element"):
            try:
                sz_nodes = paragraph.style.element.xpath('.//w:sz')
                if sz_nodes and sz_nodes[0].get(qn('w:val')):
                    font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                    if debug_log is not None:
                        debug_log.append(f"字号检测路径5.5（段落样式XML简化方法）: {font_size}pt")
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径5.5（段落样式XML简化方法）: 异常 - {str(e)}")
        
        # 5.6) 段落样式XML中pPr下的rPr（有些样式可能把字号定义在这里）
        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style, "element"):
            try:
                pPr_nodes = paragraph.style.element.xpath('.//w:pPr')
                for pPr in pPr_nodes:
                    rPr_nodes = pPr.xpath('.//w:rPr')
                    for rPr in rPr_nodes:
                        sz_nodes = rPr.xpath('.//w:sz')
                        if sz_nodes:
                            if qn('w:val') in sz_nodes[0].attrib:
                                font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                                if debug_log is not None:
                                    debug_log.append(f"字号检测路径5.6（段落样式XML pPr中的rPr attrib）: {font_size}pt")
                                break
                            elif sz_nodes[0].get(qn('w:val')):
                                font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                                if debug_log is not None:
                                    debug_log.append(f"字号检测路径5.6（段落样式XML pPr中的rPr get）: {font_size}pt")
                                break
                    if font_size:
                        break
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径5.6（段落样式XML pPr中的rPr）: 异常 - {str(e)}")
        
        # 6) 检查样式继承链（优先检查当前样式，然后检查继承链）
        if font_size is None and paragraph and paragraph.style:
            try:
                # 先检查当前样式的所有可能的XML路径
                if hasattr(paragraph.style, 'element'):
                    # 检查 rPr（字符格式）- 使用attrib方法
                    rPr_nodes = paragraph.style.element.xpath('.//w:rPr')
                    for rPr in rPr_nodes:
                        sz_nodes = rPr.xpath('.//w:sz')
                        if sz_nodes:
                            try:
                                # 优先使用attrib方法
                                if qn('w:val') in sz_nodes[0].attrib:
                                    font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                                elif sz_nodes[0].get(qn('w:val')):
                                    font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                                if font_size:
                                    break
                            except Exception:
                                pass
                    if font_size is None:
                        # 检查 pPr（段落格式）中的 rPr
                        pPr_nodes = paragraph.style.element.xpath('.//w:pPr')
                        for pPr in pPr_nodes:
                            rPr_nodes = pPr.xpath('.//w:rPr')
                            for rPr in rPr_nodes:
                                sz_nodes = rPr.xpath('.//w:sz')
                                if sz_nodes:
                                    try:
                                        # 优先使用attrib方法
                                        if qn('w:val') in sz_nodes[0].attrib:
                                            font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                                        elif sz_nodes[0].get(qn('w:val')):
                                            font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                                        if font_size:
                                            break
                                    except Exception:
                                        pass
                            if font_size:
                                break
                
                # 如果还没有找到，检查样式继承链
                if font_size is None and doc:
                    style_chain = get_style_inheritance_chain(paragraph.style, doc)
                    if debug_log is not None:
                        debug_log.append(f"字号检测路径6（样式继承链）: 找到{len(style_chain)}个继承样式")
                    for idx, style in enumerate(style_chain):
                        # 先检查style.font.size（python-docx API）
                        if hasattr(style, 'font') and hasattr(style.font, 'size') and hasattr(style.font.size, 'pt'):
                            font_size = float(style.font.size.pt)
                            style_name = getattr(style, 'name', f'样式{idx}')
                            if debug_log is not None:
                                debug_log.append(f"字号检测路径6（继承样式{idx}，{style_name}，font.size）: {font_size}pt")
                            break
                        # 再检查样式的XML元素
                        if hasattr(style, 'element'):
                            # 检查 rPr（字符格式）
                            rPr_nodes = style.element.xpath('.//w:rPr')
                            for rPr in rPr_nodes:
                                sz_nodes = rPr.xpath('.//w:sz')
                                if sz_nodes:
                                    try:
                                        # 优先使用attrib方法
                                        if qn('w:val') in sz_nodes[0].attrib:
                                            font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                                        elif sz_nodes[0].get(qn('w:val')):
                                            font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                                        if font_size:
                                            break
                                    except Exception:
                                        pass
                            if font_size is None:
                                # 检查 pPr（段落格式）中的 rPr
                                pPr_nodes = style.element.xpath('.//w:pPr')
                                for pPr in pPr_nodes:
                                    rPr_nodes = pPr.xpath('.//w:rPr')
                                    for rPr in rPr_nodes:
                                        sz_nodes = rPr.xpath('.//w:sz')
                                        if sz_nodes:
                                            try:
                                                # 优先使用attrib方法
                                                if qn('w:val') in sz_nodes[0].attrib:
                                                    font_size = float(sz_nodes[0].attrib[qn('w:val')]) / 2.0
                                                elif sz_nodes[0].get(qn('w:val')):
                                                    font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                                                if font_size:
                                                    break
                                            except Exception:
                                                pass
                                    if font_size:
                                        break
                            if font_size:
                                style_name = getattr(style, 'name', f'样式{idx}')
                                if debug_log is not None:
                                    debug_log.append(f"字号检测路径6（继承样式{idx}，{style_name}，pPr中的rPr）: {font_size}pt")
                                break
                        if font_size:
                            break
                    if font_size is None and debug_log is not None:
                        debug_log.append("字号检测路径6（样式继承链）: 所有继承样式都未找到字号")
            except Exception as e:
                if debug_log is not None:
                    debug_log.append(f"字号检测路径6（样式继承链）: 异常 - {str(e)}")
    except Exception:
        pass
    # 保存原始检测结果（用于调试信息）
    font_size_raw = font_size
    font_size_detected = font_size is not None
    font_size = font_size if font_size is not None else 12.0

    # 如果仍未检测到字号，并且在调试模式下，输出关键XML片段，便于对比分析
    if debug_log is not None and not font_size_detected:
        try:
            # 段落样式名，方便定位
            style_name = ""
            if paragraph and paragraph.style:
                style_name = getattr(paragraph.style, "name", "") or ""
            debug_log.append(f"XML调试：段落样式 = {style_name}")

            # 1) run 的 XML 片段（增加长度到1000字符）
            if run is not None and hasattr(run, "_element"):
                run_xml = run._element.xml
                if run_xml:
                    debug_log.append("XML调试：run._element.xml（截断前1000字符）: " + run_xml[:1000])

            # 1.5) run 字符样式的 XML 片段
            if run is not None and getattr(run, "style", None) and hasattr(run.style, "element"):
                try:
                    run_style_xml = run.style.element.xml
                    if run_style_xml:
                        debug_log.append("XML调试：run.style.element.xml（截断前1000字符）: " + run_style_xml[:1000])
                except Exception:
                    debug_log.append("XML调试：run.style.element.xml: 无法获取")

            # 2) 段落 pPr 的 XML 片段（增加长度到1000字符）
            if paragraph is not None and hasattr(paragraph, "_element"):
                pPr = getattr(paragraph._element, "pPr", None)
                if pPr is not None and getattr(pPr, "xml", None):
                    ppr_xml = pPr.xml
                    debug_log.append("XML调试：paragraph._element.pPr.xml（截断前1000字符）: " + ppr_xml[:1000])

            # 3) 段落样式的 XML 片段（增加长度到1000字符）
            if paragraph is not None and getattr(paragraph, "style", None) is not None:
                style_element = getattr(paragraph.style, "element", None)
                if style_element is not None and getattr(style_element, "xml", None):
                    style_xml = style_element.xml
                    debug_log.append("XML调试：paragraph.style.element.xml（截断前1000字符）: " + style_xml[:1000])
            
            # 4) 检查段落样式的继承链XML
            if paragraph and paragraph.style and doc:
                try:
                    style_chain = get_style_inheritance_chain(paragraph.style, doc)
                    for idx, style in enumerate(style_chain):
                        if hasattr(style, "element") and hasattr(style.element, "xml"):
                            style_name_chain = getattr(style, "name", f"样式{idx}")
                            style_xml_chain = style.element.xml
                            debug_log.append(f"XML调试：继承样式{idx}（{style_name_chain}）.element.xml（截断前1000字符）: " + style_xml_chain[:1000])
                except Exception as e:
                    debug_log.append(f"XML调试：检查继承链XML时出错 - {e}")
        except Exception as e:
            debug_log.append(f"XML调试：收集XML片段时出错 - {e}")

        debug_log.append(f"字号检测最终结果: 未检测到，使用默认值{font_size}pt")

    # -------- 字体检测（EastAsia优先） --------
    def extract_font_from_rPr(rPr):
        """从 rPr 元素中提取字体信息（借鉴CSDN博客方法：使用xpath和attrib）"""
        if rPr is None:
            return None, None, None
        
        # 使用xpath查找w:rFonts元素
        rFonts_nodes = rPr.xpath('.//w:rFonts')
        if not rFonts_nodes:
            return None, None, None
        
        rFonts = rFonts_nodes[0]
        east = None
        ascii_f = None
        hAnsi = None
        
        try:
            # 优先读取eastAsia（中文字体）
            if qn('w:eastAsia') in rFonts.attrib:
                east = rFonts.attrib[qn('w:eastAsia')]
        except Exception:
            pass
        
        try:
            # 读取ascii（英文字体）
            if qn('w:ascii') in rFonts.attrib:
                ascii_f = rFonts.attrib[qn('w:ascii')]
        except Exception:
            pass
        
        try:
            # 读取hAnsi（拉丁字体）
            if qn('w:hAnsi') in rFonts.attrib:
                hAnsi = rFonts.attrib[qn('w:hAnsi')]
        except Exception:
            pass
        
        # 如果xpath方法失败，回退到原来的方法
        if not east and not ascii_f and not hAnsi:
            try:
                rFonts_find = rPr.find(qn('w:rFonts'))
                if rFonts_find is not None:
                    east = rFonts_find.get(qn('w:eastAsia'))
                    ascii_f = rFonts_find.get(qn('w:ascii'))
                    hAnsi = rFonts_find.get(qn('w:hAnsi'))
            except Exception:
                pass
        
        return east, ascii_f, hAnsi

    def get_font_from_style_name(style_name, paragraph=None):
        """根据样式名称推断字体（用于处理主题字体的情况）"""
        if not style_name:
            return None
        style_lower = style_name.lower()
        
        # 1. 处理目录样式（toc = table of contents）
        if 'toc' in style_lower:
            # toc 1, toc 2, toc 3 等通常用于标题，推断为黑体
            if any(keyword in style_lower for keyword in ['toc 1', 'toc1', 'toc 2', 'toc2', 'toc 3', 'toc3']):
                return "黑体"
        
        # 2. 处理标准标题样式
        if any(keyword in style_lower for keyword in ['标题', 'heading', 'title']):
            # 检查是否是中文标题样式
            if any(keyword in style_name for keyword in ['标题一', '标题1', 'Heading 1', '标题 1']):
                return "黑体"
            elif any(keyword in style_name for keyword in ['标题二', '标题2', 'Heading 2', '标题 2']):
                return "黑体"
            elif any(keyword in style_name for keyword in ['标题三', '标题3', 'Heading 3', '标题 3']):
                return "黑体"
        
        # 3. 尝试从文档的样式定义中读取字体信息
        if paragraph and paragraph.style:
            try:
                # 检查样式的基样式（basedOn）
                style_element = getattr(paragraph.style, "element", None)
                if style_element is not None:
                    # 检查 basedOn 属性
                    based_on = style_element.get(qn('w:basedOn'))
                    if based_on:
                        # 如果基样式是标题样式，推断为黑体
                        based_on_lower = based_on.lower()
                        if any(keyword in based_on_lower for keyword in ['heading', '标题', 'toc']):
                            return "黑体"
            except Exception:
                pass
        
        return None

    font_eastasia = None
    font_ascii = None
    font_hansi = None
    font_name = None

    try:
        # 1. run直接字体名称
        if run and run.font and run.font.name:
            font_name = run.font.name
        
        # 2. run XML字体（从 rPr 读取）
        if run and hasattr(run._element, 'rPr'):
            rPr = run._element.rPr
            if rPr is not None:
                east, ascii_f, hansi_f = extract_font_from_rPr(rPr)
                font_eastasia = font_eastasia or east
                font_ascii = font_ascii or ascii_f
                font_hansi = font_hansi or hansi_f

        # 3. run.style（字符样式）中的字体设置
        if run and getattr(run, "style", None):
            # 样式直接字体名
            try:
                if run.style.font and run.style.font.name and not font_name:
                    font_name = run.style.font.name
            except Exception:
                pass
            # 样式 XML 里的 rFonts
            try:
                style_element = getattr(run.style, "element", None)
                if style_element is not None:
                    rPr_style = getattr(style_element, "rPr", None)
                    if rPr_style is not None:
                        east_s, ascii_s, hansi_s = extract_font_from_rPr(rPr_style)
                        font_eastasia = font_eastasia or east_s
                        font_ascii = font_ascii or ascii_s
                        font_hansi = font_hansi or hansi_s
            except Exception:
                pass
        
        # 4. 段落样式字体（兼容 Word 样式集中的"标题1/标题2"等）
        if paragraph and paragraph.style:
            # 4.1 段落样式直接字体名
            try:
                if paragraph.style.font and paragraph.style.font.name and not font_name:
                    font_name = paragraph.style.font.name
            except Exception:
                pass
            
            # 4.2 段落样式 XML 里的 rFonts（使用xpath方法）
            try:
                style_element = getattr(paragraph.style, "element", None)
                if style_element is not None:
                    # 使用xpath直接查找rPr
                    rPr_nodes = style_element.xpath('.//w:rPr')
                    for rPr in rPr_nodes:
                        east, ascii_f, hansi_f = extract_font_from_rPr(rPr)
                        font_eastasia = font_eastasia or east
                        font_ascii = font_ascii or ascii_f
                        font_hansi = font_hansi or hansi_f
                        if font_eastasia or font_ascii:
                            break
                    
                    # 4.3 检查样式继承链（基于样式名称）
                    style_name = getattr(paragraph.style, "name", None)
                    if style_name and not font_eastasia:
                        inferred_font = get_font_from_style_name(style_name, paragraph)
                        if inferred_font:
                            font_eastasia = inferred_font
            except Exception:
                pass
            
            # 4.4 如果仍然没有找到字体，尝试从样式名称推断
            if not font_eastasia and not font_name:
                try:
                    style_name = getattr(paragraph.style, "name", None)
                    inferred_font = get_font_from_style_name(style_name, paragraph)
                    if inferred_font:
                        font_eastasia = inferred_font
                except Exception:
                    pass
    except Exception:
        pass

    # 组合优先级：eastAsia > ascii > hAnsi > name > Unknown
    font_candidates = [font_eastasia, font_ascii, font_hansi, font_name]
    font_final = next((f for f in font_candidates if f), "未知字体")

    # -------- 粗体/斜体 --------
    font_source = run.font if run else (paragraph.style.font if paragraph else None)
    is_bold = font_source.bold if font_source and font_source.bold is not None else False
    is_italic = font_source.italic if font_source and font_source.italic is not None else False
    if run and run.font:
        is_bold = run.font.bold if run.font.bold is not None else is_bold
        is_italic = run.font.italic if run.font.italic is not None else is_italic
    is_bold = bool(is_bold) if is_bold is not None else False
    is_italic = bool(is_italic) if is_italic is not None else False

    # -------- 行距 --------
    line_spacing = None
    try:
        # 1) 段落直接格式
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
        
        # 2) 段落样式格式
        if line_spacing is None and paragraph and paragraph.style:
            if paragraph.style.paragraph_format.line_spacing:
                line_spacing = float(paragraph.style.paragraph_format.line_spacing)
            
            # 3) 从样式XML中读取（检查pPr中的spacing）
            if line_spacing is None and hasattr(paragraph.style, 'element'):
                try:
                    # 检查 pPr 中的 spacing
                    pPr_nodes = paragraph.style.element.xpath('.//w:pPr')
                    for pPr in pPr_nodes:
                        spacing_nodes = pPr.xpath('.//w:spacing')
                        if spacing_nodes:
                            spacing = spacing_nodes[0]
                            line_attr = spacing.get(qn('w:line'))
                            line_rule = spacing.get(qn('w:lineRule'))
                            if line_attr:
                                # w:line 值是以240为单位，例如240=单倍行距，360=1.5倍行距
                                line_val = float(line_attr)
                                if line_rule == 'auto':
                                    # 自动行间距：line值通常是字体大小的120%作为基准
                                    line_spacing = line_val / 240.0
                                else:
                                    # 固定行间距：240 twips = 1.0倍
                                    line_spacing = line_val / 240.0
                                break
                except Exception:
                    pass
            
            # 4) 检查样式继承链
            if line_spacing is None and doc:
                try:
                    style_chain = get_style_inheritance_chain(paragraph.style, doc)
                    for style in style_chain:
                        if hasattr(style, 'paragraph_format') and style.paragraph_format.line_spacing:
                            line_spacing = float(style.paragraph_format.line_spacing)
                            break
                        if hasattr(style, 'element'):
                            pPr_nodes = style.element.xpath('.//w:pPr')
                            for pPr in pPr_nodes:
                                spacing_nodes = pPr.xpath('.//w:spacing')
                                if spacing_nodes:
                                    spacing = spacing_nodes[0]
                                    line_attr = spacing.get(qn('w:line'))
                                    line_rule = spacing.get(qn('w:lineRule'))
                                    if line_attr:
                                        line_val = float(line_attr)
                                        if line_rule == 'auto':
                                            # 自动行间距：line值通常是字体大小的120%作为基准
                                            line_spacing = line_val / 240.0
                                        else:
                                            # 固定行间距：240 twips = 1.0倍
                                            line_spacing = line_val / 240.0
                                        break
                                if line_spacing:
                                    break
                            if line_spacing:
                                break
                except Exception:
                    pass
        
        # 5) 从段落XML中直接读取
        if line_spacing is None and paragraph and hasattr(paragraph, '_element'):
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
                                # 自动行间距：line值通常是字体大小的120%作为基准
                                line_spacing = line_val / 240.0
                            else:
                                # 固定行间距：240 twips = 1.0倍
                                line_spacing = line_val / 240.0
            except Exception:
                pass
    except Exception:
        pass
    
    # 6) 从 Normal 样式读取行距
    if line_spacing is None and doc:
        normal_ls = get_normal_style_line_spacing(doc)
        if normal_ls is not None:
            line_spacing = normal_ls
    
    # 7) 从 docDefaults 读取行距
    if line_spacing is None and doc:
        doc_ls = get_document_default_line_spacing(doc)
        if doc_ls is not None:
            line_spacing = doc_ls
    
    line_spacing = line_spacing if line_spacing is not None else 1.0

    # 返回：实际字号（带默认值）、原始字号（可能为None）、是否检测成功、字体、加粗、斜体、行距、调试日志
    return font_size, font_size_raw, font_size_detected, font_final, is_bold, is_italic, line_spacing, debug_log


def get_alignment(paragraph, doc=None):
    """获取段落对齐方式，检查样式继承链"""
    alignment = None
    
    # 1) 段落直接格式
    direct = paragraph.paragraph_format.alignment
    if direct is not None:
        alignment = int(direct)
    
    # 2) 从段落XML中直接读取
    if alignment is None and hasattr(paragraph, '_element'):
        try:
            pPr = paragraph._element.pPr
            if pPr is not None:
                jc_nodes = pPr.xpath('.//w:jc')
                if jc_nodes:
                    jc_val = jc_nodes[0].get(qn('w:val'))
                    if jc_val == 'center':
                        alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                    elif jc_val == 'right':
                        alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                    elif jc_val == 'justify':
                        alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
                    elif jc_val == 'left':
                        alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        except Exception:
            pass
    
    # 3) 段落样式格式
    if alignment is None and paragraph.style:
        try:
            style_align = paragraph.style.paragraph_format.alignment
            if style_align is not None:
                alignment = int(style_align)
        except Exception:
            pass
        
        # 4) 从样式XML中读取（检查pPr中的jc）
        if alignment is None and hasattr(paragraph.style, 'element'):
            try:
                pPr_nodes = paragraph.style.element.xpath('.//w:pPr')
                for pPr in pPr_nodes:
                    jc_nodes = pPr.xpath('.//w:jc')
                    if jc_nodes:
                        jc_val = jc_nodes[0].get(qn('w:val'))
                        if jc_val == 'center':
                            alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                        elif jc_val == 'right':
                            alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                        elif jc_val == 'justify':
                            alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
                        elif jc_val == 'left':
                            alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                        if alignment:
                            break
            except Exception:
                pass
        
        # 5) 检查样式继承链
        if alignment is None and doc:
            try:
                style_chain = get_style_inheritance_chain(paragraph.style, doc)
                for style in style_chain:
                    if hasattr(style, 'paragraph_format') and style.paragraph_format.alignment is not None:
                        alignment = int(style.paragraph_format.alignment)
                        break
                    if hasattr(style, 'element'):
                        pPr_nodes = style.element.xpath('.//w:pPr')
                        for pPr in pPr_nodes:
                            jc_nodes = pPr.xpath('.//w:jc')
                            if jc_nodes:
                                jc_val = jc_nodes[0].get(qn('w:val'))
                                if jc_val == 'center':
                                    alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                                elif jc_val == 'right':
                                    alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                                elif jc_val == 'justify':
                                    alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
                                elif jc_val == 'left':
                                    alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                                if alignment:
                                    break
                        if alignment:
                            break
            except Exception:
                pass
    
    return alignment if alignment is not None else WD_PARAGRAPH_ALIGNMENT.LEFT


def detect_spacing(paragraph, doc=None):
    """检测段前段后间距，检查样式继承链"""
    def pt(v):
        return v.pt if v else 0.0
    
    space_before = None
    space_after = None
    
    # 1) 段落直接格式
    fmt = paragraph.paragraph_format
    space_before = pt(fmt.space_before)
    space_after = pt(fmt.space_after)
    
    # 2) 从段落XML中直接读取
    if (space_before == 0.0 or space_after == 0.0) and hasattr(paragraph, '_element'):
        try:
            pPr = paragraph._element.pPr
            if pPr is not None:
                spacing_nodes = pPr.xpath('.//w:spacing')
                if spacing_nodes:
                    spacing_elem = spacing_nodes[0]
                    if space_before == 0.0:
                        before_attr = spacing_elem.get(qn('w:before'))
                        if before_attr:
                            space_before = float(before_attr) / 20.0  # 转换为pt
                    if space_after == 0.0:
                        after_attr = spacing_elem.get(qn('w:after'))
                        if after_attr:
                            space_after = float(after_attr) / 20.0  # 转换为pt
        except Exception:
            pass
    
    # 3) 从样式格式中读取
    if (space_before == 0.0 or space_after == 0.0) and paragraph.style:
        try:
            if space_before == 0.0 and paragraph.style.paragraph_format.space_before:
                space_before = pt(paragraph.style.paragraph_format.space_before)
            if space_after == 0.0 and paragraph.style.paragraph_format.space_after:
                space_after = pt(paragraph.style.paragraph_format.space_after)
            
            # 4) 从样式XML中读取（检查pPr中的spacing）
            if (space_before == 0.0 or space_after == 0.0) and hasattr(paragraph.style, 'element'):
                pPr_nodes = paragraph.style.element.xpath('.//w:pPr')
                for pPr in pPr_nodes:
                    spacing_nodes = pPr.xpath('.//w:spacing')
                    if spacing_nodes:
                        spacing_elem = spacing_nodes[0]
                        if space_before == 0.0:
                            before_attr = spacing_elem.get(qn('w:before'))
                            if before_attr:
                                space_before = float(before_attr) / 20.0
                        if space_after == 0.0:
                            after_attr = spacing_elem.get(qn('w:after'))
                            if after_attr:
                                space_after = float(after_attr) / 20.0
                        if space_before != 0.0 and space_after != 0.0:
                            break
        except Exception:
            pass
        
        # 5) 检查样式继承链
        if (space_before == 0.0 or space_after == 0.0) and doc:
            try:
                style_chain = get_style_inheritance_chain(paragraph.style, doc)
                for style in style_chain:
                    if hasattr(style, 'paragraph_format'):
                        if space_before == 0.0 and style.paragraph_format.space_before:
                            space_before = pt(style.paragraph_format.space_before)
                        if space_after == 0.0 and style.paragraph_format.space_after:
                            space_after = pt(style.paragraph_format.space_after)
                    if hasattr(style, 'element'):
                        pPr_nodes = style.element.xpath('.//w:pPr')
                        for pPr in pPr_nodes:
                            spacing_nodes = pPr.xpath('.//w:spacing')
                            if spacing_nodes:
                                spacing_elem = spacing_nodes[0]
                                if space_before == 0.0:
                                    before_attr = spacing_elem.get(qn('w:before'))
                                    if before_attr:
                                        space_before = float(before_attr) / 20.0
                                if space_after == 0.0:
                                    after_attr = spacing_elem.get(qn('w:after'))
                                    if after_attr:
                                        space_after = float(after_attr) / 20.0
                                if space_before != 0.0 and space_after != 0.0:
                                    break
                        if space_before != 0.0 and space_after != 0.0:
                            break
            except Exception:
                pass
    
    return space_before if space_before is not None else 0.0, space_after if space_after is not None else 0.0


# ---------- 结构识别 ----------
def identify_titles(doc, tpl):
    structure = tpl.get('structure_rules', {})
    level1_pattern = structure.get('level1_pattern')
    level2_pattern = structure.get('level2_pattern')
    level3_pattern = structure.get('level3_pattern')

    titles = []
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip() if paragraph.text else ''
        if not text:
            continue

        # 按从具体到一般的顺序检查：先检查三级标题，再检查二级，最后检查一级
        # 这样可以避免三级标题（如"1.2.1"）被误识别为二级标题（"1.2"）
        if level3_pattern and re.match(level3_pattern, text):
            m = re.match(level3_pattern, text)
            # 过滤掉目录中的标题（toc样式），只保留正文中的标题
            style_name = getattr(paragraph.style, 'name', '').lower() if paragraph.style else ''
            if 'toc' in style_name:
                # 跳过目录中的标题
                continue
            titles.append({
                'level': 3,
                'number': m.group(1),
                'text': m.group(2).strip(),
                'paragraph': paragraph,
                'paragraph_index': idx,
                'full_text': text
            })
        elif level2_pattern and re.match(level2_pattern, text):
            m = re.match(level2_pattern, text)
            # 过滤掉目录中的标题（toc样式），只保留正文中的标题
            style_name = getattr(paragraph.style, 'name', '').lower() if paragraph.style else ''
            if 'toc' in style_name:
                # 跳过目录中的标题
                continue
            titles.append({
                'level': 2,
                'number': m.group(1),
                'text': m.group(2).strip(),
                'paragraph': paragraph,
                'paragraph_index': idx,
                'full_text': text
            })
        elif level1_pattern and re.match(level1_pattern, text):
            m = re.match(level1_pattern, text)
            # 过滤掉目录中的标题（toc样式），只保留正文中的标题
            style_name = getattr(paragraph.style, 'name', '').lower() if paragraph.style else ''
            if 'toc' in style_name:
                # 跳过目录中的标题
                continue
            cn_num = m.group(1)
            number_int = chinese_numeral_to_int(cn_num)
            number = str(number_int) if number_int else cn_num
            titles.append({
                'level': 1,
                'number': number,
                'text': m.group(2).strip(),
                'paragraph': paragraph,
                'paragraph_index': idx,
                'full_text': text
            })
    return titles


def validate_numbering(titles, tpl):
    try:
        level1_nums = [int(t['number']) for t in titles if t['level'] == 1 and str(t['number']).isdigit()]
        if level1_nums:
            expected = list(range(1, len(level1_nums) + 1))
            if sorted(level1_nums) != expected:
                return False

        level2_nums = [t['number'] for t in titles if t['level'] == 2]
        for num in level2_nums:
            if not re.match(r'^\d+\.\d+$', num):
                return False

        level3_nums = [t['number'] for t in titles if t['level'] == 3]
        for num in level3_nums:
            if not re.match(r'^\d+\.\d+\.\d+$', num):
                return False
        return True
    except Exception:
        return False


def check_structure(doc, tpl):
    report = {'ok': True, 'messages': [], 'titles': []}
    titles = identify_titles(doc, tpl)
    report['titles'] = titles

    if not titles:
        report['ok'] = False
        msg = tpl.get('messages', {}).get('structure_hierarchy_error')
        if msg:
            report['messages'].append(msg)
        return report

    if validate_numbering(titles, tpl):
        msg = tpl.get('messages', {}).get('structure_numbering_ok')
        if msg:
            report['messages'].append(msg)
    else:
        report['ok'] = False
        msg = tpl.get('messages', {}).get('structure_numbering_error')
        if msg:
            report['messages'].append(msg)

    msg_h = tpl.get('messages', {}).get('structure_hierarchy_ok')
    if msg_h:
        report['messages'].append(msg_h)
    return report


# ---------- 格式检测 ----------
def check_format(titles, tpl, doc=None):
    report = {'ok': True, 'messages': []}
    if not titles:
        report['ok'] = False
        report['messages'].append("没有标题可供格式检查")
        return report

    format_rules = tpl.get('format_rules', {})
    check_rules = tpl.get('check_rules', {})
    issues = []

    def font_size_name(pt):
        size_map = {}
        for k, v in check_rules.get('font_size_mapping', {}).items():
            try:
                size_map[float(k)] = v
            except Exception:
                continue
        if not size_map:
            return f"{pt}pt"
        closest = min(size_map.keys(), key=lambda x: abs(x - pt))
        return size_map[closest]

    def alignment_name(align_val):
        """将对齐枚举值转换为中文描述"""
        # 对齐枚举值到字符串的映射
        align_to_str = {
            WD_PARAGRAPH_ALIGNMENT.LEFT: "left",
            WD_PARAGRAPH_ALIGNMENT.CENTER: "center",
            WD_PARAGRAPH_ALIGNMENT.RIGHT: "right",
            WD_PARAGRAPH_ALIGNMENT.JUSTIFY: "justify"
        }
        align_str = align_to_str.get(align_val, "unknown")
        # 从模板中获取中文描述
        align_map = check_rules.get('alignment_mapping', {})
        return align_map.get(align_str, f"未知对齐({align_val})")

    def line_spacing_name(spacing_val):
        """将行距数值转换为中文描述"""
        spacing_map = {}
        for k, v in check_rules.get('line_spacing_mapping', {}).items():
            try:
                spacing_map[float(k)] = v
            except Exception:
                continue
        if not spacing_map:
            return f"{spacing_val}倍行距"
        # 找到最接近的映射值
        closest = min(spacing_map.keys(), key=lambda x: abs(x - spacing_val))
        if abs(closest - spacing_val) < 0.05:  # 容差0.05
            return spacing_map[closest]
        return f"{spacing_val}倍行距"

    for title in titles:
        level = title['level']
        paragraph = title['paragraph']
        text = title['text']

        if level == 1:
            rule_key = 'level1_title'
        elif level == 2:
            rule_key = 'level2_title'
        elif level == 3:
            rule_key = 'level3_title'
        else:
            continue

        rules = format_rules.get(rule_key, {})
        if not rules or not paragraph.runs:
            continue

        # 选取用于检测的 run：
        # 1) 优先选择包含中文或英文字符、且出现在标题文本中的 run（避免只拿到编号或页码）；
        # 2) 若找不到，则退回到第一个非空 run。
        main_run = None
        title_text = text.replace("\t", "")
        for run in paragraph.runs:
            if not run.text:
                continue
            run_txt = run.text.strip()
            if not run_txt:
                continue
            # 如果 run 文本中包含中文或英文字母，且与标题内容有重叠，就认为是标题主体部分
            if (re.search(r'[\u4e00-\u9fffA-Za-z]', run_txt) and
                    any(ch in title_text for ch in run_txt if ch.strip())):
                main_run = run
                break
        if main_run is None:
            # 兜底：第一个非空 run
            for run in paragraph.runs:
                if run.text and run.text.strip():
                    main_run = run
                    break
        if main_run is None:
            continue

        size_pt, size_pt_raw, size_pt_detected, font_name, is_bold, is_italic, line_spacing, debug_log = detect_font_for_run(main_run, paragraph, doc, debug=False)
        space_before, space_after = detect_spacing(paragraph, doc)
        alignment = get_alignment(paragraph, doc)

        # 字号
        if not should_skip_check('font_size') and 'font_size_pt' in rules:
            expected = float(rules['font_size_pt'])
            if abs(size_pt - expected) > 0.5:
                issues.append(f"标题“{text}”字号应为{font_size_name(expected)}（{expected}pt），实际为{font_size_name(size_pt)}（{size_pt}pt）")

        # 字体（恢复无论是否为“未知字体”都输出实际检测结果，方便排查）
        if not should_skip_check('font_name') and 'font_name' in rules:
            expected_font = str(rules['font_name'])
            if expected_font.lower() not in (font_name or '').lower():
                # 添加调试信息：显示段落样式名称
                style_name_info = ""
                try:
                    if paragraph and paragraph.style:
                        style_name = getattr(paragraph.style, "name", None)
                        if style_name:
                            style_name_info = f"（段落样式：{style_name}）"
                except Exception:
                    pass
                issues.append(f'标题"{text}"字体应为{expected_font}，实际为{font_name}{style_name_info}')

        # 加粗
        if not should_skip_check('bold') and 'bold' in rules:
            expected_bold = bool(rules['bold'])
            if is_bold != expected_bold:
                bold_status = "加粗" if expected_bold else "不加粗"
                actual_status = "加粗" if is_bold else "不加粗"
                issues.append(f"标题“{text}”应为{bold_status}，实际为{actual_status}")

        # 斜体
        if not should_skip_check('italic') and 'italic' in rules:
            expected_italic = bool(rules['italic'])
            if is_italic != expected_italic:
                italic_status = "斜体" if expected_italic else "正体"
                actual_status = "斜体" if is_italic else "正体"
                issues.append(f"标题“{text}”应为{italic_status}，实际为{actual_status}")

        # 行距
        if not should_skip_check('spacing') and 'line_spacing' in rules:
            expected_ls = float(rules['line_spacing'])
            if abs(line_spacing - expected_ls) > 0.1:
                expected_ls_name = line_spacing_name(expected_ls)
                actual_ls_name = line_spacing_name(line_spacing)
                issues.append(f'标题"{text}"行距应为{expected_ls_name}，实际为{actual_ls_name}')

        # 对齐
        if 'alignment' in rules:
            expected_align = rules['alignment']
            align_map = {"left": WD_PARAGRAPH_ALIGNMENT.LEFT, "center": WD_PARAGRAPH_ALIGNMENT.CENTER,
                         "right": WD_PARAGRAPH_ALIGNMENT.RIGHT, "justify": WD_PARAGRAPH_ALIGNMENT.JUSTIFY}
            expected_align_val = align_map.get(expected_align, WD_PARAGRAPH_ALIGNMENT.LEFT)
            if alignment != expected_align_val:
                expected_align_name = check_rules.get('alignment_mapping', {}).get(expected_align, expected_align)
                actual_align_name = alignment_name(alignment)
                issues.append(f'标题"{text}"应为{expected_align_name}，实际为{actual_align_name}')

        # 段前段后
        if 'space_before' in rules:
            expected_before = float(rules['space_before'])
            if abs(space_before - expected_before) > 2.0:
                issues.append(f"标题“{text}”段前应为{expected_before:.1f}pt，实际为{space_before:.1f}pt")
        if 'space_after' in rules:
            expected_after = float(rules['space_after'])
            if abs(space_after - expected_after) > 2.0:
                issues.append(f"标题“{text}”段后应为{expected_after:.1f}pt，实际为{space_after:.1f}pt")

    if issues:
        report['ok'] = False
        # 添加格式问题header，与标题检测报告格式一致
        header = tpl.get('messages', {}).get('format_content_issue_header', '正文标题格式问题：')
        report['messages'].append(header)
        # 每个错误信息不加前缀，由报告生成器添加
        report['messages'].extend(issues)
    else:
        msg = tpl.get('messages', {}).get('format_level1_ok')
        if msg:
            report['messages'].append(msg)
        msg2 = tpl.get('messages', {}).get('format_level2_ok')
        if msg2:
            report['messages'].append(msg2)
        msg3 = tpl.get('messages', {}).get('format_level3_ok')
        if msg3:
            report['messages'].append(msg3)
    return report


# ---------- 主入口 ----------
def check_content_with_template(doc_path, template_identifier="Content", skip_checks=None):
    """
    主检查函数：检查中文正文格式
    
    Args:
        doc_path: Word文档路径
        template_identifier: 模板标识符或路径，默认为 "Content"
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
    
    Returns:
        检测结果字典
    """
    # 设置全局跳过检测项配置
    global _skip_checks_config
    _skip_checks_config = skip_checks or []
    
    tpl = load_template(template_identifier)
    doc = Document(doc_path)

    structure_report = check_structure(doc, tpl)

    # 清理不可序列化的字段（如 Paragraph 对象）
    raw_titles = structure_report.get('titles', [])
    sanitized_titles = []
    for t in raw_titles:
        sanitized = {k: v for k, v in t.items() if k not in ("paragraph",)}
        sanitized_titles.append(sanitized)
    structure_report['titles'] = sanitized_titles

    format_report = check_format(raw_titles, tpl, doc)

    overall_ok = structure_report.get('ok', True) and format_report.get('ok', True)
    summary_tpl = tpl.get('messages', {}).get('summary_overall', "中文正文格式检查结果: {ok}")
    summary = summary_tpl.format(ok="通过" if overall_ok else "未通过")

    report = {
        "ok": overall_ok,
        "structure": structure_report,
        "format": format_report,
        "messages": [summary]
    }
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="中文正文格式检测")
    parser.add_argument("doc", help="待检测的docx文件路径")
    parser.add_argument("-t", "--template", default="Content", help="模板标识符或路径")
    parser.add_argument("--skip", nargs="*", help="跳过的检测项，如 font_size bold italic alignment spacing indent")
    args = parser.parse_args()

    global _skip_checks_config
    _skip_checks_config = args.skip or []

    result = check_content_with_template(args.doc, args.template)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

