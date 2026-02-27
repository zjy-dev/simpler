# 事务隔离级别与 MVCC

## 并发事务的问题

多个事务并发访问相同数据时，如果不加控制，可能产生以下四类问题（按严重程度排序）：

### 脏写（Dirty Write）

一个事务修改了另一个**未提交事务**修改过的数据。

事务 B 更新了某行，事务 A 又更新了同一行。如果事务 B 回滚，事务 A 的更新也一起消失。**脏写是最严重的问题，任何隔离级别都不允许发生**。InnoDB 通过锁机制保证：第一个事务更新记录后加锁，第二个事务必须等锁释放才能更新。

### 脏读（Dirty Read）

一个事务读到了另一个**未提交事务**修改过的数据。

事务 B 把 name 改成 `'关羽'`，事务 A 读到了 `'关羽'`，随后事务 B 回滚——事务 A 读到的数据实际上从未存在过。

### 不可重复读（Non-Repeatable Read）

一个事务内两次读取同一行，结果不同——因为**另一个已提交事务**在两次读取之间修改了该行。

事务 A 第一次读 name 为 `'刘备'`，事务 B 把 name 改成 `'关羽'` 并提交，事务 A 第二次读 name 变成了 `'关羽'`。

### 幻读（Phantom Read）

一个事务按相同条件两次查询，第二次读到了第一次**没有的新行**——因为另一个已提交事务在两次查询之间插入了符合条件的记录。

事务 A 查询 `number > 0`，得到 1 条记录。事务 B 插入一条新记录并提交。事务 A 再查 `number > 0`，得到 2 条记录。

幻读专指"多出来的行"。如果是已有行被删除导致变少，本质上属于每一行的不可重复读。

## SQL 标准的四个隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| READ UNCOMMITTED | 可能 | 可能 | 可能 |
| READ COMMITTED | 不可能 | 可能 | 可能 |
| REPEATABLE READ | 不可能 | 不可能 | 可能 |
| SERIALIZABLE | 不可能 | 不可能 | 不可能 |

- 隔离级别越高，并发问题越少，但性能开销越大
- 脏写太严重，四个级别都不允许
- **MySQL 默认隔离级别：REPEATABLE READ**
- MySQL 的 RR 级别在实现上可以通过 MVCC + 间隙锁**禁止幻读**，比 SQL 标准更强

### MySQL 中设置隔离级别

```sql
-- 语法
SET [GLOBAL|SESSION] TRANSACTION ISOLATION LEVEL level;

-- level 可选值
-- REPEATABLE READ | READ COMMITTED | READ UNCOMMITTED | SERIALIZABLE
```

作用范围：

| 关键字 | 影响范围 |
|-------|---------|
| GLOBAL | 对**之后新建**的会话生效，已有会话不受影响 |
| SESSION | 对当前会话的所有后续事务生效 |
| 都不写 | 仅对当前会话的**下一个事务**生效 |

```sql
-- 查看当前隔离级别
SELECT @@transaction_isolation;
-- 结果: REPEATABLE-READ

-- 启动参数修改默认级别
-- --transaction-isolation=SERIALIZABLE
```

## MVCC 原理

MVCC（Multi-Version Concurrency Control，多版本并发控制）让**读-写操作**可以并发执行而不互相阻塞，是 RC 和 RR 两个隔离级别的核心实现机制。

### 版本链

InnoDB 聚簇索引的每条记录包含两个隐藏列：

| 隐藏列 | 作用 |
|-------|------|
| **trx_id** | 最近一次修改该记录的事务 ID |
| **roll_pointer** | 指向该记录修改前的 undo 日志（旧版本） |

每次 UPDATE 都将旧值写入 undo 日志，通过 `roll_pointer` 将所有历史版本串成一条**版本链**，链头是最新版本。每个版本都带有生成它的 `trx_id`。

示例：初始记录由事务 80 插入 `(1, '刘备', '蜀')`，之后事务 100 先后更新为 `'关羽'`、`'张飞'`，版本链为：

```
[张飞, trx_id=100] → [关羽, trx_id=100] → [刘备, trx_id=80]
```

### ReadView

ReadView 是事务在执行 SELECT 时生成的**一致性快照**，用于判断版本链中哪个版本对当前事务可见。

ReadView 包含 4 个关键字段：

| 字段 | 含义 |
|------|------|
| **m_ids** | 生成 ReadView 时，系统中所有**活跃**（未提交）的读写事务 ID 列表 |
| **min_trx_id** | m_ids 中的最小值 |
| **max_trx_id** | 系统应该分配给**下一个事务**的 ID（不是 m_ids 的最大值） |
| **creator_trx_id** | 生成该 ReadView 的事务自身的 ID（只读事务默认为 0） |

> `max_trx_id` 的值 = 当前已分配的最大事务 ID + 1。例如活跃事务为 1、2（事务 3 已提交），则 m_ids=[1,2]，min_trx_id=1，max_trx_id=4。

### 可见性判断规则

访问版本链中某个版本时，取该版本的 `trx_id`，依次判断：

1. **trx_id == creator_trx_id** → **可见**（自己修改的，当然看得到）
2. **trx_id < min_trx_id** → **可见**（该版本在 ReadView 生成前已提交）
3. **trx_id >= max_trx_id** → **不可见**（该版本由 ReadView 生成后才开启的事务产生）
4. **min_trx_id <= trx_id < max_trx_id** → 检查 trx_id 是否在 m_ids 中：
   - **在** m_ids 中 → **不可见**（生成该版本的事务仍活跃）
   - **不在** m_ids 中 → **可见**（生成该版本的事务已提交）

