"""
论文格式检测服务
服务层封装，调用核心检测器 paper_format_detector.py
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

from services.paper_format_detector import PaperFormatDetector
from services.Chinese_paper_format_detector import ChinesePaperFormatDetector
from services.document_annotator import generate_annotated_document, create_document_copy, parse_issues_from_reports, add_all_comments
# 新的中文注释引擎（并行使用，暂不删除旧实现）
from services.chinese_annotation_engine import annotate_chinese_abstract_and_keywords
from services.paper_detect.Classification_detect import detect_classification

logger = logging.getLogger(__name__)

DETECTION_ORDER = ['Title', 'Abstract', 'English_Abstract', 'Keywords', 'Content', 'Formula', 'TOC', 'Figure', 'Table', 'References', 'Chinese_section']

# 模块中文名称映射
MODULE_NAMES_CN = {
    'Title': '标题',
    'Abstract': '摘要',
    'English_Abstract': '英文摘要',
    'Keywords': '关键词',
    'Content': '正文',
    'Formula': '公式',
    'TOC': '目录/图录/表录',
    'Figure': '图',
    'Table': '表格',
    'References': '参考文献',
    'Chinese_section': '中文部分',
    'Classification': '摘要分类号',
    # 中文部分内部项目
    'chinese_title_format': '中文标题',
    'chinese_author_format': '中文作者',
    'chinese_affiliation_format': '中文单位',
    'chinese_abstract_format': '中文摘要',
    'chinese_keywords_format': '中文关键词',
}

# 检查项 key → 中文标签映射（用于前端折叠栏和文本报告）
CHECK_NAMES_CN = {
    # === 通用 ===
    'structure': '[结构]',
    'format': '[格式]',

    # === Title / Abstract / English_Abstract / Keywords ===
    'title_format': '[标题格式]',
    'content_format': '[内容格式]',

    # === Formula ===
    'formula_detection': '[公式检测]',
    'numbering': '[编号]',

    # === TOC ===
    'toc_format': '[目录格式]',
    'figure_list_format': '[图录格式]',
    'table_list_format': '[表录格式]',
    # TOC format 分段（title_type: 图录/目录/表录）
    'format_图录': '[图录格式]',
    'format_目录': '[目录格式]',
    'format_表录': '[表录格式]',

    # === Figure ===
    'figure_detection': '[图检测]',

    # === Table ===
    'table_detection': '[表格检测]',

    # === References ===
    'references_structure': '[结构]',
    'references_content': '[格式]',
    'references_header': '[标题格式]',

    # === 双语模块前缀（Keywords / Title） ===
    'chinese_structure': '[结构]',
    'chinese_format': '[格式]',
    'chinese_title_format': '[标题格式]',
    'chinese_content_format': '[内容格式]',
    'english_structure': '[结构]',
    'english_format': '[格式]',
    'english_title_format': '[标题格式]',
    'english_content_format': '[内容格式]',

    # === Chinese_section ===
    'chinese_title_format': '[中文标题格式]',
    'chinese_author_format': '[中文作者格式]',
    'chinese_affiliation_format': '[中文单位格式]',
    'chinese_abstract_format': '[中文摘要格式]',
    'chinese_keywords_format': '[中文关键词格式]',
}

# class PaperFormatService:
#     """
#     论文格式检测服务类
    
#     提供统一的论文格式检查接口，支持：
#     - 标题格式检测 (Title)
#     - 摘要格式检测 (Abstract)
#     - 关键词格式检测 (Keywords)
#     - 正文格式检测 (Content)
#     - 图片格式检测 (Figure)
#     - 公式格式检测 (Formula)
#     - 表格格式检测 (Table)
#     - 全量检测 (All)
#     - 报告生成
#     """
    
#     def __init__(self):
#         """初始化服务"""
#         try:
#             # 初始化检测器
#             templates_dir = 'paper_detect_templates'
#             self.detector = PaperFormatDetector(templates_dir=str(templates_dir))
#             logger.info(f"论文格式检测服务已初始化")
#         except Exception as e:
#             logger.error(f"初始化检测服务失败: {e}")
#             raise
    
#     def _format_response(self, success: bool, data: Any = None, 
#                         message: str = '', status_code: int = 200) -> Dict[str, Any]:
#         """格式化标准响应"""
#         return {
#             'success': success,
#             'data': data,
#             'message': message,
#             'status_code': status_code
#         }
    
#     def _make_json_serializable(self, obj: Any) -> Any:
#         """
#         递归地将对象转换为JSON可序列化的格式
#         处理python-docx的Paragraph对象和其他不可序列化的对象
#         """
#         if obj is None:
#             return None
        
#         # 处理基本类型
#         if isinstance(obj, (str, int, float, bool)):
#             return obj
        
#         # 处理列表
#         if isinstance(obj, list):
#             return [self._make_json_serializable(item) for item in obj]
        
#         # 处理字典
#         if isinstance(obj, dict):
#             return {key: self._make_json_serializable(value) for key, value in obj.items()}
        
#         # 处理Paragraph对象和其他复杂对象
#         # 尝试获取对象的文本表示
#         try:
#             # 如果是Paragraph对象，获取其text属性
#             if hasattr(obj, 'text'):
#                 return str(obj.text)
#             # 如果有__dict__属性，尝试序列化为字典
#             elif hasattr(obj, '__dict__'):
#                 return self._make_json_serializable(obj.__dict__)
#             # 其他情况转换为字符串
#             else:
#                 return str(obj)
#         except Exception as e:
#             logger.warning(f"对象序列化失败: {type(obj)}, {e}")
#             return str(obj)
    
#     def _normalize_report(self, report: Dict[str, Any], module_name: str) -> Dict[str, Any]:
#         """标准化检测报告格式"""
#         if not report:
#             return {
#                 'module': module_name,
#                 'checks': {},
#                 'summary': [],
#                 'extracted': {},
#                 'details': {}
#             }
        
#         # 处理错误报告
#         if report.get('error'):
#             return {
#                 'module': module_name,
#                 'checks': {},
#                 'summary': report.get('summary', []),
#                 'extracted': {},
#                 'details': {},
#                 'error': True,
#                 'error_message': report.get('error_message', '')
#             }
        
#         # 提取summary、extracted和details
#         summary = report.pop('summary', []) if isinstance(report, dict) else []
#         extracted = report.pop('extracted', {}) if isinstance(report, dict) else {}
#         details = report.pop('details', {}) if isinstance(report, dict) else {}
        
#         # 剩余的都是检查项
#         checks = {k: v for k, v in report.items() if isinstance(v, dict) and 'ok' in v}
        
#         # 如果没有检查项，保留原始结构
#         if not checks and isinstance(report, dict):
#             if 'tables' in report or 'numbering' in report:
#                 checks = report
        
#         # 确保所有数据都是JSON可序列化的
#         # 这是关键步骤，防止Paragraph等对象导致序列化失败
#         serializable_checks = self._make_json_serializable(checks)
#         serializable_summary = self._make_json_serializable(summary)
#         serializable_extracted = self._make_json_serializable(extracted)
#         serializable_details = self._make_json_serializable(details)
        
#         return {
#             'module': module_name,
#             'checks': serializable_checks,
#             'summary': serializable_summary,
#             'extracted': serializable_extracted,
#             'details': serializable_details
#         }
    
#     def check_all(self, docx_path: str, enable_figure_api: bool = False,
#                   enable_classification_api: bool = False,
#                   modules: Optional[List[str]] = None, 
#                   reports_dir = None, annotate_dir = None,
#                   skip_checks: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
#         """
#         执行所选择的格式检测

#         参数：
#         docx_path: 待检测的文档路径
#         enable_figure_api: 是否启用Figure模块的API内容检测
#         enable_classification_api: 是否启用摘要分类号API检测
#         modules: 检测配置列表，指定启动哪些检测模块
#         skip_checks: 跳过检测项字典，格式：{"Title": ["bold", "font_size"], "Abstract": ["font_size"]}
        
#         返回：
#             {模块名: 报告字典} 的字典
#         """
#         try:
#             logger.info(f"开始进行格式检测: {docx_path}")
            
#             if skip_checks:
#                 logger.info(f"跳过检测项配置: {skip_checks}")
            
