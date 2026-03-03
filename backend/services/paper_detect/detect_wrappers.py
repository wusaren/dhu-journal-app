#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测模块包装器
将复杂模块的旧格式输出转换为统一的新格式
"""

from paper_detect.error_formatter import convert_report_to_errors, format_error


def wrap_keywords_report(original_report):
    """
    包装Keywords检测报告
    将复杂的嵌套结构转换为统一的errors格式
    """
    all_errors = []
    
    # 提取关键词文本
    keywords_text = ''
    if 'structure' in original_report and isinstance(original_report['structure'], dict):
        keywords_text = original_report['structure'].get('content', '')
    
    # 遍历所有子报告
    for key, value in original_report.items():
        if key in ['summary', 'clc_content']:
            continue
        
        if isinstance(value, dict) and 'messages' in value:
            for msg in value['messages']:
                if isinstance(msg, str):
                    all_errors.append(format_error(
                        msg,
                        error_type='auto',
                        page_number='N/A',
                        text_snippet=keywords_text[:150] if keywords_text else 'N/A'
                    ))
    
    return {
        'ok': len(all_errors) == 0,
        'errors': all_errors
    }


def wrap_content_report(original_report):
    """
    包装Content检测报告
    """
    all_errors = []
    
    # 处理标题格式问题
    if 'heading_format_issues' in original_report:
        issues = original_report['heading_format_issues']
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict):
                    heading_text = issue.get('heading_text', '')
                    problems = issue.get('problems', [])
                    for problem in problems:
                        all_errors.append(format_error(
                            problem,
                            error_type='warning',
                            page_number=f"段落{issue.get('index', 'N/A')}",
                            text_snippet=heading_text[:150] if heading_text else 'N/A'
                        ))
    
    # 处理段落格式问题
    if 'paragraph_format_issues' in original_report:
        issues = original_report['paragraph_format_issues']
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict):
                    para_text = issue.get('text', '')
                    problems = issue.get('problems', [])
                    for problem in problems:
                        all_errors.append(format_error(
                            problem,
                            error_type='warning',
                            page_number=f"段落{issue.get('index', 'N/A')}",
                            text_snippet=para_text[:150] if para_text else 'N/A'
                        ))
    
    # 处理其他messages
    for key, value in original_report.items():
        if isinstance(value, dict) and 'messages' in value:
            for msg in value['messages']:
                if isinstance(msg, str):
                    all_errors.append(format_error(
                        msg,
                        error_type='auto',
                        page_number='N/A',
                        text_snippet='N/A'
                    ))
    
    return {
        'ok': len(all_errors) == 0,
        'errors': all_errors
    }


def wrap_formula_report(original_report):
    """
    包装Formula检测报告
    """
    all_errors = []
    
    # 处理公式符号说明问题
    if 'details' in original_report and isinstance(original_report['details'], dict):
        details = original_report['details']
        if 'symbol_definition' in details and isinstance(details['symbol_definition'], dict):
            symbol_def = details['symbol_definition']
            if 'per_formula' in symbol_def and isinstance(symbol_def['per_formula'], list):
                for formula_info in symbol_def['per_formula']:
                    if isinstance(formula_info, dict) and not formula_info.get('ok', True):
                        formula_text = formula_info.get('formula_text', '')
                        formula_number = formula_info.get('formula_number', '')
                        missing_symbols = formula_info.get('missing_symbols', [])
                        
                        if missing_symbols:
                            description = f"公式 {formula_number} 中符号首次出现未说明: {', '.join(missing_symbols)}"
                            all_errors.append({
                                'type': 'error',
                                'page_number': 'N/A',
                                'description': description,
                                'suggestion': '建议：在公式首次出现时，在正文中对所有符号进行说明',
                                'text_snippet': formula_text[:150] if formula_text else 'N/A'
                            })
    
    # 处理其他messages
    for key, value in original_report.items():
        if isinstance(value, dict) and 'messages' in value:
            for msg in value['messages']:
                if isinstance(msg, str):
                    all_errors.append(format_error(
                        msg,
                        error_type='auto',
                        page_number='N/A',
                        text_snippet='N/A'
                    ))
    
    return {
        'ok': len(all_errors) == 0,
        'errors': all_errors
    }


def wrap_figure_report(original_report):
    """
    包装Figure检测报告
    """
    all_errors = []
    
    # 处理编号问题
    if 'numbering' in original_report and isinstance(original_report['numbering'], dict):
        numbering = original_report['numbering']
        if 'messages' in numbering:
            for msg in numbering['messages']:
                if isinstance(msg, str):
                    all_errors.append(format_error(
                        msg,
                        error_type='error',
                        page_number='N/A',
                        text_snippet='N/A'
                    ))
    
    # 处理每个图片的问题
    if 'figures' in original_report and isinstance(original_report['figures'], list):
        for figure_info in original_report['figures']:
            if isinstance(figure_info, dict):
                caption_text = ''
                if 'caption_info' in figure_info and isinstance(figure_info['caption_info'], dict):
                    caption_text = figure_info['caption_info'].get('full_text', '')
                
                # 检查各项格式
                for check_name, check_data in figure_info.items():
                    if isinstance(check_data, dict) and 'messages' in check_data:
                        for msg in check_data['messages']:
                            if isinstance(msg, str):
                                all_errors.append(format_error(
                                    msg,
                                    error_type='auto',
                                    page_number='N/A',
                                    text_snippet=caption_text[:150] if caption_text else 'N/A'
                                ))
    
    return {
        'ok': len(all_errors) == 0,
        'errors': all_errors
    }
