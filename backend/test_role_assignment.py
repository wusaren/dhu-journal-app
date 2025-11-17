#!/usr/bin/env python3
"""
测试角色分配是否真正生效
"""

from app import app, db, User, Role
from flask_security import SQLAlchemyUserDatastore

def test_role_assignment():
    """测试角色分配功能"""
    with app.app_context():
        print("=== 测试角色分配功能 ===")
        
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        
        # 获取一个测试用户（假设用户ID为4）
        test_user_id = 4
        user = user_datastore.find_user(id=test_user_id)
        
        if not user:
            print(f"❌ 未找到用户ID: {test_user_id}")
            return False
        
        print(f"测试用户: {user.username} (ID: {user.id})")
        print(f"当前角色: {[role.name for role in user.roles]}")
        
        # 测试分配editor角色
        role_name = "editor"
        role = user_datastore.find_role(role_name)
        
        if not role:
            print(f"❌ 未找到角色: {role_name}")
            return False
        
        print(f"\n=== 分配角色 {role_name} ===")
        
        # 检查是否已拥有该角色
        if user.has_role(role_name):
            print(f"用户已拥有角色 {role_name}")
        else:
            print(f"用户未拥有角色 {role_name}")
        
        # 分配角色
        user_datastore.add_role_to_user(user, role)
        db.session.commit()
        
        print("✅ 角色分配完成")
        
        # 重新查询用户以验证修改
        user_updated = user_datastore.find_user(id=test_user_id)
        print(f"分配后角色: {[role.name for role in user_updated.roles]}")
        
        # 验证角色是否真正分配
        if user_updated.has_role(role_name):
            print(f"✅ 角色 {role_name} 已成功分配给用户")
            return True
        else:
            print(f"❌ 角色 {role_name} 未成功分配给用户")
            return False

def test_role_removal():
    """测试角色移除功能"""
    with app.app_context():
        print("\n=== 测试角色移除功能 ===")
        
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        
        # 获取测试用户
        test_user_id = 4
        user = user_datastore.find_user(id=test_user_id)
        
        if not user:
            print(f"❌ 未找到用户ID: {test_user_id}")
            return False
        
        print(f"测试用户: {user.username} (ID: {user.id})")
        print(f"当前角色: {[role.name for role in user.roles]}")
        
        # 测试移除editor角色
        role_name = "editor"
        role = user_datastore.find_role(role_name)
        
        if not role:
            print(f"❌ 未找到角色: {role_name}")
            return False
        
        print(f"\n=== 移除角色 {role_name} ===")
        
        # 检查是否拥有该角色
        if user.has_role(role_name):
            print(f"用户拥有角色 {role_name}，可以移除")
        else:
            print(f"用户未拥有角色 {role_name}，无需移除")
            return True
        
        # 移除角色
        user_datastore.remove_role_from_user(user, role)
        db.session.commit()
        
        print("✅ 角色移除完成")
        
        # 重新查询用户以验证修改
        user_updated = user_datastore.find_user(id=test_user_id)
        print(f"移除后角色: {[role.name for role in user_updated.roles]}")
        
        # 验证角色是否真正移除
        if not user_updated.has_role(role_name):
            print(f"✅ 角色 {role_name} 已成功从用户移除")
            return True
        else:
            print(f"❌ 角色 {role_name} 未成功从用户移除")
            return False

def check_all_users():
    """检查所有用户的角色"""
    with app.app_context():
        print("\n=== 检查所有用户角色 ===")
        
        users = User.query.all()
        
        for user in users:
            print(f"用户: {user.username} (ID: {user.id})")
            print(f"角色: {[role.name for role in user.roles]}")
            print("-" * 30)

if __name__ == '__main__':
    print("开始测试角色分配功能...")
    
    # 先检查当前状态
    check_all_users()
    
    # 测试角色分配
    if test_role_assignment():
        print("\n✅ 角色分配测试通过")
    else:
        print("\n❌ 角色分配测试失败")
    
    # 测试角色移除
    if test_role_removal():
        print("\n✅ 角色移除测试通过")
    else:
        print("\n❌ 角色移除测试失败")
    
    # 再次检查最终状态
    check_all_users()
