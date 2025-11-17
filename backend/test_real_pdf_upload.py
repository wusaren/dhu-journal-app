#!/usr/bin/env python3
"""
使用真实PDF文件测试上传过程
验证管理员用户上传真实PDF文件时的完整流程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore, hash_password
from models import User, Role, Journal, Paper, db, user_datastore
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

class RealFile:
    """使用真实文件对象"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
    
    def save(self, path):
        import shutil
        shutil.copy2(self.filepath, path)

def test_real_pdf_upload():
    """使用真实PDF文件测试上传过程"""
    print("=== 使用真实PDF文件测试上传过程 ===")
    
    app = create_test_app()
    
    with app.app_context():
        # 创建测试数据库
        db.create_all()
        
        # 使用现有的管理员用户
        admin_user = user_datastore.find_user(username='admin')
        
        print("1. 测试用户:")
        print(f"管理员用户: {admin_user.username}, ID: {admin_user.id}")
        
        print("\n2. 检查真实PDF文件:")
        pdf_path = os.path.join('uploads', 'document.pdf')
        if os.path.exists(pdf_path):
            print(f"✅ 找到PDF文件: {pdf_path}")
            file_size = os.path.getsize(pdf_path)
            print(f"   文件大小: {file_size} bytes")
        else:
            print(f"❌ PDF文件不存在: {pdf_path}")
            return
        
        print("\n3. 测试真实PDF文件上传:")
        file_service = FileService()
        
        # 使用真实PDF文件
        real_file = RealFile(pdf_path)
        
        # 测试journal_id='1'的情况（触发自动创建期刊）
        journal_id = '1'
        print(f"journal_id: {journal_id}")
        
        try:
            # 调用文件上传服务
            result = file_service.upload_file(real_file, journal_id, admin_user)
            
            if result['success']:
                print(f"✅ 上传成功: {result['message']}")
                if 'data' in result:
                    data = result['data']
                    print(f"   期刊ID: {data.get('journalId')}")
                    print(f"   期刊创建: {data.get('journalCreated', False)}")
                    print(f"   论文数量: {data.get('papersCount', 0)}")
                    print(f"   解析状态: {data.get('parsing_status', 'N/A')}")
                    print(f"   解析进度: {data.get('parsing_progress', 'N/A')}")
                    print(f"   解析成功: {data.get('parsing_success', 'N/A')}")
            else:
                print(f"❌ 上传失败: {result['message']}")
                print(f"   状态码: {result.get('status_code', 'N/A')}")
                
        except Exception as e:
            print(f"❌ 上传异常: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print("\n4. 检查数据库状态:")
        journals = Journal.query.all()
        print(f"当前期刊数量: {len(journals)}")
        for journal in journals:
            print(f"  期刊: {journal.title} (ID: {journal.id}), 创建者: {journal.created_by}")
        
        papers = db.session.execute(db.select(Paper)).scalars().all()
        print(f"当前论文数量: {len(papers)}")
        for paper in papers:
            print(f"  论文: {paper.title} (ID: {paper.id}), 期刊ID: {paper.journal_id}")
        
        print("\n5. 权限检查:")
        if journals:
            latest_journal = journals[-1]
            from services.permission_service import PermissionService
            can_edit = PermissionService.can_edit_journal(admin_user, latest_journal)
            print(f"管理员是否有权限编辑最新期刊: {can_edit}")
        
        print("\n6. 问题分析:")
        print("如果真实PDF文件上传成功，说明系统工作正常")
        print("如果仍然出现权限不足，可能是前端传递的journalId值或其他问题")
        
        # 清理测试数据（可选）
        # journals = Journal.query.all()
        # for journal in journals:
        #     db.session.delete(journal)
        # db.session.commit()
        
        print("\n=== 真实PDF文件上传测试完成 ===")

if __name__ == '__main__':
    try:
        test_real_pdf_upload()
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
