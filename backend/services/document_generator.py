import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional
import logging

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from openpyxl import Workbook

logger = logging.getLogger(__name__)

def _get(a: Any, key: str):
    """获取对象属性，兼容dict和object - 完全照搬参考代码"""
    if isinstance(a, dict): 
        return a.get(key)
    return getattr(a, key)

def format_authors_for_citation(authors: str, max_authors: int = 3) -> str:
    """
    格式化作者信息用于citation
    规则：
    1. 最多显示3个作者
    2. 作者的名只取首字母（如 "HUANG Jiacui" -> "HUANG J"）
    3. 如果超过3个作者，在第三个作者后加上 ", et al."
    
    示例：
    - "HUANG Jiacui, ZHAO Mingbo, ZHANG Hongtao, WANG Li" 
      -> "HUANG J, ZHAO M, ZHANG H, et al."
    - "HUANG Jiacui, ZHAO Mingbo, ZHANG Hongtao" 
      -> "HUANG J, ZHAO M, ZHANG H"
    """
    if not authors:
        return ""
    
    # 分割作者（支持逗号或中文逗号分隔）
    author_list = [a.strip() for a in re.split(r'[,，]', authors) if a.strip()]
    
    if not author_list:
        return ""
    
    # 格式化每个作者：名字只取首字母
    formatted_authors = []
    for author in author_list[:max_authors]:
        # 分割姓和名（通常格式：姓 名，如 "HUANG Jiacui"）
        parts = author.split()
        if len(parts) >= 2:
            # 有姓和名：姓 + 名的首字母
            last_name = parts[0]
            first_name = parts[1]
            formatted_author = f"{last_name} {first_name[0] if first_name else ''}"
            formatted_authors.append(formatted_author.strip())
        else:
            # 只有一个部分，可能是只有姓或者格式不对，保持原样
            formatted_authors.append(author)
    
    # 如果超过max_authors个作者，添加 ", et al."
    if len(author_list) > max_authors:
        formatted_authors.append("et al.")
    
    # 用逗号和空格连接
    return ", ".join(formatted_authors)

