import shutil
import os
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TODO: 修改为你的 sqlite 数据库文件路径
DB_PATH = r"d:\wsr\project\dhu-Journal-app\backend\instance\journal.db"
BACKUP_PATH = DB_PATH + ".bak_pre_migration"

if not os.path.exists(DB_PATH):
    logger.error(f"数据库文件不存在: {DB_PATH}")
    raise SystemExit(1)

# 备份数据库文件
shutil.copy2(DB_PATH, BACKUP_PATH)
logger.info(f"已备份数据库到: {BACKUP_PATH}")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

with engine.begin() as conn:
    try:
        # 临时关闭外键约束以便重建表
        conn.execute(text("PRAGMA foreign_keys=OFF;"))

        # 如果目标表已存在，先删除（谨慎）
        conn.execute(text("DROP TABLE IF EXISTS journals_new;"))

        # 创建新表 journals_new，包含 (title, issue, created_by) 的唯一约束
        conn.execute(text("""
        CREATE TABLE journals_new (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '东华学报',
            issue TEXT NOT NULL,
            publish_date DATE,
            status TEXT DEFAULT 'draft',
            description TEXT,
            paper_count INTEGER DEFAULT 0,
            created_at DATETIME,
            updated_at DATETIME,
            created_by INTEGER,
            FOREIGN KEY(created_by) REFERENCES users(id),
            UNIQUE(title, issue, created_by)
        );
        """))

        # 把旧表数据拷贝到新表（列名需和旧表一致）
        # 若旧表少某些列或列名不同，需要手动调整 SELECT 列表
        conn.execute(text("""
        INSERT INTO journals_new (id, title, issue, publish_date, status, description, paper_count, created_at, updated_at, created_by)
        SELECT id, title, issue, publish_date, status, description, paper_count, created_at, updated_at, created_by
        FROM journals;
        """))

        # 删除旧表并重命名新表
        conn.execute(text("DROP TABLE journals;"))
        conn.execute(text("ALTER TABLE journals_new RENAME TO journals;"))

        # 重新创建索引（与 models.py 保持一致）
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_journal_title ON journals(title);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_journal_issue ON journals(issue);"))

        # 打开外键约束
        conn.execute(text("PRAGMA foreign_keys=ON;"))

        logger.info("迁移完成：journals 表已替换，新的唯一约束已生效。")
    except Exception as e:
        logger.exception("迁移失败，已停止。请检查备份并恢复。")
        raise
