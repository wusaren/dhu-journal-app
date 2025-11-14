#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理数据库 - 只删除数据库文件，程序启动时会自动重建
"""

import sys
import os
import shutil

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app import app, db

def clean_database():
    """清理数据库文件"""
    print("🔄 开始清理数据库...")
    
    try:
        # 1. 删除数据库文件
        print("🗑️  删除数据库文件...")
        db_path = os.path.join('backend', 'instance', 'journal.db')
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"   已删除: {db_path}")
        else:
            print(f"   数据库文件不存在: {db_path}")
        
        # 2. 重新创建数据库目录
        print("📁 重新创建数据库目录...")
        os.makedirs('backend/instance', exist_ok=True)
        
        # 3. 重新创建数据库表
        print("🏗️  创建数据库表...")
        with app.app_context():
            db.create_all()
            print("   数据库表创建完成")
        
        print("✅ 数据库清理完成！")
        print("   程序启动时会自动创建默认用户和角色")
        
    except Exception as e:
        print(f"❌ 数据库清理失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    clean_database()
