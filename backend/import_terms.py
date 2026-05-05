"""
术语数据集导入脚本
从CSV文件导入术语数据到数据库
"""

import csv
import os
import sys
from datetime import datetime

from app import app
from models import db, Term

def import_terms_from_csv(csv_path: str, batch_size: int = 1000) -> int:
    """
    从CSV文件导入术语数据
    
    Args:
        csv_path: CSV文件路径
        batch_size: 批量插入大小
        
    Returns:
        导入的记录数
    """
    imported_count = 0
    batch = []
    
    print(f"开始导入: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # 创建Term对象
            term = Term(
                term=row['term'],
                category=row.get('category', ''),
                sentence=row.get('sentence', ''),
                label=int(row['label']) if row.get('label') else None,
                definition=row.get('definition', ''),
                gen_definition=row.get('gen-definition', ''),
                ner_tags=row.get('ner_tags', ''),
                tokens=row.get('tokens', ''),
                is_original_dataset=0,  # 原始数据集
                created_at=datetime.utcnow().date()  # 当前日期
            )
            
            batch.append(term)
            
            # 批量插入
            if len(batch) >= batch_size:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                imported_count += len(batch)
                print(f"  已导入 {imported_count} 条记录...")
                batch = []
        
        # 插入剩余的记录
        if batch:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            imported_count += len(batch)
    
    print(f"[OK] {os.path.basename(csv_path)} 导入完成: {imported_count} 条记录")
    return imported_count

def main():
    """主函数：导入所有CSV文件"""
    with app.app_context():
        # 创建表
        print("创建数据库表...")
        db.create_all()
        print("[OK] 数据库表创建完成")
        
        # 检查是否已有数据
        existing_count = Term.query.count()
        if existing_count > 0:
            print(f"\n警告: 数据库中已有 {existing_count} 条术语记录")
            response = input("是否清空现有数据并重新导入？(yes/no): ")
            if response.lower() == 'yes':
                print("正在清空现有数据...")
                Term.query.delete()
                db.session.commit()
                print("[OK] 数据已清空")
            else:
                print("取消导入")
                return
        
        # CSV文件路径
        csv_files = [
            'services/paper_term/train.csv',
            'services/paper_term/validation.csv',
            'services/paper_term/test.csv'
        ]
        
        total_imported = 0
        
        # 导入每个CSV文件
        for csv_file in csv_files:
            if not os.path.exists(csv_file):
                print(f"[ERROR] 文件不存在: {csv_file}")
                continue
            
            try:
                count = import_terms_from_csv(csv_file, batch_size=1000)
                total_imported += count
            except Exception as e:
                print(f"[ERROR] 导入失败 {csv_file}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n" + "="*60)
        print(f"导入完成！总计导入 {total_imported} 条术语记录")
        print("="*60)
        
        # 显示统计信息
        print("\n数据统计:")
        print(f"  - 总记录数: {Term.query.count()}")
        print(f"  - 原始数据集: {Term.query.filter_by(is_original_dataset=0).count()}")
        print(f"  - 新添加数据: {Term.query.filter_by(is_original_dataset=1).count()}")
        
        # 按类别统计
        print("\n按类别统计:")
        from sqlalchemy import func
        category_stats = db.session.query(
            Term.category, 
            func.count(Term.id)
        ).group_by(Term.category).all()
        
        for category, count in sorted(category_stats, key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {category}: {count}")

if __name__ == '__main__':
    main()

