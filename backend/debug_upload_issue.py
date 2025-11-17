#!/usr/bin/env python3
"""
上传问题调试脚本
检查管理员用户上传文件时的具体问题
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore, hash_password
from models import User, Role, Journal, db, user_datastore
from services.file_service import FileService
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

def debug_upload_issue():
    """调试上传问题"""
    print("=== 调试上传问题 ===")
    
    app = create_test_app()
    
    with app.app_context():
        # 创建测试数据库
        db.create_all()
        
        # 创建测试角色
        admin_role = user_datastore.find_or_create_role(name='admin', description='管理员')
        
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
        
        # 创建测试期刊
        admin_journal = Journal(
            title='测试期刊',
            issue='2024-01',
            paper_count=0,
            status='draft',
            created_by=admin_user.id
        )
        db.session.add(admin_journal)
        
        db.session.commit()
        
        print("1. 测试用户和期刊:")
        print(f"管理员用户: {admin_user.username}, ID: {admin_user.id}")
        print(f"测试期刊: {admin_journal.title}, ID: {admin_journal.id}, 创建者: {admin_journal.created_by}")
        
        print("\n2. 测试文件上传权限检查:")
        file_service = FileService()
        
        # 测试不同journal_id值的情况
        test_cases = [
            ('1', "默认期刊ID '1'"),
            ('2', "不存在的期刊ID '2'"),
            (str(admin_journal.id), f"现有期刊ID '{admin_journal.id}'")
        ]
        
        for journal_id, description in test_cases:
            print(f"\n测试情况: {description}")
            print(f"journal_id: {journal_id}")
            
            # 模拟上传过程
            if journal_id and journal_id != '1':
                journal = Journal.query.get(int(journal_id))
                if journal:
                    print(f"找到期刊: {journal.title}, 创建者: {journal.created_by}")
                    from services.permission_service import PermissionService
                    can_edit = PermissionService.can_edit_journal(admin_user, journal)
                    print(f"管理员是否有权限编辑该期刊: {can_edit}")
                else:
                    print(f"期刊不存在: {journal_id}")
            else:
                print("进入自动创建期刊逻辑")
                # 检查默认期刊逻辑
                default_journal = Journal.query.filter_by(title='东华学报', status='draft').first()
                if default_journal:
                    print(f"找到默认期刊: {default_journal.title}, ID: {default_journal.id}, 创建者: {default_journal.created_by}")
                    from services.permission_service import PermissionService
                    can_edit = PermissionService.can_edit_journal(admin_user, default_journal)
                    print(f"管理员是否有权限编辑默认期刊: {can_edit}")
                else:
                    print("没有默认期刊，将创建新期刊")
                    print("新期刊的创建者将是当前用户")
        
        print("\n3. 问题分析:")
        print("如果前端上传时传递 journalId='1'，系统会进入自动创建期刊逻辑")
        print("如果PDF解析失败，会使用默认期刊或创建新期刊")
        print("问题可能在于默认期刊的创建者不是当前管理员用户")
        
        # 清理测试数据
        db.session.delete(admin_journal)
        db.session.delete(admin_user)
        db.session.commit()
        
        print("\n=== 上传问题调试完成 ===")

if __name__ == '__main__':
    try:
        debug_upload_issue()
    except Exception as e:
        print(f"调试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
