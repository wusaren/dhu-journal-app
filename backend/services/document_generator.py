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


