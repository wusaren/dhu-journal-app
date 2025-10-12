#!/usr/bin/env python3
"""
数据库迁移脚本：恢复论文表中的issue字段，并添加外键约束
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
            # 检查issue字段是否已存在
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'papers' 
                AND COLUMN_NAME = 'issue'
            """, (current_config.DB_NAME,))
            
            if cursor.fetchone():
                logger.info("papers表中issue字段已存在")
            else:
                # 重新添加issue字段
                logger.info("正在重新添加papers表中的issue字段...")
                cursor.execute("""
                    ALTER TABLE papers 
                    ADD COLUMN issue varchar(100) NOT NULL 
                    AFTER corresponding
                """)
                
                # 从期刊表更新论文的issue字段
                logger.info("正在从期刊表更新论文的issue字段...")
                cursor.execute("""
                    UPDATE papers p 
                    JOIN journals j ON p.journal_id = j.id 
                    SET p.issue = j.issue
                """)
            
            # 添加外键约束（如果不存在）
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
            
            # 显示迁移后的表结构
            logger.info("\n迁移后的papers表结构:")
            cursor.execute("DESCRIBE papers")
            columns = cursor.fetchall()
            for column in columns:
                field, type_info, null, key, default, extra = column
                logger.info(f"  {field:<20} {type_info:<20} {'NULL' if null == 'YES' else 'NOT NULL':<10} {key:<10}")
            
    except Exception as e:
        logger.error(f"数据库迁移失败: {str(e)}")
        raise
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == '__main__':
    migrate_database()






