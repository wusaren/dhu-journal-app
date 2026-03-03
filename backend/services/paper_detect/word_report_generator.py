    #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word报告生成器模块

生成结构化的Word格式检测报告
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

from .report_styles import (
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_TABLE, FONT_TABLE_HEADER,
    FONT_SIZE_TITLE, FONT_SIZE_HEADING, FONT_SIZE_BODY, FONT_SIZE_TABLE, FONT_SIZE_TABLE_HEADER,
    MARGIN_TOP, MARGIN_BOTTOM, MARGIN_LEFT, MARGIN_RIGHT,
    SPACE_BEFORE_TITLE, SPACE_AFTER_TITLE, SPACE_BEFORE_HEADING, SPACE_AFTER_HEADING,
    SPACE_BEFORE_TABLE, SPACE_AFTER_TABLE,
    COLOR_TABLE_HEADER_BG, COLOR_TABLE_BORDER, COLOR_ERROR, COLOR_WARNING, COLOR_SUCCESS,
    TABLE_COLUMN_WIDTHS, TABLE_HEADERS, TABLE_BORDER_WIDTH,
    get_section_code, get_section_display_name, get_error_type_display, get_error_type_color, format_page_number, truncate_text
)
from .report_data_converter import ErrorEntry


class WordReportGenerator:
    """Word报告生成器"""
    
    def __init__(self):
        """初始化Word文档"""
        self.doc = Document()
        self._setup_document_styles()
        self.page_number_cache = {}
    
    def _setup_document_styles(self):
        """设置文档样式"""
        # 设置页边距
        sections = self.doc.sections
        for section in sections:
            section.top_margin = MARGIN_TOP
            section.bottom_margin = MARGIN_BOTTOM
            section.left_margin = MARGIN_LEFT
            section.right_margin = MARGIN_RIGHT
    
    def add_title(self, title: str = "论文格式检测综合报告"):
        """添加报告标题"""
        # 添加标题段落
        title_para = self.doc.add_paragraph()
        title_run = title_para.add_run(title)
        
        # 设置标题样式
        title_run.font.name = FONT_TITLE
        title_run.font.size = FONT_SIZE_TITLE
        title_run.font.bold = True
        title_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_TITLE)
        
        title_para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        title_para.space_before = SPACE_BEFORE_TITLE
        title_para.space_after = SPACE_AFTER_TITLE
        
        # 添加生成时间
        time_para = self.doc.add_paragraph()
        time_run = time_para.add_run(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        time_run.font.name = FONT_BODY
        time_run.font.size = FONT_SIZE_BODY
        time_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_BODY)
        
        time_para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        time_para.space_after = Pt(12)
    
    def add_summary(self, total_checks: int, passed_checks: int, failed_checks: int):
        """添加总体评估部分"""
        # 添加部分标题
        self.add_section("总体评估")
        
        # 计算通过率
        pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        # 添加统计信息
        stats_para = self.doc.add_paragraph()
        stats_para.space_after = Pt(6)
        
        # 总检测项数
        self._add_stat_line(stats_para, "总检测项数", str(total_checks))
        
        # 通过项数
        self._add_stat_line(stats_para, "通过项数", f"{passed_checks} ✓", COLOR_SUCCESS)
        
        # 失败项数
        self._add_stat_line(stats_para, "失败项数", f"{failed_checks} ✗", COLOR_ERROR)
        
        # 通过率
        pass_rate_text = f"{pass_rate:.1f}%"
        pass_rate_color = COLOR_SUCCESS if pass_rate >= 80 else (COLOR_WARNING if pass_rate >= 60 else COLOR_ERROR)
        self._add_stat_line(stats_para, "通过率", pass_rate_text, pass_rate_color)
        
        # 添加警告提示
        if pass_rate < 60:
            warning_para = self.doc.add_paragraph()
            warning_run = warning_para.add_run("⚠️ 警告: 通过率低于60%，建议重点关注失败项目")
            warning_run.font.color.rgb = COLOR_WARNING
            warning_run.font.bold = True
            warning_run.font.size = FONT_SIZE_BODY
            warning_run.font.name = FONT_BODY
            # 设置中文字体
            if warning_run._element.rPr is not None:
                warning_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_BODY)
            warning_para.space_after = Pt(12)
    
    def _add_stat_line(self, paragraph, label: str, value: str, color: RGBColor = None):
        """添加统计信息行"""
        # 添加标签
        label_run = paragraph.add_run(f"{label}: ")
        label_run.font.name = FONT_BODY
        label_run.font.size = FONT_SIZE_BODY
        label_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_BODY)
        
        # 添加值
        value_run = paragraph.add_run(value)
        value_run.font.name = FONT_BODY
        value_run.font.size = FONT_SIZE_BODY
        value_run.font.bold = True
        value_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_BODY)
        
        if color:
            value_run.font.color.rgb = color
        
        # 添加换行
        paragraph.add_run("\n")
    
    def add_section(self, section_name: str):
        """添加部分标题"""
        section_para = self.doc.add_paragraph()
        section_run = section_para.add_run(section_name)
        
        # 设置标题样式
        section_run.font.name = FONT_HEADING
        section_run.font.size = FONT_SIZE_HEADING
        section_run.font.bold = True
        section_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_HEADING)
        
        section_para.space_before = SPACE_BEFORE_HEADING
        section_para.space_after = SPACE_AFTER_HEADING
    
    def add_pass_message(self, section_name: str):
        """添加检测通过消息"""
        pass_para = self.doc.add_paragraph()
        pass_run = pass_para.add_run(f"✓ {section_name}检测通过")
        pass_run.font.name = FONT_BODY
        pass_run.font.size = FONT_SIZE_BODY
        pass_run.font.color.rgb = COLOR_SUCCESS
        pass_run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_BODY)
        pass_para.space_after = Pt(12)
    
    def add_error_table(self, errors: List[ErrorEntry]):
        """添加错误表格"""
        if not errors:
            return
        
        # 添加表格前间距
        spacer = self.doc.add_paragraph()
        spacer.space_before = SPACE_BEFORE_TABLE
        
        # 创建表格（6列，行数=表头+错误数）
        table = self.doc.add_table(rows=1 + len(errors), cols=6)
        table.style = 'Table Grid'
        
        # 创建表头
        self._create_table_header(table)
        
        # 添加错误行
        for i, error in enumerate(errors, 1):
            self._add_table_row(table, i, error)
        
        # 应用表格样式
        self._apply_table_style(table)
        
        # 添加表格后间距
        spacer = self.doc.add_paragraph()
        spacer.space_after = SPACE_AFTER_TABLE
    
    def _create_table_header(self, table):
        """创建表头"""
        header_row = table.rows[0]
        
        for i, header_text in enumerate(TABLE_HEADERS):
            cell = header_row.cells[i]
            cell.text = header_text
            
            # 设置表头样式
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                for run in paragraph.runs:
                    run.font.name = FONT_TABLE_HEADER
                    run.font.size = FONT_SIZE_TABLE_HEADER
                    run.font.bold = True
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_TABLE_HEADER)
            
            # 设置表头背景色
            self._set_cell_background(cell, COLOR_TABLE_HEADER_BG)
    
    def _add_table_row(self, table, row_index: int, error: ErrorEntry):
        """添加表格行"""
        row = table.rows[row_index]
        
        # 填充单元格数据
        cells_data = [
            error.error_id,
            get_error_type_display(error.error_type),
            format_page_number(error.page_number),
            error.description,
            error.suggestion,
            truncate_text(error.text_snippet, max_length=60)
        ]
        
        for i, data in enumerate(cells_data):
            cell = row.cells[i]
            cell.text = str(data)
            
            # 设置单元格样式
            for paragraph in cell.paragraphs:
                # 错误编号、类型、页码居中，其他左对齐
                if i < 3:
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                else:
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                
                for run in paragraph.runs:
                    run.font.name = FONT_TABLE
                    run.font.size = FONT_SIZE_TABLE
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_TABLE)
                    
                    # 错误类型列设置颜色
                    if i == 1:
                        run.font.color.rgb = get_error_type_color(error.error_type)
                        run.font.bold = True
    
    def _apply_table_style(self, table):
        """应用表格样式"""
        # 设置表格宽度为页面宽度
        table.autofit = False
        table.allow_autofit = False
        
        # 计算总宽度（页面宽度 - 左右边距）
        page_width = Inches(8.27)  # A4宽度
        total_width = page_width - MARGIN_LEFT - MARGIN_RIGHT
        
        # 设置列宽
        for i, (key, width_percent) in enumerate(TABLE_COLUMN_WIDTHS.items()):
            col_width = total_width * (width_percent / 100)
            for cell in table.columns[i].cells:
                cell.width = col_width
        
        # 设置表格边框
        self._set_table_borders(table)
    
    def _set_table_borders(self, table):
        """设置表格边框"""
        tbl = table._element
        tblPr = tbl.tblPr
        
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
            tbl.insert(0, tblPr)
        
        # 创建边框元素
        tblBorders = OxmlElement('w:tblBorders')
        
        # 定义边框样式
        border_attrs = {
            qn('w:val'): 'single',
            qn('w:sz'): '4',  # 1pt = 4
            qn('w:space'): '0',
            qn('w:color'): '000000'
        }
        
        # 添加各个边框
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            for attr, value in border_attrs.items():
                border.set(attr, value)
            tblBorders.append(border)
        
        tblPr.append(tblBorders)
    
    def _set_cell_background(self, cell, color: RGBColor):
        """设置单元格背景色"""
        cell_xml = cell._element
        cell_properties = cell_xml.get_or_add_tcPr()
        
        # 创建shading元素
        shading = OxmlElement('w:shd')
        # RGBColor是一个元组 (r, g, b)
        shading.set(qn('w:fill'), f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")
        cell_properties.append(shading)
    
    def calculate_page_numbers(self, docx_path: str) -> Dict[int, int]:
        """
        计算段落页码（估算）
        
        参数:
            docx_path: Word文档路径
        
        返回:
            {paragraph_index: page_number}
        """
        if docx_path in self.page_number_cache:
            return self.page_number_cache[docx_path]
        
        try:
            doc = Document(docx_path)
            page_map = {}
            
            # 简单估算：假设每页约40行（基于小四号字体，1.5倍行距）
            lines_per_page = 40
            current_line = 0
            current_page = 1
            
            for i, para in enumerate(doc.paragraphs):
                # 估算段落行数
                text_length = len(para.text)
                # 假设每行约40个字符
                chars_per_line = 40
                para_lines = max(1, (text_length + chars_per_line - 1) // chars_per_line)
                
                # 检查是否有分页符
                if self._has_page_break(para):
                    current_page += 1
                    current_line = 0
                
                page_map[i] = current_page
                
                current_line += para_lines
                if current_line >= lines_per_page:
                    current_page += 1
                    current_line = 0
            
            self.page_number_cache[docx_path] = page_map
            return page_map
        
        except Exception as e:
            print(f"警告: 计算页码时出错: {e}")
            return {}
    
    def _has_page_break(self, paragraph) -> bool:
        """检查段落是否包含分页符"""
        try:
            for run in paragraph.runs:
                if 'w:br' in run._element.xml:
                    br_elements = run._element.findall('.//w:br', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
                    for br in br_elements:
                        if br.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type') == 'page':
                            return True
        except Exception:
            pass
        return False
    
    def save(self, output_path: str):
        """保存Word文档"""
        try:
            self.doc.save(output_path)
            print(f"✓ Word报告已保存到: {output_path}")
            return True
        except PermissionError:
            base, ext = os.path.splitext(output_path)
            fallback_path = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            try:
                self.doc.save(fallback_path)
                print(f"⚠️ 目标文件被占用，已保存到: {fallback_path}")
                return True
            except Exception as e:
                print(f"✗ 保存Word报告失败: {e}")
                return False
        except Exception as e:
            print(f"✗ 保存Word报告失败: {e}")
            return False


def generate_word_report(all_reports: Dict[str, Any], output_path: str, docx_path: str = None) -> bool:
    """
    生成Word格式检测报告
    
    参数:
        all_reports: 所有检测模块的报告字典
        output_path: 输出文件路径
        docx_path: 原始Word文档路径（用于计算页码）
    
    返回:
        是否成功生成报告
    """
    try:
        # 创建报告生成器
        generator = WordReportGenerator()
        
        # 添加标题
        generator.add_title()
        
        print("正在整理检测结果...")
        errors_by_section: Dict[str, List[ErrorEntry]] = {}

        section_order = ['Title', 'Abstract', 'Keywords', 'Content', 'Formula', 'Table', 'Figure', 'Chinese_section', 'Classification']
        for section_name in section_order:
            report = all_reports.get(section_name)
            if not isinstance(report, dict):
                continue

            raw_errors = report.get('errors')
            if not isinstance(raw_errors, list):
                continue

            code = get_section_code(section_name)
            entries: List[ErrorEntry] = []
            idx_counter = 0
            for raw in raw_errors:
                if not isinstance(raw, dict):
                    continue

                idx_counter += 1
                raw_type = raw.get('type') or raw.get('error_type') or 'warning'
                if raw_type in ['警告', ' 警告', 'warning', 'WARNING', 'warn', 'WARN']:
                    error_type = 'warning'
                elif raw_type in ['错误', ' 错误', 'error', 'ERROR', 'err', 'ERR']:
                    error_type = 'error'
                else:
                    error_type = str(raw_type)

                error_id = raw.get('error_id')
                if not error_id:
                    error_id = f"{code}-{idx_counter}"

                entries.append(ErrorEntry(
                    error_id=str(error_id),
                    error_type=error_type,
                    page_number=str(raw.get('page_number', 'N/A')),
                    description=str(raw.get('description', '')),
                    suggestion=str(raw.get('suggestion', 'N/A')),
                    text_snippet=str(raw.get('text_snippet', 'N/A')),
                    section=section_name,
                    raw_data=raw
                ))

            if entries:
                errors_by_section[section_name] = entries
        
        # 计算统计信息
        total_errors = sum(len(errors) for errors in errors_by_section.values())
        total_checks = 0
        passed_checks = 0
        
        # 统计检测项（简化版，基于是否有错误）
        for section_name in ['Title', 'Abstract', 'Keywords', 'Content', 'Formula', 'Table', 'Figure', 'Chinese_section', 'Classification']:
            if section_name in all_reports:
                total_checks += 1
                if section_name not in errors_by_section:
                    passed_checks += 1
        
        failed_checks = total_checks - passed_checks
        
        # 添加总体评估
        generator.add_summary(total_checks, passed_checks, failed_checks)
        
        # 按部分添加错误表格
        for section_name in section_order:
            # 获取部分显示名称
            display_name = get_section_display_name(section_name)
            
            # 添加部分标题
            generator.add_section(display_name)
            
            # 检查是否有错误
            if section_name in errors_by_section:
                errors = errors_by_section[section_name]
                generator.add_error_table(errors)
            else:
                # 如果该部分在报告中且没有错误，显示通过消息
                if section_name in all_reports and not all_reports[section_name].get('error', False):
                    generator.add_pass_message(display_name)
        
        # 保存文档
        return generator.save(output_path)
    
    except Exception as e:
        print(f"✗ 生成Word报告时出错: {e}")
        import traceback
        traceback.print_exc()
        return False
