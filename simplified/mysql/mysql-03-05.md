# 锁

## 并发控制与锁的分类

并发事务访问同一数据有三种情况：

- **读-读**：互不影响，无需控制
- **写-写**：必须排队，通过锁实现。当前事务对记录加锁后，其他事务修改同一记录时必须等待
- **读-写**：可能产生脏读、不可重复读、幻读。两种解决方案：
  - **MVCC**（多版本并发控制）：读操作读取快照版本，写操作针对最新版本，读写不冲突，性能好
  - **加锁**：读写操作排队执行，适用于必须读到最新数据的业务场景

锁按粒度分为**表级锁**和**行级锁**；按模式分为**共享锁（S 锁）**和**排他锁（X 锁）**：

- **S 锁**（Shared Lock）：读取记录前获取，多个事务可同时持有同一记录的 S 锁
- **X 锁**（Exclusive Lock）：修改记录前获取，与任何锁互斥

S/X 锁兼容性：

| | S | X |
|---|---|---|
| **S** | 兼容 | 冲突 |
| **X** | 冲突 | 冲突 |

## 表级锁

### S 锁与 X 锁

InnoDB 执行普通 DML（SELECT/INSERT/UPDATE/DELETE）时**不会**主动加表级 S/X 锁。

DDL 语句（ALTER TABLE、DROP TABLE）通过 Server 层的**元数据锁（MDL）**实现表级互斥：DDL 执行时，其他会话的 DML 被阻塞；反之亦然。

手动加表锁（极少使用）：

```sql
LOCK TABLES t READ;   -- 加表级 S 锁
LOCK TABLES t WRITE;  -- 加表级 X 锁
```

> InnoDB 的优势在于行级锁，尽量避免使用 LOCK TABLES。

### 意向锁（IS/IX）

在给行加锁之前，InnoDB 会先在**表级别**加对应的意向锁：

- **IS 锁**（Intention Shared）：准备给某行加 S 锁前，先对表加 IS 锁
- **IX 锁**（Intention Exclusive）：准备给某行加 X 锁前，先对表加 IX 锁

意向锁的唯一目的：在后续需要加表级 S/X 锁时，能**快速判断**表中是否有行被锁定，避免逐行遍历。

**IS 与 IX 之间完全兼容**——它们只在与表级 S/X 锁交互时才有冲突。

表级锁兼容矩阵：

| | X | IX | S | IS |
|---|---|---|---|---|
| **X** | 冲突 | 冲突 | 冲突 | 冲突 |
| **IX** | 冲突 | **兼容** | 冲突 | **兼容** |
| **S** | 冲突 | 冲突 | **兼容** | **兼容** |
| **IS** | 冲突 | **兼容** | **兼容** | **兼容** |

### AUTO-INC 锁

对含 `AUTO_INCREMENT` 列的表执行插入时，需要保证自增值的分配不冲突。MySQL 提供两种机制：

1. **AUTO-INC 锁**：表级锁，在整条插入语句执行期间持有（注意是语句级别，不是事务级别），其他事务的插入被阻塞直到该语句结束。适用于无法预知插入行数的语句（`INSERT ... SELECT`、`LOAD DATA`）
2. **轻量级互斥量**：仅在分配自增值时短暂持有，分配完立即释放，不等语句结束。适用于能预知插入行数的简单 INSERT

通过 `innodb_autoinc_lock_mode` 控制：

| 值 | 策略 | 说明 |
|---|---|---|
| 0 | 全部用 AUTO-INC 锁 | 最安全，并发最差 |
| 1 | 混合模式（**默认**） | 可预知行数用轻量锁，否则用 AUTO-INC 锁 |
| 2 | 全部用轻量锁 | 并发最好，但自增值可能不连续，**基于 STATEMENT 的主从复制不安全** |

## 行级锁（InnoDB）

InnoDB 的行锁加在**索引记录**上，有以下几种类型：

### Record Lock（记录锁）

锁住**单条索引记录**。官方类型名 `LOCK_REC_NOT_GAP`。

- S 型记录锁：其他事务可加 S 型记录锁，不可加 X 型记录锁
- X 型记录锁：其他事务既不可加 S 型也不可加 X 型记录锁

### Gap Lock（间隙锁）

锁住记录**前面的间隙**，不锁记录本身。官方类型名 `LOCK_GAP`。

作用：**防止其他事务向该间隙插入新记录**，用于在 RR 隔离级别下解决幻读问题。

假设索引中有记录 3、8、15，对记录 8 加 Gap Lock，则锁住的是区间 `(3, 8)`，禁止在此间隙中插入新记录。

