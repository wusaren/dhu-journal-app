#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试异常处理功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Journal, Paper, User
import bcrypt

def test_exceptions():
    """测试异常处理"""
    print("开始测试异常处理...")
    
    try:
        with app.app_context():
            # 创建测试数据
            test_user = User.query.filter_by(username='admin').first()
        if not test_user:
            password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
            test_user = User(
                username='admin',
                password_hash=password_hash.decode('utf-8'),
                email='admin@example.com',
                role='admin'
            )
            db.session.add(test_user)
            db.session.commit()
        
        # 测试1: 创建重复期刊
        print("\n1. 测试创建重复期刊...")
        journal_data = {
            'title': '测试期刊',
            'issue': '第1期',
            'publish_date': '2024-01-01',
            'status': 'draft',
            'description': '测试期刊'
        }
        
        # 第一次创建
        journal1 = Journal(
            title=journal_data['title'],
            issue=journal_data['issue'],
            publish_date=journal_data['publish_date'],
            status=journal_data['status'],
            description=journal_data['description'],
            created_by=test_user.id
        )
        db.session.add(journal1)
        db.session.commit()
        print(f"✓ 第一次创建期刊成功: {journal1.id}")
        
        # 尝试创建重复期刊
        from services.journal_service import JournalService
        journal_service = JournalService()
        result = journal_service.create_journal(journal_data)
        
        if not result['success'] and '已存在' in result['message']:
            print(f"✓ 重复期刊检查正常: {result['message']}")
        else:
            print(f"✗ 重复期刊检查失败: {result}")
        
        # 测试2: 删除带有论文的期刊
        print("\n2. 测试删除带有论文的期刊...")
        
        # 创建一篇论文
        test_paper = Paper(
            journal_id=journal1.id,
            title='测试论文',
            authors='测试作者',
            first_author='测试作者',
            manuscript_id='TEST001',
            page_start=1,
            file_path='test.pdf'
        )
        db.session.add(test_paper)
        db.session.commit()
        print(f"✓ 创建测试论文成功: {test_paper.id}")
        
        # 尝试删除带有论文的期刊
        result = journal_service.delete_journal(journal1.id)
        
        if not result['success'] and '还有' in result['message'] and '篇论文' in result['message']:
            print(f"✓ 删除带论文期刊检查正常: {result['message']}")
        else:
            print(f"✗ 删除带论文期刊检查失败: {result}")
        
        # 清理测试数据
        db.session.delete(test_paper)
        db.session.delete(journal1)
        db.session.commit()
        print("\n✓ 测试数据清理完成")
        
        print("\n🎉 异常处理测试完成！")
    except Exception as e:
        print(f"测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_exceptions()
