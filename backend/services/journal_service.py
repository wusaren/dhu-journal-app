"""
期刊服务
从 app.py 中提取期刊相关业务逻辑，保持完全兼容
"""
from models import Journal, Paper, db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class JournalService:
    """期刊服务类"""
    
    def get_all_journals(self):
        """
        获取所有期刊 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
        """
        try:
            journals = Journal.query.all()
            journal_list = []
            
            for journal in journals:
                papers = Paper.query.filter_by(journal_id=journal.id).order_by(Paper.page_start).all()
                journal_list.append({
                    'id': journal.id,
                    'title': journal.title,
                    'issue': journal.issue,
                    'publishDate': journal.publish_date.isoformat() if journal.publish_date else None,
                    'status': journal.status,
                    'description': journal.description,
                    'paperCount': journal.paper_count,
                    'createdAt': journal.created_at.isoformat() if journal.created_at else None
                })
            
            return {'success': True, 'data': journal_list}
        
        except Exception as e:
            logger.error(f"获取期刊列表错误: {str(e)}")
            return {'success': False, 'message': f'获取期刊列表失败: {str(e)}', 'status_code': 500}
    
    def create_journal(self, data):
        """
        创建期刊 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
        """
        try:
            # 验证必填字段
            required_fields = ['issue', 'title', 'publish_date', 'status']
            for field in required_fields:
                if not data.get(field):
                    return {'success': False, 'message': f'缺少必填字段: {field}', 'status_code': 400}
            
            # 检查期刊是否已存在
            existing_journal = Journal.query.filter_by(title=data['title'], issue=data['issue']).first()
            if existing_journal:
                return {
                    'success': False, 
                    'message': f'期刊"{data["title"]} - {data["issue"]}"已存在', 
                    'status_code': 400,
                    'duplicate': True
                }
            
            # 创建新期刊
            new_journal = Journal(
                title=data['title'],
                issue=data['issue'],
                publish_date=datetime.strptime(data['publish_date'], '%Y-%m-%d').date(),
                status=data['status'],
                description=data.get('description', ''),
                created_by=1  # 默认管理员用户ID
            )
            
            db.session.add(new_journal)
            db.session.commit()
            
            logger.info(f"新期刊创建成功: {new_journal.issue}")
            
            return {
                'success': True,
                'message': '期刊创建成功',
                'journal': {
                    'id': new_journal.id,
                    'title': new_journal.title,
                    'issue': new_journal.issue,
                    'publishDate': new_journal.publish_date.isoformat(),
                    'status': new_journal.status,
                    'description': new_journal.description
                }
            }
        
        except Exception as e:
            logger.error(f"创建期刊错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'创建期刊失败: {str(e)}', 'status_code': 500}
    
    def delete_journal(self, journal_id):
        """
        删除期刊 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
        """
        try:
            journal = Journal.query.get(journal_id)
            if not journal:
                return {'success': False, 'message': '期刊不存在', 'status_code': 404}
            
            # 获取关联的论文数量
            papers_count = Paper.query.filter_by(journal_id=journal_id).count()
            
            # 如果期刊下还有论文，不允许删除
            if papers_count > 0:
                return {
                    'success': False,
                    'message': f'无法删除期刊，该期刊下还有 {papers_count} 篇论文。请先删除所有论文后再删除期刊。',
                    'papers_count': papers_count,
                    'status_code': 400,
                    'duplicate': True
                }
            
            # 删除期刊
            db.session.delete(journal)
            db.session.commit()
            
            logger.info(f"期刊删除成功: {journal.title} - {journal.issue}")
            
            return {
                'success': True,
                'message': '期刊删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除期刊错误: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': f'删除期刊失败: {str(e)}', 'status_code': 500}