关键特性：
- Gap 锁之间完全兼容（共享和独占的 Gap 锁效果相同）
- Gap 锁不阻止其他事务对同一记录加 Record Lock
- 最后一条记录之后的间隙通过对页面的 **Supremum 伪记录**加 Gap Lock 来保护

### Next-Key Lock（临键锁）

**Record Lock + Gap Lock 的组合**，既锁住记录本身，又锁住记录前面的间隙。官方类型名 `LOCK_ORDINARY`。

对记录 8 加 Next-Key Lock = 锁住区间 `(3, 8]`（左开右闭）。

**InnoDB 在 RR 隔离级别下，行锁的默认加锁方式就是 Next-Key Lock。**

### Insert Intention Lock（插入意向锁）

当事务向某个间隙插入记录、但该间隙已被其他事务加了 Gap Lock 时，插入操作会阻塞，此时会生成一个**插入意向锁**（类型名 `LOCK_INSERT_INTENTION`），表示"等待插入"。

关键特性：
- 插入意向锁是一种特殊的 Gap Lock
- **多个事务向同一间隙的不同位置插入时互不阻塞**（例如间隙 (3, 8) 中，事务 A 插入 4、事务 B 插入 5 不冲突）
- 插入意向锁不阻止任何其他类型的锁

### 隐式锁

INSERT 操作一般不显式加锁，通过**隐式锁**保护新插入的记录：

- 聚簇索引：记录的 `trx_id` 隐藏列记录了插入事务的 ID。其他事务想对该记录加锁时，发现 `trx_id` 对应事务仍活跃，就会先帮插入事务创建 X 锁，再让自己进入等待
- 二级索引：通过页面的 `PAGE_MAX_TRX_ID` 属性判断，必要时回表到聚簇索引做同样的检查

### 行锁兼容矩阵

已持有（行）↓ \ 请求→ | Record Lock | Gap Lock | Next-Key Lock | Insert Intention |
|---|---|---|---|---|
| **Record Lock** | S-S 兼容，其余冲突 | 兼容 | S-S 兼容，其余冲突 | 兼容 |
| **Gap Lock** | 兼容 | 兼容 | 兼容 | **冲突** |
| **Next-Key Lock** | S-S 兼容，其余冲突 | 兼容 | S-S 兼容，其余冲突 | **冲突** |
| **Insert Intention** | 兼容 | 兼容 | 兼容 | 兼容 |

核心规律：**Gap Lock / Next-Key Lock 会阻塞 Insert Intention Lock**；其余行锁类型之间，仅 X 与 X、X 与 S 的 Record Lock 部分互斥。

## 加锁分析

### SELECT 语句的加锁

| 语句 | 加锁方式 |
|------|---------|
| `SELECT ... FROM` （普通查询） | **不加锁**，使用 MVCC 快照读（RC/RR 级别下） |
| `SELECT ... LOCK IN SHARE MODE` | 对读取的记录加 **S 型行锁**（锁定读） |
| `SELECT ... FOR SHARE`（MySQL 8.0+） | 同上，语法更规范 |
| `SELECT ... FOR UPDATE` | 对读取的记录加 **X 型行锁**（锁定读） |

SERIALIZABLE 级别下，普通 SELECT 自动转为 `SELECT ... LOCK IN SHARE MODE`。

### INSERT/UPDATE/DELETE 的加锁

- **DELETE**：定位记录后加 X 锁，再执行删除标记
- **UPDATE**：
  - 未修改键值且存储空间不变：原地加 X 锁修改
  - 未修改键值但存储空间变化：加 X 锁 → 删除原记录 → 插入新记录（隐式锁保护）
  - 修改了键值：等同于 DELETE + INSERT
- **INSERT**：一般不加锁（隐式锁保护），插入位置有 Gap Lock 则阻塞并生成插入意向锁

### 不同隔离级别下的加锁差异

| 隔离级别 | 加锁特点 |
|---------|---------|
| READ UNCOMMITTED | 写操作加 Record Lock，读操作不加锁（可脏读） |
| READ COMMITTED | 写操作加 Record Lock，**不加 Gap Lock**，因此不防幻读 |
| REPEATABLE READ | **默认使用 Next-Key Lock**（Record + Gap），可防止幻读 |
| SERIALIZABLE | 类似 RR，但普通 SELECT 也会加 S 锁，完全串行化 |

RC 级别的一个优化：查询条件不匹配的记录上的锁会**立即释放**，而不是等事务结束。

## 死锁

