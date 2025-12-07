"""
生成默认论文数据的JSON缓存文件
运行: python generate_default_paper_data.py
"""
import os
import json
import sys
from pathlib import Path

# 强制刷新输出
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("正在导入模块...", flush=True)
from services.pdf_parser import parse_pdf_to_papers
print("✅ pdf_parser导入成功", flush=True)
from services.document_generator import generate_citation
print("✅ document_generator导入成功", flush=True)
from datetime import datetime
print("✅ 所有模块导入完成", flush=True)

def generate_default_paper_json():
    """从PDF提取数据并保存为JSON文件"""
    # PDF文件路径
    default_pdf_path = os.path.join('configs', '附件1-已排好版的论文.pdf')
    
    if not os.path.exists(default_pdf_path):
        print(f"错误: PDF文件不存在: {default_pdf_path}")
        return False
    
    print(f"开始解析PDF文件: {default_pdf_path}")
    
    # 创建临时输出目录
    temp_output_dir = os.path.join('temp_images', datetime.now().strftime('%Y%m%d_%H%M%S'))
    os.makedirs(temp_output_dir, exist_ok=True)
    
    try:
        # 解析PDF
        papers_data = parse_pdf_to_papers(default_pdf_path, journal_id=0, output_dir=temp_output_dir)
        
        if not papers_data:
            print("错误: 无法从PDF中提取论文数据")
            return False
        
        # 使用第一篇论文的数据
        source_data = papers_data[0]
        
        # 生成citation（如果还没有）
        if 'citation' not in source_data or not source_data.get('citation'):
            try:
                source_data['citation'] = generate_citation(source_data)
                print(f"✅ 已生成citation: {source_data['citation'][:100]}...")
            except Exception as e:
                print(f"警告: 生成citation失败: {str(e)}")
                source_data['citation'] = ''
        
        # 确保所有需要的字段都存在
        required_fields = {
            'title': '',
            'chinese_title': '',
            'authors': '',
            'chinese_authors': '',
            'doi': '',
            'citation': '',
            'page_start': '',
            'page_end': '',
            'first_image_url': source_data.get('first_local_path', ''),
            'second_image_url': source_data.get('second_local_path', ''),
        }
        
        # 合并数据，确保所有字段都存在
        for key, default_value in required_fields.items():
            if key not in source_data:
                source_data[key] = default_value
        
        # 将图片路径字段统一为URL格式（用于预览）
        if 'first_local_path' in source_data and source_data['first_local_path']:
            source_data['first_image_url'] = source_data['first_local_path']
        if 'second_local_path' in source_data and source_data['second_local_path']:
            source_data['second_image_url'] = source_data['second_local_path']
        
        # 保存为JSON文件
        json_path = os.path.join('configs', 'default_paper_data.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(source_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功生成JSON缓存文件: {json_path}")
        print(f"   包含字段: {', '.join(sorted(source_data.keys()))}")
        print(f"   标题: {source_data.get('title', '')[:50]}...")
        print(f"   引用信息: {source_data.get('citation', '')[:80]}...")
        return True
        
    except Exception as e:
        print(f"错误: 处理失败: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("开始生成默认论文数据JSON文件...")
    print("=" * 50)
    try:
        success = generate_default_paper_json()
        if success:
            print("=" * 50)
            print("✅ 脚本执行成功")
            print("=" * 50)
        else:
            print("=" * 50)
            print("❌ 脚本执行失败")
            print("=" * 50)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未捕获的异常: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)


