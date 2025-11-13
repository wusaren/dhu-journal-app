#!/usr/bin/env python3
"""
测试认证修复脚本
用于验证前后端认证机制是否正常工作
"""

import requests
import json

# 后端API地址
BASE_URL = "http://localhost:5000"

def test_health_check():
    """测试健康检查接口"""
    print("=== 测试健康检查 ===")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

def test_login():
    """测试登录接口"""
    print("\n=== 测试登录 ===")
    try:
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        response = requests.post(
            f"{BASE_URL}/api/login",
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            # 检查响应中是否包含用户信息
            data = response.json()
            if 'user' in data and 'username' in data['user']:
                print("✅ 登录成功，用户信息正确")
                return True
            else:
                print("❌ 登录成功但用户信息不完整")
                return False
        else:
            print("❌ 登录失败")
            return False
    except Exception as e:
        print(f"登录测试失败: {e}")
        return False

def test_protected_endpoint():
    """测试受保护的接口（需要认证）"""
    print("\n=== 测试受保护接口 ===")
    try:
        # 先登录获取session
        session = requests.Session()
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        login_response = session.post(
            f"{BASE_URL}/api/login",
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if login_response.status_code != 200:
            print("❌ 登录失败，无法测试受保护接口")
            return False
        
        # 测试获取期刊列表（需要认证）
        response = session.get(f"{BASE_URL}/api/export/excel")
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 受保护接口访问成功")
            return True
        elif response.status_code == 401:
            print("❌ 认证失败，session未正确传递")
            return False
        else:
            print(f"❌ 其他错误: {response.json()}")
            return False
            
    except Exception as e:
        print(f"受保护接口测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试认证修复...")
    
    tests = [
        test_health_check,
        test_login,
        test_protected_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！认证修复成功")
    else:
        print("⚠️ 部分测试失败，需要进一步调试")

if __name__ == "__main__":
    main()