### 死锁产生条件

两个或多个事务互相持有对方等待的锁，形成循环等待。四个必要条件：

1. **互斥**：锁是排他的
2. **持有并等待**：事务持有已获得的锁，同时等待新锁
3. **不可剥夺**：已持有的锁不能被强制释放
4. **循环等待**：事务之间形成等待环路

### MySQL 死锁检测与处理

InnoDB 采用**等待图（wait-for graph）**进行死锁检测：将事务作为节点，等待关系作为边构建有向图，图中出现**环**即表示死锁。检测到死锁后，选择**代价最小的事务**回滚（持有锁最少的），返回 `ERROR 1213 (40001): Deadlock found`。

另一种策略是**等待超时**（`innodb_lock_wait_timeout`，默认 50 秒），超时后事务回滚。但单靠超时响应太慢，InnoDB 默认开启主动死锁检测（`innodb_deadlock_detect = ON`）。

### 常见死锁场景

**场景一：交叉更新**

```
事务A: UPDATE t SET ... WHERE id = 1;  -- 获取 id=1 的 X 锁
事务B: UPDATE t SET ... WHERE id = 2;  -- 获取 id=2 的 X 锁
事务A: UPDATE t SET ... WHERE id = 2;  -- 等待 id=2 的 X 锁（B 持有）
事务B: UPDATE t SET ... WHERE id = 1;  -- 等待 id=1 的 X 锁（A 持有）→ 死锁
```

**场景二：Gap Lock 导致的死锁**

```
-- 假设表中无 id=5 的记录，id=3 和 id=8 存在
事务A: SELECT * FROM t WHERE id = 5 FOR UPDATE;  -- 对 (3,8) 加 Gap Lock
事务B: SELECT * FROM t WHERE id = 5 FOR UPDATE;  -- 也对 (3,8) 加 Gap Lock（Gap Lock 兼容）
事务A: INSERT INTO t VALUES(5, ...);  -- 被 B 的 Gap Lock 阻塞
事务B: INSERT INTO t VALUES(5, ...);  -- 被 A 的 Gap Lock 阻塞 → 死锁
```

### 避免死锁的建议

1. **按固定顺序**访问表和行（最有效的手段）
2. 事务尽量小，减少持锁时间
3. 合理使用索引，避免全表扫描导致锁住过多行
4. 在 RC 隔离级别下，Gap Lock 被禁用，可减少死锁概率（需权衡幻读风险）
5. 使用 `SHOW ENGINE INNODB STATUS\G` 查看最近一次死锁信息进行分析

## 实战：常见加锁场景

以下分析基于 **RR 隔离级别**，使用主键索引（唯一索引类似）。

### 等值查询命中

```sql
SELECT * FROM t WHERE id = 8 FOR UPDATE;
```

记录存在时：对 id=8 加 **Record Lock（X）**——Next-Key Lock 退化，不需要 Gap Lock。

### 等值查询未命中

```sql
SELECT * FROM t WHERE id = 5 FOR UPDATE;
```

记录不存在（id 在 3 和 8 之间）：对 id=8 加 **Gap Lock**，锁住 `(3, 8)` 间隙，防止幻影插入。Next-Key Lock 退化为纯 Gap Lock。

### 范围查询

```sql
SELECT * FROM t WHERE id >= 3 AND id < 8 FOR UPDATE;
```

- id=3 命中：加 Record Lock
- 继续向右扫描至 id=8（不满足 `< 8`）：对 id=8 加 Gap Lock 或 Next-Key Lock（取决于 MySQL 版本优化）
- 锁住区间 `[3, 8)` 的记录和间隙

### 唯一索引 vs 普通索引

| 场景 | 唯一索引 | 普通索引 |
|------|---------|---------|
| 等值查询命中 | Record Lock（退化） | Next-Key Lock + 右侧 Gap Lock |
| 等值查询未命中 | Gap Lock（退化） | Gap Lock（退化） |

唯一索引由于唯一性约束，等值命中时确定只有一条，**无需 Gap Lock**。普通索引可能有重复值，需要额外的 Gap Lock 防止幻读。

### 加锁范围速查（主键 1, 3, 8, 15, 20）

| 查询条件 | 加锁范围 |
|---------|---------|
| `id = 8` | Record Lock on 8 |
| `id = 5`（不存在） | Gap Lock (3, 8) |
| `id >= 8 AND id < 15` | Next-Key Lock (3, 8] + Gap Lock (8, 15) |
| `id > 18` | Next-Key Lock (15, 20] + Next-Key Lock (20, +∞) |
