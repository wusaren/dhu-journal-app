import requests
import json

# 最终测试修复
BASE_URL = "http://localhost:5000"

def test_final_fix():
    print("🧪 最终测试修复...")
    
    # 使用managing_editor登录
    session = requests.Session()
    
    try:
        # 1. 登录
        response = session.post(f"{BASE_URL}/api/login", json={
            "username": "managing_editor",
            "password": "managing_editor123"
        })
        
        if response.status_code == 200:
            print("✅ 登录成功")
            
            # 2. 获取编辑用户列表
            response = session.get(f"{BASE_URL}/api/admin/users/with-role/editor")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API调用成功，状态码: {response.status_code}")
                print(f"   返回数据结构: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 分析数据结构
                if isinstance(data, dict) and 'users' in data:
                    print("   📊 数据结构: { users: [...] }")
                    editors = data['users']
                elif isinstance(data, list):
                    print("   📊 数据结构: [...] (直接数组)")
                    editors = data
                else:
                    print(f"   ⚠️ 未知数据结构: {type(data)}")
                    editors = []
                
                print(f"   👥 解析出的用户数量: {len(editors)}")
                if editors:
                    for editor in editors:
                        print(f"      - {editor.get('username')} (ID: {editor.get('id')})")
                else:
                    print("   ⚠️ 没有解析出用户")
                    
            else:
                print(f"❌ API调用失败: {response.status_code} - {response.text}")
                
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    print("\n🎯 前端修复说明:")
    print("1. 修复了axios响应拦截器导致的数据结构问题")
    print("2. journalService现在支持多种数据结构:")
    print("   - 直接返回用户数组")
    print("   - 返回 { users: [...] }")
    print("   - 返回 { data: [...] }")
    print("3. 添加了调试日志，请查看浏览器控制台")

if __name__ == "__main__":
    test_final_fix()
