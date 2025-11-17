#!/usr/bin/env python3
"""
检查用户角色分配脚本
"""

from app import app, db, User, Role
from flask_security import SQLAlchemyUserDatastore

def check_user_roles():
    """检查用户角色分配"""
    with app.app_context():
        print("=== 检查用户角色分配 ===")
        
        # 检查管理员用户
        admin_user = User.query.filter_by(username='admin1').first()
        if admin_user:
            print(f'管理员用户: {admin_user.username}')
            print(f'用户角色: {[role.name for role in admin_user.roles]}')
            print(f'用户ID: {admin_user.id}')
            print(f'用户fs_uniquifier: {admin_user.fs_uniquifier}')
        else:
            print('❌ 未找到管理员用户')
            return False
        
        # 检查所有角色
        roles = Role.query.all()
        print(f'\n所有角色: {[role.name for role in roles]}')
        
        # 检查用户数据存储
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        admin_user2 = user_datastore.find_user(username='admin1')
        if admin_user2:
            print(f'\n通过user_datastore找到的用户: {admin_user2.username}')
            print(f'角色: {[role.name for role in admin_user2.roles]}')
            
            # 检查是否有admin角色
            has_admin_role = any(role.name == 'editor' for role in admin_user2.roles)
            if has_admin_role:
                print('✅ 管理员用户拥有editor角色')
                return True
            else:
                print('❌ 管理员用户没有editor角色')
                return False
        else:
            print('❌ 通过user_datastore未找到管理员用户')
            return False

def fix_admin_roles():
    """修复管理员角色分配"""
    with app.app_context():
        print("\n=== 修复管理员角色分配 ===")
        
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        
        # 确保角色存在
        admin_role = user_datastore.find_or_create_role(name='admin', description='管理员')
        editor_role = user_datastore.find_or_create_role(name='editor', description='编辑')
        viewer_role = user_datastore.find_or_create_role(name='viewer', description='查看者')
        
        # 获取管理员用户
        admin_user = user_datastore.find_user(username='admin')
        if not admin_user:
            print('❌ 未找到管理员用户，无法修复')
            return False
        
        # 清除现有角色并重新分配
        for role in admin_user.roles:
            user_datastore.remove_role_from_user(admin_user, role)
        
        # 分配admin角色
        user_datastore.add_role_to_user(admin_user, admin_role)
        
        # 提交更改
        db.session.commit()
        
        print('✅ 已为管理员用户分配admin角色')
        
        # 验证修复
        admin_user_updated = user_datastore.find_user(username='admin')
        print(f'修复后角色: {[role.name for role in admin_user_updated.roles]}')
        
        return True

def list_all_users():
    """列出数据库中所有用户的关键信息并返回列表"""
    with app.app_context():
        users = User.query.order_by(User.id).all()
        print("\n=== 数据库中所有用户 ===")
        user_list = []
        for u in users:
            roles = [r.name for r in getattr(u, 'roles', [])]
            info = {
                'id': getattr(u, 'id', None),
                'username': getattr(u, 'username', None),
                'email': getattr(u, 'email', None),
                'roles': roles,
                'active': getattr(u, 'active', None),
                'fs_uniquifier': getattr(u, 'fs_uniquifier', None),
                'created_at': getattr(u, 'created_at', None)
            }
            user_list.append(info)
            print(f"ID={info['id']}, username={info['username']}, email={info['email']}, roles={roles}, active={info['active']}, fs={info['fs_uniquifier']}")
        if not users:
            print("（数据库中没有用户记录）")
        return user_list

def print_users_if_requested():
    """辅助：在脚本运行时总是打印所有用户，便于检查"""
    try:
        list_all_users()
    except Exception as e:
        print(f"列出用户时出错: {e}")

if __name__ == '__main__':
    # print("开始检查用户角色...")
    
    # # 先检查当前状态
    # if not check_user_roles():
    #     print("\n需要修复角色分配...")
    #     # if fix_admin_roles():
    #     #     print("\n✅ 角色修复成功")
    #     # else:
    #     #     print("\n❌ 角色修复失败")
    # else:
    #     print("\n✅ 用户角色配置正确")

    # 额外：运行时总是打印数据库中所有用户，方便快速查看
    print_users_if_requested()
