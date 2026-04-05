#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import xml.etree.ElementTree as ET
import logging
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)



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


def get_font_size(pt_size, tpl=None):
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


def detect_font_for_run(run, paragraph=None):
    """检测 run 的字号、字体、加粗"""
    font_source = run.font if run else (paragraph.style.font if paragraph else None)
    if not font_source:
        return 12.0, "Unknown", False, False

    # 优先从 XML 中读取字体信息（更准确）
    font_name = "Unknown"
    try:
        if hasattr(run, '_element') and hasattr(run._element, 'rPr'):
            rpr = run._element.rPr
            if rpr is not None:
                rFonts = rpr.find('.//w:rFonts')
                if rFonts is not None:
                    # 检查所有可能的字体属性
                    for attr in ['w:cambriaMath', 'w:ascii', 'w:eastAsia', 'w:hAnsi', 'w:cs']:
                        val = rFonts.get(qn(attr))
                        if val:
                            font_name = val
                            # 如果找到 cambria 相关的字体，优先使用
                            if 'cambria' in val.lower():
                                break
    except Exception:
        pass

    # 如果 XML 中没有获取到，fallback 到 API
    if font_name == "Unknown":
        font_name = font_source.name if font_source.name else "Times New Roman"

    font_size = None
    try:
        if run and run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)

        if font_size is None and hasattr(run._element, 'rPr'):
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

    is_bold = font_source.bold if font_source.bold is not None else False
    is_italic = font_source.italic if font_source.italic is not None else False
    if run and run.font:
        is_bold = run.font.bold if run.font.bold is not None else is_bold
        is_italic = run.font.italic if run.font.italic is not None else is_italic

    is_bold = bool(is_bold) if is_bold is not None else False
    is_italic = bool(is_italic) if is_italic is not None else False

    return font_size, font_name, is_bold, is_italic


def detect_run_color_is_default(run):
    """返回 True 表示未设置颜色或为自动/默认颜色。"""
    try:
        if not hasattr(run, '_element'):
            return True
        rpr = run._element.rPr
        if rpr is None:
            return True
        color = rpr.find(qn('w:color'))
        if color is None:
            return True
        val = color.get(qn('w:val'))
        if val is None:
            return True
        return str(val).lower() in ['auto', '000000']
    except Exception:
        return True


def _debug_enabled(tpl, debug=None):
    if debug is not None:
        return bool(debug)
    return bool(tpl.get('check_rules', {}).get('debug', False))

def iter_all_w_p_elements(doc):
    """
    返回所有 w:p 段落节点（包含正文流 + 文本框/形状 + 表格单元格中的段落）。
    """
    try:
        body_ps = doc.element.body.xpath('./w:p')
        tbx_ps = doc.element.xpath('.//w:txbxContent//w:p')
        tbl_ps = doc.element.body.xpath('.//w:tbl//w:p')
        return body_ps + tbx_ps + tbl_ps
    except Exception:
        return []


def get_paragraph_location(p):
    """
    返回段落 p 所在的单元格位置信息。
    返回: dict {'in_table': bool, 'table_idx': int, 'row': int, 'col': int} 或 None
    仅用于调试/报告，不影响检测逻辑。
    """
    try:
        # 向上找 tc (单元格)
        tc = p.xpath('ancestor::w:tc[1]')
        if not tc:
            return None
        tc = tc[0]

        # 找所在行
        tr = tc.xpath('ancestor::w:tr[1]')
        if not tr:
            return None
        tr = tr[0]

        # 找所在表格
        tbl = tr.xpath('ancestor::w:tbl[1]')
        if not tbl:
            return None
        tbl = tbl[0]

        # 找表格在 body 中的索引
        body = p.xpath('/w:body')
        if body:
            all_tbls = body[0].xpath('./w:tbl')
            table_idx = next((i for i, t in enumerate(all_tbls) if t is tbl), -1)
        else:
            table_idx = -1

        # 找行列索引
        all_rows = tbl.xpath('./w:tr')
        row_idx = next((i for i, r in enumerate(all_rows) if r is tr), -1)

        all_cells = tr.xpath('./w:tc')
        col_idx = next((i for i, c in enumerate(all_cells) if c is tc), -1)

        return {'in_table': True, 'table_idx': table_idx, 'row': row_idx, 'col': col_idx}
    except Exception:
        return None

def get_text_from_w_p(p):
    """
    从 w:p 提取文本（尽量覆盖公式框场景）：w:t + w:instrText + m:t
    """
    try:
        parts = []
        parts.extend(p.xpath('.//w:t/text()'))
        parts.extend(p.xpath('.//w:instrText/text()'))
        parts.extend(p.xpath('.//m:t/text()'))
        text = ''.join(parts)
        return (text or '').strip()
    except Exception:
        return ''


