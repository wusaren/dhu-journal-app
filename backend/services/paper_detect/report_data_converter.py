#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告数据转换器模块

将各检测模块的原始报告数据转换为标准的ErrorEntry格式
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ErrorEntry:
    """标准错误条目数据类"""
    error_id: str              # 错误编号，格式: {部分代码}-{序号}
    error_type: str            # 错误类型: 'error' 或 'warning'
    page_number: str           # 页码或'N/A'
    description: str           # 错误描述
    suggestion: str            # 建议修改方式
    text_snippet: str          # 文本片段
    section: str               # 所属部分
    raw_data: Dict[str, Any] = field(default_factory=dict)  # 原始检测数据


def _convert_new_format_errors(report: Dict[str, Any], section: str, section_code: str) -> List[ErrorEntry]:
    errors: List[ErrorEntry] = []

    if not isinstance(report, dict):
        return errors

    raw_errors = report.get('errors')
    if not isinstance(raw_errors, list):
        return errors

    for idx, error_dict in enumerate(raw_errors, 1):
        if not isinstance(error_dict, dict):
            continue

        errors.append(ErrorEntry(
            error_id=f"{section_code}-{idx}",
            error_type=error_dict.get('type', 'warning'),
            page_number=str(error_dict.get('page_number', 'N/A')),
            description=error_dict.get('description', ''),
            suggestion=error_dict.get('suggestion', '建议：根据错误描述进行相应修改'),
            text_snippet=error_dict.get('text_snippet', 'N/A'),
            section=section,
            raw_data=error_dict
        ))

    return errors


def truncate_text(text: str, max_length: int = 150) -> str:
    """截断文本到指定长度"""
    if not text:
        return 'N/A'
    text = str(text).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'


def extract_page_number(data: Dict[str, Any]) -> str:
    """从检测数据中提取页码"""
    # 优先尝试获取实际页码
    for key in ['page', 'page_number', 'page_num']:
        if key in data and data[key] is not None:
            return str(data[key])
    
    # 如果没有页码，尝试获取段落索引
    if 'para_index' in data and data['para_index'] is not None:
        return f"段落{data['para_index']}"
    
    if 'paragraph_index' in data and data['paragraph_index'] is not None:
        return f"段落{data['paragraph_index']}"
    
    return 'N/A'


def generate_suggestion(error_type: str, description: str, data: Dict[str, Any]) -> str:
    """根据错误类型和描述生成修改建议"""
    # 这里可以根据具体的错误类型生成更详细的建议
    # 目前使用通用建议
    if '格式' in description:
        return '建议：按照规范要求调整格式'
    elif '缺失' in description or '未找到' in description:
        return '建议：补充缺失的内容'
    elif '不符合' in description:
        return '建议：修改为符合规范的内容'
    elif '符号' in description and '说明' in description:
        return '建议：在公式首次出现时添加符号说明'
    else:
        return '建议：根据错误描述进行相应修改'


