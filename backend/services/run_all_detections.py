#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=== 论文格式检测系统 - 集成检测脚本 ===

功能：
1. 调用所有检测模块（Title、Abstract、Keywords、Content、Formula、Table）
2. 生成综合文本报告
3. 在文档副本上添加批注标注所有问题

使用方法：
    python run_all_detections.py <docx文件路径>

输出：
    - <filename>_report.txt - 综合检测报告
    - <filename>_annotated.docx - 带批注的文档副本
"""

import os
import sys
import shutil
import re
from datetime import datetime
from docx import Document
from paper_detect.Classification_detect import detect_classification

# 模板配置映射：模块名 -> (检测函数所在模块, 检测函数名, 模板JSON路径)
TEMPLATE_MAPPING = {
    'Title': ('paper_detect.Title_detect', 'check_doc_with_template', 'templates/Title.json'),
    'Abstract': ('paper_detect.Abstract_detect', 'check_abstract_with_template', 'templates/Abstract.json'),
    'Keywords': ('paper_detect.Keywords_detect', 'check_keywords_with_template', 'templates/Keywords.json'),
    'Content': ('paper_detect.Content_detect', 'check_content_with_template', 'templates/Content.json'),
    'Formula': ('paper_detect.Formula_detect', 'check_doc_with_template', 'templates/Formula.json'),
    'Figure': ('paper_detect.Figure_detect', 'check_doc_with_template', 'templates/Figure.json'),
    'Table': ('paper_detect.Table_detect', 'check_doc_with_template', 'templates/Table.json'),
    'Reference': ('paper_detect.Reference_detect', 'check_doc_with_template', 'templates/Reference.json'),
    'Chinese_section': ('paper_detect.Chinese_section_detect', 'check_chinese_section_with_template', 'templates/Chinese_section.json'),
}

# 检测模块执行顺序
DETECTION_ORDER = ['Title', 'Abstract', 'Keywords', 'Content', 'Formula', 'Figure', 'Table', 'Reference', 'Chinese_section']

# 模块中文名称映射
MODULE_NAMES_CN = {
    'Title': '英文标题、作者与单位',
    'Abstract': '英文摘要',
    'Keywords': '英文关键词',
    'Content': '正文',
    'Formula': '公式',
    'Figure': '图',
    'Table': '表格',
    'Reference': '参考文献',
    'Chinese_section': '中文部分',
    'Classification': '摘要分类号',
    # 中文部分内部项目
    'chinese_title_format': '中文标题',
    'chinese_author_format': '中文作者',
    'chinese_affiliation_format': '中文单位',
    'chinese_abstract_format': '中文摘要',
    'chinese_keywords_format': '中文关键词',
}

# 全局检测配置（用于在各模块中访问）
GLOBAL_DETECTION_CONFIG = {
    'skip_checks': set(),
}


def _normalize_report_errors(module_name, report):
    if not isinstance(report, dict):
        return report

    raw_errors = report.get('errors')
    if not isinstance(raw_errors, list):
        return report

    try:
        from paper_detect.report_styles import get_section_code
    except Exception:
        get_section_code = lambda _: 'X'

    code = get_section_code(module_name)
    normalized = []
    counter = 0

    for e in raw_errors:
        if not isinstance(e, dict):
            continue

        counter += 1
        et = e.get('type') or e.get('error_type') or 'warning'
        if isinstance(et, str):
            et_stripped = et.strip().lower()
            if et_stripped in ['warning', 'warn', 'w', '警告']:
                e['type'] = 'warning'
            elif et_stripped in ['error', 'err', 'e', '错误']:
                e['type'] = 'error'
            else:
                e['type'] = et_stripped
        else:
            e['type'] = 'warning'

        if 'page_number' not in e or e.get('page_number') is None:
            e['page_number'] = 'N/A'
        if 'description' not in e or e.get('description') is None:
            e['description'] = ''
        if 'suggestion' not in e or e.get('suggestion') is None:
            e['suggestion'] = 'N/A'
        if 'text_snippet' not in e or e.get('text_snippet') is None:
            e['text_snippet'] = 'N/A'

        if not e.get('error_id'):
            e['error_id'] = f"{code}-{counter}"

        normalized.append(e)

    report['errors'] = normalized
    return report


def should_skip_check(check_name):
    """
    判断是否应该跳过某个检测项
    
    参数：
        check_name: 检测项名称（如 'font_size', 'bold', 'alignment' 等）
    
    返回：
        True 表示应该跳过，False 表示应该执行
    """
    return check_name in GLOBAL_DETECTION_CONFIG.get('skip_checks', set())


def print_usage():
    """打印使用说明"""
    print(__doc__)
    print("\n使用方法：")
    print("    python run_all_detections.py <docx文件路径> [选项]")
    print("\n选项说明：")
    print("    --enable-figure-api         启用图片内容API检测（会调用API分析图表）")
    print("    --enable-classification-api 启用摘要分类号API检测")
    print("    --no-page                  禁用综合报告中的页码定位")
    print("    --skip-font-size            跳过字体大小检测")
    print("    --skip-bold                 跳过加粗检测")
    print("    --skip-italic               跳过斜体检测")
    print("    --skip-alignment            跳过对齐检测")
    print("    --skip-spacing              跳过行距检测")
    print("    --skip-indent               跳过缩进检测")
    print("    --skip-address-zipcode      跳过中文单位的地址审核与邮编检测")
    print("    --skip-module <module>      跳过整个模块（如 Content, Title）")
    print("\n示例：")
    print("    python run_all_detections.py template/test.docx")
    print("    python run_all_detections.py template/test.docx --skip-font-size")
    print("    python run_all_detections.py template/test.docx --skip-module Content")
    print("    python run_all_detections.py template/test.docx --skip-bold --skip-italic")


def parse_arguments():
    """
    解析命令行参数
    返回：(docx文件路径, 检测配置字典)
    
    支持的参数：
        --enable-figure-api         启用图片内容API检测
        --no-page                  禁用综合报告中的页码定位
        --skip-font-size            跳过字体大小检测
        --skip-bold                 跳过加粗检测
        --skip-italic               跳过斜体检测
        --skip-alignment            跳过对齐检测
        --skip-spacing              跳过行距检测
        --skip-indent               跳过缩进检测
        --skip-address-zipcode      跳过中文单位的地址审核与邮编检测
        --skip-module <module>      跳过整个模块（如 Content, Title）
    """
    if len(sys.argv) < 2:
        print("错误：参数数量不正确")
        print_usage()
        sys.exit(1)
    
    docx_path = sys.argv[1]
    
    # 初始化检测配置
    detection_config = {
        'enable_figure_api': False,
        'enable_classification_api': False,
        'enable_page_numbers': True,
        'skip_checks': set(),  # 要跳过的检测项
        'skip_modules': set(),  # 要跳过的模块
    }
    
    # 解析其他参数
    for i in range(2, len(sys.argv)):
        arg = sys.argv[i]
        
        if arg == '--enable-figure-api':
            detection_config['enable_figure_api'] = True
            print("注意：已启用图片内容API检测")
        
        elif arg == '--enable-classification-api':
            detection_config['enable_classification_api'] = True
            print("注意：已启用摘要分类号API检测")

        elif arg == '--no-page':
            detection_config['enable_page_numbers'] = False
            print("注意：已禁用综合报告页码定位")
        
        elif arg == '--skip-font-size':
            detection_config['skip_checks'].add('font_size')
            print("注意：已跳过字体大小检测")
        
        elif arg == '--skip-bold':
            detection_config['skip_checks'].add('bold')
            print("注意：已跳过加粗检测")
        
        elif arg == '--skip-italic':
            detection_config['skip_checks'].add('italic')
            print("注意：已跳过斜体检测")
        
        elif arg == '--skip-alignment':
            detection_config['skip_checks'].add('alignment')
            print("注意：已跳过对齐检测")
        
        elif arg == '--skip-spacing':
            detection_config['skip_checks'].add('spacing')
            print("注意：已跳过行距检测")
        
        elif arg == '--skip-indent':
            detection_config['skip_checks'].add('indent')
            print("注意：已跳过缩进检测")
        
        elif arg == '--skip-address-zipcode':
            detection_config['skip_checks'].add('address_zipcode')
            print("注意：已跳过地址审核与邮编检测")
        
        elif arg == '--skip-module' and i + 1 < len(sys.argv):
            module_name = sys.argv[i + 1]
            detection_config['skip_modules'].add(module_name)
            print(f"注意：已跳过 {module_name} 模块检测")
        
        elif arg.startswith('--'):
            print(f"警告：未知参数 '{arg}'，将忽略")
    
    # 检查文件是否存在
    if not os.path.isfile(docx_path):
        print(f"错误：文件不存在: {docx_path}")
        sys.exit(1)
    
    # 检查文件扩展名
    if not docx_path.lower().endswith('.docx'):
        print(f"错误：文件必须是.docx格式: {docx_path}")
        sys.exit(1)
    
    return docx_path, detection_config


def import_detection_modules():
    """
    动态导入所有检测模块
    返回：{模块名: 检测函数} 字典
    """
    detection_functions = {}
    
    for module_name, (module_path, func_name, _) in TEMPLATE_MAPPING.items():
        try:
            # 动态导入模块
            module = __import__(module_path, fromlist=[func_name])
            # 将全局配置注入到模块中
            module.GLOBAL_DETECTION_CONFIG = GLOBAL_DETECTION_CONFIG
            # 获取检测函数
            detection_func = getattr(module, func_name)
            detection_functions[module_name] = detection_func
            print(f"✓ 成功导入 {module_name} 检测模块")
        except ImportError as e:
            print(f"✗ 导入 {module_name} 模块失败: {e}")
            sys.exit(1)
        except AttributeError as e:
            print(f"✗ 在 {module_name} 模块中找不到函数 {func_name}: {e}")
            sys.exit(1)
    
    return detection_functions


def run_all_detections(docx_path, detection_functions, enable_figure_api=False, enable_classification_api=False, detection_config=None):
    """
    调用所有检测模块并收集报告
    
    参数：
        docx_path: 待检测的文档路径
        detection_functions: 检测函数字典
        enable_figure_api: 是否启用Figure模块的API内容检测
        enable_classification_api: 是否启用Classification模块的API检测
        detection_config: 检测配置字典，指定启用哪些模块
                         例如：{'Title': True, 'Abstract': True, 'Content': False}
                         如果为None，则执行所有模块
    
    返回：
        {模块名: 报告字典} 的字典
    """
    all_reports = {}
    
    # 如果没有提供配置，默认全部执行
    if detection_config is None:
        detection_config = {module: True for module in DETECTION_ORDER}
    
    print(f"\n开始检测文档: {docx_path}")
    print("=" * 60)
    
    # 显示启用的检测模块
    enabled_modules = [m for m in DETECTION_ORDER if detection_config.get(m, True)]
    print(f"启用的检测模块: {', '.join(enabled_modules)}")
    print("=" * 60)
    
    for module_name in DETECTION_ORDER:
        # 检查模块是否启用
        if not detection_config.get(module_name, True):
            print(f"\n【{module_name} 检测】- 已跳过（未启用）")
            continue

        # Classification模块是后处理，此处跳过
        if module_name == 'Classification':
            continue

        template_path = TEMPLATE_MAPPING[module_name][2]
        detection_func = detection_functions[module_name]
        
        print(f"\n【{module_name} 检测】")
        print(f"  使用模板: {template_path}")
        
        try:
            # 调用检测函数
            # Figure模块特殊处理：根据参数决定是否启用API内容检测
            if module_name == 'Figure':
                report = detection_func(docx_path, template_path, enable_content_check=enable_figure_api)
            else:
                report = detection_func(docx_path, template_path)
            all_reports[module_name] = _normalize_report_errors(module_name, report)
            
            # 简要显示检测结果
            if isinstance(report, dict):
                # 新格式：{'ok': bool, 'errors': []}
                if 'ok' in report and 'errors' in report:
                    ok_status = "✓ 通过" if report['ok'] else "✗ 发现问题"
                    error_count = len(report.get('errors', []))
                    print(f"  结果: {ok_status} (错误数: {error_count})")
                else:
                    # 旧格式兼容（如Chinese_section等）
                    ok_count = sum(1 for key, value in report.items() 
                                  if isinstance(value, dict) and value.get('ok', False))
                    total_count = sum(1 for key, value in report.items() 
                                     if isinstance(value, dict) and 'ok' in value)
                    print(f"  结果: {ok_count}/{total_count} 项检测通过")
            else:
                print(f"  结果: 已完成")
                
        except Exception as e:
            print(f"  ✗ 检测失败: {e}")
            # 记录错误报告
            all_reports[module_name] = {
                'error': True,
                'error_message': str(e),
                'summary': [f'{module_name}检测失败: {e}']
            }
    
    print("\n" + "=" * 60)
    print("所有检测模块执行完成\n")
    
    return all_reports


def generate_comprehensive_report(all_reports, docx_path: str = None):
    """
    生成综合文本报告
    
    参数：
        all_reports: {模块名: 报告字典} 的字典
    
    返回：
        格式化的报告文本字符串
    """
    lines = []
    
    # 报告头部
    lines.append("=" * 80)
    lines.append("论文格式检测综合报告")
    lines.append("=" * 80)
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # 统计总体情况
    total_ok = 0
    total_checks = 0
    
    for module_name in DETECTION_ORDER:
        if module_name not in all_reports:
            continue
        
        report = all_reports[module_name]
        
        if report.get('error', False):
            continue
        
        # 统计该模块的检测项
        if isinstance(report, dict):
            # 新格式：{'ok': bool, 'errors': []}
            if 'ok' in report and 'errors' in report:
                total_checks += 1
                if report.get('ok', False):
                    total_ok += 1
            # 旧格式兼容（如Chinese_section等）
            else:
                # 其他旧格式模块常规统计
                for key, value in report.items():
                    if isinstance(value, dict) and 'ok' in value:
                        total_checks += 1
                        if value.get('ok', False):
                            total_ok += 1
    
    # 总体评估
    lines.append("【总体评估】")
    lines.append(f"总检测项数: {total_checks}")
    lines.append(f"通过项数: {total_ok}")
    lines.append(f"失败项数: {total_checks - total_ok}")
    if total_checks > 0:
        pass_rate = (total_ok / total_checks) * 100
        lines.append(f"通过率: {pass_rate:.1f}%")
    lines.append("")
    
    # 各模块详细报告
    for module_name in DETECTION_ORDER:
        if module_name not in all_reports:
            continue
        
        report = all_reports[module_name]
        
        lines.append("-" * 80)
        # 使用中文名称
        module_cn_name = MODULE_NAMES_CN.get(module_name, module_name)
        lines.append(f"【{module_cn_name} 检测报告】")
        lines.append("-" * 80)
        
        # 如果检测出错
        if report.get('error', False):
            lines.append(f"✗ 检测失败: {report.get('error_message', '未知错误')}")
            lines.append("")
            continue
        
        # Chinese_section模块：现在使用新格式 {'ok': bool, 'errors': []}
        elif module_name == 'Chinese_section':
            # 检查是否为新格式
            if 'ok' in report and 'errors' in report:
                # 新格式处理
                ok_status = "✓ 通过" if report.get('ok', False) else "✗ 发现问题"
                error_count = len(report.get('errors', []))
                lines.append(f"\n  总体状态: {ok_status}")
                lines.append(f"  错误数量: {error_count}")
                
                # 显示所有错误
                if error_count > 0:
                    lines.append(f"\n  【错误详情】")
                    for i, error in enumerate(report.get('errors', []), 1):
                        error_type = error.get('type', 'error')
                        type_icon = "❌" if error_type == 'error' else "⚠️"
                        page_num = error.get('page_number', 'N/A')
                        description = error.get('description', '')
                        suggestion = error.get('suggestion', '')
                        text_snippet = error.get('text_snippet', '')
                        
                        lines.append(f"\n  错误 {i}: {type_icon} {error_type.upper()}")
                        lines.append(f"    页码: {page_num}")
                        lines.append(f"    描述: {description}")
                        if suggestion and suggestion != 'N/A':
                            lines.append(f"    建议: {suggestion}")
                        if text_snippet and text_snippet != 'N/A' and len(text_snippet) > 5:
                            # 截断过长的文本片段
                            if len(text_snippet) > 100:
                                text_snippet = text_snippet[:100] + '...'
                            lines.append(f"    文本: {text_snippet}")
            else:
                # 旧格式兼容（如果还有旧格式的报告）
                for section_key, section_value in report.items():
                    if section_key == 'summary' or not isinstance(section_value, dict) or 'ok' not in section_value:
                        continue
                    
                    section_title = MODULE_NAMES_CN.get(section_key, section_key)
                    ok_status = "✓ 通过" if section_value.get('ok') else "✗ 失败"
                    lines.append(f"\n  [{section_title}] {ok_status}")
                    
                    messages = section_value.get('messages', [])
                    if messages and not section_value.get('ok'):
                        for msg in messages:
                            lines.append(f"    • {msg}")
        
        else:
            # 新格式：{'ok': bool, 'errors': []}
            if 'ok' in report and 'errors' in report:
                ok_status = "✓ 通过" if report.get('ok', False) else "✗ 发现问题"
                error_count = len(report.get('errors', []))
                lines.append(f"\n  总体状态: {ok_status}")
                lines.append(f"  错误数量: {error_count}")
                
                # 显示所有错误
                if error_count > 0:
                    lines.append(f"\n  【错误详情】")
                    for i, error in enumerate(report.get('errors', []), 1):
                        error_type = error.get('type', 'error')
                        type_icon = "❌" if error_type == 'error' else "⚠️"
                        page_num = error.get('page_number', 'N/A')
                        description = error.get('description', '')
                        suggestion = error.get('suggestion', '')
                        text_snippet = error.get('text_snippet', '')
                        
                        lines.append(f"\n  错误 {i}: {type_icon} {error_type.upper()}")
                        lines.append(f"    页码: {page_num}")
                        lines.append(f"    描述: {description}")
                        if suggestion and suggestion != 'N/A':
                            lines.append(f"    建议: {suggestion}")
                        if text_snippet and text_snippet != 'N/A' and len(text_snippet) > 5:
                            # 截断过长的文本片段
                            if len(text_snippet) > 100:
                                text_snippet = text_snippet[:100] + '...'
                            lines.append(f"    文本: {text_snippet}")
            # 旧格式兼容
            else:
                # 其他模块的常规处理（旧格式）
                for section_key, section_value in report.items():
                    if section_key in ['summary', 'extracted', 'details']:
                        continue
                    
                    if isinstance(section_value, dict) and 'ok' in section_value:
                        # 检测项标题
                        # 优先从中文映射获取，否则进行转换
                        section_title = MODULE_NAMES_CN.get(section_key, section_key.replace('_', ' ').title())
                        ok_status = "✓ 通过" if section_value.get('ok') else "✗ 失败"
                        lines.append(f"\n  [{section_title}] {ok_status}")
                        
                        # 检测项消息
                        messages = section_value.get('messages', [])
                        if messages:
                            for msg in messages:
                                # 格式化消息（添加缩进）
                                if msg.strip().startswith('-'):
                                    lines.append(f"      {msg.strip()}")
                                else:
                                    lines.append(f"    • {msg}")
        
        # 添加总结
        if 'summary' in report and report['summary']:
            lines.append("\n  【总结】")
            for summary_item in report['summary']:
                lines.append(f"    {summary_item}")
        
        lines.append("")
    
    # 公式符号说明问题清单（结构化）
    formula_report = all_reports.get('Formula', {}) if isinstance(all_reports, dict) else {}
    try:
        details = formula_report.get('details', {}) if isinstance(formula_report, dict) else {}
        sd_details = details.get('symbol_definition', {}) if isinstance(details, dict) else {}
        per_formula = sd_details.get('per_formula', []) if isinstance(sd_details, dict) else []
    except Exception:
        per_formula = []

    if per_formula:
        issue_lines = []
        for pf in per_formula:
            if not isinstance(pf, dict):
                continue

            missing = pf.get('missing_symbols', []) or []
            warnings = pf.get('warnings', []) or []
            suspected = pf.get('suspected_explained_symbols', []) or []
            if (not missing) and (not warnings) and (not suspected):
                continue

            fno = (pf.get('formula_number') or '').strip() if isinstance(pf.get('formula_number'), str) else ''
            idx = pf.get('index', '')
            number_display = fno if fno else f"段落{pf.get('paragraph_index', idx)}"

            page_display = 'N/A'

            formula_text = pf.get('formula_text', '')
            if isinstance(formula_text, str):
                snippet_formula = formula_text.strip()
                if len(snippet_formula) > 120:
                    snippet_formula = snippet_formula[:120] + '...'
            else:
                snippet_formula = ''

            evidence = pf.get('evidence', {}) if isinstance(pf.get('evidence', {}), dict) else {}

            if missing:
                desc = f"符号首次出现未说明: {', '.join(missing)}"
                suggest = f"建议在公式附近使用 where/denotes/其中… 等规范句式逐一定义: {', '.join(missing)}"
                snippet_parts = []
                if snippet_formula:
                    snippet_parts.append(snippet_formula)
                if evidence:
                    for sym in missing[:2]:
                        ev = evidence.get(sym)
                        if isinstance(ev, str) and ev.strip():
                            snippet_parts.append(f"{sym}: {ev.strip()}")
                issue_lines.append(
                    f"编号: {number_display} | 页码: {page_display} | 类型: error\n"
                    f"描述: {desc}\n"
                    f"建议: {suggest}\n"
                    f"文本片段: {' | '.join(snippet_parts) if snippet_parts else 'N/A'}\n"
                )

            if suspected:
                desc = f"符号疑似已说明（非标准定义句式）: {', '.join(suspected)}"
                suggest = "建议补充规范定义句式（where/denotes/其中…），避免歧义。"
                snippet_parts = []
                if snippet_formula:
                    snippet_parts.append(snippet_formula)
                for sym in suspected[:2]:
                    ev = evidence.get(sym)
                    if isinstance(ev, str) and ev.strip():
                        snippet_parts.append(f"{sym}: {ev.strip()}")
                issue_lines.append(
                    f"编号: {number_display} | 页码: {page_display} | 类型: warning\n"
                    f"描述: {desc}\n"
                    f"建议: {suggest}\n"
                    f"文本片段: {' | '.join(snippet_parts) if snippet_parts else 'N/A'}\n"
                )

            if isinstance(warnings, list) and warnings:
                for w in warnings:
                    if not w:
                        continue
                    desc = str(w)
                    if desc.startswith('复合符号已说明但未单独说明基符号'):
                        suggest = '建议在首次出现处单独定义基符号（如 c、k），或按模板要求使用单字母符号。'
                    elif desc.startswith('复合符号未说明'):
                        suggest = '建议在首次出现处补充对该符号的文字说明。'
                    elif desc.startswith('符号疑似已说明'):
                        suggest = '建议补充规范定义句式（where/denotes/其中…），避免歧义。'
                    else:
                        suggest = '建议按模板规范补充符号说明。'

                    snippet_parts = []
                    if snippet_formula:
                        snippet_parts.append(snippet_formula)
                    issue_lines.append(
                        f"编号: {number_display} | 页码: {page_display} | 类型: warning\n"
                        f"描述: {desc}\n"
                        f"建议: {suggest}\n"
                        f"文本片段: {' | '.join(snippet_parts) if snippet_parts else 'N/A'}\n"
                    )

        if issue_lines:
            lines.append("-" * 80)
            lines.append("【公式符号说明问题清单】")
            lines.append("-" * 80)
            for it in issue_lines:
                for line in it.strip().split('\n'):
                    lines.append(line)
                lines.append("")
    
    # 单独处理分类号报告
    if 'Classification' in all_reports:
        report = all_reports['Classification']
        lines.append("-" * 80)
        lines.append(f"【{MODULE_NAMES_CN['Classification']} 检测报告】")
        lines.append("-" * 80)
        if 'error' in report:
            lines.append(f"  ✗ 检测失败: {report['error']}")
        else:
            lines.append(f"  ✓ 检测完成")
            lines.append(f"    API 提取分类号: {report.get('code', 'N/A')} (原始: {report.get('raw_code', 'N/A')})")
            lines.append(f"    原文中的分类号: {report.get('original_clc', '未找到')}")
            
            match_status = report.get('match_status', '未知')
            if match_status == '一致':
                status_icon = '✓'
            elif match_status == '不一致':
                status_icon = '✗'
            else:
                status_icon = '?'
            lines.append(f"    对比结果: {status_icon} {match_status}")
            lines.append("\n  【分类理由】")
            # 格式化理由，每行80个字符
            reason_text = report.get('reason', '无').replace('\n', ' ')
            import textwrap
            wrapped_text = textwrap.fill(reason_text, width=70)
            for line in wrapped_text.split('\n'):
                lines.append(f"    {line}")
        lines.append("")
    
    # 报告尾部
    lines.append("=" * 80)
    lines.append("报告结束")
    lines.append("=" * 80)

    return "\n".join(lines)


def save_report_to_file(report_text, output_path):
    """
    保存报告到文件
    
    参数：
        report_text: 报告文本
        output_path: 输出文件路径
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"✓ 报告已保存到: {output_path}")
        return True
    except Exception as e:
        print(f"✗ 保存报告失败: {e}")
        return False


