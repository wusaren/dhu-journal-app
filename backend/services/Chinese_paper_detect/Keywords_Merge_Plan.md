# 关键词检测模块合并方案

## 概述

将 `Keywords_detect.py`（中文关键词检测）和 `English_Keywords_detect.py`（英文关键词检测）合并为一个统一的模块 `Keywords_detect_unified.py`，支持同时检测中文和英文关键词。

## 合并方案

### 1. 核心设计思路

- **自动语言检测**：根据模板文件自动判断是中文还是英文关键词
- **统一函数接口**：使用相同的函数名，通过参数区分语言类型
- **共享代码逻辑**：提取公共代码，减少重复
- **向后兼容**：保留原有函数接口，便于逐步迁移

### 2. 主要功能

#### 2.1 自动语言检测
```python
def detect_keywords_language(tpl):
    """根据模板自动检测语言类型"""
    # 通过模板文件名或内容判断
    return 'chinese' 或 'english'
```

#### 2.2 统一检测函数
```python
# 单个关键词检测（自动识别语言）
check_keywords_with_template(doc_path, template_identifier, skip_checks=None, language=None)

# 双语关键词同时检测
check_bilingual_keywords(doc_path, chinese_template=None, english_template=None, skip_checks=None)
```

#### 2.3 字体检测优化
```python
def detect_font_for_run(run, paragraph=None, detect_chinese_font=True):
    """
    统一的字体检测函数
    - 中文关键词：detect_chinese_font=True（检测中英文字体）
    - 英文关键词：detect_chinese_font=False（只检测英文字体，提高性能）
    """
```

### 3. 使用方式

#### 3.1 检测单个关键词（自动识别语言）
```python
from services.Chinese_paper_detect import Keywords_detect_unified as Keywords_detect

# 检测中文关键词（自动识别）
result = Keywords_detect.check_keywords_with_template(
    doc_path="paper.docx",
    template_identifier="Keywords"  # 或 "Chinese_paper_detect_templates/Keywords.json"
)

# 检测英文关键词（自动识别）
result = Keywords_detect.check_keywords_with_template(
    doc_path="paper.docx",
    template_identifier="English_Keywords"
)

# 强制指定语言
result = Keywords_detect.check_keywords_with_template(
    doc_path="paper.docx",
    template_identifier="Keywords",
    language='chinese'  # 或 'english'
)
```

#### 3.2 同时检测双语关键词
```python
# 同时检测中文和英文关键词
result = Keywords_detect.check_bilingual_keywords(
    doc_path="paper.docx",
    chinese_template="Keywords",
    english_template="English_Keywords"
)

# 返回结构：
# {
#     'chinese': {...},  # 中文关键词检测结果
#     'english': {...},  # 英文关键词检测结果
#     'summary': [...]   # 综合总结
# }
```

#### 3.3 命令行使用
```bash
# 检测单个关键词（自动识别）
python Keywords_detect_unified.py check paper.docx Keywords

# 同时检测双语关键词
python Keywords_detect_unified.py check-both paper.docx Keywords English_Keywords
```

### 4. 代码结构对比

#### 4.1 原有结构（两个独立文件）
```
Keywords_detect.py
├── check_keywords_structure()      # 中文关键词结构检测
├── check_keywords_format()         # 中文关键词格式检测
└── check_keywords_with_template()  # 中文关键词主函数

English_Keywords_detect.py
├── check_english_keywords_structure()      # 英文关键词结构检测
├── check_english_keywords_format()         # 英文关键词格式检测
└── check_english_keywords_with_template()  # 英文关键词主函数
```

#### 4.2 合并后结构（统一文件）
```
Keywords_detect_unified.py
├── detect_keywords_language()      # 自动语言检测
├── detect_font_for_run()           # 统一字体检测（支持中英文）
├── check_keywords_structure()      # 统一结构检测（支持中英文）
├── check_keywords_format()         # 统一格式检测（支持中英文）
├── check_keywords_with_template()  # 统一主函数（自动识别语言）
└── check_bilingual_keywords()      # 双语同时检测
```

### 5. 迁移步骤

#### 步骤1：替换导入
```python
# 旧代码
from services.Chinese_paper_detect import Keywords_detect
from services.Chinese_paper_detect import English_Keywords_detect

# 新代码
from services.Chinese_paper_detect import Keywords_detect_unified as Keywords_detect
```

#### 步骤2：更新函数调用
```python
# 旧代码（中文）
result = Keywords_detect.check_keywords_with_template(doc_path, "Keywords")

# 新代码（自动识别，兼容旧代码）
result = Keywords_detect.check_keywords_with_template(doc_path, "Keywords")

# 旧代码（英文）
result = English_Keywords_detect.check_english_keywords_with_template(doc_path, "English_Keywords")

# 新代码（自动识别）
result = Keywords_detect.check_keywords_with_template(doc_path, "English_Keywords")
```

#### 步骤3：使用双语检测（可选）
```python
# 新功能：同时检测双语关键词
result = Keywords_detect.check_bilingual_keywords(doc_path)
```

### 6. 优势

1. **代码复用**：减少重复代码，提高可维护性
2. **统一接口**：使用相同的函数名和参数结构
3. **自动识别**：根据模板自动判断语言类型
4. **性能优化**：英文关键词检测时跳过中文字体检测
5. **功能增强**：支持同时检测双语关键词
6. **向后兼容**：保持原有接口，便于逐步迁移

### 7. 注意事项

1. **模板路径**：确保模板文件路径正确
2. **语言检测**：如果自动检测失败，可以手动指定 `language` 参数
3. **字体检测**：中文关键词会检测中英文字体，英文关键词只检测英文字体
4. **报告格式**：报告结构保持一致，增加了 `language` 字段

### 8. 测试建议

1. 测试中文关键词检测（使用 Keywords.json 模板）
2. 测试英文关键词检测（使用 English_Keywords.json 模板）
3. 测试双语关键词同时检测
4. 测试自动语言识别功能
5. 测试向后兼容性（确保旧代码仍能正常工作）

## 总结

通过合并两个关键词检测模块，我们实现了：
- ✅ 代码统一和复用
- ✅ 自动语言识别
- ✅ 双语同时检测
- ✅ 向后兼容
- ✅ 性能优化

这个统一模块可以完全替代原有的两个独立模块，同时提供更好的功能和更简洁的接口。

