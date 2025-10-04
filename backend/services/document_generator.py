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
    生成目录Word文档 - 完全照搬参考代码实现
    """
    try:
        # 创建Word文档
        doc = Document()
        
        # 设置样式 - 完全按照参考代码
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.font.size = Pt(11)
        
        # 按页码排序 - 完全按照参考代码逻辑
        items = sorted([a for a in papers if _get(a, 'page_start') is not None], 
                      key=lambda x: _get(x, 'page_start'))
        
        # 添加内容 - 完全按照参考代码格式
        for a in items:
            doc.add_paragraph(f"{_get(a,'page_start')} {_get(a,'title') or ''}")
            doc.add_paragraph(_get(a, 'authors') or '')
        
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
    生成统计表Excel - 完全照搬参考代码实现
    """
    try:
        # 完全照搬参考代码的Excel生成逻辑
        wb = Workbook()
        ws = wb.active
        ws.title = '校内'
        headers = ['稿件号','页数','一作','通讯','刊期','是否东华大学']
        ws.append([None])
        ws.append(headers)

        col_pos = {name: idx+1 for idx, name in enumerate(headers)}
        r = 3
        maxr = ws.max_row
        if maxr >= r:
            for row in ws.iter_rows(min_row=r, max_row=maxr):
                for cell in row: cell.value = None

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