def build_math_spans_map(p, text):
    """
    建立段落中所有 Math 对象的文本位置索引。

    返回: dict  {start_pos: (end_pos, math_text)}
    用于判断编号和公式 Math 对象之间是否只隔着其他 Math 对象的文本。
    """
    math_ns = {
        'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    }
    math_paths = ['.//w:oMath', './/m:oMath', './/oMath', './/m:math']
    spans = {}  # start_pos -> (end_pos, math_text)

    for path in math_paths:
        try:
            for elem in p.xpath(path, namespaces=math_ns):
                parts = []
                parts.extend(elem.xpath('.//w:t/text()', namespaces=math_ns))
                parts.extend(elem.xpath('.//m:t/text()', namespaces=math_ns))
                math_text = ''.join(parts)
                if not math_text:
                    continue
                pos = text.find(math_text)
                if pos >= 0:
                    spans[pos] = (pos + len(math_text), math_text)
        except Exception:
            continue

    return spans


def is_adjacent_to_formula(number_start, number_end, text, math_spans, formula_text):
    """
    判断编号是否与公式 Math 对象相邻（中间只有空白字符，不含正文内容）。

    - number_start / number_end: 编号在 text 中的起止位置
    - text: 段落完整文本
    - math_spans: build_math_spans_map 返回的索引
    - formula_text: 公式 Math 对象的文本内容

    返回: True 表示编号与公式 Math 相邻（视为有效公式候选）
    """
    formula_pos = text.find(formula_text)
    if formula_pos < 0:
        return False

    formula_start = formula_pos
    formula_end = formula_pos + len(formula_text)

    # 关键修复：如果编号落在公式文本范围内，说明编号是公式内容的一部分（如 L*=116(YY0)13-16 中的 13-16）
    if formula_start < number_start < formula_end:
        return False   # 编号在公式文本内部，拒绝

    # 编号在公式左侧
    if number_end <= formula_start:
        between = text[number_end:formula_start]
    # 编号在公式右侧
    elif number_start >= formula_end:
        between = text[formula_end:number_start]
    else:
        return False  # 编号与公式重叠，不合理

    # 检查中间内容：允许空白 + 其他 Math 对象的文本，不允许正文
    cleaned = between
    for span_start, (span_end, _) in sorted(math_spans.items()):
        cleaned = cleaned.replace(text[span_start:span_end], '')

    if cleaned.strip():
        return False
    return True

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

    return 0


def build_paragraph_location_map(all_ps):
    """
    构建段落位置索引：w_p -> (table_idx, row, col)
    用于跨段落（表格内）公式-编号匹配。
    """
    loc_map = {}  # id(p) -> {'table_idx': int, 'row': int, 'col': int} 或 None
    for p in all_ps:
        loc_map[id(p)] = get_paragraph_location(p)
    return loc_map


def is_in_same_table_context(loc1, loc2, max_row_gap=0):
    """
    判断两个段落是否在"表格内相邻"的上下文中。
    - loc1/loc2: get_paragraph_location() 的返回值
    - max_row_gap: 允许的行号差距（默认0表示同一行）
    返回 True 表示两个段落属于同一表格行或相邻行，可以匹配。
    """
    if loc1 is None or loc2 is None:
        return False
    if not loc1.get('in_table') or not loc2.get('in_table'):
        return False
    # table_idx=-1 表示无法确定表格索引，此时跳过表格一致性检查
    if loc1.get('table_idx', -1) >= 0 and loc2.get('table_idx', -1) >= 0:
        if loc1.get('table_idx') != loc2.get('table_idx'):
            return False
    row_gap = abs(loc1.get('row', -1) - loc2.get('row', -1))
    return row_gap <= max_row_gap

def find_formula_candidates(doc, template, debug=None):
    """
    找出所有可能是公式的段落（简化版）

    核心逻辑：
    1. 找到包含 Math 对象的段落
    2. 提取 Math 对象内的文本作为公式内容
    3. 在段落中搜索编号（#3-3, (1-1) 等）
    4. 支持跨段落匹配：编号在独立 w:p 中（如同行表格单元格）
    """
    dbg = _debug_enabled(template, debug)

    rules = template.get('formula_detection_rules', {})
    number_pattern = rules.get('number_pattern', r'[##]?\s*\d+[-－–]?\s*\d+')
    mod = rules.get('math_object_detection', {})
    fallback_patterns = mod.get('fallback_patterns', [])

    candidates = []
    all_ps = list(iter_all_w_p_elements(doc))
    para_loc_map = build_paragraph_location_map(all_ps)
    used_as_number = set()  # 已作为编号匹配过的段落（避免重复）

    if dbg:
        tbl_ps_count = sum(1 for p in all_ps if (para_loc_map.get(id(p)) or {}).get('in_table'))
        logger.info("[Formula] 扫描到 w:p 节点总数=%s，其中表格段落=%s", len(all_ps), tbl_ps_count)
        # 打印 w:p[951] 和 w:p[952] 的 loc 情况（如果有的话）
        for p in all_ps:
            loc = para_loc_map.get(id(p))
            if loc and loc.get('in_table'):
                text_sample = get_text_from_w_p(p)[:30]
                idx_sample = all_ps.index(p)
                if text_sample in ('ci=Tokenizerzi', '3-1', 'xi=Embeddingci', '3-2', 'vCLS=BERTX1', '3-3'):
                    logger.info("[Formula] 表格段落 idx=%s text=%r loc=%s", idx_sample, text_sample, loc)

    # 编号模式列表
    number_patterns = [
        number_pattern,
        r'[##]\s*\d+[-－–]\s*\d+',
        r'\(\d+[-－–]\d+\)',
        r'\(\d+\)',
    ]

    def parse_formula_number(num_text):
        """解析编号，返回 (chapter, seq) 或 None"""
        if '-' in num_text or '－' in num_text or '–' in num_text:
            num_m = re.search(r'(?P<chapter>\d+)\s*[-－–]\s*(?P<seq>\d+)', num_text)
            if num_m:
                try:
                    return (int(num_m.group('chapter')), int(num_m.group('seq')))
                except Exception:
                    pass
        num_m = re.search(r'\d+', num_text)
        if num_m:
            return (1, int(num_m.group()))
        return None

    def _build_math_spans(p, text):
        """局部包装，避免在 stage 1 重复调用"""
        return build_math_spans_map(p, text)

    for idx, p in enumerate(all_ps):
        text = get_text_from_w_p(p)
        if not text:
            continue

        # ========== 0. 没有 Math 对象？检查是否是纯编号段落（跨段落匹配） ==========
        math_elements = []
        math_paths = ['.//w:oMath', './/m:oMath', './/oMath', './/m:math']
        for path in math_paths:
            try:
                elements = p.xpath(path)
                if elements:
                    math_elements.extend(elements)
            except Exception:
                continue

        # 段落中没有 Math 对象 → 可能是纯编号段落（编号在独立 w:p 中）
        if not math_elements:
            # 检查是否只包含编号（去掉空白后匹配编号正则）
            stripped = text.strip()
            is_number_only = False
            matched_num_text = None
            matched_parsed = None
            for pat in number_patterns:
                m = re.match(pat + r'\s*$', stripped)
                if m:
                    is_number_only = True
                    matched_num_text = m.group()
                    matched_parsed = parse_formula_number(matched_num_text)
                    break

            if not is_number_only:
                continue

            if id(p) in used_as_number:
                continue

            # 找相邻段落中包含 Math 的段落（同一表格行或相邻行）
            loc_p = para_loc_map.get(id(p))
            for other_idx, other_p in enumerate(all_ps):
                if other_p is p:
                    continue
                if id(other_p) in used_as_number:
                    continue

                loc_other = para_loc_map.get(id(other_p))
                if not is_in_same_table_context(loc_p, loc_other, max_row_gap=0):
                    continue

                other_text = get_text_from_w_p(other_p)
                if not other_text:
                    continue

                other_math = []
                for path in math_paths:
                    try:
                        elems = other_p.xpath(path)
                        if elems:
                            other_math.extend(elems)
                    except Exception:
                        continue

                if not other_math:
                    continue

                # 找到了相邻的公式段落 → 跨段落匹配成功
                for elem in other_math:
                    math_ns = {
                        'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
                        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                    }
                    math_text_parts = []
                    math_text_parts.extend(elem.xpath('.//w:t/text()', namespaces=math_ns))
                    math_text_parts.extend(elem.xpath('.//m:t/text()', namespaces=math_ns))
                    formula_text = ''.join(math_text_parts)
                    if not formula_text:
                        continue

                    used_as_number.add(id(p))
                    used_as_number.add(id(other_p))

                    if dbg:
                        logger.info(
                            "[Formula] 跨段落匹配: 编号 %s (idx=%s) ←→ 公式 %r (idx=%s, 同表格行)",
                            matched_num_text, idx, formula_text[:50], other_idx
                        )

                    candidates.append({
                        'w_p_index': other_idx,
                        'w_p': other_p,
                        'number_w_p_index': idx,
                        'number_w_p': p,
                        'text': other_text,
                        'number': matched_parsed,
                        'number_text': matched_num_text,
                        'formula_content': formula_text,
                        'formula_font': 'Cambria Math',
                        'math_object_detected': True,
                        'target_math_elem': elem,
                        'cross_paragraph': True,
                    })
                    break
            continue

        # ========== 1. 检测 Math 对象（重命名为 stage1_var 避免遮盖） ==========
        target_math_elem = None
        parsed_number = None
        number_text = None
        number_position_in_math = -1  # 编号在目标 Math 对象中的位置

        for elem in math_elements:
            # 提取当前 Math 对象的文本（统一使用 XPath 方式，与 get_text_from_w_p 一致）
            math_ns = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
                       'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            math_text_parts = []
            math_text_parts.extend(elem.xpath('.//w:t/text()', namespaces=math_ns))
            math_text_parts.extend(elem.xpath('.//m:t/text()', namespaces=math_ns))
            math_text = ''.join(math_text_parts)

            if not math_text:
                continue

            # 在当前 Math 对象内搜索编号
            for pat in number_patterns:
                try:
                    for m in re.finditer(pat, math_text):
                        num_text = m.group()
                        parsed = parse_formula_number(num_text)
                        if parsed:
                            # 关键修复：在 Math 内匹配到编号时，过滤掉公式内容中的数字（如 13-16）
                            # 有括号(如(2-1))或有#前缀(如#3-3)才视为编号；纯数字(如13-16)很可能是公式下标
                            if not (num_text.startswith('#') or num_text.startswith('(')):
                                continue
                            target_math_elem = elem
                            parsed_number = parsed
                            number_text = num_text
                            number_position_in_math = m.start()
                            if dbg:
                                logger.info("[Formula] w:p[%s]：在Math对象内找到编号 num=%s math_text=%r", idx, num_text, math_text[:80])
                            break
                except Exception:
                    continue
                if parsed_number:
                    break
            if parsed_number:
                break

        # ========== 3. 如果没在 Math 内找到，在段落中搜索编号 ==========
        # 先建立所有 Math 对象的文本位置索引（用于处理编号是独立 Math 对象的情况）
        math_spans = build_math_spans_map(p, text)

        if not parsed_number:
            if dbg:
                logger.info("[Formula] DEBUG w:p[%s]: 在Math内未找到编号，开始在段落中搜索. text=%r, math_spans=%s",
                            idx, text[:150], {k: v[1][:30] for k, v in math_spans.items()})
            for elem in math_elements:
                # 提取当前 Math 对象的文本（与 get_text_from_w_p 一致）
                math_ns = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
                           'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                math_text_parts = []
                math_text_parts.extend(elem.xpath('.//w:t/text()', namespaces=math_ns))
                math_text_parts.extend(elem.xpath('.//m:t/text()', namespaces=math_ns))
                formula_text = ''.join(math_text_parts)

                if not formula_text:
                    continue

                # 在段落中搜索编号
                for pat in number_patterns:
                    try:
                        for m in re.finditer(pat, text):
                            num_text = m.group()
                            parsed = parse_formula_number(num_text)
                            if parsed:
                                # 用新逻辑判断编号是否与公式 Math 相邻
                                if is_adjacent_to_formula(m.start(), m.end(), text, math_spans, formula_text):
                                    target_math_elem = elem
                                    parsed_number = parsed
                                    number_text = num_text
                                    if dbg:
                                        logger.info("[Formula] w:p[%s]：编号 %s 与公式 %r 相邻（via is_adjacent_to_formula）",
                                                    idx, num_text, formula_text[:50])
                                    break
                    except Exception:
                        continue
                    if parsed_number:
                        break
                if parsed_number:
                    break

        if not parsed_number:
            # ========== Stage 3（补充）：有 Math 但无编号 → 在同表格行找纯编号段落 ==========
            # 对应场景：公式在单元格 A，编号在同行单元格 B（编号在前）
            loc_p = para_loc_map.get(id(p))
            if dbg:
                logger.info("[Formula] Stage3 loc check: idx=%s text=%r loc=%s", idx, text[:50], loc_p)
            if loc_p and loc_p.get('in_table'):
                for num_idx, num_p in enumerate(all_ps):
                    if num_p is p or id(num_p) in used_as_number:
                        continue
                    loc_num = para_loc_map.get(id(num_p))
                    # 精确调试：w:p[951] 配对候选（仅在找到匹配时打一行汇总）
                    if dbg and text[:20] == 'ci=Tokenizerzi':
                        ntxt = get_text_from_w_p(num_p)[:20]
                        num_id = id(num_p)
                        ctx = is_in_same_table_context(loc_p, loc_num, max_row_gap=0)
                        num_in_map = id(num_p) in {id(p2) for p2 in all_ps}
                        # 只在可能匹配时打日志：同行同表格 且文本含数字
                        if ctx and any(c.isdigit() for c in ntxt):
                            stripped = ntxt.strip()
                            is_num = any(re.match(pat + r'\s*$', stripped) for pat in number_patterns)
                            logger.info(
                                "[Formula] Stage3-TRY: 公式idx=%s(col=%s) num_idx=%s text=%r same_table=%s is_number=%s",
                                idx, loc_p.get('col'), num_idx, ntxt, ctx, is_num
                            )
                    if not is_in_same_table_context(loc_p, loc_num, max_row_gap=0):
                        continue
                    num_text_full = get_text_from_w_p(num_p)
                    if not num_text_full:
                        continue
                    # 检查编号段落是否只含编号（纯编号）
                    stripped = num_text_full.strip()
                    is_number_only = False
                    for pat in number_patterns:
                        if re.match(pat + r'\s*$', stripped):
                            is_number_only = True
                            break
                    if not is_number_only:
                        # 精确调试：w:p[951] 配对候选
                        if dbg and text[:20] == 'ci=Tokenizerzi':
                            logger.info(
                                "[Formula] Stage3-REJECT: num_idx=%s text=%r 不是纯编号 (is_number_only=False)",
                                num_idx, stripped[:30]
                            )
                        continue
                    parsed = parse_formula_number(stripped)
                    if not parsed:
                        if dbg and text[:20] == 'ci=Tokenizerzi':
                            logger.info(
                                "[Formula] Stage3-REJECT: num_idx=%s text=%r 无法解析编号",
                                num_idx, stripped[:30]
                            )
                        continue

                    # 找该编号段落中包含 Math 的段落（第一个有 Math 的）
                    num_math = []
                    for path in math_paths:
                        try:
                            elems = num_p.xpath(path)
                            if elems:
                                num_math.extend(elems)
                        except Exception:
                            continue
                    if num_math:
                        # 编号段落自身有 Math，说明是表格中"编号与公式分列存放"的情况：
                        # - num_p (col=2) 的 Math 内容 = 编号
                        # - p (col=1) 的 math_elements = 公式内容
                        # 将两者配对：p 的 Math 作为公式内容，num_p 的 Math 作为编号
                        if dbg and text[:20] == 'ci=Tokenizerzi':
                            logger.info(
                                "[Formula] Stage3-MATCH-TABLE: 公式idx=%s(num_idx=%s) 表格编号段落含Math，编号=%s",
                                idx, num_idx, parsed
                            )
                        # 直接构造候选：公式内容来自 p，编号来自 num_p
                        candidates.append({
                            'w_p_index': idx,
                            'w_p': p,
                            'number_w_p_index': num_idx,
                            'number_w_p': num_p,
                            'text': text,
                            'number': parsed,
                            'number_text': stripped,
                            'formula_content': text,
                            'location': loc_p,
                            'source': 'stage3_table_math'
                        })
                        used_as_number.add(id(num_p))
                        used_as_number.add(id(p))
                        # 注意：当前 for 循环不再需要继续，因为 p 已找到配对
                        break

                    # 更新外层变量，确保后续逻辑能识别到编号
                    target_math_elem = math_elements[0]
                    parsed_number = parsed
                    number_text = stripped

                    used_as_number.add(id(num_p))
                    used_as_number.add(id(p))
                    if dbg and text[:20] == 'ci=Tokenizerzi':
                        logger.info(
                            "[Formula] Stage3-MATCH! 公式idx=%s(num_idx=%s) 编号=%s math_elem=%s",
                            idx, num_idx, parsed, target_math_elem
                        )

                    if dbg:
                        logger.info(
                            "[Formula] 跨段落匹配（公式在前）: 公式 idx=%s ←→ 编号 %s idx=%s（%s行/%s列 ←→ %s行/%s列）",
                            idx, stripped, num_idx,
                            loc_p.get('row'), loc_p.get('col'),
                            loc_num.get('row'), loc_num.get('col')
                        )
                    candidates.append({
                        'w_p_index': idx,
                        'w_p': p,
                        'number_w_p_index': num_idx,
                        'number_w_p': num_p,
                        'text': text,
                        'number': parsed,
                        'number_text': stripped,
                        'formula_content': text,
                        'formula_font': 'Cambria Math',
                        'math_object_detected': True,
                        'target_math_elem': math_elements[0],
                        'cross_paragraph': True,
                    })
                    break

            if dbg and parsed_number is None:
                logger.info("[Formula] w:p[%s]：有Math对象但未找到编号 preview=%r", idx, text[:80])
            if parsed_number is None:
                continue

        # ========== 4. 提取目标 Math 对象的文本作为公式内容 ==========
        # 分两种情况：
        # A. 编号在公式 Math 对象内部  → 从公式 Math 对象提取（去掉编号部分）
        # B. 编号是独立 Math 对象     → 从段落全文提取（完整保留）
        formula_text_for_check = ''
        if target_math_elem is not None:
            for node in target_math_elem.iter():
                if hasattr(node, 'text') and node.text:
                    formula_text_for_check += node.text

        number_pos_in_text = text.find(number_text)
        formula_pos_in_text = text.find(formula_text_for_check)

        # 判断编号是否真正在公式 Math 对象的文本范围内
        number_inside_formula_math = (
            formula_text_for_check
            and formula_pos_in_text >= 0
            and formula_pos_in_text <= number_pos_in_text < formula_pos_in_text + len(formula_text_for_check)
        )

        formula_content = ''

        if target_math_elem is not None:
            for node in target_math_elem.iter():
                if hasattr(node, 'text') and node.text:
                    node_text = node.text.strip()
                    if number_text in node_text:
                        pos = node_text.find(number_text)
                        formula_content += node_text[:pos]
                    else:
                        formula_content += node_text

        # 仅当编号确实在公式 Math 内部、且提取结果非空时，才认为 A 情况成功
        if not formula_content and number_inside_formula_math:
            # 备用：从全段提取并去掉编号
            fc = text
            if number_text in fc:
                pos = fc.find(number_text)
                fc = fc[:pos] + fc[pos + len(number_text):]
            formula_content = fc.strip()
        elif not formula_content:
            # 纯备用：从全段提取（保留全部）
            fc = text
            if number_text in fc:
                pos = fc.find(number_text)
                fc = fc[:pos] + fc[pos + len(number_text):]
            formula_content = fc.strip()

        formula_content = formula_content.strip()

        if not formula_content:
            if dbg:
                logger.info("[Formula] w:p[%s]：公式内容为空 preview=%r", idx, text[:80])
            continue

        # ========== 6. 构建候选结果 ==========
        candidates.append({
            'w_p_index': idx,
            'w_p': p,
            'text': text,
            'number': parsed_number,
            'number_text': number_text,
            'formula_content': formula_content,
            'formula_font': 'Cambria Math',
            'math_object_detected': True,
            'target_math_elem': target_math_elem,  # 保存 Math 对象引用，用于字体检测
        })

    if dbg:
        logger.info("[Formula] 候选公式段落数=%s", len(candidates))

    return candidates


def check_tab_stops(paragraph, expected_tabs, tolerance_chars=2, dbg=False):
    """
    检查段落制表位
    - paragraph: 段落对象
    - expected_tabs: 期望的制表位配置列表
    - tolerance_chars: 位置容差（字符数）
    - dbg: 是否输出调试日志
    返回: (是否通过, 问题列表, 检测到的制表位列表)
    """
    issues = []
    detected_tabs = []

    if dbg:
        logger.info("[TabStops] 开始检查制表位...")
        logger.info("[TabStops] 期望制表位: %s", expected_tabs)
        logger.info("[TabStops] 容差: %s 字符", tolerance_chars)

    try:
        pPr = paragraph.paragraph_format._element
        tabs_elements = pPr.xpath('.//w:tabs')

        if not tabs_elements and paragraph.style and hasattr(paragraph.style, '_element'):
            style_elem = paragraph.style._element
            tabs_elements = style_elem.xpath('.//w:tabs')

        if not tabs_elements:
            if dbg:
                logger.info("[TabStops] 未在段落格式和样式中检测到制表位设置")
            issues.append("未检测到制表位设置（段落格式和样式中都没有）")
            return False, issues, detected_tabs

        # 提取制表位信息
        for tabs_elem in tabs_elements:
            tab_elements = tabs_elem.xpath('.//w:tab')
            for tab_elem in tab_elements:
                pos_attr = tab_elem.get(qn('w:pos'))
                val_attr = tab_elem.get(qn('w:val'))

                if pos_attr and val_attr:
                    pos_twips = int(pos_attr)
                    pos_chars = round(pos_twips / 210.0)

                    alignment_map = {
                        'center': 'center',
                        'right': 'right',
                        'left': 'left',
                        'decimal': 'decimal'
                    }
                    alignment = alignment_map.get(val_attr, val_attr)

                    detected_tabs.append({
                        'position_chars': pos_chars,
                        'position_twips': pos_twips,
                        'alignment': alignment
                    })

        if dbg:
            logger.info("[TabStops] 检测到 %d 个制表位: %s", len(detected_tabs), detected_tabs)

        # 检查制表位数量
        if len(detected_tabs) < len(expected_tabs):
            issues.append(f"制表位数量不足，期望{len(expected_tabs)}个，实际{len(detected_tabs)}个")
            if dbg:
                logger.info("[TabStops] 问题: 制表位数量不足")

        # 检查每个期望的制表位
        for expected_tab in expected_tabs:
            expected_pos = int(expected_tab['position_chars'])
            expected_align = str(expected_tab['alignment'])

            matching_tab = None
            for detected_tab in detected_tabs:
                diff = abs(detected_tab['position_chars'] - expected_pos)
                if diff <= tolerance_chars:
                    matching_tab = detected_tab
                    if dbg:
                        logger.info("[TabStops] 找到匹配的制表位: 期望位置=%s, 检测位置=%s, 差距=%s, 容差=%s",
                                  expected_pos, detected_tab['position_chars'], diff, tolerance_chars)
                    break

            if not matching_tab:
                issues.append(f"未找到位置为{expected_pos}字符的制表位")
                if dbg:
                    logger.info("[TabStops] 问题: 未找到位置为 %s 字符的制表位", expected_pos)
            else:
                if matching_tab['alignment'] != expected_align:
                    issues.append(f"制表位{expected_pos}字符处对齐方式错误，期望{expected_align}，实际{matching_tab['alignment']}")
                    if dbg:
                        logger.info("[TabStops] 问题: 对齐方式错误，期望=%s, 实际=%s",
                                   expected_align, matching_tab['alignment'])

        # 检查制表符使用情况
        tab_char_count = paragraph.text.count('\t')
        expected_tab_chars = len(expected_tabs)

        if tab_char_count == 0:
            issues.append("设置了制表位但没有使用制表符，公式不会按预期对齐")
            if dbg:
                logger.info("[TabStops] 问题: 段落中没有使用制表符")
        elif tab_char_count < expected_tab_chars:
            issues.append(f"制表符使用不足，期望{expected_tab_chars}个，实际{tab_char_count}个")
            if dbg:
                logger.info("[TabStops] 问题: 制表符使用不足，期望=%s, 实际=%s", expected_tab_chars, tab_char_count)
        elif tab_char_count > expected_tab_chars:
            issues.append(f"制表符使用过多，期望{expected_tab_chars}个，实际{tab_char_count}个")
            if dbg:
                logger.info("[TabStops] 问题: 制表符使用过多，期望=%s, 实际=%s", expected_tab_chars, tab_char_count)
        else:
            if dbg:
                logger.info("[TabStops] 制表符使用正确，数量=%d", tab_char_count)

        if dbg:
            logger.info("[TabStops] 检查完成，问题数量=%d", len(issues))

        return len(issues) == 0, issues, detected_tabs

    except Exception as e:
        if dbg:
            logger.info("[TabStops] 检测异常: %s", str(e))
        return False, [f"制表位检测异常: {str(e)}"], detected_tabs


def detect_math_objects(paragraph):
    """
    检测段落中的数学对象
    返回：是否包含数学对象、数学对象列表、详细信息
    详细信息包含：计数、类型列表、内容预览、以及字体信息
    """
    math_objects = []
    info = {
        'count': 0,
        'types': [],
        'content_preview': [],
        'font_info': []  # 新增：每个 Math 对象的字体信息
    }

    try:
        if paragraph is None:
            return False, [], info
        para_xml = paragraph._element

        math_elements = []
        math_paths = [
            './/w:oMath',
            './/m:oMath',
            './/oMath',
            './/w:r/w:object',
            './/w:r[.//w:oMath]'
        ]

        for path in math_paths:
            try:
                math_elements.extend(para_xml.xpath(path))
            except Exception:
                continue

        unique_elements = []
        for elem in math_elements:
            if elem not in unique_elements:
                unique_elements.append(elem)

        info['count'] = len(unique_elements)

        for elem in unique_elements:
            try:
                obj = {
                    'element': elem,
                    'tag': elem.tag,
                    'type': 'unknown',
                    'text_content': '',
                    'font_info': {}  # 字体信息
                }

                if 'oMath' in elem.tag:
                    obj['type'] = 'office_math'
                elif 'object' in elem.tag:
                    obj['type'] = 'embedded_object'
                else:
                    obj['type'] = 'math_container'

                text_parts = []
                for node in elem.iter():
                    if hasattr(node, 'text') and node.text:
                        text_parts.append(node.text.strip())
                obj['text_content'] = ' '.join(filter(None, text_parts))

                # ========== 提取字体信息 ==========
                try:
                    xml_str = ET.tostring(elem, encoding='unicode')

                    # 检查 rPr（格式属性）
                    rpr = elem.find('.//w:rPr')
                    if rpr is not None:
                        rpr_str = ET.tostring(rpr, encoding='unicode')
                        obj['font_info']['has_rpr'] = True

                        # 检查字体
                        font_elems = rpr.xpath('.//w:rFonts')
                        if font_elems:
                            font_elem = font_elems[0]
                            fonts = {
                                'ascii': font_elem.get(qn('w:ascii')),
                                'east_asia': font_elem.get(qn('w:eastAsia')),
                                'h_ansi': font_elem.get(qn('w:hAnsi')),
                                'cambria': font_elem.get(qn('w:cambriaMath')),
                            }
                            obj['font_info']['fonts'] = {k: v for k, v in fonts.items() if v}

                            # 检查是否有 Cambria Math 字体
                            if 'cambriaMath' in fonts and fonts['cambriaMath']:
                                obj['font_info']['is_cambria_math'] = True
                    else:
                        obj['font_info']['has_rpr'] = False

                    # 检查 Math 对象的默认字体设置
                    if 'cambria' in xml_str.lower():
                        obj['font_info']['contains_cambria'] = True

                except Exception as e:
                    obj['font_info']['error'] = str(e)

                math_objects.append(obj)
                info['types'].append(obj['type'])

                preview = obj['text_content'][:50] + ('...' if len(obj['text_content']) > 50 else '')
                if preview:
                    info['content_preview'].append(preview)

                # 添加字体信息到 info
                info['font_info'].append({
                    'type': obj['type'],
                    'is_cambria_math': obj['font_info'].get('is_cambria_math', False),
                    'contains_cambria': obj['font_info'].get('contains_cambria', False),
                    'fonts': obj['font_info'].get('fonts', {})
                })

            except Exception:
                continue

        return len(math_objects) > 0, math_objects, info

    except Exception:
        return False, [], info


def extract_formula_number(text, number_pattern):
    m = re.search(number_pattern, text)
    if not m:
        return None

    try:
        chapter = int(m.group('chapter'))
        seq = int(m.group('seq'))
        return chapter, seq
    except Exception:
        return None


def check_formula_fonts(paragraph, math_objects, template, number_pattern, formula_content_text=None, target_math_elem=None, dbg=False):
    """
    检测公式字体要求：
    1. 公式内容必须全部使用 Cambria Math 字体
    2. 公式编号字号应为 12pt（小四）
    3. 公式编号字体可以是任意字体（不强检）
    """
    issues = []

    # 获取 debug 标志（优先使用参数传递的 dbg，否则从模板获取）
    check_rules = template.get('check_rules', {})
    dbg = dbg or check_rules.get('debug', False)

    font_requirements = template.get('formula_detection_rules', {}).get('font_requirements', {})
    messages = template.get('messages', {})

    # 从模板读取配置
    expected_number_font = font_requirements.get('formula_number', 'Times New Roman')
    expected_size_pt = float(font_requirements.get('font_size_pt', 12))
    expected_math_font = font_requirements.get('formula_content', 'Cambria Math')

    # 从模板读取斜体/加粗配置
    expected_content_italic = check_rules.get('formula_content_italic', False)
    expected_content_bold = check_rules.get('formula_content_bold', False)
    expected_number_italic = check_rules.get('formula_number_italic', False)
    expected_number_bold = check_rules.get('formula_number_bold', False)
    check_content_italic = check_rules.get('formula_content_italic_check', True)
    check_number_italic = check_rules.get('formula_number_italic_check', True)
    check_number_color = check_rules.get('number_color_check', True)

    # ========== 0. 提取 Math 对象中的属性信息 ==========
    math_font_info = {
        'cambria_math': None,  # Cambria Math 字体
        'font_size': None,     # 字号 (pt)
        'is_bold': None,       # 是否加粗
        'is_italic': None,     # 是否斜体
    }

    if target_math_elem is not None:
        if dbg:
            logger.info("[Formula] target_math_elem type: %s, tag: %s",
                        type(target_math_elem).__name__,
                        target_math_elem.tag if hasattr(target_math_elem, 'tag') else 'N/A')
            # 打印 XML 前 200 字符
            from lxml import etree
            xml_str = etree.tostring(target_math_elem, encoding='unicode', method='text')[:200]
            logger.info("[Formula] target_math_elem XML preview: %s...", xml_str[:200])
            # 打印所有子元素标签
            child_tags = [child.tag for child in target_math_elem]
            logger.info("[Formula] target_math_elem child tags: %s", child_tags[:10])
            # 打印第一个子元素的完整结构
            if target_math_elem:
                first_child = list(target_math_elem)[0] if len(list(target_math_elem)) > 0 else None
                if first_child:
                    # 打印所有深度1的子元素标签
                    level1_tags = [c.tag for c in first_child]
                    logger.info("[Formula] First child (eqArr) level1 tags: %s", level1_tags[:15])
                    # 打印深度2的子元素
                    if len(list(first_child)) > 0:
                        second_child = list(first_child)[0]
                        level2_tags = [c.tag for c in second_child]
                        logger.info("[Formula] Second level tags: %s", level2_tags[:15])
        try:
            # 遍历 oMath 的所有子元素，查找字体信息
            # MathML 结构: oMath -> eqArr -> {eqArrPr, e}
            # eqArrPr 是数组属性，不是公式内容字体
            # 真正的公式内容字体在 e 元素内的 sPre/rPr 中
            rpr = None
            for elem in target_math_elem.iter():
                tag = elem.tag if hasattr(elem, 'tag') else ''
                # 跳过 eqArrPr（公式数组属性）
                if 'eqArrPr' in tag:
                    continue
                # 查找 rPr 元素（公式内容字体）
                if 'rPr' in tag and 'eqArrPr' not in tag:
                    rpr = elem
                    if dbg:
                        logger.info("[Formula] Found content rPr in element: %s", tag)
                    break
            if rpr is None:
                # 备选：尝试使用安全的 XPath（不使用前缀）
                try:
                    rpr_candidates = target_math_elem.xpath('.//*[local-name()="rPr"]')
                    if rpr_candidates:
                        rpr = rpr_candidates[0]
                        if dbg:
                            logger.info("[Formula] Found rPr via local-name()")
                except Exception as e:
                    if dbg:
                        logger.info("[Formula] XPath with local-name() failed: %s", str(e))
            if dbg:
                logger.info("[Formula] rPr find result: %s", 'Found' if rpr is not None else 'Not found')
            if rpr is not None:
                # 尝试多种方式查找 rFonts
                rFonts = None
                for xpath_expr in [
                    './/*[local-name()="rFonts"]',
                    './/{http://schemas.openxmlformats.org/officeDocument/2006/math}rFonts',
                    './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts'
                ]:
                    try:
                        results = rpr.xpath(xpath_expr)
                        if results:
                            rFonts = results[0]
                            if dbg:
                                logger.info("[Formula] Found rFonts with xpath: %s", xpath_expr)
                            break
                    except Exception:
                        continue
                if dbg:
                    logger.info("[Formula] rFonts find result: %s", 'Found' if rFonts is not None else 'Not found')
                if rFonts is not None:
                    # MathML 中的属性没有命名空间前缀，直接使用 get() 获取
                    cambria = rFonts.get('cambriaMath')
                    if not cambria:
                        cambria = rFonts.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}cambriaMath')
                    if cambria:
                        math_font_info['cambria_math'] = cambria

                    # 检查其他字体属性（MathML 中无命名空间前缀）
                    ascii_font = rFonts.get('ascii')
                    east_asia = rFonts.get('eastAsia')
                    hAnsi = rFonts.get('hAnsi')
                    math_font_info['other_fonts'] = {
                        'ascii': ascii_font,
                        'eastAsia': east_asia,
                        'hAnsi': hAnsi,
                    }

                # 检查字号 (w:sz / w:szCs) - MathML 中使用 val 属性
                sz = None
                for xpath_expr in [
                    './/*[local-name()="sz"]',
                    './/{http://schemas.openxmlformats.org/officeDocument/2006/math}sz',
                    './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz'
                ]:
                    try:
                        results = rpr.xpath(xpath_expr)
                        if results:
                            sz = results[0]
                            break
                    except Exception:
                        continue
                if sz is not None:
                    val = sz.get('val')
                    if not val:
                        val = sz.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                    if val:
                        math_font_info['font_size'] = float(val) / 2.0

                # 检查是否斜体 (i / iCs)
                i_elem = None
                for xpath_expr in [
                    './/*[local-name()="i"]',
                    './/{http://schemas.openxmlformats.org/officeDocument/2006/math}i',
                    './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}i'
                ]:
                    try:
                        results = rpr.xpath(xpath_expr)
                        if results:
                            i_elem = results[0]
                            break
                    except Exception:
                        continue
                if i_elem is not None:
                    val = i_elem.get('val')
                    if not val:
                        val = i_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                    math_font_info['is_italic'] = val != '0'

                # 检查是否加粗 (b / bCs)
                b_elem = None
                for xpath_expr in [
                    './/*[local-name()="b"]',
                    './/{http://schemas.openxmlformats.org/officeDocument/2006/math}b',
                    './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b'
                ]:
                    try:
                        results = rpr.xpath(xpath_expr)
                        if results:
                            b_elem = results[0]
                            break
                    except Exception:
                        continue
                if b_elem is not None:
                    val = b_elem.get('val')
                    if not val:
                        val = b_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                    math_font_info['is_bold'] = val != '0'
        except Exception as e:
            if dbg:
                logger.info("[Formula] 解析Math对象字体信息失败: %s", str(e))

        # 调试日志：打印提取到的字体信息
        if dbg:
            logger.info("[Formula] 公式内容字体信息: %s", math_font_info)

    # ========== 1. 检查公式内容字体（必须全为 Cambria Math） ==========
    if target_math_elem is not None:
        # 从 Math 对象 XML 检测字体
        if math_font_info.get('cambria_math'):
            # Cambria Math 字体存在
            if dbg:
                logger.info("[Formula] 公式内容使用 Cambria Math 字体: %s", math_font_info.get('cambria_math'))
        elif math_font_info.get('other_fonts', {}).get('ascii') or math_font_info.get('other_fonts', {}).get('eastAsia'):
            # 其他字体（非 Cambria Math）
            issues.append(f"公式内容应全部使用 {expected_math_font} 字体")
    elif formula_content_text and paragraph:
        # 备选：从 paragraph runs 检测
        formula_runs = []
        for run in paragraph.runs:
            text = run.text or ''
            if formula_content_text in text or text in formula_content_text:
                formula_runs.append(run)

        if formula_runs:
            all_cambria = True
            for run in formula_runs:
                _, font, _, _ = detect_font_for_run(run, paragraph)
                font_lower = (font or '').lower()
                if 'cambria' not in font_lower:
                    all_cambria = False
                    break

            if not all_cambria:
                issues.append(f"公式内容应全部使用 {expected_math_font} 字体")
    elif math_objects:
        # 通过 Math 对象检查字体
        all_cambria = True
        for mo in math_objects:
            try:
                xml_str = ET.tostring(mo['element'], encoding='unicode')
                rpr = mo['element'].find('.//w:rPr')
                if rpr is not None:
                    rpr_str = ET.tostring(rpr, encoding='unicode')
                    font_elems = rpr.xpath('.//w:rFonts')
                    if font_elems:
                        font_elem = font_elems[0]
                        cambria_font = font_elem.get(qn('w:cambriaMath'))
                        if not cambria_font:
                            all_cambria = False
                            break
                else:
                    if 'cambria' not in xml_str.lower():
                        all_cambria = False
                        break
            except Exception:
                all_cambria = False
                break

        if not all_cambria:
            issues.append(f"公式内容应全部使用 {expected_math_font} 字体")

    # ========== 1b. 检查公式内容字号 ==========
    actual_size = math_font_info.get('font_size')
    if actual_size is not None:
        if dbg:
            logger.info("[Formula] 公式内容字号: 预期=%spt, 实际=%spt", expected_size_pt, actual_size)
        if abs(actual_size - expected_size_pt) > 0.5:
            issues.append(f"公式内容字号应为{get_font_size(expected_size_pt, template)}（{expected_size_pt}pt），实际为{get_font_size(actual_size, template)}（{actual_size}pt）")
    else:
        # 无法提取字号时，记录为问题
        if dbg:
            logger.info("[Formula] 公式内容：无法从Math对象提取字号信息")

    # ========== 1c. 检查公式内容是否斜体 ==========
    if check_content_italic and expected_content_italic is not None:
        if math_font_info.get('is_italic') is not None:
            if math_font_info.get('is_italic') != expected_content_italic:
                issues.append(f"公式内容斜体设置不正确，期望{'斜体' if expected_content_italic else '正体'}")

    # ========== 1d. 检查公式内容是否加粗 ==========
    if expected_content_bold is not None:
        if math_font_info.get('is_bold') is not None:
            if math_font_info.get('is_bold') != expected_content_bold:
                issues.append(f"公式内容加粗设置不正确，期望{'加粗' if expected_content_bold else '正常'}")

    # ========== 2. 检查公式编号 ==========
    # 编号字体：检查字体名称、字号、斜体、加粗、颜色

    # 尝试从 target_math_elem 内部提取编号信息
    if target_math_elem is not None:
        # 使用 XPath 查找所有 MathML r 元素
        for xpath_expr in ['.//{http://schemas.openxmlformats.org/officeDocument/2006/math}r',
                          './/m:r']:
            try:
                run_elems = target_math_elem.xpath(xpath_expr)
                break
            except Exception:
                run_elems = []
        
        for run_elem in run_elems:
            try:
                # 查找 t 元素
                t_elem = None
                for t_tag in ['{http://schemas.openxmlformats.org/officeDocument/2006/math}t',
                              '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t', 't']:
                    t_elem = run_elem.find(t_tag)
                    if t_elem is not None:
                        break
                if t_elem is None:
                    continue
                run_text = t_elem.text or ''
                if not run_text.strip():
                    continue

                # 检查是否是编号
                if re.search(number_pattern, run_text.strip()):
                    # 检测字体和字号 - 查找 rPr (使用 XPath)
                    rpr = None
                    for rpr_xpath in ['.//{http://schemas.openxmlformats.org/officeDocument/2006/math}rPr',
                                     './/m:rPr',
                                     './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr']:
                        try:
                            results = run_elem.xpath(rpr_xpath)
                            if results:
                                rpr = results[0]
                                break
                        except Exception:
                            continue
                    num_font = 'Unknown'
                    num_size = None
                    num_italic = None
                    num_bold = None

                    if rpr is not None:
                        # 查找 rFonts (使用 XPath)
                        rFonts = None
                        for rf_xpath in ['.//{http://schemas.openxmlformats.org/officeDocument/2006/math}rFonts',
                                        './/m:rFonts',
                                        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts']:
                            try:
                                results = rpr.xpath(rf_xpath)
                                if results:
                                    rFonts = results[0]
                                    break
                            except Exception:
                                continue
                        if rFonts is not None:
                            for attr_name in ['cambriaMath', 'ascii', 'eastAsia', 'hAnsi']:
                                val = rFonts.get(attr_name)
                                if val:
                                    num_font = val
                                    break

                        # 字号 (使用 XPath)
                        sz = None
                        for sz_xpath in ['.//{http://schemas.openxmlformats.org/officeDocument/2006/math}sz',
                                        './/m:sz',
                                        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz']:
                            try:
                                results = rpr.xpath(sz_xpath)
                                if results:
                                    sz = results[0]
                                    break
                            except Exception:
                                continue
                        if sz is not None:
                            val = sz.get('val')
                            if not val:
                                val = sz.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            if val:
                                num_size = float(val) / 2.0

                        # 斜体：只用 XPath 检查显式 <i> 元素，找不到则静默跳过（与公式内容一致）
                        i_elem = None
                        for i_xpath in ['.//{http://schemas.openxmlformats.org/officeDocument/2006/math}i',
                                        './/m:i',
                                        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}i']:
                            try:
                                results = rpr.xpath(i_xpath)
                                if results:
                                    i_elem = results[0]
                                    break
                            except Exception:
                                continue
                        if i_elem is not None:
                            val = i_elem.get('val')
                            if not val:
                                val = i_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            num_italic = val != '0'

                        # 检查加粗 (使用 XPath)
                        b_elem = None
                        for b_xpath in ['.//{http://schemas.openxmlformats.org/officeDocument/2006/math}b',
                                        './/m:b',
                                        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b']:
                            try:
                                results = rpr.xpath(b_xpath)
                                if results:
                                    b_elem = results[0]
                                    break
                            except Exception:
                                continue
                        if b_elem is not None:
                            val = b_elem.get('val')
                            if not val:
                                val = b_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            num_bold = val != '0'

                    # 检查字号（只在成功提取到字号时才比较）
                    if num_size is not None and abs(num_size - expected_size_pt) > 0.5:
                        issues.append(f"公式编号字号应为{get_font_size(expected_size_pt, template)}（{expected_size_pt}pt），实际为{get_font_size(num_size, template)}（{num_size}pt）")

                    # 检查斜体（由 formula_number_italic_check 控制开关）
                    if check_number_italic and num_italic is not None and expected_number_italic is not None and num_italic != expected_number_italic:
                        issues.append(f"公式编号斜体设置不正确，期望{'斜体' if expected_number_italic else '正体'}")

                    # 检查加粗（只在成功提取到加粗值时才比较）
                    if num_bold is not None and expected_number_bold is not None and num_bold != expected_number_bold:
                        issues.append(f"公式编号加粗设置不正确，期望{'加粗' if expected_number_bold else '正常'}")

                    # 检查字体名称
                    if num_font and num_font != 'Unknown':
                        font_lower = num_font.lower()
                        expected_font_lower = expected_number_font.lower()
                        # 允许 Times New Roman 或其变体
                        if 'times new roman' not in font_lower and font_lower != expected_font_lower:
                            issues.append(messages.get('font_number_error', f'公式编号字体应为{expected_number_font}，实际为{num_font}'))

                    break
            except Exception:
                continue

    # 备选：从 paragraph runs 检测编号（编号是独立 Math 对象时不可达，静默跳过）
    if paragraph is not None:
        for run in paragraph.runs:
            if not run.text.strip():
                continue

            t = run.text.strip()

            # 检查是否是编号
            if re.search(number_pattern, t):
                size, font, is_italic, _ = detect_font_for_run(run, paragraph)

                # 检查字号（只在成功提取到字号时才比较）
                if size is not None and abs(size - expected_size_pt) > 0.5:
                    issues.append(f"公式编号字号应为{get_font_size(expected_size_pt, template)}（{expected_size_pt}pt），实际为{get_font_size(size, template)}（{size}pt）")

                # 检查斜体（由 formula_number_italic_check 控制开关）
                if check_number_italic and expected_number_italic is not None and is_italic != expected_number_italic:
                    issues.append(f"公式编号斜体设置不正确，期望{'斜体' if expected_number_italic else '正体'}")

                # 检查字体名称
                if font and font != 'Unknown':
                    font_lower = font.lower()
                    # 允许 Times New Roman 或其变体
                    if 'times new roman' not in font_lower and font_lower != expected_number_font.lower():
                        issues.append(messages.get('font_number_error', f'公式编号字体应为{expected_number_font}，实际为{font}'))

                # 检查颜色
                if check_number_color and not detect_run_color_is_default(run):
                    issues.append(messages.get('font_number_color_error', '公式编号应为无特殊颜色'))

                break

    return len(issues) == 0, issues


def check_formula_reference(paragraph, parsed_number, template, tpl, doc, dbg=False):
    """
    检查公式引用：公式上一个段落必须提及该公式引用（公式{章}-{序}）
    当 paragraph 为 None 时（表格单元格段落），跳过引用检查。
    """
    report = {'ok': True, 'messages': []}
    messages = tpl.get('messages', {})
    check_rules = tpl.get('check_rules', {})

    # 检查是否启用引用检查
    reference_check = check_rules.get('formula_reference_check', True)
    if not reference_check:
        return report

    if parsed_number is None:
        return report

    # 表格单元格段落无法获取 body 位置，跳过引用检查
    if paragraph is None:
        return report

    chapter, seq = parsed_number

    # 获取段落在 body 中的位置
    para_elem = paragraph._element
    body = doc.element.body

    # 查找段落的索引
    para_index = -1
    for i, el in enumerate(body):
        if el == para_elem:
            para_index = i
            break

    if para_index <= 0:
        report['ok'] = False
        report['messages'].append(messages.get('formula_reference_error', f'公式上一段落未提及该公式引用'))
        return report

    # 向前查找直到找到有效的段落
    prev_index = para_index - 1
    while prev_index >= 0:
        prev_elem = body[prev_index]

        # 如果不是段落，则继续向前查找
        if not prev_elem.tag.endswith('p'):
            prev_index -= 1
            continue

        # 获取段落文本
        prev_text = ''
        for el in prev_elem.iter():
            if hasattr(el, 'text') and el.text:
                prev_text += el.text
        prev_text = prev_text.strip()

        if prev_text:
            # 检查是否包含公式引用
            # 匹配模式：公式3-1, 公式 3-1, 公式3.1, 公式 3 . 1 等变体
            ref_patterns = [
                rf'公式\s*{chapter}\s*[-－.．]\s*{seq}',  # 公式3-1
                rf'公式\s*{chapter}\s*[-－.．]\s*{seq}\b',  # 公式3-1 后面是单词边界
                rf'\({chapter}\s*[-－.．]\s*{seq}\)',  # (3-1) 格式
            ]

            found_ref = False
            for pattern in ref_patterns:
                if re.search(pattern, prev_text, re.IGNORECASE):
                    found_ref = True
                    break

            if found_ref:
                return report  # 找到引用，通过检查

            # 如果没有找到引用，检查是否是章节标题
            # 章节标题正则（匹配形如 "3.1", "第三章", "3.1.1 模型架构" 等）
            chapter_title_pattern = r'^\s*\d+[\.\d]+|^第[一二三四五六七八九十0-9]+[章节]'

            if re.match(chapter_title_pattern, prev_text):
                # 是标题，继续向前查找
                prev_index -= 1
                continue

            # 不是标题也没有引用，报告错误
            report['ok'] = False
            report['messages'].append(
                messages.get('formula_reference_error', f'公式上一段落未提及该公式引用（如：公式{chapter}-{seq}）')
            )
            return report

        # 空段落，继续向前查找
        prev_index -= 1

    # 没找到有效的段落
    report['ok'] = False
    report['messages'].append(messages.get('formula_reference_error', f'公式上一段落未提及该公式引用'))
    return report


def validate_formula_format(paragraph, template, parsed_number=None, formula_content_text=None, target_math_elem=None, doc=None, dbg=False):
    """
    检查单个公式段落的格式
    - parsed_number: 已解析出的编号 (chapter, seq)
    - formula_content_text: 公式内容文本（不含编号）
    - target_math_elem: 目标 Math 对象（用于检测公式内容字体）
    - doc: 文档对象（用于引用检查）
    - dbg: 是否启用调试日志

    注意：当段落来自表格单元格（无法映射到 python-docx Paragraph 对象）时，
    paragraph 为 None，此时跳过制表位和 Math 对象格式检查，仅检查编号和引用。
    """
    report = {'ok': True, 'messages': [], 'details': {}}

    rules = template.get('formula_detection_rules', {})
    messages = template.get('messages', {})
    check_rules = template.get('check_rules', {})

    number_pattern = rules.get('number_pattern')
    tab_stops_config = rules.get('tab_stops', [])

    # 表格单元格段落（paragraph 为 None）不支持制表位/Math 对象 API，跳过这两项检查
    if paragraph is None:
        report['details']['tab_stops'] = {'skipped': True, 'reason': '表格单元格段落无 Paragraph 对象'}
        report['details']['math_objects'] = {'skipped': True, 'reason': '表格单元格段落无 Paragraph 对象'}
        # 编号检查
        report['details']['number'] = {'parsed': parsed_number is not None, 'value': parsed_number}
        if not parsed_number:
            report['ok'] = False
            report['messages'].append(messages.get('formula_number_missing', '未检测到公式编号'))
        # 字体和引用检查（通过 target_math_elem 和 doc 进行）
        report['details']['fonts'] = {'skipped': True, 'reason': '表格单元格段落无 Paragraph 对象'}
        ref_report = check_formula_reference(None, parsed_number, template, template, doc, dbg=dbg)
        report['details']['reference'] = {
            'ok': ref_report['ok'],
            'messages': ref_report['messages'] if not ref_report['ok'] else []
        }
        if not ref_report['ok']:
            report['ok'] = False
            report['messages'].extend(ref_report['messages'])
        # 格式检查通过，不输出确认消息
        return report

    # ========== 1. 制表位检查（根据模板配置执行） ==========
    tab_check_enabled = check_rules.get('tab_stops_check', True)
    if tab_check_enabled and tab_stops_config:
        tolerance = check_rules.get('tab_position_tolerance', 5)
        tab_ok, tab_issues, detected_tabs = check_tab_stops(
            paragraph, tab_stops_config, tolerance_chars=tolerance, dbg=dbg
        )
        report['details']['tab_stops'] = {
            'ok': tab_ok,
            'issues': tab_issues,
            'detected': detected_tabs,
            'expected': tab_stops_config
        }
        if not tab_ok:
            if tab_issues:
                report['messages'].append(f"对齐建议: {'; '.join(tab_issues[:2])}")
    else:
        tab_check_skipped = not tab_check_enabled
        report['details']['tab_stops'] = {'skipped': tab_check_skipped}

    # ========== 2. 数学对象检查 ==========
    has_math, math_objects, math_info = detect_math_objects(paragraph)
    report['details']['math_objects'] = {
        'has_math': has_math,
        'count': math_info.get('count', 0),
        'types': math_info.get('types', []),
        'preview': math_info.get('content_preview', [])
    }
    if not has_math:
        report['messages'].append(messages.get('math_object_missing', '未检测到Office Math对象（可能是手动输入的公式）'))

    # ========== 3. 编号检查 ==========
    report['details']['number'] = {'parsed': parsed_number is not None, 'value': parsed_number}
    if not parsed_number:
        report['ok'] = False
        report['messages'].append(messages.get('formula_number_missing', '未检测到公式编号'))

    # ========== 4. 字体检查（传递 target_math_elem 和 dbg） ==========
    font_ok, font_issues = check_formula_fonts(
        paragraph, math_objects, template, number_pattern,
        formula_content_text=formula_content_text,
        target_math_elem=target_math_elem,
        dbg=dbg
    )
    report['details']['fonts'] = {'correct': font_ok, 'issues': font_issues}
    if not font_ok:
        report['ok'] = False
        report['messages'].extend([f"字体问题: {x}" for x in font_issues])

    # ========== 5. 公式引用检查 ==========
    ref_report = check_formula_reference(paragraph, parsed_number, template, template, doc, dbg=dbg)
    report['details']['reference'] = {
        'ok': ref_report['ok'],
        'messages': ref_report['messages'] if not ref_report['ok'] else []
    }
    if not ref_report['ok']:
        report['ok'] = False
        report['messages'].extend(ref_report['messages'])

    # 格式检查通过，不输出确认消息

    return report


def check_numbering_by_chapter(numbers):
    report = {'ok': True, 'messages': []}

    if not numbers:
        return report

    chapter_to_seqs = {}
    for ch, seq in numbers:
        chapter_to_seqs.setdefault(ch, []).append(seq)

    for ch, seqs in chapter_to_seqs.items():
        seqs_sorted = sorted(seqs)
        if seqs_sorted[0] != 1:
            report['ok'] = False
            report['messages'].append(f"第{ch}章公式序号应从1开始，当前从{seqs_sorted[0]}开始")

        for i in range(len(seqs_sorted) - 1):
            if seqs_sorted[i + 1] - seqs_sorted[i] != 1:
                report['ok'] = False
                report['messages'].append(f"第{ch}章公式序号不连续：{seqs_sorted}")
                break

    return report


def check_doc_with_template(doc_path, template_identifier, skip_checks=None, debug=None, log_file_path=None):
    global _skip_checks_config
    _skip_checks_config = skip_checks or []

    try:
        template = load_template(template_identifier)
        dbg = _debug_enabled(template, debug)

        if dbg:
            logger.info("[Formula] 开始公式检测: doc=%s, template=%s", doc_path, template_identifier)

        doc = Document(doc_path)

        # 1. 先找所有可能是公式的候选（含 Math 对象 + 有编号）
        candidates = find_formula_candidates(doc, template, debug=dbg)

        # candidates 已经是过滤后的结果，每个 item 都包含 number 和 formula_content
        formula_paragraphs = []
        for item in candidates:
            num = item.get('number')
            if not num:
                continue

            # 把 paragraph 对象补上（用于后续格式检查）
            # 表格单元格内的段落不在 doc.paragraphs 中，paragraph 为 None
            item['paragraph'] = None
            try:
                item['paragraph'] = next(
                    p for p in doc.paragraphs if p._element is item['w_p']
                )
            except StopIteration:
                pass  # 保持 None（表格段落等）

            formula_paragraphs.append(item)

        if dbg:
            logger.info("[Formula] 最终识别公式数量=%s（已应用编号过滤）", len(formula_paragraphs))
        if dbg and formula_paragraphs:
            logger.info("[Formula] 最终识别到的公式列表（前50条预览）：")
            for k, fp in enumerate(formula_paragraphs[:50], start=1):
                num = fp.get('number')
                # 显示 formula_content（提取后的公式内容），而不是整个段落 text
                formula_preview = (fp.get('formula_content') or '').replace('\n', ' ')
                text_preview = (fp.get('text') or '').replace('\n', ' ')
                if len(formula_preview) > 160:
                    formula_preview = formula_preview[:160] + '...'
                if len(text_preview) > 160:
                    text_preview = text_preview[:160] + '...'
                logger.info(
                    "[Formula]  #%s idx=%s num=%s formula=%r text=%r",
                    k,
                    fp.get('paragraph_index', fp.get('w_p_index')),
                    num,
                    formula_preview,
                    text_preview
                )
        report = {
            'formula_detection': {'ok': True, 'messages': []},
            'numbering': {},
            'summary': [],
            'details': {
                'total_paragraphs': len(doc.paragraphs),
                'formula_paragraphs_count': len(formula_paragraphs),
                'formula_paragraphs': [],
                'debug': dbg
            }
        }

        messages = template.get('messages', {})

        if not formula_paragraphs:
            # 如果过滤后没有公式，按“通过”处理，不报“发现问题”
            report['formula_detection']['ok'] = True
            report['summary'].append(messages.get('summary_overall', '公式格式检查结果: {ok}').format(ok='通过'))
            stats_msg = f"检测统计：共 {report['details']['total_paragraphs']} 个段落，识别出 0 个带编号的公式段落"
            report['summary'].append(stats_msg)
            return report

        all_ok = True
        extracted_numbers = []

        for i, fp in enumerate(formula_paragraphs):
            paragraph = fp.get('paragraph')

            # 无论是否在文本框，都先统计编号
            num = fp.get('number')
            if isinstance(num, tuple):
                extracted_numbers.append(num)

            # 用公式编号作为标识（如 #3-1），没有编号则用索引
            num_text = fp.get('number_text', f"#{num[0]}-{num[1]}" if isinstance(num, tuple) else f"#{i+1}")
            formula_label = f"公式{num_text}"

            if paragraph is None:
                # 这是文本框/公式框里的段落，没有 Paragraph 对象，跳过深度格式检查
                para_report = {'ok': True, 'messages': ["文本框公式，跳过格式检查"], 'details': {}}
                para_text = fp.get('text', '')
            else:
                # 这是正文流里的段落，可以正常检查
                para_report = validate_formula_format(
                    paragraph, template,
                    parsed_number=fp.get('number'),
                    formula_content_text=fp.get('formula_content', ''),
                    target_math_elem=fp.get('target_math_elem'),  # 传入 Math 对象用于字体检测
                    doc=doc,  # 传入文档对象用于引用检查
                    dbg=debug  # 传入调试标志
                )
                para_text = (paragraph.text or '').strip()

            text_preview = para_text[:150] + ('...' if len(para_text) > 150 else '')

            para_info = {
                'index': i + 1,
                'paragraph_index': fp.get('paragraph_index', fp.get('w_p_index')),
                'text_preview': text_preview,
                'formula_label': formula_label,  # 添加公式编号标识
                'has_math_object': fp.get('has_math_object', False),
                'math_object_count': fp.get('math_object_count', 0),
                'has_formula_tab_stops': fp.get('has_formula_tab_stops', False),
                'has_formula_style': fp.get('has_formula_style', False),
                'confidence_score': fp.get('confidence_score', 10),
                'format_check': para_report
            }

            report['details']['formula_paragraphs'].append(para_info)

            # 只报告有问题的内容
            if not para_report['ok']:
                all_ok = False
                report['formula_detection']['ok'] = False
                # 直接输出具体问题，不添加前缀头
                report['formula_detection']['messages'].extend(para_report['messages'])

        numbering_report = check_numbering_by_chapter(extracted_numbers)
        report['numbering'] = numbering_report
        # 注意：不要把 numbering 的 messages 复制到 formula_detection，保持报告独立

        summary_tpl = messages.get('summary_overall', '公式格式检查结果: {ok}')
        report['summary'].append(summary_tpl.format(ok='通过' if all_ok else '发现问题'))

        stats_msg = f"检测统计：共 {report['details']['total_paragraphs']} 个段落，识别出 {len(formula_paragraphs)} 个带编号的公式段落"
        report['summary'].append(stats_msg)

        return report

    except Exception as e:
        logger.error("公式检测过程中发生异常", exc_info=True)
        return {
            'formula_detection': {'ok': False, 'messages': [f"公式检测过程中发生异常: {str(e)}"]},
            'summary': [f"检查失败: {str(e)}"],
            'details': {}
        }


def print_help():
    print("用法:")
    print("  python Formula_detect.py check <paper.docx> <template.json_or_name>")


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
