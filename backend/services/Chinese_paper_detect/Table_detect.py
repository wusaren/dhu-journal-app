#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import logging
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)


def _get_font_size_name(pt_size):
    """将磅值转换为中文字号名称"""
    size_map = {
        9: "小五", 10.5: "五号", 12: "小四", 14: "四号",
        16: "三号", 18: "小二", 22: "二号", 24: "小一", 26: "一号"
    }
    closest_size = min(size_map.keys(), key=lambda x: abs(x - pt_size))
    return size_map[closest_size]


def _border_val_none_or_nil(val):
    """判断边框 w:val 是否表示'无边框'，大小写不敏感。"""
    if val is None:
        return True
    return str(val).lower().strip() in ('none', 'nil', '')



# 添加项目根目录到 sys.path 以支持独立运行（与 Title_detect.py 保持一致）
if __name__ == "__main__" and __package__ is None:
    logging.basicConfig(level=logging.INFO)
    file = Path(__file__).resolve()
    parent, root = file.parent, file.parents[1]
    sys.path.append(str(root))
    try:
        sys.path.remove(str(parent))
    except ValueError:
        pass


def should_skip_check(check_name):
    """判断是否应该跳过某个检测项"""
    global _skip_checks_config
    if _skip_checks_config is None:
        return False
    return check_name in _skip_checks_config


_skip_checks_config = []


def resolve_template_path(identifier):
    """解析模板路径，支持文件路径和模板名称（与 Title_detect.py 风格一致）"""
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
    tpl_path = resolve_template_path(identifier)
    with open(tpl_path, 'r', encoding='utf-8') as f:
        return json.load(f)




def get_document_default_fonts(doc):
    """
    从文档的默认字符格式中获取字体和字号设置

    返回: {'ascii': str, 'east_asia': str, 'hAnsi': str, 'font_size': float} 或 None
    """
    try:
        doc_defaults = doc.styles._element.xpath(
            '//w:docDefaults/w:rPrDefault/w:rPr'
        )
        if not doc_defaults:
            return None
        rpr = doc_defaults[0]
        result = {}

        # 字体
        rfonts = rpr.find(qn('w:rFonts'))
        if rfonts is not None:
            ascii_font = rfonts.get(qn('w:ascii'))
            hansi_font = rfonts.get(qn('w:hAnsi'))
            east_asia_font = rfonts.get(qn('w:eastAsia'))
            if ascii_font:
                result['ascii'] = ascii_font
            if hansi_font:
                result['hAnsi'] = hansi_font
            if east_asia_font:
                result['east_asia'] = east_asia_font

        # 字号（w:sz / w:szCs，单位 half-point，需除以 2 转为 pt）
        for xname in ['w:sz', 'w:szCs']:
            sz_node = rpr.find(qn(xname))
            if sz_node is not None and sz_node.get(qn('w:val')):
                val_str = sz_node.get(qn('w:val'))
                try:
                    result['font_size'] = float(val_str) / 2.0
                    break
                except (ValueError, TypeError):
                    continue

        return result if result else None
    except Exception:
        return None


