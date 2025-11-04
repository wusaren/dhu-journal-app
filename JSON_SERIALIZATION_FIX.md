# JSON序列化错误修复说明

## 问题描述

**错误信息：**
```
Object of type Paragraph is not JSON serializable
```

**发生位置：**
- API端点: `/api/paper-format/check-all`
- 错误类型: JSON序列化失败

## 问题原因

检测模块（来自Paper_detect项目）返回的数据中包含了 `python-docx` 库的 `Paragraph` 对象。这些对象存储在检测结果的 `extracted` 和 `details` 字段中，无法直接被JSON序列化。

当Flask尝试使用 `jsonify()` 将检测结果转换为JSON响应时，遇到这些不可序列化的对象，导致500错误。

## 解决方案

### 1. 添加JSON序列化辅助方法

在 `paper_format_service.py` 中添加 `_make_json_serializable()` 方法：

```python
def _make_json_serializable(self, obj: Any) -> Any:
    """
    递归地将对象转换为JSON可序列化的格式
    处理python-docx的Paragraph对象和其他不可序列化的对象
    """
    if obj is None:
        return None
    
    # 处理基本类型
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # 处理列表
    if isinstance(obj, list):
        return [self._make_json_serializable(item) for item in obj]
    
    # 处理字典
    if isinstance(obj, dict):
        return {key: self._make_json_serializable(value) for key, value in obj.items()}
    
    # 处理Paragraph对象和其他复杂对象
    try:
        # 如果是Paragraph对象，获取其text属性
        if hasattr(obj, 'text'):
            return str(obj.text)
        # 如果有__dict__属性，尝试序列化为字典
        elif hasattr(obj, '__dict__'):
            return self._make_json_serializable(obj.__dict__)
        # 其他情况转换为字符串
        else:
            return str(obj)
    except Exception as e:
        logger.warning(f"对象序列化失败: {type(obj)}, {e}")
        return str(obj)
```

**功能：**
- 递归处理所有嵌套的数据结构
- 自动识别并处理 `Paragraph` 对象（提取text属性）
- 兜底转换：无法处理的对象转换为字符串
- 支持基本类型、列表、字典的递归处理

### 2. 在报告标准化中应用

修改 `_normalize_report()` 方法，对所有返回数据进行序列化处理：

```python
# 确保所有数据都是JSON可序列化的
# 这是关键步骤，防止Paragraph等对象导致序列化失败
serializable_checks = self._make_json_serializable(checks)
serializable_summary = self._make_json_serializable(summary)
serializable_extracted = self._make_json_serializable(extracted)
serializable_details = self._make_json_serializable(details)

return {
    'module': module_name,
    'checks': serializable_checks,
    'summary': serializable_summary,
    'extracted': serializable_extracted,
    'details': serializable_details
}
```

### 3. 恢复其他被误删的功能

同时恢复了以下重要功能：

**a) 目录自动创建 (app.py):**
```python
# 创建必要的目录
for folder in [UPLOAD_FOLDER, FORMAT_CHECK_FOLDER, FORMAT_CHECK_TEMP_FOLDER, FORMAT_CHECK_REPORTS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"创建目录: {folder}")
```

**b) 临时文件自动清理 (app.py):**
```python
try:
    # 执行检测
    result = paper_format_service.check_all(...)
    return jsonify(result)
    
finally:
    # 清理临时文件
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
            logger.info(f"已删除临时文件: {temp_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
```

**c) 临时文件清理API:**
```python
@app.route('/api/paper-format/cleanup-temp', methods=['POST'])
def cleanup_temp_files():
    """清理超过指定时间的临时文件"""
    # ... 实现代码
```

## 修改的文件

### 1. backend/services/paper_format_service.py
- ✅ 添加 `_make_json_serializable()` 方法
- ✅ 修改 `_normalize_report()` 使用序列化方法

### 2. backend/app.py
- ✅ 恢复目录自动创建代码
- ✅ 恢复单模块检测API的 try-finally 结构
- ✅ 恢复全量检测API的 try-finally 结构
- ✅ 恢复临时文件清理API端点

## 测试验证

### 验证步骤

1. **启动后端服务**
```bash
cd backend
python app.py
```

2. **测试格式检测**
```bash
# 上传一个docx文件进行全量检测
curl -X POST http://localhost:5000/api/paper-format/check-all \
  -F "file=@test.docx" \
  -F "enableFigureApi=false"
```

3. **检查返回结果**
- 应该返回JSON格式的检测结果
- 不应该出现序列化错误
- 临时文件应该被自动删除

4. **验证临时文件清理**
```bash
curl -X POST http://localhost:5000/api/paper-format/cleanup-temp \
  -H "Content-Type: application/json" \
  -d '{"hours": 24}'
```

## 预期效果

### 修复前
```
2025-11-04 17:53:05,747 - __main__ - ERROR - 全量检测错误: Object of type Paragraph is not JSON serializable
2025-11-04 17:53:05,750 - werkzeug - INFO - 127.0.0.1 - - [04/Nov/2025 17:53:05] "POST /api/paper-format/check-all HTTP/1.1" 500 -
```

### 修复后
```
2025-11-04 18:00:15,123 - __main__ - INFO - 保存临时文件: uploads/format_check/temp/20251104_180015_example.docx
2025-11-04 18:00:18,456 - services.paper_format_service - INFO - 开始全量检测: uploads/format_check/temp/20251104_180015_example.docx
2025-11-04 18:00:25,789 - __main__ - INFO - 已删除临时文件: uploads/format_check/temp/20251104_180015_example.docx
2025-11-04 18:00:25,791 - werkzeug - INFO - 127.0.0.1 - - [04/Nov/2025 18:00:25] "POST /api/paper-format/check-all HTTP/1.1" 200 -
```

## 技术细节

### Paragraph对象的问题

`python-docx` 的 `Paragraph` 对象：
- 是一个复杂的Python对象
- 包含段落的所有格式信息和内容
- 无法直接被 `json.dumps()` 序列化
- 有 `.text` 属性可以获取文本内容

### 序列化策略

1. **基本类型直接返回**: str, int, float, bool
2. **容器类型递归处理**: list, dict
3. **Paragraph对象提取text**: 调用 `.text` 属性
4. **未知对象转字符串**: 使用 `str()` 作为兜底

### 性能影响

- 序列化处理在返回结果前执行一次
- 对于大多数检测结果，性能影响可忽略
- 递归深度有限，不会导致栈溢出

## 注意事项

1. **不要直接修改Paper_detect项目**: 序列化在服务层处理，保持检测模块的独立性
2. **保留原始数据结构**: 只在最后一步进行序列化，中间处理保持原始对象
3. **日志记录**: 序列化失败会记录警告日志，便于问题排查

## 后续优化建议

1. **优化检测模块**: 考虑在Paper_detect项目中直接返回可序列化的数据
2. **缓存序列化结果**: 如果同一检测结果需要多次使用
3. **性能监控**: 添加序列化耗时的性能监控

## 相关文档

- [论文格式检测重构文档](./PAPER_FORMAT_REDESIGN.md)
- [文件存储更新说明](./FORMAT_CHECK_STORAGE_UPDATE.md)
- [python-docx官方文档](https://python-docx.readthedocs.io/)

## 版本信息

- 修复日期: 2025-11-04
- 影响版本: v2.0+
- 修复状态: ✅ 已完成

