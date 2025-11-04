# 论文格式检测功能重构文档

## 概述

本次重构将论文格式检测功能从独立页面集成到初审系统（PreliminaryReviewView）中，实现了更加自然的审核工作流程。

## 重构时间

2025-11-04

## 文件存储结构

所有格式检测相关文件统一存储在 `uploads/format_check/` 目录下：

```
uploads/
└── format_check/
    ├── temp/              # 临时文件（检测时的文档副本）
    │   └── {timestamp}_{filename}.docx
    └── reports/           # 格式检测报告
        └── format_report_{timestamp}.txt
```

**目录说明：**
- **temp/**: 存储检测时的临时文件，检测完成后自动删除
- **reports/**: 存储生成的检测报告，供用户下载

**文件清理：**
- 临时文件在检测完成后立即删除
- 可通过API手动清理超过24小时的临时文件
- 报告文件长期保存

## 项目结构重新设计

### 后端架构

#### 1. 核心检测器 (`backend/paper_format_detector.py`)

**职责：** 封装所有Paper_detect项目的检测逻辑

**主要功能：**
- 导入和管理Paper_detect的所有检测模块
- 提供统一的检测接口
- 加载和管理JSON模板文件
- 执行单模块检测和全量检测

**核心类：** `PaperFormatDetector`

**检测模块：**
- Title（标题、作者、单位）
- Abstract（摘要）
- Keywords（关键词）
- Content（正文）
- Figure（图片）
- Formula（公式）
- Table（表格）

#### 2. 服务层 (`backend/services/paper_format_service.py`)

**职责：** 提供Web API调用的服务封装

**主要功能：**
- 调用核心检测器执行检测
- 标准化API响应格式
- 异常处理和日志记录
- 生成检测报告
- 模块信息查询

**核心类：** `PaperFormatService`

**API响应格式：**
```python
{
    'success': bool,
    'data': Any,
    'message': str,
    'status_code': int
}
```

#### 3. 模板文件 (`backend/templates/`)

从Paper_detect项目复制而来的JSON模板文件：
- Title.json
- Abstract.json
- Keywords.json
- Content.json
- Figure.json
- Formula.json
- Table.json
- Chinese.json
- paragraph_template.json

### 前端架构

#### 1. 初审系统页面重构 (`front/src/views/PreliminaryReviewView.vue`)

**主要改动：**

**新增功能：**
- 在审核对话框中集成格式检测功能
- 格式检测结果实时展示
- 检测报告生成和下载
- 检测进度可视化

**UI组件结构：**
```
审核对话框
├── 论文基本信息
├── 格式检测区域
│   ├── 检测状态提示
│   ├── 检测进度条
│   ├── 检测结果汇总
│   │   └── Descriptions（总检测项/通过项/失败项/通过率）
│   ├── 详细结果折叠面板
│   │   └── 按模块展示检测项
│   └── 操作按钮（重新检测/查看详细报告）
└── 审核表单
    ├── 审核结果（单选）
    └── 审核意见（文本域）
```

**关键功能方法：**
- `startFormatCheck()` - 启动格式检测
- `resetFormatCheck()` - 重置检测状态
- `viewDetailReport()` - 查看详细报告
- `downloadReport()` - 下载报告文件
- `getPassRateType()` - 获取通过率状态类型
- `getModuleStatus()` - 获取模块状态
- `getModuleStatusType()` - 获取模块状态类型

**界面风格统一：**
- 使用Element Plus组件库
- 主题色：#b62020ff（深红色）
- 按钮悬停色：#7a0b0b（更深的红色）
- 与现有初审系统界面风格完全统一

#### 2. API服务 (`front/src/api/paperFormatService.ts`)

**提供的服务：**
- `getModules()` - 获取所有可用检测模块
- `checkModule()` - 检测单个模块
- `checkAll()` - 执行全量检测
- `generateReport()` - 生成检测报告
- `getReportDownloadUrl()` - 获取报告下载URL

**类型定义：**
```typescript
interface CheckAllResult {
    results: Record<string, ModuleResult>
    summary: {
        total_checks: number
        passed_checks: number
        failed_checks: number
        pass_rate: number
    }
}

interface ApiResponse<T> {
    success: boolean
    data?: T
    message: string
    status_code?: number
}
```

### 路由配置

**移除：**
- `/paper-format-check` 路由（独立格式检测页面）

**保留：**
- `/preliminary-review` 路由（集成了格式检测的初审系统）

### 导航菜单

**移除：**
- "论文格式检测" 独立菜单项

**保留：**
- "初审系统" 菜单项（现在包含格式检测功能）

## 重构优势

### 1. 工作流程更自然
- 格式检测作为审核流程的一部分，无需切换页面
- 审核和格式检测结果可以一起保存
- 减少用户操作步骤

### 2. 代码结构更清晰
- 核心检测逻辑与服务层分离
- Paper_detect代码完全独立，易于维护
- 服务层只负责API封装和响应格式化

### 3. 用户体验更好
- 单个对话框完成所有审核工作
- 实时显示检测进度
- 检测结果可折叠展开，详略得当
- 界面风格统一，视觉体验一致

### 4. 维护性更强
- 模板文件独立存储在backend/templates
- 检测逻辑与Paper_detect项目同步更新
- 服务层接口稳定，前端无需频繁修改

## 使用流程

### 审核员工作流程

1. 进入"初审系统"页面
2. 在待审核列表中选择论文，点击"审核"按钮
3. 在审核对话框中查看论文基本信息
4. 点击"开始检测"按钮进行格式检测
5. 等待检测完成，查看检测结果汇总
6. 展开各模块查看详细检测项
7. 如需详细报告，点击"查看详细报告"或"下载报告"
8. 根据检测结果填写审核意见
9. 选择审核结果（已审核/需修改）
10. 点击"确定"完成审核

### 技术调用流程

```
用户操作
  ↓
PreliminaryReviewView.vue
  ↓
paperFormatService.ts (checkAll)
  ↓
backend/app.py (/api/paper-format/check-all)
  ↓
PaperFormatService.check_all()
  ↓
PaperFormatDetector.detect_all()
  ↓
Paper_detect各检测模块
  ↓
返回检测结果
  ↓
前端展示
```

## API端点

### 1. 获取可用模块
```
GET /api/paper-format/modules
Response: {
    success: true,
    data: {
        modules: [...],
        total: 7
    }
}
```

### 2. 全量检测
```
POST /api/paper-format/check-all
Request: FormData {
    file: File,
    enableFigureApi: boolean,
    modules?: string  // 逗号分隔
}
Response: {
    success: true,
    data: {
        results: {...},
        summary: {...}
    },
    message: string
}
```

### 3. 生成报告
```
POST /api/paper-format/generate-report
Request: {
    checkResults: CheckAllResult
}
Response: {
    success: true,
    data: {
        report_text: string,
        download_url: string  # 格式: /api/paper-format/download-report/{filename}
    }
}
```

### 4. 下载报告
```
GET /api/paper-format/download-report/{filename}
Response: 文件流（text/plain）
```

### 5. 清理临时文件
```
POST /api/paper-format/cleanup-temp
Request: {
    hours: number  # 可选，默认24小时
}
Response: {
    success: true,
    message: string,
    data: {
        deleted_count: number
    }
}
```

## 配置说明

### 后端配置

**文件存储目录：**
- `FORMAT_CHECK_FOLDER`: `uploads/format_check/` - 主目录
- `FORMAT_CHECK_TEMP_FOLDER`: `uploads/format_check/temp/` - 临时文件目录
- `FORMAT_CHECK_REPORTS_FOLDER`: `uploads/format_check/reports/` - 报告文件目录

**目录自动创建：**
应用启动时会自动创建这些目录，无需手动创建。

**templates目录：** `backend/templates/`
- 确保所有JSON模板文件存在
- 模板格式与Paper_detect项目保持一致

**Paper_detect项目路径：**
- 检测器会自动查找 `../Paper_detect` 目录
- 确保Paper_detect项目与dhu-journal-app项目平级

**文件清理：**
- 临时文件在检测完成后立即删除
- 可定期调用 `/api/paper-format/cleanup-temp` 清理遗留的临时文件
- 建议设置定时任务（如cron）每天清理一次

### 前端配置

**API基础路径：** 在 `front/src/api/axios.ts` 中配置
```typescript
const apiClient = axios.create({
    baseURL: '/api',
    timeout: 60000  // 格式检测可能需要较长时间
})
```

## 测试建议

### 后端测试
1. 测试各个检测模块单独调用
2. 测试全量检测功能
3. 测试报告生成功能
4. 测试异常处理（文件不存在、格式错误等）

### 前端测试
1. 测试审核对话框中的格式检测启动
2. 测试检测进度展示
3. 测试检测结果展示和折叠
4. 测试报告查看和下载
5. 测试检测结果与审核意见的关联

### 集成测试
1. 上传.docx文件并执行全量检测
2. 验证检测结果的准确性
3. 验证报告内容的完整性
4. 验证审核流程的完整性

## 已删除内容

### 前端文件
- `front/src/views/PaperFormatCheckView.vue` - 独立格式检测页面（已删除）

### 路由配置
- `/paper-format-check` 路由（已从router/index.ts移除）

### 导航菜单
- "论文格式检测" 菜单项（已从App.vue移除）

## 注意事项

1. **Paper_detect依赖：** 系统依赖Paper_detect项目，确保该项目存在且可访问
2. **模板文件：** 确保backend/templates目录包含所有必需的JSON模板文件
3. **文件上传：** 前端需要先上传文件才能进行格式检测
4. **检测时间：** 全量检测可能需要10-30秒，前端需要显示进度
5. **内存占用：** 大文件检测可能占用较多内存，建议限制文件大小
6. **并发处理：** 后端需要考虑多个用户同时检测的情况

## 未来优化建议

1. **异步任务队列：** 使用Celery等任务队列处理长时间检测
2. **结果缓存：** 对相同文件的检测结果进行缓存
3. **检测历史：** 保存历史检测记录，支持查看
4. **自定义模板：** 允许用户自定义检测模板
5. **批量检测：** 支持批量上传和检测
6. **智能建议：** 根据检测结果提供修改建议

## 版本信息

- 重构版本：v2.0
- 重构日期：2025-11-04
- 负责人：AI Assistant
- 依赖项目：Paper_detect

## 相关文档

- [Paper_detect项目文档](../Paper_detect/README.md)
- [dhu-journal-app后端API文档](./backend/README.md)
- [前端开发指南](./front/README.md)