def convert_title_report(report: Dict[str, Any], section_code: str = 'T') -> List[ErrorEntry]:
    """
    转换标题检测报告
    
    参数:
        report: 标题检测报告字典
        section_code: 部分代码，默认'T'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors
    
    # 直接使用errors数组（如果存在）
    if 'errors' in report and isinstance(report['errors'], list):
        for idx, error_dict in enumerate(report['errors'], 1):
            if isinstance(error_dict, dict):
                errors.append(ErrorEntry(
                    error_id=f"{section_code}-{idx}",
                    error_type=error_dict.get('type', 'warning'),
                    page_number=str(error_dict.get('page_number', 'N/A')),
                    description=error_dict.get('description', ''),
                    suggestion=error_dict.get('suggestion', '建议：根据错误描述进行相应修改'),
                    text_snippet=error_dict.get('text_snippet', 'N/A'),
                    section='Title',
                    raw_data=report
                ))
        return errors
    
    # 向后兼容：处理旧格式的messages
    # 提取标题文本
    title_text = ''
    if 'extracted' in report and isinstance(report['extracted'], dict):
        title_text = report['extracted'].get('title', '')
    
    # 收集所有错误消息
    all_messages = []
    
    # 遍历所有子检查项（title, authors, affiliations, format等）
    for check_name, check_data in report.items():
        if check_name in ['extracted', 'summary', 'ok']:
            continue
        if isinstance(check_data, dict):
            # 检查是否有ok字段且为False
            if 'ok' in check_data and not check_data.get('ok', True):
                # 提取messages
                if 'messages' in check_data and check_data['messages']:
                    for msg in check_data['messages']:
                        # 跳过批注标记消息
                        if not msg.startswith('__COMMENT_'):
                            all_messages.append(msg)
    
    # 如果没有错误消息，返回空列表
    if not all_messages:
        return errors
    
    # 为每个错误消息创建ErrorEntry
    for idx, msg in enumerate(all_messages, 1):
        error_id = f"{section_code}-{idx}"
        error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
        page_number = extract_page_number(report)
        description = msg
        suggestion = generate_suggestion(error_type, description, report)
        text_snippet = truncate_text(title_text)
        
        errors.append(ErrorEntry(
            error_id=error_id,
            error_type=error_type,
            page_number=page_number,
            description=description,
            suggestion=suggestion,
            text_snippet=text_snippet,
            section='Title',
            raw_data=report
        ))
    
    return errors


def convert_abstract_report(report: Dict[str, Any], section_code: str = 'A') -> List[ErrorEntry]:
    """
    转换摘要检测报告
    
    参数:
        report: 摘要检测报告字典
        section_code: 部分代码，默认'A'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors
    
    # 直接使用errors数组（如果存在）
    if 'errors' in report and isinstance(report['errors'], list):
        for idx, error_dict in enumerate(report['errors'], 1):
            if isinstance(error_dict, dict):
                errors.append(ErrorEntry(
                    error_id=f"{section_code}-{idx}",
                    error_type=error_dict.get('type', 'warning'),
                    page_number=str(error_dict.get('page_number', 'N/A')),
                    description=error_dict.get('description', ''),
                    suggestion=error_dict.get('suggestion', '建议：根据错误描述进行相应修改'),
                    text_snippet=error_dict.get('text_snippet', 'N/A'),
                    section='Abstract',
                    raw_data=report
                ))
        return errors
    
    # 向后兼容：处理旧格式的messages
    # 收集所有错误消息
    all_messages = []
    abstract_text = ''
    
    # 遍历中英文摘要
    for abstract_type in ['chinese_abstract', 'english_abstract']:
        if abstract_type in report:
            abstract_data = report[abstract_type]
            if isinstance(abstract_data, dict):
                # 提取摘要文本
                if 'extracted' in abstract_data and isinstance(abstract_data['extracted'], dict):
                    if not abstract_text:  # 优先使用中文摘要
                        abstract_text = abstract_data['extracted'].get('abstract', '')
                
                # 收集错误消息
                for check_name, check_data in abstract_data.items():
                    if isinstance(check_data, dict) and 'messages' in check_data:
                        if check_data['messages']:
                            all_messages.extend(check_data['messages'])
    
    # 如果没有错误消息，返回空列表
    if not all_messages:
        return errors
    
    # 为每个错误消息创建ErrorEntry
    for idx, msg in enumerate(all_messages, 1):
        error_id = f"{section_code}-{idx}"
        error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
        page_number = extract_page_number(report)
        description = msg
        suggestion = generate_suggestion(error_type, description, report)
        text_snippet = truncate_text(abstract_text)
        
        errors.append(ErrorEntry(
            error_id=error_id,
            error_type=error_type,
            page_number=page_number,
            description=description,
            suggestion=suggestion,
            text_snippet=text_snippet,
            section='Abstract',
            raw_data=report
        ))
    
    return errors


