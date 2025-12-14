# MinerU API 使用说明

## 配置

在项目根目录创建或编辑 `.env` 文件，添加以下配置：

```env
# MinerU API配置
MINERU_TOKEN=your_token_here  # 从MinerU官网申请的API Token
MINERU_ENABLED=True  # 是否启用MinerU服务
USE_MINERU=False  # 是否在文件上传时自动使用MinerU（False则手动调用）
MINERU_OUTPUT_DIR=mineru_output  # MinerU结果输出目录（可选，默认mineru_output）
```

## 使用方式

### 方式1：自动集成（文件上传时自动调用）

1. 在 `.env` 中设置 `USE_MINERU=True`
2. 上传PDF文件时，系统会自动提交MinerU任务（异步，不等待完成）
3. 通过API查询任务状态和结果

### 方式2：手动调用API

#### 2.1 处理文件（同步，等待完成）

```bash
POST /api/mineru/process
Content-Type: application/json

{
  "file_path": "./uploads/paper.pdf",
  "data_id": "paper_001",  # 可选
  "wait": true  # 是否等待完成，默认true
}
```

响应：
```json
{
  "success": true,
  "data": {
    "batch_id": "...",
    "markdown_path": "...",
    "json_path": "...",
    "parsed_data": {
      "title": "...",
      "authors": "...",
      "doi": "...",
      ...
    }
  }
}
```

#### 2.2 处理文件（异步，不等待）

```bash
POST /api/mineru/process
Content-Type: application/json

{
  "file_path": "./uploads/paper.pdf",
  "wait": false
}
```

响应：
```json
{
  "success": true,
  "data": {
    "batch_id": "xxx-xxx-xxx",
    "message": "文件已上传，系统将自动提交解析任务"
  }
}
```

#### 2.3 查询任务状态

```bash
GET /api/mineru/status/{batch_id}
```

响应：
```json
{
  "success": true,
  "data": [
    {
      "file_name": "paper.pdf",
      "state": "done",  # done, pending, running, failed, converting
      "full_zip_url": "https://...",
      "extract_progress": {
        "extracted_pages": 10,
        "total_pages": 10,
        "start_time": "2025-01-20 11:43:20"
      }
    }
  ]
}
```

#### 2.4 下载解析结果

```bash
POST /api/mineru/download/{batch_id}
```

响应：
```json
{
  "success": true,
  "data": {
    "markdown_path": "...",
    "json_path": "...",
    "docx_path": "...",
    "html_path": "...",
    "extract_dir": "..."
  }
}
```

#### 2.5 解析结果并提取论文信息

```bash
POST /api/mineru/parse/{batch_id}
```

响应：
```json
{
  "success": true,
  "data": {
    "title": "论文标题",
    "authors": "作者1, 作者2",
    "doi": "10.xxx/xxx",
    "issue": "2024, 42(5)",
    "abstract": "摘要内容",
    "keywords": "关键词1, 关键词2",
    "full_text": "完整文本内容"
  }
}
```

## Python代码示例

### 示例1：同步处理文件

```python
from services.mineru_service import MinerUService

mineru_service = MinerUService()

# 处理文件（等待完成）
result = mineru_service.process_local_file(
    file_path="./uploads/paper.pdf",
    data_id="paper_001",
    wait=True,  # 等待完成
    model_version="vlm",
    language="ch",
    enable_formula=True,
    enable_table=True
)

if result['success']:
    # 解析Markdown结果
    if result.get('markdown_path'):
        parsed_data = mineru_service.parse_markdown_result(result['markdown_path'])
        print(f"标题: {parsed_data.get('title')}")
        print(f"作者: {parsed_data.get('authors')}")
        print(f"DOI: {parsed_data.get('doi')}")
```

### 示例2：异步处理文件

```python
from services.mineru_service import MinerUService
import time

mineru_service = MinerUService()

# 提交任务（不等待）
result = mineru_service.process_local_file(
    file_path="./uploads/paper.pdf",
    wait=False  # 不等待
)

batch_id = result['batch_id']

# 稍后查询结果
while True:
    status_result = mineru_service.get_batch_results(batch_id)
    if status_result['success']:
        results = status_result['results']
        if results:
            state = results[0].get('state')
            if state == 'done':
                # 下载并解析
                zip_url = results[0].get('full_zip_url')
                extract_result = mineru_service.download_and_extract(zip_url, batch_id)
                break
            elif state == 'failed':
                print(f"解析失败: {results[0].get('err_msg')}")
                break
    
    time.sleep(5)  # 等待5秒后再次查询
```

## 注意事项

1. **Token配置**：确保在 `.env` 文件中正确配置 `MINERU_TOKEN`
2. **文件大小限制**：单个文件不超过200MB，页数不超过600页
3. **异步处理**：大文件解析耗时较长，建议使用异步方式
4. **结果存储**：解析结果会保存在 `mineru_output` 目录下
5. **格式选择**：默认会生成Markdown和JSON，可以通过 `extra_formats` 参数添加docx、html等格式

## 错误处理

常见错误码：
- `A0202`: Token错误
- `A0211`: Token过期
- `-60005`: 文件大小超出限制
- `-60006`: 文件页数超过限制

如果遇到错误，检查：
1. Token是否正确配置
2. 文件是否符合要求（大小、页数、格式）
3. 网络连接是否正常





