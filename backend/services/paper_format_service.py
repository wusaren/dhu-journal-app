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
from services.document_annotator import generate_annotated_document
from services.paper_detect.Classification_detect import detect_classification

logger = logging.getLogger(__name__)

DETECTION_ORDER = ['Title', 'Abstract', 'Keywords', 'Content', 'Formula', 'Figure', 'Table', 'Chinese_section']

# 模块中文名称映射
MODULE_NAMES_CN = {
    'Title': '英文标题、作者与单位',
    'Abstract': '英文摘要',
    'Keywords': '英文关键词',
    'Content': '正文',
    'Formula': '公式',
    'Figure': '图',
    'Table': '表格',
    'Chinese_section': '中文部分',
    'Classification': '摘要分类号',
    # 中文部分内部项目
    'chinese_title_format': '中文标题',
    'chinese_author_format': '中文作者',
    'chinese_affiliation_format': '中文单位',
    'chinese_abstract_format': '中文摘要',
    'chinese_keywords_format': '中文关键词',
}

class PaperFormatService:
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
            templates_dir = 'paper_detect_templates'
            self.detector = PaperFormatDetector(templates_dir=str(templates_dir))
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
        
        # 提取summary、extracted和details
        summary = report.pop('summary', []) if isinstance(report, dict) else []
        extracted = report.pop('extracted', {}) if isinstance(report, dict) else {}
        details = report.pop('details', {}) if isinstance(report, dict) else {}
        
        # 剩余的都是检查项
        checks = {k: v for k, v in report.items() if isinstance(v, dict) and 'ok' in v}
        
        # 如果没有检查项，保留原始结构
        if not checks and isinstance(report, dict):
            if 'tables' in report or 'numbering' in report:
                checks = report
        
        # 确保所有数据都是JSON可序列化的
        # 这是关键步骤，防止Paragraph等对象导致序列化失败
        serializable_checks = self._make_json_serializable(checks)
        serializable_summary = self._make_json_serializable(summary)
        serializable_extracted = self._make_json_serializable(extracted)
        serializable_details = self._make_json_serializable(details)
        
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

        # 生成带批注文档
        annotated_path = generate_annotated_document(
            docx_path,
            all_reports,
            annotate_dir
        )
        if annotated_path:
            result['data']['annotated_saved'] = True
            result['data']['annotated_filename'] = os.path.basename(annotated_path)
            result['data']['annotated_download_url'] = f'/api/paper-format/download-annotated/{os.path.basename(annotated_path)}'
            logger.info(f"批注文档已自动生成: {annotated_path}")
        else:
            # 不影响检测结果的返回
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
                # Table模块特殊处理
                if module_name == 'Table':
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
            
            # Table模块需要特殊处理
            if module_name == 'Table':
                # 处理表格编号检查
                numbering = report.get('numbering', {})
                if isinstance(numbering, dict) and 'ok' in numbering:
                    ok_status = "✓ 通过" if numbering.get('ok', False) else "✗ 失败"
                    lines.append(f"\n  [Numbering] {ok_status}")
                    messages = numbering.get('messages', [])
                    if messages:
                        for msg in messages:
                            lines.append(f"    • {msg}")
                
                # 处理每个表格
                tables = report.get('tables', [])
                for i, table_report in enumerate(tables, 1):
                    caption_info = table_report.get('caption', {})
                    caption_text = caption_info.get('text', f'Table {i}')
                    lines.append(f"\n  [表格 {i}: {caption_text[:40]}{'...' if len(caption_text) > 40 else ''}]")
                    
                    # 标题格式
                    caption_format = table_report.get('caption_format', {})
                    if isinstance(caption_format, dict) and 'ok' in caption_format:
                        ok_status = "✓" if caption_format.get('ok', False) else "✗"
                        lines.append(f"    标题格式: {ok_status}")
                        messages = caption_format.get('messages', [])
                        if messages and not caption_format.get('ok', False):
                            for msg in messages:
                                lines.append(f"      • {msg}")
                    
                    # 表格样式
                    table_style = table_report.get('table_style', {})
                    if isinstance(table_style, dict) and 'ok' in table_style:
                        ok_status = "✓" if table_style.get('ok', False) else "✗"
                        lines.append(f"    表格样式: {ok_status}")
                        messages = table_style.get('messages', [])
                        if messages and not table_style.get('ok', False):
                            for msg in messages:
                                lines.append(f"      • {msg}")
                    
                    # 表格对齐
                    table_alignment = table_report.get('table_alignment', {})
                    if isinstance(table_alignment, dict) and 'ok' in table_alignment:
                        ok_status = "✓" if table_alignment.get('ok', False) else "✗"
                        lines.append(f"    内容对齐: {ok_status}")
                        messages = table_alignment.get('messages', [])
                        if messages and not table_alignment.get('ok', False):
                            for msg in messages:
                                lines.append(f"      • {msg}")
            
            # Chinese_section模块特殊处理
            elif module_name == 'Chinese_section':
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
        

            # Figure模块需要特殊处理（类似Table模块）
            elif module_name == 'Figure':
                # 处理图片编号检查
                numbering = report.get('numbering', {})
                if isinstance(numbering, dict) and 'ok' in numbering:
                    ok_status = "✓ 通过" if numbering.get('ok', False) else "✗ 失败"
                    lines.append(f"\n  [Numbering] {ok_status}")
                    messages = numbering.get('messages', [])
                    if messages:
                        for msg in messages:
                            lines.append(f"    • {msg}")
                
                # 处理每张图片
                figures = report.get('figures', [])
                for i, fig_report in enumerate(figures, 1):
                    caption_info = fig_report.get('caption_info', {})
                    if fig_report.get('has_caption', False):
                        caption_text = caption_info.get('full_text', f'Fig.{i}')
                        lines.append(f"\n  [图片 {i}: {caption_text[:40]}{'...' if len(caption_text) > 40 else ''}]")
                    else:
                        lines.append(f"\n  [图片 {i}: (无标题)]")
                    
                    # 标题格式
                    format_check = fig_report.get('format_check', {})
                    if isinstance(format_check, dict) and 'ok' in format_check:
                        ok_status = "✓" if format_check.get('ok', False) else "✗"
                        lines.append(f"    标题格式: {ok_status}")
                        messages = format_check.get('messages', [])
                        if messages and not format_check.get('ok', False):
                            for msg in messages:
                                lines.append(f"      • {msg}")
                    
                    # 图片对齐
                    picture_check = fig_report.get('picture_check', {})
                    if isinstance(picture_check, dict) and 'ok' in picture_check:
                        ok_status = "✓" if picture_check.get('ok', False) else "✗"
                        lines.append(f"    图片对齐: {ok_status}")
                        messages = picture_check.get('messages', [])
                        if messages and not picture_check.get('ok', False):
                            for msg in messages:
                                lines.append(f"      • {msg}")

                    # 内容检测
                    content_check = fig_report.get('content_check', {})
                    if isinstance(content_check, dict) and 'ok' in content_check:
                        ok_status = "✓" if content_check.get('ok', False) else "✗"
                        lines.append(f"    内容规范: {ok_status}")
                        messages = content_check.get('messages', [])
                        if messages and not content_check.get('ok', False):
                            for msg in messages:
                                lines.append(f"      • {msg}")
            
            else:
                # 其他模块的常规处理
                for section_key, section_value in report.items():
                    if section_key in ['summary', 'extracted', 'details']:
                        continue
                    
                    if isinstance(section_value, dict) and 'ok' in section_value:
                        # 检测项标题
                        # 优先从中文映射获取，否则进行转换
                        section_title = MODULE_NAMES_CN.get(section_key, section_key.replace('_', ' ').title())
                        ok_status = "✓ 通过" if section_value.get('ok', False) else "✗ 失败"
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
                # Classification暂时跳过，其不是字典结构，不能使用_normalize_report函数处理
                if module_name == 'Classification':
                    continue
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
    
