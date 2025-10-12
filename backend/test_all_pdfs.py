#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pdfplumber
import re
import os
from pathlib import Path

def current_extract_start_page(text: str):
    """当前的页码提取函数"""
    for line in [l.strip() for l in text.splitlines()][:6]:
        m = re.search(r'(\b\d{3}\b)\s*$', line)
        if m: 
            return int(m.group(1))
    return None

def improved_extract_start_page(text: str):
    """改进的页码提取函数 - 支持奇偶数页和灵活位数"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    # 扩大搜索范围到前20行
    for line in lines[:20]:
        # 查找所有1-4位数字
        numbers = re.findall(r'\b\d{1,4}\b', line)
        
        for num_str in numbers:
            num = int(num_str)
            
            # 智能过滤：合理的页码范围
            if 1 <= num <= 9999:
                # 排除明显不是页码的数字
                if num not in [2025, 2024, 42, 4, 10, 20, 30, 100, 200, 300]:
                    return num
    
    return None

def test_single_pdf(pdf_path: str):
    """测试单个PDF文件"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                return None, None, "无页面"
            
            # 测试第1页
            page = pdf.pages[0]
            text = page.extract_text()
            
            if not text:
                return None, None, "无法提取文本"
            
            # 使用当前函数
            current_result = current_extract_start_page(text)
            
            # 使用改进函数
            improved_result = improved_extract_start_page(text)
            
            return current_result, improved_result, "成功"
            
    except Exception as e:
        return None, None, f"错误: {str(e)}"

def test_all_pdfs():
    """测试所有PDF文件"""
    uploads_dir = Path("uploads")
    pdf_files = list(uploads_dir.glob("*.pdf"))
    
    print(f"找到 {len(pdf_files)} 个PDF文件")
    print("=" * 80)
    
    results = []
    
    for i, pdf_file in enumerate(pdf_files[:10]):  # 只测试前10个文件
        print(f"\n[{i+1}] 测试文件: {pdf_file.name}")
        
        current_result, improved_result, status = test_single_pdf(str(pdf_file))
        
        print(f"当前函数结果: {current_result}")
        print(f"改进函数结果: {improved_result}")
        print(f"状态: {status}")
        
        results.append({
            'file': pdf_file.name,
            'current': current_result,
            'improved': improved_result,
            'status': status
        })
        
        print("-" * 40)
    
    # 统计结果
    print("\n" + "=" * 80)
    print("测试结果统计:")
    
    current_success = sum(1 for r in results if r['current'] is not None)
    improved_success = sum(1 for r in results if r['improved'] is not None)
    
    print(f"当前函数成功: {current_success}/{len(results)}")
    print(f"改进函数成功: {improved_success}/{len(results)}")
    
    # 显示改进情况
    print("\n改进情况:")
    for r in results:
        if r['current'] != r['improved']:
            print(f"文件: {r['file']}")
            print(f"  当前函数: {r['current']}")
            print(f"  改进函数: {r['improved']}")
            print()

if __name__ == '__main__':
    test_all_pdfs()



