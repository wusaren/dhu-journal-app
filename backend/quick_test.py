#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pdfplumber
import re

def current_extract_start_page(text: str):
    """当前的页码提取函数"""
    for line in [l.strip() for l in text.splitlines()][:6]:
        m = re.search(r'(\b\d{3}\b)\s*$', line)
        if m: 
            return int(m.group(1))
    return None

def improved_extract_start_page(text: str):
    """改进的页码提取函数"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    for line in lines[:20]:  # 扩大搜索范围
        numbers = re.findall(r'\b\d{1,4}\b', line)  # 支持1-4位数字
        
        for num_str in numbers:
            num = int(num_str)
            if 1 <= num <= 9999:
                # 排除明显不是页码的数字
                if num not in [2025, 2024, 42, 4, 10, 20, 30, 100, 200, 300]:
                    return num
    return None

def test_pdf(pdf_path: str):
    """测试单个PDF"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()
            
            if not text:
                return None, None, "无法提取文本"
            
            current = current_extract_start_page(text)
            improved = improved_extract_start_page(text)
            
            return current, improved, "成功"
            
    except Exception as e:
        return None, None, f"错误: {str(e)}"

# 测试几个关键文件
test_files = [
    "uploads/基于四丁基四氟硼酸铵修饰的导电炭黑开发头孢羟氨苄 抗生素电化学传感器.pdf",
    "uploads/20251012_153645_pdf",
    "uploads/20251012_152334_pdf"
]

print("测试改进的页码提取函数")
print("=" * 50)

for i, pdf_path in enumerate(test_files):
    print(f"\n[{i+1}] 测试: {pdf_path}")
    
    current, improved, status = test_pdf(pdf_path)
    
    print(f"当前函数: {current}")
    print(f"改进函数: {improved}")
    print(f"状态: {status}")
    
    if current != improved:
        print("✅ 有改进!")
    else:
        print("➖ 无变化")
    
    print("-" * 30)



