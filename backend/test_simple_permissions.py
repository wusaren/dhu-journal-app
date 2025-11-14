#!/usr/bin/env python3
"""
简化权限控制功能测试脚本
测试数据层权限控制是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore, hash_password
from models import User, Role, Journal, Paper, db, user_datastore
from services.permission_service import PermissionService
from backend.config.config import current_config

def create_test_app():
    """创建测试应用"""
    app = Flask(__name__)
    app.config.from_object(current_config)
    
    # Flask-Security 配置
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SECURITY_PASSWORD_SALT'] = 'test-password-salt'
    app.config['SECURITY_REGISTERABLE'] = False
    app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
    app.config['SECURITY_USERNAME_ENABLE'] = True
    app.config['SECURITY_USERNAME_REQUIRED'] = True
    app.config['SECURITY_PASSWORD_HASH'] = 'bcrypt'
    app.config['SECURITY_PASSWORD_SINGLE_HASH'] = False
    app.config['SECURITY_TOKEN_AUTHENTICATION_HEADER'] = 'Authorization'
    app.config['SECURITY_TOKEN_MAX_AGE'] = 3600
    app.config['SECURITY_JOIN_USER_ROLES'] = True
    
    db.init_app(app)
    
    # 初始化 Flask-Security
    Security(app, user_datastore)
    
    return app

def test_role_based_permissions():
    """测试基于角色的权限控制"""
    print("=== 测试基于角色的权限控制 ===")
    
    with app.app_context():
        # 创建测试数据库
        db.create_all()
        
        # 创建测试角色
        admin_role = user_datastore.find_or_create_role(name='admin', description='管理员')
        editor_role = user_datastore.find_or_create_role(name='editor', description='编辑')
        viewer_role = user_datastore.find_or_create_role(name='viewer', description='查看者')
        
        # 创建测试用户
        admin_user = user_datastore.create_user(
            username='test_admin',
            email='admin@test.com',
            password=hash_password('admin123'),
            fs_uniquifier='test_admin',
            active=True
        )
        user_datastore.add_role_to_user(admin_user, admin_role)
        
        editor_user = user_datastore.create_user(
            username='test_editor',
            email='editor@test.com',
            password=hash_password('editor123'),
            fs_uniquifier='test_editor',
            active=True
        )
        user_datastore.add_role_to_user(editor_user, editor_role)
        
        viewer_user = user_datastore.create_user(
            username='test_viewer',
            email='viewer@test.com',
            password=hash_password('viewer123'),
            fs_uniquifier='test_viewer',
            active=True
        )
        user_datastore.add_role_to_user(viewer_user, viewer_role)
        
        # 创建测试期刊
        journal = Journal(
            title='测试期刊',
            issue='2024-01',
            paper_count=0,
            status='published',
            created_by=editor_user.id  # 编辑创建的期刊
        )
        db.session.add(journal)
        db.session.commit()
        
        # 创建测试论文
        paper = Paper(
            journal_id=journal.id,
            title='测试论文',
            authors='测试作者',
            first_author='第一作者',
            page_start=1,
            manuscript_id='TEST001',
            pdf_pages=10,
            issue='2024-01'
        )
        db.session.add(paper)
        db.session.commit()
        
        # 测试角色检查
        print("\n1. 测试角色检查:")
        print(f"管理员角色: {admin_user.has_role('admin')}")
        print(f"编辑角色: {editor_user.has_role('editor')}")
        print(f"查看者角色: {viewer_user.has_role('viewer')}")
        
        # 测试期刊访问权限
        print("\n2. 测试期刊访问权限:")
        print(f"管理员可访问期刊: {PermissionService.can_view_journal(admin_user, journal)}")
        print(f"编辑可访问期刊: {PermissionService.can_view_journal(editor_user, journal)}")
        print(f"查看者可访问期刊: {PermissionService.can_view_journal(viewer_user, journal)}")
        
        # 测试期刊编辑权限
        print("\n3. 测试期刊编辑权限:")
        print(f"管理员可编辑期刊: {PermissionService.can_edit_journal(admin_user, journal)}")
        print(f"编辑可编辑期刊: {PermissionService.can_edit_journal(editor_user, journal)}")
        print(f"查看者可编辑期刊: {PermissionService.can_edit_journal(viewer_user, journal)}")
        
        # 测试论文访问权限
        print("\n4. 测试论文访问权限:")
        print(f"管理员可访问论文: {PermissionService.can_view_paper(admin_user, paper)}")
        print(f"编辑可访问论文: {PermissionService.can_view_paper(editor_user, paper)}")
        print(f"查看者可访问论文: {PermissionService.can_view_paper(viewer_user, paper)}")
        
        # 测试论文编辑权限
        print("\n5. 测试论文编辑权限:")
        print(f"管理员可编辑论文: {PermissionService.can_edit_paper(admin_user, paper)}")
        print(f"编辑可编辑论文: {PermissionService.can_edit_paper(editor_user, paper)}")
        print(f"查看者可编辑论文: {PermissionService.can_edit_paper(viewer_user, paper)}")
        
        # 测试可访问期刊
        print("\n6. 测试可访问期刊:")
        admin_journals = PermissionService.get_accessible_journals(admin_user)
        editor_journals = PermissionService.get_accessible_journals(editor_user)
        viewer_journals = PermissionService.get_accessible_journals(viewer_user)
        print(f"管理员可访问期刊数: {len(admin_journals)}")
        print(f"编辑可访问期刊数: {len(editor_journals)}")
        print(f"查看者可访问期刊数: {len(viewer_journals)}")
        
        # 测试可访问论文
        print("\n7. 测试可访问论文:")
        admin_papers = PermissionService.get_accessible_papers(admin_user)
        editor_papers = PermissionService.get_accessible_papers(editor_user)
        viewer_papers = PermissionService.get_accessible_papers(viewer_user)
        print(f"管理员可访问论文数: {len(admin_papers)}")
        print(f"编辑可访问论文数: {len(editor_papers)}")
        print(f"查看者可访问论文数: {len(viewer_papers)}")
        
        # 清理测试数据
        db.session.delete(paper)
        db.session.delete(journal)
        db.session.delete(admin_user)
        db.session.delete(editor_user)
        db.session.delete(viewer_user)
        db.session.commit()
        
        print("\n=== 权限控制测试完成 ===")

if __name__ == '__main__':
    app = create_test_app()
    
    try:
        test_role_based_permissions()
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
