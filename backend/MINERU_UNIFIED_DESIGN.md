# MinerU 统一设计说明

## 设计理念

**统一使用服务类，不再分开设计**

所有调用（文件上传、API接口）都使用同一个服务类 `MinerUService`，参数统一管理。

## 架构设计

```
┌─────────────────────────────────────────┐
│         MinerUService (服务类)           │
│  - get_default_params() 统一默认参数     │
│  - process_local_file() 统一处理逻辑    │
└─────────────────────────────────────────┘
              ▲              ▲
              │              │
    ┌─────────┘              └─────────┐
    │                                  │
┌───┴──────────┐            ┌─────────┴────────┐
│ 文件上传时    │            │  API接口调用     │
│ file_service │            │  files.py        │
│              │            │                  │
│ 使用默认参数  │            │ 可自定义参数     │
└──────────────┘            └──────────────────┘
```

## 统一后的调用方式

### 1. 文件上传时（file_service.py）

```python
# 直接使用服务类，使用默认参数
mineru_service = MinerUService()
result = mineru_service.process_local_file(
    file_path=file_path,
    data_id=f"file_{file_upload.id}"
    # 不传其他参数 = 使用默认参数（统一管理）
)
```

### 2. API接口调用（files.py）

```python
# 使用服务类，可以覆盖默认参数
mineru_service = MinerUService()
result = mineru_service.process_local_file(
    file_path=file_path,
    data_id=data_id,
    # 可以传入自定义参数，覆盖默认值
    wait=True,              # 覆盖默认的False
    is_ocr=True,            # 覆盖默认的False
    # 不传的参数 = 使用默认值
)
```

## 默认参数（统一管理）

所有默认参数都在 `MinerUService.get_default_params()` 中定义：

```python
{
    'model_version': 'vlm',      # vlm模型
    'language': 'ch',            # 中文
    'enable_formula': True,      # 开启公式识别
    'enable_table': True,        # 开启表格识别
    'is_ocr': False,             # 不开启OCR
    'wait': False                # 异步处理
}
```

## 优势

### ✅ 统一管理
- 所有默认参数在一个地方定义
- 修改默认值只需要改一个地方

### ✅ 代码复用
- 文件上传和API调用使用相同的逻辑
- 不需要重复代码

### ✅ 灵活配置
- API调用时可以覆盖默认参数
- 文件上传时使用默认参数（简单场景）

### ✅ 易于维护
- 逻辑集中，易于调试
- 参数统一，避免不一致

## 使用示例

### 示例1：文件上传时（使用默认参数）

```python
# 在 file_service.py 中
mineru_service = MinerUService()
result = mineru_service.process_local_file(
    file_path="./uploads/paper.pdf",
    data_id="file_123"
)
# 自动使用默认参数：
# - wait=False (异步)
# - model_version="vlm"
# - language="ch"
# - enable_formula=True
# - enable_table=True
```

### 示例2：API调用（自定义参数）

```bash
POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf",
    "wait": true,              # 覆盖默认值，改为同步
    "is_ocr": true             # 覆盖默认值，开启OCR
    # 其他参数不传，使用默认值
}
```

### 示例3：API调用（全部使用默认值）

```bash
POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf"
    # 不传任何参数，全部使用默认值
}
```

## 如果需要修改默认参数

### 方式1：修改代码（永久修改）

在 `mineru_service.py` 的 `get_default_params()` 方法中修改：

```python
@staticmethod
def get_default_params() -> Dict[str, Any]:
    return {
        'model_version': 'vlm',
        'language': 'ch',
        'enable_formula': True,
        'enable_table': True,
        'is_ocr': True,        # 改为True
        'wait': True           # 改为True
    }
```

### 方式2：从配置文件读取（推荐）

可以在 `config.py` 中添加配置项，然后从配置读取：

```python
# config.py
MINERU_DEFAULT_MODEL_VERSION = os.getenv('MINERU_DEFAULT_MODEL_VERSION', 'vlm')
MINERU_DEFAULT_WAIT = os.getenv('MINERU_DEFAULT_WAIT', 'False').lower() == 'true'

# mineru_service.py
@staticmethod
def get_default_params() -> Dict[str, Any]:
    from config.config import current_config
    return {
        'model_version': current_config.MINERU_DEFAULT_MODEL_VERSION,
        'wait': current_config.MINERU_DEFAULT_WAIT,
        # ...
    }
```

## 总结

✅ **统一设计**：所有调用都使用同一个服务类
✅ **统一参数**：默认参数统一管理
✅ **灵活配置**：API调用时可以覆盖默认值
✅ **易于维护**：逻辑集中，代码复用

这样设计的好处是：
- 不需要分开维护两套逻辑
- 参数统一，不会出现不一致
- 代码更简洁，易于理解





