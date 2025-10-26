#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单测试异常处理
"""

from app import app
from models import db, Journal, Paper, User
import bcrypt

def test_simple():
    print("开始简单测试...")
    
    with app.app_context():
        # 测试创建重复期刊
        print("\n1. 测试创建重复期刊...")
        
        # 先创建一个期刊
        journal1 = Journal(
            title='测试期刊',
            issue='第1期',
            publish_date='2024-01-01',
            status='draft',
            description='测试期刊',
            created_by=1
        )
        db.session.add(journal1)
        db.session.commit()
        print(f"✓ 创建期刊成功: {journal1.id}")
        
        # 尝试创建重复期刊
        from services.journal_service import JournalService
        journal_service = JournalService()
        
        duplicate_data = {
            'title': '测试期刊',
            'issue': '第1期',
            'publish_date': '2024-01-01',
            'status': 'draft',
            'description': '测试期刊'
        }
        
        result = journal_service.create_journal(duplicate_data)
        print(f"重复期刊测试结果: {result}")
        
        if not result['success'] and '已存在' in result['message']:
            print("✓ 重复期刊检查正常")
        else:
            print("✗ 重复期刊检查异常")
        
        # 清理
        db.session.delete(journal1)
        db.session.commit()
        print("✓ 测试完成")

if __name__ == '__main__':
    test_simple()

