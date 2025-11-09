"""
导出服务
从 app.py 中提取导出相关业务逻辑，保持完全兼容
"""
from models import Journal, Paper, JournalTemplate
from services.document_generator import generate_toc_docx, generate_excel_stats, generate_excel_stats_from_template, generate_tuiwen_content
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
    
    def export_tuiwen(self, journal_id):
        """
        生成推文 - 从 app.py 中提取，保持完全兼容
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
                return {'success': False, 'message': '该期刊没有论文数据，无法生成推文', 'status_code': 400}
            
            # 生成推文文档
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
        生成统计表 - 支持自定义列配置和模板生成
        columns_config: 列配置列表，格式: [{'key': 'manuscript_id', 'order': 1}, ...]
                       如果期刊有模板，此参数会被忽略，使用模板配置
        """
        try:
            # 获取期刊信息
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 检查是否有模板
            template = JournalTemplate.query.filter_by(journal_id=journal_id).first()
            
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
            
            # 如果有模板，使用模板生成
            if template and template.template_file_path and template.column_mapping:
                logger.info(f"使用模板生成统计表: {template.template_file_path}")
                output_path = generate_excel_stats_from_template(
                    articles, 
                    journal, 
                    template.template_file_path, 
                    template.column_mapping
                )
            else:
                # 否则使用原来的逻辑
                logger.info("使用默认方式生成统计表")
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