def get_inherited_style_properties(style, doc, visited_styles=None):
    """
    递归获取样式及其继承链的所有属性（字号、字体、加粗、斜体）

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
        if hasattr(style, 'element') and style.element is not None:
            elem = style.element

            # 字号（w:sz / w:szCs，单位 half-point，需除以 2）
            for xname in ['.//w:sz', './/w:szCs']:
                sz_nodes = elem.xpath(xname)
                if sz_nodes and sz_nodes[0].get(qn('w:val')):
                    val = float(sz_nodes[0].get(qn('w:val'))) / 2.0
                    properties['font_size'] = val
                    break

            # 加粗（w:b / w:bCs）
            for xname in ['.//w:b', './/w:bCs']:
                b_nodes = elem.xpath(xname)
                if b_nodes:
                    v = b_nodes[0].get(qn('w:val'))
                    properties['is_bold'] = (v != '0') if v else True
                    break

            # 斜体（w:i / w:iCs）
            for xname in ['.//w:i', './/w:iCs']:
                i_nodes = elem.xpath(xname)
                if i_nodes:
                    v = i_nodes[0].get(qn('w:val'))
                    properties['is_italic'] = (v != '0') if v else True
                    break

            # 字体名称
            rfonts_nodes = elem.xpath('.//w:rFonts')
            if rfonts_nodes:
                rfonts = rfonts_nodes[0]
                ascii_font = rfonts.get(qn('w:ascii'))
                eastasia_font = rfonts.get(qn('w:eastAsia'))
                hansi_font = rfonts.get(qn('w:hAnsi'))
                if ascii_font:
                    properties['font_ascii'] = ascii_font
                if eastasia_font:
                    properties['font_east_asia'] = eastasia_font
                elif hansi_font:
                    properties['font_name'] = hansi_font

            # python-docx API 兜底（字号）
            if 'font_size' not in properties:
                if (hasattr(style, 'font')
                        and hasattr(style.font, 'size')
                        and style.font.size is not None
                        and hasattr(style.font.size, 'pt')):
                    properties['font_size'] = float(style.font.size.pt)

            # python-docx API 兜底（加粗）
            if 'is_bold' not in properties:
                if (hasattr(style, 'font')
                        and hasattr(style.font, 'bold')
                        and style.font.bold is not None):
                    properties['is_bold'] = style.font.bold

            # python-docx API 兜底（斜体）
            if 'is_italic' not in properties:
                if (hasattr(style, 'font')
                        and hasattr(style.font, 'italic')
                        and style.font.italic is not None):
                    properties['is_italic'] = style.font.italic
    except Exception:
        pass

    if hasattr(style, 'base_style') and style.base_style:
        parent_properties = get_inherited_style_properties(style.base_style, doc, visited_styles)
        parent_properties.update(properties)
        properties = parent_properties

    return properties


def _get_run_effective_font_size(run, paragraph=None):
    """
    获取单个 run 的有效字号，按优先级依次尝试：
    1. run XML w:szCs（Complex Script 显示字号，Word 渲染值）
    2. run XML w:sz
    3. None（需从样式继承）
    返回 float 或 None
    """
    try:
        if hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                szCs_nodes = rpr.xpath('.//w:szCs')
                if szCs_nodes and szCs_nodes[0].get(qn('w:val')):
                    return float(szCs_nodes[0].get(qn('w:val'))) / 2.0
                sz_nodes = rpr.xpath('.//w:sz')
                if sz_nodes and sz_nodes[0].get(qn('w:val')):
                    return float(sz_nodes[0].get(qn('w:val'))) / 2.0
    except Exception:
        pass
    return None


def detect_font_for_run(run, paragraph=None, doc=None, expected_size_fallback=None):
    """
    检测 run 的字号、英文字体(ASCII/hAnsi)、中文字体(EastAsia)、加粗、斜体。
    支持样式继承链和 docDefaults，各属性追溯路径如下：

      字号：  1)run XML szCs  2)run XML sz  3)paragraph.style API  4)paragraph.style XML
               5)paragraph direct XML  6)段落样式继承链  7)docDefaults  8)expected_size_fallback

      字体：  1)run XML rFonts  2)paragraph.style XML  3)段落样式继承链  4)docDefaults

      加粗：  1)run API  2)paragraph.style API  3)run XML  4)段落样式继承链

      斜体：  1)run API  2)paragraph.style API  3)run XML  4)段落样式继承链
    """
    font_size = None
    font_ascii = None
    font_eastasia = None
    is_bold = None
    is_italic = None

    if not run:
        return expected_size_fallback or 12.0, "Times New Roman", "宋体", False, False

    # ---------- 字号（5 层精确路径） ----------
    try:
        if hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                szCs_nodes = rpr.xpath('.//w:szCs')
                szCs_val = szCs_nodes[0].get(qn('w:val')) if szCs_nodes and szCs_nodes[0].get(qn('w:val')) else None
                if szCs_val:
                    font_size = float(szCs_val) / 2.0
                    logger.info("[DBG_FONT]   size step1 szCs=%.1f(pt) raw=%s", font_size, szCs_val)

        if font_size is None and hasattr(run._element, 'rPr'):
            sz_nodes = run._element.xpath('.//w:sz')
            sz_val = sz_nodes[0].get(qn('w:val')) if sz_nodes and sz_nodes[0].get(qn('w:val')) else None
            if sz_val:
                font_size = float(sz_val) / 2.0
                logger.info("[DBG_FONT]   size step2 sz=%.1f(pt) raw=%s", font_size, sz_val)

        if font_size is None and paragraph and paragraph.style and getattr(paragraph.style, 'font', None):
            try:
                style_size_obj = paragraph.style.font.size
                style_size_pt = float(style_size_obj.pt) if (style_size_obj and hasattr(style_size_obj, 'pt')) else None
                if style_size_pt:
                    font_size = style_size_pt
                    logger.info("[DBG_FONT]   size step3 para_style.font.size=%.1f(pt)", font_size)
            except Exception as e:
                logger.info("[DBG_FONT]   size step3 exception: %s", e)

        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style, 'element'):
            sz_nodes = paragraph.style.element.xpath('.//w:sz')
            sz_val = sz_nodes[0].get(qn('w:val')) if sz_nodes and sz_nodes[0].get(qn('w:val')) else None
            if sz_val:
                font_size = float(sz_val) / 2.0
                logger.info("[DBG_FONT]   size step4 para_style_xml sz=%.1f(pt) raw=%s", font_size, sz_val)

        if font_size is None and paragraph:
            para_sz_nodes = paragraph._element.xpath('.//w:sz')
            para_szCs_nodes = paragraph._element.xpath('.//w:szCs')
            para_szCs_val = para_szCs_nodes[0].get(qn('w:val')) if para_szCs_nodes and para_szCs_nodes[0].get(qn('w:val')) else None
            para_sz_val = para_sz_nodes[0].get(qn('w:val')) if para_sz_nodes and para_sz_nodes[0].get(qn('w:val')) else None
            if para_szCs_val:
                font_size = float(para_szCs_val) / 2.0
                logger.info("[DBG_FONT]   size step5 para_direct_xml szCs=%.1f(pt) raw=%s", font_size, para_szCs_val)
            elif para_sz_val:
                font_size = float(para_sz_val) / 2.0
                logger.info("[DBG_FONT]   size step5 para_direct_xml sz=%.1f(pt) raw=%s", font_size, para_sz_val)
    except Exception:
        pass

    # ---------- 字体名称（run XML + 段落样式 XML + 继承链 + docDefaults） ----------
    try:
        if run.font and run.font.name:
            font_ascii = run.font.name

        if hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                rfonts = rpr.find(qn('w:rFonts'))
                if rfonts is not None:
                    xml_ascii = rfonts.get(qn('w:ascii'))
                    xml_hansi = rfonts.get(qn('w:hAnsi'))
                    xml_eastasia = rfonts.get(qn('w:eastAsia'))

                    if xml_ascii:
                        font_ascii = xml_ascii
                    elif xml_hansi and font_ascii is None:
                        font_ascii = xml_hansi

                    if xml_eastasia:
                        font_eastasia = xml_eastasia
                    elif xml_hansi and font_eastasia is None:
                        font_eastasia = xml_hansi

        # 段落样式 XML
        if not font_ascii or not font_eastasia:
            if paragraph and paragraph.style and hasattr(paragraph.style, 'element'):
                rfonts_list = paragraph.style.element.xpath('.//w:rFonts')
                if rfonts_list:
                    rfonts = rfonts_list[0]
                    xml_ascii_s = rfonts.get(qn('w:ascii'))
                    xml_hansi_s = rfonts.get(qn('w:hAnsi'))
                    xml_eastasia_s = rfonts.get(qn('w:eastAsia'))
                    if not font_ascii:
                        if xml_ascii_s:
                            font_ascii = xml_ascii_s
                        elif xml_hansi_s:
                            font_ascii = xml_hansi_s
                    if not font_eastasia:
                        if xml_eastasia_s:
                            font_eastasia = xml_eastasia_s
                        elif xml_hansi_s:
                            font_eastasia = xml_hansi_s

        # 样式继承链追溯
        if (not font_ascii or not font_eastasia) and paragraph and paragraph.style and doc:
            inherited_props = get_inherited_style_properties(paragraph.style, doc)
            if not font_ascii and 'font_ascii' in inherited_props:
                font_ascii = inherited_props['font_ascii']
            if not font_eastasia:
                if 'font_east_asia' in inherited_props:
                    font_eastasia = inherited_props['font_east_asia']
                elif 'font_name' in inherited_props:
                    font_eastasia = inherited_props['font_name']

        # docDefaults 兜底
        if not font_ascii or not font_eastasia:
            if doc:
                doc_defaults = get_document_default_fonts(doc)
                if doc_defaults:
                    if not font_ascii:
                        font_ascii = doc_defaults.get('ascii') or doc_defaults.get('hAnsi')
                    if not font_eastasia:
                        font_eastasia = doc_defaults.get('east_asia') or doc_defaults.get('hAnsi')
    except Exception:
        pass

    font_ascii = font_ascii if font_ascii else "Times New Roman"
    font_eastasia = font_eastasia if font_eastasia else ""

    # ---------- 加粗（run API + 段落样式 API + run XML + 继承链） ----------
    try:
        if run.font and run.font.bold is not None:
            is_bold = run.font.bold
        if is_bold is None and paragraph and paragraph.style and getattr(paragraph.style, 'font', None):
            try:
                if paragraph.style.font.bold is not None:
                    is_bold = paragraph.style.font.bold
            except Exception:
                pass
        if is_bold is None and hasattr(run._element, 'rPr'):
            b_nodes = run._element.xpath('.//w:b')
            if b_nodes:
                v = b_nodes[0].get(qn('w:val'))
                is_bold = (v != '0') if v else True

        # 样式继承链追溯（加粗）
        if is_bold is None and paragraph and paragraph.style and doc:
            inherited_props = get_inherited_style_properties(paragraph.style, doc)
            if 'is_bold' in inherited_props:
                is_bold = inherited_props['is_bold']
    except Exception:
        pass

    is_bold = bool(is_bold) if is_bold is not None else False

    # ---------- 斜体（run API + 段落样式 API + run XML + 继承链） ----------
    try:
        if run.font and run.font.italic is not None:
            is_italic = run.font.italic
        if is_italic is None and paragraph and paragraph.style and getattr(paragraph.style, 'font', None):
            try:
                if paragraph.style.font.italic is not None:
                    is_italic = paragraph.style.font.italic
            except Exception:
                pass
        if is_italic is None and hasattr(run._element, 'rPr'):
            i_nodes = run._element.xpath('.//w:i')
            if i_nodes:
                v = i_nodes[0].get(qn('w:val'))
                is_italic = (v != '0') if v else True

        # 样式继承链追溯（斜体）
        if is_italic is None and paragraph and paragraph.style and doc:
            inherited_props = get_inherited_style_properties(paragraph.style, doc)
            if 'is_italic' in inherited_props:
                is_italic = inherited_props['is_italic']
    except Exception:
        pass

    is_italic = bool(is_italic) if is_italic is not None else False

    # ---------- 字号最终兜底：样式继承链 → docDefaults → expected_size_fallback ----------
    if font_size is None:
        inherited_size = None
        if paragraph and paragraph.style and doc:
            inherited_props = get_inherited_style_properties(paragraph.style, doc)
            inherited_size = inherited_props.get('font_size')

        doc_size = None
        if doc:
            doc_defaults = get_document_default_fonts(doc)
            if doc_defaults:
                doc_size = doc_defaults.get('font_size')

        font_size = inherited_size or doc_size or (expected_size_fallback if expected_size_fallback is not None else 12.0)
        src = ('继承链 ' + str(round(inherited_size, 1)) + 'pt') if inherited_size \
              else ('docDefaults ' + str(round(doc_size, 1)) + 'pt') if doc_size \
              else ('expected_size_fallback ' + str(round(expected_size_fallback, 1)) + 'pt') if expected_size_fallback \
              else 'hardcoded 12.0pt'
        logger.info("[DBG_FONT]   size fallback -> %s", src)

    return font_size, font_ascii, font_eastasia, is_bold, is_italic


def get_run_actual_color(run):
    """返回实际颜色值字符串，若无特殊颜色则返回 None"""
    try:
        if not hasattr(run, '_element'):
            return None
        rpr = run._element.rPr
        if rpr is None:
            return None
        color = rpr.find(qn('w:color'))
        if color is None:
            return None
        val = color.get(qn('w:val'))
        if val is None:
            return None
        if str(val).lower() in ['auto', '000000']:
            return None
        return str(val)
    except Exception:
        return None


def detect_run_color_is_default(run):
    """返回 True 表示未设置颜色或为自动/默认颜色。"""
    return get_run_actual_color(run) is None


def _debug_enabled(tpl, debug=None):
    if debug is not None:
        return bool(debug)
    return bool(tpl.get('check_rules', {}).get('debug', False))


def _strip_invisible(s: str) -> str:
    """去除零宽字符等不可见字符，避免正则匹配失败。"""
    if not s:
        return s
    return re.sub(r'[\u00A0\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]', '', s)

def get_text_from_w_t(paragraph):
    try:
        texts = paragraph._element.xpath('.//w:t/text()')
        if not texts:
            return ''
        return ''.join(texts)
    except Exception:
        return ''

def get_paragraph_visible_text(paragraph):
    """
    更稳地拿段落文本（兼容域/字段），同时尽量保留分隔信息：
    - 合并 w:instrText + w:t
    - 用空格拼接，避免 ''.join() 把分隔吞掉
    """
    try:
        parts = []
        # 域指令文本（有些编号会在这里）
        parts.extend(paragraph._element.xpath('.//w:instrText/text()'))
        # 普通文本
        parts.extend(paragraph._element.xpath('.//w:t/text()'))

        if not parts:
            return paragraph.text or ''

        # 用空格拼接，避免相邻 token 直接粘连导致正则匹配失败
        return ' '.join(p for p in parts if p is not None)
    except Exception:
        return paragraph.text or ''

def _strip_toc_page_num_suffix(text: str) -> str:
    """去掉类似目录项末尾的“\t页码”部分，例如：表 3-1 标题\t17"""
    if not text:
        return text
    return re.sub(r'\t\s*[0-9IVXLCDM]+\s*$', '', text, flags=re.IGNORECASE)


def _is_possible_table_caption_cn(text: str) -> bool:
    if not text:
        return False
    return ('表' in text) and any(ch.isdigit() for ch in text)


def _is_possible_table_caption_en(text: str) -> bool:
    if not text:
        return False
    t = _strip_invisible(text or '').strip().lower()
    # 检查是否以"table"开头（忽略大小写）
    return t.startswith('table')

def build_body_paragraph_index_map(doc):
    """
    建立 doc.element.body 的索引 -> doc.paragraphs 的索引映射。
    这样我们从 body 回溯到 w:p 时，能拿到对应的 paragraph 对象。
    """
    body_i_to_para_i = {}
    para_i = -1
    for body_i, el in enumerate(doc.element.body):
        if el.tag.endswith('p'):
            para_i += 1
            body_i_to_para_i[body_i] = para_i
    return body_i_to_para_i


def extract_tables_with_body_index(doc, body_p_map=None):
    """
    先枚举文档里所有表格（w:tbl），并记录：
    - table_body_index: 在 doc.element.body 的位置
    - table_paragraph_index: 表格在 doc.paragraphs 中的对应索引（用于引用搜索）
    - table_index: 在 doc.tables 中的位置
    - table: python-docx Table 对象

    table_paragraph_index 的计算方式：
    body_p_map 只映射 body 中 w:p 元素的索引 -> doc.paragraphs 索引。
    所以对于表格（w:tbl），需要找表格之后 body 中的第一个 w:p，
    再用 body_p_map 查出对应的 doc.paragraphs 索引。
    如果 body_p_map 为 None，则 table_paragraph_index 为 None。
    """
    items = []
    table_idx = -1
    body_elements = doc.element.body
    body_len = len(body_elements)

    for body_i, el in enumerate(body_elements):
        if el.tag.endswith('tbl'):
            table_idx += 1
            if table_idx < len(doc.tables):
                item = {
                    'table_body_index': body_i,
                    'table_index': table_idx,
                    'table': doc.tables[table_idx],
                }
                # 计算表格在 doc.paragraphs 中的对应索引：
                # 找表格之后 body 中的第一个 w:p，再用 body_p_map 查其对应的段落索引
                if body_p_map is not None:
                    next_p_body_i = None
                    for j in range(body_i + 1, body_len):
                        if body_elements[j].tag.endswith('p'):
                            next_p_body_i = j
                            break
                    if next_p_body_i is not None:
                        item['table_paragraph_index'] = body_p_map.get(next_p_body_i)
                items.append(item)
    return items


def attach_caption_to_table_item(doc, table_item, tpl, body_p_map, debug=None):
    """
    对单个表格：从表格上方回溯找 caption（中文/英文），并解析 chapter/seq/title。

    规则：
    - 从 table_body_index-1 往上找 w:p，最多找 N 个段落（默认 10，可从模板读）
    - 优先找最近的英文表题（Table...），找到后再向上找中文表题（表...）
    - 英文编号缺失时，用中文编号补齐（沿用你现有逻辑）
    """
    dbg = _debug_enabled(tpl or {}, debug)

    rules = tpl.get('table_detection_rules', {})
    cn_pat = rules.get('caption_cn_pattern',
                       r'^\s*表\s*(\d+)\s*(?:[-－]|\s+)\s*(\d+)\s*(.*?)\s*$')
    en_pat = rules.get(
    'caption_en_pattern',
    r'^\s*Table\s*(\d*)\s*[-－–\s]+\s*(\d*)\s*[:：]?\s*(.*?)\s*$'
)
    en_line_pat = r'^\s*Table\b(.*)$'

    max_back = int(rules.get('caption_search_back_paragraphs', 10))

    table_item['caption_cn_paragraph_index'] = None
    table_item['caption_en_paragraph_index'] = None
    table_item['caption_cn_paragraph'] = None
    table_item['caption_en_paragraph'] = None
    table_item['caption_cn_full_text'] = ''
    table_item['caption_en_full_text'] = ''
    table_item['chapter'] = None
    table_item['seq'] = None
    table_item['cn_title'] = ''
    table_item['en_title'] = ''

    # 从表格上方回溯找段落
    start = table_item['table_body_index'] - 1
    found_en = None  # (para_obj, para_index, text)
    found_cn = None  # (para_obj, para_index, text)

    back_count = 0
    body_i = start
    while body_i >= 0 and back_count < max_back:
        el = doc.element.body[body_i]
        if el.tag.endswith('p') and body_i in body_p_map:
            para_i = body_p_map[body_i]
            para = doc.paragraphs[para_i]
            raw = _strip_invisible((para.text or '').strip())

            if raw:
                text = _strip_toc_page_num_suffix(raw)
                text = re.sub(r'\s+', ' ', text).strip()
                # 先找英文（最近的）
                if found_en is None and _is_possible_table_caption_en(text):
                    # 先把“这行是英文表题行”识别出来（即使编号解析失败也算找到）
                    if re.match(en_line_pat, text, flags=re.IGNORECASE):
                        found_en = (para, para_i, text)

                    # 再尝试解析编号（解析成功就后面用；失败就允许为空）
                    m_en = re.match(en_pat, text, flags=re.IGNORECASE)
                    if not m_en:
                        # 备用：用 w:t 提取再试一次（只为尽量解析出编号）
                        xml_raw = _strip_invisible((''.join(para._element.xpath('.//w:t/text()')) or '').strip())
                        if xml_raw:
                            xml_text = _strip_toc_page_num_suffix(xml_raw)
                            xml_text = re.sub(r'\s+', ' ', xml_text).strip()
                            m_en = re.match(en_pat, xml_text, flags=re.IGNORECASE)
                            if m_en:
                                found_en = (para, para_i, xml_text)
                        
                # 中文表题：在英文表题下方紧挨着的第一个中文表题（如果有英文表题的话）
                # 注意：中文表题应该在英文表题之后、表格之前
                # 如果没有英文表题，则找最近的一个中文表题
                if _is_possible_table_caption_cn(text):
                    m_cn = re.match(cn_pat, text)
                    if m_cn:
                        if found_en is None:
                            # 还没找到英文，也先记住最近的中文（以防只有中文）
                            if found_cn is None:
                                found_cn = (para, para_i, text)
                        else:
                            # 已找到英文，找到第一个中文表题就停止
                            # 因为中文表题应该在英文表题之后
                            if found_cn is None:
                                found_cn = (para, para_i, text)
                                # 找到中文表题后停止搜索
                                if dbg:
                                    logger.info(
                                        "[Table] 找到英文表题后，在下方找到中文表题，停止搜索"
                                    )
                                break

                # 如果英文和中文都找到了，就停止
                if found_en is not None and found_cn is not None:
                    break

                back_count += 1

        body_i -= 1

    # 绑定 paragraph
    if found_cn is not None:
        table_item['caption_cn_paragraph'] = found_cn[0]
        table_item['caption_cn_paragraph_index'] = found_cn[1]
        table_item['caption_cn_full_text'] = found_cn[2]
    if found_en is not None:
        table_item['caption_en_paragraph'] = found_en[0]
        table_item['caption_en_paragraph_index'] = found_en[1]
        table_item['caption_en_full_text'] = found_en[2]

    # 解析中文
    cn_chapter = None
    cn_seq = None
    cn_title = ''
    is_continuation = False  # 标记是否为续表
    if found_cn is not None:
        m_cn = re.match(cn_pat, table_item['caption_cn_full_text'])
        if m_cn:
            try:
                cn_chapter = int(m_cn.group(1))
                cn_seq = int(m_cn.group(2))
                raw_title = (m_cn.group(3) or '').strip()
                # 检查是否是续表：表名末尾包含"（续）"
                if raw_title.endswith('（续）'):
                    is_continuation = True
                    cn_title = raw_title[:-3].strip()  # 去掉"（续）"
                else:
                    cn_title = raw_title
            except Exception:
                cn_chapter = None
                cn_seq = None

    table_item['is_continuation'] = is_continuation

    # 解析英文（允许编号缺失）
    en_chapter = None
    en_seq = None
    en_title = ''
    if found_en is not None:
        m_en = re.match(en_pat, table_item['caption_en_full_text'], flags=re.IGNORECASE)
        if m_en:
            en_chapter_raw = (m_en.group(1) or '').strip()
            en_seq_raw = (m_en.group(2) or '').strip()
            en_title = (m_en.group(3) or '').strip()

            if en_chapter_raw:
                try:
                    en_chapter = int(en_chapter_raw)
                except Exception:
                    en_chapter = None
            if en_seq_raw:
                try:
                    en_seq = int(en_seq_raw)
                except Exception:
                    en_seq = None
    table_item['_en_number_parsed'] = bool(en_chapter is not None and en_seq is not None)
    # 补齐编号：优先用中文
    final_chapter = cn_chapter if cn_chapter is not None else en_chapter
    final_seq = cn_seq if cn_seq is not None else en_seq

    # 如果英文缺失但中文有，则补齐到英文（用于后续一致性判断/报告）
    if en_chapter is None:
        en_chapter = final_chapter
    if en_seq is None:
        en_seq = final_seq

    table_item['chapter'] = final_chapter
    table_item['seq'] = final_seq
    table_item['cn_title'] = cn_title
    table_item['en_title'] = en_title

    # 另外存一下英文解析出的 chapter/seq（便于一致性检查）
    table_item['_en_chapter'] = en_chapter
    table_item['_en_seq'] = en_seq

    if dbg:
        logger.info(
            "[Table] 表格(table_index=%s, body_index=%s) 回溯结果: CN_idx=%s EN_idx=%s chapter=%s seq=%s",
            table_item.get('table_index'),
            table_item.get('table_body_index'),
            table_item.get('caption_cn_paragraph_index'),
            table_item.get('caption_en_paragraph_index'),
            table_item.get('chapter'),
            table_item.get('seq'),
        )

    return table_item


def detect_paragraph_alignment(paragraph):
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

    # 段落和样式都没有显式对齐，说明对齐由 Word 默认行为决定
    # 硬编码返回 0（左对齐），这是一个近似值
    return 0


def check_caption_text_rules(table_item, tpl):
    """检查中英文表题文本规则：编号一致、中文表题不含标点等（基于 table_item）"""
    report = {'ok': True, 'messages': []}
    messages = tpl.get('messages', {})

    cn_para = table_item.get('caption_cn_paragraph')
    en_para = table_item.get('caption_en_paragraph')
    is_continuation = table_item.get('is_continuation', False)
    en_check = tpl.get('check_rules', {}).get('caption_en_check', True)

    # 续表允许没有英文表题
    if cn_para is None:
        report['ok'] = False
        report['messages'].append(messages.get('caption_missing_cn', '未找到中文表题'))
    if en_para is None and not is_continuation and en_check:
        report['ok'] = False
        report['messages'].append(messages.get('caption_missing_en', '未找到英文表题'))

    # 如果都没有，就没必要继续
    if cn_para is None and en_para is None:
        return report

    # 编号一致性：只有在两者都有时比较
    cn_ch = table_item.get('chapter')
    cn_seq = table_item.get('seq')
    en_ch = table_item.get('_en_chapter')
    en_seq = table_item.get('_en_seq')

    if cn_para is not None and en_para is not None:
        # 中文编号是权威：中文解析不到才算格式错误
        if cn_ch is None or cn_seq is None:
            report['ok'] = False
            report['messages'].append(messages.get('caption_pattern_error', '表格标题格式不符合要求'))
        else:
            # 英文编号能解析出来就比对；解析不出来就跳过比对（不报错）
            if en_ch is not None and en_seq is not None:
                if cn_ch != en_ch or cn_seq != en_seq:
                    report['ok'] = False
                    msg = messages.get('caption_number_mismatch_error', '中英文表序不一致')
                    report['messages'].append(f"{msg}：中文为表{cn_ch}-{cn_seq}，英文为Table {en_ch}-{en_seq}")

    # 中文表题禁用标点
    cn_title = table_item.get('cn_title', '') or ''
    punctuation_pat = tpl.get('table_detection_rules', {}).get(
        'caption_cn_forbidden_punct_pattern',
        r'[，。；：、？！……—（）【】《》“”‘’,.!?;:()\[\]{}]'
    )
    if cn_title and re.search(punctuation_pat, cn_title):
        report['ok'] = False
        report['messages'].append(messages.get('caption_cn_punct_error', '中文表题中不允许出现标点符号'))

    return report


def check_caption_format(paragraph, expected, tpl, language='cn', doc=None):
    """
    检查表格标题格式
    参数:
        paragraph: 标题段落
        expected: 期望格式
        tpl: 模板对象
        language: 'cn' 或 'en'
        doc: docx文档对象（用于读取样式继承链和docDefaults）
    """
    report = {'ok': True, 'messages': []}

    messages = tpl.get('messages', {})

    non_empty_runs = [r for r in paragraph.runs if (r.text or '').strip()]
    if not non_empty_runs:
        report['ok'] = False
        report['messages'].append("表题段落没有有效文本")
        return report

    # 遍历所有 run 检测字体属性，取众数（最常见的值）
    from collections import Counter
    size_values = []
    eastasia_values = []
    ascii_values = []
    bold_values = []
    italic_values = []
    expected_size_pt = expected.get('font_size_pt')
    for r in non_empty_runs:
        sz, fa, fe, bd, italic = detect_font_for_run(r, paragraph, doc, expected_size_fallback=expected_size_pt)
        size_values.append(sz)
        if fe:
            eastasia_values.append(fe)
        if fa:
            ascii_values.append(fa)
        bold_values.append(bd)
        italic_values.append(italic)
        logger.info(
            "[DBG_FONT] run text=%r size=%.2f eastAsia=%r ascii=%r bold=%r italic=%r",
            r.text, sz, fe, fa, bd, italic,
        )

    # 字号：取出现次数最多的值
    size_counter = Counter(size_values)
    size_pt = size_counter.most_common(1)[0][0]
    logger.info("[DBG_FONT] lang=%s para=%r | all_sizes=%s | size_mode=%.2f (count=%d)",
        language, (paragraph.text or '')[:30], dict(size_counter), size_pt, size_counter[size_pt])

    # 字体：中文字体取众数（仅统计有值的）
    font_eastasia = ""
    if eastasia_values:
        ea_counter = Counter(eastasia_values)
        font_eastasia = ea_counter.most_common(1)[0][0]
    font_ascii = "Times New Roman"
    if ascii_values:
        fa_counter = Counter(ascii_values)
        font_ascii = fa_counter.most_common(1)[0][0]

    # 加粗：任意一个 run 加粗则视为加粗（更严格）
    is_bold = any(bold_values)
    if not should_skip_check('font_size'):
        expected_size = float(expected.get('font_size_pt', 10.5))
        if abs(size_pt - expected_size) > 0.5:
            report['ok'] = False
            if language == 'cn':
                report['messages'].append(f'中文表题字号应为{_get_font_size_name(expected_size)}({expected_size}pt)，实际为{_get_font_size_name(size_pt)}({size_pt}pt)')
            else:
                report['messages'].append(f'英文表题字号应为{_get_font_size_name(expected_size)}({expected_size}pt)，实际为{_get_font_size_name(size_pt)}({size_pt}pt)')

    if not should_skip_check('font_name'):
        if language == 'cn':
            expected_cn_font = expected.get('font_name_eastasia')
            if expected_cn_font:
                # 关键：eastAsia 读不到时，不判错（否则会大量误报）
                if not font_eastasia:
                    # 可选：如果你想在报告里提示“读不到字体已跳过”
                    # report['messages'].append("中文表题字体信息无法读取，已跳过字体检查")
                    pass
                else:
                    if expected_cn_font.lower() not in (font_eastasia or '').lower():
                        report['ok'] = False
                        report['messages'].append(f"中文表题字体应为{expected_cn_font}，实际为{font_eastasia or '未设置'}")
        else:
            expected_en_font = expected.get('font_name_ascii')
            if expected_en_font and expected_en_font.lower() not in (font_ascii or '').lower():
                report['ok'] = False
                report['messages'].append(f"英文表题字体应为{expected_en_font}，实际为{font_ascii or '未设置'}")

    if not should_skip_check('bold') and 'bold' in expected:
        expected_bold = bool(expected.get('bold'))
        if is_bold != expected_bold:
            report['ok'] = False
            if language == 'cn':
                report['messages'].append(f"中文表题{'应加粗' if expected_bold else '应不加粗'}，实际为{'加粗' if is_bold else '不加粗'}")
            else:
                report['messages'].append(f"英文表题{'应加粗' if expected_bold else '应不加粗'}，实际为{'加粗' if is_bold else '不加粗'}")

    if not should_skip_check('italic') and 'italic' in expected:
        is_italic = any(italic_values)
        expected_italic = bool(expected.get('italic'))
        if is_italic != expected_italic:
            report['ok'] = False
            if language == 'cn':
                report['messages'].append(f"中文表题{'应为斜体' if expected_italic else '应不为斜体'}，实际为{'斜体' if is_italic else '非斜体'}")
            else:
                report['messages'].append(f"英文表题{'应为斜体' if expected_italic else '应不为斜体'}，实际为{'斜体' if is_italic else '非斜体'}")

    if not should_skip_check('color') and expected.get('no_special_color', True):
        # 颜色：任意一个 run 有特殊颜色则报错
        colored_runs = [r for r in non_empty_runs if not detect_run_color_is_default(r)]
        if colored_runs:
            report['ok'] = False
            actual_color = get_run_actual_color(colored_runs[0])
            if language == 'cn':
                report['messages'].append(f"中文表题应为无特殊颜色，实际为{'#' + actual_color if actual_color else '默认/无特殊颜色'}")
            else:
                report['messages'].append(f"英文表题应为无特殊颜色，实际为{'#' + actual_color if actual_color else '默认/无特殊颜色'}")

    if not should_skip_check('alignment') and expected.get('alignment'):
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        exp = alignment_map.get(str(expected.get('alignment')).lower())
        if exp is not None:
            actual = detect_paragraph_alignment(paragraph)
            raw_direct = paragraph.paragraph_format.alignment
            raw_style = paragraph.style.paragraph_format.alignment if paragraph.style else None
            logger.info("[DBG_ALIGN] lang=%s para=%r | direct=%r style=%r | expected=%s actual=%s",
                language, (paragraph.text or '')[:30], raw_direct, raw_style, exp, actual)
            # 当 direct 和 style 都没有显式对齐时，说明对齐由 Word 默认行为决定
            # 无法通过 XML 确定，跳过检查以避免误报
            if raw_direct is not None or raw_style is not None:
                if actual != exp:
                    report['ok'] = False
                    alignment_name_map = {0: "左对齐", 1: "居中对齐", 2: "右对齐", 3: "两端对齐"}
                    alignment_int_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
                    exp_raw = alignment_int_map.get(str(expected.get('alignment')).lower() if expected.get('alignment') else '', None)
                    exp = alignment_name_map.get(exp_raw, '未知') if exp_raw is not None else '未知'
                    act = alignment_name_map.get(actual, '未知')
                    report['messages'].append(f'表题对齐应为{exp}，实际为{act}')

    return report


def check_table_content_alignment(table, tpl):
    """
    检查表格内容的对齐方式
    规则：
    - 表头行（第一行）：居中对齐
    - 内容行：根据长度判断，较长文本（>阈值）左对齐，较短文本居中对齐
    """
    issues = []
    messages = tpl.get('messages', {})
    check_rules = tpl.get('check_rules', {})

    # 检查是否启用内容对齐检查
    content_alignment_check = check_rules.get('table_content_alignment_check', True)
    if not content_alignment_check:
        return True, [], {'skipped': True}

    length_threshold = check_rules.get('alignment_length_threshold', 20)
    content_alignment_rules = tpl.get('table_detection_rules', {}).get('content_alignment', {})

    expected_header_align = content_alignment_rules.get('header_row', 'center')
    expected_long_align = content_alignment_rules.get('content_long', 'left')
    expected_short_align = content_alignment_rules.get('content_short', 'center')

    if not table:
        return False, [messages.get('table_not_found', '未找到表格对象')], {}

    try:
        # 获取表格行和列
        rows = list(table.rows)
        if len(rows) < 2:
            return True, [], {'skipped': True}  # 只有表头或无内容，跳过

        # 对齐方式映射
        align_map = {
            'left': 0,
            'center': 1,
            'right': 2,
            'justify': 3
        }

        header_row = rows[0]
        content_rows = rows[1:]

        header_issues = []
        content_issues = []

        # 检查表头行对齐
        for cell in header_row.cells:
            cell_para = cell.paragraphs[0] if cell.paragraphs else None
            if cell_para:
                cell_align = detect_paragraph_alignment(cell_para)
                expected_align = align_map.get(expected_header_align, 1)
                if cell_align != expected_align:
                    header_issues.append(cell)
                    break

        if header_issues:
            issues.append(messages.get('table_header_alignment_error', '表头行应居中对齐'))

        # 检查内容行对齐
        for row in content_rows:
            for cell in row.cells:
                cell_para = cell.paragraphs[0] if cell.paragraphs else None
                if cell_para:
                    cell_text = cell_para.text.strip()
                    # 判断文本长度
                    if len(cell_text) > length_threshold:
                        # 较长文本，应左对齐
                        cell_align = detect_paragraph_alignment(cell_para)
                        expected_align = align_map.get(expected_long_align, 0)
                        if cell_align != expected_align:
                            content_issues.append(cell)
                            break
                    elif cell_text:  # 非空文本
                        # 较短文本，应居中对齐
                        cell_align = detect_paragraph_alignment(cell_para)
                        expected_align = align_map.get(expected_short_align, 1)
                        if cell_align != expected_align:
                            content_issues.append(cell)
                            break
            if content_issues:
                break

        if content_issues:
            if length_threshold > 0:
                issues.append(messages.get('table_content_long_error', f'内容行（>{length_threshold}字符）应{expected_long_align}对齐'))
            else:
                issues.append(messages.get('table_content_short_error', f'内容行（≤{length_threshold}字符）应{expected_short_align}对齐'))

        ok = len(issues) == 0
        detected = {
            'header_row_count': 1,
            'content_row_count': len(content_rows),
            'header_issues_count': len(header_issues),
            'content_issues_count': len(content_issues),
            'expected_header_align': expected_header_align,
            'expected_long_align': expected_long_align,
            'expected_short_align': expected_short_align,
            'length_threshold': length_threshold
        }
        return ok, issues, detected

    except Exception as e:
        return False, [f"表格内容对齐检测异常: {str(e)}"], {}


def check_table_reference(table_item, doc, tpl):
    """
    检查表格是否在文档中被引用
    在表格上方和下方的一定范围内查找引用文本
    支持中文引用格式：表3-1、见表格3-1、如下表3-1等
    """
    report = {'ok': True, 'messages': [], 'reference_found': False, 'reference_text': ''}
    messages = tpl.get('messages', {})
    check_rules = tpl.get('check_rules', {})

    reference_check = check_rules.get('table_reference_check', True)
    if not reference_check:
        return report

    if table_item.get('is_continuation', False):
        return report

    chapter = table_item.get('chapter')
    seq = table_item.get('seq')

    if chapter is None or seq is None:
        return report

    # 优先使用 table_paragraph_index（直接对应 doc.paragraphs 的索引），
    # 降级使用 table_body_index（仅当表格是 body 中第一个元素时才正确）
    table_para_index = table_item.get('table_paragraph_index')
    if table_para_index is None:
        # 降级：使用 body_index，但需要注意 doc.paragraphs 长度可能小于 table_body_index
        table_para_index = table_item.get('table_body_index')

    if table_para_index is None:
        return report

    connector_chars = r'[-－.．]'

    ref_patterns = [
        rf'表\s*{chapter}\s*{connector_chars}\s*{seq}',
        rf'表格\s*{chapter}\s*{connector_chars}\s*{seq}',
        rf'下表\s*{chapter}\s*{connector_chars}\s*{seq}',
        rf'上表\s*{chapter}\s*{connector_chars}\s*{seq}',
        rf'见表\s*{chapter}\s*{connector_chars}\s*{seq}',
        rf'如表\s*{chapter}\s*{connector_chars}\s*{seq}',
    ]

    search_range = 10
    # table_para_index 是表格在 doc.paragraphs 中的对应位置，
    # 所以 skip 时应该用 table_para_index 而非 table_body_index
    skip_index = table_para_index
    total_paragraphs = len(doc.paragraphs)
    start_idx = max(0, table_para_index - search_range)
    end_idx = min(total_paragraphs, table_para_index + search_range + 1)

    for i in range(start_idx, end_idx):
        if i == skip_index:
            continue

        para = doc.paragraphs[i]
        text = _strip_invisible((''.join(para._element.xpath('.//w:t/text()')) or '').strip())

        if not text:
            continue

        found_ref = False
        matched = ''
        for pattern in ref_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found_ref = True
                matched = match.group(0)
                break

        if found_ref:
            report['reference_found'] = True
            report['reference_text'] = matched
            return report

    report['ok'] = False
    msg_tpl = messages.get('table_reference_error', '表格引用检测未通过（如：表{chapter}-{seq}）').format(chapter=chapter, seq=seq)
    report['messages'].append(msg_tpl)
    return report


def check_table_style_three_line(table, tpl):
    issues = []
    messages = tpl.get('messages', {})

    if not table:
        return False, [messages.get('table_not_found', '未找到表格对象')]

    try:
        tbl = table._element
        tblPr = tbl.find(qn('w:tblPr'))
        if tblPr is None:
            return False, ["表格缺少格式属性"]

        tblBorders = tblPr.find(qn('w:tblBorders'))

        # 表级别边框检查（左右边线和内部竖线）
        if tblBorders is not None:
            left_border = tblBorders.find(qn('w:left'))
            right_border = tblBorders.find(qn('w:right'))
            inside_v = tblBorders.find(qn('w:insideV'))
            inside_h = tblBorders.find(qn('w:insideH'))

            if left_border is not None and not _border_val_none_or_nil(left_border.get(qn('w:val'))):
                issues.append("表格不应有左边框（三线表格式）")
            if right_border is not None and not _border_val_none_or_nil(right_border.get(qn('w:val'))):
                issues.append("表格不应有右边框（三线表格式）")
            if inside_v is not None and not _border_val_none_or_nil(inside_v.get(qn('w:val'))):
                issues.append("表格不应有内部竖线（三线表格式）")
            # 内部水平线（insideH）也不应出现（三线表只有表头底线，内部不应有水平分隔线）
            if inside_h is not None and not _border_val_none_or_nil(inside_h.get(qn('w:val'))):
                issues.append("表格内部不应有水平分隔线（三线表格式）")

        # 单元格级别边框检查：遍历所有单元格，确保没有多余的边线
        # 注意：三线表允许第一行顶边和第一行底边（表头底线），这些由表级别 tblBorders 控制
        for row_idx, row in enumerate(table.rows):
            for cell in row.cells:
                tc = cell._element
                tcPr = tc.find(qn('w:tcPr'))
                if tcPr is None:
                    continue
                tcBorders = tcPr.find(qn('w:tcBorders'))
                if tcBorders is None:
                    continue
                # 检查左右边线（任何行都不应有左右边线）
                for side, side_name in [
                    (qn('w:left'), '左边框'),
                    (qn('w:right'), '右边框'),
                ]:
                    border_el = tcBorders.find(side)
                    if border_el is not None and not _border_val_none_or_nil(border_el.get(qn('w:val'))):
                        issues.append(f"表格单元格不应有{side_name}（三线表格式）")
                        break  # 该单元格已报错，跳过其他边（避免同一单元格重复报错）

        if tpl.get('check_rules', {}).get('border_width_check', False):
            border_config = tpl.get('table_detection_rules', {}).get('table_style', {}).get('border_width', {})
            tolerance = tpl.get('check_rules', {}).get('border_width_tolerance', 0.1)

            expected_top = float(border_config.get('top_line', 1.5))
            expected_bottom = float(border_config.get('bottom_line', 1.5))
            expected_header = float(border_config.get('header_line', 0.75))

            top_msg_template = messages.get('top_border_width_error', f'顶线宽度应为{expected_top}磅，实际为{{actual}}磅')
            header_msg_template = messages.get('header_border_width_error', f'表头底线宽度应为{expected_header}磅，实际为{{actual}}磅')
            bottom_msg_template = messages.get('bottom_border_width_error', f'底线宽度应为{expected_bottom}磅，实际为{{actual}}磅')

            border_width_issues = []

            # 顶线：从第一行第一列的单元格顶边获取（使用表级别 tblBorders 的 top）
            tbl_top_border = None
            if tblBorders is not None:
                tbl_top_border = tblBorders.find(qn('w:top'))
            # 如果表级别没有顶线，再从单元格级别获取
            if tbl_top_border is None or _border_val_none_or_nil(tbl_top_border.get(qn('w:val'))):
                if len(table.rows) > 0 and len(table.rows[0].cells) > 0:
                    tc = table.rows[0].cells[0]._element
                    tcPr = tc.find(qn('w:tcPr'))
                    if tcPr is not None:
                        tcBorders = tcPr.find(qn('w:tcBorders'))
                        if tcBorders is not None:
                            tbl_top_border = tcBorders.find(qn('w:top'))
            if tbl_top_border is not None:
                sz = tbl_top_border.get(qn('w:sz'))
                if sz:
                    actual_width = float(sz) / 8.0
                    if abs(actual_width - expected_top) > tolerance:
                        border_width_issues.append(top_msg_template.format(actual=round(actual_width, 2)))

            # 表头底线（第一行底边）
            header_bottom_border = None
            if tblBorders is not None:
                header_bottom_border = tblBorders.find(qn('w:insideH'))
            if header_bottom_border is None or _border_val_none_or_nil(header_bottom_border.get(qn('w:val'))):
                if len(table.rows) > 0 and len(table.rows[0].cells) > 0:
                    tc = table.rows[0].cells[0]._element
                    tcPr = tc.find(qn('w:tcPr'))
                    if tcPr is not None:
                        tcBorders = tcPr.find(qn('w:tcBorders'))
                        if tcBorders is not None:
                            header_bottom_border = tcBorders.find(qn('w:bottom'))
            if header_bottom_border is not None:
                sz = header_bottom_border.get(qn('w:sz'))
                if sz:
                    actual_width = float(sz) / 8.0
                    if abs(actual_width - expected_header) > tolerance:
                        border_width_issues.append(header_msg_template.format(actual=round(actual_width, 2)))

            # 底线（最后一行底边）
            tbl_bottom_border = None
            if tblBorders is not None:
                tbl_bottom_border = tblBorders.find(qn('w:bottom'))
            if tbl_bottom_border is None or _border_val_none_or_nil(tbl_bottom_border.get(qn('w:val'))):
                if len(table.rows) > 0 and len(table.rows[-1].cells) > 0:
                    tc = table.rows[-1].cells[0]._element
                    tcPr = tc.find(qn('w:tcPr'))
                    if tcPr is not None:
                        tcBorders = tcPr.find(qn('w:tcBorders'))
                        if tcBorders is not None:
                            tbl_bottom_border = tcBorders.find(qn('w:bottom'))
            if tbl_bottom_border is not None:
                sz = tbl_bottom_border.get(qn('w:sz'))
                if sz:
                    actual_width = float(sz) / 8.0
                    if abs(actual_width - expected_bottom) > tolerance:
                        border_width_issues.append(bottom_msg_template.format(actual=round(actual_width, 2)))

            issues.extend(border_width_issues)

        # 去重，避免同一问题被多次报告
        unique_issues = list(dict.fromkeys(issues))
        return len(unique_issues) == 0, unique_issues

    except Exception as e:
        return False, [f"表格样式检测异常: {str(e)}"]


def check_table_numbering_by_chapter(table_items, tpl):
    report = {'ok': True, 'messages': []}
    messages = tpl.get('messages', {})
    check_rules = tpl.get('check_rules', {})
    numbering_check = bool(check_rules.get('caption_numbering_check', True))

    if not table_items:
        return report

    chapter_to_seqs = {}
    for item in table_items:
        # 跳过续表：续表不计入编号连续性检查
        if item.get('is_continuation', False):
            continue
        ch = item.get('chapter')
        seq = item.get('seq')
        if ch is None or seq is None:
            continue
        # 存储 (seq, item_ref) 以便报告
        chapter_to_seqs.setdefault(ch, []).append({'seq': seq, 'item': item})

    for ch, seq_items in chapter_to_seqs.items():
        if not seq_items:
            continue
        seq_items_sorted = sorted(seq_items, key=lambda x: x['seq'])
        seqs = [s['seq'] for s in seq_items_sorted]

        # 检查是否从1开始
        if seqs[0] != 1:
            report['ok'] = False
            report['messages'].append(f"第{ch}章的表序号应从1开始，当前从{seqs[0]}开始")

        if numbering_check:
            # 检查连续性
            missing_seqs = []
            for i in range(len(seqs) - 1):
                current = seqs[i]
                next_seq = seqs[i + 1]
                if next_seq - current > 1:
                    # 找出缺失的序号
                    for missing in range(current + 1, next_seq):
                        missing_seqs.append(missing)

            if missing_seqs:
                report['ok'] = False
                # 生成缺失的表标识列表
                missing_tables = [f"表{ch}-{s}" for s in missing_seqs]
                report['messages'].append(f"第{ch}章缺失表序号：{', '.join(missing_tables)}")

    return report


def check_doc_with_template(doc_path, template_identifier, skip_checks=None, debug=None, log_file_path=None):
    global _skip_checks_config
    _skip_checks_config = skip_checks or []

    tpl = load_template(template_identifier)
    dbg = _debug_enabled(tpl, debug)
    if dbg:
        logger.info("[Table] 开始表格检测(新逻辑: 先找表): doc=%s, template=%s", doc_path, template_identifier)

    doc = Document(doc_path)
    messages = tpl.get('messages', {})

    body_p_map = build_body_paragraph_index_map(doc)
    table_items = extract_tables_with_body_index(doc, body_p_map)

    report = {
        'table_detection': {'ok': True, 'messages': []},
        'numbering': {},
        'tables': [],
        'summary': [],
        'details': {
            'total_tables': len(table_items),
            'debug': dbg
        }
    }

    if not table_items:
        report['table_detection']['ok'] = False
        report['table_detection']['messages'].append(messages.get('table_not_found', '未找到表格对象'))
        report['summary'].append(messages.get('table_detection_error', '表格格式检查发现问题'))
        return report

    # 为每个表格回溯绑定表题
    for item in table_items:
        attach_caption_to_table_item(doc, item, tpl, body_p_map, debug=dbg)
    # 中英文表题都未找到：不视为论文中的表格，直接跳过不检测不报告
    table_items = [
        item for item in table_items
        if not (item.get('caption_cn_paragraph') is None and item.get('caption_en_paragraph') is None)
    ]
    
    # 去重：基于中文表题段落索引去重，避免同一表题绑定多个表格导致重复识别
    # 如果多个表格绑定到同一个中文表题段落，只保留第一个
    seen_cn_caption_indices = set()
    unique_table_items = []
    for item in table_items:
        cn_idx = item.get('caption_cn_paragraph_index')
        if cn_idx is not None:
            if cn_idx in seen_cn_caption_indices:
                if dbg:
                    logger.info(
                        "[Table] 跳过重复表格: table_index=%s, body_index=%s, cn_para_idx=%s, table_desc=%s",
                        item.get('table_index'),
                        item.get('table_body_index'),
                        cn_idx,
                        f"表{item.get('chapter')}-{item.get('seq')}" if item.get('chapter') and item.get('seq') else "表格"
                    )
                continue
            seen_cn_caption_indices.add(cn_idx)
        unique_table_items.append(item)
    table_items = unique_table_items
    
    if dbg:
        logger.info(f"[Table] 去重后表格数量: {len(table_items)}")
    # 按章编号连续性
    numbering_report = check_table_numbering_by_chapter(table_items, tpl)
    report['numbering'] = numbering_report
    if not numbering_report.get('ok', True):
        report['table_detection']['ok'] = False

    # 逐表检查
    expected_cn = tpl.get('format_rules', {}).get('caption_cn', {})
    expected_en = tpl.get('format_rules', {}).get('caption_en', {})
    check_rules = tpl.get('check_rules', {})

    for item in table_items:
        cn_para = item.get('caption_cn_paragraph')
        en_para = item.get('caption_en_paragraph')

        text_rules = check_caption_text_rules(item, tpl)

        # 格式检查：缺失就直接报错，不传 None
        if cn_para is None:
            cn_format = {'ok': False, 'messages': [messages.get('caption_missing_cn', '未找到中文表题')]}
        else:
            cn_format = check_caption_format(cn_para, expected_cn, tpl, language='cn', doc=doc)

        en_check = check_rules.get('caption_en_check', True)
        if en_check and en_para is not None:
            en_format = check_caption_format(en_para, expected_en, tpl, language='en', doc=doc)
        elif en_check and en_para is None:
            en_format = {'ok': False, 'messages': [messages.get('caption_missing', '未找到英文表题')]}
        else:
            en_format = {'ok': True, 'messages': []}

        table = item.get('table')
        has_table = table is not None

        if not has_table:
            style_ok, style_issues = False, [messages.get('table_not_found', '未找到表格对象')]
        else:
            style_ok, style_issues = check_table_style_three_line(table, tpl)

        en_check = check_rules.get('caption_en_check', True)
        en_ok = en_format['ok'] if en_check else True
        table_item_ok = text_rules['ok'] and cn_format['ok'] and en_ok and has_table and style_ok
        if not table_item_ok:
            report['table_detection']['ok'] = False

        # 组织输出（你可以按需要改字段）
        table_desc = None
        if item.get('chapter') is not None and item.get('seq') is not None:
            cn_title = item.get('cn_title', '')
            if item.get('is_continuation', False):
                table_desc = f"表{item.get('chapter')}-{item.get('seq')}{cn_title}（续）"
            else:
                table_desc = f"表{item.get('chapter')}-{item.get('seq')}{cn_title}"
        else:
            table_desc = f"表格(table_index={item.get('table_index')})"

        out_item = {
            'table_ref': {
                'table_index': item.get('table_index'),
                'table_body_index': item.get('table_body_index'),
            },
            'table_desc': table_desc,  # 添加表格描述（包含续表标记）
            'captions': {
                'cn': {
                    'paragraph_index': item.get('caption_cn_paragraph_index'),
                    'chapter': item.get('chapter'),
                    'seq': item.get('seq'),
                    'title': item.get('cn_title') + ('（续）' if item.get('is_continuation', False) else ''),
                    'full_text': item.get('caption_cn_full_text'),
                },
                'en': {
                    'paragraph_index': item.get('caption_en_paragraph_index'),
                    'chapter': item.get('chapter'),
                    'seq': item.get('seq'),
                    'title': item.get('en_title'),
                    'full_text': item.get('caption_en_full_text'),
                }
            },
            'text_rules': text_rules,
            'caption_cn_format': cn_format,
            'caption_en_format': en_format,
            'table_object': has_table,
            'table_style': {
                'ok': style_ok,
                'messages': style_issues
            }
        }

        # 添加表格内容对齐检查（续表跳过）
        if has_table and not item.get('is_continuation', False):
            content_align_ok, content_align_issues, content_align_detected = check_table_content_alignment(table, tpl)
            out_item['table_content_alignment'] = {
                'ok': content_align_ok,
                'messages': content_align_issues,
                'detected': content_align_detected
            }
            if not content_align_ok:
                table_item_ok = False
        else:
            out_item['table_content_alignment'] = {'skipped': True}

        # 添加表格引用检查
        ref_report = check_table_reference(item, doc, tpl)
        out_item['table_reference'] = {
            'ok': ref_report['ok'],
            'messages': ref_report['messages'] if not ref_report['ok'] else []
        }
        if not ref_report['ok']:
            table_item_ok = False

        report['tables'].append(out_item)

        # 收集所有问题消息
        all_issues = []
        for msg in text_rules.get('messages', []):
            if not text_rules.get('ok', True):
                all_issues.append(msg)
        for msg in cn_format.get('messages', []):
            if not cn_format.get('ok', True):
                all_issues.append(msg)
        for msg in en_format.get('messages', []):
            if not en_format.get('ok', True):
                all_issues.append(msg)
        for msg in style_issues:
            all_issues.append(msg)
        for msg in out_item.get('table_content_alignment', {}).get('messages', []):
            if not out_item.get('table_content_alignment', {}).get('ok', True):
                all_issues.append(msg)
        for msg in out_item.get('table_reference', {}).get('messages', []):
            if not out_item.get('table_reference', {}).get('ok', True):
                all_issues.append(msg)

        if not table_item_ok:
            # 添加表格标识和概要
            report['table_detection']['messages'].append(f"{table_desc} {messages.get('table_detection_error', '表格格式检查发现问题')}")
            # 添加具体问题
            for msg in all_issues:
                report['table_detection']['messages'].append(f"  - {msg}")

    summary_tpl = messages.get('summary_overall', '表格格式检查结果: {ok}')
    report['summary'].append(summary_tpl.format(ok='通过' if report['table_detection']['ok'] else '发现问题'))

    count_tpl = messages.get('table_count', '检测到 {count} 个表格')
    report['summary'].append(count_tpl.format(count=len(table_items)))

    return report

def print_help():
    print("用法:")
    print("  python Table_detect.py check <paper.docx> <template.json_or_name>")


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
            report = check_doc_with_template(paper_path, tpl_id, debug=True)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        except Exception as e:
            print("检查时出错:", e)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print_help()
        sys.exit(0)
