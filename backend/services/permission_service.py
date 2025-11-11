"""
权限控制服务
实现数据层权限控制，确保用户只能访问和操作自己创建的数据
"""
from flask_security import current_user
from models import User, Journal, Paper, FileUpload
import logging

logger = logging.getLogger(__name__)

class PermissionService:
    """权限控制服务类"""
    
    @staticmethod
    def can_view_journal(user, journal):
        """检查用户是否有权限查看期刊"""
        if not user or not journal:
            return False
            
        # 管理员可以查看所有期刊
        if user.has_role('admin'):
            return True
            
        # 编辑只能查看自己创建的期刊
        if user.has_role('editor'):
            return journal.created_by == user.id
            
        # 总编能查看所有的期刊
        if user.has_role('managing_editor'):
            return True
            
        return False
    
    @staticmethod
    def can_edit_journal(user, journal):
        """检查用户是否有权限编辑期刊"""
        if not user or not journal:
            return False
            
        # 管理员不可以编辑期刊
        if user.has_role('admin'):
            return False
            
        # 编辑只能编辑自己创建的期刊
        if user.has_role('editor'):
            return journal.created_by == user.id
        if user.has_role('managing_editor'):
            return True    
        return False
    
    @staticmethod
    def can_delete_journal(user, journal):
        """检查用户是否有权限删除期刊"""
        # 删除权限与编辑权限相同
        return PermissionService.can_edit_journal(user, journal)
    
    @staticmethod
    def can_view_paper(user, paper):
        """检查用户是否有权限查看论文"""
        if not user or not paper:
            return False
            
        # 管理员不可以查看论文
        if user.has_role('admin'):
            return False
            
        # 编辑只能查看自己创建的期刊中的论文
        if user.has_role('editor'):
            journal = Journal.query.get(paper.journal_id)
            return journal and journal.created_by == user.id
            
        # 总编能查看所用期刊中的论文
        if user.has_role('managing_editor'):
            return True
            
        return False
    
    @staticmethod
    def can_edit_paper(user, paper):
        """检查用户是否有权限编辑论文"""
        if not user or not paper:
            return False
            
        # 管理员不可以编辑论文
        if user.has_role('admin'):
            return False
            
        # 编辑只能编辑自己创建的期刊中的论文
        if user.has_role('editor'):
            journal = Journal.query.get(paper.journal_id)
            return journal and journal.created_by == user.id
        
        # 总编可以编辑论文
        if user.has_role('managing_editor'):
            return True
        return False
    @staticmethod
    def can_delete_paper(user, paper):
        """检查用户是否有权限删除论文"""
        # 删除权限与编辑权限相同
        return PermissionService.can_edit_paper(user, paper)
    
    @staticmethod
    def can_view_file(user, file_upload):
        """检查用户是否有权限查看文件"""
        if not user or not file_upload:
            return False
            
        # 管理员不可以查看所有文件
        if user.has_role('admin'):
            return False
            
        # 编辑只能查看自己创建的期刊中的文件
        if user.has_role('editor'):
            journal = Journal.query.get(file_upload.journal_id)
            return journal and journal.created_by == user.id
            
        # 总编能查看所有的文件
        if user.has_role('managing_editor'):
            return True
            
        return False
    
    @staticmethod
    def get_accessible_journals(user):
        """获取用户可以访问的期刊列表"""
        if not user:
            return []
            
        if user.has_role('admin'):
            return []
        elif user.has_role('editor'):
            return Journal.query.filter_by(created_by=user.id).all()
        elif user.has_role('managing_editor'):
            return Journal.query.all()
    
    @staticmethod
    def get_accessible_papers(user, journal_id=None):
        """获取用户可以访问的论文列表"""
        if not user or user.has_role('admin'):
            # 未登录用户和管理员不允许查看
            return []
        elif user.has_role('editor'):
            # 编辑只能看到自己创建的期刊中的论文
            user_journals = Journal.query.filter_by(created_by=user.id).all()
            user_journal_ids = [j.id for j in user_journals]
            
            if journal_id:
                if journal_id in user_journal_ids:
                    return Paper.query.filter_by(journal_id=journal_id).all()
                else:
                    return []
            else:
                return Paper.query.filter(Paper.journal_id.in_(user_journal_ids)).all()
        elif user.has_role('managing_editor'):
            # 总编只能看到所有期刊中的论文
            return Paper.query.all()
    
    @staticmethod
    def get_accessible_files(user):
        """获取用户可以访问的文件列表"""
        if not user or user.has_role('admin'):
            return []
            
        if user.has_role('managing_editor'):
            return FileUpload.query.all()
        elif user.has_role('editor'):
            # 编辑只能看到自己创建的期刊中的文件
            user_journals = Journal.query.filter_by(created_by=user.id).all()
            user_journal_ids = [j.id for j in user_journals]
            return FileUpload.query.filter(FileUpload.journal_id.in_(user_journal_ids)).all()
        else:
            return []
