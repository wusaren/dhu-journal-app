# MinerU 参数使用对比说明

## 当前两种调用方式的差异

### 1. 文件上传时自动调用（file_service.py）

**位置**：`backend/services/file_service.py` 第191行

**调用方式**：
```python
mineru_service.process_local_file(
    file_path=file_path,
    data_id=f"file_{file_upload.id}",
    wait=False,                    # ← 固定为False（异步）
    model_version="vlm",            # ← 固定值
    language="ch",                  # ← 固定值
    enable_formula=True,            # ← 固定值
    enable_table=True               # ← 固定值
)
```

**特点**：
- ✅ 自动触发（当 `USE_MINERU=True` 时）
- ✅ 异步处理（`wait=False`），不阻塞文件上传流程
- ❌ 参数固定，无法自定义

### 2. API接口调用（files.py）

**位置**：`backend/blueprints/files.py` 第201行

**调用方式**：
```python
# 请求参数
{
    "file_path": "./uploads/paper.pdf",
    "data_id": "paper_001",         # 可选
    "wait": false,                  # 可选，默认false（已统一）
    "model_version": "vlm",         # 可选，默认vlm
    "language": "ch",               # 可选，默认ch
    "enable_formula": true,         # 可选，默认true
    "enable_table": true,           # 可选，默认true
    "is_ocr": false,                # 可选，默认false
    "page_ranges": "1-100",         # 可选
    "extra_formats": ["docx"]      # 可选
}

# 内部调用
mineru_service.process_local_file(
    file_path=file_path,
    data_id=data_id,
    wait=wait,                      # ← 从请求参数获取，默认false
    model_version=model_version,    # ← 从请求参数获取，默认vlm
    language=language,              # ← 从请求参数获取，默认ch
    enable_formula=enable_formula,  # ← 从请求参数获取，默认true
    enable_table=enable_table,      # ← 从请求参数获取，默认true
    is_ocr=is_ocr,                  # ← 从请求参数获取，默认false
    page_ranges=page_ranges,        # ← 从请求参数获取
    extra_formats=extra_formats     # ← 从请求参数获取
)
```

**特点**：
- ✅ 手动调用（通过API）
- ✅ 参数可自定义
- ✅ 支持更多参数（is_ocr, page_ranges, extra_formats等）

## 参数对比表

| 参数 | 文件上传时 | API调用时 | 说明 |
|------|-----------|----------|------|
| `wait` | `False`（固定） | `False`（默认，可改） | ✅ 已统一 |
| `model_version` | `"vlm"`（固定） | `"vlm"`（默认，可改） | ✅ 已统一 |
| `language` | `"ch"`（固定） | `"ch"`（默认，可改） | ✅ 已统一 |
| `enable_formula` | `True`（固定） | `True`（默认，可改） | ✅ 已统一 |
| `enable_table` | `True`（固定） | `True`（默认，可改） | ✅ 已统一 |
| `is_ocr` | ❌ 不支持 | ✅ 支持（可设置） | ⚠️ 差异 |
| `page_ranges` | ❌ 不支持 | ✅ 支持（可设置） | ⚠️ 差异 |
| `extra_formats` | ❌ 不支持 | ✅ 支持（可设置） | ⚠️ 差异 |

## 统一后的默认参数

两种方式现在使用**相同的默认参数**：

```python
{
    "wait": False,                  # 异步处理
    "model_version": "vlm",         # vlm模型
    "language": "ch",               # 中文
    "enable_formula": True,         # 开启公式识别
    "enable_table": True            # 开启表格识别
}
```

## 使用建议

### 场景1：文件上传时自动使用
- **适用**：批量上传，不需要立即获取结果
- **特点**：参数固定，异步处理
- **配置**：在 `.env` 中设置 `USE_MINERU=True`

### 场景2：通过API手动调用
- **适用**：需要自定义参数，或需要立即获取结果
- **特点**：参数可配置，支持更多选项
- **使用**：调用 `/api/mineru/process` 接口

## 如果需要统一更多参数

如果希望文件上传时也能自定义参数，可以：

1. **方案1**：在配置文件中添加参数
   ```python
   # config.py
   MINERU_MODEL_VERSION = os.getenv('MINERU_MODEL_VERSION', 'vlm')
   MINERU_ENABLE_OCR = os.getenv('MINERU_ENABLE_OCR', 'False').lower() == 'true'
   ```

2. **方案2**：在文件上传接口中添加可选参数
   ```python
   # 从请求中获取参数（如果提供）
   use_mineru_params = request.form.get('mineru_params')
   if use_mineru_params:
       # 解析参数并传递给MinerU
   ```

## 总结

✅ **已统一**：默认参数值（wait, model_version, language等）
⚠️ **有差异**：API调用支持更多可选参数（is_ocr, page_ranges等）
💡 **建议**：根据需求选择使用方式
   - 简单场景：使用文件上传自动调用
   - 复杂场景：使用API手动调用，自定义参数





