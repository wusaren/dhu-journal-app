"""
数据库迁移脚本：为papers表添加mineru_folder字段

使用方法：
1. MySQL: 直接运行此脚本
2. SQLite: 修改数据库路径后运行

功能：
1. 添加 minern_folder 列
2. 自动回填：基于 paper.file_path 关联的原始PDF文件名，匹配 mineru_output 中的文件夹
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


def get_mineru_output_dir():
    """获取MinerU输出目录"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_dir, 'mineru_output')


def get_mineru_folder_mapping(mineru_output_dir):
    """
    扫描 mineru_output 目录，建立"PDF文件名 -> mineru文件夹名"的映射。
    例如：JDHUE2026.1 -> JDHUE2026.1_1772798463
    """
    mapping = {}
    if not os.path.exists(mineru_output_dir):
        logger.warning(f"MinerU输出目录不存在: {mineru_output_dir}")
        return mapping

    for folder_name in os.listdir(mineru_output_dir):
        folder_path = os.path.join(mineru_output_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        # 从文件夹名提取基础文件名（去掉时间戳后缀）
        # 文件夹名格式可能是: JDHUE2026.1 或 JDHUE2026.1_1772798463
        parts = folder_name.rsplit('_', 1)
        if len(parts) == 2 and parts[1].isdigit():
            base_name = parts[0]
        else:
            base_name = folder_name
        if base_name not in mapping:
            mapping[base_name] = folder_name
            logger.info(f"  匹配: {base_name} -> {folder_name}")

    return mapping


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

    # Step 1: 添加列
    with engine.begin() as conn:
        if check_column_exists(engine, 'papers', 'mineru_folder'):
            logger.info("papers表已存在mineru_folder字段，跳过添加列")
        else:
            logger.info("正在为papers表添加mineru_folder字段...")
            if 'mysql' in database_uri.lower():
                conn.execute(text("""
                    ALTER TABLE papers
                    ADD COLUMN mineru_folder VARCHAR(255) NULL
                    AFTER second_image_url
                """))
            else:
                conn.execute(text("""
                    ALTER TABLE papers
                    ADD COLUMN mineru_folder TEXT
                """))
            logger.info("成功添加mineru_folder字段")

    # Step 2: 回填数据
    logger.info("开始回填mineru_folder数据...")

    mineru_output_dir = get_mineru_output_dir()
    folder_mapping = get_mineru_folder_mapping(mineru_output_dir)

    if not folder_mapping:
        logger.warning("没有找到任何miner_output文件夹，跳过回填")
        return

    logger.info(f"扫描到 {len(folder_mapping)} 个mineru_output文件夹")

    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, file_path, first_image_url, second_image_url FROM papers WHERE mineru_folder IS NULL OR mineru_folder = ''"))
        papers = result.fetchall()

        if not papers:
            logger.info("没有需要回填的论文")
            return

        logger.info(f"找到 {len(papers)} 篇论文需要回填")

        updated = 0
        for paper in papers:
            paper_id, file_path, first_img, second_img = paper
            mineru_folder = None

            # 策略1：从file_path反推
            if file_path:
                file_basename = os.path.splitext(os.path.basename(file_path))[0]
                if file_basename in folder_mapping:
                    mineru_folder = folder_mapping[file_basename]
                    logger.info(f"  论文 {paper_id}: file_path='{file_path}' -> mineru_folder='{mineru_folder}'")
                else:
                    # 尝试前缀匹配（文件夹名可能带时间戳后缀）
                    for base, folder in folder_mapping.items():
                        if file_basename.startswith(base) or base.startswith(file_basename):
                            mineru_folder = folder
                            logger.info(f"  论文 {paper_id}: file_path='{file_path}' -> mineru_folder='{mineru_folder}' (前缀匹配)")
                            break

            # 策略2：从图片路径反推（如果图片路径包含图片文件名）
            if not mineru_folder and (first_img or second_img):
                img_path = first_img or second_img
                if img_path:
                    img_basename = os.path.basename(img_path)
                    for folder_name in os.listdir(mineru_output_dir):
                        img_folder = os.path.join(mineru_output_dir, folder_name, 'images')
                        if os.path.exists(img_folder) and os.path.exists(os.path.join(img_folder, img_basename)):
                            mineru_folder = folder_name
                            logger.info(f"  论文 {paper_id}: 图片文件名='{img_basename}' -> mineru_folder='{mineru_folder}'")
                            break

            if mineru_folder:
                conn.execute(
                    text("UPDATE papers SET mineru_folder = :folder WHERE id = :id"),
                    {"folder": mineru_folder, "id": paper_id}
                )
                updated += 1

        logger.info(f"回填完成，共更新 {updated} 篇论文")

    logger.info("迁移完成!")


if __name__ == '__main__':
    try:
        migrate()
        logger.info("迁移完成！")
    except Exception as e:
        logger.error(f"迁移失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
