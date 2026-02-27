# MySQL 常用命令速查

## 连接与基本操作

```sql
-- 连接数据库
mysql -u root -p
mysql -h 127.0.0.1 -P 3306 -u root -p database_name

-- 查看数据库/表
SHOW DATABASES;
USE database_name;
SHOW TABLES;
DESC table_name;              -- 查看表结构
SHOW CREATE TABLE table_name; -- 查看建表语句
SHOW TABLE STATUS LIKE 'table_name'\G

-- 查看当前连接信息
SELECT USER(), DATABASE(), VERSION();
SHOW PROCESSLIST;             -- 查看所有连接
KILL connection_id;           -- 杀死连接
```

## DDL（数据定义）

```sql
-- 数据库
CREATE DATABASE db_name DEFAULT CHARSET utf8mb4;
DROP DATABASE db_name;
ALTER DATABASE db_name DEFAULT CHARSET utf8mb4;

-- 建表
CREATE TABLE users (
    id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name      VARCHAR(64)  NOT NULL DEFAULT '',
    email     VARCHAR(128) NOT NULL,
    status    TINYINT      NOT NULL DEFAULT 1,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    UNIQUE KEY uk_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 改表
ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0 AFTER name;
ALTER TABLE users DROP COLUMN age;
ALTER TABLE users MODIFY COLUMN name VARCHAR(128) NOT NULL;
ALTER TABLE users CHANGE COLUMN name username VARCHAR(128) NOT NULL;
ALTER TABLE users RENAME TO members;

-- 索引
CREATE INDEX idx_name ON users(name);
CREATE UNIQUE INDEX uk_email ON users(email);
ALTER TABLE users ADD INDEX idx_status_created(status, created_at);
DROP INDEX idx_name ON users;
SHOW INDEX FROM users;
```

## DML（数据操作）

```sql
-- 插入
INSERT INTO users (name, email) VALUES ('alice', 'a@x.com');
INSERT INTO users (name, email) VALUES ('bob', 'b@x.com'), ('carol', 'c@x.com');
INSERT INTO users (name, email) SELECT name, email FROM old_users;
INSERT INTO users (name, email) VALUES ('alice', 'a@x.com')
  ON DUPLICATE KEY UPDATE email = VALUES(email);
REPLACE INTO users (id, name, email) VALUES (1, 'alice', 'new@x.com');

-- 更新
UPDATE users SET status = 0 WHERE id = 1;
UPDATE users SET status = 0 WHERE created_at < '2024-01-01' LIMIT 1000;

-- 删除
DELETE FROM users WHERE id = 1;
DELETE FROM users WHERE status = 0 LIMIT 1000;
TRUNCATE TABLE users;  -- 清空表（DDL 操作，不可回滚）
```

## 查询

```sql
-- 基本查询
SELECT * FROM users WHERE id = 1;
SELECT name, email FROM users WHERE status = 1 ORDER BY created_at DESC LIMIT 10;
SELECT status, COUNT(*) AS cnt FROM users GROUP BY status HAVING cnt > 10;

-- 连接
SELECT u.name, o.amount
FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.created_at > '2024-01-01';

SELECT u.name, o.amount
FROM users u
LEFT JOIN orders o ON u.id = o.user_id;

-- 子查询
SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE amount > 100);
SELECT * FROM users WHERE EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id);

-- 分页
SELECT * FROM users ORDER BY id LIMIT 10 OFFSET 20;        -- 偏移量分页（大偏移慢）
SELECT * FROM users WHERE id > 1000 ORDER BY id LIMIT 10;   -- 游标分页（推荐）

-- UNION
SELECT name FROM users UNION ALL SELECT name FROM admins;   -- 保留重复
SELECT name FROM users UNION SELECT name FROM admins;       -- 去重
```

## 事务

```sql
-- 显式事务
BEGIN;                       -- 或 START TRANSACTION
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- 回滚
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
ROLLBACK;

-- 保存点
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
SAVEPOINT sp1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
ROLLBACK TO sp1;  -- 只回滚到 sp1，id=1 的修改保留
COMMIT;

-- 隔离级别
SELECT @@transaction_isolation;                             -- 查看当前隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;    -- MySQL 默认
```

