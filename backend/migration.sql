-- 为papers表添加中文标题和中文作者字段
-- 执行这些SQL语句来添加新字段

-- 添加中文标题字段
ALTER TABLE papers ADD COLUMN chinese_title TEXT;

-- 添加中文作者字段  
ALTER TABLE papers ADD COLUMN chinese_authors TEXT;

-- 验证字段是否添加成功
PRAGMA table_info(papers);













