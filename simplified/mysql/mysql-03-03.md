# undo 日志

## 为什么需要 undo 日志

事务要求原子性：要么全做，要么全不做。如果事务执行到一半遇到错误或手动 `ROLLBACK`，就需要把已做的修改全部撤销——这就是**回滚**。

回滚的本质是"反向操作"：
- 插入了一条记录 → 回滚时删除它
- 删除了一条记录 → 回滚时重新插入
- 修改了一条记录 → 回滚时还原旧值

每次对记录做增删改之前，InnoDB 会先记录一条 **undo 日志**，保存回滚所需的信息。SELECT 不修改数据，不产生 undo 日志。

除了回滚之外，undo 日志的另一个核心用途是支撑 **MVCC**（多版本并发控制）。通过 undo 日志中记录的历史版本，其他事务可以读到某条记录"在过去某个时间点"的快照版本，而不必等待当前事务提交。

## 事务 ID

### 分配时机

InnoDB 不会在事务开启时立即分配事务 ID，而是：
- **读写事务**：在它**第一次对某个表执行增删改**时，才分配一个唯一的 `trx_id`
- **只读事务**：只有对用户创建的**临时表**做增删改时才分配
- 如果一个事务全是 SELECT，不会分配事务 ID

### 生成方式

服务器在内存中维护一个全局递增变量，每次分配事务 ID 就取当前值并自增。每当该值为 256 的倍数时，持久化到系统表空间（第 5 号页面的 `Max Trx ID`）。重启后加载该值 +256 继续分配，保证全局单调递增。

### trx_id 和 roll_pointer 隐藏列

聚簇索引的每条记录自动携带两个隐藏列：
- **trx_id**：最近一次对该记录做改动的事务 ID
- **roll_pointer**：指向该记录对应的 undo 日志的指针（7 字节），是构建版本链的关键

## INSERT 的 undo 日志

类型：**TRX_UNDO_INSERT_REC**

插入操作的回滚只需要"按主键删除"，因此 undo 日志只记录：
- `undo no`：本事务中第几条 undo 日志（从 0 递增）
- `table id`：表的 ID
- 主键各列的长度和值

回滚时根据主键值执行删除，聚簇索引记录被删后，对应的二级索引记录也会被一并清除。

插入记录后，该记录的 `roll_pointer` 就指向这条 undo 日志。

## DELETE 的 undo 日志

删除操作分**两个阶段**：

### 阶段一：delete mark

在事务**提交前**，只将记录头信息中的 `delete_mask` 标志位置为 1，记录仍留在正常记录链表中，不会真正移除。同时更新 `trx_id` 和 `roll_pointer`。

此时记录处于"中间状态"——标记了删除但物理上还在。这是为 MVCC 服务的：其他事务可能还需要读取这条记录的内容。

这一步产生的 undo 日志类型为 **TRX_UNDO_DEL_MARK_REC**，记录内容包括：
- `undo no`、`table id`
- **old trx_id**、**old roll_pointer**（记录修改前的值，用于串联版本链）
- 索引列各列信息（`<pos, len, value>` 列表），供 purge 阶段使用

### 阶段二：purge

事务**提交后**，由后台 **purge 线程**异步执行真正的物理删除：将记录从正常链表移到垃圾链表，释放存储空间供后续复用。

undo 日志只需要记录阶段一（delete mark）的信息，因为提交后不再需要回滚。

## UPDATE 的 undo 日志

UPDATE 操作根据是否更新主键，处理方式完全不同。

### 不更新主键

分两种情况：

**就地更新（in-place update）**：被更新的**每个列**更新前后占用的存储空间大小都相同，就直接在原位置修改。例如 `VARCHAR` 列从 `'M416'`（4 字节）更新为 `'M249'`（4 字节）。任何一个列的大小变了都不能就地更新。

**先删后插**：如果有列大小发生变化，先把旧记录从聚簇索引页面中**真正删除**（移入垃圾链表，注意这里不是 delete mark，是用户线程同步执行的真正删除），然后插入一条用更新后列值构建的新记录。

两种情况产生的 undo 日志类型相同：**TRX_UNDO_UPD_EXIST_REC**，记录内容包括：
- `undo no`、`table id`
- old trx_id、old roll_pointer
- `n_updated`：被更新的列数
- 每个被更新列的 `<pos, old_len, old_value>`（旧值信息）
- 如果更新了索引列，还会额外记录索引列各列信息

### 更新主键

更新主键意味着记录在聚簇索引中的位置要改变，InnoDB 分两步处理：

1. **对旧记录执行 delete mark**（不是真删，purge 线程后续处理）→ 产生一条 **TRX_UNDO_DEL_MARK_REC** 类型的 undo 日志
2. **根据新主键值插入新记录**（重新定位位置）→ 产生一条 **TRX_UNDO_INSERT_REC** 类型的 undo 日志

