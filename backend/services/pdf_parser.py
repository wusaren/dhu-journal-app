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

def extract_font_sizes_from_pdf_page(pdf_page) -> List[Dict[str, Any]]:
    """
    从PDF页面提取文本及其字号信息
    返回格式: [{"text": "文本内容", "fontsize": 字号, "line_number": 行号}]
    """
    try:
        import pdfplumber
        chars = pdf_page.chars
        if not chars:
            return []
        
        # 按y坐标分组，相同y坐标的字符在同一行
        lines = {}
        for char in chars:
            y = round(char['top'], 1)  # 四舍五入到小数点后1位，避免浮点误差
            if y not in lines:
                lines[y] = []
            lines[y].append(char)
        
        # 处理每一行
        line_data = []
        for line_num, (y, chars_in_line) in enumerate(sorted(lines.items())):
            # 按x坐标排序字符
            chars_in_line.sort(key=lambda c: c['x0'])
            
            # 获取该行的主要字号（出现频率最高的字号）
            font_sizes = [char['size'] for char in chars_in_line if char.get('size')]
            if not font_sizes:
                continue
                
            # 计算最频繁的字号
            from collections import Counter
            size_counter = Counter(font_sizes)
            most_common_size = size_counter.most_common(1)[0][0]
            
            # 合并该行的文本，保持空格分隔
            line_text = ''
            for i, char in enumerate(chars_in_line):
                if i > 0:
                    # 检查是否需要添加空格
                    prev_char = chars_in_line[i-1]
                    if char['x0'] - prev_char['x1'] > 2:  # 如果字符间距大于2，添加空格
                        line_text += ' '
                line_text += char['text']
            
            line_data.append({
                "text": line_text.strip(),
                "fontsize": most_common_size,
                "line_number": line_num
            })
        
        return line_data
    except Exception as e:
        logger.warning(f"提取字号信息失败: {e}")
        return []

def extract_title_authors_with_fontsize(text: str, pdf_page=None) -> tuple[str, str]:
    """
    基于字号检测的标题和作者提取 - 改进版本
    如果提供了pdf_page，则使用字号信息；否则回退到原来的方法
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    doi_idx = None
    for i, l in enumerate(lines[:15]):
        if re.search(r"\bDOI\b", l, re.I):
            doi_idx = i
            break
    
    title = authors = ""
    if doi_idx is None:
        return title, authors
    
    # 如果提供了PDF页面，使用字号检测
    if pdf_page:
        try:
            line_data = extract_font_sizes_from_pdf_page(pdf_page)
            if line_data:
                # 使用字号信息确定标题行数量，但完全使用原方法的文本处理逻辑
                title_line_count = get_title_line_count_by_fontsize(line_data, doi_idx)
                if title_line_count > 0:
                    return extract_title_authors_with_line_count(text, doi_idx, title_line_count)
        except Exception as e:
            logger.warning(f"字号检测失败，回退到原方法: {e}")
    
    # 回退到原来的方法
    return extract_title_authors_with_line_count(text, doi_idx, 2)

def get_title_line_count_by_fontsize(line_data: List[Dict[str, Any]], doi_line_idx: int) -> int:
    """根据字号信息确定标题行数量"""
    if not line_data:
        return 0
    
    # 找到DOI行在line_data中的对应位置
    doi_line_in_data = None
    for i, line_info in enumerate(line_data):
        if re.search(r"\bDOI\b", line_info["text"], re.I):
            doi_line_in_data = i
            break
    
    if doi_line_in_data is None:
        return 0
    
    # 获取DOI行之后的文本行
    subsequent_lines = line_data[doi_line_in_data + 1:]
    
    if not subsequent_lines:
        return 0
    
    # 计算字号统计信息
    font_sizes = [line["fontsize"] for line in subsequent_lines if line["fontsize"] and line["fontsize"] > 1]
    if not font_sizes:
        return 0
    
    # 找到最大字号（通常是标题字号）
    max_font_size = max(font_sizes)
    
    # 设置字号阈值：标题字号应该明显大于正文
    avg_font_size = sum(font_sizes) / len(font_sizes)
    font_size_threshold = max_font_size * 0.9 if max_font_size > avg_font_size * 1.2 else avg_font_size * 1.1
    
    # 找到标题行结束的位置（基于字号判断）
    title_line_count = 0
    title_started = False
    
    for i, line_info in enumerate(subsequent_lines):
        text = line_info["text"].strip()
        fontsize = line_info["fontsize"]
        
        # 跳过分隔符行和空行
        if text in (":", "：", "") or fontsize < 1:
            continue
        
        # 如果字号符合标题要求
        if fontsize >= font_size_threshold:
            title_started = True
            title_line_count += 1
        else:
            # 如果已经开始提取标题，遇到小字号行就停止
            if title_started:
                break
    
    return title_line_count if title_line_count > 0 else 2

def extract_title_authors_with_line_count(text: str, doi_idx: int, title_line_count: int) -> tuple[str, str]:
    """使用指定标题行数量提取标题和作者 - 完全使用原方法逻辑"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    # 完全使用原来的逻辑，只是把2改为title_line_count
    i = doi_idx + 1
    title_lines = []
    while i < len(lines) and len(title_lines) < title_line_count:
        if lines[i] in (":", "："): 
            i += 1
            continue
        title_lines.append(lines[i])
        i += 1
    title = re.sub(r"\s+", " ", " ".join(title_lines)).strip(" :")
    
    # 完全使用原来的作者提取逻辑
    authors = ""
    while i < len(lines):
        if lines[i] in (":", "："): 
            i += 1
            continue
        # 允许单空格、多空格、或逗号的作者行
        authors = re.sub(r"\s{2,}", ", ", re.sub(r"[∗*¹²³⁴⁵⁶⁷⁸⁹⁰0-9]", "", lines[i])).strip(" ,")
        break
    
    return title, authors