#             if not os.path.isfile(docx_path):
#                 return self._format_response(
#                     success=False,
#                     message=f"文件不存在: {docx_path}",
#                     status_code=404
#                 )
            
#             # 执行检测
#             all_reports = self.detector.detect_all(
#                 docx_path,
#                 modules=modules,
#                 enable_figure_api=enable_figure_api,
#                 skip_checks=skip_checks
#             )

#         except Exception as e:
#             error_msg=f"格式检测失败：{str(e)}"
#             logger.error(error_msg)
#             return self._format_response(
#                 success=False,
#                 message=error_msg,
#                 status_code=404)

#         logger.info('格式检测成功！')

#         # 在所有常规检测完成后，独立执行分类号检测
#         if enable_classification_api:
#             print("\n【摘要分类号 检测】")
#             try:
#                 all_reports = detect_classification(all_reports)
#                 classification_report = all_reports.get('Classification', {})
#                 if 'error' in classification_report:
#                     print(f"  ✗ 检测失败: {classification_report['error']}")
#                 else:
#                     print(f"  ✓ API 提取分类号: {classification_report.get('code', 'N/A')}")
#                     print(f"    原文中的分类号: {classification_report.get('original_clc', '未找到')}")
#                     match_status = classification_report.get('match_status', '未知')
#                     status_icon = '✓' if match_status == '一致' else '✗' if match_status == '不一致' else '?'
#                     print(f"    对比结果: {status_icon} {match_status}")
#             except Exception as e:
#                 print(f"  ✗ 检测失败: {e}")
#                 all_reports['Classification'] = {'error': f'分类号检测失败: {e}'}
        
#         # 对所有的检测报告进行处理（计算通过率）
#         result = self.process_report(all_reports)
#         logger.info('检测报告处理成功！')

#         # 开始生成检测报告
#         report_text = self.generate_comprehensive_report(all_reports)
#         # 保存报告
#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         report_filename = f"{timestamp}_format_report.txt"
#         # 保存文件路径
#         report_path = os.path.join(reports_dir, report_filename)
#         try:
#             output_dir = os.path.dirname(report_path)
#             if output_dir and not os.path.exists(output_dir):
#                 os.makedirs(output_dir, exist_ok=True)
            
#             with open(report_path, 'w', encoding='utf-8') as f:
#                 f.write(report_text)
#             logger.info(f"检测报告已保存到: {report_path}")
#         except Exception as e:
#             error_msg=f"检测报告保存失败: {str(e)}"
#             logger.error(error_msg)
#             return self._format_response(
#                 success=False,
#                 message=error_msg,
#                 status_code=404)
        
#         # 将报告信息添加到返回结果中
#         result['data']['report_saved'] = True
#         result['data']['report_filename'] = report_filename
#         result['data']['report_download_url'] = f'/api/paper-format/download-report/{report_filename}'
#         result['data']['report_text'] = report_text

#         # 生成带批注文档
#         annotated_path = generate_annotated_document(
#             docx_path,
#             all_reports,
#             annotate_dir
#         )
#         if annotated_path:
#             result['data']['annotated_saved'] = True
#             result['data']['annotated_filename'] = os.path.basename(annotated_path)
#             result['data']['annotated_download_url'] = f'/api/paper-format/download-annotated/{os.path.basename(annotated_path)}'
#             logger.info(f"批注文档已自动生成: {annotated_path}")
#         else:
#             # 不影响检测结果的返回
#             logger.warning("批注文档生成失败")

#         return result
        

#     def generate_comprehensive_report(self, all_reports):
#         """
#         生成综合文本报告
        
#         参数：
#             all_reports: {模块名: 报告字典} 的字典
        
#         返回：
#             格式化的报告文本字符串
#         """
#         logger.info("开始生成检测报告")
        
#         lines = []
        
#         # 报告头部
#         lines.append("=" * 80)
#         lines.append("论文格式检测综合报告")
#         lines.append("=" * 80)
#         lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#         lines.append("")
        
#         # 统计总体情况
#         total_ok = 0
#         total_checks = 0

#         for module_name in DETECTION_ORDER:
#             if module_name not in all_reports:
#                 continue
            
#             report = all_reports[module_name]
            
#             if report.get('error', False):
#                 continue
            
#             # 统计该模块的检测项
#             if isinstance(report, dict):
#                 # Table模块特殊处理
#                 if module_name == 'Table':
#                     # 统计numbering
#                     numbering = report.get('numbering', {})
#                     if isinstance(numbering, dict) and 'ok' in numbering:
#                         total_checks += 1
#                         if numbering.get('ok', False):
#                             total_ok += 1
                    
#                     # 统计每个表格的检测项
#                     tables = report.get('tables', [])
#                     for table_report in tables:
#                         for key in ['caption_format', 'table_style', 'table_alignment']:
#                             value = table_report.get(key, {})
#                             if isinstance(value, dict) and 'ok' in value:
#                                 total_checks += 1
#                                 if value.get('ok', False):
#                                     total_ok += 1
#                 else:
#                     # 其他模块常规统计
#                     for key, value in report.items():
#                         if isinstance(value, dict) and 'ok' in value:
#                             total_checks += 1
#                             if value.get('ok', False):
#                                 total_ok += 1
        
#         # 总体评估
#         lines.append("【总体评估】")
#         lines.append(f"总检测项数: {total_checks}")
#         lines.append(f"通过项数: {total_ok}")
#         lines.append(f"失败项数: {total_checks - total_ok}")
#         if total_checks > 0:
#             pass_rate = (total_ok / total_checks) * 100
#             lines.append(f"通过率: {pass_rate:.1f}%")
#         lines.append("")
        
#         # 各模块详细报告
#         for module_name in DETECTION_ORDER:
#             if module_name not in all_reports:
#                 continue
            
#             report = all_reports[module_name]
            
#             lines.append("-" * 80)
#             # 使用中文名称
#             module_cn_name = MODULE_NAMES_CN.get(module_name, module_name)
#             lines.append(f"【{module_cn_name} 检测报告】")
#             lines.append("-" * 80)
            
#             # 如果检测出错
#             if report.get('error', False):
#                 lines.append(f"✗ 检测失败: {report.get('error_message', '未知错误')}")
#                 lines.append("")
#                 continue
            
#             # Table模块需要特殊处理
#             if module_name == 'Table':
#                 # 处理表格编号检查
#                 numbering = report.get('numbering', {})
#                 if isinstance(numbering, dict) and 'ok' in numbering:
#                     ok_status = "✓ 通过" if numbering.get('ok', False) else "✗ 失败"
#                     lines.append(f"\n  [Numbering] {ok_status}")
#                     messages = numbering.get('messages', [])
#                     if messages:
#                         for msg in messages:
#                             lines.append(f"    • {msg}")
                
#                 # 处理每个表格
#                 tables = report.get('tables', [])
#                 for i, table_report in enumerate(tables, 1):
#                     caption_info = table_report.get('caption', {})
#                     caption_text = caption_info.get('text', f'Table {i}')
#                     lines.append(f"\n  [表格 {i}: {caption_text[:40]}{'...' if len(caption_text) > 40 else ''}]")
                    
#                     # 标题格式
#                     caption_format = table_report.get('caption_format', {})
#                     if isinstance(caption_format, dict) and 'ok' in caption_format:
#                         ok_status = "✓" if caption_format.get('ok', False) else "✗"
#                         lines.append(f"    标题格式: {ok_status}")
#                         messages = caption_format.get('messages', [])
#                         if messages and not caption_format.get('ok', False):
#                             for msg in messages:
#                                 lines.append(f"      • {msg}")
                    
#                     # 表格样式
#                     table_style = table_report.get('table_style', {})
#                     if isinstance(table_style, dict) and 'ok' in table_style:
#                         ok_status = "✓" if table_style.get('ok', False) else "✗"
#                         lines.append(f"    表格样式: {ok_status}")
#                         messages = table_style.get('messages', [])
#                         if messages and not table_style.get('ok', False):
#                             for msg in messages:
#                                 lines.append(f"      • {msg}")
                    
