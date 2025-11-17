#!/usr/bin/env python3
"""
管理员权限调试脚本
验证管理员用户的权限检查是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore, hash_password
from models import User, Role, Journal, db, user_datastore
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
    
    db.init_app(app)
    
    # 初始化 Flask-Security
    Security(app, user_datastore)
    
    return app

def debug_admin_permissions():
    """调试管理员权限"""
    print("=== 调试管理员权限 ===")
    
    app = create_test_app()
    
    with app.app_context():
        # 创建测试数据库
        db.create_all()
        
        # 创建测试角色
        admin_role = user_datastore.find_or_create_role(name='admin', description='管理员')
        editor_role = user_datastore.find_or_create_role(name='editor', description='编辑')
        
        # 创建测试管理员用户
        import secrets
        admin_user = user_datastore.create_user(
            username='debug_admin',
            email='debug_admin@example.com',
            password=hash_password('admin123'),
            fs_uniquifier=secrets.token_hex(16),
            active=True
        )
        user_datastore.add_role_to_user(admin_user, admin_role)
        
        # 创建测试编辑用户
        editor_user = user_datastore.create_user(
            username='debug_editor',
            email='debug_editor@example.com',
            password=hash_password('editor123'),
            fs_uniquifier=secrets.token_hex(16),
            active=True
        )
        user_datastore.add_role_to_user(editor_user, editor_role)
        
        # 创建测试期刊
        admin_journal = Journal(
            title='管理员期刊',
            issue='2024-01',
            paper_count=0,
            status='draft',
            created_by=admin_user.id
        )
        db.session.add(admin_journal)
        
        editor_journal = Journal(
            title='编辑期刊',
            issue='2024-02',
            paper_count=0,
            status='draft',
            created_by=editor_user.id
        )
        db.session.add(editor_journal)
        
        db.session.commit()
        
        print("1. 测试用户角色检查:")
        print(f"管理员用户: {admin_user.username}")
        print(f"管理员角色: {[role.name for role in admin_user.roles]}")
        print(f"has_role('admin'): {admin_user.has_role('admin')}")
        print(f"has_role('editor'): {admin_user.has_role('editor')}")
        
        print(f"\n编辑用户: {editor_user.username}")
        print(f"编辑角色: {[role.name for role in editor_user.roles]}")
        print(f"has_role('admin'): {editor_user.has_role('admin')}")
        print(f"has_role('editor'): {editor_user.has_role('editor')}")
        
        print("\n2. 测试权限服务:")
        print(f"管理员可编辑管理员期刊: {PermissionService.can_edit_journal(admin_user, admin_journal)}")
        print(f"管理员可编辑编辑期刊: {PermissionService.can_edit_journal(admin_user, editor_journal)}")
        print(f"编辑可编辑编辑期刊: {PermissionService.can_edit_journal(editor_user, editor_journal)}")
        print(f"编辑可编辑管理员期刊: {PermissionService.can_edit_journal(editor_user, admin_journal)}")
        
        print("\n3. 测试文件上传权限:")
        print(f"管理员上传到管理员期刊: {PermissionService.can_edit_journal(admin_user, admin_journal)}")
        print(f"管理员上传到编辑期刊: {PermissionService.can_edit_journal(admin_user, editor_journal)}")
        
        # 清理测试数据
        db.session.delete(admin_journal)
        db.session.delete(editor_journal)
        db.session.delete(admin_user)
        db.session.delete(editor_user)
        db.session.commit()
        
        print("\n=== 管理员权限调试完成 ===")

if __name__ == '__main__':
    try:
        debug_admin_permissions()
    except Exception as e:
        print(f"调试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
