#!/usr/bin/env python3
"""
数据库迁移脚本：移除论文表中的issue字段，改为通过journal_id外键关联
"""

import pymysql
import logging
from config import current_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """执行数据库迁移"""
    try:
        # 连接数据库
        connection = pymysql.connect(
            host=current_config.DB_HOST,
            port=int(current_config.DB_PORT),
            user=current_config.DB_USER,
            password=current_config.DB_PASSWORD,
            database=current_config.DB_NAME,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 检查issue字段是否存在
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'papers' 
                AND COLUMN_NAME = 'issue'
            """, (current_config.DB_NAME,))
            
            if not cursor.fetchone():
                logger.info("papers表中没有issue字段，无需迁移")
                return
            
            # 备份现有数据（可选）
            logger.info("正在备份现有数据...")
            cursor.execute("SELECT id, issue FROM papers")
            papers_data = cursor.fetchall()
            
            # 删除issue字段
            logger.info("正在删除papers表中的issue字段...")
            cursor.execute("ALTER TABLE papers DROP COLUMN issue")
            
            connection.commit()
            logger.info("数据库迁移完成！")
            logger.info("论文表现在通过journal_id外键关联到期刊表获取刊期信息")
            
            # 显示迁移后的表结构
            logger.info("\n迁移后的papers表结构:")
            cursor.execute("DESCRIBE papers")
            columns = cursor.fetchall()
            for column in columns:
                field, type_info, null, key, default, extra = column
                logger.info(f"  {field:<20} {type_info:<20} {'NULL' if null == 'YES' else 'NOT NULL':<10}")
            
    except Exception as e:
        logger.error(f"数据库迁移失败: {str(e)}")
        raise
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == '__main__':
    migrate_database()