#                     # 表格对齐
#                     table_alignment = table_report.get('table_alignment', {})
#                     if isinstance(table_alignment, dict) and 'ok' in table_alignment:
#                         ok_status = "✓" if table_alignment.get('ok', False) else "✗"
#                         lines.append(f"    内容对齐: {ok_status}")
#                         messages = table_alignment.get('messages', [])
#                         if messages and not table_alignment.get('ok', False):
#                             for msg in messages:
#                                 lines.append(f"      • {msg}")
            
#             # Chinese_section模块特殊处理
#             elif module_name == 'Chinese_section':
#                 for section_key, section_value in report.items():
#                     if section_key == 'summary' or not isinstance(section_value, dict) or 'ok' not in section_value:
#                         continue
                    
#                     section_title = MODULE_NAMES_CN.get(section_key, section_key)
#                     ok_status = "✓ 通过" if section_value.get('ok') else "✗ 失败"
#                     lines.append(f"\n  [{section_title}] {ok_status}")
                    
#                     messages = section_value.get('messages', [])
#                     if messages and not section_value.get('ok'):
#                         for msg in messages:
#                             lines.append(f"    • {msg}")
        

#             # Figure模块需要特殊处理（类似Table模块）
#             elif module_name == 'Figure':
#                 # 处理图片编号检查
#                 numbering = report.get('numbering', {})
#                 if isinstance(numbering, dict) and 'ok' in numbering:
#                     ok_status = "✓ 通过" if numbering.get('ok', False) else "✗ 失败"
#                     lines.append(f"\n  [Numbering] {ok_status}")
#                     messages = numbering.get('messages', [])
#                     if messages:
#                         for msg in messages:
#                             lines.append(f"    • {msg}")
                
#                 # 处理每张图片
#                 figures = report.get('figures', [])
#                 for i, fig_report in enumerate(figures, 1):
#                     caption_info = fig_report.get('caption_info', {})
#                     if fig_report.get('has_caption', False):
#                         caption_text = caption_info.get('full_text', f'Fig.{i}')
#                         lines.append(f"\n  [图片 {i}: {caption_text[:40]}{'...' if len(caption_text) > 40 else ''}]")
#                     else:
#                         lines.append(f"\n  [图片 {i}: (无标题)]")
                    
#                     # 标题格式
#                     format_check = fig_report.get('format_check', {})
#                     if isinstance(format_check, dict) and 'ok' in format_check:
#                         ok_status = "✓" if format_check.get('ok', False) else "✗"
#                         lines.append(f"    标题格式: {ok_status}")
#                         messages = format_check.get('messages', [])
#                         if messages and not format_check.get('ok', False):
#                             for msg in messages:
#                                 lines.append(f"      • {msg}")
                    
#                     # 图片对齐
#                     picture_check = fig_report.get('picture_check', {})
#                     if isinstance(picture_check, dict) and 'ok' in picture_check:
#                         ok_status = "✓" if picture_check.get('ok', False) else "✗"
#                         lines.append(f"    图片对齐: {ok_status}")
#                         messages = picture_check.get('messages', [])
#                         if messages and not picture_check.get('ok', False):
#                             for msg in messages:
#                                 lines.append(f"      • {msg}")

#                     # 内容检测
#                     content_check = fig_report.get('content_check', {})
#                     if isinstance(content_check, dict) and 'ok' in content_check:
#                         ok_status = "✓" if content_check.get('ok', False) else "✗"
#                         lines.append(f"    内容规范: {ok_status}")
#                         messages = content_check.get('messages', [])
#                         if messages and not content_check.get('ok', False):
#                             for msg in messages:
#                                 lines.append(f"      • {msg}")
            
#             else:
#                 # 其他模块的常规处理
#                 for section_key, section_value in report.items():
#                     if section_key in ['summary', 'extracted', 'details']:
#                         continue
                    
#                     if isinstance(section_value, dict) and 'ok' in section_value:
#                         # 检测项标题
#                         # 优先从中文映射获取，否则进行转换
#                         section_title = MODULE_NAMES_CN.get(section_key, section_key.replace('_', ' ').title())
#                         ok_status = "✓ 通过" if section_value.get('ok', False) else "✗ 失败"
#                         lines.append(f"\n  [{section_title}] {ok_status}")
                        
#                         # 检测项消息
#                         messages = section_value.get('messages', [])
#                         if messages:
#                             for msg in messages:
#                                 # 格式化消息（添加缩进）
#                                 if msg.strip().startswith('-'):
#                                     lines.append(f"      {msg.strip()}")
#                                 else:
#                                     lines.append(f"    • {msg}")
            
#             # 添加总结
#             if 'summary' in report and report['summary']:
#                 lines.append("\n  【总结】")
#                 for summary_item in report['summary']:
#                     lines.append(f"    {summary_item}")
            
#             lines.append("")
        
#         # 单独处理分类号报告
#         if 'Classification' in all_reports:
#             report = all_reports['Classification']
#             lines.append("-" * 80)
#             lines.append(f"【{MODULE_NAMES_CN['Classification']} 检测报告】")
#             lines.append("-" * 80)
#             if 'error' in report:
#                 lines.append(f"  ✗ 检测失败: {report['error']}")
#             else:
#                 lines.append(f"  ✓ 检测完成")
#                 lines.append(f"    API 提取分类号: {report.get('code', 'N/A')} (原始: {report.get('raw_code', 'N/A')})")
#                 lines.append(f"    原文中的分类号: {report.get('original_clc', '未找到')}")
                
#                 match_status = report.get('match_status', '未知')
#                 if match_status == '一致':
#                     status_icon = '✓'
#                 elif match_status == '不一致':
#                     status_icon = '✗'
#                 else:
#                     status_icon = '?'
#                 lines.append(f"    对比结果: {status_icon} {match_status}")
#                 lines.append("\n  【分类理由】")
#                 # 格式化理由，每行80个字符
#                 reason_text = report.get('reason', '无').replace('\n', ' ')
#                 import textwrap
#                 wrapped_text = textwrap.fill(reason_text, width=70)
#                 for line in wrapped_text.split('\n'):
#                     lines.append(f"    {line}")
#             lines.append("")
    
        
#         # 报告尾部
#         lines.append("=" * 80)
#         lines.append("报告结束")
#         lines.append("=" * 80)
        
#         return "\n".join(lines)


#     def process_report(self, all_reports):
#         """对所有的检测报告进行处理"""
#         try:
#             # 标准化所有结果
#             all_results = {}
#             for module_name, report in all_reports.items():
#                 all_results[module_name] = self._normalize_report(report, module_name)
            
#             # 计算统计信息
#             total_checks = 0
#             passed_checks = 0
            
#             for module_name, module_result in all_results.items():
#                 checks = module_result.get('checks', {})
#                 for check_name, check_result in checks.items():
#                     if isinstance(check_result, dict) and 'ok' in check_result:
#                         total_checks += 1
#                         if check_result.get('ok', False):
#                             passed_checks += 1
            
#             failed_checks = total_checks - passed_checks
#             pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
            
#             summary = {
#                 'total_checks': total_checks,
#                 'passed_checks': passed_checks,
#                 'failed_checks': failed_checks,
#                 'pass_rate': round(pass_rate, 2)
#             }
            
#             message = f"格式检测完成，通过率: {pass_rate:.1f}%"
            
#             return self._format_response(
#                 success=True,
#                 data={
#                     'results': all_results,
#                     'summary': summary
#                 },
#                 message=message,
#                 status_code=200
#             )
            
#         except Exception as e:
#             error_msg=f"对检测报告进行处理失败：{str(e)}"
#             logger.error(error_msg)
#             return self._format_response(
#                 success=False,
#                 message=error_msg,
#                 status_code=404)
    
#     def generate_report(self, check_results: Dict[str, Any], 
#                        output_path: Optional[str] = None) -> Dict[str, Any]:
#         """生成文本格式的检测报告"""
#         try:
#             logger.info("开始生成检测报告")
            
#             if not check_results or not check_results.get('success'):
#                 return self._format_response(
#                     success=False,
#                     message="无效的检测结果",
#                     status_code=400
#                 )
            
#             data = check_results.get('data', {})
#             results = data.get('results', {})
#             summary = data.get('summary', {})
            
#             # 生成报告文本
#             lines = []
#             lines.append("=" * 80)
#             lines.append("论文格式检测综合报告")
#             lines.append("=" * 80)
#             lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#             lines.append("")
            
