"""
PDF解析服务 - 基于MinerU _content_list.json文件
适配新版MinerU输出的 content_list.json 格式
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


def load_content_list_json(json_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """
    加载并解析 _content_list.json 文件，按 page_idx 分组

    参数:
        json_path: _content_list.json 文件路径

    返回:
        Dict[int, List[Dict]]  key=page_idx, value=该页所有元素列表
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.error(f"JSON文件格式错误：期望数组，得到 {type(data)}")
            return {}

        grouped = defaultdict(list)
        for elem in data:
            page_idx = elem.get('page_idx', 0)
            grouped[page_idx].append(elem)

        # 按 page_idx 排序
        sorted_grouped = dict(sorted(grouped.items()))
        logger.info(f"成功加载JSON文件，共 {len(data)} 个元素，{len(sorted_grouped)} 页")
        return sorted_grouped
    except FileNotFoundError:
        logger.error(f"JSON文件不存在: {json_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"JSON文件解析失败: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"加载JSON文件失败: {str(e)}")
        return {}


def find_papers_by_doi(pages_dict: Dict[int, List[Dict[str, Any]]]) -> List[int]:
    """
    通过DOI识别论文起始页的 page_idx

    参数:
        pages_dict: 页分组字典（从load_content_list_json返回）

    返回:
        论文起始 page_idx 列表（按出现顺序）
    """
    doi_page_indices = []

    # 遍历所有页的 header 和 text 元素
    for page_idx, elements in sorted(pages_dict.items()):
        for element in elements:
            if element.get('type') in ('header', 'text'):
                text = element.get('text', '')
                if re.search(r'DOI\s*:', text, re.I):
                    doi_page_indices.append(page_idx)
                    logger.info(f"发现DOI页 page_idx={page_idx}, 内容: {text[:60]}...")
                    break

    logger.info(f"共发现 {len(doi_page_indices)} 篇论文（DOI页）")
    return doi_page_indices


def extract_doi_from_text(text: str) -> Optional[str]:
    """
    从文本中提取DOI

    参数:
        text: 包含DOI的文本

    返回:
        DOI字符串，如 "10.19884/j.1672-5220.202504002"
    """
    # 兼容带空格的 DOI，如 "DOI: 10.19884 / j.1672-5220.202504002"
    # 也兼容 "10.19884/j.1672-5220.2025-02001" 这种末尾有连字符的形式
    match = re.search(r'10\.19884\s*/?\s*j\s*/?\s*[\w\-\./]+', text, re.I)
    if match:
        doi = match.group(0)
        doi = clean_doi(doi)
        return doi if doi else None
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
    doi = clean_doi(doi)
    match = re.search(r'\.(\d+)$', doi)
    if not match:
        return None
    tail = match.group(1)
    year = tail[:4]
    seq = tail[4:] or '0000'
    return f"E{year}-{seq}"

def clean_doi(doi: str) -> str:
    """清理DOI中的空格、多余斜杠"""
    if not doi:
        return ''
    doi = re.sub(r'\s*/\s*', '/', doi)
    doi = re.sub(r'\s+', '', doi)
    doi = re.sub(r'^.*?10\.19884', '10.19884', doi, flags=re.I)
    # 末尾稿件号部分的连字符（如 2025-02001 → 202502001）
    # 只处理 "年份(4位)-序号(5位)" 的末尾形式，保留期刊编号中的连字符（如 1672-5220）
    doi = re.sub(r'(\d{4})-(\d{5})$', r'\1\2', doi)
    return doi


def extract_corresponding_from_footnotes(pages_dict: Dict[int, List[Dict[str, Any]]],
                                        start_page_idx: int,
                                        end_page_idx: int) -> str:
    """
    从page_footnote或footer中提取通讯作者

    参数:
        pages_dict: 页分组字典
        start_page_idx: 起始 page_idx
        end_page_idx: 结束 page_idx

    返回:
        通讯作者名称
    """
    supported_types = ['page_footnote', 'footer']

    for page_idx in range(start_page_idx, min(end_page_idx + 1, max(pages_dict.keys()) + 1)):
        elements = pages_dict.get(page_idx, [])
        for element in elements:
            element_type = element.get('type')
            if element_type in supported_types:
                content = element.get('text', '')
                if 'Correspondence should be addressed to' in content:
                    match = re.search(
                        r'Correspondence\s+should\s+be\s+addressed\s+to\s+([^,;，；\n]+)',
                        content,
                        re.I
                    )
                    if match:
                        return match.group(1).strip()
    return ""


