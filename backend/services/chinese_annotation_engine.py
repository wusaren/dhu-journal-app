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
    定位公式段落：如果公式段落无法添加批注（公式在文本框中），
    则尝试在右边的段落添加批注
    """
    if not isinstance(data, int):
        return None
    
    # 优先返回公式段落本身
    if 0 <= data < len(doc.paragraphs):
        return data
    
    return None


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
    
    # 用于去重：记录已处理过的表格编号（基于 table_desc）
    processed_tables = set()
    
    # 遍历每个表格
    for idx, table_item in enumerate(tables):
        if not isinstance(table_item, dict):
            continue

        table_desc = table_item.get('table_desc', f"表格")
        cn_idx = table_item.get('captions', {}).get('cn', {}).get('paragraph_index')
        en_idx = table_item.get('captions', {}).get('en', {}).get('paragraph_index')

        logger.info(f"table_adapter: processing table {idx}: {table_desc}, cn_para_idx={cn_idx}, en_para_idx={en_idx}")
        
        # 去重：检查是否已经处理过相同的表格编号
        # 使用 table_desc 作为去重键，同时考虑中文表题段落索引
        dedup_key = (table_desc, cn_idx)
        if dedup_key in processed_tables:
            logger.info(f"table_adapter: skipping duplicate table {table_desc} at cn_para_idx={cn_idx}")
            continue
        processed_tables.add(dedup_key)
        
        # 收集所有问题（不包含编号连续性问题，因为那是全局的）
        # 每个表格独立收集问题，避免问题累积
        all_messages = []
        
        # 中文表题格式问题
        cn_format = table_item.get('caption_cn_format', {})
        if isinstance(cn_format, dict) and cn_format.get('ok') is False:
            for msg in cn_format.get('messages', []):
                all_messages.append(f"[中文表题] {msg}")
        
        # 英文表题格式问题
        en_format = table_item.get('caption_en_format', {})
        if isinstance(en_format, dict) and en_format.get('ok') is False:
            for msg in en_format.get('messages', []):
                all_messages.append(f"[英文表题] {msg}")
        
        # 表格样式问题
        table_style = table_item.get('table_style', {})
        if isinstance(table_style, dict) and table_style.get('ok') is False:
            for msg in table_style.get('messages', []):
                all_messages.append(f"[表格样式] {msg}")
        
        # 内容对齐问题
        content_align = table_item.get('table_content_alignment', {})
        if isinstance(content_align, dict) and content_align.get('ok') is False:
            for msg in content_align.get('messages', []):
                all_messages.append(f"[内容对齐] {msg}")
        
        # 引用检查问题
        table_ref = table_item.get('table_reference', {})
        if isinstance(table_ref, dict) and table_ref.get('ok') is False:
            for msg in table_ref.get('messages', []):
                all_messages.append(f"[表格引用] {msg}")
        
        if not all_messages:
            continue
        
        # 获取定位信息
        para_idx = None
        captions = table_item.get('captions', {})
        cn_caption = captions.get('cn', {})
        en_caption = captions.get('en', {})
        
        # 优先使用中文表题段落（用户要求定位到中文表题）
        para_idx = cn_caption.get('paragraph_index')
        if para_idx is None:
            para_idx = en_caption.get('paragraph_index')
        if para_idx is None:
            para_idx = table_item.get('table_body_index')
        
        logger.info(f"table_adapter: adding issue for {table_desc} at para_idx={para_idx} with {len(all_messages)} messages")
        
        if isinstance(para_idx, int) and 0 <= para_idx < 100000:  # 合理的段落索引范围
            issues.append(Issue(
                module='Table',
                section=table_desc,
                messages=all_messages,
                locate_method='index',
                locate_data=para_idx
            ))
        else:
            # 尝试通过表题关键词定位
            locate_method = 'table_caption_en'
            locate_data = table_item
            issues.append(Issue(
                module='Table',
                section=table_desc,
                messages=all_messages,
                locate_method=locate_method,
                locate_data=locate_data
            ))
    
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
        
        # 只处理有问题的公式
        is_ok = format_check.get('ok', True)
        formula_label = para_item.get('formula_label', '公式')
        logger.info(f"formula_adapter: processing {formula_label}, ok={is_ok}")
        
        if is_ok:
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
        
        # 获取段落索引
        para_idx = para_item.get('paragraph_index')
        if para_idx is None:
            para_idx = para_item.get('index')
        if para_idx is None:
            para_idx = para_item.get('w_p_index')
        
        logger.info(f"formula_adapter: adding issue for {formula_label} at para_idx={para_idx}")
        
        if isinstance(para_idx, int) and 0 <= para_idx < 100000:
            # 尝试在公式段落添加批注，如果失败则在右边段落添加
            # 使用 special 定位方式，Commenter 会处理
            issues.append(Issue(
                module='Formula',
                section=formula_label,
                messages=all_messages,
                locate_method='formula_with_fallback',
                locate_data=para_idx
            ))
        else:
            import re
            kw_match = re.search(r'公式?[\s#]*(\d+[-\uFF0D]\d+)', formula_label)
            if kw_match:
                kw = f"公式{kw_match.group(1)}"
            else:
                kw = '公式'
            issues.append(Issue(
                module='Formula',
                section=formula_label,
                messages=all_messages,
                locate_method='keyword',
                locate_data=kw
            ))
    
    # 处理编号连续性问题（全局）
    numbering = formula_report.get('numbering', {})
    if isinstance(numbering, dict) and numbering.get('ok') is False:
        for msg in numbering.get('messages', []):
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
            
            # 对于 formula_with_fallback，如果定位失败或添加失败，尝试右边段落
            if para_idx is None and issue.locate_method == 'formula_with_fallback':
                # 直接使用传入的段落索引
                original_idx = issue.locate_data
                if isinstance(original_idx, int) and 0 <= original_idx < len(doc.paragraphs):
                    para_idx = original_idx
            
            # fallback: keyword search across paragraphs
            if para_idx is None and issue.locate_data:
                kw = str(issue.locate_data).lower()
                # search for paragraph that contains kw and matches language expectation
                def para_matches_language(text: str, section_name: str) -> bool:
                    # if english section, require ascii letters or 'keywords'
                    s = (text or "").strip().lower()
                    if 'english' in section_name.lower():
                        if any(c.isalpha() for c in s):
                            return True
                        if 'keywords' in s or 'abstract' in s:
                            return True
                        return False
                    # if chinese section, require CJK characters
                    if 'chinese' in section_name.lower():
                        return any('\u4e00' <= ch <= '\u9fff' for ch in s)
                    # otherwise accept any match
                    return True

                found_idx = None
                for i, text in para_texts:
                    if kw in text and para_matches_language(text, issue.section):
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

            added = commenter.add_comment_to_para_idx(para_idx, comment_text.strip())
            
            # 如果公式段落添加失败，尝试在右边的段落添加
            if not added and issue.locate_method == 'formula_with_fallback':
                # 尝试右边的段落
                right_idx = para_idx + 1
                if right_idx < len(doc.paragraphs):
                    added = commenter.add_comment_to_para_idx(right_idx, comment_text.strip())
                    if added:
                        logger.info(f"Added comment at right para {right_idx} for {issue.module}-{issue.section}")
            
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


