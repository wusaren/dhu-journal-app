"""
PDF解析服务 - 基于MinerU JSON文件
完全重写，使用MinerU生成的_model.json文件进行解析
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def load_model_json(json_path: str) -> List[List[Dict[str, Any]]]:
    """
    加载并解析_model.json文件
    
    参数:
        json_path: _model.json文件路径
    
    返回:
        二维数组，外层是页数组，内层是每页的元素数组
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            logger.error(f"JSON文件格式错误：期望数组，得到 {type(data)}")
            return []
        
        logger.info(f"成功加载JSON文件，共 {len(data)} 页")
        return data
    except FileNotFoundError:
        logger.error(f"JSON文件不存在: {json_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON文件解析失败: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"加载JSON文件失败: {str(e)}")
        return []


def find_papers_by_doi(pages: List[List[Dict[str, Any]]]) -> List[int]:
    """
    通过DOI识别论文起始页
    
    参数:
        pages: 页数组（从load_model_json返回）
    
    返回:
        包含DOI的页索引列表（0-based）
    """
    doi_page_indices = []
    
    for page_idx, page_elements in enumerate(pages):
        # 查找该页中是否有包含"DOI:"的header元素
        for element in page_elements:
            if element.get('type') == 'header':
                content = element.get('content', '')
                if 'DOI:' in content or 'doi:' in content.lower():
                    doi_page_indices.append(page_idx)
                    logger.info(f"发现DOI页: 第 {page_idx + 1} 页，内容: {content[:50]}...")
                    break
    
    logger.info(f"共发现 {len(doi_page_indices)} 篇论文（DOI页）")
    return doi_page_indices


def extract_doi_from_header(header_content: str) -> Optional[str]:
    """
    从header content中提取DOI
    
    参数:
        header_content: header元素的content字段
    
    返回:
        DOI字符串，如 "10.19884/j.1672-5220.202405007"
    """
    # 提取DOI:后面的内容
    match = re.search(r'DOI\s*[:：]\s*([0-9]+\.[0-9]+/[^\s]+)', header_content, re.I)
    if match:
        return match.group(1).strip()
    return None


def doi_to_manuscript_id(doi: Optional[str]) -> Optional[str]:
    """
    DOI转稿件号
    
    参数:
        doi: DOI字符串
    
    返回:
        稿件号，如 "E2024-05007"
    """
    if not doi:
        return None
    match = re.search(r'\.(\d{9})$', doi)
    if not match:
        return None
    tail = match.group(1)  # YYYYMMNNN
    return f"E{tail[:4]}-{tail[4:]}"


def extract_corresponding_from_footnotes(pages: List[List[Dict[str, Any]]], 
                                        start_page_idx: int, 
                                        end_page_idx: int) -> str:
    """
    从page_footnote或footer中提取通讯作者
    
    参数:
        pages: 页数组
        start_page_idx: 起始页索引
        end_page_idx: 结束页索引
    
    返回:
        通讯作者名称
    """
    # 支持的元素类型：page_footnote 和 footer
    supported_types = ['page_footnote', 'footer']
    
    for page_idx in range(start_page_idx, min(end_page_idx + 1, len(pages))):
        page_elements = pages[page_idx]
        for element in page_elements:
            element_type = element.get('type')
            # 检查是否是支持的类型
            if element_type in supported_types:
                content = element.get('content', '')
                if 'Correspondence should be addressed to' in content:
                    # 提取"Correspondence should be addressed to"后面的内容
                    match = re.search(
                        r'Correspondence\s+should\s+be\s+addressed\s+to\s+([^,;，；\n]+)',
                        content,
                        re.I
                    )
                    if match:
                        return match.group(1).strip()
    return ""


def extract_citations_from_footnotes(pages: List[List[Dict[str, Any]]], 
                                     start_page_idx: int, 
                                     end_page_idx: int) -> str:
    """
    提取Citations：查找以"Citation:"开头的page_footnote或footer元素，
    将该元素以及后续的所有page_footnote/footer元素（直到遇见别的元素类型）提取并拼接
    
    参数:
        pages: 页数组
        start_page_idx: 起始页索引
        end_page_idx: 结束页索引
    
    返回:
        拼接后的citations字符串
    """
    citations = []
    found_citation_start = False
    # 支持的元素类型：page_footnote 和 footer
    supported_types = ['page_footnote', 'footer']
    
    for page_idx in range(start_page_idx, min(end_page_idx + 1, len(pages))):
        page_elements = pages[page_idx]
        
        for i, element in enumerate(page_elements):
            element_type = element.get('type')
            content = element.get('content', '')
            
            # 查找以"Citation:"开头的page_footnote或footer
            if element_type in supported_types and content.strip().startswith('Citation:'):
                found_citation_start = True
                # 提取"Citation:"后的内容
                citation_text = re.sub(r'^Citation\s*[:：]\s*', '', content, flags=re.I).strip()
                if citation_text:
                    citations.append(citation_text)
                
                # 继续提取后续的page_footnote或footer元素
                for j in range(i + 1, len(page_elements)):
                    next_element = page_elements[j]
                    next_element_type = next_element.get('type')
                    if next_element_type in supported_types:
                        next_content = next_element.get('content', '').strip()
                        if next_content:
                            citations.append(next_content)
                    else:
                        # 遇到其他类型元素，停止提取
                        break
                break
            elif found_citation_start and element_type not in supported_types:
                # 如果已经开始提取citations，遇到非支持类型元素就停止
                break
    
    return ' '.join(citations) if citations else ""


def extract_images_from_json(pages: List[List[Dict[str, Any]]], 
                             start_page_idx: int, 
                             end_page_idx: int) -> List[Dict[str, Any]]:
    """
    从JSON中提取图片信息
    
    参数:
        pages: 页数组
        start_page_idx: 起始页索引
        end_page_idx: 结束页索引
    
    返回:
        图片元素列表
    """
    images = []
    for page_idx in range(start_page_idx, min(end_page_idx + 1, len(pages))):
        page_elements = pages[page_idx]
        for element in page_elements:
            if element.get('type') == 'image':
                images.append(element)
    return images


def extract_paper_info_from_json(pages: List[List[Dict[str, Any]]], 
                                 start_page_idx: int, 
                                 end_page_idx: int) -> Dict[str, Any]:
    """
    从指定页码范围提取论文信息
    
    参数:
        pages: 页数组
        start_page_idx: 起始页索引（0-based）
        end_page_idx: 结束页索引（0-based）
    
    返回:
        论文信息字典
    """
    if start_page_idx >= len(pages) or end_page_idx >= len(pages):
        logger.error(f"页码范围超出范围: {start_page_idx}-{end_page_idx}, 总页数: {len(pages)}")
        return {}
    
    first_page = pages[start_page_idx]
    last_page = pages[end_page_idx]
    
    # 初始化结果
    result = {
        'title': '',
        'authors': '',
        'first_author': '',
        'corresponding': '',
        'doi': '',
        'manuscript_id': '',
        'issue': '',
        'page_start': None,
        'page_end': None,
        'chinese_title': '',
        'chinese_authors': '',
        'abstract': '',
        'keywords': '',
        'citation': '',
        'is_dhu': False
    }
    
    # 1. 提取期刊期号：第一页第一个header的content
    # 格式应为：2025, 42(3) 这种格式
    # 支持格式：
    # - 标准格式：2025, 42(3)
    # - 英文格式：Journal of Donghua University (Eng. Ed.) Vol. 42, No. 3 (2025)
    for element in first_page:
        if element.get('type') == 'header':
            issue_raw = element.get('content', '').strip()
            # 确保格式为：年份, 卷号(期号)
            # 如果已经是正确格式，直接使用；否则尝试格式化
            if re.match(r'^\d{4},\s*\d+\(\d+\)', issue_raw):
                result['issue'] = issue_raw
            else:
                # 尝试匹配英文格式：Vol. 42, No. 3 (2025) 或类似格式
                # 匹配模式：Vol. 卷号, No. 期号 (年份) 或 Vol. 卷号 No. 期号 (年份)
                english_match = re.search(r'Vol\.\s*(\d+)[,\s]+No\.\s*(\d+)\s*\((\d{4})\)', issue_raw, re.I)
                if english_match:
                    volume, number, year = english_match.groups()
                    result['issue'] = f"{year}, {volume}({number})"
                    logger.info(f"从英文格式提取期刊期号: {issue_raw} -> {result['issue']}")
                else:
                    # 尝试提取年份、卷号、期号并格式化（中文格式）
                    # 匹配格式如：2025, 42(3) 或 2025,42(3) 或 2025 42(3) 等
                    match = re.search(r'(\d{4})[,\s]+(\d+)[\(（](\d+)[\)）]', issue_raw)
                    if match:
                        year, volume, number = match.groups()
                        result['issue'] = f"{year}, {volume}({number})"
                    else:
                        # 如果无法匹配，使用原始内容
                        result['issue'] = issue_raw
            logger.info(f"提取期刊期号: {result['issue']}")
            break
    
    # 2. 提取起始页码：第一页第一个page_number的content
    for element in first_page:
        if element.get('type') == 'page_number':
            page_num_str = element.get('content', '').strip()
            try:
                result['page_start'] = int(page_num_str)
                logger.info(f"提取起始页码: {result['page_start']}")
            except ValueError:
                logger.warning(f"无法解析起始页码: {page_num_str}")
            break
    
    # 3. 提取结束页码：最后一页最后一个page_number的content
    page_numbers = [e for e in last_page if e.get('type') == 'page_number']
    if page_numbers:
        last_page_num_str = page_numbers[-1].get('content', '').strip()
        try:
            result['page_end'] = int(last_page_num_str)
            logger.info(f"提取结束页码: {result['page_end']}")
        except ValueError:
            logger.warning(f"无法解析结束页码: {last_page_num_str}")
            # 如果没有，使用起始页+页数计算
            if result['page_start']:
                result['page_end'] = result['page_start'] + (end_page_idx - start_page_idx)
    else:
        # 如果没有找到，使用起始页+页数计算
        if result['page_start']:
            result['page_end'] = result['page_start'] + (end_page_idx - start_page_idx)
    
    # 4. 提取DOI：第一页第二个header的content（包含"DOI:"的）
    header_count = 0
    for element in first_page:
        if element.get('type') == 'header':
            header_count += 1
            if header_count == 2:  # 第二个header
                content = element.get('content', '')
                if 'DOI:' in content or 'doi:' in content.lower():
                    result['doi'] = extract_doi_from_header(content)
                    logger.info(f"提取DOI: {result['doi']}")
                    if result['doi']:
                        result['manuscript_id'] = doi_to_manuscript_id(result['doi'])
                    break
    
    # 5. 提取标题：第一页第一个title的content
    for element in first_page:
        if element.get('type') == 'title':
            result['title'] = element.get('content', '').strip()
            logger.info(f"提取标题: {result['title'][:50]}...")
            break
    
    # 6. 提取作者：第一页第一个title之后第一个text的content
    found_title = False
    for element in first_page:
        if element.get('type') == 'title':
            found_title = True
            continue
        if found_title and element.get('type') == 'text':
            authors_raw = element.get('content', '').strip()
            logger.info(f"提取作者: {authors_raw[:50]}...")
            # 清理和格式化英文作者
            # 要求：删除除了*以外的所有特殊字符，还要删除数字
            # 保留：字母、空格、逗号、*号
            if authors_raw:
                # 统一逗号格式
                authors_clean = authors_raw.replace(';', ',')
                # 统一逗号周围的空格
                authors_clean = re.sub(r'\s*,\s*', ', ', authors_clean)
                # 删除数字和除了*以外的所有特殊字符
                # 保留：字母（a-zA-Z）、空格、逗号、*号
                authors_clean = re.sub(r'[^a-zA-Z\s,*]', '', authors_clean)
                # 清理多余空格
                authors_clean = re.sub(r'\s+', ' ', authors_clean).strip()
                result['authors'] = authors_clean
                
                # 提取第一作者
                if result['authors']:
                    # 按逗号分割
                    if ',' in result['authors']:
                        result['first_author'] = result['authors'].split(',')[0].strip()
                    else:
                        # 如果没有逗号，取前两个词作为第一作者
                        parts = result['authors'].split()
                        if len(parts) >= 2:
                            result['first_author'] = ' '.join(parts[:2])
                        else:
                            result['first_author'] = result['authors']
            break
    
    # 7. 提取通讯作者：遍历所有页的page_footnote
    result['corresponding'] = extract_corresponding_from_footnotes(pages, start_page_idx, end_page_idx)
    if result['corresponding']:
        logger.info(f"提取通讯作者: {result['corresponding']}")
    
    # 8. 提取摘要：第一页中content以"Abstract:"或"Abstract："开头的text元素
    for element in first_page:
        if element.get('type') == 'text':
            content = element.get('content', '')
            if content.strip().startswith('Abstract:') or content.strip().startswith('Abstract：'):
                # 提取冒号后的内容
                abstract_text = re.sub(r'^Abstract\s*[:：]\s*', '', content, flags=re.I).strip()
                result['abstract'] = abstract_text
                logger.info(f"提取摘要: {result['abstract'][:50]}...")
                break
    
    # 9. 提取关键词：第一页中content以"Keywords:"或"Keywords："开头的text元素
    for element in first_page:
        if element.get('type') == 'text':
            content = element.get('content', '')
            if content.strip().startswith('Keywords:') or content.strip().startswith('Keywords：'):
                # 提取冒号后的内容
                keywords_text = re.sub(r'^Keywords\s*[:：]\s*', '', content, flags=re.I).strip()
                result['keywords'] = keywords_text
                logger.info(f"提取关键词: {result['keywords']}")
                break
    
    # 10. 提取Citations：查找以"Citation:"开头的page_footnote
    result['citation'] = extract_citations_from_footnotes(pages, start_page_idx, end_page_idx)
    if result['citation']:
        logger.info(f"提取Citations: {result['citation'][:50]}...")
    
    # 11. 提取中文标题：最后一页第一个title的content
    for element in last_page:
        if element.get('type') == 'title':
            result['chinese_title'] = element.get('content', '').strip()
            logger.info(f"提取中文标题: {result['chinese_title'][:50]}...")
            break
    
    # 12. 提取中文作者：最后一页第一个title之后第一个text的content
    found_chinese_title = False
    for element in last_page:
        if element.get('type') == 'title':
            found_chinese_title = True
            continue
        if found_chinese_title and element.get('type') == 'text':
            chinese_authors_raw = element.get('content', '').strip()
            # 清理和格式化中文作者
            # 要求：删除除了*以外的所有特殊字符，还要删除数字
            # 保留：中文字符、字母、逗号、空格、*号
            if chinese_authors_raw:
                # 统一逗号格式
                chinese_authors = chinese_authors_raw.replace('，', ',').replace(';', ',')
                # 统一逗号周围的空格
                chinese_authors = re.sub(r'\s*,\s*', ', ', chinese_authors)
                # 删除数字和除了*以外的所有特殊字符
                # 保留：中文字符（\u4e00-\u9fff）、字母（a-zA-Z）、空格、逗号、*号
                chinese_authors = re.sub(r'[^\u4e00-\u9fffa-zA-Z\s,*]', '', chinese_authors)
                # 处理两字人名中间的空格
                chinese_authors = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', chinese_authors)
                # 清理多余空格
                chinese_authors = re.sub(r'\s+', ' ', chinese_authors).strip()
                result['chinese_authors'] = chinese_authors
                logger.info(f"提取中文作者: {result['chinese_authors']}")
            break
    
    # 13. 判断是否东华大学
    full_text = ' '.join([e.get('content', '') for page in pages[start_page_idx:end_page_idx+1] 
                         for e in page if e.get('content')])
    result['is_dhu'] = 'donghua university' in full_text.lower() or '东华大学' in full_text
    
    return result


def extract_images_from_paper(pdf_path: str, paper_page_range: tuple, output_dir: str, start_page_offset: int = 0) -> Dict[str, Optional[str]]:
    """
    从论文页面范围提取第一张和第二张图片（保留原有逻辑，从PDF提取）
    
    参数:
        pdf_path: PDF文件路径
        paper_page_range: (start_page, end_page) 期刊页码范围
        output_dir: 输出目录
        start_page_offset: 期刊起始页码与PDF第一页的偏移量
    
    返回:
        包含两张图片路径的字典 {'first_image': 路径, 'second_image': 路径}
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF未安装，请运行: pip install PyMuPDF")
        return {'first_image': None, 'second_image': None}
    
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    image_paths = {'first_image': None, 'second_image': None}
    extracted_count = 0
    
    journal_start_page = paper_page_range[0]
    journal_end_page = paper_page_range[1]
    pdf_start_index = journal_start_page - start_page_offset - 1
    pdf_end_index = journal_end_page - start_page_offset - 1
    
    for pdf_page_index in range(pdf_start_index, pdf_end_index + 1):
        if pdf_page_index < 0 or pdf_page_index >= len(doc):
            continue
        
        page = doc[pdf_page_index]
        image_list = page.get_images()
        journal_page_num = pdf_page_index + start_page_offset + 1
        
        if image_list and extracted_count < 2:
            for img_index, img in enumerate(image_list[:2]):
                if extracted_count >= 2:
                    break
                
                try:
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha == 4:  # CMYK
                        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                        filename = f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image_QRcode.png" if extracted_count == 0 else f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image.png"
                        output_path = os.path.join(output_dir, filename)
                        pix_rgb.save(output_path)
                        if extracted_count == 0:
                            image_paths['first_image'] = output_path
                        else:
                            image_paths['second_image'] = output_path
                        pix_rgb = None
                        extracted_count += 1
                    elif pix.n - pix.alpha < 4:
                        filename = f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image_QRcode.png" if extracted_count == 0 else f"paper_{journal_start_page}-{journal_end_page}_page_{journal_page_num}_image.png"
                        output_path = os.path.join(output_dir, filename)
                        pix.save(output_path)
                        if extracted_count == 0:
                            image_paths['first_image'] = output_path
                        else:
                            image_paths['second_image'] = output_path
                        extracted_count += 1
                    
                    pix = None
                except Exception as e:
                    logger.error(f"提取图片失败: {str(e)}")
                    continue
        
        if extracted_count >= 2:
            break
    
    doc.close()
    return image_paths


def parse_pdf_from_mineru_json(model_json_path: str, pdf_path: str, journal_id: int, output_dir: str) -> List[Dict[str, Any]]:
    """
    基于MinerU JSON文件解析PDF
    
    参数:
        model_json_path: _model.json文件路径
        pdf_path: PDF文件路径（用于提取图片）
        journal_id: 期刊ID
        output_dir: 输出目录
    
    返回:
        论文记录列表
    """
    try:
        # 1. 加载JSON文件
        pages = load_model_json(model_json_path)
        if not pages:
            logger.error("无法加载JSON文件或文件为空")
            return []
        
        # 2. 查找所有包含DOI的页（识别论文起始页）
        doi_page_indices = find_papers_by_doi(pages)
        if not doi_page_indices:
            logger.warning("未找到包含DOI的页，无法识别论文")
            return []
        
        records = []
        
        # 3. 为每篇论文确定页码范围并提取信息
        for i, start_page_idx in enumerate(doi_page_indices):
            try:
                # 确定结束页索引
                if i < len(doi_page_indices) - 1:
                    # 不是最后一篇论文：结束页 = 下一篇论文起始页 - 1
                    end_page_idx = doi_page_indices[i + 1] - 1
                else:
                    # 最后一篇论文：结束页 = 最后一页
                    end_page_idx = len(pages) - 1
                
                logger.info(f"处理第 {i+1} 篇论文，页码范围: 第 {start_page_idx + 1} 页到第 {end_page_idx + 1} 页")
                
                # 4. 提取论文信息
                paper_info = extract_paper_info_from_json(pages, start_page_idx, end_page_idx)
                
                if not paper_info.get('page_start') or not paper_info.get('page_end'):
                    logger.warning(f"论文 {i+1} 缺少页码范围，跳过")
                    continue
                
                # 5. 提取图片
                paper_page_range = (paper_info['page_start'], paper_info['page_end'])
                image_paths = extract_images_from_paper(
                    pdf_path, 
                    paper_page_range, 
                    output_dir, 
                    paper_info['page_start'] - 1
                )
                
                # 6. 保存图片到本地
                local_storage_path = "images"
                os.makedirs(local_storage_path, exist_ok=True)
                
                first_local_path = None
                if image_paths['first_image'] and os.path.exists(image_paths['first_image']):
                    file_extension = Path(image_paths['first_image']).suffix.lower()
                    issue_clean = paper_info.get('issue', '').replace(',', '_').replace('(', '_').replace(')', '')
                    first_local_filename = f"papers_{issue_clean}_pages_{paper_info['page_start']}-{paper_info['page_end']}_image_QRcode{file_extension}"
                    first_local_path = os.path.join(local_storage_path, first_local_filename)
                    import shutil
                    shutil.copy2(image_paths['first_image'], first_local_path)
                    if not os.path.exists(first_local_path):
                        first_local_path = None
                
                second_local_path = None
                if image_paths['second_image'] and os.path.exists(image_paths['second_image']):
                    file_extension = Path(image_paths['second_image']).suffix.lower()
                    issue_clean = paper_info.get('issue', '').replace(',', '_').replace('(', '_').replace(')', '')
                    second_local_filename = f"papers_{issue_clean}_pages_{paper_info['page_start']}-{paper_info['page_end']}_image{file_extension}"
                    second_local_path = os.path.join(local_storage_path, second_local_filename)
                    import shutil
                    shutil.copy2(image_paths['second_image'], second_local_path)
                    if not os.path.exists(second_local_path):
                        second_local_path = None
                
                # 7. 构建论文记录
                record = {
                    "file_name": os.path.basename(pdf_path),
                    "pdf_pages": paper_info['page_end'] - paper_info['page_start'] + 1 if paper_info.get('page_end') and paper_info.get('page_start') else None,
                    "start_page": paper_info['page_start'],
                    "title": paper_info['title'],
                    "authors": paper_info['authors'],
                    "first_author": paper_info['first_author'],
                    "corresponding": paper_info['corresponding'],
                    "doi": paper_info['doi'],
                    "manuscript_id": paper_info['manuscript_id'],
                    "issue": paper_info['issue'],
                    "citation": paper_info['citation'],
                    "is_dhu": paper_info['is_dhu'],
                    "page_start": paper_info['page_start'],
                    "page_end": paper_info['page_end'],
                    "chinese_title": paper_info['chinese_title'],
                    "chinese_authors": paper_info['chinese_authors'],
                    "abstract": paper_info['abstract'],
                    "keywords": paper_info['keywords'],
                    "first_local_path": first_local_path,
                    "second_local_path": second_local_path,
                }
                
                records.append(record)
                logger.info(f"提取论文 {i+1}: {paper_info['title'][:50]}...")
                
            except Exception as e:
                logger.error(f"处理第 {i+1} 篇论文时出错: {str(e)}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
                continue
        
        if not records:
            logger.warning("未从JSON中提取到论文信息")
            return []
        
        logger.info(f"成功解析出 {len(records)} 篇论文")
        return records
        
    except Exception as e:
        logger.error(f"JSON解析失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return []


# 保持向后兼容的接口（但内部使用新的JSON解析）
def parse_pdf_to_papers(pdf_path: str, journal_id: int, output_dir: str) -> List[Dict[str, Any]]:
    """
    解析PDF文件（兼容接口）
    
    注意：此函数现在需要model_json_path参数，但为了兼容性保留此接口
    实际应该调用parse_pdf_from_mineru_json
    """
    logger.warning("parse_pdf_to_papers已废弃，请使用parse_pdf_from_mineru_json")
    return []
