# 论文格式检测功能集成说明

## 概述

已成功将 Paper_detect 项目的论文格式检测功能集成到 dhu-journal-app 项目中。

## 集成内容

### 后端集成

1. **服务类**: `backend/services/paper_format_service.py`
   - 封装了所有论文格式检测功能
   - 支持7个检测模块：Title、Abstract、Keywords、Content、Figure、Formula、Table
   - 提供统一的API响应格式

2. **API路由**: 在 `backend/app.py` 中添加了以下API端点
   - `GET /api/paper-format/modules` - 获取可用的检测模块列表
   - `POST /api/paper-format/check/<module_name>` - 检测单个模块
   - `POST /api/paper-format/check-all` - 执行全量检测
   - `POST /api/paper-format/generate-report` - 生成检测报告

### 前端集成

1. **API服务**: `front/dhu-Journal-app/src/api/paperFormatService.ts`
   - 提供类型安全的API调用接口
   - 完整的TypeScript类型定义

2. **视图组件**: `front/dhu-Journal-app/src/views/PaperFormatCheckView.vue`
   - 文件上传功能
   - 检测模块选择
   - 实时检测进度
   - 检测结果展示
   - 报告生成和下载

3. **路由配置**: 添加了 `/paper-format-check` 路由

4. **导航菜单**: 在侧边栏添加了"论文格式检测"菜单项

## 使用方法

### 启动项目

#### 后端

```bash
cd dhu-journal-app/backend
python app.py
```

确保后端服务在 `http://localhost:5000` 运行。

#### 前端

```bash
cd dhu-journal-app/front/dhu-Journal-app
npm install  # 首次运行需要安装依赖
npm run dev
```

前端服务通常在 `http://localhost:5173` 运行。

### 使用论文格式检测功能

1. **访问页面**
   - 在浏览器中打开前端地址
   - 点击左侧导航栏的"论文格式检测"

2. **上传文件**
   - 点击"选择文件"按钮
   - 选择 `.docx` 格式的论文文件

3. **配置检测选项**
   - 选择"全量检测"或选择特定模块
   - 可选：启用图片内容API检测（需要较长时间）

4. **执行检测**
   - 点击"开始检测"按钮
   - 等待检测完成（显示进度条）

5. **查看结果**
   - 查看总体统计（通过率、失败项等）
   - 查看各模块详细检测结果
   - 查看具体问题和建议

6. **生成报告**
   - 点击"生成报告"按钮
   - 查看报告预览
   - 点击"下载报告"保存txt格式报告

## 依赖关系

### 重要说明

该功能依赖于 Paper_detect 项目，确保：

1. **项目位置**: Paper_detect 项目与 dhu-journal-app 项目在同一父目录下
   ```
   C:\Users\31943\Desktop\pro\
   ├── Paper_detect/
   │   ├── paper_detect/
   │   ├── templates/
   │   └── ...
   └── dhu-journal-app/
       ├── backend/
       ├── front/
       └── ...
   ```

2. **模板文件**: Paper_detect/templates 目录必须包含以下JSON模板文件：
   - Title.json
   - Abstract.json
   - Keywords.json
   - Content.json
   - Figure.json
   - Formula.json
   - Table.json

3. **Python依赖**: 确保安装了 Paper_detect 所需的依赖
   ```bash
   pip install python-docx
   # 如果使用标题大小写检测，还需要安装 spacy
   pip install spacy
   python -m spacy download en_core_web_sm
   ```

## API文档

### 1. 获取检测模块列表

**请求**:
```http
GET /api/paper-format/modules
```

**响应**:
```json
{
  "success": true,
  "data": {
    "modules": [
      {
        "exists": true,
        "module_name": "Title",
        "default_template": "Title.json",
        "description": "标题、作者、单位格式检测"
      },
      ...
    ],
    "total": 7
  }
}
```

### 2. 执行全量检测

**请求**:
```http
POST /api/paper-format/check-all
Content-Type: multipart/form-data

file: [docx文件]
enableFigureApi: false (可选)
modules: Title,Abstract,Keywords (可选，逗号分隔)
```

