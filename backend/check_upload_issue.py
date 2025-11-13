#!/usr/bin/env python3
"""
检查文件上传问题的根本原因
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Journal, Paper
from services.file_service import FileService
from services.permission_service import PermissionService

def check_upload_issue():
    """检查文件上传问题的根本原因"""
    print("=== 检查文件上传问题的根本原因 ===")
    
    with app.app_context():
        # 检查数据库状态
        print("1. 数据库状态检查:")
        
        admin_user = User.query.filter_by(username='admin').first()
        print(f"管理员用户: {admin_user.username}, ID: {admin_user.id}")
        print(f"角色: {[role.name for role in admin_user.roles]}")
        
        journals = Journal.query.all()
        print(f"当前期刊数量: {len(journals)}")
        for journal in journals:
            print(f"  期刊: {journal.title} (ID: {journal.id}), 创建者: {journal.created_by}")
            
            # 检查权限
            can_edit = PermissionService.can_edit_journal(admin_user, journal)
            print(f"  管理员是否有权限编辑: {can_edit}")
        
        papers = Paper.query.all()
        print(f"当前论文数量: {len(papers)}")
        
        print("\n2. 问题分析:")
        print("如果管理员用户有admin角色，应该能够通过API权限检查")
        print("如果自动创建的期刊的created_by字段正确设置为管理员用户ID，权限检查应该通过")
        print("如果仍然出现403权限不足，可能是:")
        print("  - 前端没有正确传递认证令牌")
        print("  - 前端传递的journalId值导致系统进入自动创建期刊逻辑")
        print("  - Flask-Security的认证机制有问题")
        
        print("\n3. 解决方案建议:")
        print("  - 检查前端上传时传递的journalId值")
        print("  - 检查前端是否正确传递了认证令牌")
        print("  - 检查浏览器开发者工具中的网络请求")
        print("  - 检查后端日志中的详细错误信息")
        
        print("\n4. 临时解决方案:")
        print("  如果前端传递journalId='1'导致自动创建期刊，可以:")
        print("  - 在前端创建一个真实的期刊，然后使用该期刊ID")
        print("  - 或者修改文件服务逻辑，避免自动创建期刊时的权限问题")
        
        print("\n=== 问题检查完成 ===")

if __name__ == '__main__':
    try:
        check_upload_issue()
    except Exception as e:
        print(f"检查过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
