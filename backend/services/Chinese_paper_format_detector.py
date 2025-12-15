"""
论文格式检测核心模块
从 Paper_detect 项目整合而来，提供独立的格式检测功能
"""

import os
import json
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ChinesePaperFormatDetector:
    """
    论文格式检测器核心类
    整合了Title、Abstract、Keywords、Content、Figure、Formula、Table等检测模块
    """
    
    def __init__(self, templates_dir: str = None):
        """
        初始化检测器
        Args:
            templates_dir: 模板文件目录，默认为 paper_detect_templates
        """
        if templates_dir is None:
            self.templates_dir = 'Chinese_paper_detect_templates'
        else:
            self.templates_dir = Path(templates_dir)

        self.templates_dir = Path(__file__).parent / self.templates_dir
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"模板目录不存在: {self.templates_dir}")
        
        logger.info(f"论文格式检测器已初始化，模板目录: {self.templates_dir}")
        
        # 导入检测模块（延迟导入以支持灵活部署）
        self._import_detection_modules()
    
    def _import_detection_modules(self):
        """导入所有检测模块"""
        try:
            # 导入检测模块
            from services.paper_detect import Title_detect
            from services.Chinese_paper_detect import Abstract_detect
            from services.Chinese_paper_detect import English_Abstract_detect
            from services.Chinese_paper_detect import Keywords_detect_unified as Keywords_detect
            from services.paper_detect import Content_detect
            from services.paper_detect import Figure_detect
            from services.paper_detect import Formula_detect
            from services.paper_detect import Table_detect
            from services.paper_detect import Chinese_section_detect
            
            # 保存模块引用
            self.modules = {
                'Title': Title_detect,
                'Abstract': Abstract_detect,
                'English_Abstract': English_Abstract_detect,
                'Keywords': Keywords_detect,
                'Content': Content_detect,
                'Figure': Figure_detect,
                'Formula': Formula_detect,
                'Table': Table_detect,
                'Chinese_section': Chinese_section_detect
            }
            
            logger.info("所有检测模块已加载")
            
        except ImportError as e:
            logger.error(f"导入检测模块失败: {e}")
    
    def _load_template(self, template_name: str) -> Dict[str, Any]:
        """
        加载JSON模板文件
        
        Args:
            template_name: 模板名称（如 'Title.json' 或 'Title'）
        
        Returns:
            模板数据字典
        """
        if not template_name.endswith('.json'):
            template_name = f"{template_name}.json"
        
        template_path = self.templates_dir / template_name
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def detect_title(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测标题、作者、单位格式
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Title.json')
            Title_detect = self.modules['Title']
            
            result = Title_detect.check_doc_with_template(docx_path, template_path, skip_checks)
            return result
            
        except Exception as e:
            logger.error(f"标题检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'标题检测失败: {e}']
            }
    
    def detect_abstract(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测摘要格式
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Abstract.json')
            Abstract_detect = self.modules['Abstract']
            
            result = Abstract_detect.check_abstract_with_template(docx_path, template_path, skip_checks)
            return result
            
        except Exception as e:
            logger.error(f"摘要检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'摘要检测失败: {e}']
            }
    def detect_english_abstract(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测摘要格式
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'English_Abstract.json')
            English_Abstract_detect = self.modules['English_Abstract']
            
            return English_Abstract_detect.check_english_abstract_with_template(docx_path, template_path, skip_checks)
            
        except Exception as e:
            logger.error(f"摘要检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'摘要检测失败: {e}']
            }    
    def detect_keywords(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测关键词格式（双语检测：同时检测中文和英文关键词）
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典，包含 'chinese'、'english' 和 'summary' 字段
        """
        try:
            chinese_template_path = str(self.templates_dir / 'Keywords.json')
            english_template_path = str(self.templates_dir / 'English_Keywords.json')
            Keywords_detect = self.modules['Keywords']
            
            # 执行双语关键词检测
            result = Keywords_detect.check_bilingual_keywords(
                docx_path, 
                chinese_template=chinese_template_path,
                english_template=english_template_path,
                skip_checks=skip_checks
            )
            
            # 确保返回结果包含必要的字段
            if 'chinese' not in result:
                result['chinese'] = {'error': True, 'error_message': '中文关键词检测未执行'}
            if 'english' not in result:
                result['english'] = {'error': True, 'error_message': '英文关键词检测未执行'}
            if 'summary' not in result:
                result['summary'] = []
            
            return result
            
        except Exception as e:
            logger.error(f"关键词检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'chinese': {'error': True, 'error_message': str(e)},
                'english': {'error': True, 'error_message': str(e)},
                'summary': [f'关键词检测失败: {e}']
            }
    
    def detect_content(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测正文格式
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Content.json')
            Content_detect = self.modules['Content']
            
            result = Content_detect.check_content_with_template(docx_path, template_path, skip_checks)
            return result
            
        except Exception as e:
            logger.error(f"正文检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'正文检测失败: {e}']
            }
    
    def detect_figure(self, docx_path: str, enable_content_check: bool = False,
                     skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测图片格式
        
        Args:
            docx_path: Word文档路径
            enable_content_check: 是否启用内容API检测
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Figure.json')
            Figure_detect = self.modules['Figure']
            
            result = Figure_detect.check_doc_with_template(
                docx_path, 
                template_path,
                enable_content_check=enable_content_check,
                skip_checks=skip_checks
            )
            return result
            
        except Exception as e:
            logger.error(f"图片检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'图片检测失败: {e}']
            }
    
    def detect_formula(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测公式格式
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Formula.json')
            Formula_detect = self.modules['Formula']
            
            result = Formula_detect.check_doc_with_template(docx_path, template_path, skip_checks)
            return result
            
        except Exception as e:
            logger.error(f"公式检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'公式检测失败: {e}']
            }
    
    def detect_table(self, docx_path: str, skip_checks: List[str] = None) -> Dict[str, Any]:
        """
        检测表格格式
        
        Args:
            docx_path: Word文档路径
            skip_checks: 要跳过的检测项列表
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Table.json')
            Table_detect = self.modules['Table']
            
            result = Table_detect.check_doc_with_template(docx_path, template_path, skip_checks)
            return result
            
        except Exception as e:
            logger.error(f"表格检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'表格检测失败: {e}']
            }
    
    def detect_chinese_section(self, docx_path: str) -> Dict[str, Any]:
        """
        检测中文部分格式（中文标题、作者、单位、摘要和关键词）
        
        Args:
            docx_path: Word文档路径
        
        Returns:
            检测结果字典
        """
        try:
            template_path = str(self.templates_dir / 'Chinese_section.json')
            Chinese_section_detect = self.modules['Chinese_section']
            
            result = Chinese_section_detect.check_chinese_section_with_template(docx_path, template_path)
            return result
            
        except Exception as e:
            logger.error(f"中文部分检测失败: {e}", exc_info=True)
            return {
                'error': True,
                'error_message': str(e),
                'summary': [f'中文部分检测失败: {e}']
            }
    
    def detect_all(self, docx_path: str, modules: List[str] = None,
                   enable_figure_api: bool = False,
                   skip_checks: Dict[str, List[str]] = None) -> Dict[str, Any]:
        """
        执行全量检测
        
        Args:
            docx_path: Word文档路径
            modules: 指定检测的模块列表，None表示检测所有模块
            enable_figure_api: 是否启用图片内容API检测
            skip_checks: 跳过检测项字典，格式：{"Title": ["bold", "font_size"], "Abstract": ["font_size"]}
        
        Returns:
            包含所有模块检测结果的字典
        """
        if modules is None:
            modules = ['Title', 'Abstract','English_Abstract', 'Keywords', 'Content', 'Formula', 'Figure', 'Table']
        
        if skip_checks is None:
            skip_checks = {}
        
        all_reports = {}
        
        for module_name in modules:
            logger.info(f"执行 {module_name} 检测")
            
            # 获取当前模块的跳过检测项配置
            module_skip_checks = skip_checks.get(module_name, [])
            
            try:
                if module_name == 'Title':
                    result = self.detect_title(docx_path, module_skip_checks)
                elif module_name == 'Abstract':
                    result = self.detect_abstract(docx_path, module_skip_checks)
                elif module_name == 'English_Abstract':
                    result = self.detect_english_abstract(docx_path, module_skip_checks)
                elif module_name == 'Keywords':
                    result = self.detect_keywords(docx_path, module_skip_checks)
                elif module_name == 'Content':
                    result = self.detect_content(docx_path, module_skip_checks)
                elif module_name == 'Figure':
                    result = self.detect_figure(docx_path, enable_content_check=enable_figure_api, 
                                                skip_checks=module_skip_checks)
                elif module_name == 'Formula':
                    result = self.detect_formula(docx_path, module_skip_checks)
                elif module_name == 'Table':
                    result = self.detect_table(docx_path, module_skip_checks)
                elif module_name == 'Chinese_section':
                    # 中文部分检测不支持跳过项
                    result = self.detect_chinese_section(docx_path)
                else:
                    logger.warning(f"未知模块: {module_name}")
                    continue
                
                all_reports[module_name] = result
                
            except Exception as e:
                logger.error(f"{module_name} 检测异常: {e}")
                all_reports[module_name] = {
                    'error': True,
                    'error_message': str(e),
                    'summary': [f'{module_name}检测失败: {e}']
                }
        
        return all_reports
    

