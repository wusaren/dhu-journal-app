"""
数据库迁移脚本：为papers表添加citation字段

使用方法：
1. MySQL: 直接运行此脚本
2. SQLite: 修改数据库路径后运行
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_uri():
    """获取数据库连接URI"""
    db_type = os.getenv('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        # SQLite配置
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'journal.db')
        return f'sqlite:///{db_path}'
    else:
        # MySQL配置
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '3306')
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        db_name = os.getenv('DB_NAME', 'journal')
        return f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def check_column_exists(engine, table_name, column_name):
    """检查列是否已存在"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def migrate():
    """执行迁移"""
    database_uri = get_database_uri()
    logger.info(f"连接数据库: {database_uri.split('@')[-1] if '@' in database_uri else database_uri}")
    
    engine = create_engine(database_uri)
    
    with engine.begin() as conn:
        try:
            # 检查citation列是否已存在
            if check_column_exists(engine, 'papers', 'citation'):
                logger.info("papers表已存在citation字段，跳过迁移")
                return
            
            # 添加citation字段
            logger.info("正在为papers表添加citation字段...")
            
            if 'mysql' in database_uri.lower():
                # MySQL语法
                conn.execute(text("""
                    ALTER TABLE papers 
                    ADD COLUMN citation TEXT NULL 
                    AFTER keywords
                """))
            else:
                # SQLite语法
                conn.execute(text("""
                    ALTER TABLE papers 
                    ADD COLUMN citation TEXT
                """))
            
            logger.info("✓ 成功添加citation字段到papers表")
            
        except Exception as e:
            logger.error(f"迁移失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise

if __name__ == '__main__':
    try:
        migrate()
        logger.info("迁移完成！")
    except Exception as e:
        logger.error(f"迁移失败: {str(e)}")
        sys.exit(1)