def extract_citations_from_footnotes(pages_dict: Dict[int, List[Dict[str, Any]]],
                                     start_page_idx: int,
                                     end_page_idx: int) -> str:
    """
    提取Citations：查找以"Citation:"开头的page_footnote或footer元素，
    将该元素以及后续的所有page_footnote/footer元素提取并拼接

    参数:
        pages_dict: 页分组字典
        start_page_idx: 起始 page_idx
        end_page_idx: 结束 page_idx

    返回:
        拼接后的citations字符串
    """
    citations = []
    found_citation_start = False
    supported_types = ['page_footnote', 'footer']

    for page_idx in range(start_page_idx, min(end_page_idx + 1, max(pages_dict.keys()) + 1)):
        elements = pages_dict.get(page_idx, [])

        for i, element in enumerate(elements):
            element_type = element.get('type')
            content = element.get('text', '')

            if element_type in supported_types and content.strip().startswith('Citation:'):
                found_citation_start = True
                citation_text = re.sub(r'^Citation\s*[:：]\s*', '', content, flags=re.I).strip()
                if citation_text:
                    citations.append(citation_text)

                for j in range(i + 1, len(elements)):
                    next_element = elements[j]
                    next_element_type = next_element.get('type')
                    if next_element_type in supported_types:
                        next_content = next_element.get('text', '').strip()
                        if next_content:
                            citations.append(next_content)
                    else:
                        break
                break
            # 处理 Citation 缺失冒号的情况，如 "Citation ZHU Z X..."
            elif element_type in supported_types and re.match(r'^Citation\s+[A-Z]', content, re.I):
                found_citation_start = True
                citation_text = re.sub(r'^Citation\s+', '', content, flags=re.I).strip()
                if citation_text:
                    citations.append(citation_text)

                for j in range(i + 1, len(elements)):
                    next_element = elements[j]
                    next_element_type = next_element.get('type')
                    if next_element_type in supported_types:
                        next_content = next_element.get('text', '').strip()
                        if next_content:
                            citations.append(next_content)
                    else:
                        break
                break
            elif found_citation_start and element_type not in supported_types:
                break

    return ' '.join(citations) if citations else ""


def extract_images_from_json(pages_dict: Dict[int, List[Dict[str, Any]]],
                             start_page_idx: int,
                             end_page_idx: int) -> List[Dict[str, Any]]:
    """
    从JSON中提取指定页码范围内的图片元素

    参数:
        pages_dict: 页分组字典
        start_page_idx: 起始 page_idx
        end_page_idx: 结束 page_idx

    返回:
        图片元素列表（每个元素含 img_path）
    """
    images = []
    for page_idx in range(start_page_idx, min(end_page_idx + 1, max(pages_dict.keys()) + 1)):
        elements = pages_dict.get(page_idx, [])
        for element in elements:
            if element.get('type') == 'image':
                images.append(element)
    return images


