# 格式检测文件存储更新说明

## 更新日期
2025-11-04

## 更新内容

将论文格式检测功能的临时文件和报告文件统一存储到 `uploads/format_check/` 目录下的子目录中。

## 新目录结构

```
dhu-journal-app/
└── backend/
    └── uploads/
        └── format_check/
            ├── temp/              # 临时文件（检测时使用）
            │   └── 20251104_143022_example.docx
            └── reports/           # 检测报告
                └── format_report_20251104_143055.txt
```

## 主要变更

### 1. 后端配置 (app.py)

**新增配置项：**
```python
FORMAT_CHECK_TEMP_FOLDER = 'uploads/format_check/temp'
FORMAT_CHECK_REPORTS_FOLDER = 'uploads/format_check/reports'
```

**自动创建目录：**
应用启动时自动创建所需目录，无需手动操作。

### 2. API端点调整

#### 修改的端点：
- `POST /api/paper-format/check/<module_name>` - 临时文件存储到temp目录
- `POST /api/paper-format/check-all` - 临时文件存储到temp目录
- `POST /api/paper-format/generate-report` - 报告存储到reports目录

#### 新增端点：
- `GET /api/paper-format/download-report/<filename>` - 下载检测报告
- `POST /api/paper-format/cleanup-temp` - 清理临时文件

### 3. 文件管理策略

**临时文件 (temp/):**
- 检测完成后立即删除
- 如有遗留，可通过API手动清理超过24小时的文件

**报告文件 (reports/):**
- 长期保存，供用户随时下载
- 建议定期清理旧报告（如保留30天）

## 使用示例

### 清理临时文件

```bash
curl -X POST http://localhost:5000/api/paper-format/cleanup-temp \
  -H "Content-Type: application/json" \
  -d '{"hours": 24}'
```

响应：
```json
{
  "success": true,
  "message": "成功清理 3 个临时文件",
  "data": {
    "deleted_count": 3
  }
}
```

### 下载报告

```bash
curl -O http://localhost:5000/api/paper-format/download-report/format_report_20251104_143055.txt
```

## 兼容性说明

- **向后兼容**: 原有API接口保持不变，只是底层存储位置改变
- **前端无需修改**: 前端代码无需任何调整
- **数据迁移**: 无需数据迁移，新文件自动使用新目录

## 维护建议

### 1. 定时清理任务 (Linux)

创建cron任务，每天清理临时文件：

```bash
# 编辑crontab
crontab -e

# 添加以下行（每天凌晨2点执行）
0 2 * * * curl -X POST http://localhost:5000/api/paper-format/cleanup-temp -H "Content-Type: application/json" -d '{"hours": 24}'
```

### 2. 监控磁盘空间

```bash
# 查看uploads目录大小
du -sh uploads/format_check/*

# 输出示例：
# 125M    uploads/format_check/temp
# 2.3G    uploads/format_check/reports
```

### 3. 报告归档

如果reports目录过大，可定期归档旧报告：

```bash
# 归档30天前的报告
find uploads/format_check/reports -name "*.txt" -mtime +30 -exec mv {} archives/ \;
```

## 安全注意事项

1. **文件权限**: 确保Web服务器对uploads目录有读写权限
2. **文件名安全**: 所有文件名都经过 `secure_filename()` 处理
3. **路径遍历防护**: 下载API使用 `secure_filename()` 防止路径遍历攻击
4. **定期清理**: 避免磁盘空间被临时文件耗尽

## 故障排除

### 问题1: 目录创建失败

**症状**: 应用启动时报错 "Permission denied"

**解决方案**:
```bash
# 赋予uploads目录写权限
chmod 755 backend/uploads
# 或者
sudo chown -R www-data:www-data backend/uploads
```

### 问题2: 临时文件未被删除

**原因**: 检测过程中异常退出

**解决方案**:
```bash
# 手动调用清理API
curl -X POST http://localhost:5000/api/paper-format/cleanup-temp
```

### 问题3: 报告下载失败

**检查**:
1. 确认文件存在于 `uploads/format_check/reports/` 目录
2. 检查文件名是否正确
3. 查看服务器日志

## 相关文档

- [论文格式检测重构文档](./PAPER_FORMAT_REDESIGN.md)
- [uploads目录说明](./backend/uploads/README.md)
- [.gitignore配置](./.gitignore)

## 联系方式

如有问题，请查看项目文档或联系开发团队。

