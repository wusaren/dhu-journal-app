"""
中文论文批注生成器（独立模块）

职责：
- 把检测器的报告（all_reports）通过 adapter 转成标准 Issue 列表
- 使用多种 locator 定位到文档段落索引
- 使用 Commenter 在 docx 副本上添加批注并保存

当前实现包含：
- Issue dataclass
- Locator 注册与若干内置 locator（index, keyword, abstract_title, abstract_content, keywords_title, keywords_content, content_paragraph, table_caption_cn, table_caption_en, formula_paragraph）
- Commenter（只打开一次 doc，按 paragraph index 添加注释并保存）
- Adapter：abstract_adapter, keywords_adapter, table_adapter, formula_adapter
- orchestrator 函数：annotate_chinese_abstract_and_keywords(docx_path, all_reports, output_dir)

说明：此模块为独立实现，不依赖原有的 document_annotator.py；用于快速接入中文摘要/关键词/表格/公式批注功能。
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import os
import shutil
from pathlib import Path
from datetime import datetime
import logging

from docx import Document

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    module: str
    section: str
    messages: List[str]
    locate_method: str
    locate_data: Any
    extra: Optional[Dict[str, Any]] = None


# Locator registry
LOCATORS: Dict[str, Callable[[Document, Any, Optional[Dict[str, Any]]], Optional[int]]] = {}

def register_locator(name: str):
    def dec(fn: Callable[[Document, Any, Optional[Dict[str, Any]]], Optional[int]]):
        LOCATORS[name] = fn
        return fn
    return dec


@register_locator('index')
def locate_by_index(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    try:
        idx = int(data)
        if 0 <= idx < len(doc.paragraphs):
            return idx
    except Exception:
        return None
    return None


@register_locator('keyword')
def locate_by_keyword(doc: Document, keyword: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    if not keyword:
        return None
    kw = str(keyword).lower()
    for i, p in enumerate(doc.paragraphs):
        if p.text and kw in p.text.lower():
            return i
    return None


@register_locator('abstract_title')
def locate_abstract_title(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    # find paragraph whose text contains 摘要 or 摘 要 (Chinese)
    for i, p in enumerate(doc.paragraphs):
        txt = (p.text or '').strip()
        if '摘要' in txt:
            return i
    return None


@register_locator('abstract_content')
def locate_abstract_content(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    # find first non-empty paragraph after abstract title
    title_idx = locate_abstract_title(doc, data, extra)
    if title_idx is None:
        return None
    for j in range(title_idx + 1, min(title_idx + 6, len(doc.paragraphs))):
        if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
            return j
    return None


@register_locator('english_abstract_title')
def locate_english_abstract_title(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    # find paragraph whose text contains 'abstract' (English)
    for i, p in enumerate(doc.paragraphs):
        txt = (p.text or '').strip().lower()
        if 'abstract' in txt:
            return i
    return None


@register_locator('english_abstract_content')
def locate_english_abstract_content(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    title_idx = locate_english_abstract_title(doc, data, extra)
    if title_idx is None:
        return None
    for j in range(title_idx + 1, min(title_idx + 6, len(doc.paragraphs))):
        if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
            return j
    return None


@register_locator('keywords_title')
def locate_keywords_title(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    for i, p in enumerate(doc.paragraphs):
        txt = (p.text or '').strip()
        if '关键词' in txt:
            return i
    return None


@register_locator('keywords_content')
def locate_keywords_content(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    kidx = locate_keywords_title(doc, data, extra)
    if kidx is None:
        return None
    # often keywords are same paragraph as title; if not, find next non-empty
    para = doc.paragraphs[kidx]
    # if title paragraph contains keywords content (like "关键词: ..."), return that paragraph
    if ':' in (para.text or '') or '：' in (para.text or ''):
        return kidx
    for j in range(kidx + 1, min(kidx + 4, len(doc.paragraphs))):
        if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
            return j
    return None


@register_locator('english_keywords_title')
def locate_english_keywords_title(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    # look for common English keywords header
    for i, p in enumerate(doc.paragraphs):
        txt = (p.text or '').strip().lower()
        if 'keywords' in txt or 'key words' in txt or 'key-words' in txt:
            return i
    return None


@register_locator('english_keywords_content')
def locate_english_keywords_content(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    kidx = locate_english_keywords_title(doc, data, extra)
    if kidx is None:
        return None
    para = doc.paragraphs[kidx]
    if ':' in (para.text or '') or '：' in (para.text or ''):
        return kidx
    for j in range(kidx + 1, min(kidx + 4, len(doc.paragraphs))):
        if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
            return j
    return None


@register_locator('content_paragraph')
def locate_content_paragraph(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    # data expected 1-based paragraph number relative to content (as used in some reports)
    try:
        para_no = int(data)
    except Exception:
        return None
    # heuristic: find "Introduction" or first main section, then count paragraph_no after that
    intro_idx = None
    for i, p in enumerate(doc.paragraphs):
        if 'Introduction' in (p.text or '') or '引言' in (p.text or ''):
            intro_idx = i
            break
    if intro_idx is None:
        # fallback: use absolute para index (consider para_no is 0-based)
        if 0 <= para_no - 1 < len(doc.paragraphs):
            return para_no - 1
        return None
    # count valid content paragraphs after intro
    count = 0
    for j in range(intro_idx + 1, len(doc.paragraphs)):
        text = (doc.paragraphs[j].text or '').strip()
        if not text or len(text) < 10:
            continue
        count += 1
        if count == para_no:
            return j
    return None


@register_locator('table_caption_cn')
def locate_table_caption_cn(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """定位中文表题段落"""
    if isinstance(data, dict):
        idx = data.get('paragraph_index')
        if isinstance(idx, int) and 0 <= idx < len(doc.paragraphs):
            return idx
        # 尝试从 captions.cn 获取
        cn = data.get('captions', {}).get('cn', {})
        idx = cn.get('paragraph_index')
        if isinstance(idx, int) and 0 <= idx < len(doc.paragraphs):
            return idx
    return None


@register_locator('table_caption_en')
def locate_table_caption_en(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """定位英文表题段落"""
    if isinstance(data, dict):
        idx = data.get('paragraph_index')
        if isinstance(idx, int) and 0 <= idx < len(doc.paragraphs):
            return idx
        # 尝试从 captions.en 获取
        en = data.get('captions', {}).get('en', {})
        idx = en.get('paragraph_index')
        if isinstance(idx, int) and 0 <= idx < len(doc.paragraphs):
            return idx
    return None


@register_locator('formula_paragraph')
def locate_formula_paragraph(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """定位公式段落"""
    if isinstance(data, dict):
        idx = data.get('paragraph_index')
        if isinstance(idx, int) and 0 <= idx < len(doc.paragraphs):
            return idx
    elif isinstance(data, int):
        if 0 <= data < len(doc.paragraphs):
            return data
    return None


@register_locator('formula_with_fallback')
def locate_formula_with_fallback(doc: Document, data: Any, extra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """
    定位公式段落，优先级顺序：
    1. extra['paragraph_index'] — 公式内容段落索引（同行场景，优先）
    2. extra['number_w_p_index'] — 编号所在段落索引（跨段落场景）

    原则：直接使用公式内容段落，即使段落文本为空（公式内容为 Math 对象时文本为空是正常现象），
    不做向前搜索以避免跑到旁边的描述段落。
    """
    formula_para_idx = None
    if isinstance(extra, dict):
        formula_para_idx = extra.get('paragraph_index')
        if not isinstance(formula_para_idx, int):
            formula_para_idx = extra.get('number_w_p_index')
    if not isinstance(formula_para_idx, int):
        formula_para_idx = data

    if not isinstance(formula_para_idx, int):
        return None

    if not (0 <= formula_para_idx < len(doc.paragraphs)):
        return None

    # 直接返回公式内容段落（Math 对象在此段落内）
    # 不搜索邻居段落，避免跑到公式旁边的描述段落
    logger.info(f"locate_formula_with_fallback: using para {formula_para_idx}, text='{(doc.paragraphs[formula_para_idx].text or '')[:40]}'")
    return formula_para_idx


class Commenter:
    """一次打开 doc、按 paragraph index 添加注释并保存"""
    def __init__(self, copy_path: str):
        self.copy_path = copy_path
        self.doc = Document(copy_path)
        self.count = 0

    def add_comment_to_para_idx(self, idx: int, text: str, author: str = "论文检测系统", initials: str = "PDS") -> bool:
        if not (0 <= idx < len(self.doc.paragraphs)):
            return False
        para = self.doc.paragraphs[idx]
        if not para.runs:
            para.add_run("")
        runs = para.runs if len(para.runs) > 1 else para.runs[0]
        try:
            self.doc.add_comment(runs=runs, text=text, author=author, initials=initials)
            self.count += 1
            return True
        except Exception:
            # fallback to single run
            try:
                self.doc.add_comment(runs=para.runs[0], text=text, author=author, initials=initials)
                self.count += 1
                return True
            except Exception as e:
                logger.warning(f"add_comment failed for para {idx}: {e}")
                return False

    def add_comment_to_math_run(self, para_idx: int, math_elem, text: str, author: str = "论文检测系统", initials: str = "PDS") -> bool:
        """
        将批注锚定到包含 Math 对象的段落中的第一个 Run（公式本体），
        而不是整个段落。

        math_elem 参数来自原始文档的检测结果，在副本中需要通过段落索引重新查找 Math 元素。
        """
        if not (0 <= para_idx < len(self.doc.paragraphs)):
            return False
        para = self.doc.paragraphs[para_idx]

        run_to_anchor = None
        try:
            from lxml import etree
            para_xml = para._element
            # 在段落 XML 中查找 w:oMath 元素（MathML/OMML 公式对象）
            math_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
            w_ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            omath_elems = para_xml.xpath(
                f'.//*[local-name()="oMath" and namespace-uri()="{math_ns}"]',
            )
            if not omath_elems:
                # 也尝试不带命名空间的写法
                omath_elems = para_xml.xpath('.//*[local-name()="oMath"]')
            if omath_elems:
                math_lxml = omath_elems[0]
                # 在段落中找到第一个 run，其祖先链包含 oMath 元素
                for run in para.runs:
                    run_lxml = run._element
                    for ancestor in run_lxml.iterancestors():
                        if ancestor is math_lxml:
                            run_to_anchor = run
                            break
                    if run_to_anchor:
                        break
        except Exception as e:
            logger.warning(f"Failed to find math run in para {para_idx}: {e}")

        if run_to_anchor is None:
            return self.add_comment_to_para_idx(para_idx, text, author, initials)

        try:
            self.doc.add_comment(runs=run_to_anchor, text=text, author=author, initials=initials)
            self.count += 1
            logger.info(f"Comment anchored to math run at para {para_idx}")
            return True
        except Exception as e:
            logger.warning(f"add_comment to math run failed: {e}, falling back to para method")
            return self.add_comment_to_para_idx(para_idx, text, author, initials)

    def save(self, path: Optional[str] = None):
        out = path or self.copy_path
        self.doc.save(out)


def create_copy(original_path: str, output_dir: str) -> Optional[str]:
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = Path(original_path).stem
        copy_name = f"{timestamp}_{base_name}_annotated.docx"
        os.makedirs(output_dir, exist_ok=True)
        copy_path = os.path.join(output_dir, copy_name)
        shutil.copy(original_path, copy_path)
        return copy_path
    except Exception as e:
        logger.error(f"create_copy failed: {e}")
        return None


# ----------------- Adapters (report -> List[Issue]) -----------------
def abstract_adapter(all_reports: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    # support chinese and english abstract keys
    def _collect_msgs(rep_part):
        msgs_local: List[str] = []
        if not rep_part:
            return msgs_local
        if isinstance(rep_part, dict):
            msgs_local.extend(rep_part.get('messages', []))
            msgs_local.extend((rep_part.get('format') or {}).get('messages', []))
            msgs_local.extend((rep_part.get('structure') or {}).get('messages', []))
        else:
            if isinstance(rep_part, list):
                msgs_local.extend(rep_part)
            elif isinstance(rep_part, str):
                msgs_local.append(rep_part)
        return msgs_local

    # chinese abstract - iterate subsections and annotate failing subsections
    crep = all_reports.get('chinese_abstract_format') or all_reports.get('chinese_abstract')
    if isinstance(crep, dict):
        for section_key, section_val in crep.items():
            if section_key in ['summary', 'extracted', 'details']:
                continue
            if isinstance(section_val, dict) and section_val.get('ok') is False:
                msgs = []
                msgs.extend(section_val.get('messages', []))
                # include nested format/structure messages if present
                if isinstance(section_val.get('format'), dict):
                    msgs.extend(section_val['format'].get('messages', []))
                if isinstance(section_val.get('structure'), dict):
                    msgs.extend(section_val['structure'].get('messages', []))
                if not msgs:
                    continue
                # prefer explicit paragraph_index if provided by detector (section-level or container-level)
                para_idx = None
                if isinstance(section_val, dict):
                    # prefer content paragraph indices for content-related subsections
                    if isinstance(section_key, str) and 'content' in section_key.lower():
                        # try to map "第N段" in messages to specific content paragraph index first;
                        # if not found, fall back to first content index, then other indices
                        para_idx = None
                        try:
                            import re
                            if isinstance(section_val.get('messages'), list):
                                for m in section_val.get('messages', []):
                                    match = re.search(r'第\s*(\d+)\s*段', str(m))
                                    if match:
                                        n = int(match.group(1))
                                        cidxs = section_val.get('content_paragraphs_indices') or section_val.get('content_paragraph_indexes') or []
                                        if isinstance(cidxs, list) and len(cidxs) >= n:
                                            para_idx = cidxs[n-1]
                                            break
                        except Exception:
                            para_idx = None
                        if para_idx is None:
                            para_idx = (section_val.get('content_paragraphs_indices') or section_val.get('content_paragraph_indexes') or [None])[0] \
                                or section_val.get('paragraph_index') \
                                or section_val.get('title_paragraph_index')
                else:
                    para_idx = section_val.get('paragraph_index') \
                        or section_val.get('title_paragraph_index') \
                        or (section_val.get('content_paragraphs_indices')[0] if isinstance(section_val.get('content_paragraphs_indices'), list) and section_val.get('content_paragraphs_indices') else None)
                # If this is a content-format issue, try to map "第N段" messages to the corresponding content paragraph index
                if para_idx is None and isinstance(section_val, dict):
                    try:
                        import re
                        # look for "第<number>段" in messages
                        if isinstance(section_val.get('messages'), list):
                            for m in section_val.get('messages', []):
                                match = re.search(r'第\s*(\d+)\s*段', str(m))
                                if match:
                                    n = int(match.group(1))
                                    container_indices = erep.get('content_paragraphs_indices') if isinstance(erep, dict) else None
                                    if isinstance(container_indices, list) and len(container_indices) >= n:
                                        para_idx = container_indices[n-1]
                                        break
                    except Exception:
                        pass
                # fallback to container-level indices (crep)
                if para_idx is None and isinstance(crep, dict):
                    # prefer container-level content indices when subsection is content-related
                    if isinstance(section_key, str) and 'content' in section_key.lower():
                        para_idx = (crep.get('content_paragraphs_indices') or crep.get('content_paragraph_indexes') or [None])[0] \
                            or crep.get('paragraph_index') \
                            or crep.get('title_paragraph_index') \
                            or (crep.get('structure') or {}).get('title_paragraph_index')
                    else:
                        para_idx = crep.get('title_paragraph_index') \
                            or (crep.get('content_paragraphs_indices')[0] if isinstance(crep.get('content_paragraphs_indices'), list) and crep.get('content_paragraphs_indices') else None) \
                            or (crep.get('structure') or {}).get('title_paragraph_index') \
                            or ((crep.get('structure') or {}).get('content_paragraphs_indices') or [None])[0]
                if para_idx is not None:
                    issues.append(Issue(
                        module='Abstract',
                        section=f"chinese_{section_key}",
                        messages=msgs,
                        locate_method='index',
                        locate_data=para_idx
                    ))
                else:
                    locate_method = 'abstract_content' if section_key != 'structure' else 'abstract_title'
                    issues.append(Issue(
                        module='Abstract',
                        section=f"chinese_{section_key}",
                        messages=msgs,
                        locate_method=locate_method,
                        locate_data='Abstract'
                    ))
    else:
        if crep is not None:
            logger.info("abstract_adapter: non-dict chinese abstract report ignored for annotations")

    # english abstract - iterate subsections and annotate failing subsections
    erep = all_reports.get('English_Abstract') or all_reports.get('Abstract') or all_reports.get('english_abstract')
    if isinstance(erep, dict):
        for section_key, section_val in erep.items():
            if section_key in ['summary', 'extracted', 'details']:
                continue
            if isinstance(section_val, dict) and section_val.get('ok') is False:
                msgs = []
                msgs.extend(section_val.get('messages', []))
                if isinstance(section_val.get('format'), dict):
                    msgs.extend(section_val['format'].get('messages', []))
                if isinstance(section_val.get('structure'), dict):
                    msgs.extend(section_val['structure'].get('messages', []))
                if not msgs:
                    continue
                para_idx = None
                if isinstance(section_val, dict):
                    # Prefer mapping content-related issues to content paragraph indices,
                    # using explicit "第N段" mentions in messages when present.
                    if isinstance(section_key, str) and 'content' in section_key.lower():
                        try:
                            import re
                            if isinstance(section_val.get('messages'), list):
                                for m in section_val.get('messages', []):
                                    match = re.search(r'第\s*(\d+)\s*段', str(m))
                                    if match:
                                        n = int(match.group(1))
                                        # prefer section-level indices, then container-level
                                        cidxs = section_val.get('content_paragraphs_indices') or section_val.get('content_paragraph_indexes') or erep.get('content_paragraphs_indices') or []
                                        if isinstance(cidxs, list) and len(cidxs) >= n:
                                            para_idx = cidxs[n-1]
                                            break
                        except Exception:
                            para_idx = None
                        if para_idx is None:
                            # fallback order: section content indices, container content indices, paragraph_index, title_paragraph_index
                            para_idx = (section_val.get('content_paragraphs_indices') or section_val.get('content_paragraph_indexes') or (erep.get('content_paragraphs_indices') if isinstance(erep, dict) else [] ) or [None])[0] \
                                or section_val.get('paragraph_index') \
                                or section_val.get('title_paragraph_index')
                    else:
                        para_idx = section_val.get('paragraph_index') \
                            or section_val.get('title_paragraph_index') \
                            or (section_val.get('content_paragraphs_indices')[0] if isinstance(section_val.get('content_paragraphs_indices'), list) and section_val.get('content_paragraphs_indices') else None)
                if para_idx is None and isinstance(erep, dict):
                    # prefer container-level content indices when subsection is content-related
                    if isinstance(section_key, str) and 'content' in section_key.lower():
                        para_idx = (erep.get('content_paragraphs_indices') or erep.get('content_paragraph_indexes') or [None])[0] \
                            or erep.get('paragraph_index') \
                            or erep.get('title_paragraph_index') \
                            or (erep.get('structure') or {}).get('title_paragraph_index')
                    else:
                        para_idx = erep.get('title_paragraph_index') \
                            or (erep.get('content_paragraphs_indices')[0] if isinstance(erep.get('content_paragraphs_indices'), list) and erep.get('content_paragraphs_indices') else None) \
                            or (erep.get('structure') or {}).get('title_paragraph_index') \
                            or ((erep.get('structure') or {}).get('content_paragraphs_indices') or [None])[0]
                if para_idx is not None:
                    issues.append(Issue(
                        module='Abstract',
                        section=f"english_{section_key}",
                        messages=msgs,
                        locate_method='index',
                        locate_data=para_idx
                    ))
                else:
                    locate_method = 'english_abstract_content' if section_key != 'structure' else 'english_abstract_title'
                    issues.append(Issue(
                        module='Abstract',
                        section=f"english_{section_key}",
                        messages=msgs,
                        locate_method=locate_method,
                        locate_data='ABSTRACT'
                    ))
    else:
        if erep is not None:
            logger.info("abstract_adapter: non-dict english abstract report ignored for annotations")
    return issues


def keywords_adapter(all_reports: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    # Support both bilingual structure: all_reports['Keywords'] may contain 'chinese' and 'english'
    # or separate keys like 'chinese_keywords_format' and 'English_Keywords'
    # Collect chinese part
    def _collect_msgs_from(rep_part):
        msgs_local: List[str] = []
        if not rep_part:
            return msgs_local
        if isinstance(rep_part, dict):
            struct = rep_part.get('structure') or {}
            fmt = rep_part.get('format') or {}
            # structure may contain messages list
            msgs_local.extend(struct.get('messages', []))
            msgs_local.extend(fmt.get('messages', []))
            # also top-level messages
            msgs_local.extend(rep_part.get('messages', []))
        else:
            if isinstance(rep_part, list):
                msgs_local.extend(rep_part)
            elif isinstance(rep_part, str):
                msgs_local.append(rep_part)
        return msgs_local

    # Chinese messages
    chinese_rep = None
    # Check common places
    if 'chinese_keywords_format' in all_reports:
        chinese_rep = all_reports.get('chinese_keywords_format')
    elif 'Keywords' in all_reports and isinstance(all_reports['Keywords'], dict) and 'chinese' in all_reports['Keywords']:
        chinese_rep = all_reports['Keywords'].get('chinese')
    elif 'chinese_keywords' in all_reports:
        chinese_rep = all_reports.get('chinese_keywords')

    # chinese keywords - iterate subsections
    if isinstance(chinese_rep, dict):
        for section_key, section_val in chinese_rep.items():
            if section_key in ['summary', 'extracted', 'details']:
                continue
            if isinstance(section_val, dict) and section_val.get('ok') is False:
                msgs = []
                msgs.extend(section_val.get('messages', []))
                if isinstance(section_val.get('format'), dict):
                    msgs.extend(section_val['format'].get('messages', []))
                if isinstance(section_val.get('structure'), dict):
                    msgs.extend(section_val['structure'].get('messages', []))
                if not msgs:
                    continue
                # prefer explicit paragraph index
                para_idx = None
                if isinstance(section_val, dict):
                    para_idx = section_val.get('paragraph_index') or section_val.get('keywords_paragraph_index')
                if para_idx is None and isinstance(chinese_rep, dict):
                    para_idx = chinese_rep.get('keywords_paragraph_index') or (chinese_rep.get('structure') or {}).get('keywords_paragraph_index')

                if para_idx is not None:
                    issues.append(Issue(
                        module='Keywords',
                        section=f"chinese_{section_key}",
                        messages=msgs,
                        locate_method='index',
                        locate_data=para_idx
                    ))
                else:
                    locate_method = 'keywords_title' if section_key == 'structure' else 'keywords_content'
                    issues.append(Issue(
                        module='Keywords',
                        section=f"chinese_{section_key}",
                        messages=msgs,
                        locate_method=locate_method,
                        locate_data='Keywords'
                    ))
    else:
        if chinese_rep is not None:
            logger.info("keywords_adapter: non-dict chinese keywords report ignored for annotations")

    # English messages
    english_rep = None
    if 'English_Keywords' in all_reports:
        english_rep = all_reports.get('English_Keywords')
    elif 'Keywords' in all_reports and isinstance(all_reports['Keywords'], dict) and 'english' in all_reports['Keywords']:
        english_rep = all_reports['Keywords'].get('english')
    elif 'english_keywords' in all_reports:
        english_rep = all_reports.get('english_keywords')

    # english keywords - iterate subsections
    if isinstance(english_rep, dict):
        for section_key, section_val in english_rep.items():
            if section_key in ['summary', 'extracted', 'details']:
                continue
            if isinstance(section_val, dict) and section_val.get('ok') is False:
                msgs = []
                msgs.extend(section_val.get('messages', []))
                if isinstance(section_val.get('format'), dict):
                    msgs.extend(section_val['format'].get('messages', []))
                if isinstance(section_val.get('structure'), dict):
                    msgs.extend(section_val['structure'].get('messages', []))
                if not msgs:
                    continue
                para_idx = None
                if isinstance(section_val, dict):
                    para_idx = section_val.get('paragraph_index') or section_val.get('keywords_paragraph_index')
                if para_idx is None and isinstance(english_rep, dict):
                    para_idx = english_rep.get('keywords_paragraph_index') or (english_rep.get('structure') or {}).get('keywords_paragraph_index')

                if para_idx is not None:
                    issues.append(Issue(
                        module='Keywords',
                        section=f"english_{section_key}",
                        messages=msgs,
                        locate_method='index',
                        locate_data=para_idx
                    ))
                else:
                    locate_method = 'english_keywords_title' if section_key == 'structure' else 'english_keywords_content'
                    issues.append(Issue(
                        module='Keywords',
                        section=f"english_{section_key}",
                        messages=msgs,
                        locate_method=locate_method,
                        locate_data='KEYWORDS'
                    ))
    else:
        if english_rep is not None:
            logger.info("keywords_adapter: non-dict english keywords report ignored for annotations")
    return issues


def table_adapter(all_reports: Dict[str, Any]) -> List[Issue]:
    """表格检测结果适配器"""
    issues: List[Issue] = []

    table_report = all_reports.get('Table')
    if not isinstance(table_report, dict):
        logger.info("table_adapter: Table report is not a dict or missing")
        return issues

    logger.info(f"table_adapter: found Table report with {len(table_report.get('tables', []))} tables")

    tables = table_report.get('tables', [])
    if not isinstance(tables, list):
        tables = []

    # 首先处理编号连续性问题（全局，只添加一次）
    numbering = table_report.get('numbering', {})
    if isinstance(numbering, dict) and numbering.get('ok') is False:
        for msg in numbering.get('messages', []):
            issues.append(Issue(
                module='Table',
                section='编号连续性',
                messages=[f"[编号问题] {msg}"],
                locate_method='keyword',
                locate_data='表'
            ))

    # 用于去重：记录已处理过的 (table_desc, para_idx) 组合
    # 优先用 cn_idx，fallback 到 en_idx，再 fallback 到 table_body_index
    processed_table_keys = set()

    # 遍历每个表格
    for idx, table_item in enumerate(tables):
        if not isinstance(table_item, dict):
            continue

        table_desc = table_item.get('table_desc', f"表格")
        captions = table_item.get('captions', {})
        cn_caption = captions.get('cn', {})
        en_caption = captions.get('en', {})

        # 获取段落索引：优先 cn，再 en，最后 table_body_index
        cn_idx = cn_caption.get('paragraph_index') if isinstance(cn_caption, dict) else None
        en_idx = en_caption.get('paragraph_index') if isinstance(en_caption, dict) else None
        body_idx = table_item.get('table_body_index')

        para_idx = cn_idx if cn_idx is not None else (en_idx if en_idx is not None else body_idx)

        logger.info(f"table_adapter: processing table {idx}: {table_desc}, cn_idx={cn_idx}, en_idx={en_idx}, body_idx={body_idx}")

        # 去重键：table_desc + 实际使用的段落索引（三个都 None 时才只用 table_desc）
        dedup_key = (table_desc, para_idx)
        if para_idx is None:
            dedup_key = table_desc  # 所有索引都是 None 时，只用描述去重
        if dedup_key in processed_table_keys:
            logger.info(f"table_adapter: skipping duplicate table {table_desc} at para_idx={para_idx}")
            continue
        processed_table_keys.add(dedup_key)

        # 获取各类问题的消息列表（不再合并到一个 Issue）
        text_rules = table_item.get('text_rules', {})
        cn_format = table_item.get('caption_cn_format', {})
        en_format = table_item.get('caption_en_format', {})
        table_style = table_item.get('table_style', {})
        content_align = table_item.get('table_content_alignment', {})
        table_ref = table_item.get('table_reference', {})

        def collect_messages(report_dict):
            if isinstance(report_dict, dict) and report_dict.get('ok') is False:
                return report_dict.get('messages', [])
            return []

        text_msgs = collect_messages(text_rules)  # 文本规则消息本身已包含上下文，不加前缀
        cn_msgs = [f"[中文表题] {m}" for m in collect_messages(cn_format)]
        en_msgs = [f"[英文表题] {m}" for m in collect_messages(en_format)]
        style_msgs = [f"[表格样式] {m}" for m in collect_messages(table_style)]
        align_msgs = [f"[内容对齐] {m}" for m in collect_messages(content_align)]
        ref_msgs = [f"[表格引用] {m}" for m in collect_messages(table_ref)]

        # 如果段落索引无效，尝试用关键词定位
        locate_method = 'index'
        locate_data = para_idx
        if not isinstance(para_idx, int) or not (0 <= para_idx < 100000):
            locate_method = 'keyword'
            locate_data = table_desc[:30] if table_desc else '表'

        # 收集所有问题的消息，分类标签作为前缀
        all_issue_messages = []
        for bucket_name, bucket_msgs in [
            ('caption_cn', cn_msgs),
            ('caption_en', en_msgs),
            ('style', style_msgs),
            ('alignment', align_msgs),
            ('reference', ref_msgs),
        ]:
            for m in bucket_msgs:
                all_issue_messages.append(m)

        # text_rules 消息不带分类前缀（消息本身已有上下文）
        for m in collect_messages(text_rules):
            all_issue_messages.append(m)

        if all_issue_messages:
            issues.append(Issue(
                module='Table',
                section=table_desc,
                messages=all_issue_messages,
                locate_method=locate_method,
                locate_data=locate_data
            ))
            logger.info(f"table_adapter: added issue for {table_desc} at {locate_data} with msgs: {all_issue_messages}")

    logger.info(f"table_adapter: total issues generated = {len(issues)}")
    return issues


def formula_adapter(all_reports: Dict[str, Any]) -> List[Issue]:
    """公式检测结果适配器"""
    issues: List[Issue] = []
    
    formula_report = all_reports.get('Formula')
    if not isinstance(formula_report, dict):
        logger.info("formula_adapter: Formula report is not a dict or missing")
        return issues
    
    # 输出完整报告结构用于调试
    logger.info(f"formula_adapter: formula_report type={type(formula_report)}, keys={formula_report.keys()}")
    logger.info(f"formula_adapter: formula_report={formula_report}")
    
    # 尝试从 formula_detection 获取公式段落列表（公式报告结构可能是 {formula_detection: {...}, numbering: {...}}）
    formula_paragraphs = []
    formula_detection = formula_report.get('formula_detection')
    
    logger.info(f"formula_adapter: formula_detection type={type(formula_detection)}, value={formula_detection}")
    
    if isinstance(formula_detection, dict):
        # 方式1: formula_detection 包含 details
        if 'details' in formula_detection:
            details = formula_detection['details']
            logger.info(f"formula_adapter: found details in formula_detection: {details}")
            if isinstance(details, dict) and 'formula_paragraphs' in details:
                formula_paragraphs = details['formula_paragraphs']
                logger.info(f"formula_adapter: found {len(formula_paragraphs)} formula paragraphs in formula_detection.details")
        
        # 方式2: formula_detection 直接包含 formula_paragraphs
        if not formula_paragraphs and 'formula_paragraphs' in formula_detection:
            formula_paragraphs = formula_detection['formula_paragraphs']
            logger.info(f"formula_adapter: found {len(formula_paragraphs)} formula paragraphs in formula_detection directly")
    
    # 备选：从顶层获取（正确的位置是 report['details']['formula_paragraphs']）
    if not formula_paragraphs:
        logger.info(f"formula_adapter: checking top-level formula_report, keys={list(formula_report.keys())}")
        if 'details' in formula_report:
            details = formula_report['details']
            logger.info(f"formula_adapter: found details at top-level: {details}")
            if isinstance(details, dict) and 'formula_paragraphs' in details:
                formula_paragraphs = details['formula_paragraphs']
                logger.info(f"formula_adapter: found {len(formula_paragraphs)} formula paragraphs in formula_report.details")
        if not formula_paragraphs and 'formula_paragraphs' in formula_report:
            formula_paragraphs = formula_report['formula_paragraphs']
            logger.info(f"formula_adapter: found {len(formula_paragraphs)} formula paragraphs in formula_report directly")
    
    if not isinstance(formula_paragraphs, list):
        formula_paragraphs = []
    
    logger.info(f"formula_adapter: total formula_paragraphs found = {len(formula_paragraphs)}")
    
    # 遍历每个公式段落
    for para_item in formula_paragraphs:
        if not isinstance(para_item, dict):
            continue

        format_check = para_item.get('format_check', {})
        if not isinstance(format_check, dict):
            continue

        formula_label = para_item.get('formula_label', '公式')

        # 检测是否为文本框公式（检测器跳过了格式检查）
        skipped_msgs = format_check.get('messages', [])
        is_textbox = any('文本框' in m or '跳过' in m or 'skipped' in str(m).lower() for m in skipped_msgs)

        # 只处理有问题的公式（文本框公式如果检测器跳过了检查，不视为"问题"）
        is_ok = format_check.get('ok', True)
        if is_ok and not (is_textbox and skipped_msgs):
            continue

        all_messages = []

        # 收集所有问题消息
        for msg in format_check.get('messages', []):
            all_messages.append(msg)

        # 引用检查问题
        reference = format_check.get('details', {}).get('reference', {})
        if isinstance(reference, dict) and reference.get('ok') is False:
            for msg in reference.get('messages', []):
                all_messages.append(f"[引用检查] {msg}")

        if not all_messages:
            continue

        # 获取段落索引（优先 number_w_p_index，即编号所在段落）
        raw_para_idx = para_item.get('number_w_p_index')
        if not isinstance(raw_para_idx, int):
            raw_para_idx = para_item.get('paragraph_index')
        if not isinstance(raw_para_idx, int):
            raw_para_idx = para_item.get('index')
        if not isinstance(raw_para_idx, int):
            raw_para_idx = para_item.get('w_p_index')

        logger.info(f"formula_adapter: adding issue for {formula_label} at raw_para_idx={raw_para_idx}, is_textbox={is_textbox}")

        # 去掉消息中已有的公式标签前缀（section 头已包含，避免重复）
        clean_messages = []
        for m in all_messages:
            prefix = f"{formula_label}: "
            if m.startswith(prefix):
                clean_messages.append(m[len(prefix):])
            else:
                clean_messages.append(m)

        if is_textbox:
            # 文本框公式：无法直接定位，用关键词搜索
            import re
            kw_match = re.search(r'公式?[\s#]*(\d+[-\uFF0D]\d+)', formula_label)
            kw = f"公式{kw_match.group(1)}" if kw_match else '公式'
            issues.append(Issue(
                module='Formula',
                section=formula_label,
                messages=clean_messages,
                locate_method='keyword',
                locate_data=kw
            ))
        elif isinstance(raw_para_idx, int) and 0 <= raw_para_idx < 100000:
            # 正文公式：传入原始索引和文本框标记，由 locator 做验证
            math_elem = para_item.get('target_math_elem')
            issues.append(Issue(
                module='Formula',
                section=formula_label,
                messages=clean_messages,
                locate_method='formula_with_fallback',
                locate_data=raw_para_idx,
                extra={
                    'is_textbox': False,
                    'formula_label': formula_label,
                    'target_math_elem': math_elem,
                    'paragraph_index': para_item.get('paragraph_index'),
                    'number_w_p_index': para_item.get('number_w_p_index'),
                }
            ))
        else:
            # 索引无效，用关键词
            import re
            kw_match = re.search(r'公式?[\s#]*(\d+[-\uFF0D]\d+)', formula_label)
            kw = f"公式{kw_match.group(1)}" if kw_match else '公式'
            issues.append(Issue(
                module='Formula',
                section=formula_label,
                messages=clean_messages,
                locate_method='keyword',
                locate_data=kw
            ))
    
    # 处理编号连续性问题（按章节分别定位）
    numbering = formula_report.get('numbering', {})
    if isinstance(numbering, dict) and numbering.get('ok') is False:
        import re
        # 获取所有公式段落及其章节信息
        all_formula_paragraphs = []
        for para_item in formula_paragraphs:
            para_idx = para_item.get('paragraph_index')
            if para_idx is None:
                para_idx = para_item.get('index')
            if para_idx is None:
                para_idx = para_item.get('w_p_index')
            if para_idx is not None:
                all_formula_paragraphs.append({
                    'para_idx': para_idx,
                    'label': para_item.get('formula_label', '')
                })
        
        # 按章节号排序公式段落
        def get_chapter_from_label(label):
            # 从 label 如 "公式(2-1)" 提取章节号 2
            match = re.search(r'\((\d+)-', label)
            return int(match.group(1)) if match else 0
        
        all_formula_paragraphs.sort(key=lambda x: get_chapter_from_label(x['label']))
        
        # 记录每个章节的第一个公式段落索引
        chapter_first_para = {}
        for fp in all_formula_paragraphs:
            ch = get_chapter_from_label(fp['label'])
            if ch not in chapter_first_para:
                chapter_first_para[ch] = fp['para_idx']
        
        # 处理每个连续性问题的消息（去重，避免重复添加）
        processed_numbering_issues = set()
        for msg in numbering.get('messages', []):
            # 提取章节号
            ch_match = re.search(r'第(\d+)章', msg)
            if ch_match:
                ch = int(ch_match.group(1))
                # 去重键：章节号
                dedup_key = f"ch_{ch}"
                if dedup_key in processed_numbering_issues:
                    logger.info(f"formula_adapter: skipping duplicate numbering issue for chapter {ch}")
                    continue
                processed_numbering_issues.add(dedup_key)
                
                para_idx = chapter_first_para.get(ch)
                if para_idx is not None:
                    issues.append(Issue(
                        module='Formula',
                        section=f'第{ch}章编号连续性',
                        messages=[f"[编号问题] {msg}"],
                        locate_method='index',
                        locate_data=para_idx
                    ))
                else:
                    # 没找到对应章节的公式，尝试用关键词定位
                    issues.append(Issue(
                        module='Formula',
                        section=f'第{ch}章编号连续性',
                        messages=[f"[编号问题] {msg}"],
                        locate_method='keyword',
                        locate_data='公式'
                    ))
            else:
                # 无法提取章节号，默认用关键词（去重）
                dedup_key = "no_chapter"
                if dedup_key in processed_numbering_issues:
                    logger.info(f"formula_adapter: skipping duplicate numbering issue without chapter")
                    continue
                processed_numbering_issues.add(dedup_key)
                
                issues.append(Issue(
                    module='Formula',
                    section='编号连续性',
                    messages=[f"[编号问题] {msg}"],
                    locate_method='keyword',
                    locate_data='公式'
                ))
    
    logger.info(f"formula_adapter: total issues generated = {len(issues)}")
    return issues


def references_adapter(all_reports: Dict[str, Any]) -> List[Issue]:
    """参考文献检测结果适配器"""
    issues: List[Issue] = []
    
    references_report = all_reports.get('References')
    if not isinstance(references_report, dict):
        logger.info("references_adapter: References report is not a dict or missing")
        return issues
    
    logger.info(f"references_adapter: found References report")
    
    # 获取结构报告（包含段落索引信息）
    structure_report = references_report.get('structure', {})
    header_idx = structure_report.get('header_paragraph_index')
    content_paragraphs = structure_report.get('content_paragraphs', [])
    content_paragraph_indices = structure_report.get('content_paragraph_indices', [])
    reference_numbers = structure_report.get('reference_numbers', [])
    
    # 获取格式报告
    header_format = references_report.get('header_format', {})
    content_format = references_report.get('content_format', {})
    
    # 1. 处理标题格式问题
    if isinstance(header_format, dict) and header_format.get('ok') is False:
        for msg in header_format.get('messages', []):
            if header_idx is not None:
                issues.append(Issue(
                    module='References',
                    section='标题格式',
                    messages=[msg],
                    locate_method='index',
                    locate_data=header_idx
                ))
            else:
                # 尝试通过关键词定位
                issues.append(Issue(
                    module='References',
                    section='标题格式',
                    messages=[msg],
                    locate_method='keyword',
                    locate_data='参考文献'
                ))
    
    # 2. 处理内容格式问题（精确定位到具体条目）
    if isinstance(content_format, dict) and content_format.get('ok') is False:
        content_messages = content_format.get('messages', [])
        
        if content_messages and content_paragraph_indices:
            import re
            
            # 用于记录已添加问题的段落索引，避免重复
            processed_indices = set()
            
            for msg in content_messages:
                # 匹配 "第X条" 来确定具体条目
                match = re.search(r'第\s*(\d+)\s*条', msg)
                if match:
                    ref_idx = int(match.group(1)) - 1  # 转为0-based
                    if 0 <= ref_idx < len(content_paragraph_indices):
                        para_idx = content_paragraph_indices[ref_idx]
                        
                        # 避免同一段落重复添加问题
                        if para_idx not in processed_indices:
                            issues.append(Issue(
                                module='References',
                                section=f'第{ref_idx + 1}条参考文献',
                                messages=[msg],
                                locate_method='index',
                                locate_data=para_idx
                            ))
                            processed_indices.add(para_idx)
                        else:
                            # 如果段落已添加过问题，只追加消息
                            # 找到已存在的 issue 并追加消息
                            for issue in issues:
                                if issue.locate_data == para_idx:
                                    issue.messages.append(msg)
                                    break
                    continue
                
                # 如果没有匹配到"第X条"，添加到标题
                if header_idx is not None and header_idx not in processed_indices:
                    issues.append(Issue(
                        module='References',
                        section='内容格式',
                        messages=[msg],
                        locate_method='index',
                        locate_data=header_idx
                    ))
                    processed_indices.add(header_idx)
    
    # 3. 处理结构问题（序号连续性等）
    structure_messages = structure_report.get('messages', [])
    numbering_issues = [m for m in structure_messages if '序号' in m or '连续' in m]
    
    if numbering_issues:
        if header_idx is not None:
            issues.append(Issue(
                module='References',
                section='序号连续性',
                messages=numbering_issues,
                locate_method='index',
                locate_data=header_idx
            ))
        else:
            issues.append(Issue(
                module='References',
                section='序号连续性',
                messages=numbering_issues,
                locate_method='keyword',
                locate_data='参考文献'
            ))
    
    # 4. 处理引用检测问题（citation）
    citation_report = references_report.get('citation', {})
    if isinstance(citation_report, dict):
        citation_messages = citation_report.get('messages', [])
        
        # 获取未被引用的文献详情
        unreferenced_details = citation_report.get('unreferenced_details', [])
        
        # 如果有未被引用的文献详情，可以精确定位到具体文献条目
        if unreferenced_details and content_paragraph_indices:
            # 判断是否是自动编号
            is_auto_numbered = all(num == -1 or num is None for num in reference_numbers)
            
            for detail in unreferenced_details:
                ref_num = detail.get('number')
                ref_content = detail.get('content', '')[:50]  # 取前50字符
                
                # 找到对应的段落索引
                para_idx = None
                if is_auto_numbered:
                    # 自动编号：序号是虚拟的 1,2,3...
                    ref_idx = ref_num - 1
                    if 0 <= ref_idx < len(content_paragraph_indices):
                        para_idx = content_paragraph_indices[ref_idx]
                else:
                    # 手动编号：查找实际序号的位置
                    try:
                        ref_idx = reference_numbers.index(ref_num)
                        if 0 <= ref_idx < len(content_paragraph_indices):
                            para_idx = content_paragraph_indices[ref_idx]
                    except ValueError:
                        pass
                
                if para_idx is not None:
                    # 精确定位到具体文献条目
                    issues.append(Issue(
                        module='References',
                        section=f'未被引用-[{ref_num}]',
                        messages=[f"[{ref_num}] {ref_content}..."],
                        locate_method='index',
                        locate_data=para_idx
                    ))
                else:
                    # 无法精确定位，添加到标题
                    if header_idx is not None:
                        issues.append(Issue(
                            module='References',
                            section='未被引用',
                            messages=[f"[{ref_num}] {ref_content}..."],
                            locate_method='index',
                            locate_data=header_idx
                        ))
        
        # 处理无效引用
        invalid_citations = citation_report.get('invalid_citations', [])
        if invalid_citations:
            issues.append(Issue(
                module='References',
                section='无效引用',
                messages=[f"正文引用了不存在的序号: {invalid_citations}"],
                locate_method='keyword',
                locate_data='参考文献'
            ))
    
    logger.info(f"references_adapter: total issues generated = {len(issues)}")
    return issues


# Orchestrator
def annotate_chinese_abstract_and_keywords(docx_path: str, all_reports: Dict[str, Any], output_dir: str) -> Optional[str]:
    """
    入口：生成带批注文档，针对中文摘要与关键词
    返回副本路径或 None
    """
    try:
        copy_path = create_copy(docx_path, output_dir)
        if not copy_path:
            logger.error("create_copy failed")
            return None

        # collect issues from adapters
        issues: List[Issue] = []
        issues.extend(abstract_adapter(all_reports))
        issues.extend(keywords_adapter(all_reports))
        issues.extend(table_adapter(all_reports))       # 添加表格适配器
        issues.extend(formula_adapter(all_reports))     # 添加公式适配器
        issues.extend(references_adapter(all_reports)) # 添加参考文献适配器

        if not issues:
            logger.info("No issues from adapters -> nothing to annotate")
            return copy_path

        commenter = Commenter(copy_path)
        doc = commenter.doc  # Document object

        # For efficiency, build a simple lowercase paragraph text cache
        para_texts = [(i, (p.text or "").strip().lower()) for i, p in enumerate(doc.paragraphs)]

        # process issues
        for issue in issues:
            locator = LOCATORS.get(issue.locate_method)
            para_idx = None
            if locator:
                try:
                    para_idx = locator(doc, issue.locate_data, issue.extra)
                except Exception as e:
                    logger.warning(f"locator {issue.locate_method} error: {e}")
            
            # fallback: keyword search across paragraphs
            if para_idx is None and issue.locate_data:
                kw = str(issue.locate_data).lower()

                # Helper: check if a paragraph contains a formula label pattern
                import re as _re
                FORMULA_PAT = _re.compile(
                    r'公式\s*[\(（]?\s*\d+(?:[-\uFF0D]\d+)?\s*[\)）]?'
                    r'|'
                    r'^\s*\(?\s*\d+(?:[-\uFF0D]\d+)?\s*\)?\s*$'
                )

                def para_matches_language(text: str, section_name: str) -> bool:
                    s = (text or "").strip().lower()
                    if 'english' in section_name.lower():
                        if any(c.isalpha() for c in s):
                            return True
                        if 'keywords' in s or 'abstract' in s:
                            return True
                        return False
                    if 'chinese' in section_name.lower():
                        return any('\u4e00' <= ch <= '\u9fff' for ch in s)
                    return True

                # For formula issues, verify the matched paragraph actually contains a formula pattern
                is_formula_issue = issue.module == 'Formula'

                found_idx = None
                for i, text in para_texts:
                    if kw in text and para_matches_language(text, issue.section):
                        if is_formula_issue:
                            # Skip paragraphs that don't contain a formula label pattern
                            if not FORMULA_PAT.search(text):
                                continue
                        found_idx = i
                        break
                para_idx = found_idx

            # if still None, skip but log
            if para_idx is None:
                logger.info(f"Could not locate paragraph for issue {issue.module}-{issue.section}, method={issue.locate_method}, data={issue.locate_data}")
                continue

            # format comment text
            comment_text = f"[{issue.module}-{issue.section}]\n"
            for m in issue.messages:
                comment_text += f"• {m}\n"

            # 公式批注优先锚定到 Math 元素内部，而非整个段落
            if issue.module == 'Formula' and issue.extra:
                math_elem = issue.extra.get('target_math_elem')
                if math_elem is not None:
                    added = commenter.add_comment_to_math_run(para_idx, math_elem, comment_text.strip())
                    if added:
                        logger.info(f"Added comment (math-anchored) at para {para_idx} for {issue.module}-{issue.section}")
                    else:
                        logger.warning(f"Failed to add math-anchored comment at para {para_idx}")
                    continue

            added = commenter.add_comment_to_para_idx(para_idx, comment_text.strip())

            if added:
                logger.info(f"Added comment at para {para_idx} for {issue.module}-{issue.section}")
            else:
                logger.warning(f"Failed to add comment at para {para_idx} for {issue.module}-{issue.section}")

        commenter.save(copy_path)
        logger.info(f"Annotation saved: {copy_path} (count={commenter.count})")
        return copy_path

    except Exception as e:
        logger.error(f"annotate_chinese_abstract_and_keywords failed: {e}", exc_info=True)
        return None