def create_document_copy(original_path):
    """
    创建文档副本
    
    参数：
        original_path: 原始文档路径
    
    返回：
        副本文件路径
    """
    # 将副本文件放在与原文件相同的目录
    dir_path = os.path.dirname(original_path)
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    copy_filename = f"{base_name}_annotated.docx"
    copy_path = os.path.join(dir_path, copy_filename) if dir_path else copy_filename
    
    try:
        shutil.copy(original_path, copy_path)
        print(f"✓ 文档副本已创建: {copy_path}")
        return copy_path
    except Exception as e:
        print(f"✗ 创建文档副本失败: {e}")
        return None


def find_paragraph_by_keyword(doc, keyword, case_sensitive=False):
    """
    通过关键字查找段落
    
    参数：
        doc: Document对象
        keyword: 关键字
        case_sensitive: 是否区分大小写
    
    返回：
        匹配的段落对象，未找到返回None
    """
    for paragraph in doc.paragraphs:
        if not paragraph.text:
            continue
        
        text = paragraph.text if case_sensitive else paragraph.text.lower()
        search_key = keyword if case_sensitive else keyword.lower()
        
        if search_key in text:
            return paragraph
    
    return None


def find_paragraph_by_index(doc, index, skip_empty=True):
    """
    通过索引查找段落
    
    参数：
        doc: Document对象
        index: 段落索引
        skip_empty: 是否跳过空段落（默认True，兼容旧逻辑）
    
    返回：
        段落对象，索引无效返回None
    """
    try:
        if not skip_empty:
            # 不跳过空行，直接返回
            if 0 <= index < len(doc.paragraphs):
                return doc.paragraphs[index]
        else:
            # 跳过空行，找到第N个非空段落
            non_empty_count = 0
            for paragraph in doc.paragraphs:
                if paragraph.text and paragraph.text.strip():
                    if non_empty_count == index:
                        return paragraph
                    non_empty_count += 1
    except Exception:
        pass
    
    return None


