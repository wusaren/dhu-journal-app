#!/usr/bin/env python3
"""
测试导出接口修复脚本
专门测试 /api/export/excel 和 /api/export/tuiwen 接口
"""

import requests
import json

# 后端API地址
BASE_URL = "http://localhost:5000"

def test_export_excel():
    """测试统计表导出接口"""
    print("=== 测试统计表导出接口 ===")
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
            print("❌ 登录失败，无法测试导出接口")
            return False
        
        print("✅ 登录成功")
        
        # 获取期刊列表，选择一个期刊进行测试
        journals_response = session.get(f"{BASE_URL}/api/journals")
        if journals_response.status_code == 200:
            journals = journals_response.json()
            if journals and len(journals) > 0:
                journal_id = journals[0]['id']
                print(f"✅ 找到期刊，ID: {journal_id}")
                
                # 测试导出统计表
                export_data = {
                    "journalId": journal_id
                }
                export_response = session.post(
                    f"{BASE_URL}/api/export/excel",
                    json=export_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                print(f"导出接口状态码: {export_response.status_code}")
                if export_response.status_code == 200:
                    result = export_response.json()
                    print(f"✅ 统计表导出成功: {result}")
                    return True
                else:
                    print(f"❌ 统计表导出失败: {export_response.text}")
                    return False
            else:
                print("❌ 没有找到期刊，请先创建期刊")
                return False
        else:
            print(f"❌ 获取期刊列表失败: {journals_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 统计表导出测试失败: {e}")
        return False

def test_export_tuiwen():
    """测试推文导出接口"""
    print("\n=== 测试推文导出接口 ===")
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
            print("❌ 登录失败，无法测试导出接口")
            return False
        
        print("✅ 登录成功")
        
        # 获取期刊列表，选择一个期刊进行测试
        journals_response = session.get(f"{BASE_URL}/api/journals")
        if journals_response.status_code == 200:
            journals = journals_response.json()
            if journals and len(journals) > 0:
                journal_id = journals[0]['id']
                print(f"✅ 找到期刊，ID: {journal_id}")
                
                # 测试导出推文
                export_data = {
                    "journalId": journal_id
                }
                export_response = session.post(
                    f"{BASE_URL}/api/export/tuiwen",
                    json=export_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                print(f"导出接口状态码: {export_response.status_code}")
                if export_response.status_code == 200:
                    result = export_response.json()
                    print(f"✅ 推文导出成功: {result}")
                    return True
                else:
                    print(f"❌ 推文导出失败: {export_response.text}")
                    return False
            else:
                print("❌ 没有找到期刊，请先创建期刊")
                return False
        else:
            print(f"❌ 获取期刊列表失败: {journals_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 推文导出测试失败: {e}")
        return False

def test_export_without_auth():
    """测试未认证时访问导出接口"""
    print("\n=== 测试未认证访问导出接口 ===")
    try:
        session = requests.Session()
        
        # 直接访问导出接口，不登录
        export_data = {
            "journalId": 1
        }
        export_response = session.post(
            f"{BASE_URL}/api/export/excel",
            json=export_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"未认证访问状态码: {export_response.status_code}")
        if export_response.status_code == 401:
            print("✅ 未认证访问正确返回401")
            return True
        else:
            print(f"❌ 未认证访问返回了意外的状态码: {export_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 未认证访问测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试导出接口修复...")
    
    tests = [
        test_export_excel,
        test_export_tuiwen,
        test_export_without_auth
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== 导出接口测试结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有导出接口测试通过！")
    else:
        print("⚠️ 部分导出接口测试失败")
        print("\n可能的问题：")
        print("1. 确保数据库中有期刊和论文数据")
        print("2. 检查导出服务是否有依赖问题")
        print("3. 查看后端日志获取详细错误信息")

if __name__ == "__main__":
    main()
