# 事务简介

## 事务的概念

事务（transaction）是一个或多个数据库操作的逻辑单元，这些操作要么全部成功，要么全部失败。事务必须满足 ACID 四个特性。

典型场景：转账操作包含两条 UPDATE 语句（一条扣钱、一条加钱），它们必须作为一个整体执行，不能只完成一半。

## ACID 特性

### 原子性（Atomicity）

事务中的所有操作要么全部执行成功，要么全部回滚到执行前的状态，不存在"执行了一半"的中间态。

数据库通过 undo log 实现原子性——执行过程中发生错误时，利用 undo log 把已完成的操作撤销。

### 一致性（Consistency）

事务执行前后，数据库都必须满足所有既定约束（主键、唯一索引、外键、NOT NULL 以及业务规则等）。

一致性由两方面保证：

- **数据库层面**：主键约束、唯一索引、外键、NOT NULL 等。MySQL 支持 `CHECK` 语法但**不实际执行检查**（SQL Server/Oracle 会执行）；可用触发器自定义约束。
- **应用层面**：复杂业务规则（如余额不能为负）需要程序员在代码中保证。

原子性和隔离性是保证一致性的**手段**，一致性是最终**结果**。满足原子性和隔离性不一定满足一致性（如余额变负），反之亦然。

### 隔离性（Isolation）

并发执行的多个事务之间互不干扰。若不做隔离控制，并发事务的操作可能交叉执行，导致数据不一致（如两次转账只扣了一次钱却加了两次钱）。

数据库通过锁机制和 MVCC 来保证不同隔离级别下的隔离性。

### 持久性（Durability）

事务一旦提交，其对数据库的修改就永久保存到磁盘上，即使之后系统崩溃也不会丢失。

数据库通过 redo log 实现持久性——数据修改先写 redo log，确保崩溃后可重做。

## 事务的状态

事务从开始到结束经历以下状态：

| 状态 | 含义 |
|------|------|
| **活动的**（active） | 事务正在执行中 |
| **部分提交的**（partially committed） | 最后一个操作执行完成，但修改还在内存中，尚未刷盘 |
| **失败的**（failed） | 在 active 或 partially committed 阶段遇到错误，无法继续执行 |
| **中止的**（aborted） | 失败事务完成回滚，数据库恢复到事务执行前的状态 |
| **提交的**（committed） | 部分提交的事务成功将修改刷到磁盘，事务完成 |

状态转换路径：

```
active → partially committed → committed
  ↓              ↓
failed    →    failed    →    aborted
```

事务生命周期在 **committed** 或 **aborted** 状态结束。

## MySQL 中的事务用法

MySQL 中只有 **InnoDB**（和 NDB）支持事务。MyISAM 不支持事务，ROLLBACK 对其无效。

### 开启事务（BEGIN / START TRANSACTION）

```sql
-- 方式一
BEGIN;

-- 方式二（支持修饰符）
START TRANSACTION;
START TRANSACTION READ ONLY;               -- 只读事务
START TRANSACTION READ WRITE;              -- 读写事务（默认）
START TRANSACTION WITH CONSISTENT SNAPSHOT; -- 一致性读
START TRANSACTION READ ONLY, WITH CONSISTENT SNAPSHOT; -- 可组合
```

`READ ONLY` 和 `READ WRITE` 不能同时使用。只读事务仍可操作临时表。

### 提交与回滚

```sql
COMMIT;    -- 提交事务
ROLLBACK;  -- 回滚事务，撤销所有修改
```

执行过程中遇到错误时，事务会自动回滚。手动发现问题也可主动 ROLLBACK。

### 保存点（SAVEPOINT）

保存点允许回滚到事务中的某个中间位置，而非回到起点。

```sql
SAVEPOINT s1;                -- 创建保存点
ROLLBACK TO s1;              -- 回滚到保存点 s1（s1 之后的操作撤销）
RELEASE SAVEPOINT s1;        -- 删除保存点
```

不带保存点名称的 `ROLLBACK` 回滚整个事务。

### autocommit

```sql
SHOW VARIABLES LIKE 'autocommit';  -- 默认 ON
```

autocommit = ON 时，每条语句自动作为独立事务提交。关闭自动提交的方式：

1. 用 `BEGIN` / `START TRANSACTION` 显式开启事务（提交/回滚后恢复自动提交）
2. `SET autocommit = OFF;`（后续语句属于同一事务，直到显式 COMMIT 或 ROLLBACK）

### 隐式提交

某些语句会自动提交当前未完成的事务：

- **DDL 语句**：`CREATE` / `ALTER` / `DROP` 表、视图、存储过程等
- **用户管理**：`CREATE USER` / `ALTER USER` / `GRANT` / `REVOKE` 等
- **事务控制**：未提交时再次 `BEGIN`，或将 autocommit 从 OFF 改为 ON
- **锁语句**：`LOCK TABLES` / `UNLOCK TABLES`
- **数据加载**：`LOAD DATA`
- **复制命令**：`START SLAVE` / `STOP SLAVE` 等
- **维护语句**：`ANALYZE TABLE` / `OPTIMIZE TABLE` / `CHECK TABLE` 等
