#!/usr/bin/env python3
"""
数据库迁移脚本：为期刊表的issue字段添加唯一约束，然后添加外键约束
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
            # 为期刊表的issue字段添加唯一约束
            logger.info("正在为期刊表的issue字段添加唯一约束...")
            try:
                cursor.execute("""
                    ALTER TABLE journals 
                    ADD CONSTRAINT uk_journals_issue 
                    UNIQUE (issue)
                """)
                logger.info("唯一约束添加成功")
            except Exception as e:
                if "Duplicate key name" in str(e) or "already exists" in str(e):
                    logger.info("唯一约束已存在")
                else:
                    logger.warning(f"唯一约束添加失败: {str(e)}")
            
            # 添加外键约束
            logger.info("正在添加外键约束...")
            try:
                cursor.execute("""
                    ALTER TABLE papers 
                    ADD CONSTRAINT fk_papers_issue 
                    FOREIGN KEY (issue) REFERENCES journals(issue)
                """)
                logger.info("外键约束添加成功")
            except Exception as e:
                if "Duplicate key name" in str(e) or "already exists" in str(e):
                    logger.info("外键约束已存在")
                else:
                    logger.warning(f"外键约束添加失败: {str(e)}")
            
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






