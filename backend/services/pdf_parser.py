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

def extract_citation(text: str) -> Optional[str]:
    """
    提取Citation:后的在当前页的所有文本
    Citation:位于整页的最下面，需要提取Citation:后同一行的内容和当前页Citation行下面的所有内容
    参数:
        text: PDF页面的文本内容
    返回:
        Citation文本内容，如果没有找到则返回None
    """
    try:
        lines = text.split('\n')
        citation_lines = []
        found_citation = False
        
        # 从最后一行开始向前搜索，因为Citation在页面底部
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            
            # 查找包含Citation的行
            if re.search(r'Citation\s*[:：]', line, re.IGNORECASE):
                found_citation = True
                
                # 提取Citation:后的内容（同一行）
                citation_part = re.sub(r'Citation\s*[:：]\s*', '', line, flags=re.IGNORECASE)
                if citation_part:
                    citation_lines.insert(0, citation_part)  # 插入到列表开头
                
                # 继续向前收集Citation行上面的内容（页面底部向上）
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line:  # 只收集非空行
                        citation_lines.append(next_line)
                    else:
                        # 遇到空行停止收集（可能是页面边界）
                        break
                
                break  # 找到第一个Citation行就停止搜索
        
        if citation_lines:
            citation_text = ' '.join(citation_lines).strip()
            citation_text = re.sub(r'\s+', ' ', citation_text)  # 清理多余空格
            
            # 如果提取的文本太短，可能是匹配不完整
            if len(citation_text) < 10:
                logger.info("提取的Citation文本太短，可能不完整")
                return None
            
            logger.info(f"成功提取Citation文本，长度: {len(citation_text)}")
            return citation_text
        
        logger.info("未找到Citation信息")
        return None
        
    except Exception as e:
        logger.error(f"提取Citation时出错: {str(e)}")
        return None

