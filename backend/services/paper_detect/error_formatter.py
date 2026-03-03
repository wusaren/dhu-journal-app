#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误格式化辅助模块
用于将旧的messages格式转换为新的errors格式
"""


def format_error(message, error_type='warning', page_number='N/A', text_snippet='N/A', suggestion=None):
    """
    将单个消息转换为标准错误格式
    
    参数:
        message: 错误描述消息
        error_type: 错误类型 ('error' 或 'warning')
        page_number: 页码或段落索引
        text_snippet: 相关文本片段
        suggestion: 修改建议（如果为None，则自动生成）
    
    返回:
        标准错误字典
    """
    # 自动判断错误类型
    if error_type == 'auto':
        if '错误' in message or '不符合' in message or '缺失' in message:
            error_type = 'error'
        else:
            error_type = 'warning'
    
    # 自动生成建议
    if suggestion is None:
        if '格式' in message:
            suggestion = '建议：按照规范要求调整格式'
        elif '缺失' in message or '未找到' in message:
            suggestion = '建议：补充缺失的内容'
        elif '不符合' in message or '不正确' in message:
            suggestion = '建议：修改为符合规范的内容'
        elif '编号' in message:
            suggestion = '建议：调整编号顺序'
        else:
            suggestion = '建议：根据错误描述进行相应修改'
    
    # 截断文本片段
    if text_snippet and len(text_snippet) > 150:
        text_snippet = text_snippet[:150] + '...'
    
    return {
        'type': error_type,
        'page_number': str(page_number),
        'description': message,
        'suggestion': suggestion,
        'text_snippet': text_snippet or 'N/A'
    }


def messages_to_errors(messages, error_type='auto', page_number='N/A', text_snippet='N/A'):
    """
    将messages列表转换为errors列表
    
    参数:
        messages: 消息列表
        error_type: 默认错误类型
        page_number: 默认页码
        text_snippet: 默认文本片段
    
    返回:
        errors列表
    """
    errors = []
    for msg in messages:
        if isinstance(msg, str):
            errors.append(format_error(msg, error_type, page_number, text_snippet))
    return errors


def convert_report_to_errors(report, text_snippet='N/A', page_number='N/A'):
    """
    将包含多个子报告的复杂报告转换为统一的errors格式
    
    参数:
        report: 原始报告字典，可能包含多个子报告
        text_snippet: 默认文本片段
        page_number: 默认页码
    
    返回:
        {'ok': bool, 'errors': []}
    """
    all_errors = []
    overall_ok = True
    
    # 遍历报告中的所有子项
    for key, value in report.items():
        if key in ['ok', 'summary', 'details', 'extracted', 'clc_content']:
            continue
        
        if isinstance(value, dict):
            # 检查是否有ok字段
            if 'ok' in value and not value.get('ok', True):
                overall_ok = False
            
            # 提取messages
            if 'messages' in value and value['messages']:
                for msg in value['messages']:
                    if isinstance(msg, str) and not msg.startswith('__COMMENT_'):
                        all_errors.append(format_error(
                            msg,
                            error_type='auto',
                            page_number=page_number,
                            text_snippet=text_snippet
                        ))
    
    return {
        'ok': overall_ok and len(all_errors) == 0,
        'errors': all_errors
    }
