import requests
import json

# 测试分配任务功能
BASE_URL = "http://localhost:5000"

def test_assignment_functionality():
    print("🧪 测试分配任务功能...")
    
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
    
    # 2. 获取编辑用户列表
    print("2. 获取编辑用户列表...")
    try:
        response = session.get(f"{BASE_URL}/api/admin/users/with-role/editor")
        if response.status_code == 200:
            data = response.json()
            editors = data.get('users', [])
            print(f"✅ 获取编辑用户成功: 找到 {len(editors)} 个编辑")
            for editor in editors:
                print(f"   - {editor['username']} (ID: {editor['id']})")
        else:
            print(f"❌ 获取编辑用户失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 获取编辑用户请求失败: {e}")
        return False
    
    # 3. 获取期刊列表
    print("3. 获取期刊列表...")
    try:
        response = session.get(f"{BASE_URL}/api/journals")
        if response.status_code == 200:
            journals = response.json()
            print(f"✅ 获取期刊列表成功: 找到 {len(journals)} 个期刊")
            if journals:
                journal = journals[0]
                print(f"   第一个期刊: {journal['title']} - {journal['issue']} (ID: {journal['id']})")
                
                # 4. 测试分配任务
                print("4. 测试分配任务...")
                if editors:
                    assignee_id = editors[0]['id']
                    assign_data = {
                        "assignee_id": assignee_id
                    }
                    
                    response = session.post(f"{BASE_URL}/api/journals/{journal['id']}/assign", json=assign_data)
                    if response.status_code == 200:
                        print(f"✅ 分配任务成功: 期刊 {journal['id']} 已分配给用户 {assignee_id}")
                        print(f"   响应: {response.json()}")
                    else:
                        print(f"❌ 分配任务失败: {response.status_code} - {response.text}")
                        return False
                else:
                    print("⚠️ 没有可用的编辑用户，跳过分配测试")
            else:
                print("⚠️ 没有可用的期刊，跳过分配测试")
        else:
            print(f"❌ 获取期刊列表失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 获取期刊列表请求失败: {e}")
        return False
    
    print("🎉 分配任务功能测试完成！")
    return True

if __name__ == "__main__":
    test_assignment_functionality()