def extract_images_from_paper(pdf_path: str, paper_page_range: tuple, output_dir: str, start_page_offset: int = 0) -> Dict[str, Optional[str]]:
    """
    从论文页面范围提取第一张和第二张图片
    paper_page_range: (start_page, end_page) 期刊页码范围
    start_page_offset: 期刊起始页码与PDF第一页的偏移量
    返回: 包含两张图片路径的字典 {'first_image': 路径, 'second_image': 路径}
    """
    try:
        # 尝试导入PyMuPDF
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF未安装，请运行: pip install PyMuPDF")
            return {'first_image': None, 'second_image': None}
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        doc = fitz.open(pdf_path)
        image_paths = {'first_image': None, 'second_image': None}
        extracted_count = 0
        
        logger.info(f"开始提取图片，期刊页码范围: {paper_page_range}, PDF总页数: {len(doc)}, 偏移量: {start_page_offset}")
        
        # 计算期刊页码与PDF页面索引的映射
        journal_start_page = paper_page_range[0]
        journal_end_page = paper_page_range[1]
        
        # 计算PDF页面索引范围
        pdf_start_index = journal_start_page - start_page_offset - 1  # 期刊页码315对应PDF索引0
        pdf_end_index = journal_end_page - start_page_offset - 1
        
        logger.info(f"期刊页码 {journal_start_page}-{journal_end_page} 映射到PDF索引 {pdf_start_index}-{pdf_end_index}")
        
        # 遍历论文的所有页面（PDF索引范围）
        for pdf_page_index in range(pdf_start_index, pdf_end_index + 1):
            try:
                if pdf_page_index < 0 or pdf_page_index >= len(doc):
                    logger.warning(f"PDF索引 {pdf_page_index} 超出PDF范围 (0-{len(doc)-1})")
                    continue
                
                page = doc[pdf_page_index]
                image_list = page.get_images()
                
                # 计算对应的期刊页码
                journal_page_num = pdf_page_index + start_page_offset + 1
                
                logger.info(f"检查PDF第 {pdf_page_index + 1} 页 (期刊第 {journal_page_num} 页): 找到 {len(image_list)} 张图片")
                
                if image_list:
                    # 提取图片，最多提取两张
                    for img_index, img in enumerate(image_list[:2]):  # 只处理前两张图片
                        if extracted_count >= 2:
                            break  # 已经提取了两张图片
                            
                        try:
                            xref = img[0]
                            logger.info(f"提取图片 {img_index + 1}: xref={xref}, 图片元数据: {img}")
                            
                            pix = fitz.Pixmap(doc, xref)
                            
                            # 处理CMYK格式图片 - 转换为RGB
                            if pix.n - pix.alpha == 4:  # CMYK格式
                                logger.info(f"检测到CMYK格式图片，转换为RGB")
                                # 创建RGB Pixmap
                                pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                                
                                # 生成有意义的文件名
                                if extracted_count == 0:
                                    # 第一张图片：添加QRcode后缀
                                    filename = f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image_QRcode.png"
                                else:
                                    # 第二张图片：不加后缀
                                    filename = f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image.png"
                                
                                output_path = os.path.join(output_dir, filename)
                                pix_rgb.save(output_path)
                                
                                if extracted_count == 0:
                                    image_paths['first_image'] = output_path
                                    logger.info(f"✅ 成功提取第一张图片(QRcode): {output_path}, 尺寸: {pix_rgb.width}x{pix_rgb.height}")
                                else:
                                    image_paths['second_image'] = output_path
                                    logger.info(f"✅ 成功提取第二张图片: {output_path}, 尺寸: {pix_rgb.width}x{pix_rgb.height}")
                                
                                pix_rgb = None  # 释放内存
                                extracted_count += 1
                                
                            elif pix.n - pix.alpha < 4:  # 如果不是CMYK
                                # 生成有意义的文件名
                                if extracted_count == 0:
                                    # 第一张图片：添加QRcode后缀
                                    filename = f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image_QRcode.png"
                                else:
                                    # 第二张图片：不加后缀
                                    filename = f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image.png"
                                
                                output_path = os.path.join(output_dir, filename)
                                pix.save(output_path)
                                
                                if extracted_count == 0:
                                    image_paths['first_image'] = output_path
                                    logger.info(f"✅ 成功提取第一张图片(QRcode): {output_path}, 尺寸: {pix.width}x{pix.height}")
                                else:
                                    image_paths['second_image'] = output_path
                                    logger.info(f"✅ 成功提取第二张图片: {output_path}, 尺寸: {pix.width}x{pix.height}")
                                
                                extracted_count += 1
                            else:
                                logger.warning(f"图片格式不支持: n={pix.n}, alpha={pix.alpha}")
                            
                            pix = None  # 释放内存
                            
                        except Exception as img_error:
                            logger.error(f"提取图片 {img_index + 1} 时出错: {str(img_error)}")
                            continue
                    
                    if extracted_count >= 2:
                        break  # 已经提取了两张图片，停止搜索
                else:
                    logger.info(f"PDF第 {pdf_page_index + 1} 页 (期刊第 {journal_page_num} 页) 未找到图片")
            
            except Exception as page_error:
                logger.error(f"处理PDF第 {pdf_page_index + 1} 页时出错: {str(page_error)}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
                continue
        
        doc.close()
        
        if extracted_count == 0:
            logger.warning(f"在页码范围 {paper_page_range} 内未找到任何图片")
        else:
            logger.info(f"成功提取 {extracted_count} 张图片")
        
        return image_paths
        
    except Exception as e:
        logger.error(f"图片提取失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {'first_image': None, 'second_image': None}

def batch_extract_images_for_journal(journal_papers: List[Dict], pdf_path: str, output_dir: str, journal_issue: str = None) -> List[Dict]:
    """
    批量处理期刊中的所有论文，为每篇论文提取第一张和第二张图片
    journal_papers: 论文列表，每个论文包含page_start和page_end
    pdf_path: PDF文件路径
    output_dir: 图片输出目录
    journal_issue: 期刊期号，用于MinIO对象命名
    返回: 更新后的论文列表，包含两张图片路径字段
    """
    logger.info(f"开始批量提取图片，共 {len(journal_papers)} 篇论文")
    
    # 计算页码偏移量：期刊起始页码 - 1
    if journal_papers:
        first_paper_start = journal_papers[0].get('page_start')
        if first_paper_start:
            start_page_offset = first_paper_start - 1
            logger.info(f"计算页码偏移量: 期刊起始页码 {first_paper_start} -> 偏移量 {start_page_offset}")
        else:
            start_page_offset = 0
            logger.warning("无法获取期刊起始页码，使用默认偏移量 0")
    else:
        start_page_offset = 0
        logger.warning("没有论文数据，使用默认偏移量 0")
    
    for i, paper in enumerate(journal_papers):
        try:
            # 获取论文的页码范围
            page_start = paper.get('page_start')
            page_end = paper.get('page_end')
            
            if not page_start or not page_end:
                logger.warning(f"论文 {i+1} 缺少页码范围，跳过图片提取")
                continue
            
            paper_page_range = (page_start, page_end)
            logger.info(f"处理第 {i+1} 篇论文: 页码范围 {paper_page_range}")
            
            # 提取第一张和第二张图片，使用正确的偏移量
            image_paths = extract_images_from_paper(pdf_path, paper_page_range, output_dir, start_page_offset)
            
            # 更新论文信息
            paper['first_image_path'] = image_paths['first_image']
            paper['second_image_path'] = image_paths['second_image']
            paper['has_first_image'] = image_paths['first_image'] is not None
            paper['has_second_image'] = image_paths['second_image'] is not None
            
            if image_paths['first_image']:
                logger.info(f"论文 {i+1} 成功提取第一张图片(QRcode): {image_paths['first_image']}")
            else:
                logger.info(f"论文 {i+1} 未找到第一张图片")
                
            if image_paths['second_image']:
                logger.info(f"论文 {i+1} 成功提取第二张图片: {image_paths['second_image']}")
            else:
                logger.info(f"论文 {i+1} 未找到第二张图片")
                
        except Exception as paper_error:
            logger.error(f"处理论文 {i+1} 时出错: {str(paper_error)}")
            paper['first_image_path'] = None
            paper['second_image_path'] = None
            paper['has_first_image'] = False
            paper['has_second_image'] = False
    
    logger.info("批量图片提取完成")
    return journal_papers

def upload_images_to_minio(journal_papers: List[Dict], journal_issue: str) -> List[Dict]:
    """
    将提取的两张图片上传到MinIO，但不立即更新数据库
    journal_papers: 论文列表，包含first_image_path和second_image_path字段
    journal_issue: 期刊期号
    返回: 更新后的论文列表，包含两张图片的minio_url字段
    """
    try:
        from services.minio_service import minio_service
        
        logger.info(f"开始上传两张图片到MinIO，期刊期号: {journal_issue}")
        
        for i, paper in enumerate(journal_papers):
            try:
                # 获取两张图片的路径
                first_image_path = paper.get('first_image_path')
                second_image_path = paper.get('second_image_path')
                
                # 获取论文的页码范围
                page_start = paper.get('page_start')
                page_end = paper.get('page_end')
                
                if not page_start or not page_end:
                    logger.warning(f"论文 {i+1} 缺少页码范围，跳过上传")
                    continue
                
                # 清理期刊期号中的特殊字符，使其适合作为文件名
                clean_journal_issue = journal_issue.replace(',', '_').replace('(', '_').replace(')', '')
                
                # 上传第一张图片（QRcode）
                if first_image_path and os.path.exists(first_image_path):
                    # 生成第一张图片的对象名称：期刊号+页码范围+QRcode
                    file_extension = Path(first_image_path).suffix.lower()
                    first_object_name = f"papers/{clean_journal_issue}/pages_{page_start}-{page_end}_image_QRcode{file_extension}"
                    
                    logger.info(f"处理论文 {i+1} 第一张图片(QRcode): 期刊期号={journal_issue}, 页码范围={page_start}-{page_end}, 对象名称={first_object_name}")
                    
                    # 上传第一张图片到MinIO
                    first_minio_url = minio_service.upload_image(first_image_path, first_object_name)
                    
                    if first_minio_url:
                        logger.info(f"论文 {i+1} 第一张图片(QRcode) MinIO上传成功: {first_minio_url}")
                        paper['first_minio_url'] = first_minio_url
                        paper['first_minio_upload_success'] = True
                    else:
                        logger.error(f"论文 {i+1} 第一张图片(QRcode) 上传到MinIO失败")
                        paper['first_minio_url'] = None
                        paper['first_minio_upload_success'] = False
                else:
                    logger.warning(f"论文 {i+1} 第一张图片不存在或路径无效: {first_image_path}")
                    paper['first_minio_url'] = None
                    paper['first_minio_upload_success'] = False
                
                # 上传第二张图片
                if second_image_path and os.path.exists(second_image_path):
                    # 生成第二张图片的对象名称：期刊号+页码范围
                    file_extension = Path(second_image_path).suffix.lower()
                    second_object_name = f"papers/{clean_journal_issue}/pages_{page_start}-{page_end}_image{file_extension}"
                    
                    logger.info(f"处理论文 {i+1} 第二张图片: 期刊期号={journal_issue}, 页码范围={page_start}-{page_end}, 对象名称={second_object_name}")
                    
                    # 上传第二张图片到MinIO
                    second_minio_url = minio_service.upload_image(second_image_path, second_object_name)
                    
                    if second_minio_url:
                        logger.info(f"论文 {i+1} 第二张图片 MinIO上传成功: {second_minio_url}")
                        paper['second_minio_url'] = second_minio_url
                        paper['second_minio_upload_success'] = True
                    else:
                        logger.error(f"论文 {i+1} 第二张图片 上传到MinIO失败")
                        paper['second_minio_url'] = None
                        paper['second_minio_upload_success'] = False
                else:
                    logger.warning(f"论文 {i+1} 第二张图片不存在或路径无效: {second_image_path}")
                    paper['second_minio_url'] = None
                    paper['second_minio_upload_success'] = False
                    
            except Exception as upload_error:
                logger.error(f"论文 {i+1} 上传过程出错: {str(upload_error)}")
                paper['first_minio_url'] = None
                paper['second_minio_url'] = None
                paper['first_minio_upload_success'] = False
                paper['second_minio_upload_success'] = False
        
        logger.info("两张图片的MinIO上传完成")
        return journal_papers
        
    except Exception as e:
        logger.error(f"MinIO上传失败: {str(e)}")
        return journal_papers

def update_paper_images_in_db(journal_papers: List[Dict]) -> int:
    """
    将两张图片的MinIO URL批量更新到数据库
    journal_papers: 论文列表，包含first_minio_url和second_minio_url字段
    返回: 成功更新的论文数量
    """
    try:
        # 添加父目录到Python路径，以便导入models
        import sys
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        sys.path.append(parent_dir)
        
        from models import Paper, db
        
        logger.info("开始批量更新数据库中的两张图片URL")
        
        updated_count = 0
        
        for i, paper in enumerate(journal_papers):
            try:
                first_minio_url = paper.get('first_minio_url')
                second_minio_url = paper.get('second_minio_url')
                page_start = paper.get('page_start')
                page_end = paper.get('page_end')
                
                # 只有有页码范围的论文才更新数据库
                if not page_start or not page_end:
                    continue
                
                # 查找对应的论文记录
                paper_record = Paper.query.filter_by(
                    page_start=page_start,
                    page_end=page_end
                ).first()
                
                if paper_record:
                    # 更新第一张图片URL（QRcode）
                    if first_minio_url:
                        paper_record.first_image_url = first_minio_url
                        logger.info(f"论文 {i+1} 第一张图片(QRcode) URL更新准备: {first_minio_url}")
                    
                    # 更新第二张图片URL
                    if second_minio_url:
                        paper_record.second_image_url = second_minio_url
                        logger.info(f"论文 {i+1} 第二张图片 URL更新准备: {second_minio_url}")
                    
                    updated_count += 1
                else:
                    logger.warning(f"论文 {i+1} 在数据库中未找到对应记录，页码范围: {page_start}-{page_end}")
                    
            except Exception as update_error:
                logger.error(f"论文 {i+1} 数据库更新准备失败: {str(update_error)}")
        
        # 批量提交数据库更新
        if updated_count > 0:
            db.session.commit()
            logger.info(f"✅ 成功批量更新 {updated_count} 篇论文的两张图片URL到数据库")
        else:
            logger.info("没有需要更新的论文记录")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"数据库批量更新失败: {str(e)}")
        db.session.rollback()
        return 0

def process_journal_with_images(pdf_path: str, journal_id: int, journal_issue: str, output_dir: str) -> List[Dict]:
    """
    完整的期刊处理流程：解析PDF、提取图片、上传MinIO、更新数据库
    pdf_path: PDF文件路径
    journal_id: 期刊ID
    journal_issue: 期刊期号
    output_dir: 临时图片输出目录
    返回: 处理后的论文列表
    """
    logger.info(f"开始完整期刊处理流程: {pdf_path}")
    
    # 1. 解析PDF获取论文信息（使用集成解析函数）
    papers = parse_pdf_to_papers(pdf_path, journal_id, output_dir)
    if not papers:
        logger.error("PDF解析失败，无法继续处理")
        return []
    
    logger.info(f"成功解析出 {len(papers)} 篇论文")
    
    # 2. 批量提取图片（如果需要额外的图片处理）
    papers_with_images = batch_extract_images_for_journal(papers, pdf_path, output_dir, journal_issue)
    
    # 3. 上传图片到MinIO（不立即更新数据库）
    papers_with_minio_urls = upload_images_to_minio(papers_with_images, journal_issue)
    
    # 4. 批量更新数据库（在最后统一更新）
    updated_count = update_paper_images_in_db(papers_with_minio_urls)
    
    # 统计结果
    first_images_extracted = sum(1 for p in papers_with_minio_urls if p.get('has_first_image', False))
    second_images_extracted = sum(1 for p in papers_with_minio_urls if p.get('has_second_image', False))
    first_images_uploaded = sum(1 for p in papers_with_minio_urls if p.get('first_minio_upload_success', False))
    second_images_uploaded = sum(1 for p in papers_with_minio_urls if p.get('second_minio_upload_success', False))
    
    logger.info(f"处理完成: 提取第一张图片 {first_images_extracted}/{len(papers_with_minio_urls)}，第二张图片 {second_images_extracted}/{len(papers_with_minio_urls)}，上传成功 {first_images_uploaded}/{first_images_extracted} + {second_images_uploaded}/{second_images_extracted}，数据库更新 {updated_count}/{len(papers_with_minio_urls)}")
    
    return papers_with_minio_urls
def parse_pdf_to_papers(pdf_path: str, journal_id: int, output_dir: str) -> List[Dict[str, Any]]:
    """
    解析PDF文件并提取图片，构建完整的论文记录（包含图片URL）
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
            
            # 第二步：为每篇论文提取信息、提取图片并计算正确的结束页码
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
                    citation = extract_citation(text)
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
                    
                    # 提取图片
                    paper_page_range = (actual_start_page, page_end)
                    image_paths = extract_images_from_paper(pdf_path, paper_page_range, output_dir, actual_start_page - 1)
                    
                    # 上传图片到MinIO并获取URL
                    first_minio_url = None
                    second_minio_url = None
                    first_upload_success = False
                    second_upload_success = False
                    
                    # 上传第一张图片（QRcode）
                    if image_paths['first_image'] and os.path.exists(image_paths['first_image']):
                        try:
                            from services.minio_service import minio_service
                            # 使用解析出的issue信息来构建MinIO对象名称
                            if issue:
                                clean_journal_issue = issue.replace(',', '_').replace('(', '_').replace(')', '')
                            else:
                                clean_journal_issue = "unknown_issue"
                            file_extension = Path(image_paths['first_image']).suffix.lower()
                            first_object_name = f"papers/{clean_journal_issue}/pages_{actual_start_page}-{page_end}_image_QRcode{file_extension}"
                            
                            first_minio_url = minio_service.upload_image(image_paths['first_image'], first_object_name)
                            if first_minio_url:
                                first_upload_success = True
                                logger.info(f"论文 {i+1} 第一张图片(QRcode) MinIO上传成功: {first_minio_url}")
                            else:
                                logger.error(f"论文 {i+1} 第一张图片(QRcode) 上传到MinIO失败")
                        except Exception as upload_error:
                            logger.error(f"论文 {i+1} 第一张图片上传失败: {str(upload_error)}")
                    
                    # 上传第二张图片
                    if image_paths['second_image'] and os.path.exists(image_paths['second_image']):
                        try:
                            from services.minio_service import minio_service
                            # 使用解析出的issue信息来构建MinIO对象名称
                            if issue:
                                clean_journal_issue = issue.replace(',', '_').replace('(', '_').replace(')', '')
                            else:
                                clean_journal_issue = "unknown_issue"
                            file_extension = Path(image_paths['second_image']).suffix.lower()
                            second_object_name = f"papers/{clean_journal_issue}/pages_{actual_start_page}-{page_end}_image{file_extension}"
                            
                            second_minio_url = minio_service.upload_image(image_paths['second_image'], second_object_name)
                            if second_minio_url:
                                second_upload_success = True
                                logger.info(f"论文 {i+1} 第二张图片 MinIO上传成功: {second_minio_url}")
                            else:
                                logger.error(f"论文 {i+1} 第二张图片 上传到MinIO失败")
                        except Exception as upload_error:
                            logger.error(f"论文 {i+1} 第二张图片上传失败: {str(upload_error)}")
                    
                    # 构建完整的论文记录（只保留URL信息）
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
                        "citation": citation,  # 新增Citation信息
                        "is_dhu": is_dhu,
                        "page_start": actual_start_page,
                        "page_end": page_end,
                        "abstract": "解析出的摘要信息...",  # 简化处理
                        "keywords": "解析出的关键词...",  # 简化处理
                        
                        # MinIO图片URL信息
                        "first_minio_url": first_minio_url,
                        "second_minio_url": second_minio_url,
                        "first_minio_upload_success": first_upload_success,
                        "second_minio_upload_success": second_upload_success
                    }
                    
                    # 调试信息
                    logger.info(f"解析结果: 标题={title[:30]}, 作者={authors_display[:30]}, 期刊页码={actual_start_page}-{page_end}, 期号={issue}")
                    if first_upload_success:
                        logger.info(f"第一张图片URL: {first_minio_url}")
                    if second_upload_success:
                        logger.info(f"第二张图片URL: {second_minio_url}")
                    
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