def find_paragraph_by_text(doc, text_fragment, threshold=0.7):
    """
    通过文本片段查找段落（模糊匹配）
    
    参数：
        doc: Document对象
        text_fragment: 文本片段
        threshold: 相似度阈值（0-1）
    
    返回：
        最匹配的段落对象，未找到返回None
    """
    best_match = None
    best_score = 0
    
    search_text = text_fragment.lower().strip()
    if len(search_text) < 5:
        # 文本太短，使用精确匹配
        for paragraph in doc.paragraphs:
            if search_text in paragraph.text.lower():
                return paragraph
        return None
    
    for paragraph in doc.paragraphs:
        if not paragraph.text or len(paragraph.text.strip()) < 5:
            continue
        
        para_text = paragraph.text.lower().strip()
        
        # 简单的相似度计算：检查搜索文本是否在段落中
        if search_text in para_text:
            score = len(search_text) / len(para_text)
            if score > best_score:
                best_score = score
                best_match = paragraph
    
    if best_score >= threshold:
        return best_match
    
    return None


def add_comment_to_paragraph(doc, paragraph, comment_text, author="论文检测系统", initials="PDS"):
    """
    为段落添加批注（覆盖整个段落）
    
    参数：
        doc: Document对象
        paragraph: 段落对象
        comment_text: 批注内容
        author: 批注作者
        initials: 批注作者缩写
    
    返回：
        成功返回True，失败返回False
    """
    try:
        # 确保段落有run
        if not paragraph.runs:
            # 如果段落没有run，添加一个
            paragraph.add_run("")
        
        # 策略：为了让批注覆盖整个段落，我们选择所有的runs
        # 如果段落有多个runs，收集它们；如果只有一个run，就用那个
        runs_to_annotate = paragraph.runs if len(paragraph.runs) > 1 else paragraph.runs[0]
        
        # 添加批注
        doc.add_comment(runs=runs_to_annotate, text=comment_text, author=author, initials=initials)
        return True
    except Exception as e:
        # 如果出错，尝试备用方案：只使用第一个run
        try:
            run = paragraph.runs[0]
            doc.add_comment(runs=run, text=comment_text, author=author, initials=initials)
            print(f"  ⚠ 批注仅覆盖部分文本（备用方案）")
            return True
        except Exception as e2:
            print(f"  ✗ 添加批注失败: {e2}")
            return False


