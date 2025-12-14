# MinerU API 参数设置说明

## 当前代码中的参数设置

### 1. 文件上传时自动调用（file_service.py）

```python
mineru_service.process_local_file(
    file_path=file_path,                    # 必需：本地文件路径
    data_id=f"file_{file_upload.id}",      # 可选：业务数据ID，用于标识
    wait=False,                             # 是否等待完成：False=异步，True=同步
    model_version="vlm",                    # 模型版本：vlm 或 pipeline
    language="ch",                          # 文档语言：ch=中文，en=英文等
    enable_formula=True,                    # 是否开启公式识别
    enable_table=True                       # 是否开启表格识别
)
```

### 2. API接口调用（files.py）

```python
# POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf",    # 必需：文件路径
    "data_id": "paper_001",                 # 可选：业务数据ID
    "wait": true                            # 可选：是否等待完成，默认true
}

# 内部调用参数（固定值）：
model_version="vlm"
language="ch"
enable_formula=True
enable_table=True
```

## 参数详细说明

### 必需参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `file_path` | string | 本地PDF文件路径 | `"./uploads/paper.pdf"` |
| `filename` | string | 文件名（自动从file_path提取） | `"paper.pdf"` |

### 可选参数

#### 1. 基础参数

| 参数 | 类型 | 默认值 | 说明 | 推荐值 |
|------|------|--------|------|--------|
| `data_id` | string | None | 业务数据ID，用于标识你的数据 | `"file_123"` 或 `"paper_001"` |
| `wait` | bool | False | 是否等待解析完成 | `False`=异步（推荐），`True`=同步 |

#### 2. 模型和语言参数

| 参数 | 类型 | 默认值 | 可选值 | 推荐值 | 说明 |
|------|------|--------|--------|--------|------|
| `model_version` | string | `"vlm"` | `"vlm"` 或 `"pipeline"` | `"vlm"` | vlm对中文和复杂格式支持更好 |
| `language` | string | `"ch"` | `"ch"`, `"en"` 等 | `"ch"` | 你的项目有中文内容 |

#### 3. 功能开关参数

| 参数 | 类型 | 默认值 | 推荐值 | 说明 |
|------|------|--------|--------|------|
| `enable_formula` | bool | True | `True` | 论文通常有公式，建议开启 |
| `enable_table` | bool | True | `True` | 论文通常有表格，建议开启 |
| `is_ocr` | bool | False | `True`（扫描版PDF） | 是否启动OCR，对扫描版PDF有用 |

#### 4. 文件处理参数

| 参数 | 类型 | 默认值 | 说明 | 示例 |
|------|------|--------|------|------|
| `page_ranges` | string | None | 指定页码范围 | `"1-100"` 或 `"2,4-6"` |
| `extra_formats` | list | None | 额外导出格式 | `["docx", "html"]` |

#### 5. 回调参数（高级）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `callback` | string | None | 回调通知URL |
| `seed` | string | None | 回调签名校验用的随机字符串 |

## 针对你的项目的推荐配置

### 推荐配置1：标准论文处理（当前使用）

```python
{
    "model_version": "vlm",        # 对中文支持好
    "language": "ch",              # 中文文档
    "enable_formula": True,        # 论文有公式
    "enable_table": True,           # 论文有表格
    "is_ocr": False,               # 普通PDF不需要OCR
    "wait": False                  # 异步处理，不阻塞
}
```

### 推荐配置2：扫描版PDF

```python
{
    "model_version": "vlm",
    "language": "ch",
    "enable_formula": True,
    "enable_table": True,
    "is_ocr": True,                # 开启OCR
    "wait": False
}
```

### 推荐配置3：需要额外格式

```python
{
    "model_version": "vlm",
    "language": "ch",
    "enable_formula": True,
    "enable_table": True,
    "extra_formats": ["docx"],     # 额外导出Word格式
    "wait": False
}
```

### 推荐配置4：大文件分页处理

```python
{
    "model_version": "vlm",
    "language": "ch",
    "enable_formula": True,
    "enable_table": True,
    "page_ranges": "1-100",        # 只处理前100页
    "wait": False
}
```

## 参数使用示例

### 示例1：Python代码调用

```python
from services.mineru_service import MinerUService

mineru_service = MinerUService()

# 标准配置
result = mineru_service.process_local_file(
    file_path="./uploads/paper.pdf",
    data_id="paper_001",
    wait=False,                    # 异步
    model_version="vlm",
    language="ch",
    enable_formula=True,
    enable_table=True
)

# 扫描版PDF
result = mineru_service.process_local_file(
    file_path="./uploads/scanned_paper.pdf",
    wait=False,
    model_version="vlm",
    language="ch",
    enable_formula=True,
    enable_table=True,
    is_ocr=True                    # 开启OCR
)
```

### 示例2：API调用

```bash
# 标准调用
POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf",
    "data_id": "paper_001",
    "wait": false
}

# 同步调用（等待完成）
POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf",
    "wait": true
}
```

## 参数说明总结

### 必须设置的参数
- ✅ `file_path`: 文件路径（必需）

### 推荐设置的参数
- ✅ `model_version`: `"vlm"` （对中文支持好）
- ✅ `language`: `"ch"` （你的项目是中文）
- ✅ `enable_formula`: `True` （论文有公式）
- ✅ `enable_table`: `True` （论文有表格）
- ✅ `wait`: `False` （异步处理，不阻塞）

### 可选设置的参数
- ⚪ `data_id`: 用于标识业务数据
- ⚪ `is_ocr`: 扫描版PDF需要设置为 `True`
- ⚪ `page_ranges`: 大文件可以限制页数
- ⚪ `extra_formats`: 需要额外格式时设置

### 不需要设置的参数
- ❌ `callback`: 除非需要回调通知
- ❌ `seed`: 除非使用回调

## 注意事项

1. **model_version选择**：
   - `"vlm"`: 推荐，对中文和复杂格式支持更好
   - `"pipeline"`: 传统模型，速度可能更快但效果稍差

2. **wait参数**：
   - `False`: 异步，立即返回batch_id，适合大文件
   - `True`: 同步，等待完成，适合小文件或需要立即获取结果

3. **is_ocr参数**：
   - `False`: 普通PDF（文本型）
   - `True`: 扫描版PDF（图片型）

4. **page_ranges格式**：
   - `"1-100"`: 第1页到100页
   - `"2,4-6"`: 第2页，第4-6页
   - `"2--2"`: 第2页到倒数第2页

5. **extra_formats**：
   - 默认会生成 `markdown` 和 `json`
   - 可选添加：`["docx"]`, `["html"]`, `["latex"]` 或组合





