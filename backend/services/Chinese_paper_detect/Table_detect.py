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




def detect_font_for_run(run, paragraph=None):
    """检测 run 的字号、英文字体(ASCII/hAnsi)、中文字体(EastAsia)、加粗"""
    font_size = None
    font_ascii = None
    font_eastasia = None
    is_bold = None

    if not run:
        return 12.0, "Times New Roman", "宋体", False

    try:
        if run.font and run.font.size and hasattr(run.font.size, 'pt'):
            font_size = float(run.font.size.pt)

        if font_size is None and paragraph and paragraph.style and getattr(paragraph.style, 'font', None):
            try:
                if paragraph.style.font.size and hasattr(paragraph.style.font.size, 'pt'):
                    font_size = float(paragraph.style.font.size.pt)
            except Exception:
                pass

        if font_size is None and hasattr(run._element, 'rPr'):
            sz_nodes = run._element.xpath('.//w:sz')
            if sz_nodes and sz_nodes[0].get(qn('w:val')):
                font_size = float(sz_nodes[0].get(qn('w:val'))) / 2.0

        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style, 'element'):
            sz_nodes = paragraph.style.element.xpath('.//w:sz')
            if sz_nodes and sz_nodes[0].get(qn('w:val')):
                font_size = float(paragraph.style.element.xpath('.//w:sz')[0].get(qn('w:val'))) / 2.0
    except Exception:
        pass

    font_size = font_size if font_size is not None else 12.0

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
    except Exception:
        pass

    font_ascii = font_ascii if font_ascii else "Times New Roman"
    font_eastasia = font_eastasia if font_eastasia else ""

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
                is_bold = True
    except Exception:
        pass

    is_bold = bool(is_bold) if is_bold is not None else False

    return font_size, font_ascii, font_eastasia, is_bold


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


def extract_tables_with_body_index(doc):
    """
    先枚举文档里所有表格（w:tbl），并记录：
    - table_body_index: 在 doc.element.body 的位置
    - table_index: 在 doc.tables 中的位置
    - table: python-docx Table 对象
    """
    items = []
    table_idx = -1
    for body_i, el in enumerate(doc.element.body):
        if el.tag.endswith('tbl'):
            table_idx += 1
            if table_idx < len(doc.tables):
                items.append({
                    'table_body_index': body_i,
                    'table_index': table_idx,
                    'table': doc.tables[table_idx],
                })
    return items