def extract_paper_info_from_json(pages_dict: Dict[int, List[Dict[str, Any]]],
                                 start_page_idx: int,
                                 end_page_idx: int,
                                 output_dir: str = '') -> Dict[str, Any]:
    """
    从指定页码范围提取论文信息

    参数:
        pages_dict: 页分组字典（从load_content_list_json返回）
        start_page_idx: 起始 page_idx（论文"第一页"的 page_idx，即DOI所在页）
        end_page_idx: 结束 page_idx

    返回:
        论文信息字典
    """
    if start_page_idx not in pages_dict:
        logger.error(f"起始页 page_idx={start_page_idx} 不存在")
        return {}

    first_page_elements = pages_dict[start_page_idx]
    last_page_elements = pages_dict.get(end_page_idx, first_page_elements)

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
        'is_dhu': False,
        'first_image_path': '',
        'second_image_path': '',
    }

    # ========== DOI ==========
    doi_found = False
    for element in first_page_elements:
        if element.get('type') in ('header', 'text'):
            text = element.get('text', '')
            if re.search(r'DOI\s*:', text, re.I):
                result['doi'] = extract_doi_from_text(text)
                if result['doi']:
                    result['manuscript_id'] = doi_to_manuscript_id(result['doi'])
                logger.info(f"提取DOI: {result['doi']}")
                doi_found = True
                break

    # ========== 起始页 page_start（真实期刊页码）==========
    # 论文"第一页"（page_idx=start_page_idx）上的 page_number 元素即为起始页码
    for element in first_page_elements:
        if element.get('type') == 'page_number':
            page_num_str = element.get('text', '').strip()
            try:
                result['page_start'] = int(page_num_str)
                logger.info(f"提取起始页码（page_start）: {result['page_start']}")
            except ValueError:
                logger.warning(f"无法解析起始页码: {page_num_str}")
            break

    # ========== 结束页 page_end ==========
    page_numbers = [e for e in last_page_elements if e.get('type') == 'page_number']
    if page_numbers:
        last_page_num_str = page_numbers[-1].get('text', '').strip()
        try:
            result['page_end'] = int(last_page_num_str)
            logger.info(f"提取结束页码（page_end）: {result['page_end']}")
        except ValueError:
            if result['page_start']:
                result['page_end'] = result['page_start'] + (end_page_idx - start_page_idx)
    else:
        if result['page_start']:
            result['page_end'] = result['page_start'] + (end_page_idx - start_page_idx)

    # ========== issue（期刊期号）==========
    # 在论文"第一页"的 header 元素中匹配 Vol. 格式
    for element in first_page_elements:
        if element.get('type') == 'header':
            text = element.get('text', '').strip()
            match = re.search(r'Vol\.\s*(\d+)\s*[,.]?\s*No?\.\s*(\d+)', text, re.I)
            if match:
                volume, number = match.groups()
                year_match = re.search(r'Vol\.\s*\d+\s*[,.]?\s*No?\.\s*\d+\s*\((\d{4})\)', text, re.I)
                if year_match:
                    year = year_match.group(1)
                else:
                    year_match = re.search(r'\b(20\d{2})\b', text)
                    year = year_match.group(1) if year_match else ''
                result['issue'] = f"{year}, {volume}({number})" if year else f"{volume}({number})"
                logger.info(f"提取期刊期号: {result['issue']}")
                break
            match2 = re.search(r'(\d{4}),?\s*(\d+)\s*\((\d+)\)', text)
            if match2 and not result['issue']:
                year, vol, num = match2.groups()
                result['issue'] = f"{year}, {vol}({num})"
                logger.info(f"提取期刊期号: {result['issue']}")
                break

    # ========== title（英文标题）==========
    # DOI所在页的第一个 text_level=1 的 text 元素
    for element in first_page_elements:
        if element.get('type') == 'text' and element.get('text_level') == 1:
            result['title'] = element.get('text', '').strip()
            logger.info(f"提取英文标题: {result['title'][:50]}...")
            break

    # ========== authors（英文作者）==========
    # title 之后第一个 text 元素
    found_title = False
    for element in first_page_elements:
        if element.get('type') == 'text' and element.get('text_level') == 1:
            found_title = True
            continue
        if found_title and element.get('type') == 'text':
            authors_raw = element.get('text', '').strip()
            if authors_raw:
                # 预处理：移除 LaTeX 数学格式，如 ${ \mathrm{Yu} }^{1}、^{2}、_{1} 等
                authors_clean = re.sub(r'\$\{[^}]*\\mathrm\{([^}]+)\}[^}]*\}\s*\^?\{[^}]*\}', r'\1', authors_raw)
                authors_clean = re.sub(r'\$\{[^}]*\}', '', authors_clean)
                authors_clean = re.sub(r'\^{[^}]+}', '', authors_clean)
                authors_clean = re.sub(r'_{+[^}]+}', '', authors_clean)
                authors_clean = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', authors_clean)
                authors_clean = re.sub(r'\\[a-zA-Z]+', '', authors_clean)

                # 通用清理
                authors_clean = authors_clean.replace(';', ',')
                authors_clean = re.sub(r'\s*,\s*', ', ', authors_clean)

                # 保留 a-zA-Z、空格、逗号，以及星号 ∗ 和标准星号 *
                # 先把 ∗ 临时替换为占位符，避免被 [^...] 误删
                authors_clean = authors_clean.replace('∗', '⟨STAR⟩')
                authors_clean = authors_clean.replace('*', '⟨STAR⟩')
                authors_clean = re.sub(r'[^a-zA-Z\s,⟨STAR⟩]', '', authors_clean)
                authors_clean = authors_clean.replace('⟨STAR⟩', '∗')

                # 移除末尾逗号（可能连着星号，如 ", ∗" 或 ","）
                authors_clean = re.sub(r'\s*,+\s*$', '', authors_clean)
                # 清理末尾孤立的 ∗
                authors_clean = re.sub(r'\s*∗\s*$', '', authors_clean)
                # 再次清理末尾逗号
                authors_clean = re.sub(r'\s*,+\s*$', '', authors_clean)
                # 移除末尾的数字上标（ affiliations 编号），但保留星号
                # 如 "ZHANG Xuan2∗" → "ZHANG Xuan∗"，"LI Wang1∗" → "LI Wang∗"
                authors_clean = re.sub(r'\s+\d+(∗)\s*$', r' \1', authors_clean)
                authors_clean = re.sub(r'\s+', ' ', authors_clean).strip()

                result['authors'] = authors_clean

                if result['authors']:
                    if ',' in result['authors']:
                        result['first_author'] = result['authors'].split(',')[0].strip()
                    else:
                        parts = result['authors'].split()
                        if len(parts) >= 2:
                            result['first_author'] = ' '.join(parts[:2])
                        else:
                            result['first_author'] = result['authors']
            break

    # ========== corresponding（通讯作者）==========
    result['corresponding'] = extract_corresponding_from_footnotes(pages_dict, start_page_idx, end_page_idx)
    if result['corresponding']:
        logger.info(f"提取通讯作者: {result['corresponding']}")

    # ========== abstract（摘要）==========
    for element in first_page_elements:
        if element.get('type') == 'text':
            content = element.get('text', '')
            if content.strip().startswith('Abstract:') or content.strip().startswith('Abstract：'):
                abstract_text = re.sub(r'^Abstract\s*[:：]\s*', '', content, flags=re.I).strip()
                result['abstract'] = abstract_text
                logger.info(f"提取摘要: {result['abstract'][:50]}...")
                break

    # ========== keywords（关键词）==========
    for element in first_page_elements:
        if element.get('type') == 'text':
            content = element.get('text', '')
            if content.strip().startswith('Keywords:') or content.strip().startswith('Keywords：'):
                keywords_text = re.sub(r'^Keywords\s*[:：]\s*', '', content, flags=re.I).strip()
                result['keywords'] = keywords_text
                logger.info(f"提取关键词: {result['keywords']}")
                break

    # ========== citation（引用格式）==========
    result['citation'] = extract_citations_from_footnotes(pages_dict, start_page_idx, end_page_idx)
    if result['citation']:
        logger.info(f"提取Citation: {result['citation'][:50]}...")

    # ========== 中文标题和中文作者（最后一页）==========
    found_chinese_title = False
    for element in last_page_elements:
        if element.get('type') == 'text' and element.get('text_level') == 1:
            result['chinese_title'] = element.get('text', '').strip()
            logger.info(f"提取中文标题: {result['chinese_title'][:50]}...")
            found_chinese_title = True
            continue
        if found_chinese_title and element.get('type') == 'text':
            chinese_authors_raw = element.get('text', '').strip()
            if chinese_authors_raw:
                chinese_authors = chinese_authors_raw.replace('，', ',').replace(';', ',')
                chinese_authors = re.sub(r'\s*,\s*', ', ', chinese_authors)
                # 保留星号 ∗ 和 *
                chinese_authors = chinese_authors.replace('∗', '⟨STAR⟩')
                chinese_authors = chinese_authors.replace('*', '⟨STAR⟩')
                chinese_authors = re.sub(r'[^\u4e00-\u9fffa-zA-Z\s,⟨STAR⟩]', '', chinese_authors)
                chinese_authors = chinese_authors.replace('⟨STAR⟩', '∗')
                chinese_authors = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', chinese_authors)
                # 移除末尾逗号和孤立星号
                chinese_authors = re.sub(r'\s*,+\s*$', '', chinese_authors)
                chinese_authors = re.sub(r'\s*∗\s*$', '', chinese_authors)
                chinese_authors = re.sub(r'\s*,+\s*$', '', chinese_authors)
                # 移除末尾的数字上标（ affiliations 编号），但保留星号
                chinese_authors = re.sub(r'\s+\d+(∗)\s*$', r' \1', chinese_authors)
                chinese_authors = re.sub(r'\s+', ' ', chinese_authors).strip()
                result['chinese_authors'] = chinese_authors
                logger.info(f"提取中文作者: {result['chinese_authors']}")
            break

    # ========== 东华大学标记 ==========
    all_text = ' '.join([
        e.get('text', '')
        for elements in pages_dict.values()
        for e in elements
        if e.get('text')
    ])
    result['is_dhu'] = 'donghua university' in all_text.lower() or '东华大学' in all_text

    # ========== 图片路径（取前两张，存储相对路径）==========
    images = extract_images_from_json(pages_dict, start_page_idx, end_page_idx)
    if len(images) >= 1:
        result['first_image_path'] = images[0].get('img_path', '')  # 相对路径，如 images/xxx.jpg
    if len(images) >= 2:
        result['second_image_path'] = images[1].get('img_path', '')  # 相对路径

    return result