def convert_keywords_report(report: Dict[str, Any], section_code: str = 'K') -> List[ErrorEntry]:
    """
    转换关键词检测报告
    
    参数:
        report: 关键词检测报告字典
        section_code: 部分代码，默认'K'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors

    new_format_errors = _convert_new_format_errors(report, section='Keywords', section_code=section_code)
    if new_format_errors:
        return new_format_errors
    
    # 提取关键词文本
    keywords_text = ''
    if 'extracted' in report and isinstance(report['extracted'], dict):
        keywords = report['extracted'].get('keywords', [])
        if isinstance(keywords, list):
            keywords_text = '、'.join(keywords)
        else:
            keywords_text = str(keywords)
    
    # 收集所有错误消息
    all_messages = []
    
    # 遍历所有检查项
    for check_name, check_data in report.items():
        if isinstance(check_data, dict) and 'messages' in check_data:
            if check_data['messages']:
                all_messages.extend(check_data['messages'])
    
    # 如果没有错误消息，返回空列表
    if not all_messages:
        return errors
    
    # 为每个错误消息创建ErrorEntry
    for idx, msg in enumerate(all_messages, 1):
        error_id = f"{section_code}-{idx}"
        error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
        page_number = extract_page_number(report)
        description = msg
        suggestion = generate_suggestion(error_type, description, report)
        text_snippet = truncate_text(keywords_text)
        
        errors.append(ErrorEntry(
            error_id=error_id,
            error_type=error_type,
            page_number=page_number,
            description=description,
            suggestion=suggestion,
            text_snippet=text_snippet,
            section='Keywords',
            raw_data=report
        ))
    
    return errors


def convert_content_report(report: Dict[str, Any], section_code: str = 'C') -> List[ErrorEntry]:
    """
    转换正文检测报告
    
    参数:
        report: 正文检测报告字典
        section_code: 部分代码，默认'C'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors

    new_format_errors = _convert_new_format_errors(report, section='Content', section_code=section_code)
    if new_format_errors:
        return new_format_errors
    
    # 检查是否有段落问题列表
    if 'paragraphs_with_issues' in report:
        paragraphs = report['paragraphs_with_issues']
        if isinstance(paragraphs, list):
            for para in paragraphs:
                if isinstance(para, dict) and 'issues' in para:
                    issues = para['issues']
                    if isinstance(issues, list):
                        for issue in issues:
                            error_id = f"{section_code}-{len(errors) + 1}"
                            error_type = 'error' if '错误' in issue or '不符合' in issue else 'warning'
                            page_number = extract_page_number(para)
                            description = issue
                            suggestion = generate_suggestion(error_type, description, para)
                            text_snippet = truncate_text(para.get('text', ''))
                            
                            errors.append(ErrorEntry(
                                error_id=error_id,
                                error_type=error_type,
                                page_number=page_number,
                                description=description,
                                suggestion=suggestion,
                                text_snippet=text_snippet,
                                section='Content',
                                raw_data=para
                            ))
    
    return errors


