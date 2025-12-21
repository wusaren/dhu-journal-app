"""
中文论文批注生成器（独立模块）

职责：
- 把检测器的报告（all_reports）通过 adapter 转成标准 Issue 列表
- 使用多种 locator 定位到文档段落索引
- 使用 Commenter 在 docx 副本上添加批注并保存

当前实现包含：
- Issue dataclass
- Locator 注册与若干内置 locator（index, keyword, abstract_title, abstract_content, keywords_title, keywords_content, content_paragraph）
- Commenter（只打开一次 doc，按 paragraph index 添加注释并保存）
- 两个 adapter：abstract_adapter、keywords_adapter（针对中文检测器输出）
- orchestrator 函数：annotate_chinese_abstract_and_keywords(docx_path, all_reports, output_dir)

说明：此模块为独立实现，不依赖原有的 document_annotator.py；用于快速接入中文摘要/关键词批注功能。
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


