# 本地数据库设置指南

## 方法1：使用SQLite数据库（推荐用于本地测试）

### 配置说明
项目已经配置为默认使用SQLite数据库进行本地测试。SQLite数据库文件将自动创建在项目根目录下。

### 使用方法
1. **无需额外安装**：SQLite已经包含在Python标准库中
2. **自动创建**：启动应用时会自动创建数据库文件 `journal.db`
3. **数据持久化**：所有数据将保存在本地文件中

### 启动应用
```bash
cd dhu-Journal-app/backend
python app.py
```

## 方法2：使用本地MySQL数据库

### 安装MySQL
1. 下载并安装MySQL Community Server
2. 启动MySQL服务
3. 创建数据库：
```sql
CREATE DATABASE journal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 配置环境变量
修改 `.env` 文件：
```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=journal
```

## 方法3：从远程数据库同步结构

### 导出远程数据库结构
```bash
# 导出结构（不包含数据）
mysqldump -h 192.168.1.3 -u username -p --no-data journal > journal_structure.sql

# 导出结构（包含数据）
mysqldump -h 192.168.1.3 -u username -p journal > journal_full.sql
```

### 导入到本地数据库
```bash
# 导入到本地MySQL
mysql -u root -p journal < journal_structure.sql

# 或者导入到SQLite（需要转换工具）
```

## 方法4：使用Docker创建本地MySQL

### 启动MySQL容器
```bash
docker run --name mysql-local -e MYSQL_ROOT_PASSWORD=password -e MYSQL_DATABASE=journal -p 3306:3306 -d mysql:8.0
```

### 配置环境变量
```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=password
DB_NAME=journal
```

## 数据库迁移说明

### 自动创建表结构
应用启动时会自动创建所有需要的表结构：
- users (用户表)
- journals (期刊表) 
- papers (论文表)
- file_uploads (文件上传表)
- paper_authors (论文作者关联表)
- authors (作者表)

### 默认数据
系统会自动创建默认管理员用户：
- 用户名：admin
- 密码：admin123

## 切换数据库类型

### 从SQLite切换到MySQL
1. 安装并启动MySQL服务
2. 创建数据库 `journal`
3. 修改 `.env` 文件中的 `DB_TYPE=mysql`
4. 重启应用

### 从MySQL切换到SQLite
1. 修改 `.env` 文件中的 `DB_TYPE=sqlite`
2. 重启应用
3. 数据将自动迁移到SQLite数据库

## 注意事项

1. **数据备份**：定期备份SQLite数据库文件 `journal.db`
2. **开发环境**：建议使用SQLite进行开发测试
3. **生产环境**：建议使用MySQL或PostgreSQL
4. **数据一致性**：确保本地和远程数据库结构保持一致

## 故障排除

### SQLite常见问题
- **权限问题**：确保应用有写入权限
- **文件锁定**：重启应用释放文件锁

### MySQL常见问题
- **连接失败**：检查MySQL服务是否启动
- **权限问题**：确保用户有数据库访问权限
- **字符集问题**：确保使用utf8mb4字符集

### 通用问题
- **表不存在**：重启应用重新创建表结构
- **数据丢失**：检查数据库连接配置