def extract_paragraph_number_from_message(message):
    """
    从错误消息中提取段落编号
    例如："正文段落 1 字体大小..." -> 返回 1
    """
    match = re.search(r'正文段落\s*(\d+)', message)
    if match:
        return int(match.group(1))
    
    match = re.search(r'段落\s*(\d+)', message)
    if match:
        return int(match.group(1))
    
    return None


def group_messages_by_paragraph(messages):
    """
    将消息按段落分组
    
    返回：
        {段落编号: [消息列表], None: [无段落编号的消息]}
    """
    grouped = {}
    
    for msg in messages:
        para_num = extract_paragraph_number_from_message(msg)
        if para_num not in grouped:
            grouped[para_num] = []
        grouped[para_num].append(msg)
    
    return grouped


def group_messages_by_title(messages, titles):
    """
    将标题格式/大小写消息按标题文本分组
    
    参数：
        messages: 消息列表
        titles: 标题信息列表
    
    返回：
        {标题文本: [消息列表]}
    """
    import re
    grouped = {}
    
    for msg in messages:
        # 从消息中提取标题文本
        # 消息格式：标题 'xxx' 字体大小应为...
        # 或：一级标题 'xxx' 大小写不正确...
        title_match = re.search(r"标题\s+'([^']+)'", msg)
        if title_match:
            title_text = title_match.group(1)
            if title_text not in grouped:
                grouped[title_text] = []
            grouped[title_text].append(msg)
        else:
            # 消息头（如"标题格式问题："）或无法提取标题的消息，归到None
            if None not in grouped:
                grouped[None] = []
            grouped[None].append(msg)
    
    # 移除None键（这些是消息头）
    if None in grouped:
        del grouped[None]
    
    return grouped


