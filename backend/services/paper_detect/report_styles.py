#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from docx.shared import Pt, Cm, RGBColor

FONT_TITLE = '黑体'
FONT_HEADING = '黑体'
FONT_BODY = '宋体'
FONT_TABLE = '宋体'
FONT_TABLE_HEADER = '宋体'

FONT_SIZE_TITLE = Pt(18)
FONT_SIZE_HEADING = Pt(14)
FONT_SIZE_BODY = Pt(10.5)
FONT_SIZE_TABLE = Pt(10.5)
FONT_SIZE_TABLE_HEADER = Pt(11)

MARGIN_TOP = Cm(2.54)
MARGIN_BOTTOM = Cm(2.54)
MARGIN_LEFT = Cm(3.17)
MARGIN_RIGHT = Cm(3.17)

SPACE_BEFORE_TITLE = Pt(0)
SPACE_AFTER_TITLE = Pt(12)
SPACE_BEFORE_HEADING = Pt(12)
SPACE_AFTER_HEADING = Pt(6)
SPACE_BEFORE_TABLE = Pt(6)
SPACE_AFTER_TABLE = Pt(12)

COLOR_ERROR = RGBColor(255, 0, 0)
COLOR_WARNING = RGBColor(255, 165, 0)
COLOR_SUCCESS = RGBColor(0, 170, 0)
COLOR_TABLE_HEADER_BG = RGBColor(217, 226, 243)
COLOR_TABLE_BORDER = RGBColor(0, 0, 0)
COLOR_TEXT_NORMAL = RGBColor(0, 0, 0)

TABLE_COLUMN_WIDTHS = {'error_id': 8, 'error_type': 10, 'page_number': 8, 'description': 25, 'suggestion': 30, 'text_snippet': 19}
TABLE_HEADERS = ['错误编号', '错误类型', '错误页码', '错误描述', '建议修改方式', '文本片段']
TABLE_BORDER_WIDTH = Pt(1)

ERROR_TYPE_DISPLAY = {'error': ' 错误', 'warning': ' 警告'}
ERROR_TYPE_COLOR = {'error': COLOR_ERROR, 'warning': COLOR_WARNING}

SECTION_CODE_MAP = {'Title': 'T', 'Abstract': 'A', 'Keywords': 'K', 'Content': 'C', 'Formula': 'F', 'Table': 'TB', 'Figure': 'FG', 'Classification': 'CL'}
SECTION_NAME_MAP = {'Title': '标题检测', 'Abstract': '摘要检测', 'Keywords': '关键词检测', 'Content': '正文检测', 'Formula': '公式检测', 'Table': '表格检测', 'Figure': '图片检测', 'Classification': '分类号检测'}

def get_section_code(section_name):
    return SECTION_CODE_MAP.get(section_name, 'X')

def get_section_display_name(section_name):
    return SECTION_NAME_MAP.get(section_name, section_name)

def get_error_type_display(error_type):
    return ERROR_TYPE_DISPLAY.get(error_type, error_type)

def get_error_type_color(error_type):
    return ERROR_TYPE_COLOR.get(error_type, COLOR_TEXT_NORMAL)

def format_page_number(page_num):
    if page_num is None or page_num == 'N/A':
        return 'N/A'
    return str(page_num)

def truncate_text(text, max_length=150):
    if not text:
        return 'N/A'
    text = str(text).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'
