# 数据库配置说明

## 配置系统概述

本项目现在使用配置文件来管理数据库连接，取代了之前的硬编码方式。配置系统支持环境变量和配置文件两种方式。

## 配置文件结构

### 1. config.py
主配置文件，定义了配置类和环境配置映射：
- `Config`: 基础配置类
- `DevelopmentConfig`: 开发环境配置
- `ProductionConfig`: 生产环境配置
- `TestingConfig`: 测试环境配置

### 2. .env
环境变量配置文件（不提交到版本控制）
- 包含敏感信息如数据库密码
- 根据实际环境修改

### 3. .env.example
环境变量配置示例文件
- 提供配置模板
- 提交到版本控制

## 配置优先级

1. 环境变量（最高优先级）
2. .env 文件
3. config.py 中的默认值（最低优先级）

## 使用方法

### 1. 开发环境
```bash
# 确保 .env 文件存在并配置正确
cp .env.example .env
# 编辑 .env 文件，修改数据库连接信息

# 运行应用
python app.py
```

### 2. 生产环境
```bash
# 设置环境变量
export FLASK_ENV=production
export DB_HOST=your-production-host
export DB_PORT=3306
export DB_USER=your-production-user
export DB_PASSWORD=your-production-password
export DB_NAME=your-production-database

# 运行应用
python app.py
```

### 3. 使用系统环境变量
```bash
# 直接在系统环境变量中设置
set DB_HOST=localhost
set DB_USER=root
set DB_PASSWORD=your-password

# 或者使用命令行
DB_HOST=localhost DB_USER=root DB_PASSWORD=your-password python app.py
```

## 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| DB_HOST | 数据库主机地址 | localhost |
| DB_PORT | 数据库端口 | 3306 |
| DB_USER | 数据库用户名 | root |
| DB_PASSWORD | 数据库密码 | zs156987 |
| DB_NAME | 数据库名称 | journal |
| FLASK_ENV | Flask环境 | development |
| DEBUG | 调试模式 | True |
| SECRET_KEY | Flask密钥 | your-secret-key-here |
| JWT_SECRET_KEY | JWT密钥 | jwt-secret-string |

## 安全注意事项

1. **不要提交 .env 文件到版本控制**
2. 在生产环境中使用强密码
3. 定期更换密钥
4. 使用不同的数据库用户权限

## 故障排除

如果遇到数据库连接问题：

1. 检查 .env 文件是否存在且格式正确
2. 验证数据库服务是否运行
3. 检查网络连接和防火墙设置
4. 查看应用日志获取详细错误信息

## 迁移说明

从旧版本迁移：
1. 备份原有数据库
2. 安装新的依赖：`pip install python-dotenv`
3. 创建 .env 文件并配置数据库连接
4. 启动应用测试连接