def generate_toc_docx(papers: List[Any], journal: Any) -> str:
    """
    生成目录Word文档 - 导出期刊内所有论文
    """
    try:
        # 创建Word文档
        doc = Document()
        
        # 设置样式
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 添加期刊标题
        title_para = doc.add_paragraph()
        title_run = title_para.runs[0] if title_para.runs else title_para.add_run()
        title_run.text = f"{journal.title} - {journal.issue}"
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        
        # 添加空行
        doc.add_paragraph()
        
        # 按页码排序
        items = sorted([a for a in papers if _get(a, 'page_start') is not None], 
                      key=lambda x: _get(x, 'page_start'))
        
        # 添加目录内容
        for i, a in enumerate(items, 1):
            # 论文标题和页码
            doc.add_paragraph(f"{_get(a,'page_start')} {_get(a,'title') or ''}")
            # 作者信息
            doc.add_paragraph(_get(a, 'authors') or '')
            # 空行分隔
            if i < len(items):
                doc.add_paragraph()
        
        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"目录_{journal.issue}_{timestamp}.docx"
        output_path = os.path.join('uploads', filename)
        
        # 确保目录存在
        os.makedirs('uploads', exist_ok=True)
        
        doc.save(output_path)
        logger.info(f"目录文档已生成: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"生成目录文档失败: {str(e)}")
        raise Exception(f"生成目录文档失败: {str(e)}")

def generate_excel_stats(articles, journal) -> str:
    """
    生成统计表Excel - 导出期刊内所有论文的统计信息
    """
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = '期刊统计表'
        
        # 添加期刊信息标题
        ws.cell(row=1, column=1, value=f"{journal.title} - {journal.issue}")
        ws.cell(row=2, column=1, value=f"论文总数: {len(articles)}")
        ws.cell(row=3, column=1, value="")  # 空行
        
        # 表头
        headers = ['稿件号','页数','一作','通讯','刊期','是否东华大学']
        ws.append(headers)

        col_pos = {name: idx+1 for idx, name in enumerate(headers)}
        r = 5  # 从第5行开始（前面有标题）
        
        # 添加所有论文数据
        for a in articles:
            values = {
                '稿件号': _get(a, 'manuscript_id'),
                '页数': _get(a, 'pdf_pages'),
                '一作': _get(a, 'first_author'),
                '通讯': (_get(a, 'corresponding') or ''),
                '刊期': _get(a, 'issue'),
                '是否东华大学': '是' if _get(a, 'is_dhu') else '否',
            }
            for k, v in values.items():
                if k in col_pos:
                    ws.cell(row=r, column=col_pos[k], value=v)
            r += 1

        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"统计表_{journal.issue}_{timestamp}.xlsx"
        output_path = os.path.join('uploads', filename)
        
        os.makedirs('uploads', exist_ok=True)
        wb.save(output_path)
        
        logger.info(f"统计表已生成: {output_path}")
        
        # 记录生成的数据用于调试
        debug_data = []
        for a in articles:
            debug_data.append({
                '稿件号': _get(a, 'manuscript_id'),
                '页数': _get(a, 'pdf_pages'),
                '一作': _get(a, 'first_author'),
                '通讯': (_get(a, 'corresponding') or ''),
                '刊期': _get(a, 'issue'),
                '是否东华大学': '是' if _get(a, 'is_dhu') else '否'
            })
        logger.info(f"生成的数据: {debug_data}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"生成统计表Excel失败: {str(e)}")
        raise Exception(f"生成统计表Excel失败: {str(e)}")
def get_local_image_path(image_path: str, temp_dir: str) -> Optional[str]:
    """
    获取本地图片路径，如果图片存在则返回路径，否则返回None
    返回: 本地图片路径，如果图片不存在则返回None
    """
    try:
        # 检查图片路径是否存在
        if image_path and os.path.exists(image_path):
            logger.info(f"本地图片存在: {image_path}")
            return image_path
        else:
            logger.warning(f"本地图片不存在: {image_path}")
            return None
            
    except Exception as e:
        logger.error(f"检查本地图片时出错: {str(e)}")
        return None

def generate_tuiwen_content(papers, journal):
    """生成秀米推文内容 - Word文档格式"""
    try:
        # 创建临时目录用于存储下载的图片
        temp_dir = os.path.join('temp_images', datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(temp_dir, exist_ok=True)
        
        # 创建Word文档
        doc = Document()
        
        # 设置样式
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 获取当前日期
        current_date = datetime.now().strftime('%Y年%m月%d日')
        issue = journal.issue
        
        # 转换期刊号格式：从"2025,42(3)"转换为"2025年第42卷第3期"
        def convert_issue_format(issue_str):
            """
            将期刊号格式从"2025,42(3)"转换为"2025年第42卷第3期"
            支持多种可能的格式：
            - "2025,42(3)" -> "2025年第42卷第3期"
            - "2025,42(3-4)" -> "2025年第42卷第3-4期"
            - "2025,42(3,4)" -> "2025年第42卷第3-4期"
            """
            try:
                # 匹配格式：年份,卷号(期号)
                match = re.match(r'(\d{4}),\s*(\d+)\(([^)]+)\)', issue_str)
                if match:
                    year = match.group(1)  # 年份
                    volume = match.group(2)  # 卷号
                    issue_num = match.group(3)  # 期号
                    
                    # 处理期号中的特殊字符
                    issue_num = issue_num.replace(',', '-')  # 将逗号替换为连字符
                    
                    return f"{year}年第{volume}卷第{issue_num}期"
                else:
                    # 如果格式不匹配，返回原格式
                    logger.warning(f"无法解析期刊号格式: {issue_str}")
                    return issue_str
            except Exception as e:
                logger.error(f"转换期刊号格式失败: {str(e)}")
                return issue_str
        
        # 转换期刊号格式
        issue_info = convert_issue_format(issue)
        
        # 添加期刊标题
        title_para = doc.add_paragraph()
        title_run = title_para.runs[0] if title_para.runs else title_para.add_run()
        title_run.text = "东华大学学报"
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        title_run.font.color.rgb = None  # 黑色
        
        # 添加期刊号
        issue_para = doc.add_paragraph()
        issue_run = issue_para.runs[0] if issue_para.runs else issue_para.add_run()
        issue_run.text = issue_info
        issue_run.font.size = Pt(12)
        
        # 添加分隔线
        doc.add_paragraph("─" * 30)  # 使用字符作为分隔线
        
        # 添加编辑信息
        editor_para = doc.add_paragraph()
        editor_run = editor_para.runs[0] if editor_para.runs else editor_para.add_run()
        editor_run.text = f"本期责编: 编辑部 | {current_date}"
        editor_run.font.size = Pt(10)
        editor_run.font.italic = True
        
        # 添加空行
        doc.add_paragraph()
        
        # 添加论文内容
        for i, paper in enumerate(papers, 1):
            # 处理数据库Paper对象或字典
            if hasattr(paper, 'title'):
                # 数据库对象
                title = paper.title
                authors = paper.authors
                chinese_title = getattr(paper, 'chinese_title', '') or ''
                chinese_authors = getattr(paper, 'chinese_authors', '') or ''
                doi = paper.doi or ''
                page_start = paper.page_start
                page_end = paper.page_end
                # 获取图片URL
                first_image_url = getattr(paper, 'first_image_url', '') or ''
                second_image_url = getattr(paper, 'second_image_url', '') or ''
                # 格式化作者用于citation（最多3个，名字只取首字母）
                formatted_authors = format_authors_for_citation(authors, max_authors=3)
                # 生成引用信息
                citation = f"{formatted_authors}. {title} [J]. Journal of Donghua University (English Edition), 2025, 42(3): {page_start}-{page_end}."
            
            # 添加中文标题（如果有）
            if chinese_title:
                chinese_title_para = doc.add_paragraph()
                chinese_title_run = chinese_title_para.runs[0] if chinese_title_para.runs else chinese_title_para.add_run()
                chinese_title_run.text = f"{i}. {chinese_title}"
                chinese_title_run.font.size = Pt(12)
                chinese_title_run.font.bold = True
            
            # 添加中文作者（如果有）
            if chinese_authors:
                chinese_authors_para = doc.add_paragraph()
                chinese_authors_run = chinese_authors_para.runs[0] if chinese_authors_para.runs else chinese_authors_para.add_run()
                chinese_authors_run.text = chinese_authors
                chinese_authors_run.font.size = Pt(11)
            
            # 添加第二张图片（在中文标题和中文作者下面）
            if second_image_url:
                try:
                    logger.info(f"开始处理第二张图片: {second_image_url}")
                    # 获取本地图片路径
                    local_image_path = get_local_image_path(second_image_url, temp_dir)
                    logger.info(f"本地图片路径检查结果: {local_image_path}, 文件存在: {os.path.exists(local_image_path) if local_image_path else False}")
                    
                    if local_image_path and os.path.exists(local_image_path):
                        # 添加图片描述
                        # image_desc_para = doc.add_paragraph()
                        # image_desc_run = image_desc_para.runs[0] if image_desc_para.runs else image_desc_para.add_run()
                        # image_desc_run.text = "论文配图:"
                        # image_desc_run.font.size = Pt(10)
                        # image_desc_run.font.italic = True
                        
                        # 插入图片到Word文档 - 添加异常处理
                        try:
                            logger.info(f"尝试插入图片到Word: {local_image_path}")
                            doc.add_picture(local_image_path, width=Pt(300))  # 设置图片宽度为300磅
                            logger.info(f"✅ 为论文 {i} 成功插入第二张图片: {second_image_url}")
                        except Exception as picture_error:
                            logger.error(f"❌ 插入图片到Word失败: {str(picture_error)}")
                            # 如果插入失败，添加图片路径作为替代
                            url_para = doc.add_paragraph()
                            url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                            url_run.text = f"图片路径: {second_image_url}"
                            url_run.font.size = Pt(9)
                    else:
                        logger.warning(f"❌ 无法找到第二张图片: {second_image_url}")
                except Exception as img_error:
                    logger.error(f"❌ 处理第二张图片失败: {str(img_error)}")
            
            # 添加论文标题
            paper_title_para = doc.add_paragraph()
            paper_title_run = paper_title_para.runs[0] if paper_title_para.runs else paper_title_para.add_run()
            paper_title_run.text = title
            paper_title_run.font.size = Pt(12)
            paper_title_run.font.bold = True
            
            # 添加作者信息（去掉"作者："前缀）
            doc.add_paragraph(authors)
            
            # 添加DOI信息（保留"DOI："前缀）
            if doi:
                doc.add_paragraph(f"DOI: {doi}")
            
            # 添加引用信息（添加"Citation:"前缀，调整字体大小）
            citation_para = doc.add_paragraph()
            citation_run = citation_para.runs[0] if citation_para.runs else citation_para.add_run()
            citation_run.text = f"Citation: {citation}"
            citation_run.font.size = Pt(11)  # 调整字体大小和其他内容一样
            
            # 在论文版块最后添加"作者说链接/OSID"文字和第一张图片
            # 添加分隔线
            doc.add_paragraph("─" * 20)
            
            # 添加"作者说链接/OSID"文字
            osid_para = doc.add_paragraph()
            osid_run = osid_para.runs[0] if osid_para.runs else osid_para.add_run()
            osid_run.text = "作者说链接/OSID"
            osid_run.font.size = Pt(10)
            osid_run.font.bold = True
            
            # 添加第一张图片（QRcode）
            if first_image_url:
                try:
                    logger.info(f"开始处理第一张图片(QRcode): {first_image_url}")
                    # 获取本地图片路径
                    local_image_path = get_local_image_path(first_image_url, temp_dir)
                    logger.info(f"本地图片路径检查结果: {local_image_path}, 文件存在: {os.path.exists(local_image_path) if local_image_path else False}")
                    
                    if local_image_path and os.path.exists(local_image_path):
                        # 插入图片到Word文档 - 添加异常处理
                        try:
                            logger.info(f"尝试插入第一张图片到Word: {local_image_path}")
                            doc.add_picture(local_image_path, width=Pt(100))  # 设置较小的宽度用于二维码
                            logger.info(f"✅ 为论文 {i} 成功插入第一张图片(QRcode): {first_image_url}")
                        except Exception as picture_error:
                            logger.error(f"❌ 插入第一张图片到Word失败: {str(picture_error)}")
                            # 如果插入失败，添加图片路径作为替代
                            url_para = doc.add_paragraph()
                            url_run = url_para.runs[0] if url_para.runs else url_para.add_run()
                            url_run.text = f"二维码路径: {first_image_url}"
                            url_run.font.size = Pt(9)
                    else:
                        logger.warning(f"❌ 无法找到第一张图片(QRcode): {first_image_url}")
                except Exception as qrcode_error:
                    logger.error(f"❌ 处理第一张图片(QRcode)失败: {str(qrcode_error)}")
            
            # 添加空行分隔
            doc.add_paragraph()
        
        # 添加页脚信息
        doc.add_paragraph("─" * 30)  # 分隔线
        footer_para = doc.add_paragraph()
        footer_run = footer_para.runs[0] if footer_para.runs else footer_para.add_run()
        footer_run.text = "感谢您的阅读！欢迎引用本文内容"
        footer_run.font.size = Pt(10)
        
        copyright_para = doc.add_paragraph()
        copyright_run = copyright_para.runs[0] if copyright_para.runs else copyright_para.add_run()
        copyright_run.text = "© 2025 东华大学学报 版权所有"
        copyright_run.font.size = Pt(9)
        
        # 保存Word文档
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"推文_{journal.issue}_{timestamp}.docx"
        output_path = os.path.join('uploads', filename)
        
        # 确保目录存在
        os.makedirs('uploads', exist_ok=True)
        
        doc.save(output_path)
        logger.info(f"推文Word文档已生成: {output_path}")
        
        # 返回文件路径
        return output_path
    
    except Exception as e:
        logger.error(f"生成推文Word文档失败: {str(e)}")
        raise Exception(f"生成推文Word文档失败: {str(e)}")