所以更新主键时，一条记录的修改会产生 **2 条** undo 日志。

旧记录只做 delete mark 而不立即真删，是因为其他事务可能正在通过 MVCC 读取该版本。

## 版本链

每条 undo 日志中都保存了 **old trx_id** 和 **old roll_pointer**。记录的 `roll_pointer` 指向最新的 undo 日志，而这条 undo 日志通过 `old roll_pointer` 又指向更早的 undo 日志，如此串联形成一条**版本链**。

```
当前记录 (trx_id=200)
   ↓ roll_pointer
undo日志 (trx_id=200, old_roll_pointer →)
   ↓
undo日志 (trx_id=100, old_roll_pointer →)
   ↓
undo日志 (trx_id=50, ...)
```

通过版本链，MVCC 可以沿着链表回溯，找到对某个事务"可见"的那个历史版本，实现不加锁的一致性读。这是下一章 MVCC 的核心基础。

## undo 日志的存储

### undo 日志的两大类

InnoDB 将 undo 日志分为两大类，分开存储在不同的 Undo 页面中，不能混放：

| 类别 | 包含的日志类型 | 说明 |
|------|--------------|------|
| **TRX_UNDO_INSERT** | TRX_UNDO_INSERT_REC | INSERT 产生（含 UPDATE 更新主键时的插入） |
| **TRX_UNDO_UPDATE** | TRX_UNDO_DEL_MARK_REC、TRX_UNDO_UPD_EXIST_REC 等 | DELETE、UPDATE 产生 |

分开的原因：INSERT 类的 undo 日志提交后可立即释放；UPDATE 类因 MVCC 依赖不能立即释放。

### Undo 页面链表

一个事务执行中，undo 日志写在类型为 `FIL_PAGE_UNDO_LOG` 的页面中。一个页面放不下时追加新页面，通过链表串联。由于两大类不能混放，一个事务最多产生 **4 条 Undo 页面链表**：

- 普通表的 insert undo 链表
- 普通表的 update undo 链表
- 临时表的 insert undo 链表
- 临时表的 update undo 链表

按需分配，不需要就不分配。不同事务的 undo 日志写入不同的链表，互不干扰。

### 回滚段（Rollback Segment）

每条 Undo 页面链表需要占用一个 **undo slot**。InnoDB 用一个 `Rollback Segment Header` 页面来集中管理 undo slot，每个这样的页面包含 **1024 个 undo slot**。

InnoDB 共有 **128 个回滚段**，即 128 × 1024 = **131072 个 undo slot**。回滚段分布如下：

| 编号 | 用途 | 位置 |
|------|------|------|
| 第 0 号 | 普通表 | 系统表空间 |
| 第 1~32 号 | 临时表 | 临时表空间（ibtmp1） |
| 第 33~127 号 | 普通表 | 系统表空间或 undo 表空间 |

分配 undo slot 的流程：
1. 轮询（round-robin）选一个回滚段
2. 先看 cached 链表有无可重用的 slot
3. 没有则遍历该回滚段中 1024 个 slot，找到空闲的（值为 `FIL_NULL`）
4. 全满则报错 `Too many active concurrent transactions`

### undo 表空间

第 33~127 号回滚段可配置到独立的 **undo 表空间**中（`innodb_undo_tablespaces`）。好处是 undo 表空间可以 truncate 缩小文件，而系统表空间只能增长不能缩小。

## undo 日志的生命周期

### insert undo 日志

事务提交后，INSERT 的 undo 日志就没用了（新插入的记录对其他事务不存在历史版本问题），因此可以**立即释放**。

如果 insert undo 链表只有一个页面且已用空间 < 3/4，则该链表会被**缓存**起来（标记为 `TRX_UNDO_CACHED`），后续事务可以直接**覆盖**重写，避免反复分配页面。

不满足重用条件的链表，对应的段直接释放，undo slot 置为 `FIL_NULL`。

### update undo 日志

事务提交后，DELETE/UPDATE 的 undo 日志**不能立即释放**，因为其他事务可能正通过 MVCC 的版本链读取这些历史版本。

处理方式：
1. 事务提交时，将这组 undo 日志放入 **History 链表**
2. 后台 **purge 线程**定期检查：当没有任何活跃事务再需要某个历史版本时，才清理对应的 undo 日志并释放空间

如果 update undo 链表符合重用条件（单页面 + 已用 < 3/4），后续事务可以在同一页面中**追加**新的 undo 日志组（不能覆盖，因为旧的还有用）。

### 总结

| 类型 | 提交后处理 | 原因 |
|------|-----------|------|
| insert undo | 立即释放或缓存重用 | 新记录无历史版本需求 |
| update undo | 放入 History 链表，等 purge 清理 | MVCC 版本链依赖 |
