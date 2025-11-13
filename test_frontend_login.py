import requests
import json

# 测试前端登录状态
BASE_URL = "http://localhost:5000"

def test_frontend_login():
    print("🧪 测试前端登录状态...")
    
    # 测试不同用户的登录状态
    test_users = [
        {"username": "managing_editor", "password": "managing_editor123", "role": "managing_editor"},
        {"username": "editor", "password": "editor123", "role": "editor"},
        {"username": "admin", "password": "admin123", "role": "admin"}
    ]
    
    for user in test_users:
        print(f"\n--- 测试用户: {user['username']} ({user['role']}) ---")
        
        session = requests.Session()
        
        try:
            # 1. 登录
            response = session.post(f"{BASE_URL}/api/login", json={
                "username": user["username"],
                "password": user["password"]
            })
            
            if response.status_code == 200:
                print(f"✅ 登录成功")
                user_info = response.json()
                print(f"   当前用户: {user_info['user']['username']} (角色: {user_info['user']['role']})")
                
                # 2. 测试获取编辑用户列表
                print("   测试获取编辑用户列表...")
                response = session.get(f"{BASE_URL}/api/admin/users/with-role/editor")
                
                if response.status_code == 200:
                    data = response.json()
                    editors = data.get('users', [])
                    print(f"   ✅ 成功获取编辑用户列表: {len(editors)} 个用户")
                    if editors:
                        for editor in editors:
                            print(f"      - {editor['username']} (ID: {editor['id']})")
                else:
                    print(f"   ❌ 获取编辑用户列表失败: {response.status_code} - {response.text}")
                    
            else:
                print(f"❌ 登录失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    print("\n🎉 前端登录状态测试完成！")
    print("\n📋 总结:")
    print("- 只有 managing_editor 角色才能查看编辑用户列表")
    print("- 请确保前端使用 managing_editor 用户登录")
    print("- 检查前端登录状态和用户角色")

if __name__ == "__main__":
    test_frontend_login()
