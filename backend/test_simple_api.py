#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单API测试
"""

import requests
import json

def test_api():
    print("🔧 测试API异常处理...")
    
    base_url = "http://localhost:5000/api"
    
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
    try:
        response1 = requests.post(f"{base_url}/journals/create", json=journal_data)
        print(f"第一次创建状态码: {response1.status_code}")
        print(f"第一次创建响应: {response1.json()}")
    except Exception as e:
        print(f"第一次创建失败: {e}")
    
    # 重复创建
    try:
        response2 = requests.post(f"{base_url}/journals/create", json=journal_data)
        print(f"重复创建状态码: {response2.status_code}")
        print(f"重复创建响应: {response2.json()}")
    except Exception as e:
        print(f"重复创建失败: {e}")
    
    print("\n✅ API测试完成")

if __name__ == '__main__':
    test_api()