**响应**:
```json
{
  "success": true,
  "data": {
    "results": {
      "Title": {
        "module": "Title",
        "checks": {
          "title": {
            "ok": true,
            "messages": ["标题检查通过"]
          },
          ...
        },
        "summary": ["所有检查通过"]
      },
      ...
    },
    "summary": {
      "total_checks": 50,
      "passed_checks": 45,
      "failed_checks": 5,
      "pass_rate": 90.0
    }
  },
  "message": "全量检测完成，通过率: 90.0%"
}
```

### 3. 生成报告

**请求**:
```http
POST /api/paper-format/generate-report
Content-Type: application/json

{
  "checkResults": {检测结果数据}
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "report_text": "报告文本内容...",
    "download_url": "/api/download/format_report_20251103_120000.txt"
  },
  "message": "报告生成成功"
}
```

## 故障排查

### 常见问题

1. **模块导入错误**
   ```
   ModuleNotFoundError: No module named 'paper_detect'
   ```
   
   **解决方案**: 
   - 确认 Paper_detect 项目路径是否正确
   - 检查 `paper_format_service.py` 中的路径配置

2. **模板文件未找到**
   ```
   FileNotFoundError: 模板文件不存在
   ```
   
   **解决方案**:
   - 确认 Paper_detect/templates 目录存在
   - 确认所有JSON模板文件都存在

3. **文件上传失败**
   ```
   只支持 .docx 格式的文件
   ```
   
   **解决方案**:
   - 确保上传的是 .docx 格式文件（不是 .doc）
   - 检查文件是否损坏

4. **前端API调用失败**
   ```
   Network Error or CORS Error
   ```
   
   **解决方案**:
   - 确认后端服务是否正常运行
   - 检查前端API baseURL配置
   - 确认CORS配置是否正确

## 功能特性

### 检测模块说明

1. **Title (标题检测)**
   - 标题格式：芝加哥格式大小写规则
   - 作者格式：姓氏全大写，名首字母大写
   - 单位格式：编号一致性检查

2. **Abstract (摘要检测)**
   - 结构检查：Abstract: 冒号格式
   - 格式检查：字体、字号、行距、对齐方式
   - 长度检查：内容长度范围验证

3. **Keywords (关键词检测)**
   - 关键词数量检查
   - 格式检查：分隔符、大小写
   - CLC分类号检查

4. **Content (正文检测)**
   - 标题层级结构检查
   - 段落格式检查：字体、缩进、对齐
   - 标题大小写检查

5. **Figure (图片检测)**
   - 图片标题格式
   - 图片编号连续性
   - 图片对齐方式
   - 可选：图表内容API检测

6. **Formula (公式检测)**
   - 公式编号格式
   - 公式对齐方式

7. **Table (表格检测)**
   - 表格标题格式
   - 表格编号连续性
   - 表格样式和对齐

### 检测结果说明

- **✓ 通过**: 该检查项符合规范
- **✗ 失败**: 该检查项不符合规范，会显示具体问题

### 报告功能

- **文本报告**: 生成详细的txt格式报告
- **在线预览**: 直接在浏览器中查看报告内容
- **下载保存**: 支持下载报告文件到本地

## 技术架构

### 后端

- **框架**: Flask
- **服务层**: 面向对象封装
- **检测引擎**: Paper_detect 模块
- **文件处理**: python-docx

### 前端

- **框架**: Vue 3 + TypeScript
- **UI组件**: Element Plus
- **路由**: Vue Router
- **HTTP客户端**: Axios

## 未来改进

### 计划功能

1. **批注功能**: 在文档中添加批注标记问题位置
2. **批量检测**: 支持同时检测多个文件
3. **检测模板管理**: 允许自定义检测规则
4. **历史记录**: 保存检测历史和结果对比
5. **异步检测**: 对大文件支持后台异步检测
6. **通知功能**: 检测完成后邮件或消息通知

### 性能优化

1. **结果缓存**: 缓存检测结果避免重复检测
2. **增量检测**: 只检测文档修改的部分
3. **并发处理**: 支持多个检测任务并行

## 维护说明

### 更新检测规则

修改 Paper_detect/templates 目录下的JSON文件即可更新检测规则，无需修改代码。

### 添加新模块

1. 在 Paper_detect 项目中添加新的检测模块
2. 在 `paper_format_service.py` 的 `DETECTION_MODULES` 中注册
3. 添加对应的检测方法
4. 更新前端界面

## 联系支持

如有问题或建议，请联系开发团队。

---

**版本**: 1.0.0  
**更新日期**: 2025-11-03  
**集成完成**: ✅

