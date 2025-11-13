import requests
import json

# 测试API返回的数据结构
BASE_URL = "http://localhost:5000"

def test_api_response():
    print("🧪 测试API返回的数据结构...")
    
    # 1. 使用managing_editor登录
    print("1. 登录...")
    login_data = {
        "username": "managing_editor",
        "password": "managing_editor123"
    }
    
    session = requests.Session()
    
    try:
        response = session.post(f"{BASE_URL}/api/login", json=login_data)
        if response.status_code == 200:
            print("✅ 登录成功")
            user_info = response.json()
            print(f"   当前用户: {user_info['user']['username']} (角色: {user_info['user']['role']})")
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return False
    
    # 2. 获取编辑用户列表并检查数据结构
    print("2. 获取编辑用户列表并检查数据结构...")
    try:
        response = session.get(f"{BASE_URL}/api/admin/users/with-role/editor")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API调用成功，状态码: {response.status_code}")
            print(f"   返回数据完整结构: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # 检查数据结构
            if 'users' in data:
                editors = data['users']
                print(f"   ✅ 找到 'users' 字段，包含 {len(editors)} 个用户")
                
                if editors:
                    print("   用户列表详情:")
                    for i, editor in enumerate(editors):
                        print(f"     [{i+1}] ID: {editor.get('id')}, 用户名: {editor.get('username')}, 邮箱: {editor.get('email', '无')}")
                        
                        # 检查必需的字段
                        required_fields = ['id', 'username']
                        missing_fields = [field for field in required_fields if field not in editor]
                        if missing_fields:
                            print(f"     ⚠️ 用户缺少字段: {missing_fields}")
                else:
                    print("   ⚠️ 'users' 字段为空数组")
            else:
                print("   ❌ 返回数据中没有 'users' 字段")
                print(f"   实际字段: {list(data.keys())}")
        else:
            print(f"❌ API调用失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ API请求失败: {e}")
        return False
    
    print("🎉 API数据结构测试完成！")
    return True

if __name__ == "__main__":
    test_api_response()
