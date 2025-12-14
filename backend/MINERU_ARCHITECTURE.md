# MinerU API 架构说明

## 设计理念

**统一通过API接口调用，所有MinerU相关操作都走同一个入口**

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    统一入口层                            │
│  _process_file_with_mineru_internal()                    │
│  (blueprints/files.py)                                  │
│  - 参数处理                                              │
│  - 调用 MinerUService                                    │
│  - 返回统一格式的结果                                    │
└─────────────────────────────────────────────────────────┘
                        ▲
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────┴────────┐            ┌────────┴────────┐
│ 文件上传时      │            │  API接口调用    │
│ file_service   │            │  /api/mineru/   │
│                │            │  process        │
│ 调用内部函数    │            │                 │
│ (内部调用)      │            │ HTTP请求        │
└────────────────┘            └─────────────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │      MinerUService            │
        │  (services/mineru_service.py)│
        │  - 申请上传链接                │
        │  - 上传文件                    │
        │  - 查询结果                    │
        │  - 下载解压                    │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │      MinerU API               │
        │  (外部服务)                    │
        └───────────────────────────────┘
```

## 代码结构

### 1. 统一入口函数

**位置**: `backend/blueprints/files.py`

```python
def _process_file_with_mineru_internal(file_path: str, data_id: str = None, **kwargs):
    """
    MinerU处理文件的内部函数（统一入口）
    可以被API路由和文件服务调用
    """
    # 1. 参数处理
    # 2. 调用 MinerUService
    # 3. 返回结果
```

**作用**:
- ✅ 统一处理逻辑
- ✅ 统一参数处理
- ✅ 统一返回格式
- ✅ 可以被多个地方调用

### 2. API接口

**位置**: `backend/blueprints/files.py`

```python
@files_bp.route('/mineru/process', methods=['POST'])
def process_file_with_mineru():
    """使用MinerU处理文件 - API接口"""
    # 1. 从request.json获取参数
    # 2. 调用统一入口函数
    # 3. 返回JSON响应
```

**调用方式**:
```bash
POST /api/mineru/process
{
    "file_path": "./uploads/paper.pdf",
    "data_id": "paper_001",
    "wait": false
}
```

### 3. 文件上传时调用

**位置**: `backend/services/file_service.py`

```python
# 文件上传时
if current_config.USE_MINERU:
    from blueprints.files import _process_file_with_mineru_internal
    
    # 调用统一入口函数（内部调用）
    result = _process_file_with_mineru_internal(
        file_path=file_path,
        data_id=f"file_{file_upload.id}",
        wait=False
    )
```

**特点**:
- ✅ 直接调用统一入口函数（内部调用，不需要HTTP）
- ✅ 使用相同的处理逻辑
- ✅ 参数统一

### 4. 服务层

**位置**: `backend/services/mineru_service.py`

```python
class MinerUService:
    """MinerU API服务类"""
    - apply_upload_url()      # 申请上传链接
    - upload_file()            # 上传文件
    - get_batch_results()     # 查询结果
    - wait_for_completion()   # 等待完成
    - download_and_extract()  # 下载解压
    - process_local_file()    # 完整流程
```

## 调用流程

### 场景1：文件上传时

```
用户上传PDF文件
    ↓
file_service.upload_file()
    ↓
检测到PDF文件 && USE_MINERU=True
    ↓
调用 _process_file_with_mineru_internal()
    ↓
调用 MinerUService.process_local_file()
    ↓
返回 batch_id（异步处理）
```

### 场景2：API接口调用

```
HTTP POST /api/mineru/process
    ↓
process_file_with_mineru() 路由处理
    ↓
调用 _process_file_with_mineru_internal()
    ↓
调用 MinerUService.process_local_file()
    ↓
返回JSON响应
```

## 优势

### ✅ 统一入口
- 所有MinerU调用都通过 `_process_file_with_mineru_internal()`
- 逻辑集中，易于维护

### ✅ 代码复用
- 文件上传和API调用使用相同的处理逻辑
- 不需要重复代码

### ✅ 参数统一
- 参数处理逻辑统一
- 默认值统一管理

### ✅ 易于扩展
- 新增功能只需要修改统一入口函数
- 所有调用自动获得新功能

### ✅ 易于测试
- 可以单独测试统一入口函数
- 不需要模拟HTTP请求

## 文件说明

| 文件 | 作用 | 关键函数/类 |
|------|------|------------|
| `blueprints/files.py` | API路由和统一入口 | `_process_file_with_mineru_internal()`, `process_file_with_mineru()` |
| `services/file_service.py` | 文件上传服务 | 调用 `_process_file_with_mineru_internal()` |
| `services/mineru_service.py` | MinerU服务类 | `MinerUService` |
| `config/config.py` | 配置管理 | MinerU相关配置项 |

## 配置说明

在 `.env` 文件中：

```env
MINERU_TOKEN=your_token_here
MINERU_ENABLED=True
USE_MINERU=True  # 文件上传时是否自动使用MinerU
```

## 使用示例

### 示例1：文件上传时（自动调用）

```python
# 在 file_service.py 中
if current_config.USE_MINERU:
    result = _process_file_with_mineru_internal(
        file_path=file_path,
        data_id=f"file_{file_upload.id}",
        wait=False
    )
```

### 示例2：API调用

```bash
POST /api/mineru/process
Content-Type: application/json

{
    "file_path": "./uploads/paper.pdf",
    "data_id": "paper_001",
    "wait": false,
    "is_ocr": true
}
```

## 总结

**核心设计**：
- ✅ 统一入口函数 `_process_file_with_mineru_internal()`
- ✅ API路由调用统一入口函数
- ✅ 文件上传时也调用统一入口函数
- ✅ 所有逻辑都通过统一入口，不再分开设计

**好处**：
- 代码更简洁
- 逻辑更清晰
- 维护更容易
- 扩展更方便