如果当前版本不可见，沿 `roll_pointer` 找到上一个版本，重复上述判断，直到找到可见版本或遍历完所有版本（该记录对当前事务完全不可见）。

## READ COMMITTED 的 MVCC 实现

RC 级别下，**每次执行 SELECT 都会生成一个新的 ReadView**。

示例，初始数据 `(1, '刘备', '蜀')` 由事务 80 插入：

**第一次 SELECT**（事务 100 和 200 均未提交）：
- 事务 100 已将 name 更新为 `'关羽'` → `'张飞'`
- 生成 ReadView：m_ids=[100,200]，min_trx_id=100，max_trx_id=201
- 版本链：`张飞(100)` → `关羽(100)` → `刘备(80)`
- 100 在 m_ids 中 → 不可见；80 < 100 → 可见
- **结果：`'刘备'`**

**第二次 SELECT**（事务 100 已提交，事务 200 更新为 `'赵云'` → `'诸葛亮'`）：
- **重新生成** ReadView：m_ids=[200]，min_trx_id=200，max_trx_id=201
- 版本链：`诸葛亮(200)` → `赵云(200)` → `张飞(100)` → `关羽(100)` → `刘备(80)`
- 200 在 m_ids 中 → 不可见；100 < 200 → 可见
- **结果：`'张飞'`**（能看到事务 100 提交后的值）

两次读取结果不同——这就是**不可重复读**。

## REPEATABLE READ 的 MVCC 实现

RR 级别下，**只在第一次执行 SELECT 时生成 ReadView，之后复用同一个**。

同样的场景：

**第一次 SELECT**（事务 100 和 200 均未提交）：
- 生成 ReadView：m_ids=[100,200]，min_trx_id=100，max_trx_id=201
- 判断过程同上，**结果：`'刘备'`**

**第二次 SELECT**（事务 100 已提交，事务 200 更新为 `'诸葛亮'`）：
- **复用**第一次的 ReadView：m_ids=[100,200]，min_trx_id=100，max_trx_id=201
- 版本链：`诸葛亮(200)` → `赵云(200)` → `张飞(100)` → `关羽(100)` → `刘备(80)`
- 200 在 m_ids → 不可见；100 在 m_ids → 不可见；80 < 100 → 可见
- **结果：仍然是 `'刘备'`**

两次读取结果一致——这就是**可重复读**。

**核心区别总结**：

| 隔离级别 | ReadView 生成时机 | 效果 |
|---------|-----------------|------|
| READ COMMITTED | 每次 SELECT 都生成新的 | 能看到其他已提交事务的修改 |
| REPEATABLE READ | 第一次 SELECT 时生成，之后复用 | 整个事务期间看到的数据快照一致 |

## 当前读与快照读

MVCC 中的读操作分两类：

**快照读（Snapshot Read）**：普通 SELECT 语句，读取的是版本链中符合 ReadView 可见性规则的历史版本，不加锁。

```sql
SELECT * FROM hero WHERE number = 1;
```

**当前读（Current Read）**：读取记录的**最新已提交版本**，并对记录加锁。以下操作都是当前读：

```sql
SELECT * FROM hero WHERE number = 1 FOR UPDATE;        -- 加排他锁
SELECT * FROM hero WHERE number = 1 LOCK IN SHARE MODE; -- 加共享锁
INSERT INTO hero VALUES (2, '关羽', '蜀');               -- 插入前检查
UPDATE hero SET name = '张飞' WHERE number = 1;          -- 更新
DELETE FROM hero WHERE number = 1;                       -- 删除
```

INSERT / UPDATE / DELETE 内部需要先读取最新数据再执行修改，因此**始终是当前读**，不走 MVCC 版本链。

## 幻读的解决

SQL 标准中 RR 级别仍可能幻读，但 **MySQL 的 RR 级别通过两种机制配合解决幻读**：

**1. 快照读：MVCC 天然防幻读**

RR 下 ReadView 只生成一次。即使其他事务插入了新行并提交，由于新行的 trx_id 要么在 m_ids 中、要么 >= max_trx_id，对当前事务不可见。快照读层面不会出现幻行。

**2. 当前读：间隙锁（Gap Lock）防幻读**

当执行 `SELECT ... FOR UPDATE` 或 UPDATE/DELETE 等当前读操作时，InnoDB 不仅锁住已有记录（Record Lock），还会锁住**记录之间的间隙**（Gap Lock），两者合称 **Next-Key Lock**。

间隙锁阻止其他事务在锁定范围内插入新记录，从而在当前读层面也避免了幻读。

> 间隙锁只在 RR 级别下生效。RC 级别没有间隙锁，因此 RC 下当前读可能出现幻读。

## purge 机制

- INSERT 的 undo 日志在事务提交后即可释放
- UPDATE/DELETE 的 undo 日志需要支撑 MVCC，不能立即删除
- 被 DELETE 标记的记录也不会立即物理删除（MVCC 可能还需要该版本）
- InnoDB 后台运行 **purge 线程**，在确认没有任何活跃 ReadView 需要访问这些旧版本后，才真正回收 undo 日志和物理删除记录