def extract_title_authors(text: str) -> tuple[str, str]:
    """提取标题和作者 - 保持向后兼容的接口"""
    return extract_title_authors_with_fontsize(text, None)
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

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_chinese_title_authors_from_page(pdf_page, page_start: int, page_end: int) -> tuple[str, str]:
    """
    从指定页面提取中文标题和作者
    结合字号判断和文本提取
    """
    try:
        # 提取文本
        text = pdf_page.extract_text() or ""
        
        if not text:
            return "", ""
        
        # 按行分割
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 找到包含中文的行
        chinese_lines = []
        for line in lines:
            if contains_chinese(line):
                chinese_lines.append(line)
        
        if not chinese_lines:
            return "", ""
        
        # 提取标题和作者
        chinese_title = ""
        chinese_authors = ""
        
        # 策略1：使用字号判断（暂时禁用，因为可能丢失逗号）
        # try:
        #     line_data = extract_font_sizes_from_pdf_page(pdf_page)
        #     if line_data:
        #         chinese_line_data = []
        #         for line_info in line_data:
        #             text = line_info["text"].strip()
        #             if text and contains_chinese(text):
        #                 chinese_line_data.append(line_info)
        #         
        #         if chinese_line_data:
        #             # 计算字号统计信息
        #             font_sizes = [line["fontsize"] for line in chinese_line_data if line["fontsize"] > 1]
        #             if font_sizes:
        #                 max_font_size = max(font_sizes)
        #                 avg_font_size = sum(font_sizes) / len(font_sizes)
        #                 font_size_threshold = max_font_size * 0.9 if max_font_size > avg_font_size * 1.2 else avg_font_size * 1.1
        #                 
        #                 # 提取标题和作者
        #                 title_lines = []
        #                 author_started = False
        #                 
        #                 for line_info in chinese_line_data:
        #                     text = line_info["text"].strip()
        #                     fontsize = line_info["fontsize"]
        #                     
        #                     if not text or fontsize < 1:
        #                         continue
        #                     
        #                     if fontsize >= font_size_threshold and not author_started:
        #                         title_lines.append(text)
        #                     else:
        #                         if title_lines and not author_started:
        #                             author_started = True
        #                             if fontsize < font_size_threshold:
        #                                 chinese_authors = text
        #                                 break
        #                             else:
        #                                 title_lines.append(text)
        #                         elif not title_lines:
        #                             title_lines.append(text)
        #                 
        #                 if title_lines:
        #                     chinese_title = " ".join(title_lines)
        # except:
        #     pass
        
        # 策略2：使用文本提取 + 字号判断标题行数
        if not chinese_title or not chinese_authors:
            # 使用字号判断来确定标题有几行
            title_line_count = 1  # 默认1行
            try:
                line_data = extract_font_sizes_from_pdf_page(pdf_page)
                if line_data:
                    chinese_line_data = []
                    for line_info in line_data:
                        text = line_info["text"].strip()
                        if text and contains_chinese(text):
                            chinese_line_data.append(line_info)
                    
                    if chinese_line_data:
                        # 计算字号统计信息
                        font_sizes = [line["fontsize"] for line in chinese_line_data if line["fontsize"] > 1]
                        if font_sizes:
                            max_font_size = max(font_sizes)
                            avg_font_size = sum(font_sizes) / len(font_sizes)
                            font_size_threshold = max_font_size * 0.9 if max_font_size > avg_font_size * 1.2 else avg_font_size * 1.1
                            
                            # 计算标题行数
                            title_line_count = 0
                            for line_info in chinese_line_data:
                                text = line_info["text"].strip()
                                fontsize = line_info["fontsize"]
                                if text and fontsize >= font_size_threshold:
                                    title_line_count += 1
                                else:
                                    break
                            if title_line_count == 0:
                                title_line_count = 1
            except:
                pass
            
            # 根据字号判断的结果，合并相应行数的标题
            title_lines = []
            for i, line in enumerate(chinese_lines):
                if i < title_line_count:
                    title_lines.append(line)
                else:
                    # 查找包含逗号的中文行作为作者
                    if (',' in line or '，' in line) and not chinese_authors:
                        chinese_authors = line
                        break
            
            # 合并标题行
            if title_lines:
                chinese_title = "".join(title_lines)
        
        # 如果还是没有作者，尝试合并多行标题
        if not chinese_authors and len(chinese_lines) > 1:
            # 合并前几行作为标题，最后一行作为作者
            title_lines = []
            for i, line in enumerate(chinese_lines):
                if i < len(chinese_lines) - 1:
                    title_lines.append(line)
                else:
                    chinese_authors = line
                    break
            if title_lines:
                chinese_title = "".join(title_lines)
        
        # 清理和格式化结果
        chinese_title = re.sub(r"\s+", " ", chinese_title).strip()
        
        if chinese_authors:
            # 先移除数字和特殊符号
            chinese_authors = re.sub(r"[∗*¹²³⁴⁵⁶⁷⁸⁹⁰0-9]", "", chinese_authors)
            # 将中文逗号转换为英文逗号
            chinese_authors = chinese_authors.replace('，', ',')
            # 处理两字人名中间的空格（如"张 煊" -> "张煊"）
            chinese_authors = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', chinese_authors)
            # 按逗号分离，清理每个部分的空格
            author_parts = [part.strip() for part in chinese_authors.split(',') if part.strip()]
            # 重新用英文逗号连接
            chinese_authors = ', '.join(author_parts)
        
        return chinese_title, chinese_authors
        
    except Exception as e:
        logger.warning(f"提取中文标题和作者失败: {e}")
        return "", ""

