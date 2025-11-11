"""
论文服务
从 app.py 中提取论文相关业务逻辑，保持完全兼容
集成数据层权限控制
"""
from models import Paper, Journal, db
from services.permission_service import PermissionService
import logging

logger = logging.getLogger(__name__)

class PaperService:
    """论文服务类"""
    
    def get_papers(self, journal_id=None, user=None):
        """
        获取论文列表 - 集成数据层权限控制
        返回格式与原来完全一致
        """
        try:
            # 使用权限服务获取可访问的论文
            accessible_papers = PermissionService.get_accessible_papers(user, journal_id)
            paper_list = []
            
            for paper in accessible_papers:
                paper_list.append({
                    'id': paper.id,
                    'journal_id': paper.journal_id,
                    'title': paper.title,
                    'authors': paper.authors,
                    'first_author': paper.first_author,
                    'corresponding': paper.corresponding,
                    'doi': paper.doi,
                    'page_start': paper.page_start,
                    'page_end': paper.page_end,
                    'pdf_pages': paper.pdf_pages,
                    'manuscript_id': paper.manuscript_id,
                    'chinese_title': paper.chinese_title,
                    'chinese_authors': paper.chinese_authors,
                    'issue': paper.issue,
                    'is_dhu': paper.is_dhu,
                    'abstract': paper.abstract,
                    'keywords': paper.keywords,
                    'file_path': paper.file_path,
                    'created_at': paper.created_at.isoformat() if paper.created_at else None
                })
            
            return {'success': True, 'data': paper_list}
        
        except Exception as e:
            logger.error(f"获取论文列表错误: {str(e)}")
            return {'success': False, 'message': f'获取论文列表失败: {str(e)}', 'status_code': 500}
    
    def create_paper(self, data, user=None):
        """
        创建论文 - 集成数据层权限控制
        返回格式与原来完全一致
        """
        try:
            # 验证必填字段
            required_fields = ['journal_id', 'title', 'authors', 'first_author', 'page_start', 'manuscript_id']
            for field in required_fields:
                if not data.get(field):
                    return {'success': False, 'message': f'缺少必填字段: {field}', 'status_code': 400}
            
            # 检查期刊是否存在
            journal = Journal.query.get(data['journal_id'])
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 检查创建权限
            if not PermissionService.can_edit_journal(user, journal):
                return {
                    'success': False,
                    'message': '您没有权限在此期刊中创建论文',
                    'status_code': 403
                }
            
            # 创建新论文
            new_paper = Paper(
                journal_id=data['journal_id'],
                title=data['title'],
                authors=data['authors'],
                first_author=data['first_author'],
                corresponding=data.get('corresponding', ''),
                doi=data.get('doi', ''),
                page_start=data['page_start'],
                page_end=data.get('page_end'),
                pdf_pages=data.get('pdf_pages'),
                manuscript_id=data['manuscript_id'],
                is_dhu=data.get('is_dhu', False),
                abstract=data.get('abstract', ''),
                keywords=data.get('keywords', ''),
                file_path=data.get('file_path', ''),
                chinese_title=data.get('chinese_title', ''),
                chinese_authors=data.get('chinese_authors', '')
            )
            
            db.session.add(new_paper)
            db.session.commit()
            
            logger.info(f"新论文创建成功: {new_paper.title} (创建者: {user.id if user else '未知'})")
            
            return {
                'success': True,
                'message': '论文创建成功',
                'paper': {
                    'id': new_paper.id,
                    'title': new_paper.title,
                    'authors': new_paper.authors,
                    'first_author': new_paper.first_author,
                    'manuscript_id': new_paper.manuscript_id
                }
            }
        
        except Exception as e:
            logger.error(f"创建论文错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'创建论文失败: {str(e)}', 'status_code': 500}
    
    def update_paper(self, paper_id, data, user=None):
        """
        更新论文 - 集成数据层权限控制
        返回格式与原来完全一致
        """
        try:
            paper = Paper.query.get(paper_id)
            if not paper:
                return {'success': False, 'message': '论文不存在', 'status_code': 404}
            
            # 检查编辑权限
            if not PermissionService.can_edit_paper(user, paper):
                return {
                    'success': False,
                    'message': '您没有权限编辑此论文',
                    'status_code': 403
                }
            
            # 更新字段
            if 'title' in data:
                paper.title = data['title']
            if 'authors' in data:
                paper.authors = data['authors']
            if 'first_author' in data:
                paper.first_author = data['first_author']
            if 'corresponding' in data:
                paper.corresponding = data['corresponding']
            if 'doi' in data:
                paper.doi = data['doi']
            if 'page_start' in data:
                paper.page_start = data['page_start']
            if 'page_end' in data:
                paper.page_end = data['page_end']
            if 'pdf_pages' in data:
                paper.pdf_pages = data['pdf_pages']
            if 'manuscript_id' in data:
                paper.manuscript_id = data['manuscript_id']
            if 'is_dhu' in data:
                paper.is_dhu = data['is_dhu']
            if 'abstract' in data:
                paper.abstract = data['abstract']
            if 'keywords' in data:
                paper.keywords = data['keywords']
            
            db.session.commit()
            
            logger.info(f"论文更新成功: {paper.title} (更新者: {user.id if user else '未知'})")
            
            return {
                'success': True,
                'message': '论文更新成功'
            }
        
        except Exception as e:
            logger.error(f"更新论文错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'更新论文失败: {str(e)}', 'status_code': 500}
    
    def delete_paper(self, paper_id, user=None):
        """
        删除论文 - 集成数据层权限控制
        返回格式与原来完全一致
        """
        try:
            paper = Paper.query.get(paper_id)
            if not paper:
                return {'success': False, 'message': '论文不存在', 'status_code': 404}
            
            # 检查删除权限
            if not PermissionService.can_delete_paper(user, paper):
                return {
                    'success': False,
                    'message': '您没有权限删除此论文',
                    'status_code': 403
                }
            
            # 获取期刊ID，用于后续更新paper_count
            journal_id = paper.journal_id
            
            # 删除论文
            db.session.delete(paper)
            db.session.commit()
            
            # 更新期刊的论文数量
            journal = Journal.query.get(journal_id)
            if journal:
                journal.paper_count = Paper.query.filter_by(journal_id=journal_id).count()
                db.session.commit()
                logger.info(f"期刊 {journal.title} 论文数量已更新为: {journal.paper_count}")
            
            logger.info(f"论文删除成功: {paper.title} (删除者: {user.id if user else '未知'})")
            
            return {
                'success': True,
                'message': '论文删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除论文错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'删除论文失败: {str(e)}', 'status_code': 500}
