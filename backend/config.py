import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""
    
    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # 数据库配置 - 使用MySQL
    DB_TYPE = os.getenv('DB_TYPE', 'sqlite')  # sqlite 或 mysql
    
    if DB_TYPE == 'sqlite':
        # SQLite配置
        SQLALCHEMY_DATABASE_URI = 'sqlite:///journal.db'
    else:
        # MySQL配置
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '3306')
        DB_USER = os.getenv('DB_USER', 'root')
        DB_PASSWORD = os.getenv('DB_PASSWORD', 'zs156987')
        DB_NAME = os.getenv('DB_NAME', 'journal')
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT配置
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-string')
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60  # 24小时
    
    # 文件上传配置
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx'}
    
    # 调试模式
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 根据环境变量选择配置
config_mapping = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

# 默认使用开发环境
current_env = os.getenv('FLASK_ENV', 'development')
current_config = config_mapping.get(current_env, DevelopmentConfig)
