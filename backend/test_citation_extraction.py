"""
测试Citation提取功能
"""

import sys
import os

# 添加父目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from services.pdf_parser import extract_citation

def test_extract_citation():
    """测试Citation提取功能"""
    
    # 测试用例1：标准的Citation格式
    test_text_1 = """
    This is some text before the citation.
    Citation: Author, A. (2023). Title of the paper. Journal Name, 42(3), 315-329. DOI: 10.1234/example
    This is some text after the citation.
    """
    
    # 测试用例2：中文Citation格式
    test_text_2 = """
    这是引用前的文本。
    引用：作者A. (2023). 论文标题. 期刊名称, 42(3), 315-329. DOI: 10.1234/example
    这是引用后的文本。
    """
    
    # 测试用例3：多行Citation
    test_text_3 = """
    Abstract: This is the abstract.
    Citation: Author, A., & Author, B. (2023). 
    A very long title that spans multiple lines 
    in the citation section. Journal Name, 
    42(3), 315-329. DOI: 10.1234/example
    Keywords: keyword1, keyword2
    """
    
    # 测试用例4：没有Citation的情况
    test_text_4 = """
    This is a text without any citation information.
    Just some regular content here.
    """
    
    # 测试用例5：Citation在行尾
    test_text_5 = """
    Some content here. Citation: Author, A. (2023). Short citation.
    Next line content.
    """
    
    test_cases = [
        ("标准Citation格式", test_text_1),
        ("中文Citation格式", test_text_2),
        ("多行Citation", test_text_3),
        ("无Citation", test_text_4),
        ("行尾Citation", test_text_5)
    ]
    
    print("=== Citation提取功能测试 ===\n")
    
    for test_name, test_text in test_cases:
        print(f"测试: {test_name}")
        print("-" * 50)
        print(f"输入文本:\n{test_text}")
        
        citation = extract_citation(test_text)
        
        if citation:
            print(f"✅ 提取到Citation: {citation}")
            print(f"   长度: {len(citation)} 字符")
        else:
            print("❌ 未提取到Citation")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    test_extract_citation()