def parse_pdf_from_mineru_json(content_list_json_path: str, pdf_path: str, journal_id: int, output_dir: str, mineru_folder: str = None) -> List[Dict[str, Any]]:
    """
    基于MinerU _content_list.json文件解析PDF

    参数:
        content_list_json_path: _content_list.json 文件路径
        pdf_path: PDF文件路径（用于提取图片，已废弃，改用JSON中的img_path）
        journal_id: 期刊ID
        output_dir: 输出目录
        mineru_folder: MinerU输出文件夹名（如 DHDY202602-四排_1777374343），用于定位图片

    返回:
        论文记录列表
    """
    try:
        # 1. 加载JSON文件（按page_idx分组）
        pages_dict = load_content_list_json(content_list_json_path)
        if not pages_dict:
            logger.error("无法加载JSON文件或文件为空")
            return []

        # 2. 查找所有包含DOI的页（识别论文起始页）
        doi_page_indices = find_papers_by_doi(pages_dict)
        if not doi_page_indices:
            logger.warning("未找到包含DOI的页，无法识别论文")
            return []

        all_page_indices = sorted(pages_dict.keys())
        max_page_idx = max(all_page_indices) if all_page_indices else 0

        records = []

        # 3. 为每篇论文确定页码范围并提取信息
        for i, start_page_idx in enumerate(doi_page_indices):
            try:
                # 确定结束页索引
                if i < len(doi_page_indices) - 1:
                    end_page_idx = doi_page_indices[i + 1] - 1
                else:
                    end_page_idx = max_page_idx

                logger.info(f"处理第 {i+1} 篇论文，page_idx范围: {start_page_idx} 到 {end_page_idx}")

                # 4. 提取论文信息
                paper_info = extract_paper_info_from_json(pages_dict, start_page_idx, end_page_idx, output_dir)

                if not paper_info.get('page_start') or not paper_info.get('page_end'):
                    logger.warning(f"论文 {i+1} 缺少页码范围，跳过")
                    continue

                # 5. 构建论文记录
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
                    "first_image_path": paper_info.get('first_image_path', ''),
                    "second_image_path": paper_info.get('second_image_path', ''),
                    "mineru_folder": mineru_folder,
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


# 保持向后兼容的接口
def parse_pdf_to_papers(pdf_path: str, journal_id: int, output_dir: str) -> List[Dict[str, Any]]:
    """
    解析PDF文件（兼容接口，已废弃）
    """
    logger.warning("parse_pdf_to_papers已废弃，请使用parse_pdf_from_mineru_json")
    return []
