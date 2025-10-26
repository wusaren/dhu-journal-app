#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试异常处理修复
"""

def test_exception_handling():
    print("🔧 测试异常处理修复...")
    
    # 测试1: 创建重复期刊
    print("\n1. 测试创建重复期刊...")
    from services.journal_service import JournalService
    journal_service = JournalService()
    
    # 先创建一个期刊
    journal_data = {
        'title': '测试期刊',
        'issue': '第1期',
        'publish_date': '2024-01-01',
        'status': 'draft',
        'description': '测试期刊'
    }
    
    result1 = journal_service.create_journal(journal_data)
    print(f"第一次创建: {result1['success']} - {result1['message']}")
    
    # 尝试创建重复期刊
    result2 = journal_service.create_journal(journal_data)
    print(f"重复创建: {result2['success']} - {result2['message']}")
    
    if not result2['success'] and '已存在' in result2['message']:
        print("✅ 重复期刊检查正常")
    else:
        print("❌ 重复期刊检查异常")
    
    # 测试2: 删除带有论文的期刊
    print("\n2. 测试删除带有论文的期刊...")
    
    # 获取刚创建的期刊ID
    if result1['success']:
        journal_id = result1['journal']['id']
        
        # 创建一篇论文
        from models import Paper, db
        from app import app
        
        with app.app_context():
            test_paper = Paper(
                journal_id=journal_id,
                title='测试论文',
                authors='测试作者',
                first_author='测试作者',
                manuscript_id='TEST001',
                page_start=1,
                pdf_pages=5,
                issue='第1期'
            )
            db.session.add(test_paper)
            db.session.commit()
            print(f"✅ 创建测试论文成功: {test_paper.id}")
            
            # 尝试删除带有论文的期刊
            result3 = journal_service.delete_journal(journal_id)
            print(f"删除期刊结果: {result3['success']} - {result3['message']}")
            
            if not result3['success'] and '还有' in result3['message'] and '篇论文' in result3['message']:
                print("✅ 删除带论文期刊检查正常")
            else:
                print("❌ 删除带论文期刊检查异常")
            
            # 清理测试数据
            db.session.delete(test_paper)
            db.session.delete(Paper.query.get(journal_id))
            db.session.commit()
            print("✅ 测试数据清理完成")
    
    print("\n🎉 异常处理测试完成！")

if __name__ == '__main__':
    test_exception_handling()

