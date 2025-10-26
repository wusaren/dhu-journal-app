#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试API响应
"""

import requests
import json

def test_api_response():
    print("🔧 测试API响应...")
    
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
        
        # 检查是否包含duplicate字段
        if response2.status_code == 400:
            response_data = response2.json()
            print(f"重复创建包含duplicate字段: {'duplicate' in response_data}")
            if 'duplicate' in response_data:
                print(f"duplicate值: {response_data['duplicate']}")
        
    except Exception as e:
        print(f"重复创建失败: {e}")
    
    print("\n✅ API响应测试完成！")

if __name__ == '__main__':
    test_api_response()