def attach_caption_to_table_item(doc, table_item, tpl, body_p_map, debug=None):
    """
    对单个表格：从表格上方回溯找 caption（中文/英文），并解析 chapter/seq/title。

    规则：
    - 从 table_body_index-1 往上找 w:p，最多找 N 个段落（默认 30，可从模板读）
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

    max_back = int(rules.get('caption_search_back_paragraphs', 30))

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

    return 0


def check_caption_text_rules(table_item, tpl):
    """检查中英文表题文本规则：编号一致、中文表题不含标点等（基于 table_item）"""
    report = {'ok': True, 'messages': []}
    messages = tpl.get('messages', {})

    cn_para = table_item.get('caption_cn_paragraph')
    en_para = table_item.get('caption_en_paragraph')
    is_continuation = table_item.get('is_continuation', False)

    # 续表允许没有英文表题
    if cn_para is None:
        report['ok'] = False
        report['messages'].append(messages.get('caption_missing_cn', '未找到中文表题'))
    if en_para is None and not is_continuation:
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


def check_caption_format(paragraph, expected, tpl, language='cn'):
    
    report = {'ok': True, 'messages': []}

    messages = tpl.get('messages', {})

    non_empty_runs = [r for r in paragraph.runs if (r.text or '').strip()]
    main_run = max(non_empty_runs, key=lambda r: len((r.text or '').strip()), default=None)
    if not main_run:
        report['ok'] = False
        report['messages'].append("表题段落没有有效文本")
        return report

    size_pt, font_ascii, font_eastasia, is_bold = detect_font_for_run(main_run, paragraph)
    logger.info(
        "[DBG_FONT] lang=%s para=%r | main_run=%r | eastAsia=%r ascii=%r",
        language,
        paragraph.text,
        main_run.text,
        font_eastasia,
        font_ascii
    )
    if not should_skip_check('font_size'):
        expected_size = float(expected.get('font_size_pt', 10.5))
        if abs(size_pt - expected_size) > 0.5:
            report['ok'] = False
            if language == 'cn':
                report['messages'].append(messages.get('caption_cn_font_size_error', '中文表题字号应为五号(10.5pt)'))
            else:
                report['messages'].append(messages.get('caption_en_font_size_error', '英文表题字号应为五号(10.5pt)'))

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
                        report['messages'].append(
                            messages.get('caption_cn_font_name_error', f"中文表题字体应为{expected_cn_font}")
                        )
        else:
            expected_en_font = expected.get('font_name_ascii')
            if expected_en_font and expected_en_font.lower() not in (font_ascii or '').lower():
                report['ok'] = False
                report['messages'].append(messages.get('caption_en_font_name_error', f"英文表题字体应为{expected_en_font}"))

    if not should_skip_check('bold') and 'bold' in expected:
        expected_bold = bool(expected.get('bold'))
        if is_bold != expected_bold:
            report['ok'] = False
            if language == 'cn':
                report['messages'].append(messages.get('caption_cn_bold_error', '中文表题不应加粗'))
            else:
                report['messages'].append(messages.get('caption_en_bold_error', '英文表题不应加粗'))

    if not should_skip_check('color') and expected.get('no_special_color', True):
        if not detect_run_color_is_default(main_run):
            report['ok'] = False
            if language == 'cn':
                report['messages'].append(messages.get('caption_cn_color_error', '中文表题应为无特殊颜色'))
            else:
                report['messages'].append(messages.get('caption_en_color_error', '英文表题应为无特殊颜色'))

    if not should_skip_check('alignment') and expected.get('alignment'):
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        exp = alignment_map.get(str(expected.get('alignment')).lower())
        if exp is not None:
            actual = detect_paragraph_alignment(paragraph)
            if actual != exp:
                report['ok'] = False
                report['messages'].append(messages.get('caption_alignment_error', '表题段落对齐方式不符合要求'))

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
    检查表格引用：表格上一个段落必须提及该表格引用（表{章}-{序}）
    """
    report = {'ok': True, 'messages': []}
    messages = tpl.get('messages', {})
    check_rules = tpl.get('check_rules', {})

    # 检查是否启用引用检查
    reference_check = check_rules.get('table_reference_check', True)
    if not reference_check:
        return report

    # 跳过续表
    if table_item.get('is_continuation', False):
        return report

    chapter = table_item.get('chapter')
    seq = table_item.get('seq')

    if chapter is None or seq is None:
        return report  # 无法获取编号，跳过检查

    # 获取表格的 body_index
    table_body_index = table_item.get('table_body_index')
    if table_body_index is None:
        return report

    # 获取上一个段落元素（直接通过索引获取）
    prev_body_index = table_body_index - 1
    if prev_body_index < 0:
        report['ok'] = False
        report['messages'].append(messages.get('table_reference_error', f'表格上一段落未提及该表格引用'))
        return report

    # 直接获取上一个元素
    try:
        prev_elem = doc.element.body[prev_body_index]
    except IndexError:
        report['ok'] = False
        report['messages'].append(messages.get('table_reference_error', f'表格上一段落未提及该表格引用'))
        return report

    # 合并的表题正则（匹配 "Table 3-1 Title" 或 "表3-1 标题"）
    # 格式：Table/表 + 数字 + 分隔符 + 数字，忽略中间的空格
    caption_pattern = r'^\s*(Table|表)\s*\d+[-－.．]?\s*\d+'
    # 章节标题正则（匹配形如 "3.1", "第三章", "3.1.1" 等）
    chapter_title_pattern = r'^\s*\d+[\.\d]*\s*|^第[一二三四五六七八九十0-9]+[章节]'

    # 如果不是段落，则继续向前查找
    while prev_body_index >= 0:
        if prev_elem.tag.endswith('p'):
            # 获取段落文本
            prev_text = _strip_invisible((''.join(prev_elem.xpath('.//w:t/text()')) or '').strip())

            if prev_text:
                # 检查是否是表题（英文表题如 "Table 3-1 Title" 或中文表题如 "表3-1 标题"）
                if re.match(caption_pattern, prev_text, re.IGNORECASE):
                    # 是表题，继续向上查找
                    prev_body_index -= 1
                    if prev_body_index < 0:
                        break
                    try:
                        prev_elem = doc.element.body[prev_body_index]
                    except IndexError:
                        break
                    continue

                # 检查是否包含表格引用
                # 匹配模式：表3-1, 见表格3-1, 如下表3-1等
                # 忽略表名和引用词之间的空格
                ref_patterns = [
                    rf'表\s*{chapter}\s*[-－.．]\s*{seq}',  # 表3-1
                    rf'表格\s*{chapter}\s*[-－.．]\s*{seq}',  # 表格3-1
                    rf'下表\s*{chapter}\s*[-－.．]\s*{seq}',  # 下表3-1
                    rf'上表\s*{chapter}\s*[-－.．]\s*{seq}',  # 上表3-1
                    rf'见表\s*{chapter}\s*[-－.．]\s*{seq}',  # 见表3-1
                    rf'如表\s*{chapter}\s*[-－.．]\s*{seq}',  # 如表3-1
                ]

                found_ref = False
                for pattern in ref_patterns:
                    if re.search(pattern, prev_text, re.IGNORECASE):
                        found_ref = True
                        break

                if found_ref:
                    return report  # 找到引用，通过检查

                # 如果没有找到引用，检查是否是章节标题
                if re.match(chapter_title_pattern, prev_text):
                    # 是标题，继续向上查找
                    prev_body_index -= 1
                    if prev_body_index < 0:
                        break
                    try:
                        prev_elem = doc.element.body[prev_body_index]
                    except IndexError:
                        break
                    continue

                # 不是标题也没有引用，报告错误
                report['ok'] = False
                report['messages'].append(
                    messages.get('table_reference_error', f'表格上一段落未提及该表格引用（如：表{chapter}-{seq}）')
                )
                return report

        # 继续向上查找
        prev_body_index -= 1
        if prev_body_index < 0:
            break
        try:
            prev_elem = doc.element.body[prev_body_index]
        except IndexError:
            break

    # 没找到有效的段落或没有引用
    report['ok'] = False
    report['messages'].append(messages.get('table_reference_error', f'表格上一段落未提及该表格引用'))
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

        if tblBorders is not None:
            left_border = tblBorders.find(qn('w:left'))
            right_border = tblBorders.find(qn('w:right'))
            inside_v = tblBorders.find(qn('w:insideV'))

            if left_border is not None and left_border.get(qn('w:val')) not in [None, 'none', 'nil']:
                issues.append("表格不应有左边框（三线表格式）")
            if right_border is not None and right_border.get(qn('w:val')) not in [None, 'none', 'nil']:
                issues.append("表格不应有右边框（三线表格式）")
            if inside_v is not None and inside_v.get(qn('w:val')) not in [None, 'none', 'nil']:
                issues.append("表格不应有内部竖线（三线表格式）")

        if tpl.get('check_rules', {}).get('border_width_check', False):
            border_config = tpl.get('table_detection_rules', {}).get('table_style', {}).get('border_width', {})
            tolerance = tpl.get('check_rules', {}).get('border_width_tolerance', 0.1)

            expected_top = float(border_config.get('top_line', 1.5))
            expected_bottom = float(border_config.get('bottom_line', 1.5))
            expected_header = float(border_config.get('header_line', 0.75))

            # 获取消息模板，如果配置中有期望值则使用配置值
            top_msg_template = messages.get('top_border_width_error', f'顶线宽度应为{expected_top}磅，实际为{{actual}}磅')
            header_msg_template = messages.get('header_border_width_error', f'表头底线宽度应为{expected_header}磅，实际为{{actual}}磅')
            bottom_msg_template = messages.get('bottom_border_width_error', f'底线宽度应为{expected_bottom}磅，实际为{{actual}}磅')

            border_width_issues = []

            if len(table.rows) > 0 and table.rows[0].cells:
                tc = table.rows[0].cells[0]._element
                tcPr = tc.find(qn('w:tcPr'))
                if tcPr is not None:
                    tcBorders = tcPr.find(qn('w:tcBorders'))
                    if tcBorders is not None:
                        top_border = tcBorders.find(qn('w:top'))
                        bottom_border = tcBorders.find(qn('w:bottom'))

                        if top_border is not None:
                            sz = top_border.get(qn('w:sz'))
                            if sz:
                                actual_width = float(sz) / 8.0
                                if abs(actual_width - expected_top) > tolerance:
                                    border_width_issues.append(top_msg_template.format(actual=round(actual_width, 2)))

                        if bottom_border is not None:
                            sz = bottom_border.get(qn('w:sz'))
                            if sz:
                                actual_width = float(sz) / 8.0
                                if abs(actual_width - expected_header) > tolerance:
                                    border_width_issues.append(header_msg_template.format(actual=round(actual_width, 2)))

            if len(table.rows) > 0 and table.rows[-1].cells:
                tc = table.rows[-1].cells[0]._element
                tcPr = tc.find(qn('w:tcPr'))
                if tcPr is not None:
                    tcBorders = tcPr.find(qn('w:tcBorders'))
                    if tcBorders is not None:
                        bottom_border = tcBorders.find(qn('w:bottom'))
                        if bottom_border is not None:
                            sz = bottom_border.get(qn('w:sz'))
                            if sz:
                                actual_width = float(sz) / 8.0
                                if abs(actual_width - expected_bottom) > tolerance:
                                    border_width_issues.append(bottom_msg_template.format(actual=round(actual_width, 2)))

            issues.extend(border_width_issues)

        return len(issues) == 0, issues

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
    table_items = extract_tables_with_body_index(doc)

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

    for item in table_items:
        cn_para = item.get('caption_cn_paragraph')
        en_para = item.get('caption_en_paragraph')

        text_rules = check_caption_text_rules(item, tpl)

        # 格式检查：缺失就直接报错，不传 None
        if cn_para is None:
            cn_format = {'ok': False, 'messages': [messages.get('caption_missing_cn', '未找到中文表题')]}
        else:
            cn_format = check_caption_format(cn_para, expected_cn, tpl, language='cn')

        if en_para is None:
            en_format = {'ok': False, 'messages': []}
        else:
            en_format = check_caption_format(en_para, expected_en, tpl, language='en')

        table = item.get('table')
        has_table = table is not None

        if not has_table:
            style_ok, style_issues = False, [messages.get('table_not_found', '未找到表格对象')]
        else:
            style_ok, style_issues = check_table_style_three_line(table, tpl)

        table_item_ok = text_rules['ok'] and cn_format['ok'] and en_format['ok'] and has_table and style_ok
        if not table_item_ok:
            report['table_detection']['ok'] = False

        # 组织输出（你可以按需要改字段）
        table_desc = None
        if item.get('chapter') is not None and item.get('seq') is not None:
            if item.get('is_continuation', False):
                table_desc = f"表{item.get('chapter')}-{item.get('seq')}（续）"
            else:
                table_desc = f"表{item.get('chapter')}-{item.get('seq')}"
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
                'messages': style_issues if not style_ok else [messages.get('table_style_ok', '表格为三线表格式')]
            }
        }

        # 添加表格内容对齐检查（续表跳过）
        if has_table and not item.get('is_continuation', False):
            content_align_ok, content_align_issues, content_align_detected = check_table_content_alignment(table, tpl)
            out_item['table_content_alignment'] = {
                'ok': content_align_ok,
                'messages': content_align_issues if not content_align_ok else [messages.get('table_content_alignment_ok', '表格内容对齐方式正确')],
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
            'messages': ref_report['messages'] if not ref_report['ok'] else [messages.get('table_reference_ok', '表格引用检查通过')]
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
