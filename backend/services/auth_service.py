"""
认证服务
从 app.py 中提取认证相关业务逻辑，保持完全兼容
"""
from models import User, db
from flask_jwt_extended import create_access_token
import bcrypt
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """认证服务类"""
    
    def login(self, username, password):
        """
        用户登录 - 从 app.py 中提取，保持完全兼容
        返回格式与原来完全一致
        """
        try:
            if not username or not password:
                return {'success': False, 'message': '用户名和密码不能为空', 'status_code': 400}
            
            user = User.query.filter_by(username=username).first()
            if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return {'success': False, 'message': '用户名或密码错误', 'status_code': 401}
            
            access_token = create_access_token(identity=user.id)
            return {
                'success': True,
                'message': '登录成功',
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role
                }
            }
        
        except Exception as e:
            logger.error(f"登录错误: {str(e)}")
            return {'success': False, 'message': f'登录失败: {str(e)}', 'status_code': 500}
    
    def create_default_admin(self):
        """创建默认管理员用户 - 从 app.py 中提取"""
        try:
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
                admin_user = User(
                    username='admin',
                    password_hash=password_hash.decode('utf-8'),
                    email='admin@example.com',
                    role='admin'
                )
                db.session.add(admin_user)
                db.session.commit()
                logger.info("默认管理员用户已创建")
                return True
            return False
        except Exception as e:
            logger.error(f"创建默认管理员用户失败: {str(e)}")
            return False

