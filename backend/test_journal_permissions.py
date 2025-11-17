#!/usr/bin/env python3
"""
测试期刊权限和论文显示问题
"""

from app import app, db, User, Journal, Paper
from flask_security import SQLAlchemyUserDatastore

def check_journal_created_by():
    """检查所有期刊的created_by字段"""
    with app.app_context():
        print("=== 检查所有期刊的created_by字段 ===")
        
        journals = Journal.query.all()
        
        for journal in journals:
            print(f"期刊: {journal.title} - {journal.issue} (ID: {journal.id})")
            print(f"created_by: {journal.created_by}")
            print(f"论文数量: {journal.paper_count}")
            
            # 检查该期刊下的论文
            papers = Paper.query.filter_by(journal_id=journal.id).all()
            print(f"实际论文数量: {len(papers)}")
            
            for paper in papers:
                print(f"  - 论文: {paper.title} (ID: {paper.id})")
            
            print("-" * 50)

def check_user_journals():
    """检查用户创建的期刊"""
    with app.app_context():
        print("\n=== 检查用户创建的期刊 ===")
        
        user_datastore = SQLAlchemyUserDatastore(db, User, Journal)
        
        # 获取所有用户
        users = User.query.all()
        
        for user in users:
            print(f"用户: {user.username} (ID: {user.id})")
            print(f"角色: {[role.name for role in user.roles]}")
            
            # 查找该用户创建的期刊
            user_journals = Journal.query.filter_by(created_by=user.id).all()
            print(f"创建的期刊数量: {len(user_journals)}")
            
            for journal in user_journals:
                print(f"  - 期刊: {journal.title} - {journal.issue}")
            
            print("-" * 30)

def test_editor_permissions():
    """测试editor用户的权限"""
    with app.app_context():
        print("\n=== 测试editor用户的权限 ===")
        
        user_datastore = SQLAlchemyUserDatastore(db, User, Journal)
        
        # 查找editor用户
        editor_users = []
        for user in User.query.all():
            if user.has_role('editor'):
                editor_users.append(user)
        
        if not editor_users:
            print("❌ 未找到editor用户")
            return
        
        for editor in editor_users:
            print(f"Editor用户: {editor.username} (ID: {editor.id})")
            
            # 查找该editor创建的期刊
            editor_journals = Journal.query.filter_by(created_by=editor.id).all()
            print(f"创建的期刊数量: {len(editor_journals)}")
            
            # 查找该editor可以访问的论文
            from services.permission_service import PermissionService
            accessible_papers = PermissionService.get_accessible_papers(editor)
            print(f"可访问的论文数量: {len(accessible_papers)}")
            
            for paper in accessible_papers:
                print(f"  - 论文: {paper.title} (期刊ID: {paper.journal_id})")
            
            print("-" * 30)

def fix_journal_created_by():
    """修复期刊的created_by字段"""
    with app.app_context():
        print("\n=== 修复期刊的created_by字段 ===")
        
        # 查找管理员用户
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print("❌ 未找到管理员用户")
            return
        
        # 查找没有设置created_by的期刊
        journals_without_creator = Journal.query.filter_by(created_by=None).all()
        
        if not journals_without_creator:
            print("✅ 所有期刊都已设置created_by字段")
            return
        
        print(f"找到 {len(journals_without_creator)} 个未设置created_by的期刊")
        
        for journal in journals_without_creator:
            print(f"修复期刊: {journal.title} - {journal.issue}")
            journal.created_by = admin_user.id
            db.session.add(journal)
        
        db.session.commit()
        print("✅ 期刊created_by字段修复完成")

if __name__ == '__main__':
    print("开始测试期刊权限和论文显示问题...")
    
    # 检查当前状态
    check_journal_created_by()
    check_user_journals()
    test_editor_permissions()
    
    # 修复问题
    fix_journal_created_by()
    
    # 再次检查修复后的状态
    print("\n=== 修复后的状态 ===")
    check_journal_created_by()
    test_editor_permissions()