def parse_issues_from_reports(all_reports):
    """
    从报告中提取问题列表和定位信息
    
    参数：
        all_reports: {模块名: 报告字典} 的字典
    
    返回：
        问题列表 [{
            'module': 模块名,
            'section': 检测项名称,
            'messages': 问题消息列表,
            'locate_method': 定位方法（'keyword', 'index', 'text', 'paragraph_object'），
            'locate_data': 定位数据（关键字、索引、文本片段、段落对象）
        }]
    """
    issues = []
    
    # ========== 新格式到旧格式的转换层 ==========
    # 对于新格式的报告，直接生成issues，不需要转换为旧格式
    converted_reports = {}
    new_format_issues = []  # 存储从新格式直接生成的issues
    
    for module_name, report in all_reports.items():
        if report.get('error', False):
            converted_reports[module_name] = report
            continue
        
        # Figure和Table模块有特殊的定位逻辑，不在这里处理
        if module_name in ('Figure', 'Table'):
            converted_reports[module_name] = report
            continue
        
        # 检查是否为新格式
        if 'ok' in report and 'errors' in report and isinstance(report.get('errors'), list):
            # 新格式：直接从errors生成issues
            errors = report.get('errors', [])
            
            # 新的分组策略：
            # 1. 对于有有效text_snippet的错误，按text_snippet分组
            # 2. 对于没有text_snippet的错误，按page_number分组
            # 这样可以确保每个批注都能精确定位
            
            errors_by_location = {}  # key: (locate_method, locate_data), value: [errors]
            
            for error in errors:
                if not isinstance(error, dict):
                    continue
                
                desc = error.get('description', '')
                if not desc:
                    continue
                
                page_num = error.get('page_number', 'N/A')
                snippet = error.get('text_snippet', '')
                
                # 确定定位方法和数据
                locate_method = 'index'
                locate_data = 0
                location_key = None
                
                # 新的定位优先级策略：
                # 1. 优先使用page_number中的段落索引（最精确）
                # 2. 其次使用text_snippet进行keyword定位
                # 3. 最后使用默认定位
                
                # 优先级1：检查page_number是否包含段落索引
                if isinstance(page_num, str):
                    import re
                    match = re.search(r'段落\s*(\d+)', page_num)
                    if match:
                        para_idx = int(match.group(1))
                        # paragraph_index是python索引（从0开始），直接使用
                        locate_method = 'index'
                        locate_data = para_idx
                        location_key = (locate_method, locate_data)
                
                # 优先级2：如果没有段落索引，使用text_snippet进行keyword定位
                if location_key is None and snippet and snippet.strip() and snippet.strip().upper() != 'N/A':
                    snippet_text = snippet.strip()

                    # Figure模块中，编号统计类文本（如“发现编号：...”）并不在正文中出现，
                    # 不适合作为关键字定位，会导致“无法定位段落”。
                    if module_name == 'Figure' and re.search(r'发现编号|期望编号|编号不连续|连续性', snippet_text):
                        locate_method = 'keyword'
                        locate_data = 'Fig.'
                    else:
                        locate_method = 'keyword'
                        locate_data = snippet_text[:30]
                    location_key = (locate_method, locate_data)
                
                # 优先级3：如果都没有，使用默认定位
                elif location_key is None and isinstance(page_num, str):
                    if page_num == 'N/A':
                        # 无法精确定位，使用模块默认关键字
                        if module_name == 'Content':
                            locate_method = 'keyword'
                            locate_data = 'Introduction'
                        elif module_name == 'Abstract':
                            locate_method = 'keyword'
                            locate_data = 'Abstract'
                        elif module_name == 'Keywords':
                            locate_method = 'keyword'
                            locate_data = 'Keywords'
                        else:
                            locate_method = 'index'
                            locate_data = 0
                        location_key = (locate_method, locate_data)
                    else:
                        # 其他格式的page_number
                        location_key = ('page', page_num)
                
                # 如果还是没有确定定位方法，使用默认定位
                if location_key is None:
                    location_key = ('index', 0)
                
                # 按定位信息分组
                if location_key not in errors_by_location:
                    errors_by_location[location_key] = []
                errors_by_location[location_key].append(error)
            
            # 为每个定位创建一个issue
            for (loc_method, loc_data), error_list in errors_by_location.items():
                messages = []
                for e in error_list:
                    desc = e.get('description', '')
                    if desc:
                        messages.append(desc)
                
                if not messages:
                    continue
                
                # 创建issue
                new_issue = {
                    'module': module_name,
                    'section': f'location_{len(new_format_issues)}',
                    'messages': messages,
                    'locate_method': loc_method,
                    'locate_data': loc_data,
                }
                
                # 特殊处理Content模块的content_paragraph定位
                if loc_method == 'content_paragraph':
                    new_issue['extra'] = {
                        'hierarchy_report': report.get('hierarchy', {}) if isinstance(report, dict) else {}
                    }
                
                # 当使用index定位方法时，检查是否来自段落索引（python索引）
                # 这些模块的段落索引是python索引（从0开始），不应该跳过空行
                if loc_method == 'index':
                    # 检查error_list中是否有任何error的page_number包含"段落"
                    has_paragraph_index = False
                    for e in error_list:
                        page_num = e.get('page_number', '')
                        if isinstance(page_num, str) and '段落' in page_num:
                            has_paragraph_index = True
                            break
                    
                    # 如果来自段落索引，添加skip_empty=False标记
                    if has_paragraph_index:
                        if 'extra' not in new_issue:
                            new_issue['extra'] = {}
                        new_issue['extra']['skip_empty'] = False
                
                new_format_issues.append(new_issue)
            
            # 标记为已处理（不需要再次处理）
            converted_reports[module_name] = {'_processed': True}
        else:
            # 旧格式：直接使用
            converted_reports[module_name] = report
    
    # 使用转换后的报告
    all_reports = converted_reports
    # ========== 转换层结束 ==========
    
    for module_name in DETECTION_ORDER:
        if module_name not in all_reports:
            continue
        
        report = all_reports[module_name]
        
        # 跳过错误报告
        if report.get('error', False):
            continue
        
        # 跳过已处理的新格式报告
        if report.get('_processed', False):
            continue
        
        # 为不同模块设计定位策略
        if module_name == 'Title':
            # Title模块：使用关键字定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details']:
                    continue
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if not messages:
                        continue
                    
                    # 根据section类型确定关键字
                    if 'title' in section_key.lower():
                        locate_method = 'index'
                        locate_data = 0  # 标题通常是第一个段落
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
                    elif 'author' in section_key.lower():
                        locate_method = 'index'
                        locate_data = 1  # 作者通常是第二个段落
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
                    elif 'affiliation' in section_key.lower():
                        locate_method = 'keyword'
                        locate_data = 'College'  # 单位通常包含College关键字
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
                    elif 'format' in section_key.lower():
                        # Title模块的格式消息优先使用结构化字段
                        structured_title_msgs = section_value.get('title_messages', [])
                        structured_author_msgs = section_value.get('author_messages', [])
                        structured_affiliation_msgs = section_value.get('affiliation_messages', [])
                        
                        use_structured = any(structured_title_msgs) or any(structured_author_msgs) or any(structured_affiliation_msgs)
                        
                        if use_structured:
                            if structured_title_msgs and any('问题' in msg or '错误' in msg for msg in structured_title_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_title',
                                    'messages': structured_title_msgs,
                                    'locate_method': 'index',
                                    'locate_data': 0
                                })
                            
                            if structured_author_msgs and any('问题' in msg or '错误' in msg for msg in structured_author_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_authors',
                                    'messages': structured_author_msgs,
                                    'locate_method': 'index',
                                    'locate_data': 1
                                })
                            
                            affiliation_msgs = structured_affiliation_msgs
                        else:
                            # format问题需要按消息内容分组（兼容旧格式）
                            title_msgs = []
                            author_msgs = []
                            affiliation_msgs = []
                            current_group = None  # 跟踪当前消息组
                            
                            for msg in messages:
                                # 跳过独立批注标记的消息
                                if msg.startswith('__COMMENT_PARA_'):
                                    affiliation_msgs.append(msg)
                                    continue
                                    
                                msg_lower = msg.lower()
                                msg_stripped = msg.strip()
                                
                                # 判断是否是标题行（非子项）
                                is_header = not msg_stripped.startswith('- ')
                                
                                if is_header:
                                    # 这是一个标题行，确定它属于哪个组
                                    if '标题格式' in msg or 'title' in msg_lower:
                                        current_group = 'title'
                                        title_msgs.append(msg)
                                    elif '作者格式' in msg or 'author' in msg_lower:
                                        current_group = 'author'
                                        author_msgs.append(msg)
                                    elif '单位格式' in msg or '单位段落' in msg or 'affiliation' in msg_lower:
                                        current_group = 'affiliation'
                                        affiliation_msgs.append(msg)
                                    else:
                                        # 默认归类到标题
                                        current_group = 'title'
                                        title_msgs.append(msg)
                                else:
                                    # 这是子项，归入当前组
                                    if current_group == 'title':
                                        title_msgs.append(msg)
                                    elif current_group == 'author':
                                        author_msgs.append(msg)
                                    elif current_group == 'affiliation':
                                        affiliation_msgs.append(msg)
                                    else:
                                        # 如果没有当前组，默认归类到标题
                                        title_msgs.append(msg)
                            
                            # 为每组消息创建独立的issue（只添加包含问题的组）
                            # 判断是否有实际问题：检查消息中是否包含"问题"或"错误"关键字
                            if title_msgs and any('问题' in msg or '错误' in msg for msg in title_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_title',
                                    'messages': title_msgs,
                                    'locate_method': 'index',
                                    'locate_data': 0
                                })
                            
                            if author_msgs and any('问题' in msg or '错误' in msg for msg in author_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_authors',
                                    'messages': author_msgs,
                                    'locate_method': 'index',
                                    'locate_data': 1
                                })
                        
                        if structured_affiliation_msgs or not use_structured:
                            # 分组单位消息：按段落和问题类型
                            # 1. 提取独立批注标记的消息 (__COMMENT_PARA_X__)
                            # 2. 其他消息按段落分组
                            comment_issues = {}  # {para_idx: [messages]}
                            affiliation_by_para = {}
                            general_affiliation_msgs = []
                            current_para_idx = None
                            
                            for msg in affiliation_msgs:
                                # 检查是否是独立批注标记
                                comment_match = re.match(r'__COMMENT_PARA_(\d+)__(.+)', msg)
                                if comment_match:
                                    para_num = int(comment_match.group(1))
                                    # para_num 现在是doc.paragraphs中的实际1-based索引
                                    para_idx = para_num - 1  # 转换为0-based索引用于定位
                                    comment_msg = comment_match.group(2)
                                    
                                    if para_idx not in comment_issues:
                                        comment_issues[para_idx] = []
                                    comment_issues[para_idx].append(comment_msg)
                                    continue
                                
                                msg_stripped = msg.strip()
                                is_header = not msg_stripped.startswith('- ')
                                
                                if is_header:
                                    # 标题行，尝试提取段落编号
                                    para_match = re.search(r'第(\d+)段', msg)
                                    if para_match:
                                        # 这个编号现在是实际的1-based索引（包括空行）
                                        para_num = int(para_match.group(1))
                                        current_para_idx = para_num - 1  # 转换为0-based
                                        if current_para_idx not in affiliation_by_para:
                                            affiliation_by_para[current_para_idx] = []
                                        affiliation_by_para[current_para_idx].append(msg)
                                    else:
                                        current_para_idx = None
                                        # 跳过总结性的标题（如"单位编号格式错误（共 3 处）"）
                                        if '共' not in msg and '处' not in msg:
                                            general_affiliation_msgs.append(msg)
                                else:
                                    # 子项，归入当前段落
                                    if current_para_idx is not None:
                                        affiliation_by_para[current_para_idx].append(msg)
                                    else:
                                        general_affiliation_msgs.append(msg)
                            
                            # 为每个段落的独立问题创建批注
                            for para_idx, comment_msgs in comment_issues.items():
                                # 每两条消息一组（错误描述+建议修改）
                                for i in range(0, len(comment_msgs), 2):
                                    issue_msgs = comment_msgs[i:i+2]
                                    issue_type = 'numbering' if '编号' in issue_msgs[0] else 'other'
                                    issues.append({
                                        'module': module_name,
                                        'section': section_key + f'_affiliation_para{para_idx+1}_{issue_type}',
                                        'messages': issue_msgs,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                            
                            # 为每个单位段落的其他问题创建批注（段后间距等）
                            # 只添加包含实际问题的段落
                            for para_idx, msgs in affiliation_by_para.items():
                                if any('问题' in msg or '错误' in msg for msg in msgs):
                                    issues.append({
                                        'module': module_name,
                                        'section': section_key + f'_affiliation_para{para_idx+1}_format',
                                        'messages': msgs,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                            
                            # 通用单位消息（只添加包含实际问题的消息）
                            if general_affiliation_msgs and any('问题' in msg or '错误' in msg for msg in general_affiliation_msgs):
                                issues.append({
                                    'module': module_name,
                                    'section': section_key + '_affiliations',
                                    'messages': general_affiliation_msgs,
                                    'locate_method': 'keyword',
                                    'locate_data': 'College'
                                })
                    else:
                        # 其他section默认定位到第一个段落
                        locate_method = 'index'
                        locate_data = 0
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
        
        elif module_name == 'Abstract':
            # Abstract模块：使用关键字定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details']:
                    continue
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if messages:
                        # 根据section类型决定定位策略
                        if section_key == 'structure':
                            # structure批注放在Abstract标题段落
                            locate_method = 'abstract_title'
                        else:
                            # paragraphs和format批注放在内容段落
                            locate_method = 'abstract_content'
                        
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': 'Abstract'
                        })
        
        elif module_name == 'Keywords':
            # Keywords模块：使用关键字定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details']:
                    continue
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if messages:
                        # 区分Keywords和CLC、Footnote
                        if 'clc' in section_key.lower():
                            locate_data = 'CLC number'
                            locate_method = 'keyword'
                        elif 'footnote' in section_key.lower():
                            # 脚注问题：定位到CLC行（脚注引用通常在这一行）
                            # 因为Word脚注在文档底部，无法直接定位，所以定位到引用位置
                            locate_data = 'CLC number'
                            locate_method = 'keyword'
                        elif section_key == 'structure':
                            # structure批注放在Keywords标题段落
                            locate_data = 'Keywords'
                            locate_method = 'keywords_title'
                        else:
                            # paragraphs和format批注放在内容段落
                            locate_data = 'Keywords'
                            locate_method = 'keywords_content'
                        
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
        
        elif module_name == 'Content':
            # Content模块：需要识别具体的正文段落
            hierarchy_report = report.get('hierarchy', {})
            titles = report.get('titles', [])  # 获取标题信息用于定位
            
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted', 'details', 'hierarchy', 'titles']:
                    continue
                
                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if not messages:
                        continue
                    
                    # 特殊处理content_format：按段落分组
                    if section_key == 'content_format':
                        # 将消息按段落编号分组
                        grouped_messages = group_messages_by_paragraph(messages)
                        
                        # 为每个段落创建独立的批注issue
                        for para_num, para_messages in grouped_messages.items():
                            if para_num is not None:
                                # 有段落编号，需要定位到具体的正文段落
                                # 使用特殊的定位方法：content_paragraph
                                issues.append({
                                    'module': module_name,
                                    'section': f'{section_key}_para{para_num}',
                                    'messages': para_messages,
                                    'locate_method': 'content_paragraph',
                                    'locate_data': para_num,  # 段落编号（1-based）
                                    'extra': {
                                        'hierarchy_report': hierarchy_report  # 传递标题信息
                                    }
                                })
                            # 忽略没有段落编号的消息（如标题行）
                    
                    elif section_key in ['format', 'case']:
                        # 标题format和case问题：按标题分组定位
                        # 从messages中提取标题名称，定位到具体标题段落
                        grouped_title_messages = group_messages_by_title(messages, titles)
                        
                        for title_text, title_messages in grouped_title_messages.items():
                            if title_text and title_messages:
                                # 在titles列表中查找对应的标题
                                title_info = next((t for t in titles if t.get('text') == title_text), None)
                                if title_info and 'paragraph_index' in title_info:
                                    # 直接使用paragraph_index定位，更准确
                                    para_idx = title_info.get('paragraph_index')
                                    # 为每个标题创建单独的批注，使用唯一的section名称
                                    clean_title = re.sub(r'[^\w]', '_', title_text[:20])  # 清理标题用作section名称
                                    issues.append({
                                        'module': module_name,
                                        'section': f'{section_key}_{clean_title}',
                                        'messages': title_messages,
                                        'locate_method': 'index',
                                        'locate_data': para_idx
                                    })
                                elif title_text:
                                    # 如果没有索引，尝试用完整标题文本（包括编号）定位
                                    full_title_text = title_info.get('full_text', title_text) if title_info else title_text
                                    clean_title = re.sub(r'[^\w]', '_', title_text[:20])
                                    issues.append({
                                        'module': module_name,
                                        'section': f'{section_key}_{clean_title}',
                                        'messages': title_messages,
                                        'locate_method': 'text',
                                        'locate_data': full_title_text
                                    })
                    else:
                        # 其他section（如hierarchy）使用Introduction定位
                        issues.append({
                            'module': module_name,
                            'section': section_key,
                            'messages': messages,
                            'locate_method': 'keyword',
                            'locate_data': 'Introduction'
                        })
        
        elif module_name == 'Formula':
            # Formula模块：根据报告中的公式段落信息进行定位
            for section_key, section_value in report.items():
                if section_key in ['summary', 'extracted']:
                    continue

                if section_key == 'symbol_definition':
                    details = report.get('details', {})
                    symbol_def_details = details.get('symbol_definition', {})
                    per_formula = symbol_def_details.get('per_formula', []) if isinstance(symbol_def_details, dict) else []

                    for pf in per_formula:
                        if not isinstance(pf, dict):
                            continue

                        missing = pf.get('missing_symbols', []) or []
                        warnings = pf.get('warnings', []) or []
                        suspected = pf.get('suspected_explained_symbols', []) or []
                        if (not missing) and (not warnings) and (not suspected):
                            continue

                        formula_number = pf.get('formula_number')
                        para_idx_1based = pf.get('paragraph_index')

                        if isinstance(formula_number, str) and formula_number.strip():
                            section_suffix = re.sub(r'[^\w]', '_', formula_number.strip())
                        else:
                            section_suffix = f"para{pf.get('index', i)}"

                        formula_text = pf.get('formula_text', '')
                        if isinstance(formula_text, str):
                            formula_snippet = formula_text.strip()
                            if len(formula_snippet) > 140:
                                formula_snippet = formula_snippet[:140] + '...'
                        else:
                            formula_snippet = ''

                        evidence = pf.get('evidence', {}) if isinstance(pf.get('evidence', {}), dict) else {}

                        def _append_issue(issue_section: str, issue_messages: list):
                            if isinstance(para_idx_1based, int) and para_idx_1based >= 1:
                                issues.append({
                                    'module': module_name,

                                    'section': issue_section,
                                    'messages': issue_messages,
                                    'locate_method': 'index',
                                    'locate_data': para_idx_1based - 1
                                })
                            elif isinstance(formula_number, str) and formula_number.strip():
                                issues.append({
                                    'module': module_name,
                                    'section': issue_section,
                                    'messages': issue_messages,
                                    'locate_method': 'formula_number',
                                    'locate_data': formula_number.strip()
                                })

                        if missing:
                            pf_messages = [
                                "[类型] error",
                                f"[描述] 符号首次出现未说明: {', '.join(missing)}",
                                f"[建议] 建议在公式附近使用 where/denotes/其中… 等规范句式逐一定义: {', '.join(missing)}",
                            ]
                            if formula_snippet:
                                pf_messages.append(f"[片段] {formula_snippet}")
                            for sym in missing[:2]:
                                ev = evidence.get(sym)
                                if isinstance(ev, str) and ev.strip():
                                    pf_messages.append(f"[证据] {sym}: {ev.strip()}")

                            _append_issue(f"symbol_definition_error_{section_suffix}", pf_messages)

                        if suspected:
                            pf_messages = [
                                "[类型] warning",
                                f"[描述] 符号疑似已说明（非标准定义句式）: {', '.join(suspected)}",
                                "[建议] 建议补充规范定义句式（where/denotes/其中…），避免歧义。",
                            ]
                            if formula_snippet:
                                pf_messages.append(f"[片段] {formula_snippet}")
                            for sym in suspected[:2]:
                                ev = evidence.get(sym)
                                if isinstance(ev, str) and ev.strip():
                                    pf_messages.append(f"[证据] {sym}: {ev.strip()}")

                            _append_issue(f"symbol_definition_suspected_{section_suffix}", pf_messages)

                        if isinstance(warnings, list) and warnings:
                            w_msgs = []
                            for w in warnings[:5]:
                                if w:
                                    desc = str(w)
                                    if desc.startswith('复合符号已说明但未单独说明基符号'):
                                        suggest = '建议在首次出现处单独定义基符号（如 c、k），或按模板要求使用单字母符号。'
                                    elif desc.startswith('复合符号未说明'):
                                        suggest = '建议在首次出现处补充对该符号的文字说明。'
                                    elif desc.startswith('符号疑似已说明'):
                                        suggest = '建议补充规范定义句式（where/denotes/其中…），避免歧义。'
                                    else:
                                        suggest = '建议按模板规范补充符号说明。'
                                    w_msgs.append("[类型] warning")
                                    w_msgs.append(f"[描述] {desc}")
                                    w_msgs.append(f"[建议] {suggest}")
                                    if formula_snippet:
                                        w_msgs.append(f"[片段] {formula_snippet}")
                            if w_msgs:
                                _append_issue(f"symbol_definition_warning_{section_suffix}", w_msgs)

                    continue

                if isinstance(section_value, dict) and not section_value.get('ok', False):
                    messages = section_value.get('messages', [])
                    if not messages:
                        continue

                    # 尝试从details中获取公式段落信息
                    details = report.get('details', {})
                    formula_paragraphs = details.get('formula_paragraphs', [])

                    if formula_paragraphs:
                        # 如果有公式段落信息，使用第一个公式段落的文本片段定位
                        first_formula = formula_paragraphs[0]
                        text_preview = first_formula.get('text_preview', '')

                        # 从文本中提取公式编号，如 (1)、(2) 等
                        # 公式编号通常在文本末尾
                        number_match = re.search(r'\((\d+)\)\s*$', text_preview)

                        if number_match:
                            # 使用公式编号定位
                            formula_number = number_match.group(0).strip()  # 如 "(2)"
                            issues.append({
                                'module': module_name,
                                'section': section_key,
                                'messages': messages,
                                'locate_method': 'formula_number',  # 新的定位方法
                                'locate_data': formula_number,
                                'extra': {
                                    'text_preview': text_preview  # 保存完整预览用于备用
                                }
                            })
                        else:
                            # 如果没有公式编号，尝试使用文本末尾的部分
                            # 只取最后的一小段（可能包含编号或特征）
                            locate_text = text_preview[-20:].strip() if len(text_preview) > 20 else text_preview

                            if locate_text and len(locate_text) >= 3:
                                issues.append({
                                    'module': module_name,
                                    'section': section_key,
                                    'messages': messages,
                                    'locate_method': 'text',
                                    'locate_data': locate_text
                                })
                            else:
                                print(f"  ! Formula模块无法定位批注（文本不足）")
                    else:
                        # 如果没有找到公式段落，说明文档中可能没有公式
                        # 不添加批注，因为无法准确定位
                        print(f"  ! Formula模块未检测到公式段落，跳过批注")
        
        elif module_name == 'Table':
            # Table模块：定位到表格标题段落
            # 1. 处理numbering问题（表格编号连续性）
            numbering_report = report.get('numbering', {})
            if isinstance(numbering_report, dict) and not numbering_report.get('ok', False):
                messages = numbering_report.get('messages', [])
                if messages:
                    # 定位到第一个表格标题
                    details = report.get('details', {})
                    caption_info_list = details.get('caption_info', [])
                    if caption_info_list:
                        first_caption = caption_info_list[0]
                        caption_text = first_caption.get('text', 'Table')
                        caption_para_idx = first_caption.get('paragraph_index')
                        if isinstance(caption_para_idx, int):
                            locate_method = 'index_including_empty'
                            locate_data = caption_para_idx
                        else:
                            locate_method = 'keyword'
                            locate_data = caption_text[:20]
                        issues.append({
                            'module': module_name,
                            'section': 'numbering',
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
            
            # 2. 处理每个表格的问题
            tables_report = report.get('tables', [])
            
            # Fallback: 如果tables列表为空，但有errors，则从errors中生成批注
            if not tables_report and report.get('errors'):
                print(f"  ! Table模块：使用fallback模式从errors生成批注")
                
                # 为每个error独立创建一个issue，以便精确定位到各个表格标题
                for err in report.get('errors', []):
                    desc = err.get('description', '')
                    snippet = err.get('text_snippet', '')
                    
                    if desc:
                        # 使用text_snippet前30字符精确定位标题
                        locate_keyword = snippet[:30] if snippet and snippet != 'N/A' and snippet != '...' else 'Table '
                        
                        issues.append({
                            'module': module_name,
                            'section': f'table_error_{len(issues)}',  # 使用唯一标识避免重复
                            'messages': [f"• {desc}"],
                            'locate_method': 'keyword',
                            'locate_data': locate_keyword
                        })
            else:
                # 正常处理每个表格
                for i, table_report in enumerate(tables_report):
                    caption_info = table_report.get('caption', {})
                    caption_text = caption_info.get('text', f'Table {i+1}')
                    caption_para_idx = caption_info.get('paragraph_index')

                    if isinstance(caption_para_idx, int):
                        locate_method = 'index_including_empty'
                        locate_data = caption_para_idx
                    else:
                        locate_method = 'keyword'
                        locate_data = caption_text[:20]
                    
                    # 检查标题格式
                    caption_format = table_report.get('caption_format', {})
                    if isinstance(caption_format, dict) and not caption_format.get('ok', False):
                        messages = caption_format.get('messages', [])
                        if messages:
                            issues.append({
                                'module': module_name,
                                'section': f'table{i+1}_caption',
                                'messages': messages,
                                'locate_method': locate_method,
                                'locate_data': locate_data
                            })
                    
                    # 检查表格样式
                    table_style = table_report.get('table_style', {})
                    if isinstance(table_style, dict) and not table_style.get('ok', False):
                        messages = table_style.get('messages', [])
                        if messages:
                            issues.append({
                                'module': module_name,
                                'section': f'table{i+1}_style',
                                'messages': messages,
                                'locate_method': locate_method,
                                'locate_data': locate_data
                            })

                    # 检查表格对齐
                    table_alignment = table_report.get('table_alignment', {})
                    if isinstance(table_alignment, dict) and not table_alignment.get('ok', False):
                        messages = table_alignment.get('messages', [])
                        if messages:
                            issues.append({
                                'module': module_name,
                                'section': f'table{i+1}_alignment',
                                'messages': messages,
                                'locate_method': locate_method,
                                'locate_data': locate_data
                            })

        elif module_name == 'Figure':
            # Figure模块：定位到图片标题段落（类似Table模块）
            # 1. 处理numbering问题（图片编号连续性）
            numbering_report = report.get('numbering', {})
            if isinstance(numbering_report, dict) and not numbering_report.get('ok', False):
                messages = numbering_report.get('messages', [])
                if messages:
                    # 定位到第一个图片标题
                    captions = report.get('captions', [])
                    if captions:
                        first_caption = captions[0]
                        caption_text = first_caption.get('full_text', 'Fig.')
                        caption_para_idx = first_caption.get('paragraph_index')
                        if isinstance(caption_para_idx, int):
                            locate_method = 'index_including_empty'
                            locate_data = caption_para_idx
                        else:
                            locate_method = 'keyword'
                            locate_data = caption_text[:20]
                        issues.append({
                            'module': module_name,
                            'section': 'numbering',
                            'messages': messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
            
            # 2. 处理每张图片的问题（支持新的报告结构）
            figures = report.get('figures', [])
            
            # Fallback: 如果figures列表为空，但有errors，则从errors中生成批注
            if not figures and report.get('errors'):
                print(f"  ! Figure模块：使用fallback模式从errors生成批注")
                
                # 按图片编号分组errors
                from collections import defaultdict
                errors_by_fig = defaultdict(list)
                general_errors = []
                
                for err in report.get('errors', []):
                    desc = err.get('description', '')
                    snippet = err.get('text_snippet', 'N/A')
                    
                    # 尝试从描述中提取图片编号
                    fig_match = re.match(r'Fig\.(\d+)', desc) or re.match(r'Fig\.(\d+)', snippet)
                    if fig_match:
                        fig_num = int(fig_match.group(1))
                        errors_by_fig[fig_num].append(f"• {desc}")
                    elif re.search(r'第(\d+)张图片', desc):
                        fig_match = re.search(r'第(\d+)张图片', desc)
                        fig_num = int(fig_match.group(1))
                        errors_by_fig[fig_num].append(f"• {desc}")
                    else:
                        general_errors.append(f"• {desc}")
                
                # 为每个图片编号创建批注
                for fig_num in sorted(errors_by_fig.keys()):
                    messages = errors_by_fig[fig_num]
                    
                    # 查找对应错误的text_snippet作为定位关键字
                    # text_snippet通常包含标题文本（如"Fig. 2 Dynamic model..."）
                    locate_keyword = None
                    for err in report.get('errors', []):
                        desc = err.get('description', '')
                        snippet = err.get('text_snippet', '')
                        if f'Fig.{fig_num}' in desc and snippet and snippet != 'N/A':
                            # 使用标题文本的前30字符，这样能精确匹配标题段落
                            locate_keyword = snippet[:30]
                            break
                    
                    # 如果没有找到有效的snippet，回退到 'Fig. X ' （注意末尾空格，避免匹配Fig. X1）
                    if not locate_keyword:
                        locate_keyword = f'Fig. {fig_num} '
                    
                    issues.append({
                        'module': module_name,
                        'section': f'figure{fig_num}_errors',
                        'messages': messages,
                        'locate_method': 'keyword',
                        'locate_data': locate_keyword
                    })
                
                # 通用错误（如编号连续性）定位到第一个图片标题
                if general_errors:
                    issues.append({
                        'module': module_name,
                        'section': 'figure_general_errors',
                        'messages': general_errors,
                        'locate_method': 'keyword',
                        'locate_data': 'Fig. 1 '  # 定位到第一个标题（注意末尾空格）
                    })
            else:
                # 正常处理每张图片
                for fig_report in figures:
                    fig_idx = fig_report.get('figure_index', 0)
                    para_idx = fig_report.get('paragraph_index', 0)
                    
                    # 获取标题信息（如果有）
                    has_caption = fig_report.get('has_caption', False)
                    caption_info = fig_report.get('caption_info') if has_caption else None
                    
                    # 标题相关的问题 → 批注在标题段落
                    caption_messages = []
                    format_check = fig_report.get('format_check', {})
                    if isinstance(format_check, dict) and not format_check.get('ok', False):
                        caption_messages.extend(format_check.get('messages', []))
                    
                    if caption_messages and has_caption:
                        # 批注在标题上
                        caption_text = caption_info.get('full_text', f'Fig.{caption_info.get("number", fig_idx)}')[:30]
                        caption_para_idx = caption_info.get('paragraph_index') if isinstance(caption_info, dict) else None
                        if isinstance(caption_para_idx, int):
                            locate_method = 'index_including_empty'
                            locate_data = caption_para_idx
                        else:
                            locate_method = 'keyword'
                            locate_data = caption_text
                        issues.append({
                            'module': module_name,
                            'section': f'figure{fig_idx}_caption',
                            'messages': caption_messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })
                    
                    # 图片本身的问题 → 批注在图片段落
                    picture_messages = []
                    
                    # 图片对齐等问题
                    picture_check = fig_report.get('picture_check', {})
                    if isinstance(picture_check, dict) and not picture_check.get('ok', False):
                        picture_messages.extend(picture_check.get('messages', []))
                    
                    # 图表内容问题
                    content_check = fig_report.get('content_check', {})
                    if isinstance(content_check, dict) and not content_check.get('ok', False):
                        if content_check.get('is_chart', False):
                            picture_messages.extend(content_check.get('messages', []))
                    
                    if picture_messages:
                        # 批注在图片段落（使用段落索引）
                        if isinstance(para_idx, int) and para_idx >= 0:
                            locate_method = 'index_including_empty'
                            locate_data = para_idx
                        elif isinstance(caption_info, dict) and isinstance(caption_info.get('paragraph_index'), int):
                            locate_method = 'index_including_empty'
                            locate_data = caption_info.get('paragraph_index')
                        else:
                            locate_method = 'keyword'
                            locate_data = (caption_info.get('full_text', 'Fig.')[:20] if isinstance(caption_info, dict) else 'Fig.')

                        issues.append({
                            'module': module_name,
                            'section': f'figure{fig_idx}_picture',
                            'messages': picture_messages,
                            'locate_method': locate_method,
                            'locate_data': locate_data
                        })

        elif module_name == 'Chinese_section':
            # 为中文部分的每个子项添加精确定位
            details = report.get('details', {})
            for section_key, section_value in report.items():
                if section_key in ['summary', 'affiliations_detail', 'details'] or not isinstance(section_value, dict) or section_value.get('ok', True):
                    continue

                messages = section_value.get('messages', [])
                if not messages:
                    continue

                locate_method = 'index'
                locate_data = None

                if section_key == 'chinese_title_format':
                    locate_data = details.get('title_index')
                elif section_key == 'chinese_author_format':
                    locate_data = details.get('author_index')
                elif section_key == 'chinese_affiliation_format':
                    locate_data = details.get('affiliation_index')
                elif section_key == 'chinese_abstract_format':
                    locate_data = details.get('abstract_index')
                elif section_key == 'chinese_keywords_format':
                    locate_data = details.get('keywords_index')

                # 兼容旧结构：如果details缺失索引，回退到keyword定位
                if locate_data is None:
                    locate_method = 'keyword'
                    locate_data = ''

                    if section_key == 'chinese_title_format':
                        # 从报告的 'details' 中获取标题文本用于定位
                        title_text = report.get('details', {}).get('title_text', '')
                        locate_data = title_text[:30] if title_text else '用于高效电催化析氢反应'
                    elif section_key == 'chinese_author_format':
                        locate_data = '刘   影'
                    elif section_key == 'chinese_affiliation_format':
                        locate_data = '东华大学'
                    elif section_key == 'chinese_abstract_format':
                        locate_data = '摘   要'
                    elif section_key == 'chinese_keywords_format':
                        locate_data = '关键词'

                if locate_data is not None and locate_data != '':
                    issues.append({
                        'module': module_name,
                        'section': section_key,
                        'messages': messages,
                        'locate_method': locate_method,
                        'locate_data': locate_data
                    })

    # 单独处理分类号不一致的批注
    if 'Classification' in all_reports:
        class_report = all_reports['Classification']

        if class_report.get('match_status') == '不一致':
            messages = [
                f"API建议分类号与原文不一致。",
                f"原文分类号: {class_report.get('original_clc', 'N/A')}",
                f"API建议分类号: {class_report.get('code', 'N/A')} (原始: {class_report.get('raw_code', 'N/A')})",
                "请根据API提供的分类理由进行核对。"
            ]
            issues.append({
                'module': 'Classification',
                'section': 'mismatch',
                'messages': messages,
                'locate_method': 'keyword',
                'locate_data': 'CLC number'
            })
    
    # 添加从新格式直接生成的issues
    issues.extend(new_format_issues)

    return issues


def find_content_paragraph_by_number(doc, para_number, hierarchy_report):
    """
    根据段落编号定位具体的正文段落
    
    参数：
        doc: Document对象
        para_number: 段落编号（1-based，如"正文段落 1"中的1）
        hierarchy_report: 标题层级报告（包含标题段落索引信息）
    
    返回：
        对应的段落对象，未找到返回None
    """
    # 获取所有标题段落的索引
    title_paragraph_indices = set()
    introduction_index = None
    
    if hierarchy_report and hierarchy_report.get('titles'):
        for title_info in hierarchy_report['titles']:
            if 'paragraph_index' in title_info:
                idx = title_info['paragraph_index']
                title_paragraph_indices.add(idx)
                # 找到Introduction段落索引
                if title_info['level'] == 0 and title_info['text'] == 'Introduction':
                    introduction_index = idx
    
    # 如果没有找到Introduction，尝试用关键字查找
    if introduction_index is None:
        for i, para in enumerate(doc.paragraphs):
            if para.text and 'Introduction' in para.text:
                introduction_index = i
                break
    
    if introduction_index is None:
        return None
    
    # 从Introduction之后开始查找正文段落
    content_paragraph_count = 0
    
    for i in range(introduction_index + 1, len(doc.paragraphs)):
        paragraph = doc.paragraphs[i]
        
        # 排除标题段落
        if i in title_paragraph_indices:
            continue
        
        # 检查是否为有效正文段落（与Content_detect.py逻辑一致）
        text = paragraph.text.strip() if paragraph.text else ""
        if not text or len(text) <= 20:
            continue
        
        # 排除表格标题、图片标题等
        text_lower = text.lower()
        if (text_lower.startswith('table ') or 
            text_lower.startswith('figure ') or 
            text_lower.startswith('fig.') or
            text_lower.startswith('图 ') or 
            text_lower.startswith('表 ') or
            re.match(r'^(表|图|Table|Figure)\s*\d+', text, re.IGNORECASE)):
            continue
        
        # 排除居中对齐的短段落（可能是标题或表格标题）
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        alignment = paragraph.alignment
        if alignment is not None and alignment == WD_PARAGRAPH_ALIGNMENT.CENTER and len(text) < 80:
            continue
        
        # 这是有效的正文段落
        content_paragraph_count += 1
        
        # 找到目标段落
        if content_paragraph_count == para_number:
            return paragraph
    
    return None


def add_all_comments(doc_path, copy_path, issues_list):
    """
    在文档副本上添加所有批注
    
    参数：
        doc_path: 原始文档路径（用于对比）
        copy_path: 副本文档路径
        issues_list: 问题列表
    
    返回：
        成功添加的批注数量
    """
    try:
        doc = Document(copy_path)
        comment_count = 0
        
        print(f"\n正在添加批注...")
        print(f"  共有 {len(issues_list)} 个问题需要批注")
        
        for issue in issues_list:
            module_name = issue['module']
            section_name = issue['section']
            messages = issue['messages']
            locate_method = issue['locate_method']
            locate_data = issue['locate_data']
            extra = issue.get('extra', {})
            
            # 根据定位方法查找段落
            paragraph = None
            if locate_method == 'keyword' and locate_data:
                paragraph = find_paragraph_by_keyword(doc, locate_data)
            elif locate_method == 'abstract_title':
                # 定位到Abstract标题段落（用于structure批注）
                # 先尝试正确格式
                paragraph = find_paragraph_by_keyword(doc, 'Abstract:')
                if not paragraph:
                    # 尝试错误格式（Abstract单独成行）
                    for para in doc.paragraphs:
                        if para.text and re.match(r'^\s*Abstract\s*$', para.text.strip(), re.IGNORECASE):
                            paragraph = para  # 定位到标题段落本身
                            break
            elif locate_method == 'abstract_content':
                # 定位到Abstract内容段落（用于paragraphs和format批注）
                # 先尝试正确格式
                paragraph = find_paragraph_by_keyword(doc, 'Abstract:')
                if not paragraph:
                    # 尝试错误格式（Abstract单独成行，定位到下一个内容段落）
                    for i, para in enumerate(doc.paragraphs):
                        if para.text and re.match(r'^\s*Abstract\s*$', para.text.strip(), re.IGNORECASE):
                            # 找到Abstract单独一行，定位到下一个非空段落（实际内容）
                            for j in range(i+1, min(i+3, len(doc.paragraphs))):
                                if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
                                    paragraph = doc.paragraphs[j]
                                    break
                            break
            elif locate_method == 'keywords_title':
                # 定位到Keywords标题段落（用于structure批注）
                # 先尝试正确格式
                paragraph = find_paragraph_by_keyword(doc, 'Keywords:')
                if not paragraph:
                    # 尝试错误格式（Keywords单独成行）
                    for para in doc.paragraphs:
                        if para.text and re.match(r'^\s*Keywords\s*$', para.text.strip(), re.IGNORECASE):
                            paragraph = para  # 定位到标题段落本身
                            break
            elif locate_method == 'keywords_content':
                # 灵活定位Keywords：优先找Keywords:，找不到就找Keywords（单独一行）
                # 先尝试正确格式
                paragraph = find_paragraph_by_keyword(doc, 'Keywords:')
                if not paragraph:
                    # 尝试错误格式（Keywords单独成行）
                    for i, para in enumerate(doc.paragraphs):
                        if para.text and re.match(r'^\s*Keywords\s*$', para.text.strip(), re.IGNORECASE):
                            # 找到Keywords单独一行，定位到下一个非空段落（实际内容）
                            for j in range(i+1, min(i+3, len(doc.paragraphs))):
                                if doc.paragraphs[j].text and doc.paragraphs[j].text.strip():
                                    paragraph = doc.paragraphs[j]
                                    break
                            break
            elif locate_method == 'index':
                # 判断是否需要跳过空行
                # 单位段落和Content标题格式批注都不应该跳过空行（使用实际索引）
                skip_empty = (
                    module_name not in ['Figure', 'Chinese_section', 'Formula']
                    and 'affiliation_para' not in section_name
                    and 'Content-format' not in f"{module_name}-{section_name}"
                    and 'Content-case' not in f"{module_name}-{section_name}"
                )
                if extra.get('skip_empty') is False:
                    skip_empty = False
                paragraph = find_paragraph_by_index(doc, locate_data, skip_empty=skip_empty)
            elif locate_method == 'text':
                paragraph = find_paragraph_by_text(doc, locate_data)
            elif locate_method == 'paragraph_object':
                paragraph = locate_data  # 直接使用paragraph对象
            elif locate_method == 'content_paragraph':
                # 定位到具体的正文段落
                hierarchy_report = extra.get('hierarchy_report', {})
                paragraph = find_content_paragraph_by_number(doc, locate_data, hierarchy_report)
            elif locate_method == 'formula_number':
                # 通过公式编号定位（如 "(2)"）
                paragraph = find_paragraph_by_keyword(doc, locate_data)
            elif locate_method == 'index_including_empty':
                paragraph = find_paragraph_by_index(doc, locate_data, skip_empty=False)
            
            if paragraph:
                # 构建批注内容
                comment_text = f"[{module_name}-{section_name}]\n"
                for msg in messages:
                    comment_text += f"• {msg}\n"
                
                # 添加批注
                if add_comment_to_paragraph(doc, paragraph, comment_text.strip()):
                    comment_count += 1
                    print(f"  ✓ 已添加批注: {module_name}-{section_name}")
            else:
                print(f"  ✗ 无法定位段落: {module_name}-{section_name} (方法:{locate_method}, 数据:{locate_data})")
        
        # 保存文档
        doc.save(copy_path)
        print(f"\n✓ 成功添加 {comment_count} 个批注")
        print(f"✓ 批注文档已保存: {copy_path}")
        
        return comment_count
    
    except Exception as e:
        print(f"\n✗ 添加批注过程出错: {e}")
        return 0


def main():
    """主函数"""
    print("=" * 60)
    print("论文格式检测系统 - 集成检测工具")
    print("=" * 60)
    
    # 解析命令行参数
    docx_path, detection_config = parse_arguments()
    print(f"\n待检测文件: {docx_path}")
    
    if not detection_config['enable_figure_api']:
        print("注意：图片内容API检测已禁用（使用 --enable-figure-api 启用）")
    
    # 设置全局检测配置（必须在导入模块之前）
    global GLOBAL_DETECTION_CONFIG
    GLOBAL_DETECTION_CONFIG['skip_checks'] = detection_config['skip_checks']
    
    # 导入检测模块
    print("\n正在加载检测模块...")
    detection_functions = import_detection_modules()
    
    # 构建模块启用配置
    module_config = {}
    for module_name in DETECTION_ORDER:
        # 如果模块在skip_modules中，则禁用
        module_config[module_name] = module_name not in detection_config['skip_modules']
    
    # 执行所有检测
    all_reports = run_all_detections(
        docx_path, 
        detection_functions, 
        enable_figure_api=detection_config['enable_figure_api'],
        detection_config=module_config
    )

    # 在所有常规检测完成后，独立执行分类号检测
    if detection_config['enable_classification_api']:
        print("\n【摘要分类号 检测】")
        try:
            all_reports = detect_classification(all_reports)
            classification_report = all_reports.get('Classification', {})
            if 'error' in classification_report:
                print(f"  ✗ 检测失败: {classification_report['error']}")
            else:
                print(f"  ✓ API 提取分类号: {classification_report.get('code', 'N/A')}")
                print(f"    原文中的分类号: {classification_report.get('original_clc', '未找到')}")
                match_status = classification_report.get('match_status', '未知')
                status_icon = '✓' if match_status == '一致' else '✗' if match_status == '不一致' else '?'
                print(f"    对比结果: {status_icon} {match_status}")
        except Exception as e:
            print(f"  ✗ 检测失败: {e}")
            all_reports['Classification'] = {'error': f'分类号检测失败: {e}'}
    
    # 生成综合报告
    print("\n正在生成综合报告...")
    report_docx_path = docx_path if detection_config.get('enable_page_numbers', True) else None
    report_text = generate_comprehensive_report(all_reports, docx_path=report_docx_path)
    
    # 保存txt报告（放在与原文件相同的目录）
    dir_path = os.path.dirname(docx_path)
    base_name = os.path.splitext(os.path.basename(docx_path))[0]
    report_filename = f"{base_name}_report.txt"
    report_path = os.path.join(dir_path, report_filename) if dir_path else report_filename
    save_report_to_file(report_text, report_path)
    
    # 生成Word格式报告
    print("\n正在生成Word格式报告...")
    word_report_filename = f"{base_name}_report.docx"
    word_report_path = os.path.join(dir_path, word_report_filename) if dir_path else word_report_filename
    
    try:
        from paper_detect.word_report_generator import generate_word_report
        word_success = generate_word_report(all_reports, word_report_path, docx_path)
        if not word_success:
            print("  ⚠️ Word报告生成失败，但txt报告已生成")
    except Exception as e:
        print(f"  ⚠️ Word报告生成出错: {e}")
        print("  txt报告已正常生成")
    
    # 创建文档副本
    print("\n正在创建文档副本...")
    copy_path = create_document_copy(docx_path)
    
    if copy_path:
        # 从报告中提取问题
        print("\n正在分析问题...")
        issues_list = parse_issues_from_reports(all_reports)
        print(f"  共识别出 {len(issues_list)} 个问题")
        
        # 添加批注
        if issues_list:
            comment_count = add_all_comments(docx_path, copy_path, issues_list)
            if comment_count > 0:
                print(f"\n✓ 批注添加完成！共添加 {comment_count} 个批注")
        else:
            print("\n✓ 未发现问题，无需添加批注")
    
    print("\n" + "=" * 60)
    print("检测流程完成")
    print("=" * 60)
    print(f"\n输出文件：")
    print(f"  1. 文本报告: {report_path}")
    print(f"  2. Word报告: {word_report_path}")
    if copy_path:
        print(f"  3. 批注文档: {copy_path}")
    print("")


if __name__ == '__main__':
    main()

# python run_all_detections.py template/test.docx --enable-figure-api