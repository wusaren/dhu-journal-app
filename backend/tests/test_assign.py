import sys
import os

# 确保测试运行时能找到后端模块（把 backend 根目录加入 sys.path）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# 保证在导入 app 之前有必要的环境变量，避免 app 在导入时因缺少 SECRET_KEY 等崩溃
os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ.setdefault('SECURITY_PASSWORD_SALT', 'test-salt')

import pytest
from app import app
from models import db, User, Role, Journal, user_datastore
from flask_security import hash_password
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # 使用内存 sqlite 以避免污染开发数据库
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()

        # 创建角色（若已存在则复用，避免 UNIQUE 约束错误）
        editor_role = user_datastore.find_role('editor') or user_datastore.create_role(name='editor', description='编辑')
        me_role = user_datastore.find_role('managing editor') or user_datastore.create_role(name='managing editor', description='总编')

        # 创建分配者（具有 managing editor 角色）
        assigner = user_datastore.create_user(
            username='manager',
            email='manager@example.com',
            password=hash_password('pass1'),
            fs_uniquifier='u_manager'
        )
        user_datastore.add_role_to_user(assigner, me_role)

        # 创建被分配者（具有 editor 角色）
        assignee = user_datastore.create_user(
            username='editor1',
            email='editor1@example.com',
            password=hash_password('pass2'),
            fs_uniquifier='u_editor1'
        )
        user_datastore.add_role_to_user(assignee, editor_role)

        # 创建一个期刊，initial created_by 为 assigner
        journal = Journal(title='Test Journal', issue='Vol1', created_by=assigner.id)
        db.session.add(journal)
        db.session.commit()

    with app.test_client() as client:
        yield client

def test_assign_journal_updates_created_by(client):
    # 登录为 managing editor
    resp = client.post('/api/login', json={'username': 'manager', 'password': 'pass1'})
    assert resp.status_code == 200, f"登录失败: {resp.get_data(as_text=True)}"

    # 查找被分配者与期刊 id
    with app.app_context():
        assignee = User.query.filter_by(username='editor1').first()
        assert assignee is not None
        journal = Journal.query.filter_by(title='Test Journal').first()
        assert journal is not None

    # 调用分配接口
    resp = client.post(f'/api/journals/{journal.id}/assign', json={'assignee_id': assignee.id})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data and data.get('message') == '分配成功'

    # 验证数据库中 created_by 已被更新为 assignee.id
    with app.app_context():
        j = Journal.query.get(journal.id)
        assert j.created_by == assignee.id, f"期刊 created_by 未更新 (expected {assignee.id}, got {j.created_by})"