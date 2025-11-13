#!/usr/bin/env python3
"""
测试用户级别模板配置功能
"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from app import app, db
from models import User, Journal, Paper
from services.template_config_service import TemplateConfigService
from services.tuiwen_template_service import TuiwenTemplateService
from services.export_service import ExportService

def test_user_template_config():
    """测试用户模板配置功能"""
    print("=== 测试用户级别模板配置功能 ===")
    
    with app.app_context():
        # 创建测试用户
        test_user = User.query.filter_by(username='admin').first()
        if not test_user:
            print("❌ 测试用户不存在，请先创建admin用户")
            return
        
        print(f"✅ 使用测试用户: {test_user.username} (ID: {test_user.id})")
        
        # 创建测试期刊
        test_journal = Journal.query.filter_by(title='测试期刊').first()
        if not test_journal:
            test_journal = Journal(
                title='测试期刊',
                issue='2025-01',
                created_by=test_user.id
            )
            db.session.add(test_journal)
            db.session.commit()
            print(f"✅ 创建测试期刊: {test_journal.title} (ID: {test_journal.id})")
        else:
            print(f"✅ 使用现有测试期刊: {test_journal.title} (ID: {test_journal.id})")
        
        # 测试统计表模板配置
        print("\n--- 测试统计表模板配置 ---")
        template_config_service = TemplateConfigService()
        
        # 创建用户模板配置
        user_template_config = {
            'template_file_path': 'test_template.xlsx',
            'column_mapping': [
                {'system_field': 'manuscript_id', 'template_header': '稿件号', 'order': 1},
                {'system_field': 'title', 'template_header': '标题', 'order': 2},
                {'system_field': 'authors', 'template_header': '作者', 'order': 3}
            ]
        }
        
        # 保存用户模板配置
        result = template_config_service.save_user_template(
            test_user.id,
            user_template_config['template_file_path'],
            user_template_config['column_mapping']
        )
        
        if result['success']:
            print("✅ 用户统计表模板配置保存成功")
        else:
            print(f"❌ 用户统计表模板配置保存失败: {result['message']}")
        
        # 加载用户模板配置
        loaded_config = template_config_service.load_user_config(test_user.id)
        if loaded_config:
            print("✅ 用户统计表模板配置加载成功")
            print(f"   模板文件: {loaded_config.get('template_file_path')}")
            print(f"   列映射数量: {len(loaded_config.get('column_mapping', []))}")
        else:
            print("❌ 用户统计表模板配置加载失败")
        
        # 测试推文模板配置
        print("\n--- 测试推文模板配置 ---")
        tuiwen_template_service = TuiwenTemplateService()
        
        # 创建用户推文模板配置
        user_tuiwen_config = {
            'fields': [
                {'field': 'title', 'label': '标题', 'required': True},
                {'field': 'authors', 'label': '作者', 'required': True},
                {'field': 'abstract', 'label': '摘要', 'required': False}
            ]
        }
        
        # 保存用户推文模板配置
        result = tuiwen_template_service.save_user_template_config(
            test_user.id,
            user_tuiwen_config['fields']
        )
        
        if result['success']:
            print("✅ 用户推文模板配置保存成功")
        else:
            print(f"❌ 用户推文模板配置保存失败: {result['message']}")
        
        # 加载用户推文模板配置
        loaded_tuiwen_config = tuiwen_template_service.load_user_config(test_user.id)
        if loaded_tuiwen_config:
            print("✅ 用户推文模板配置加载成功")
            print(f"   字段数量: {len(loaded_tuiwen_config.get('fields', []))}")
        else:
            print("❌ 用户推文模板配置加载失败")
        
        # 测试导出服务
        print("\n--- 测试导出服务 ---")
        export_service = ExportService()
        
        # 测试统计表导出（使用用户模板）
        print("测试统计表导出（使用用户模板）...")
        result = export_service.export_excel(test_journal.id, user_id=test_user.id)
        if result['success']:
            print("✅ 统计表导出成功（使用用户模板）")
            print(f"   下载链接: {result.get('downloadUrl')}")
        else:
            print(f"❌ 统计表导出失败: {result['message']}")
        
        # 测试推文导出（使用用户模板）
        print("测试推文导出（使用用户模板）...")
        result = export_service.export_tuiwen(test_journal.id, user_id=test_user.id)
        if result['success']:
            print("✅ 推文导出成功（使用用户模板）")
            print(f"   下载链接: {result.get('downloadUrl')}")
        else:
            print(f"❌ 推文导出失败: {result['message']}")
        
        print("\n=== 测试完成 ===")

if __name__ == '__main__':
    test_user_template_config()
