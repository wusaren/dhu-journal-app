"""
导出服务
从 app.py 中提取导出相关业务逻辑，保持完全兼容
"""
from models import Journal, Paper
from services.document_generator import generate_toc_docx, generate_excel_stats, generate_tuiwen_content
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
    
    def export_excel(self, journal_id):
        """
        生成统计表 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
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
            
            # 直接使用数据库中的字段
            articles = []
            for paper in papers:
                article = {
                    'manuscript_id': paper.manuscript_id or '',
                    'pdf_pages': paper.pdf_pages or 0,
                    'first_author': paper.first_author or '',
                    'corresponding': paper.corresponding or '',
                    'issue': paper.issue or journal.issue,
                    'is_dhu': paper.is_dhu or False
                }
                articles.append(article)
                
                # 调试信息
                logger.info(f"论文数据: manuscript_id={article['manuscript_id']}, pdf_pages={article['pdf_pages']}, first_author={article['first_author']}, corresponding={article['corresponding']}, issue={article['issue']}, is_dhu={article['is_dhu']}")
            
            # 生成统计表Excel
            output_path = generate_excel_stats(articles, journal)
            
            return {
                'success': True,
                'message': '统计表生成成功',
                'downloadUrl': f'/api/download/{os.path.basename(output_path)}',
                'filePath': output_path
            }
        
        except Exception as e:
            logger.error(f"统计表生成错误: {str(e)}")
            return {'success': False, 'message': f'统计表生成失败: {str(e)}', 'status_code': 500}