## 锁

```sql
-- 锁定读
SELECT * FROM users WHERE id = 1 FOR UPDATE;            -- 加 X 锁
SELECT * FROM users WHERE id = 1 FOR SHARE;             -- 加 S 锁（8.0+）
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;    -- 加 S 锁（兼容写法）

-- 查看锁等待
SELECT * FROM information_schema.INNODB_LOCKS;
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
-- 8.0+
SELECT * FROM performance_schema.data_locks;
SELECT * FROM performance_schema.data_lock_waits;

-- 死锁信息
SHOW ENGINE INNODB STATUS\G

-- 表锁
LOCK TABLES users READ;
LOCK TABLES users WRITE;
UNLOCK TABLES;
```

## EXPLAIN 与性能分析

```sql
-- EXPLAIN
EXPLAIN SELECT * FROM users WHERE name = 'alice';
EXPLAIN FORMAT=JSON SELECT * FROM users WHERE name = 'alice';

-- 慢查询
SHOW VARIABLES LIKE 'slow_query%';
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;

-- 查看状态
SHOW STATUS LIKE 'Handler%';      -- 行操作统计
SHOW STATUS LIKE 'Innodb_rows%';  -- InnoDB 行操作统计
SHOW VARIABLES LIKE 'innodb%';    -- InnoDB 配置

-- profiling
SET profiling = 1;
SELECT * FROM users WHERE id = 1;
SHOW PROFILES;
SHOW PROFILE FOR QUERY 1;
```

## 用户与权限

```sql
-- 创建用户
CREATE USER 'app'@'%' IDENTIFIED BY 'password';
CREATE USER 'app'@'192.168.1.%' IDENTIFIED BY 'password';

-- 授权
GRANT SELECT, INSERT, UPDATE ON db_name.* TO 'app'@'%';
GRANT ALL PRIVILEGES ON db_name.* TO 'app'@'%';
FLUSH PRIVILEGES;

-- 查看权限
SHOW GRANTS FOR 'app'@'%';

-- 撤销权限
REVOKE INSERT ON db_name.* FROM 'app'@'%';

-- 修改密码
ALTER USER 'app'@'%' IDENTIFIED BY 'new_password';

-- 删除用户
DROP USER 'app'@'%';
```

## 备份与恢复

```sql
-- mysqldump（逻辑备份）
mysqldump -u root -p db_name > backup.sql
mysqldump -u root -p --all-databases > all_backup.sql
mysqldump -u root -p db_name table1 table2 > tables_backup.sql
mysqldump -u root -p --single-transaction db_name > backup.sql  -- InnoDB 一致性备份

-- 恢复
mysql -u root -p db_name < backup.sql
```

## 常用系统变量与状态

| 变量 | 说明 | 查看命令 |
|------|------|----------|
| `innodb_buffer_pool_size` | Buffer Pool 大小 | `SHOW VARIABLES LIKE 'innodb_buffer_pool_size'` |
| `innodb_flush_log_at_trx_commit` | redo 刷盘策略（0/1/2） | `SHOW VARIABLES LIKE 'innodb_flush%'` |
| `innodb_log_file_size` | redo 日志文件大小 | `SHOW VARIABLES LIKE 'innodb_log%'` |
| `max_connections` | 最大连接数 | `SHOW VARIABLES LIKE 'max_connections'` |
| `innodb_lock_wait_timeout` | 锁等待超时（秒） | `SHOW VARIABLES LIKE 'innodb_lock%'` |
| `transaction_isolation` | 事务隔离级别 | `SELECT @@transaction_isolation` |
| `autocommit` | 自动提交 | `SELECT @@autocommit` |
| `innodb_autoinc_lock_mode` | 自增锁模式（0/1/2） | `SHOW VARIABLES LIKE 'innodb_autoinc%'` |
