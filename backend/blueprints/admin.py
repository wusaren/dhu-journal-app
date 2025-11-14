from flask import Blueprint, request, jsonify
from flask_security import auth_required, roles_required, current_user
from models import User, Role, db, user_datastore

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/users', methods=['GET'])
@auth_required()
@roles_required('admin')
def get_all_users():
    """获取所有用户列表（带角色信息）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    users = User.query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    user_list = []
    for user in users.items:
        user_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'active': user.active,
            'roles': [role.name for role in user.roles],
            'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None
        })
    
    return jsonify({
        'users': user_list,
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    })

@admin_bp.route('/users/<int:user_id>/roles', methods=['GET'])
@auth_required()
@roles_required('admin')
def get_user_roles(user_id):
    """获取用户的角色列表"""
    user = user_datastore.find_user(id=user_id)
    if not user:
        return jsonify({'message': '用户不存在'}), 404
    
    roles = [{'name': role.name, 'description': role.description} 
             for role in user.roles]
    
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'roles': roles
    })

@admin_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@auth_required()
@roles_required('admin')
def assign_role_to_user(user_id):
    """为用户分配角色"""
    data = request.get_json()
    role_name = data.get('role_name')
    
    user = user_datastore.find_user(id=user_id)
    role = user_datastore.find_role(role_name)
    
    if not user or not role:
        return jsonify({'message': '用户或角色不存在'}), 404
    
    # 检查是否已拥有该角色
    if user.has_role(role_name):
        return jsonify({'message': '用户已拥有该角色'}), 400
    
    # 分配角色
    user_datastore.add_role_to_user(user, role)
    db.session.commit()
    
    # 重新查询用户以确保获取最新数据
    user_updated = user_datastore.find_user(id=user_id)
    
    return jsonify({
        'message': f'成功为用户 {user_updated.username} 分配角色 {role_name}',
        'user': {
            'id': user_updated.id,
            'username': user_updated.username,
            'email': user_updated.email,
            'roles': [role.name for role in user_updated.roles]
        }
    })

@admin_bp.route('/users/<int:user_id>/roles', methods=['DELETE'])
@auth_required()
@roles_required('admin')
def remove_role_from_user(user_id):
    """移除用户的角色"""
    data = request.get_json()
    role_name = data.get('role_name')
    
    user = user_datastore.find_user(id=user_id)
    role = user_datastore.find_role(role_name)
    
    if not user or not role:
        return jsonify({'message': '用户或角色不存在'}), 404
    
    # 移除角色
    user_datastore.remove_role_from_user(user, role)
    db.session.commit()
    
    # 重新查询用户以确保获取最新数据
    user_updated = user_datastore.find_user(id=user_id)
    
    return jsonify({
        'message': f'成功移除用户 {user_updated.username} 的角色 {role_name}',
        'user': {
            'id': user_updated.id,
            'username': user_updated.username,
            'email': user_updated.email,
            'roles': [role.name for role in user_updated.roles]
        }
    })

@admin_bp.route('/users/<int:user_id>/roles/batch', methods=['PUT'])
@auth_required()
@roles_required('admin')
def update_user_roles(user_id):
    """批量更新用户角色"""
    data = request.get_json()
    role_names = data.get('roles', [])
    
    user = user_datastore.find_user(id=user_id)
    if not user:
        return jsonify({'message': '用户不存在'}), 404
    
    # 获取所有有效角色
    valid_roles = []
    for role_name in role_names:
        role = user_datastore.find_role(role_name)
        if role:
            valid_roles.append(role)
        else:
            return jsonify({'message': f'角色 {role_name} 不存在'}), 400
    
    # 设置用户角色（替换现有角色）
    user_datastore.set_roles(user, valid_roles)
    db.session.commit()
    
    # 重新查询用户以确保获取最新数据
    user_updated = user_datastore.find_user(id=user_id)
    
    return jsonify({
        'message': f'成功更新用户 {user_updated.username} 的角色',
        'user': {
            'id': user_updated.id,
            'username': user_updated.username,
            'email': user_updated.email,
            'roles': [role.name for role in user_updated.roles]
        }
    })

@admin_bp.route('/users/with-role/<role_name>', methods=['GET'])
@auth_required()
# @roles_required('admin', 'managing_editor')
def get_users_by_role(role_name):
    """返回具有指定角色的用户列表（简化字段）"""
    try:
        if not current_user.has_role('managing_editor'):
            return jsonify({'message': '权限不足，只有管理员才能查看特定角色的用户'}), 403
        role = user_datastore.find_role(role_name)
        if not role:
            return jsonify({'users': []})
        # role.users 可能是 dynamic query 或 list
        try:
            role_users = role.users.all()
        except Exception:
            role_users = role.users or []
        users = []
        for u in role_users:
            users.append({
                'id': u.id,
                'username': getattr(u, 'username', None),
                'email': getattr(u, 'email', None),
                'active': getattr(u, 'active', None)
            })
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'message': f'查询失败: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>/activate', methods=['PUT'])
@auth_required()
@roles_required('admin')
def toggle_user_active(user_id):
    """启用/禁用用户"""
    user = user_datastore.find_user(id=user_id)
    if not user:
        return jsonify({'message': '用户不存在'}), 404
    
    user.active = not user.active
    db.session.commit()
    
    status = "启用" if user.active else "禁用"
    return jsonify({
        'message': f'成功{status}用户 {user.username}',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'active': user.active,
            'roles': [role.name for role in user.roles]
        }
    })

@admin_bp.route('/roles', methods=['GET'])
@auth_required()
@roles_required('admin')
def get_all_roles():
    """获取所有角色"""
    roles = Role.query.all()
    
    role_list = []
    for role in roles:
        role_list.append({
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'user_count': role.users.count()
        })
    
    return jsonify({'roles': role_list})

@admin_bp.route('/roles', methods=['POST'])
@auth_required()
@roles_required('admin')
def create_role():
    """创建新角色"""
    data = request.get_json()
    role_name = data.get('name')
    description = data.get('description', '')
    
    if not role_name:
        return jsonify({'message': '角色名不能为空'}), 400
    
    # 检查角色是否已存在
    if user_datastore.find_role(role_name):
        return jsonify({'message': '角色已存在'}), 400
    
    # 创建角色
    role = user_datastore.create_role(name=role_name, description=description)
    db.session.commit()
    
    return jsonify({
        'message': '角色创建成功',
        'role': {
            'id': role.id,
            'name': role.name,
            'description': role.description
        }
    }), 201

@admin_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@auth_required()
@roles_required('admin')
def delete_role(role_id):
    """删除角色"""
    role = Role.query.get(role_id)
    if not role:
        return jsonify({'message': '角色不存在'}), 404
    
    # 检查是否有用户使用该角色
    if role.users.count() > 0:
        return jsonify({
            'message': '无法删除该角色，仍有用户在使用',
            'user_count': role.users.count()
        }), 400
    
    db.session.delete(role)
    db.session.commit()
    
    return jsonify({'message': '角色删除成功'})



@admin_bp.route('/stats', methods=['GET'])
@auth_required()
@roles_required('admin')
def get_admin_stats():
    """获取管理面板统计信息"""
    total_users = User.query.count()
    active_users = User.query.filter_by(active=True).count()
    total_roles = Role.query.count()
    
    # 按角色统计用户数量
    role_stats = []
    roles = Role.query.all()
    for role in roles:
        role_stats.append({
            'name': role.name,
            'description': role.description,
            'user_count': role.users.count()
        })
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'total_roles': total_roles,
        'role_stats': role_stats
    })