#             # 总体评估
#             lines.append("【总体评估】")
#             lines.append(f"总检测项数: {summary.get('total_checks', 0)}")
#             lines.append(f"通过项数: {summary.get('passed_checks', 0)}")
#             lines.append(f"失败项数: {summary.get('failed_checks', 0)}")
#             lines.append(f"通过率: {summary.get('pass_rate', 0)}%")
#             lines.append("")
            
#             # 各模块详细报告
#             for module_name in DETECTION_ORDER:
#                 if module_name not in results:
#                     continue
                
#                 module_result = results[module_name]
                
#                 lines.append("-" * 80)
#                 lines.append(f"【{module_name} 检测报告】")
#                 lines.append("-" * 80)
                
#                 checks = module_result.get('checks', {})
#                 for check_name, check_result in checks.items():
#                     if not isinstance(check_result, dict):
#                         continue
                    
#                     ok_status = "✓ 通过" if check_result.get('ok', False) else "✗ 失败"
#                     lines.append(f"\n  [{check_name}] {ok_status}")
                    
#                     messages = check_result.get('messages', [])
#                     if messages:
#                         for msg in messages:
#                             lines.append(f"    • {msg}")
                
#                 # 添加总结
#                 summary_list = module_result.get('summary', [])
#                 if summary_list:
#                     lines.append("\n  【总结】")
#                     for summary_item in summary_list:
#                         lines.append(f"    {summary_item}")
                
#                 lines.append("")
            
#             # 报告尾部
#             lines.append("=" * 80)
#             lines.append("报告结束")
#             lines.append("=" * 80)
            
#             report_text = "\n".join(lines)
            
#             # 保存报告文件
#             file_path = None
#             if output_path:
#                 try:
#                     output_dir = os.path.dirname(output_path)
#                     if output_dir and not os.path.exists(output_dir):
#                         os.makedirs(output_dir, exist_ok=True)
                    
#                     with open(output_path, 'w', encoding='utf-8') as f:
#                         f.write(report_text)
                    
#                     file_path = output_path
#                     logger.info(f"报告已保存到: {file_path}")
#                 except Exception as e:
#                     logger.error(f"保存报告文件失败: {e}")
            
#             return self._format_response(
#                 success=True,
#                 data={
#                     'report_text': report_text,
#                     'file_path': file_path
#                 },
#                 message='报告生成成功',
#                 status_code=200
#             )
            
#         except Exception as e:
#             return self._handle_exception(e, 'ReportGeneration')
    
