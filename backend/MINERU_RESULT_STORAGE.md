# MinerU 结果保存位置说明

## 结果保存位置

### 1. 配置位置

**配置文件**: `backend/config/config.py` 第47行

```python
MINERU_OUTPUT_DIR = os.getenv('MINERU_OUTPUT_DIR', 'mineru_output')
```

**环境变量**: `.env` 文件（可选）

```env
MINERU_OUTPUT_DIR=mineru_output
```

**默认值**: `mineru_output`（项目根目录下的 `mineru_output` 文件夹）

---

## 文件结构

### 目录结构

```
backend/
└── mineru_output/                    # 主输出目录（可配置）
    ├── {batch_id}.zip               # 压缩包（从MinerU下载的原始文件）
    └── {batch_id}/                   # 解压后的文件夹
        ├── *.md                     # Markdown文件
        ├── *.json                    # JSON文件
        ├── *.docx                   # Word文件（如果设置了extra_formats）
        └── *.html                   # HTML文件（如果设置了extra_formats）
```

### 实际示例

假设 `batch_id = "abc123-def456-ghi789"`，则：

```
backend/
└── mineru_output/
    ├── abc123-def456-ghi789.zip     # 压缩包
    └── abc123-def456-ghi789/        # 解压后的文件夹
        ├── paper.md                 # Markdown文件
        ├── paper.json               # JSON文件
        └── ...                      # 其他文件
```

---

## 代码中的保存逻辑

### 1. 压缩包保存位置

**代码位置**: `backend/services/mineru_service.py` 第318行

```python
zip_filename = f"{batch_id}.zip"
zip_path = os.path.join(self.output_dir, zip_filename)
# 结果: mineru_output/{batch_id}.zip
```

### 2. 解压文件保存位置

**代码位置**: `backend/services/mineru_service.py` 第332行

```python
extract_dir = os.path.join(self.output_dir, batch_id)
# 结果: mineru_output/{batch_id}/
```

### 3. 文件查找

**代码位置**: `backend/services/mineru_service.py` 第342-352行

```python
# 在解压目录中查找各种格式的文件
for root, dirs, files in os.walk(extract_dir):
    for file in files:
        if file.endswith('.md'):
            markdown_path = ...  # mineru_output/{batch_id}/xxx.md
        elif file.endswith('.json'):
            json_path = ...      # mineru_output/{batch_id}/xxx.json
```

---

## 返回结果中的路径

### API返回结果

调用 `/api/mineru/download/{batch_id}` 或 `/api/mineru/parse/{batch_id}` 后，返回：

```json
{
    "success": true,
    "data": {
        "markdown_path": "mineru_output/abc123-def456-ghi789/paper.md",
        "json_path": "mineru_output/abc123-def456-ghi789/paper.json",
        "docx_path": "mineru_output/abc123-def456-ghi789/paper.docx",
        "html_path": "mineru_output/abc123-def456-ghi789/paper.html",
        "zip_path": "mineru_output/abc123-def456-ghi789.zip",
        "extract_dir": "mineru_output/abc123-def456-ghi789"
    }
}
```

**注意**: 这些路径是**相对路径**（相对于项目根目录）

---

## 如何修改保存位置

### 方式1：修改配置文件（推荐）

**位置**: `backend/config/config.py`

```python
MINERU_OUTPUT_DIR = os.getenv('MINERU_OUTPUT_DIR', 'custom_output_dir')
```

### 方式2：通过环境变量

**位置**: `.env` 文件

```env
MINERU_OUTPUT_DIR=custom_output_dir
```

### 方式3：使用绝对路径

**位置**: `.env` 文件

```env
MINERU_OUTPUT_DIR=/path/to/your/output
```

---

## 文件说明

### 1. 压缩包文件（.zip）

- **位置**: `mineru_output/{batch_id}.zip`
- **内容**: MinerU返回的原始压缩包
- **大小**: 通常较大（包含所有解析结果）
- **用途**: 备份原始结果

### 2. Markdown文件（.md）

- **位置**: `mineru_output/{batch_id}/*.md`
- **内容**: PDF转换后的Markdown格式文本
- **用途**: 文本提取、内容分析

### 3. JSON文件（.json）

- **位置**: `mineru_output/{batch_id}/*.json`
- **内容**: 结构化的解析数据
- **用途**: 程序化处理、数据提取

### 4. Word文件（.docx）

- **位置**: `mineru_output/{batch_id}/*.docx`
- **内容**: Word格式文档（如果设置了 `extra_formats: ["docx"]`）
- **用途**: 编辑、查看

### 5. HTML文件（.html）

- **位置**: `mineru_output/{batch_id}/*.html`
- **内容**: HTML格式文档（如果设置了 `extra_formats: ["html"]`）
- **用途**: 网页查看

---

## 访问结果文件

### 方式1：通过API返回的路径

```python
# 从API返回结果中获取路径
result = mineru_service.process_local_file(...)
markdown_path = result['markdown_path']

# 读取文件
with open(markdown_path, 'r', encoding='utf-8') as f:
    content = f.read()
```

### 方式2：直接访问文件系统

```python
import os
from config.config import current_config

output_dir = current_config.MINERU_OUTPUT_DIR
batch_id = "your_batch_id"

# 构建文件路径
markdown_path = os.path.join(output_dir, batch_id, "paper.md")
```

### 方式3：通过batch_id查找

```python
import os
import glob

batch_id = "your_batch_id"
output_dir = "mineru_output"

# 查找所有markdown文件
markdown_files = glob.glob(f"{output_dir}/{batch_id}/**/*.md", recursive=True)
```

---

## 清理结果文件

### 手动清理

```bash
# 删除整个输出目录
rm -rf mineru_output/

# 删除特定batch的结果
rm -rf mineru_output/{batch_id}/
rm mineru_output/{batch_id}.zip
```

### 程序清理

```python
import os
import shutil

# 删除特定batch的结果
batch_id = "your_batch_id"
output_dir = "mineru_output"

# 删除解压目录
extract_dir = os.path.join(output_dir, batch_id)
if os.path.exists(extract_dir):
    shutil.rmtree(extract_dir)

# 删除压缩包
zip_path = os.path.join(output_dir, f"{batch_id}.zip")
if os.path.exists(zip_path):
    os.remove(zip_path)
```

---

## 注意事项

### 1. 路径是相对路径

所有返回的路径都是**相对于项目根目录**的相对路径。

### 2. 目录自动创建

如果 `mineru_output` 目录不存在，代码会自动创建。

### 3. 文件不会自动清理

结果文件会一直保存，需要手动清理或编写清理脚本。

### 4. 磁盘空间

压缩包和解压文件都会占用磁盘空间，注意定期清理。

---

## 总结

| 项目 | 位置 |
|------|------|
| **配置位置** | `config.py` 或 `.env` 文件 |
| **默认目录** | `mineru_output/` |
| **压缩包** | `mineru_output/{batch_id}.zip` |
| **解压文件** | `mineru_output/{batch_id}/` |
| **Markdown** | `mineru_output/{batch_id}/*.md` |
| **JSON** | `mineru_output/{batch_id}/*.json` |





