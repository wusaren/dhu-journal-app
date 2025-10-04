import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 完全照搬你的参考代码的提取函数
def extract_issue_info(text: str) -> Optional[str]:
    """提取期刊期号信息 - 完全照搬参考代码"""
    m = re.search(r"Vol\.\s*(\d+)\s+No\.\s*(\d+)\s+(\d{4})", text, re.I)
    if not m: 
        return None
    vol, no, year = m.groups()
    return f"{year}, {vol}({no})"

def extract_start_page(text: str) -> Optional[int]:
    """提取起始页码 - 完全照搬参考代码"""
    for line in [l.strip() for l in text.splitlines()][:6]:
        m = re.search(r"(\b\d{3}\b)\s*$", line)
        if m: 
            return int(m.group(1))
    return None

def extract_doi(text: str) -> Optional[str]:
    """提取DOI - 完全照搬参考代码"""
    m = re.search(r"\bDOI\b\s*[:：]?\s*([0-9]+\.[0-9]+/[^\s]+)", text, re.I)
    return m.group(1) if m else None

def extract_title_authors(text: str) -> tuple[str, str]:
    """提取标题和作者 - 完全照搬参考代码"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    doi_idx = None
    for i, l in enumerate(lines[:15]):
        if re.search(r"\bDOI\b", l, re.I):
            doi_idx = i
            break
    
    title = authors = ""
    if doi_idx is not None:
        i = doi_idx + 1
        title_lines = []
        while i < len(lines) and len(title_lines) < 2:
            if lines[i] in (":", "："): 
                i += 1
                continue
            title_lines.append(lines[i])
            i += 1
        title = re.sub(r"\s+", " ", " ".join(title_lines)).strip(" :")
        
        while i < len(lines):
            if lines[i] in (":", "："): 
                i += 1
                continue
            # 允许单空格、多空格、或逗号的作者行
            authors = re.sub(r"\s{2,}", ", ", re.sub(r"[∗*]", "", lines[i])).strip(" ,")
            break
    
    return title, authors

def normalize_authors_for_display(authors_line: str) -> str:
    """鲁棒作者规范化 - 完全照搬参考代码"""
    if "," in authors_line:
        parts = [p.strip() for p in re.split(r",\s*", authors_line) if p.strip()]
        pairs, i = [], 0
        while i < len(parts):
            if i + 1 < len(parts):
                pairs.append(f"{parts[i]} {parts[i+1]}")
                i += 2
            else:
                pairs.append(parts[i])
                i += 1
        return ", ".join(pairs)
    
    tokens = [t for t in re.split(r"\s+", authors_line.strip()) if t]
    pairs = [" ".join(tokens[i:i+2]) for i in range(0, len(tokens), 2)]
    return ", ".join(pairs)

def first_author_from_authors(authors_line: str) -> str:
    """提取第一作者 - 完全照搬参考代码"""
    disp = normalize_authors_for_display(authors_line)
    return disp.split(",")[0].strip() if disp else ""

def extract_corresponding(text: str, authors_display: Optional[str] = None) -> str:
    """提取通讯作者 - 完全照搬参考代码"""
    m = re.search(r"Correspondence\s+should\s+be\s+addressed\s+to\s+([^,;，；\n]+)", text, re.I)
    name = m.group(1).strip() if m else ""
    if not name: 
        return ""
    if authors_display:
        def norm(s: str) -> str: 
            return re.sub(r"\s+", "", s).lower()
        for a in [x.strip() for x in authors_display.split(",") if x.strip()]:
            if norm(name) in norm(a) or norm(a) in norm(name):
                return a
    return name

def doi_to_manuscript_id(doi: Optional[str]) -> Optional[str]:
    """DOI转稿件号 - 完全照搬参考代码"""
    if not doi: 
        return None
    m = re.search(r"\.(\d{9})$", doi)
    if not m: 
        return None
    tail = m.group(1)  # YYYYMMNNN
    return f"E{tail[:4]}-{tail[4:]}"

def parse_pdf_to_papers(pdf_path: str, journal_id: int) -> List[Dict[str, Any]]:
    """
    解析PDF文件，提取论文信息 - 完全照搬参考代码逻辑
    """
    try:
        # 尝试导入pdfplumber
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber未安装，请运行: pip install pdfplumber")
            return []
        
        records: List[Dict[str, Any]] = []
        
        with pdfplumber.open(pdf_path) as pdf:
            n_pages = len(pdf.pages)
            logger.info(f"PDF总页数: {n_pages}")
            
            for pi in range(n_pages):
                try:
                    text = pdf.pages[pi].extract_text() or ""
                    if "DOI" not in text: 
                        continue
                    
                    logger.info(f"处理第 {pi+1} 页，找到DOI信息")
                    
                    # 提取各种信息 - 严格按照参考代码
                    start_page = extract_start_page(text)
                    doi = extract_doi(text)
                    title, authors_line = extract_title_authors(text)
                    authors_display = normalize_authors_for_display(authors_line) if authors_line else ""
                    first_author = first_author_from_authors(authors_line) if authors_line else ""
                    issue = extract_issue_info(text)
                    corresponding = extract_corresponding(text, authors_display)
                    is_dhu = "donghua university" in text.lower() or "东华大学" in text
                    
                    # 计算结束页码（简单估算）
                    page_end = start_page + 4 if start_page else None
                    
                    # 按照参考代码逻辑 - 使用总页数
                    pdf_pages = n_pages if n_pages < 2000 else None
                    
                    logger.info(f"提取信息: DOI={doi}, 标题={title[:30]}, 作者={authors_display[:30]}")
                    
                    # 完全按照参考代码的字段结构
                    record = {
                        "file_name": os.path.basename(pdf_path),
                        "pdf_pages": pdf_pages,
                        "start_page": start_page,
                        "title": title,
                        "authors": authors_display,
                        "first_author": first_author,
                        "corresponding": corresponding,
                        "doi": doi,
                        "manuscript_id": doi_to_manuscript_id(doi),
                        "issue": issue,
                        "is_dhu": is_dhu,
                        "page_start": start_page,
                        "page_end": page_end,
                        "abstract": "解析出的摘要信息...",  # 简化处理
                        "keywords": "解析出的关键词..."  # 简化处理
                    }
                    
                    # 调试信息
                    logger.info(f"解析结果: manuscript_id={record['manuscript_id']}, pdf_pages={record['pdf_pages']}, first_author={record['first_author']}, corresponding={record['corresponding']}, issue={record['issue']}, is_dhu={record['is_dhu']}")
                    
                    records.append(record)
                    logger.info(f"提取论文: {title[:50]}...")
                    
                except Exception as page_error:
                    logger.error(f"处理第 {pi+1} 页时出错: {str(page_error)}")
                    continue
        
        if not records:
            logger.warning("未从PDF中提取到论文信息")
            return []
        
        logger.info(f"成功解析出 {len(records)} 篇论文")
        return records
        
    except Exception as e:
        logger.error(f"PDF解析失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return []