def find_paper_last_page(pdf, page_start: int, page_end: int) -> Optional[Any]:
    """
    根据页码范围找到论文的最后一页
    page_start, page_end: 期刊实际页码
    """
    try:
        for page in pdf.pages:
            text = page.extract_text() or ""
            actual_page_num = extract_start_page(text)
            if actual_page_num == page_end:
                return page
        return None
    except Exception as e:
        logger.warning(f"查找论文最后一页失败: {e}")
        return None

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
                    # 使用新的字号检测方法提取标题和作者
                    title, authors_line = extract_title_authors_with_fontsize(text, pdf.pages[page_index])
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
                    
                    # 提取中文标题和作者（从论文的最后一页）
                    chinese_title = ""
                    chinese_authors = ""
                    if page_end:
                        try:
                            last_page = find_paper_last_page(pdf, actual_start_page, page_end)
                            if last_page:
                                chinese_title, chinese_authors = extract_chinese_title_authors_from_page(
                                    last_page, actual_start_page, page_end
                                )
                                logger.info(f"中文标题: '{chinese_title[:50]}...'")
                                logger.info(f"中文作者: '{chinese_authors[:50]}...'")
                        except Exception as chinese_error:
                            logger.warning(f"提取中文标题和作者失败: {chinese_error}")
                    
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
                        "chinese_title": chinese_title,
                        "chinese_authors": chinese_authors,
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
