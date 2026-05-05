"""
数据库迁移脚本：为format_check_files表添加所有缺失字段

添加：term_result_path, review_status, review_comment, reviewed_at,
      total_checks, passed_checks, failed_checks, pass_rate

使用方法：python add_term_result_path.py
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_database_uri():
    """获取数据库连接URI"""
    db_type = os.getenv('DB_TYPE', 'sqlite')

    if db_type == 'sqlite':
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'journal.db')
        return f'sqlite:///{db_path}'
    else:
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


# 需要添加的字段列表：(字段名, MySQL类型, SQLite类型)
COLUMNS_TO_ADD = [
    ('term_result_path', 'VARCHAR(500)', 'VARCHAR(500)'),
    ('review_status', 'VARCHAR(50)', 'VARCHAR(50)'),
    ('review_comment', 'TEXT', 'TEXT'),
    ('reviewed_at', 'DATETIME', 'DATETIME'),
    ('total_checks', 'INT', 'INTEGER'),
    ('passed_checks', 'INT', 'INTEGER'),
    ('failed_checks', 'INT', 'INTEGER'),
    ('pass_rate', 'FLOAT', 'FLOAT'),
]


def migrate():
    """执行迁移"""
    database_uri = get_database_uri()
    logger.info(f"连接数据库: {database_uri.split('@')[-1] if '@' in database_uri else database_uri}")

    engine = create_engine(database_uri)
    is_mysql = 'mysql' in database_uri.lower()

    with engine.begin() as conn:
        table_name = 'format_check_files'
        added = []
        skipped = []

        for col_name, mysql_type, sqlite_type in COLUMNS_TO_ADD:
            col_type = mysql_type if is_mysql else sqlite_type

            if check_column_exists(engine, table_name, col_name):
                skipped.append(col_name)
                logger.info(f"  - {col_name}: 已存在，跳过")
                continue

            try:
                if is_mysql:
                    conn.execute(text(f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN {col_name} {col_type} NULL
                    """))
                else:
                    # SQLite 不支持 ADD COLUMN 后加 AFTER，需要调整顺序
                    conn.execute(text(f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN {col_name} {col_type}
                    """))
                added.append(col_name)
                logger.info(f"  + {col_name}: 添加成功")
            except Exception as e:
                logger.error(f"  ! {col_name}: 添加失败 - {e}")
                raise

        logger.info("=" * 50)
        if added:
            logger.info(f"成功添加字段: {', '.join(added)}")
        if skipped:
            logger.info(f"跳过字段: {', '.join(skipped)}")
        if not added and not skipped:
            logger.info("没有需要添加的字段")


if __name__ == '__main__':
    try:
        migrate()
        logger.info("迁移完成！")
    except Exception as e:
        logger.error(f"迁移失败: {str(e)}")
        sys.exit(1)
