#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
直接测试服务层
"""

def test_service_direct():
    print("🔧 直接测试服务层...")
    
    from services.journal_service import JournalService
    journal_service = JournalService()
    
    # 测试创建重复期刊
    print("\n1. 测试创建重复期刊...")
    journal_data = {
        'title': '测试期刊',
        'issue': '第1期',
        'publish_date': '2024-01-01',
        'status': 'draft',
        'description': '测试期刊'
    }
    
    # 第一次创建
    result1 = journal_service.create_journal(journal_data)
    print(f"第一次创建: {result1}")
    
    # 重复创建
    result2 = journal_service.create_journal(journal_data)
    print(f"重复创建: {result2}")
    print(f"重复创建包含duplicate: {'duplicate' in result2}")
    if 'duplicate' in result2:
        print(f"duplicate值: {result2['duplicate']}")
    
    # 测试删除期刊
    print("\n2. 测试删除期刊...")
    if result1['success']:
        journal_id = result1['journal']['id']
        
        # 创建论文
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
            print(f"创建论文成功: {test_paper.id}")
            
            # 尝试删除期刊
            result3 = journal_service.delete_journal(journal_id)
            print(f"删除期刊: {result3}")
            print(f"删除期刊包含duplicate: {'duplicate' in result3}")
            if 'duplicate' in result3:
                print(f"duplicate值: {result3['duplicate']}")
            
            # 清理
            db.session.delete(test_paper)
            db.session.delete(Paper.query.get(journal_id))
            db.session.commit()
    
    print("\n✅ 服务层测试完成！")

if __name__ == '__main__':
    test_service_direct()