def convert_formula_report(report: Dict[str, Any], section_code: str = 'F') -> List[ErrorEntry]:
    """
    转换公式检测报告（特殊处理符号说明问题）
    
    参数:
        report: 公式检测报告字典
        section_code: 部分代码，默认'F'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors

    new_format_errors = _convert_new_format_errors(report, section='Formula', section_code=section_code)
    if new_format_errors:
        return new_format_errors
    
    # 收集所有错误消息
    all_messages = []
    
    # 遍历所有检查项
    for check_name, check_data in report.items():
        if isinstance(check_data, dict) and 'messages' in check_data:
            if check_data['messages']:
                all_messages.extend(check_data['messages'])
    
    # 处理详细的公式符号说明问题
    if 'details' in report and isinstance(report['details'], dict):
        details = report['details']
        if 'symbol_definition' in details and isinstance(details['symbol_definition'], dict):
            symbol_def = details['symbol_definition']
            if 'per_formula' in symbol_def and isinstance(symbol_def['per_formula'], list):
                for formula_info in symbol_def['per_formula']:
                    if isinstance(formula_info, dict) and not formula_info.get('ok', True):
                        # 构建错误描述
                        formula_text = formula_info.get('formula_text', '')
                        formula_number = formula_info.get('formula_number', '')
                        missing_symbols = formula_info.get('missing_symbols', [])
                        
                        if missing_symbols:
                            error_id = f"{section_code}-{len(errors) + 1}"
                            description = f"公式 {formula_number} 中符号首次出现未说明: {', '.join(missing_symbols)}"
                            suggestion = '建议：在公式首次出现时，在正文中对所有符号进行说明'
                            
                            # 提取证据
                            evidence = formula_info.get('evidence', {})
                            if evidence:
                                evidence_text = '; '.join([f"{k}: {v}" for k, v in evidence.items()])
                                text_snippet = truncate_text(f"公式: {formula_text}\n证据: {evidence_text}")
                            else:
                                text_snippet = truncate_text(f"公式: {formula_text}")
                            
                            page_number = extract_page_number(formula_info)
                            
                            errors.append(ErrorEntry(
                                error_id=error_id,
                                error_type='error',
                                page_number=page_number,
                                description=description,
                                suggestion=suggestion,
                                text_snippet=text_snippet,
                                section='Formula',
                                raw_data=formula_info
                            ))
    
    # 处理一般错误消息
    for idx, msg in enumerate(all_messages, 1):
        error_id = f"{section_code}-{len(errors) + 1}"
        error_type = 'error'
        if '警告' in msg or '建议' in msg or '疑似' in msg:
            error_type = 'warning'
        
        page_number = extract_page_number(report)
        description = msg
        suggestion = generate_suggestion(error_type, description, report)
        text_snippet = 'N/A'
        
        errors.append(ErrorEntry(
            error_id=error_id,
            error_type=error_type,
            page_number=page_number,
            description=description,
            suggestion=suggestion,
            text_snippet=text_snippet,
            section='Formula',
            raw_data=report
        ))
    
    return errors


def convert_table_report(report: Dict[str, Any], section_code: str = 'TB') -> List[ErrorEntry]:
    """
    转换表格检测报告
    
    参数:
        report: 表格检测报告字典
        section_code: 部分代码，默认'TB'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors

    new_format_errors = _convert_new_format_errors(report, section='Table', section_code=section_code)
    if new_format_errors:
        return new_format_errors
    
    # 收集全局错误消息（如编号问题）
    for check_name, check_data in report.items():
        if isinstance(check_data, dict) and 'messages' in check_data:
            if check_data['messages']:
                for msg in check_data['messages']:
                    error_id = f"{section_code}-{len(errors) + 1}"
                    error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
                    page_number = extract_page_number(report)
                    description = msg
                    suggestion = generate_suggestion(error_type, description, report)
                    text_snippet = 'N/A'
                    
                    errors.append(ErrorEntry(
                        error_id=error_id,
                        error_type=error_type,
                        page_number=page_number,
                        description=description,
                        suggestion=suggestion,
                        text_snippet=text_snippet,
                        section='Table',
                        raw_data=report
                    ))
    
    # 处理每个表格的具体问题
    if 'tables' in report and isinstance(report['tables'], list):
        for table_info in report['tables']:
            if isinstance(table_info, dict):
                # 提取表格标题
                table_caption = ''
                if 'caption' in table_info and isinstance(table_info['caption'], dict):
                    table_caption = table_info['caption'].get('text', '')
                
                # 检查各项格式
                for check_name, check_data in table_info.items():
                    if isinstance(check_data, dict) and 'messages' in check_data:
                        if check_data['messages']:
                            for msg in check_data['messages']:
                                error_id = f"{section_code}-{len(errors) + 1}"
                                error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
                                page_number = extract_page_number(table_info)
                                description = msg
                                suggestion = generate_suggestion(error_type, description, table_info)
                                text_snippet = truncate_text(table_caption or '表格内容')
                                
                                errors.append(ErrorEntry(
                                    error_id=error_id,
                                    error_type=error_type,
                                    page_number=page_number,
                                    description=description,
                                    suggestion=suggestion,
                                    text_snippet=text_snippet,
                                    section='Table',
                                    raw_data=table_info
                                ))
    
    return errors