class ChinesePaperFormatService:
    """
    论文格式检测服务类
    
    提供统一的论文格式检查接口，支持：
    - 标题格式检测 (Title)
    - 摘要格式检测 (Abstract)
    - 关键词格式检测 (Keywords)
    - 正文格式检测 (Content)
    - 图片格式检测 (Figure)
    - 公式格式检测 (Formula)
    - 表格格式检测 (Table)
    - 全量检测 (All)
    - 报告生成
    """
    
    def __init__(self):
        """初始化服务"""
        try:
            # 初始化检测器
            templates_dir = 'Chinese_paper_detect_templates'
            self.detector = ChinesePaperFormatDetector(templates_dir=str(templates_dir))
            logger.info(f"论文格式检测服务已初始化")
        except Exception as e:
            logger.error(f"初始化检测服务失败: {e}")
            raise
    
    def _format_response(self, success: bool, data: Any = None, 
                        message: str = '', status_code: int = 200) -> Dict[str, Any]:
        """格式化标准响应"""
        return {
            'success': success,
            'data': data,
            'message': message,
            'status_code': status_code
        }
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """
        递归地将对象转换为JSON可序列化的格式
        处理python-docx的Paragraph对象和其他不可序列化的对象
        """
        if obj is None:
            return None
        
        # 处理基本类型
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # 处理列表
        if isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        
        # 处理字典
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        
        # 处理Paragraph对象和其他复杂对象
        # 尝试获取对象的文本表示
        try:
            # 如果是Paragraph对象，获取其text属性
            if hasattr(obj, 'text'):
                return str(obj.text)
            # 如果有__dict__属性，尝试序列化为字典
            elif hasattr(obj, '__dict__'):
                return self._make_json_serializable(obj.__dict__)
            # 其他情况转换为字符串
            else:
                return str(obj)
        except Exception as e:
            logger.warning(f"对象序列化失败: {type(obj)}, {e}")
            return str(obj)
    
    def _normalize_report(self, report: Dict[str, Any], module_name: str) -> Dict[str, Any]:
        """标准化检测报告格式"""
        if not report:
            return {
                'module': module_name,
                'checks': {},
                'summary': [],
                'extracted': {},
                'details': {}
            }
        
        # 处理错误报告
        if report.get('error'):
            return {
                'module': module_name,
                'checks': {},
                'summary': report.get('summary', []),
                'extracted': {},
                'details': {},
                'error': True,
                'error_message': report.get('error_message', '')
            }
        
            # TOC模块特殊处理：三段（结构 + 三个格式分段）
        if module_name == 'TOC' and isinstance(report, dict):
            checks = {}
            structure = report.get('structure', {})
            if isinstance(structure, dict) and 'ok' in structure:
                checks['structure'] = structure

            format_reports = report.get('format', [])
            if isinstance(format_reports, list):
                for fr in format_reports:
                    title_type = fr.get('title_type', '未知')
                    format_report = fr.get('report', {})
                    if isinstance(format_report, dict) and 'ok' in format_report:
                        checks[f'format_{title_type}'] = format_report

            summary = report.get('summary', [])
            extracted = {}
            details = {}

        # Keywords和Title模块特殊处理（双语检测）
        elif module_name in ['Keywords', 'Title'] and isinstance(report, dict) and 'chinese' in report and 'english' in report:
            checks = {}
            chinese_report = report.get('chinese', {})
            english_report = report.get('english', {})

            if isinstance(chinese_report, dict):
                exclude_keys = ['summary', 'extracted', 'details', 'language']
                if module_name == 'Keywords':
                    exclude_keys.extend(['keywords_paragraph', 'keywords_text', 'keywords_list'])
                elif module_name == 'Title':
                    exclude_keys.extend(['title_paragraph', 'title_text'])

                for key, value in chinese_report.items():
                    if key not in exclude_keys:
                        if isinstance(value, dict) and 'ok' in value:
                            checks[f'chinese_{key}'] = value

            if isinstance(english_report, dict):
                exclude_keys = ['summary', 'extracted', 'details', 'language']
                if module_name == 'Keywords':
                    exclude_keys.extend(['keywords_paragraph', 'keywords_text', 'keywords_list'])
                elif module_name == 'Title':
                    exclude_keys.extend(['title_paragraph', 'title_text'])

                for key, value in english_report.items():
                    if key not in exclude_keys:
                        if isinstance(value, dict) and 'ok' in value:
                            checks[f'english_{key}'] = value

            summary = []
            if 'summary' in report:
                summary.extend(report.get('summary', []))
            if isinstance(chinese_report, dict) and 'summary' in chinese_report:
                summary.extend(chinese_report.get('summary', []))
            if isinstance(english_report, dict) and 'summary' in english_report:
                summary.extend(english_report.get('summary', []))

            extracted = {}
            details = {}

        # References 模块特殊处理：三段（结构/格式/标题格式），引用消息并入格式分段
        elif module_name == 'References' and isinstance(report, dict):
            checks = {}

            structure = report.get('structure', {})
            if isinstance(structure, dict) and 'ok' in structure:
                checks['references_structure'] = structure

            references_header = report.get('references_header', {})
            if isinstance(references_header, dict) and 'ok' in references_header:
                checks['references_header'] = references_header

            content_format = report.get('content_format', {})
            citation = report.get('citation', {})
            if isinstance(content_format, dict) and isinstance(citation, dict):
                merged_ok = content_format.get('ok', True) and citation.get('ok', True)
                merged_messages = content_format.get('messages', []) + citation.get('messages', [])
                checks['references_content'] = {'ok': merged_ok, 'messages': merged_messages}

            summary = report.get('summary', [])
            extracted = {}
            details = {}

        # Figure 模块特殊处理：只保留 [图检测] 和 [编号] 两个分段
        elif module_name == 'Figure' and isinstance(report, dict):
            checks = {}

            numbering = report.get('numbering', {})
            if isinstance(numbering, dict) and 'ok' in numbering:
                checks['numbering'] = numbering

            figures = report.get('figures', [])
            total = len(figures)
            failed = 0
            all_messages = []
            for idx, fr in enumerate(figures, 1):
                if isinstance(fr, dict):
                    fc = fr.get('format_check', {})
                    pc = fr.get('picture_check', {})
                    rc = fr.get('reference_check', {})
                    cc = fr.get('content_check', {})
                    if not (fc.get('ok', True) and pc.get('ok', True)
                            and rc.get('ok', True) and cc.get('ok', True)):
                        failed += 1
                        caption_info = fr.get('caption_info', {})
                        if fr.get('has_caption'):
                            fig_label = caption_info.get('full_text', f'图{idx}')
                        else:
                            fig_label = f'图{idx}（无标题）'
                        for check_key, check_label in [
                            ('format_check', '标题格式'),
                            ('picture_check', '图片对齐'),
                            ('reference_check', '引用检查'),
                        ]:
                            cv = fr.get(check_key, {})
                            if isinstance(cv, dict) and not cv.get('ok', False):
                                msgs = cv.get('messages', [])
                                if msgs:
                                    all_messages.append(f"{fig_label}：{check_label}——{msgs[0]}")
                        is_chart = fr.get('content_check', {}).get('is_chart', False)
                        cc_val = fr.get('content_check', {})
                        if is_chart and not cc_val.get('ok', False):
                            cc_msgs = cc_val.get('messages', [])
                            if cc_msgs:
                                all_messages.append(f"{fig_label}：内容检测——{cc_msgs[0]}")
            checks['figure_detection'] = {'ok': failed == 0, 'messages': all_messages, 'total': total, 'failed': failed}

            summary = report.get('summary', [])
            extracted = {}
            details = {'figure_count': total}

        # Table 模块特殊处理：只保留 [表格检测] 和 [编号] 两个分段
        elif module_name == 'Table' and isinstance(report, dict):
            checks = {}

            numbering = report.get('numbering', {})
            if isinstance(numbering, dict) and 'ok' in numbering:
                checks['numbering'] = numbering

            tables = report.get('tables', [])
            total = len(tables)
            failed = 0
            all_messages = []
            for tr in tables:
                if isinstance(tr, dict):
                    # 表题格式：caption_cn_format / caption_en_format / text_rules
                    cn_fmt = tr.get('caption_cn_format', {})
                    en_fmt = tr.get('caption_en_format', {})
                    txt_rules = tr.get('text_rules', {})
                    ts = tr.get('table_style', {})
                    ta = tr.get('table_content_alignment', {})
                    tr2 = tr.get('table_reference', {})
                    if not (cn_fmt.get('ok', True) and en_fmt.get('ok', True)
                            and txt_rules.get('ok', True) and ts.get('ok', True)
                            and ta.get('ok', True) and tr2.get('ok', True)):
                        failed += 1
                        tbl_desc = tr.get('table_desc', f'表格{failed}')
                        for check_key, check_label in [
                            ('caption_cn_format', '中文表题格式'),
                            ('caption_en_format', '英文表题格式'),
                            ('text_rules', '表题文字规则'),
                            ('table_style', '表格样式'),
                            ('table_content_alignment', '内容对齐'),
                            ('table_reference', '表格引用'),
                        ]:
                            cv = tr.get(check_key, {})
                            if isinstance(cv, dict) and not cv.get('ok', False):
                                msgs = cv.get('messages', [])
                                if msgs:
                                    all_messages.append(f"{tbl_desc}：{check_label}——{msgs[0]}")
            checks['table_detection'] = {'ok': failed == 0, 'messages': all_messages, 'total': total, 'failed': failed}

            summary = report.get('summary', [])
            extracted = {}
            details = {'table_count': total}

        # References 模块特殊处理：只保留结构、格式、标题格式三个分段
        # 注意：References_detect 返回的 key 是 structure/content_format/references_header
        elif module_name == 'References' and isinstance(report, dict):
            checks = {}
            # structure_report → [结构]
            structure_report = report.get('structure', {})
            if isinstance(structure_report, dict) and 'ok' in structure_report:
                checks['references_structure'] = structure_report
            # content_format_report → [格式]
            content_report = report.get('content_format', {})
            if isinstance(content_report, dict) and 'ok' in content_report:
                checks['references_content'] = content_report
            # references_header → [标题格式]
            header_report = report.get('references_header', {})
            if isinstance(header_report, dict) and 'ok' in header_report:
                checks['references_header'] = header_report
            summary = report.get('summary', [])
            extracted = report.get('extracted', {})
            details = {}

        else:
            summary = report.get('summary', []) if isinstance(report, dict) else []
            extracted = report.get('extracted', {}) if isinstance(report, dict) else {}
            details = report.get('details', {}) if isinstance(report, dict) else {}
            exclude_keys = ['summary', 'extracted', 'details']
            checks = {k: v for k, v in report.items() if k not in exclude_keys and isinstance(v, dict) and 'ok' in v}

        # 确保所有数据都是JSON可序列化的
        # 这是关键步骤，防止Paragraph等对象导致序列化失败
        serializable_checks = self._make_json_serializable(checks)
        serializable_summary = self._make_json_serializable(summary)
        serializable_extracted = self._make_json_serializable(extracted)
        serializable_details = self._make_json_serializable(details)

        # 将检查项 key 替换为中文标签（CHECK_NAMES_CN 映射）
        cn_checks = {}
        for k, v in serializable_checks.items():
            cn_key = CHECK_NAMES_CN.get(k, k)
            cn_checks[cn_key] = v
        serializable_checks = cn_checks

        return {
            'module': module_name,
            'checks': serializable_checks,
            'summary': serializable_summary,
            'extracted': serializable_extracted,
            'details': serializable_details
        }
    
    def check_all(self, docx_path: str, enable_figure_api: bool = False,
                  enable_classification_api: bool = False,
                  modules: Optional[List[str]] = None, 
                  reports_dir = None, annotate_dir = None,
                  skip_checks: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """
        执行所选择的格式检测

        参数：
        docx_path: 待检测的文档路径
        enable_figure_api: 是否启用Figure模块的API内容检测
        enable_classification_api: 是否启用摘要分类号API检测
        modules: 检测配置列表，指定启动哪些检测模块
        skip_checks: 跳过检测项字典，格式：{"Title": ["bold", "font_size"], "Abstract": ["font_size"]}
        
        返回：
            {模块名: 报告字典} 的字典
        """
        try:
            logger.info(f"开始进行格式检测: {docx_path}")
            
            if skip_checks:
                logger.info(f"跳过检测项配置: {skip_checks}")
            
            if not os.path.isfile(docx_path):
                return self._format_response(
                    success=False,
                    message=f"文件不存在: {docx_path}",
                    status_code=404
                )
            
            # 执行检测
            all_reports = self.detector.detect_all(
                docx_path,
                modules=modules,
                enable_figure_api=enable_figure_api,
                skip_checks=skip_checks
            )

        except Exception as e:
            error_msg=f"格式检测失败：{str(e)}"
            logger.error(error_msg)
            return self._format_response(
                success=False,
                message=error_msg,
                status_code=404)

        logger.info('格式检测成功！')

        # 在所有常规检测完成后，独立执行分类号检测
        if enable_classification_api:
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
        
        # 对所有的检测报告进行处理（计算通过率）
        result = self.process_report(all_reports)
        logger.info('检测报告处理成功！')

        # 开始生成检测报告
        report_text = self.generate_comprehensive_report(all_reports)
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{timestamp}_format_report.txt"
        # 保存文件路径
        report_path = os.path.join(reports_dir, report_filename)
        try:
            output_dir = os.path.dirname(report_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logger.info(f"检测报告已保存到: {report_path}")
        except Exception as e:
            error_msg=f"检测报告保存失败: {str(e)}"
            logger.error(error_msg)
            return self._format_response(
                success=False,
                message=error_msg,
                status_code=404)
        
        # 将报告信息添加到返回结果中
        result['data']['report_saved'] = True
        result['data']['report_filename'] = report_filename
        result['data']['report_download_url'] = f'/api/paper-format/download-report/{report_filename}'
        result['data']['report_text'] = report_text

        # 生成带批注文档（使用中文注释引擎 + document_annotator）
        annotated_path = None
        try:
            # 1. 先使用中文注释引擎处理摘要和关键词
            annotated_path = annotate_chinese_abstract_and_keywords(
                docx_path,
                all_reports,
                annotate_dir
            )
            if annotated_path:
                logger.info(f"中文注释引擎已生成批注文档: {annotated_path}")
            else:
                # 如果中文引擎失败，创建基础副本供后续使用
                annotated_path = create_document_copy(docx_path, annotate_dir)
                if annotated_path:
                    logger.info(f"已创建文档副本供批注使用: {annotated_path}")
        except Exception as e:
            logger.exception(f"中文注释引擎生成批注文档时发生异常: {e}")
            # 创建基础副本供后续使用
            try:
                annotated_path = create_document_copy(docx_path, annotate_dir)
            except Exception as e2:
                logger.error(f"创建文档副本失败: {e2}")
        
        # 2. 使用 document_annotator 处理其他模块（Title, Content, Formula, Figure, Table, Chinese_section等）
        if annotated_path:
            try:
                # 调试：检查 all_reports 中的模块
                logger.info(f"document_annotator 开始处理，all_reports 中的模块: {list(all_reports.keys())}")
                
                # 从报告中提取问题（排除已由 chinese_annotation_engine 处理的 Abstract 和 Keywords）
                issues_list = parse_issues_from_reports(all_reports)
                logger.info(f"document_annotator parse_issues_from_reports 返回 {len(issues_list)} 个问题")
                
                # 调试：显示所有问题
                if issues_list:
                    for issue in issues_list:
                        logger.debug(f"  - 模块: {issue.get('module')}, 检测项: {issue.get('section')}, 消息数: {len(issue.get('messages', []))}")
                
                # 过滤掉 Abstract 和 Keywords 的问题，避免重复批注
                filtered_issues = [
                    issue for issue in issues_list 
                    if issue.get('module') not in ['Abstract', 'Keywords']
                ]
                logger.info(f"过滤后剩余 {len(filtered_issues)} 个问题（已排除 Abstract 和 Keywords）")
                
                if filtered_issues:
                    logger.info(f"document_annotator 识别出 {len(filtered_issues)} 个问题需要批注")
                    comment_count = add_all_comments(docx_path, annotated_path, filtered_issues)
                    if comment_count > 0:
                        logger.info(f"document_annotator 成功添加 {comment_count} 个批注")
                    else:
                        logger.warning("document_annotator 未能添加任何批注")
                else:
                    logger.info("document_annotator 未发现需要批注的问题（除摘要和关键词外）")
                    if issues_list:
                        logger.warning(f"注意：parse_issues_from_reports 返回了 {len(issues_list)} 个问题，但全部被过滤（可能都是 Abstract 或 Keywords）")
            except Exception as e:
                logger.exception(f"document_annotator 添加批注时发生异常: {e}")
        
        # 3. 设置返回结果
        if annotated_path:
            result['data']['annotated_saved'] = True
            result['data']['annotated_filename'] = os.path.basename(annotated_path)
            result['data']['annotated_download_url'] = f'/api/paper-format/download-annotated/{os.path.basename(annotated_path)}'
            logger.info(f"批注文档已自动生成 (chinese engine + document_annotator): {annotated_path}")
        else:
            logger.warning("批注文档生成失败")

        return result
        

    def generate_comprehensive_report(self, all_reports):
        """
        生成综合文本报告
        
        参数：
            all_reports: {模块名: 报告字典} 的字典
        
        返回：
            格式化的报告文本字符串
        """
        logger.info("开始生成检测报告")
        
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
                # Keywords和Title模块特殊处理（双语检测）
                if module_name in ['Keywords', 'Title'] and 'chinese' in report and 'english' in report:
                    # 统计中文关键词检测项
                    chinese_report = report.get('chinese', {})
                    if isinstance(chinese_report, dict):
                        for key, value in chinese_report.items():
                            if key != 'summary' and isinstance(value, dict) and 'ok' in value:
                                total_checks += 1
                                if value.get('ok', False):
                                    total_ok += 1
                    
                    # 统计英文关键词检测项
                    english_report = report.get('english', {})
                    if isinstance(english_report, dict):
                        for key, value in english_report.items():
                            if key != 'summary' and isinstance(value, dict) and 'ok' in value:
                                total_checks += 1
                                if value.get('ok', False):
                                    total_ok += 1
                # TOC模块特殊处理
                elif module_name == 'TOC':
                    # 统计structure
                    structure = report.get('structure', {})
                    if isinstance(structure, dict) and 'ok' in structure:
                        total_checks += 1
                        if structure.get('ok', False):
                            total_ok += 1
                    
                    # 统计format（是一个列表）
                    format_reports = report.get('format', [])
                    if isinstance(format_reports, list):
                        for fr in format_reports:
                            format_report = fr.get('report', {})
                            if isinstance(format_report, dict) and 'ok' in format_report:
                                total_checks += 1
                                if format_report.get('ok', False):
                                    total_ok += 1
                
                # Table模块特殊处理
                elif module_name == 'Table':
                    # 统计numbering
                    numbering = report.get('numbering', {})
                    if isinstance(numbering, dict) and 'ok' in numbering:
                        total_checks += 1
                        if numbering.get('ok', False):
                            total_ok += 1
                    
                    # 统计每个表格的检测项
                    tables = report.get('tables', [])
                    for table_report in tables:
                        for key in ['caption_format', 'table_style', 'table_alignment']:
                            value = table_report.get(key, {})
                            if isinstance(value, dict) and 'ok' in value:
                                total_checks += 1
                                if value.get('ok', False):
                                    total_ok += 1
                else:
                    # 其他模块常规统计
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
            
            # Table模块：[表格检测] 和 [编号] 始终显示，失败时追加详细表格信息
            if module_name == 'Table':
                table_det = report.get('table_detection', {})
                if isinstance(table_det, dict) and 'ok' in table_det:
                    total = table_det.get('total', len(report.get('tables', [])))
                    # table_detection 没有 failed 字段，直接从子项统计
                    # 注意：Table_detect 返回的键名是 caption_cn_format / caption_en_format / text_rules，
                    # 没有 caption_format，也没有 table_alignment；续表 table_content_alignment 为 {'skipped': True}
                    def table_has_issues(t):
                        for k in ('caption_cn_format', 'caption_en_format', 'text_rules',
                                  'table_style', 'table_content_alignment', 'table_reference'):
                            cv = t.get(k, {})
                            if isinstance(cv, dict) and not cv.get('skipped', False) and not cv.get('ok', False):
                                return True
                        return False
                    failed = sum(1 for t in report.get('tables', []) if table_has_issues(t))
                    if table_det.get('ok', False):
                        lines.append(f"\n  [表格检测] ✓ 符合规范（共检测 {total} 张表格）")
                    else:
                        lines.append(f"\n  [表格检测] ✗ 发现 {failed} 项问题（共检测 {total} 张表格）")

                numbering = report.get('numbering', {})
                if isinstance(numbering, dict) and 'ok' in numbering:
                    if numbering.get('ok', False):
                        lines.append(f"  [编号] ✓ 符合规范")
                    else:
                        msgs = numbering.get('messages', [])
                        if msgs:
                            lines.append(f"  [编号] ✗ 发现 {len(msgs)} 项问题")
                            for msg in msgs:
                                lines.append(f"    • {msg}")

                tables = report.get('tables', [])
                for i, table_report in enumerate(tables, 1):
                    failed_checks = []
                    for check_key, check_label in [
                        ('caption_cn_format', '中文表题格式'),
                        ('caption_en_format', '英文表题格式'),
                        ('text_rules', '表题文字规范'),
                        ('table_style', '表格样式'),
                        ('table_content_alignment', '内容对齐'),
                        ('table_reference', '表格引用'),
                    ]:
                        cv = table_report.get(check_key, {})
                        if isinstance(cv, dict) and not cv.get('skipped', False) and not cv.get('ok', False):
                            msgs = cv.get('messages', [])
                            if msgs:
                                failed_checks.append((check_label, msgs))
                    if failed_checks:
                        table_desc = table_report.get('table_desc', '')
                        cn_title = table_report.get('captions', {}).get('cn', {}).get('title', '')
                        caption_text = table_desc or cn_title or f'表格 {i}'
                        lines.append(f"\n  [{caption_text}]")
                        for check_label, msgs in failed_checks:
                            lines.append(f"    • [{check_label}] {msgs[0]}")
                            for msg in msgs[1:]:
                                lines.append(f"    • {msg}")
            
            # Chinese_section模块：每个检查项始终显示，通过时✓符合规范，失败时✗发现N项问题
            elif module_name == 'Chinese_section':
                for section_key, section_value in report.items():
                    if section_key in ['summary', 'extracted', 'details']:
                        continue
                    if not isinstance(section_value, dict) or 'ok' not in section_value:
                        continue
                    section_title = CHECK_NAMES_CN.get(section_key, section_key)
                    msgs = section_value.get('messages', [])
                    if section_value.get('ok', False):
                        lines.append(f"  [{section_title}] ✓ 符合规范")
                    elif msgs:
                        lines.append(f"\n  [{section_title}] ✗ 发现 {len(msgs)} 项问题")
                        for msg in msgs:
                            lines.append(f"    • {msg}")

            # References模块：三段始终显示，通过时✓符合规范，失败时✗发现问题
            elif module_name == 'References':
                for check_key, check_label in [
                    ('structure', '结构'),
                    ('content_format', '格式'),
                    ('references_header', '标题格式'),
                ]:
                    check_val = report.get(check_key, {})
                    if isinstance(check_val, dict) and 'ok' in check_val:
                        if check_val.get('ok', False):
                            lines.append(f"\n  [{check_label}] ✓ 符合规范")
                        else:
                            messages = check_val.get('messages', [])
                            # 过滤掉 "XXX格式问题：" 这类前缀头消息和以"问题"结尾的消息
                            filtered = [m for m in messages if not m.rstrip('：').rstrip(':').endswith('格式问题') and not m.rstrip('：').rstrip(':').endswith('问题')]
                            if filtered:
                                lines.append(f"\n  [{check_label}] ✗ 发现 {len(filtered)} 项问题")
                                for msg in filtered:
                                    lines.append(f"    • {msg}")
        

            # Figure模块：[图检测] 和 [编号] 始终显示，失败时追加详细图片信息
            elif module_name == 'Figure':
                figure_det = report.get('figure_detection', {})
                if not figure_det:
                    figure_det = report.get('overall', {})
                if isinstance(figure_det, dict) and 'ok' in figure_det:
                    total = figure_det.get('total', len(report.get('figures', [])))
                    # overall 没有 failed 字段，直接从子项统计
                    def figure_has_issues(fig):
                        for k in ('format_check', 'picture_check', 'reference_check'):
                            if not fig.get(k, {}).get('ok', False):
                                return True
                        if fig.get('content_check', {}).get('is_chart', False):
                            if not fig.get('content_check', {}).get('ok', False):
                                return True
                        return False
                    failed = sum(1 for f in report.get('figures', []) if figure_has_issues(f))
                    if figure_det.get('ok', False):
                        lines.append(f"\n  [图检测] ✓ 符合规范（共检测 {total} 张图片）")
                    else:
                        lines.append(f"\n  [图检测] ✗ 发现 {failed} 项问题（共检测 {total} 张图片）")

                numbering = report.get('numbering', {})
                if isinstance(numbering, dict) and 'ok' in numbering:
                    if numbering.get('ok', False):
                        lines.append(f"  [编号] ✓ 符合规范")
                    else:
                        msgs = numbering.get('messages', [])
                        if msgs:
                            lines.append(f"  [编号] ✗ 发现 {len(msgs)} 项问题")
                            for msg in msgs:
                                lines.append(f"    • {msg}")

                figures = report.get('figures', [])
                for i, fig_report in enumerate(figures, 1):
                    failed_checks = []
                    for check_key, check_label in [
                        ('format_check', '标题格式'),
                        ('picture_check', '图片对齐'),
                        ('reference_check', '引用检查'),
                    ]:
                        cv = fig_report.get(check_key, {})
                        if isinstance(cv, dict) and not cv.get('ok', False):
                            msgs = cv.get('messages', [])
                            if msgs:
                                failed_checks.append((check_label, msgs))
                    is_chart = fig_report.get('content_check', {}).get('is_chart', False)
                    cc = fig_report.get('content_check', {})
                    if is_chart and not cc.get('ok', False):
                        msgs = cc.get('messages', [])
                        if msgs:
                            failed_checks.append(('内容检测', msgs))

                    if failed_checks:
                        caption_info = fig_report.get('caption_info', {})
                        if fig_report.get('has_caption', False):
                            ct = caption_info.get('full_text', f'Fig.{i}')
                            lines.append(f"\n  [图片 {i}: {ct[:40]}{'...' if len(ct) > 40 else ''}]")
                        else:
                            lines.append(f"\n  [图片 {i}: (无标题)]")
                        for check_label, msgs in failed_checks:
                            lines.append(f"    • [{check_label}] {msgs[0]}")
                            for msg in msgs[1:]:
                                lines.append(f"    • {msg}")

            # TOC模块：[结构] 和三格式分段始终显示
            elif module_name == 'TOC':
                structure = report.get('structure', {})
                if isinstance(structure, dict) and 'ok' in structure:
                    msgs = structure.get('messages', [])
                    if structure.get('ok', False):
                        lines.append(f"  [结构] ✓ 符合规范")
                    elif msgs:
                        lines.append(f"\n  [结构] ✗ 发现 {len(msgs)} 项问题")
                        for msg in msgs:
                            lines.append(f"    • {msg}")

                format_reports = report.get('format', [])
                title_type_map = {'图录': '图录格式', '目录': '目录格式', '表录': '表录格式'}
                if isinstance(format_reports, list):
                    for fr in format_reports:
                        title_type = fr.get('title_type', '未知')
                        check_label = title_type_map.get(title_type, f'{title_type}格式')
                        format_report = fr.get('report', {})
                        if isinstance(format_report, dict) and 'ok' in format_report:
                            if format_report.get('ok', False):
                                lines.append(f"  [{check_label}] ✓ 符合规范")
                            else:
                                msgs = format_report.get('messages', [])
                                if msgs:
                                    lines.append(f"  [{check_label}] ✗ 发现 {len(msgs)} 项问题")
                                    for msg in msgs:
                                        lines.append(f"    • {msg}")
            
            # Formula模块：[公式检测] 和 [编号] 始终显示
            elif module_name == 'Formula':
                # 按 formula_label 分组，从 formula_paragraphs 中提取每个公式的错误
                formula_paragraphs = report.get('details', {}).get('formula_paragraphs', [])
                all_formula_issues = {}  # formula_label -> [(check_label, msg)]
                for fp in formula_paragraphs:
                    fcheck = fp.get('format_check', {})
                    if not isinstance(fcheck, dict):
                        continue
                    label = fp.get('formula_label', '公式')
                    if not fcheck.get('ok', True):
                        for msg in fcheck.get('messages', []):
                            if label not in all_formula_issues:
                                all_formula_issues[label] = []
                            all_formula_issues[label].append(msg)

                if all_formula_issues:
                    total = sum(len(v) for v in all_formula_issues.values())
                    lines.append(f"\n  [公式检测] ✗ 发现 {total} 项问题（涉及 {len(all_formula_issues)} 个公式）")
                    for label, msgs in all_formula_issues.items():
                        for msg in msgs:
                            # 去掉消息中已包含的公式标签前缀（避免显示重复）
                            prefix = f"{label}: "
                            display_msg = msg[len(prefix):] if msg.startswith(prefix) else msg
                            lines.append(f"    • [{label}] {display_msg}")
                else:
                    lines.append(f"\n  [公式检测] ✓ 符合规范")

                numbering = report.get('numbering', {})
                if isinstance(numbering, dict) and 'ok' in numbering:
                    if numbering.get('ok', False):
                        lines.append(f"  [编号] ✓ 符合规范")
                    else:
                        msgs = numbering.get('messages', [])
                        if msgs:
                            lines.append(f"  [编号] ✗ 发现 {len(msgs)} 项问题")
                            for msg in msgs:
                                lines.append(f"    • {msg}")

            # Title/Keywords双语模块：每个检查项始终显示，通过时✓符合规范，失败时✗发现N项问题
            elif module_name in ['Keywords', 'Title'] and 'chinese' in report and 'english' in report:
                chinese_report = report.get('chinese', {})
                if chinese_report and not chinese_report.get('error'):
                    if module_name == 'Keywords':
                        lines.append("\n  【中文关键词】")
                    elif module_name == 'Title':
                        lines.append("\n  【中文标题】")

                    exclude_keys = ['summary', 'extracted', 'details', 'language']
                    if module_name == 'Keywords':
                        exclude_keys.extend(['keywords_paragraph', 'keywords_text', 'keywords_list'])
                    elif module_name == 'Title':
                        exclude_keys.extend(['title_paragraph', 'title_text'])

                    for section_key, section_value in chinese_report.items():
                        if section_key in exclude_keys:
                            continue

                        if isinstance(section_value, dict) and 'ok' in section_value:
                            section_title = CHECK_NAMES_CN.get(f'chinese_{section_key}',
                                CHECK_NAMES_CN.get(section_key, section_key.replace('_', ' ').title()))
                            messages = section_value.get('messages', [])
                            # 过滤掉 "XXX格式问题：" 这类前缀头消息和以"问题"结尾的消息
                            filtered = [m for m in messages if not m.rstrip('：').rstrip(':').endswith('格式问题') and not m.rstrip('：').rstrip(':').endswith('问题')]
                            if section_value.get('ok', False):
                                lines.append(f"    [{section_title}] ✓ 符合规范")
                            elif filtered:
                                lines.append(f"    [{section_title}] ✗ 发现 {len(filtered)} 项问题")
                                for msg in filtered:
                                    lines.append(f"      • {msg}")

                english_report = report.get('english', {})
                if english_report and not english_report.get('error'):
                    if module_name == 'Keywords':
                        lines.append("\n  【英文关键词】")
                    elif module_name == 'Title':
                        lines.append("\n  【英文标题】")

                    exclude_keys = ['summary', 'extracted', 'details', 'language']
                    if module_name == 'Keywords':
                        exclude_keys.extend(['keywords_paragraph', 'keywords_text', 'keywords_list'])
                    elif module_name == 'Title':
                        exclude_keys.extend(['title_paragraph', 'title_text'])

                    for section_key, section_value in english_report.items():
                        if section_key in exclude_keys:
                            continue

                        if isinstance(section_value, dict) and 'ok' in section_value:
                            section_title = CHECK_NAMES_CN.get(f'english_{section_key}',
                                CHECK_NAMES_CN.get(section_key, section_key.replace('_', ' ').title()))
                            messages = section_value.get('messages', [])
                            # 过滤掉 "XXX格式问题：" 这类前缀头消息和以"问题"结尾的消息
                            filtered = [m for m in messages if not m.rstrip('：').rstrip(':').endswith('格式问题') and not m.rstrip('：').rstrip(':').endswith('问题')]
                            if section_value.get('ok', False):
                                lines.append(f"    [{section_title}] ✓ 符合规范")
                            elif filtered:
                                lines.append(f"    [{section_title}] ✗ 发现 {len(filtered)} 项问题")
                                for msg in filtered:
                                    lines.append(f"      • {msg}")

            else:
                # 其他模块的常规处理（Abstract、English_Abstract、Content等）：每个检查项始终显示
                for section_key, section_value in report.items():
                    if section_key in ['summary', 'extracted', 'details']:
                        continue

                    if isinstance(section_value, dict) and 'ok' in section_value:
                        section_title = CHECK_NAMES_CN.get(section_key, section_key.replace('_', ' ').title())
                        messages = section_value.get('messages', [])
                        # 过滤掉 "XXX格式问题：" 这类前缀头消息和以"问题"结尾的消息
                        filtered = [m for m in messages if not m.rstrip('：').rstrip(':').endswith('格式问题') and not m.rstrip('：').rstrip(':').endswith('问题')]
                        if section_value.get('ok', False):
                            lines.append(f"  [{section_title}] ✓ 符合规范")
                        elif filtered:
                            lines.append(f"\n  [{section_title}] ✗ 发现 {len(filtered)} 项问题")
                            for msg in filtered:
                                lines.append(f"    • {msg}")

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


    def process_report(self, all_reports):
        """对所有的检测报告进行处理"""
        try:
            # 标准化所有结果
            all_results = {}
            for module_name, report in all_reports.items():
                all_results[module_name] = self._normalize_report(report, module_name)
            
            # 计算统计信息
            total_checks = 0
            passed_checks = 0
            
            for module_name, module_result in all_results.items():
                checks = module_result.get('checks', {})
                for check_name, check_result in checks.items():
                    if isinstance(check_result, dict) and 'ok' in check_result:
                        total_checks += 1
                        if check_result.get('ok', False):
                            passed_checks += 1
            
            failed_checks = total_checks - passed_checks
            pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
            
            summary = {
                'total_checks': total_checks,
                'passed_checks': passed_checks,
                'failed_checks': failed_checks,
                'pass_rate': round(pass_rate, 2)
            }
            
            message = f"格式检测完成，通过率: {pass_rate:.1f}%"
            
            return self._format_response(
                success=True,
                data={
                    'results': all_results,
                    'summary': summary
                },
                message=message,
                status_code=200
            )
            
        except Exception as e:
            error_msg=f"对检测报告进行处理失败：{str(e)}"
            logger.error(error_msg)
            return self._format_response(
                success=False,
                message=error_msg,
                status_code=404)
    
    def generate_report(self, check_results: Dict[str, Any], 
                       output_path: Optional[str] = None) -> Dict[str, Any]:
        """生成文本格式的检测报告"""
        try:
            logger.info("开始生成检测报告")
            
            if not check_results or not check_results.get('success'):
                return self._format_response(
                    success=False,
                    message="无效的检测结果",
                    status_code=400
                )
            
            data = check_results.get('data', {})
            results = data.get('results', {})
            summary = data.get('summary', {})
            
            # 生成报告文本
            lines = []
            lines.append("=" * 80)
            lines.append("论文格式检测综合报告")
            lines.append("=" * 80)
            lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            
            # 总体评估
            lines.append("【总体评估】")
            lines.append(f"总检测项数: {summary.get('total_checks', 0)}")
            lines.append(f"通过项数: {summary.get('passed_checks', 0)}")
            lines.append(f"失败项数: {summary.get('failed_checks', 0)}")
            lines.append(f"通过率: {summary.get('pass_rate', 0)}%")
            lines.append("")
            
            # 各模块详细报告
            for module_name in DETECTION_ORDER:
                if module_name not in results:
                    continue
                
                module_result = results[module_name]
                
                lines.append("-" * 80)
                lines.append(f"【{module_name} 检测报告】")
                lines.append("-" * 80)
                
                checks = module_result.get('checks', {})
                for check_name, check_result in checks.items():
                    if not isinstance(check_result, dict):
                        continue
                    
                    ok_status = "✓ 通过" if check_result.get('ok', False) else "✗ 失败"
                    lines.append(f"\n  [{check_name}] {ok_status}")
                    
                    messages = check_result.get('messages', [])
                    if messages:
                        for msg in messages:
                            lines.append(f"    • {msg}")
                
                # 添加总结
                summary_list = module_result.get('summary', [])
                if summary_list:
                    lines.append("\n  【总结】")
                    for summary_item in summary_list:
                        lines.append(f"    {summary_item}")
                
                lines.append("")
            
            # 报告尾部
            lines.append("=" * 80)
            lines.append("报告结束")
            lines.append("=" * 80)
            
            report_text = "\n".join(lines)
            
            # 保存报告文件
            file_path = None
            if output_path:
                try:
                    output_dir = os.path.dirname(output_path)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(report_text)
                    
                    file_path = output_path
                    logger.info(f"报告已保存到: {file_path}")
                except Exception as e:
                    logger.error(f"保存报告文件失败: {e}")
            
            return self._format_response(
                success=True,
                data={
                    'report_text': report_text,
                    'file_path': file_path
                },
                message='报告生成成功',
                status_code=200
            )
            
        except Exception as e:
            return self._handle_exception(e, 'ReportGeneration')
    