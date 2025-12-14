# MinerU 参数修改指南

## 参数修改位置

根据你的需求，可以在以下位置修改参数：

### 1. 修改默认参数（推荐）

**位置**: `backend/services/mineru_service.py` 第381-388行

```python
@staticmethod
def get_default_params() -> Dict[str, Any]:
    return {
        'model_version': 'vlm',      # ← 修改这里
        'language': 'ch',            # ← 修改这里
        'enable_formula': True,      # ← 修改这里
        'enable_table': True,        # ← 修改这里
        'is_ocr': False,             # ← 修改这里
        'wait': False                # ← 修改这里
    }
```

**影响范围**：
- ✅ 文件上传时自动调用（如果不传参数）
- ✅ API调用时（如果不传参数）
- ✅ 所有使用默认值的地方

**示例**：如果想默认开启OCR
```python
'is_ocr': True,  # 改为True
```

---

### 2. 修改文件上传时的参数

**位置**: `backend/services/file_service.py` 第191-195行

```python
mineru_result = _process_file_with_mineru_internal(
    file_path=file_path,
    data_id=f"file_{file_upload.id}",
    wait=False,                    # ← 修改这里
    # 可以添加其他参数
    is_ocr=True,                   # ← 添加参数
    model_version="pipeline"       # ← 添加参数
)
```

**影响范围**：
- ✅ 只影响文件上传时的调用
- ❌ 不影响API调用

**示例**：文件上传时开启OCR
```python
mineru_result = _process_file_with_mineru_internal(
    file_path=file_path,
    data_id=f"file_{file_upload.id}",
    wait=False,
    is_ocr=True  # 添加这个参数
)
```

---

### 3. API调用时传参（动态）

**位置**: HTTP请求中传入

```bash
POST /api/mineru/process
Content-Type: application/json

{
    "file_path": "./uploads/paper.pdf",
    "wait": true,                  # ← 传参覆盖默认值
    "is_ocr": true,                # ← 传参覆盖默认值
    "model_version": "pipeline"    # ← 传参覆盖默认值
}
```

**影响范围**：
- ✅ 只影响本次API调用
- ❌ 不影响默认值和其他调用

---

### 4. 从配置文件读取（高级）

如果想从配置文件读取参数，可以修改：

**位置1**: `backend/config/config.py`

```python
# 添加配置项
MINERU_DEFAULT_MODEL_VERSION = os.getenv('MINERU_DEFAULT_MODEL_VERSION', 'vlm')
MINERU_DEFAULT_OCR = os.getenv('MINERU_DEFAULT_OCR', 'False').lower() == 'true'
MINERU_DEFAULT_WAIT = os.getenv('MINERU_DEFAULT_WAIT', 'False').lower() == 'true'
```

**位置2**: `backend/services/mineru_service.py`

```python
@staticmethod
def get_default_params() -> Dict[str, Any]:
    from config.config import current_config
    return {
        'model_version': current_config.MINERU_DEFAULT_MODEL_VERSION,
        'is_ocr': current_config.MINERU_DEFAULT_OCR,
        'wait': current_config.MINERU_DEFAULT_WAIT,
        # ...
    }
```

**位置3**: `.env` 文件

```env
MINERU_DEFAULT_MODEL_VERSION=vlm
MINERU_DEFAULT_OCR=True
MINERU_DEFAULT_WAIT=False
```

---

## 参数优先级

```
API调用时传参 > 文件上传时传参 > 默认参数
```

**示例**：
- 默认参数：`is_ocr=False`
- 文件上传时：`is_ocr=True`
- API调用时：`is_ocr=False`（传参）

结果：API调用时使用 `False`（API传参优先级最高）

---

## 常见修改场景

### 场景1：所有调用都默认开启OCR

**修改位置**: `services/mineru_service.py` 第386行

```python
'is_ocr': True,  # 改为True
```

### 场景2：文件上传时开启OCR，API调用不开启

**修改位置**: `services/file_service.py` 第194行

```python
mineru_result = _process_file_with_mineru_internal(
    file_path=file_path,
    data_id=f"file_{file_upload.id}",
    wait=False,
    is_ocr=True  # 添加这个参数
)
```

### 场景3：API调用时动态传参

**调用方式**:
```bash
POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf",
    "is_ocr": true  # 本次调用开启OCR
}
```

### 场景4：修改模型版本

**修改默认值**: `services/mineru_service.py`
```python
'model_version': 'pipeline',  # 改为pipeline
```

**或API调用时传参**:
```bash
{
    "file_path": "./uploads/paper.pdf",
    "model_version": "pipeline"
}
```

### 场景5：添加额外导出格式

**API调用时**:
```bash
{
    "file_path": "./uploads/paper.pdf",
    "extra_formats": ["docx", "html"]
}
```

---

## 参数说明表

| 参数 | 类型 | 默认值 | 修改位置 | 说明 |
|------|------|--------|----------|------|
| `model_version` | string | `"vlm"` | `mineru_service.py:382` | vlm或pipeline |
| `language` | string | `"ch"` | `mineru_service.py:383` | 文档语言 |
| `enable_formula` | bool | `True` | `mineru_service.py:384` | 公式识别 |
| `enable_table` | bool | `True` | `mineru_service.py:385` | 表格识别 |
| `is_ocr` | bool | `False` | `mineru_service.py:386` | OCR功能 |
| `wait` | bool | `False` | `mineru_service.py:387` | 是否等待完成 |
| `page_ranges` | string | `None` | API调用时传参 | 页码范围 |
| `extra_formats` | list | `None` | API调用时传参 | 额外格式 |

---

## 快速修改指南

### 修改所有调用的默认值
👉 编辑 `backend/services/mineru_service.py` 第381-388行

### 只修改文件上传时的参数
👉 编辑 `backend/services/file_service.py` 第191-195行

### API调用时动态传参
👉 在HTTP请求的JSON body中传入参数

### 从配置文件读取
👉 修改 `config.py` 和 `.env` 文件

---

## 推荐做法

1. **一般情况**：修改默认参数（`mineru_service.py`）
2. **特殊情况**：文件上传时单独传参（`file_service.py`）
3. **动态需求**：API调用时传参（HTTP请求）





