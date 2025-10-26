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
    """提取起始页码 - 改进版本，处理奇偶页不同位置"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    # 分别处理奇偶页的页码位置
    even_page_patterns = [
        r'^\s*(\d{1,4})\b',  # 行首的1-4位数字（偶数页）
    ]
    
    odd_page_patterns = [
        r'\b(\d{1,4})\s*$',  # 行尾的1-4位数字（奇数页）
    ]
    
    candidates = []
    
    # 搜索偶数页位置（行首）
    for line in lines[:10]:
        for pattern in even_page_patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                num = int(match)
                if 1 <= num <= 9999:
                    candidates.append(num)
    
    # 搜索奇数页位置（行尾）
    for line in lines[:10]:
        for pattern in odd_page_patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                num = int(match)
                if 1 <= num <= 9999:
                    candidates.append(num)
    
    if not candidates:
        return None
    
    # 选择策略：优先选择合理的页码范围
    reasonable_candidates = [c for c in candidates if 100 <= c <= 999]
    
    if reasonable_candidates:
        # 返回最小的合理页码（通常是起始页）
        return min(reasonable_candidates)
    else:
        # 如果没有合理范围内的页码，返回最小的候选页码
        return min(candidates)

def extract_end_page(text: str, start_page: int = None, total_pages: int = None) -> Optional[int]:
    """提取结束页码 - 简化版本，直接使用数学计算"""
    # 如果有起始页和总页数，直接计算
    if start_page and total_pages:
        return start_page + total_pages - 1
    
    # 如果没有起始页或总页数，返回None
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
            authors = re.sub(r"\s{2,}", ", ", re.sub(r"[∗*¹²³⁴⁵⁶⁷⁸⁹⁰0-9]", "", lines[i])).strip(" ,")
            break
    
    return title, authors
# def extract_title_authors(text: str) -> tuple[str, str]:
#     """提取标题和作者 - 先找作者行，再提取标题"""
#     lines = [l.strip() for l in text.splitlines() if l.strip()]
#     doi_idx = None
#     author_idx = None
    
#     # 1. 先找到DOI行
#     for i, l in enumerate(lines[:15]):
#         if re.search(r"\bDOI\b", l, re.I):
#             doi_idx = i
#             break
    
#     title = authors = ""
#     if doi_idx is not None:
#         # 2. 在DOI行之后寻找作者行
#         for i in range(doi_idx + 1, min(doi_idx + 10, len(lines))):
#             line = lines[i]
#             # 跳过分隔符行
#             if line in (":", "：", ""):
#                 continue
            
#             # 检查是否符合作者行特征：2-5个连续大写字母开头，逗号分隔
#             # 匹配模式：大写字母开头，包含逗号分隔的名字
#             if re.search(r'^[A-Z]{2,5}\b.*?,.*?[A-Z]', line):
#                 author_idx = i
#                 # 提取作者
#                 authors = re.sub(r"\s{2,}", ", ", re.sub(r"[∗*¹²³⁴⁵⁶⁷⁸⁹⁰0-9]", "", line)).strip(" ,")
#                 break
        
#         # 3. 提取标题（DOI行和作者行之间的内容）
#         if author_idx is not None:
#             title_lines = []
#             for i in range(doi_idx + 1, author_idx):
#                 line = lines[i]
#                 # 跳过分隔符行
#                 if line in (":", "：", ""):
#                     continue
#                 title_lines.append(line)
            
#             title = re.sub(r"\s+", " ", " ".join(title_lines)).strip(" :")
    
#     return title, authors

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
    解析PDF文件，提取论文信息 - 改进版本，支持多篇论文
    基于论文边界识别策略：
    - 每篇论文起始页都有DOI
    - 论文结尾另起一页再接下一篇论文
    - 论文结束页 = 下一篇论文起始页 - 1
    - 最后一篇论文结束页 = 最后一页的实际页码
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
            
            # 第一步：收集所有包含DOI的页面及其实际页码
            doi_pages_info = []  # 存储(页面索引, 实际页码)
            for pi in range(n_pages):
                try:
                    text = pdf.pages[pi].extract_text() or ""
                    if "DOI" in text:
                        actual_page_num = extract_start_page(text)
                        if actual_page_num:
                            doi_pages_info.append((pi, actual_page_num))
                            logger.info(f"发现DOI页: PDF第 {pi+1} 页，期刊页码 {actual_page_num}")
                        else:
                            logger.warning(f"发现DOI页但无法提取页码: PDF第 {pi+1} 页")
                except Exception as e:
                    logger.warning(f"读取第 {pi+1} 页时出错: {e}")
                    continue
            
            logger.info(f"共发现 {len(doi_pages_info)} 篇论文")
            
            # 第二步：为每篇论文提取信息并计算正确的结束页码
            for i, (page_index, actual_start_page) in enumerate(doi_pages_info):
                try:
                    # 获取当前论文的起始页文本
                    text = pdf.pages[page_index].extract_text() or ""
                    
                    logger.info(f"处理第 {i+1} 篇论文，期刊起始页码: {actual_start_page}")
                    
                    # 提取各种信息
                    doi = extract_doi(text)
                    title, authors_line = extract_title_authors(text)
                    authors_display = normalize_authors_for_display(authors_line) if authors_line else ""
                    first_author = first_author_from_authors(authors_line) if authors_line else ""
                    issue = extract_issue_info(text)
                    corresponding = extract_corresponding(text, authors_display)
                    is_dhu = "donghua university" in text.lower() or "东华大学" in text
                    
                    # 计算正确的结束页码（使用期刊实际页码）
                    if i < len(doi_pages_info) - 1:
                        # 不是最后一篇论文：结束页 = 下一篇论文起始页 - 1
                        next_start_page = doi_pages_info[i + 1][1]
                        page_end = next_start_page - 1
                    else:
                        # 最后一篇论文：结束页 = 最后一页的实际页码
                        try:
                            last_page_text = pdf.pages[-1].extract_text() or ""
                            last_page_num = extract_start_page(last_page_text)
                            page_end = last_page_num if last_page_num else None
                        except:
                            page_end = None
                    
                    logger.info(f"期刊页码范围: {actual_start_page} -> {page_end}")
                    
                    # 构建论文记录
                    record = {
                        "file_name": os.path.basename(pdf_path),
                        "pdf_pages": page_end - actual_start_page + 1 if page_end and actual_start_page else None,
                        "start_page": actual_start_page,
                        "title": title,
                        "authors": authors_display,
                        "first_author": first_author,
                        "corresponding": corresponding,
                        "doi": doi,
                        "manuscript_id": doi_to_manuscript_id(doi),
                        "issue": issue,
                        "is_dhu": is_dhu,
                        "page_start": actual_start_page,
                        "page_end": page_end,
                        "abstract": "解析出的摘要信息...",  # 简化处理
                        "keywords": "解析出的关键词..."  # 简化处理
                    }
                    
                    # 调试信息
                    logger.info(f"解析结果: 标题={title[:30]}, 作者={authors_display[:30]}, 期刊页码={actual_start_page}-{page_end}")
                    
                    records.append(record)
                    logger.info(f"提取论文 {i+1}: {title[:50]}...")
                    
                except Exception as page_error:
                    logger.error(f"处理第 {i+1} 篇论文时出错: {str(page_error)}")
                    continue
        
        if not records:
            logger.warning("未从PDF中提取到论文信息")
            return []
        
        logger.info(f"成功解析出 {len(records)} 篇论文，按顺序排列")
        return records
        
    except Exception as e:
        logger.error(f"PDF解析失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return []