def convert_figure_report(report: Dict[str, Any], section_code: str = 'FG') -> List[ErrorEntry]:
    """
    转换图片检测报告
    
    参数:
        report: 图片检测报告字典
        section_code: 部分代码，默认'FG'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors

    new_format_errors = _convert_new_format_errors(report, section='Figure', section_code=section_code)
    if new_format_errors:
        return new_format_errors
    
    # 收集全局错误消息（如编号问题）
    for check_name, check_data in report.items():
        if isinstance(check_data, dict) and 'messages' in check_data:
            if check_data['messages']:
                for msg in check_data['messages']:
                    error_id = f"{section_code}-{len(errors) + 1}"
                    error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
                    page_number = extract_page_number(report)
                    description = msg
                    suggestion = generate_suggestion(error_type, description, report)
                    text_snippet = 'N/A'
                    
                    errors.append(ErrorEntry(
                        error_id=error_id,
                        error_type=error_type,
                        page_number=page_number,
                        description=description,
                        suggestion=suggestion,
                        text_snippet=text_snippet,
                        section='Figure',
                        raw_data=report
                    ))
    
    # 处理每个图片的具体问题
    if 'figures' in report and isinstance(report['figures'], list):
        for figure_info in report['figures']:
            if isinstance(figure_info, dict):
                # 提取图片标题
                figure_caption = ''
                if 'caption_info' in figure_info and isinstance(figure_info['caption_info'], dict):
                    figure_caption = figure_info['caption_info'].get('full_text', '')
                
                # 检查各项格式
                for check_name, check_data in figure_info.items():
                    if isinstance(check_data, dict) and 'messages' in check_data:
                        if check_data['messages']:
                            for msg in check_data['messages']:
                                error_id = f"{section_code}-{len(errors) + 1}"
                                error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
                                page_number = extract_page_number(figure_info)
                                description = msg
                                suggestion = generate_suggestion(error_type, description, figure_info)
                                text_snippet = truncate_text(figure_caption or '图片内容')
                                
                                errors.append(ErrorEntry(
                                    error_id=error_id,
                                    error_type=error_type,
                                    page_number=page_number,
                                    description=description,
                                    suggestion=suggestion,
                                    text_snippet=text_snippet,
                                    section='Figure',
                                    raw_data=figure_info
                                ))
    
    return errors


def convert_classification_report(report: Dict[str, Any], section_code: str = 'CL') -> List[ErrorEntry]:
    """
    转换分类号检测报告
    
    参数:
        report: 分类号检测报告字典
        section_code: 部分代码，默认'CL'
    
    返回:
        ErrorEntry列表
    """
    errors = []
    
    if not report or report.get('error', False):
        return errors

    new_format_errors = _convert_new_format_errors(report, section='Classification', section_code=section_code)
    if new_format_errors:
        return new_format_errors
    
    # 检查分类号匹配状态
    match_status = report.get('match_status', '')
    if match_status == '不一致':
        error_id = f"{section_code}-1"
        error_type = 'warning'  # 分类号不一致通常是警告
        page_number = extract_page_number(report)
        
        # 构建描述
        original_clc = report.get('original_clc', '')
        recommended_code = report.get('code', '')
        reason = report.get('reason', '')
        
        description = f"分类号不一致：原文使用 {original_clc}，建议使用 {recommended_code}"
        if reason:
            description += f"。{reason}"
        
        suggestion = f"建议：使用更精确的分类号 {recommended_code}"
        
        # 提取分类号文本
        classification_text = f"原分类号: {original_clc}, 推荐分类号: {recommended_code}"
        text_snippet = truncate_text(classification_text)
        
        errors.append(ErrorEntry(
            error_id=error_id,
            error_type=error_type,
            page_number=page_number,
            description=description,
            suggestion=suggestion,
            text_snippet=text_snippet,
            section='Classification',
            raw_data=report
        ))
    
    # 收集其他错误消息
    for check_name, check_data in report.items():
        if isinstance(check_data, dict) and 'messages' in check_data:
            if check_data['messages']:
                for msg in check_data['messages']:
                    error_id = f"{section_code}-{len(errors) + 1}"
                    error_type = 'error' if '错误' in msg or '不符合' in msg else 'warning'
                    page_number = extract_page_number(report)
                    description = msg
                    suggestion = generate_suggestion(error_type, description, report)
                    
                    classification = report.get('classification', '')
                    clc_number = report.get('clc_number', '')
                    text_snippet = truncate_text(classification or clc_number or 'N/A')
                    
                    errors.append(ErrorEntry(
                        error_id=error_id,
                        error_type=error_type,
                        page_number=page_number,
                        description=description,
                        suggestion=suggestion,
                        text_snippet=text_snippet,
                        section='Classification',
                        raw_data=report
                    ))
    
    return errors


def convert_all_reports(all_reports: Dict[str, Any]) -> Dict[str, List[ErrorEntry]]:
    """
    转换所有检测报告为标准格式
    
    参数:
        all_reports: 所有检测模块的报告字典，格式:
        {
            'Title': {...},
            'Abstract': {...},
            'Keywords': {...},
            'Content': {...},
            'Formula': {...},
            'Table': {...},
            'Figure': {...},
            'Classification': {...}
        }
    
    返回:
        按部分组织的ErrorEntry字典，格式:
        {
            'Title': [ErrorEntry, ...],
            'Abstract': [ErrorEntry, ...],
            ...
        }
    """
    errors_by_section = {}
    
    # 定义转换映射
    converters = {
        'Title': convert_title_report,
        'Abstract': convert_abstract_report,
        'Keywords': convert_keywords_report,
        'Content': convert_content_report,
        'Formula': convert_formula_report,
        'Table': convert_table_report,
        'Figure': convert_figure_report,
        'Classification': convert_classification_report
    }
    
    # 转换每个部分的报告
    for section_name, converter_func in converters.items():
        if section_name in all_reports:
            report = all_reports[section_name]
            try:
                errors = converter_func(report)
                if errors:  # 只添加有错误的部分
                    errors_by_section[section_name] = errors
            except Exception as e:
                print(f"警告: 转换{section_name}报告时出错: {e}")
                # 继续处理其他部分
                continue
    
    return errors_by_section


# 辅助函数：从检测结果中提取统计信息
def extract_statistics(all_reports: Dict[str, Any]) -> Dict[str, int]:
    """
    从所有报告中提取统计信息
    
    参数:
        all_reports: 所有检测模块的报告字典
    
    返回:
        统计信息字典，包含:
        - total_checks: 总检测项数
        - passed_checks: 通过项数
        - failed_checks: 失败项数
        - total_errors: 总错误数
        - total_warnings: 总警告数
    """
    stats = {
        'total_checks': 0,
        'passed_checks': 0,
        'failed_checks': 0,
        'total_errors': 0,
        'total_warnings': 0
    }
    
    # 转换所有报告
    errors_by_section = convert_all_reports(all_reports)
    
    # 统计每个部分
    for section_name in ['Title', 'Abstract', 'Keywords', 'Content', 'Formula', 'Table', 'Figure', 'Classification']:
        if section_name in all_reports:
            stats['total_checks'] += 1
            
            if section_name in errors_by_section:
                stats['failed_checks'] += 1
                # 统计错误和警告
                for error in errors_by_section[section_name]:
                    if error.error_type == 'error':
                        stats['total_errors'] += 1
                    elif error.error_type == 'warning':
                        stats['total_warnings'] += 1
            else:
                stats['passed_checks'] += 1
    
    return stats


# 辅助函数：生成部分统计信息
def get_section_statistics(all_reports: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    生成各模块的错误统计信息
    
    参数:
        all_reports: 所有检测模块的报告字典
    
    返回:
        模块统计列表，每项包含:
        - section_name: 模块名称
        - error_count: 错误数量
        - warning_count: 警告数量
        - total: 总计
    """
    errors_by_section = convert_all_reports(all_reports)
    section_stats = []
    
    section_names = {
        'Title': '标题检测',
        'Abstract': '摘要检测',
        'Keywords': '关键词检测',
        'Content': '正文检测',
        'Formula': '公式检测',
        'Table': '表格检测',
        'Figure': '图片检测',
        'Classification': '分类号检测'
    }
    
    for section_key, section_name in section_names.items():
        error_count = 0
        warning_count = 0
        
        if section_key in errors_by_section:
            for error in errors_by_section[section_key]:
                if error.error_type == 'error':
                    error_count += 1
                elif error.error_type == 'warning':
                    warning_count += 1
        
        section_stats.append({
            'section_name': section_name,
            'error_count': error_count,
            'warning_count': warning_count,
            'total': error_count + warning_count
        })
    
    # 按总数降序排列
    section_stats.sort(key=lambda x: x['total'], reverse=True)
    
    return section_stats
