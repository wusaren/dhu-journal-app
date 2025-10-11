#!/usr/bin/env python3
"""
数据库迁移脚本：为期刊表添加paper_count字段
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
            # 检查字段是否已存在
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'journals' 
                AND COLUMN_NAME = 'paper_count'
            """, (current_config.DB_NAME,))
            
            if cursor.fetchone():
                logger.info("paper_count字段已存在，跳过迁移")
                return
            
            # 添加paper_count字段
            logger.info("正在添加paper_count字段...")
            cursor.execute("""
                ALTER TABLE journals 
                ADD COLUMN paper_count INT DEFAULT 0 
                AFTER description
            """)
            
            # 更新现有期刊的论文数量
            logger.info("正在更新现有期刊的论文数量...")
            cursor.execute("""
                UPDATE journals 
                SET paper_count = (
                    SELECT COUNT(*) 
                    FROM papers 
                    WHERE papers.journal_id = journals.id
                )
            """)
            
            connection.commit()
            logger.info("数据库迁移完成！")
            
    except Exception as e:
        logger.error(f"数据库迁移失败: {str(e)}")
        raise
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == '__main__':
    migrate_database()
