#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
英文关键词检测器
依据模板 Chinese_paper_detect_templates/English_Keywords.json
"""

import os
import sys
import json
import re
from pathlib import Path
from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn

# 便于独立运行
if __name__ == "__main__" and __package__ is None:
    file = Path(__file__).resolve()
    parent, root = file.parent, file.parents[1]
    sys.path.append(str(root))
    try:
        sys.path.remove(str(parent))
    except ValueError:
        pass

_skip_checks_config = []


def should_skip_check(check_name):
    global _skip_checks_config
    return check_name in (_skip_checks_config or [])


# ---------- 模板加载 ----------
def resolve_template_path(identifier):
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
    raise FileNotFoundError(f"Template not found: '{identifier}' (tried {candidates})")


def load_template(identifier):
    tpl_path = resolve_template_path(identifier)
    with open(tpl_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- 基础检测工具 ----------
def detect_font_for_run(run, paragraph=None):
    font_size = None
    font_name_ascii = None
    is_bold = None
    is_italic = False

    if not run:
        return 12.0, "Times New Roman", False, False, 1.0

    # 字号：直接格式
    try:
        if run.font and run.font.size and hasattr(run.font.size, "pt"):
            font_size = float(run.font.size.pt)

        # run.style
        if font_size is None and getattr(run, "style", None) and getattr(run.style, "font", None):
            if run.style.font.size and hasattr(run.style.font.size, "pt"):
                font_size = float(run.style.font.size.pt)

        # paragraph.style
        if font_size is None and paragraph and paragraph.style and getattr(paragraph.style, "font", None):
            if paragraph.style.font.size and hasattr(paragraph.style.font.size, "pt"):
                font_size = float(paragraph.style.font.size.pt)

        # 段落样式 XML
        if font_size is None and paragraph and paragraph.style and hasattr(paragraph.style, "element"):
            sz_nodes = paragraph.style.element.xpath(".//w:sz")
            if sz_nodes and sz_nodes[0].get(qn("w:val")):
                font_size = float(sz_nodes[0].get(qn("w:val"))) / 2.0

        # run 的 rPr
        if font_size is None and hasattr(run._element, "rPr"):
            sz_nodes = run._element.xpath(".//w:sz")
            if sz_nodes and sz_nodes[0].get(qn("w:val")):
                font_size = float(sz_nodes[0].get(qn("w:val"))) / 2.0
    except Exception:
        pass
    font_size = font_size if font_size is not None else 12.0

    # 字体名称
    try:
        if run.font and run.font.name:
            font_name_ascii = run.font.name

        if hasattr(run._element, "rPr"):
            rpr = run._element.rPr
            if rpr is not None:
                rfonts = rpr.find(qn("w:rFonts"))
                if rfonts is not None:
                    xml_ascii = rfonts.get(qn("w:ascii"))
                    xml_hansi = rfonts.get(qn("w:hAnsi"))
                    if xml_ascii:
                        font_name_ascii = xml_ascii
                    elif xml_hansi and font_name_ascii is None:
                        font_name_ascii = xml_hansi
    except Exception:
        pass

    font_name_ascii = font_name_ascii if font_name_ascii else "Times New Roman"

    # 加粗和斜体
    try:
        if run.font:
            if run.font.bold is not None:
                is_bold = run.font.bold
            if run.font.italic is not None:
                is_italic = run.font.italic

        if is_bold is None and getattr(run, "style", None) and getattr(run.style, "font", None):
            if run.style.font.bold is not None:
                is_bold = run.style.font.bold

        if is_bold is None and paragraph and paragraph.style and getattr(paragraph.style, "font", None):
            if paragraph.style.font.bold is not None:
                is_bold = paragraph.style.font.bold

        if is_bold is None and hasattr(run._element, "rPr"):
            b_nodes = run._element.xpath(".//w:b")
            if b_nodes:
                is_bold = True

        is_bold = bool(is_bold) if is_bold is not None else False
        is_italic = bool(is_italic)
    except Exception:
        pass

    # 行间距
    line_spacing = 1.0
    try:
        if paragraph and paragraph.paragraph_format.line_spacing:
            line_spacing = float(paragraph.paragraph_format.line_spacing)
        elif paragraph and paragraph.style and paragraph.style.paragraph_format.line_spacing:
            line_spacing = float(paragraph.style.paragraph_format.line_spacing)
    except Exception:
        pass

    return font_size, font_name_ascii, is_bold, is_italic, line_spacing


def get_font_size(pt_size, tpl=None):
    """字体大小转换为中文字号"""
    if tpl and "check_rules" in tpl and "font_size_mapping" in tpl["check_rules"]:
        size_config = tpl["check_rules"]["font_size_mapping"]
        size_map = {}
        for key, value in size_config.items():
            try:
                size_map[float(key)] = value
            except (ValueError, TypeError):
                continue
    else:
        size_map = {
            9: "小五",
            10.5: "五号",
            12: "小四",
            14: "四号",
            16: "三号",
            18: "小二",
            22: "二号",
            24: "小一",
            26: "一号",
        }

    if not size_map:
        return f"{pt_size}pt"

    closest_size = min(size_map.keys(), key=lambda x: abs(x - pt_size))
    return size_map[closest_size]


def get_line_spacing_name(spacing, tpl=None):
    """行间距转换为中文描述"""
    if tpl and "check_rules" in tpl and "line_spacing_mapping" in tpl["check_rules"]:
        spacing_config = tpl["check_rules"]["line_spacing_mapping"]
        spacing_map = {}
        for key, value in spacing_config.items():
            try:
                spacing_map[float(key)] = value
            except (ValueError, TypeError):
                continue
    else:
        spacing_map = {
            1.0: "单倍行距",
            1.15: "1.15倍行距",
            1.25: "1.25倍行距",
            1.5: "1.5倍行距",
            2.0: "双倍行距",
        }

    if not spacing_map:
        return f"{spacing}倍行距"

    closest_spacing = min(spacing_map.keys(), key=lambda x: abs(x - spacing))
    return spacing_map[closest_spacing]


def get_alignment_name(alignment_value, tpl=None):
    """段落对齐方式转换为中文描述"""
    alignment_map = {0: "左对齐", 1: "居中对齐", 2: "右对齐", 3: "两端对齐"}
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


# ---------- 关键词检测逻辑 ----------
def find_abstract_end(doc, abstract_header_pattern=None, keywords_header_pattern=None):
    """
    查找英文摘要结束位置（用于检查空行）
    参数:
        doc: Word文档对象
        abstract_header_pattern: 摘要标题的正则表达式模式（从模板中读取）
        keywords_header_pattern: 关键词标题的正则表达式模式（从模板中读取）
    """
    # 如果没有提供模式，使用默认值
    if abstract_header_pattern is None:
        abstract_header_pattern = r"^\s*ABSTRACT\s*$"
    if keywords_header_pattern is None:
        keywords_header_pattern = r"KEY\s+WORDS"
    
    # 从keywords_header_pattern中提取用于搜索的模式
    # 模板中的模式通常是 "^\\s*KEY\\s+WORDS\\s*[:：]?\\s*(.+)$"
    # 我们需要提取出 "KEY\\s+WORDS" 部分用于搜索
    keywords_search_pattern = keywords_header_pattern
    # 尝试提取 KEY WORDS 部分
    # 匹配 "KEY" 后面跟着空白字符和 "WORDS" 的模式
    # 处理转义字符：模板中可能是 "\\s" 或 "\s"
    match = re.search(r"KEY\s*[\\]?s\s*\+?\s*WORDS", keywords_search_pattern, re.IGNORECASE)
    if match:
        keywords_search_pattern = match.group(0)
        # 确保使用正确的转义格式
        keywords_search_pattern = keywords_search_pattern.replace("\\\\s", r"\s").replace("\\s", r"\s")
    else:
        # 如果提取失败，使用默认值
        keywords_search_pattern = r"KEY\s+WORDS"
    
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        # 使用从模板读取的正则表达式查找"ABSTRACT"标题
        if re.match(abstract_header_pattern, text, re.IGNORECASE):
            # 从ABSTRACT标题后开始查找摘要内容结束位置
            for j in range(idx + 1, len(doc.paragraphs)):
                para_text = doc.paragraphs[j].text.strip()
                if not para_text:
                    continue
                # 使用从模板读取的正则表达式查找KEY WORDS标题
                if re.search(keywords_search_pattern, para_text, re.IGNORECASE):
                    return j - 1
    return None


def check_english_keywords_structure(doc, tpl):
    """
    检查英文关键词结构
    返回 {'ok': bool, 'messages': [], 'keywords_paragraph': paragraph, 'keywords_text': str, 'keywords_list': []}
    """
    report = {
        "ok": True,
        "messages": [],
        "keywords_paragraph": None,
        "keywords_text": "",
        "keywords_list": [],
    }

    structure_rules = tpl.get("structure_rules", {})
    header_pattern = structure_rules.get("header_pattern", r"^\\s*KEY\\s+WORDS\\s*[:：]?\\s*(.+)$")
    expected_separator = structure_rules.get("separator", ",")
    min_count = structure_rules.get("min_keywords_count", 3)
    max_count = structure_rules.get("max_keywords_count", 5)
    blank_lines_before = structure_rules.get("blank_lines_before", 1)

    # 查找KEY WORDS段落
    keywords_para = None
    keywords_idx = None

    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if re.search(header_pattern, text, re.IGNORECASE):
            keywords_para = paragraph
            keywords_idx = idx
            break

    if not keywords_para:
        report["ok"] = False
        error_msg = tpl.get("messages", {}).get("structure_header_error")
        if error_msg:
            report["messages"].append(error_msg)
        else:
            report["messages"].append("未找到 KEY WORDS 段落")
        return report

    report["keywords_paragraph"] = keywords_para

    # 检查标题格式
    keywords_text = keywords_para.text.strip()
    match = re.search(header_pattern, keywords_text, re.IGNORECASE)
    if match:
        ok_msg = tpl.get("messages", {}).get("structure_header_ok")
        if ok_msg:
            report["messages"].append(ok_msg)
        keywords_content = match.group(1).strip()
    else:
        report["ok"] = False
        error_msg = tpl.get("messages", {}).get("structure_header_error")
        if error_msg:
            report["messages"].append(error_msg)
        keywords_content = keywords_text

    report["keywords_text"] = keywords_content

    # 检查摘要与关键词之间的空行
    # 从English_Abstract.json模板中读取ABSTRACT标题的正则表达式
    abstract_header_pattern = None
    try:
        abstract_tpl = load_template("English_Abstract")
        abstract_structure_rules = abstract_tpl.get("structure_rules", {})
        abstract_header_pattern = abstract_structure_rules.get("header_pattern", r"^\s*ABSTRACT\s*$")
    except Exception:
        # 如果加载失败，使用默认值
        abstract_header_pattern = r"^\s*ABSTRACT\s*$"
    
    # 从当前模板中读取KEY WORDS标题的正则表达式
    keywords_header_pattern = structure_rules.get("header_pattern", r"^\\s*KEY\\s+WORDS\\s*[:：]?\\s*(.+)$")
    
    abstract_end_idx = find_abstract_end(doc, abstract_header_pattern, keywords_header_pattern)
    if abstract_end_idx is not None and keywords_idx is not None:
        blank_count = keywords_idx - abstract_end_idx - 1
        if blank_count != blank_lines_before:
            report["ok"] = False
            error_msg = tpl.get("messages", {}).get("structure_blank_before_error")
            if error_msg:
                report["messages"].append(error_msg)
        else:
            ok_msg = tpl.get("messages", {}).get("structure_blank_before_ok")
            if ok_msg:
                report["messages"].append(ok_msg)

    # 检查分隔符和关键词数量
    if keywords_content:
        # 使用英文逗号分隔
        keywords_list = [kw.strip() for kw in re.split(r",", keywords_content) if kw.strip()]

        # 检查分隔符
        separators = re.findall(r"[，,;；]", keywords_content)
        if separators:
            wrong_separators = [sep for sep in separators if sep != expected_separator]
            if wrong_separators:
                report["ok"] = False
                error_msg = tpl.get("messages", {}).get("structure_separator_error")
                if error_msg:
                    report["messages"].append(error_msg)
            else:
                ok_msg = tpl.get("messages", {}).get("structure_separator_ok")
                if ok_msg:
                    report["messages"].append(ok_msg)

        # 检查关键词数量
        keyword_count = len(keywords_list)
        if keyword_count < min_count:
            report["ok"] = False
            msg_tpl = tpl.get("messages", {}).get("structure_count_few")
            if msg_tpl:
                try:
                    report["messages"].append(msg_tpl.format(count=keyword_count, min=min_count))
                except:
                    report["messages"].append(msg_tpl)
        elif keyword_count > max_count:
            report["ok"] = False
            msg_tpl = tpl.get("messages", {}).get("structure_count_many")
            if msg_tpl:
                try:
                    report["messages"].append(msg_tpl.format(count=keyword_count, max=max_count))
                except:
                    report["messages"].append(msg_tpl)
        else:
            ok_msg = tpl.get("messages", {}).get("structure_count_ok")
            if ok_msg:
                try:
                    report["messages"].append(ok_msg.format(count=keyword_count))
                except:
                    report["messages"].append(ok_msg)

        report["keywords_list"] = keywords_list

    return report


def check_english_keywords_format(paragraph, tpl):
    """
    检查英文关键词格式
    返回 {'ok': bool, 'messages': []}
    """
    report = {"ok": True, "messages": []}

    if not paragraph or not paragraph.runs:
        report["ok"] = False
        report["messages"].append("关键词段落没有文本内容")
        return report

    format_rules = tpl.get("format_rules", {}).get("keywords", {})
    issues = []

    # 检测第一个非空run的格式
    main_run = None
    for run in paragraph.runs:
        if run.text.strip():
            main_run = run
            break

    if not main_run:
        report["ok"] = False
        report["messages"].append("关键词段落没有有效文本")
        return report

    # 检测实际格式
    actual_size_pt, actual_font_ascii, actual_bold, actual_italic, actual_line_spacing = detect_font_for_run(
        main_run, paragraph
    )

    # 字体大小检查
    if not should_skip_check("font_size") and "font_size_pt" in format_rules:
        expected_size_pt = float(format_rules["font_size_pt"])
        actual_size_name = get_font_size(actual_size_pt, tpl)
        expected_size_name = get_font_size(expected_size_pt, tpl)
        if abs(actual_size_pt - expected_size_pt) > 0.5:
            issues.append(
                f"字体大小应为{expected_size_name}（{expected_size_pt}pt），实际为{actual_size_name}（{actual_size_pt}pt）"
            )

    # 字体名称检查
    if not should_skip_check("font_name") and "english_font" in format_rules:
        expected_font = format_rules.get("english_font", "Times New Roman")
        if expected_font.lower() not in actual_font_ascii.lower():
            issues.append(f"字体应为{expected_font}，实际为{actual_font_ascii}")

    # 加粗检查
    if not should_skip_check("bold") and "bold" in format_rules:
        expected_bold = bool(format_rules["bold"])
        if actual_bold != expected_bold:
            bold_status = "加粗" if expected_bold else "不加粗"
            actual_status = "加粗" if actual_bold else "不加粗"
            issues.append(f"字体应为{bold_status}，实际为{actual_status}")

    # 行间距检查
    if not should_skip_check("spacing") and "line_spacing" in format_rules:
        expected_line_spacing = float(format_rules["line_spacing"])
        if abs(actual_line_spacing - expected_line_spacing) > 0.1:
            actual_spacing_name = get_line_spacing_name(actual_line_spacing, tpl)
            expected_spacing_name = get_line_spacing_name(expected_line_spacing, tpl)
            issues.append(
                f"行间距应为{expected_spacing_name}（{expected_line_spacing}倍），实际为{actual_spacing_name}（{actual_line_spacing}倍）"
            )

    # 段落对齐检查
    if "alignment" in format_rules:
        expected_alignment_str = str(format_rules["alignment"])
        alignment_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        expected_alignment = alignment_map.get(expected_alignment_str, 0)

        actual_alignment = detect_paragraph_alignment(paragraph)
        if actual_alignment != expected_alignment:
            actual_alignment_name = get_alignment_name(actual_alignment, tpl)
            expected_alignment_name = get_alignment_name(expected_alignment, tpl)
            issues.append(f"段落应为{expected_alignment_name}，实际为{actual_alignment_name}")

    # 缩进检查
    if "first_line_indent" in format_rules or "left_indent" in format_rules:
        first_line_indent, left_indent, right_indent = detect_paragraph_indent(paragraph)

        if "first_line_indent" in format_rules:
            expected_first_indent = float(format_rules["first_line_indent"])
            if abs(first_line_indent - expected_first_indent) > 1.0:
                issues.append(f"首行缩进应为{expected_first_indent}pt，实际为{first_line_indent:.1f}pt")

        if "left_indent" in format_rules:
            expected_left_indent = float(format_rules["left_indent"])
            if abs(left_indent - expected_left_indent) > 1.0:
                issues.append(f"左缩进应为{expected_left_indent}pt，实际为{left_indent:.1f}pt")

    if issues:
        report["ok"] = False
        header = tpl.get("messages", {}).get("format_keywords_issue_header")
        if header:
            report["messages"].append(header)
        report["messages"].extend([f"  - {i}" for i in issues])
    else:
        ok_msg = tpl.get("messages", {}).get("format_keywords_ok")
        if ok_msg:
            report["messages"].append(ok_msg)

    return report


def check_english_keywords_with_template(doc_path, template_identifier, skip_checks=None):
    """
    主检查函数：检查英文关键词格式
    参数:
        doc_path: 文档路径
        template_identifier: 模板标识符
        skip_checks: 要跳过的检测项列表，如 ['font_size', 'bold']
    """
    global _skip_checks_config
    _skip_checks_config = skip_checks or []

    tpl = load_template(template_identifier)
    doc = Document(doc_path)

    # 执行各项检查
    structure_report = check_english_keywords_structure(doc, tpl)

    format_report = {"ok": True, "messages": []}
    if structure_report.get("keywords_paragraph"):
        format_report = check_english_keywords_format(structure_report["keywords_paragraph"], tpl)

    # 组装报告
    report = {"structure": structure_report, "format": format_report, "summary": []}

    # 生成总结
    all_ok = structure_report["ok"] and format_report["ok"]
    summary_tpl = tpl.get("messages", {}).get("summary_overall")
    if summary_tpl:
        try:
            report["summary"].append(summary_tpl.format(ok="通过" if all_ok else "失败"))
        except Exception:
            report["summary"].append(str(summary_tpl))

    return report


# ---------- 报告输出 ----------
def print_english_keywords_report(report):
    """打印英文关键词检查报告"""
    print("=== 英文关键词检查报告 ===")

    sections = [("structure", "结构检测"), ("format", "格式检测")]

    for sec_key, sec_name in sections:
        info = report.get(sec_key, {})
        print(f"--- {sec_name} ---")
        print(" 状态:", "✓ 通过" if info.get("ok", False) else "✗ 失败")
        for m in info.get("messages", []):
            print("  -", m)

    print("--- 总结 ---")
    for s in report.get("summary", []):
        print(" ", s)


def print_help():
    print("使用方法:")
    print("  python English_Keywords_detect.py check <paper.docx> <template.json_or_name>")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "check":
        paper_path = sys.argv[2]
        tpl_id = sys.argv[3]
        if not os.path.isfile(paper_path):
            print(f"论文文件不存在: {paper_path}")
            sys.exit(1)
        try:
            print("=== 开始英文关键词格式检查 ===")
            report = check_english_keywords_with_template(paper_path, tpl_id)
        except Exception as e:
            print("检查时出错:", e)
            import traceback

            traceback.print_exc()
            sys.exit(1)
        print_english_keywords_report(report)
    else:
        print_help()
        sys.exit(0)

