"""
导出服务
从 app.py 中提取导出相关业务逻辑，保持完全兼容
"""
from models import Journal, Paper
from services.document_generator import generate_toc_docx, generate_excel_stats, generate_excel_stats_from_template, generate_tuiwen_content
from typing import List, Dict
import os
import logging

logger = logging.getLogger(__name__)

class ExportService:
    """导出服务类"""
    
    def export_toc(self, journal_id):
        """
        生成目录 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
        """
        try:
            # 获取期刊信息
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 获取论文信息，按页码排序
            papers = Paper.query.filter_by(journal_id=journal_id).order_by(Paper.page_start).all()
            
            # 如果没有论文数据，返回错误
            if not papers:
                return {'success': False, 'message': '该期刊没有论文数据，无法生成目录', 'status_code': 400}
            
            # 生成目录文档
            output_path = generate_toc_docx(papers, journal)
            
            return {
                'success': True,
                'message': '目录生成成功',
                'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
                'filePath': output_path
            }
        
        except Exception as e:
            logger.error(f"目录生成错误: {str(e)}")
            return {'success': False, 'message': f'目录生成失败: {str(e)}', 'status_code': 500}
    
    # def export_tuiwen(self, journal_id, user_id=None):
    def export_tuiwen(self, journal_id):
        """
        生成推文 - 支持用户级别的推文模板配置
        返回格式与原来完全兼容
        """
        try:
            # 获取期刊信息
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 获取论文信息，按页码排序
            papers = Paper.query.filter_by(journal_id=journal_id).order_by(Paper.page_start).all()
            
            # 如果没有论文数据，返回错误
            if not papers:
                return {'success': False, 'message': '该期刊没有论文数据，无法生成推文', 'status_code': 400}
            
            # 使用默认格式生成推文（从JSON文件加载配置或硬编码后备）
            output_path = generate_tuiwen_content(papers, journal)
            
            return {
                'success': True,
                'message': '推文生成成功',
                'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
                'filePath': output_path
            }
        
        except Exception as e:
            logger.error(f"推文生成错误: {str(e)}")
            return {'success': False, 'message': f'推文生成失败: {str(e)}', 'status_code': 500}
    
    def export_excel(self, journal_id, columns_config=None):
        """
        生成统计表 - 使用列配置或默认配置
        注意：用户模板配置的检查由 app.py 路由层负责，此方法只负责生成统计表
        
        Args:
            journal_id: 期刊ID
            columns_config: 列配置列表，格式: [{'key': 'manuscript_id', 'order': 1}, ...]
                          如果为None，将从默认配置文件加载（default_stats_columns.json）
        
        Returns:
            {'success': True/False, 'message': '...', 'downloadUrl': '...', 'filePath': '...'}
        """
        try:
            # 获取期刊信息
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 获取论文信息，按页码排序
            papers = Paper.query.filter_by(journal_id=journal_id).order_by(Paper.page_start).all()
            
            logger.info(f"期刊 {journal_id} 找到 {len(papers)} 篇论文")
            
            # 如果没有论文数据，返回错误
            if not papers:
                return {'success': False, 'message': '该期刊没有论文数据，请先上传并解析PDF文件', 'status_code': 400}
            
            # 构建论文数据（包含所有可能需要的字段）
            articles = []
            for paper in papers:
                article = {
                    'manuscript_id': paper.manuscript_id or '',
                    'pdf_pages': paper.pdf_pages or 0,
                    'first_author': paper.first_author or '',
                    'corresponding': paper.corresponding or '',
                    'authors': paper.authors or '',
                    'issue': paper.issue or journal.issue,
                    'is_dhu': paper.is_dhu or False,
                    'title': paper.title or '',
                    'chinese_title': getattr(paper, 'chinese_title', None) or '',
                    'chinese_authors': getattr(paper, 'chinese_authors', None) or '',
                    'doi': paper.doi or '',
                    'page_start': paper.page_start,
                    'page_end': paper.page_end,
                }
                articles.append(article)
            
            # 生成统计表Excel（如果 columns_config 为 None，generate_excel_stats 会从默认配置文件加载）
            output_path = generate_excel_stats(articles, journal, columns_config)
            
            return {
                'success': True,
                'message': '统计表生成成功',
                'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
                'filePath': output_path
            }
        
        except Exception as e:
            logger.error(f"统计表生成错误: {str(e)}")
            return {'success': False, 'message': f'统计表生成失败: {str(e)}', 'status_code': 500}
    
    def export_excel_with_template(self, journal_id, template_file_path: str, column_mapping: List[Dict]):
        """
        基于模板生成统计表
        """
        try:
            # 获取期刊信息
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 获取论文信息，按页码排序
            papers = Paper.query.filter_by(journal_id=journal_id).order_by(Paper.page_start).all()
            
            logger.info(f"期刊 {journal_id} 找到 {len(papers)} 篇论文")
            
            # 如果没有论文数据，返回错误
            if not papers:
                return {'success': False, 'message': '该期刊没有论文数据，请先上传并解析PDF文件', 'status_code': 400}
            
            # 构建论文数据（包含所有可能需要的字段）
            articles = []
            for paper in papers:
                article = {
                    'manuscript_id': paper.manuscript_id or '',
                    'pdf_pages': paper.pdf_pages or 0,
                    'first_author': paper.first_author or '',
                    'corresponding': paper.corresponding or '',
                    'authors': paper.authors or '',
                    'issue': paper.issue or journal.issue,
                    'is_dhu': paper.is_dhu or False,
                    'title': paper.title or '',
                    'chinese_title': getattr(paper, 'chinese_title', None) or '',
                    'chinese_authors': getattr(paper, 'chinese_authors', None) or '',
                    'doi': paper.doi or '',
                    'page_start': paper.page_start,
                    'page_end': paper.page_end,
                }
                articles.append(article)
            
            # 基于模板生成统计表Excel
            output_path = generate_excel_stats_from_template(articles, journal, template_file_path, column_mapping)
            
            return {
                'success': True,
                'message': '统计表生成成功',
                'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
                'filePath': output_path
            }
        
        except Exception as e:
            logger.error(f"基于模板生成统计表错误: {str(e)}")
            return {'success': False, 'message': f'统计表生成失败: {str(e)}', 'status_code': 500}
