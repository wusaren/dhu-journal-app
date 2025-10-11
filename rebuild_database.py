#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建数据库 - 使用新的设计
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app import app, db, init_db
from backend.models import User, Author, Journal, Paper, PaperAuthor, FileUpload

def rebuild_database():
    """重建数据库"""
    print("🔄 开始重建数据库...")
    
    with app.app_context():
        try:
            # 删除所有表
            print("🗑️  删除现有表...")
            db.drop_all()
            
            # 创建新表
            print("🏗️  创建新表...")
            db.create_all()
            
            # 创建默认管理员用户
            print("👤 创建默认管理员用户...")
            import bcrypt
            password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
            admin_user = User(
                username='admin',
                password_hash=password_hash.decode('utf-8'),
                email='admin@example.com',
                role='admin'
            )
            db.session.add(admin_user)
            db.session.flush()  # 先保存用户，获取ID
            
            # 创建测试期刊
            print("📚 创建测试期刊...")
            test_journal = Journal(
                title='东华学报',
                issue='测试期刊-2025',
                publish_date='2025-01-01',
                status='published',
                description='测试期刊',
                created_by=admin_user.id  # 使用实际的用户ID
            )
            db.session.add(test_journal)
            db.session.flush()
            
            # 创建测试作者
            print("创建测试作者...")
            author1 = Author(
                name='HUANG Jiacui',
                name_en='HUANG Jiacui',
                name_cn='黄佳翠',
                email='huangjc@dhu.edu.cn',
                affiliation='东华大学',
                is_dhu=True,
                is_corresponding=False
            )
            author2 = Author(
                name='ZHAO Mingbo',
                name_en='ZHAO Mingbo', 
                name_cn='赵明博',
                email='zhaomb@dhu.edu.cn',
                affiliation='东华大学',
                is_dhu=True,
                is_corresponding=True
            )
            db.session.add(author1)
            db.session.add(author2)
            db.session.flush()
            
            # 创建测试论文
            print("创建测试论文...")
            test_paper = Paper(
                journal_id=test_journal.id,
                title='测试论文标题',
                authors='HUANG Jiacui, ZHAO Mingbo',
                abstract='这是测试摘要',
                keywords='测试, 关键词',
                doi='10.19884/j.1672-5220.202405007',
                page_start=1,
                page_end=15,
                file_path='test.pdf',
                # 统计表字段
                manuscript_id='E202405007',
                pdf_pages=15,
                first_author='HUANG Jiacui',
                corresponding='ZHAO Mingbo',
                issue='测试期刊-2025',
                is_dhu=True
            )
            db.session.add(test_paper)
            db.session.flush()
            
            # 创建论文-作者关联
            print("创建论文-作者关联...")
            paper_author1 = PaperAuthor(
                paper_id=test_paper.id,
                author_id=author1.id,
                author_order=1,
                is_corresponding=False
            )
            paper_author2 = PaperAuthor(
                paper_id=test_paper.id,
                author_id=author2.id,
                author_order=2,
                is_corresponding=True
            )
            db.session.add(paper_author1)
            db.session.add(paper_author2)
            
            db.session.commit()
            
            print("数据库重建完成！")
            print(f"   管理员用户: admin / admin123")
            print(f"   测试期刊ID: {test_journal.id}")
            print(f"   测试论文ID: {test_paper.id}")
            print(f"   测试作者ID: {author1.id}, {author2.id}")
            print(f"   稿件号: {test_paper.manuscript_id}")
            print(f"   第一作者: {test_paper.first_author}")
            print(f"   通讯作者: {test_paper.corresponding}")
            print(f"   页数: {test_paper.pdf_pages}")
            print(f"   刊期: {test_paper.issue}")
            print(f"   是否东华: {test_paper.is_dhu}")
            
        except Exception as e:
            print(f"❌ 数据库重建失败: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    rebuild_database()
