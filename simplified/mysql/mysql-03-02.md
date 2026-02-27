# redo 日志

## 为什么需要 redo 日志

InnoDB 以页（16KB）为单位管理存储，所有修改先在内存 Buffer Pool 中进行。事务提交后如果系统崩溃，内存中的修改就会丢失，无法满足事务的**持久性（Durability）**。

最直觉的方案是事务提交时把所有修改过的页刷到磁盘，但有两个致命问题：

1. **写放大**：可能只改了页中几个字节，却要刷整个 16KB 页
2. **随机 IO**：一个事务可能修改多个不相邻的页，产生大量随机写

解决思路就是 **WAL（Write-Ahead Logging）**：不刷数据页，而是把"做了什么修改"以日志形式**顺序写**到磁盘。这就是 redo 日志。

redo 日志的两大优势：

- **体积小**：只记录"哪个表空间、哪个页、哪个偏移量、改成什么值"
- **顺序写**：日志按产生顺序追加写入，顺序 IO 远快于随机 IO

崩溃重启时，按 redo 日志重放修改即可恢复数据，保证持久性。

## redo 日志格式

每条 redo 日志的通用结构：

| 字段 | 含义 |
|------|------|
| type | 日志类型（共 53 种） |
| space ID | 表空间 ID |
| page number | 页号 |
| data | 具体修改内容 |

### 简单类型（物理日志）

直接记录"在某页某偏移量处写入 N 个字节"，包括：

- `MLOG_1BYTE` / `MLOG_2BYTE` / `MLOG_4BYTE` / `MLOG_8BYTE`：写入固定字节数
- `MLOG_WRITE_STRING`：写入变长数据，额外带 `len` 字段

这类日志结构为：`type + space ID + page number + offset + data`。

### 复杂类型（逻辑日志）

一条 INSERT 可能修改页面中的多个位置（记录数据、Page Directory、Page Header、记录链表等）。如果每个修改点都写一条物理日志，开销太大。

因此 InnoDB 设计了复合类型日志，如 `MLOG_COMP_REC_INSERT`（插入紧凑行格式记录）、`MLOG_COMP_REC_DELETE`（删除记录）、`MLOG_COMP_PAGE_CREATE`（创建页面）等。

这类日志的特点：

- **物理层面**：指明了对哪个表空间的哪个页修改
- **逻辑层面**：恢复时不是简单地覆盖字节，而是调用对应函数（如"插入记录"函数），用日志中的数据作为参数重新执行操作，间接恢复页面所有相关字段

## Mini-Transaction（mtr）

### 为什么需要 mtr

向 B+ 树插入一条记录时，可能涉及页分裂，需要修改多个页面（原页、新页、父节点页、段/区管理页等），产生几十条 redo 日志。这些修改必须是**原子的**——要么全部恢复，要么全部不恢复，否则会产生不正确的 B+ 树结构。

### mtr 的原子性保证

InnoDB 把对底层页面的一次原子操作称为一个 **Mini-Transaction（mtr）**。一个 mtr 产生的一组 redo 日志是不可分割的整体。

实现方式：

- **多条日志的 mtr**：在最后一条日志后追加一条 `MLOG_MULTI_REC_END` 类型的标记日志。恢复时只有扫描到该标记才认为是完整的一组，否则丢弃
- **单条日志的 mtr**：利用 type 字段的最高位（第 1 bit）标记为 1，表示该条日志本身就是一个完整的 mtr

### 事务、语句与 mtr 的关系

```
事务 → 包含多条语句
  语句 → 包含多个 mtr
    mtr → 包含一组 redo 日志（不可分割）
```

## redo log buffer

### 基本结构

InnoDB 启动时申请一块连续内存作为 **redo log buffer**，由参数 `innodb_log_buffer_size` 控制大小（默认 16MB）。

log buffer 内部划分为若干个 **512 字节的 block**（称为 redo log block）。每个 block 结构：

| 部分 | 大小 | 说明 |
|------|------|------|
| log block header | 12 字节 | 管理信息（block 编号、已用字节数等） |
| log block body | 496 字节 | 实际存储 redo 日志 |
| log block trailer | 4 字节 | 校验值 |

写入时通过全局变量 `buf_free` 标记下一条日志的写入位置，顺序追加。

### 写入时机

mtr 执行过程中产生的日志先暂存于 mtr 内部，**mtr 结束时才将整组日志一次性复制到 log buffer**。这保证了同一 mtr 的日志在 buffer 中是连续的。

不同事务的 mtr 可能并发执行，因此 log buffer 中不同事务的日志是交替存放的。

### 刷盘时机

log buffer 中的日志在以下情况刷入磁盘：

1. **log buffer 空间不足**：已用空间超过总容量一半时触发刷盘
2. **事务提交时**：根据 `innodb_flush_log_at_trx_commit` 参数决定行为
3. **后台线程**：约每秒刷新一次
4. **做 checkpoint 时**
5. **服务器正常关闭时**

### 刷盘策略：innodb_flush_log_at_trx_commit

| 值 | 行为 | 持久性 | 性能 |
|----|------|--------|------|
| **0** | 提交时不刷盘，交给后台线程 | 崩溃可能丢最近约 1 秒的事务 | 最快 |
| **1** | 提交时同步刷盘（fsync） | 完全保证持久性 | 最慢（默认值） |
| **2** | 提交时写到 OS 缓冲区，不 fsync | 数据库崩溃不丢，OS 崩溃可能丢 | 折中 |

生产环境通常使用 1；对允许少量丢失的场景（如日志表）可用 2 提升性能。

## redo 日志文件

### 文件组结构

MySQL 数据目录下默认有 `ib_logfile0` 和 `ib_logfile1` 两个日志文件，构成一个**日志文件组**。相关参数：

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `innodb_log_file_size` | 单个日志文件大小 | 48MB |
| `innodb_log_files_in_group` | 日志文件个数 | 2 |
| `innodb_log_group_home_dir` | 日志文件目录 | 数据目录 |

总日志容量 = `innodb_log_file_size × innodb_log_files_in_group`。

### 循环写入

日志文件组采用**循环写**：写满 `ib_logfile0` → 写 `ib_logfile1` → … → 写满最后一个文件后回到 `ib_logfile0`。每个文件前 2048 字节（4 个 block）存储管理信息（包括 checkpoint 信息），实际日志从偏移量 2048 开始。

循环写意味着新日志会覆盖旧日志，因此需要 checkpoint 机制来标记哪些旧日志可以安全覆盖。

## LSN（Log Sequence Number）

LSN 是一个**全局递增的日志序列号**，表示系统已产生的 redo 日志总量（单位：字节）。初始值为 8704。

每个 mtr 写入 log buffer 时，lsn 增加该 mtr 日志的字节数（跨 block 时还要加上 block header/trailer 的开销）。**LSN 越小，日志越早产生。**

### 几个关键 LSN

| 变量 | 含义 |
|------|------|
| **lsn** | 当前系统已写入（含 log buffer 中）的日志总量 |
| **flushed_to_disk_lsn** | 已刷到磁盘的日志量。等于 lsn 时表示所有日志已落盘 |
| **checkpoint_lsn** | 已做 checkpoint 的位置，之前的日志可被覆盖 |

可通过 `SHOW ENGINE INNODB STATUS` 查看：

```
Log sequence number 124476971    -- lsn
Log flushed up to   124099769    -- flushed_to_disk_lsn
Pages flushed up to 124052503    -- flush 链表尾部 oldest_modification
Last checkpoint at  124052494    -- checkpoint_lsn
```

### flush 链表与 LSN

mtr 结束时，除了将 redo 日志写入 log buffer，还会把修改过的页加入 Buffer Pool 的 **flush 链表**（按首次修改时间从新到旧排序）。每个脏页维护两个 LSN：

- `oldest_modification`：该页首次被修改时 mtr 的起始 lsn
- `newest_modification`：该页最近一次被修改时 mtr 的结束 lsn

## checkpoint

### 为什么需要 checkpoint

日志文件组空间有限，循环写会覆盖旧日志。只有当 redo 日志对应的**脏页已经刷到磁盘**，该段日志才不再需要，可以被覆盖。

### checkpoint 过程

1. **计算 checkpoint_lsn**：取 flush 链表尾部（最早修改的脏页）的 `oldest_modification` 值，所有 lsn 小于该值的日志均可覆盖
2. **持久化 checkpoint 信息**：将 `checkpoint_lsn`、对应的日志文件偏移量、checkpoint 编号（`checkpoint_no`）写入第一个日志文件的管理区域（`checkpoint_no` 为偶数写 checkpoint1 block，奇数写 checkpoint2 block）

### write pos 与 checkpoint 的追赶关系

可以把循环日志想象为一个环形结构：

- **write pos**：当前日志写入位置，不断前进
- **checkpoint**：可覆盖位置，随脏页刷盘而前进

write pos 追上 checkpoint 时，意味着日志空间满了，必须先推进 checkpoint（刷脏页）才能继续写入。如果后台线程刷脏不够快，用户线程会被迫同步刷脏。

## 崩溃恢复

### 确定恢复起点

读取第一个日志文件中 checkpoint1 和 checkpoint2 的 `checkpoint_no`，取较大的那个。其对应的 `checkpoint_lsn` 和 `checkpoint_offset` 就是恢复的起点——之前的日志对应的脏页已持久化，无需恢复。

### 确定恢复终点

从起点开始顺序扫描 block。每个 block 的 `LOG_BLOCK_HDR_DATA_LEN` 记录已使用字节数，被写满的 block 该值为 512。**第一个该值不为 512 的 block 就是终点。**

### 恢复过程

1. **扫描 redo 日志**：从 checkpoint_lsn 对应的偏移量开始，顺序读取到终点
2. **按页面分组（哈希表优化）**：以 `(space ID, page number)` 为 key 建哈希表，同一页的 redo 日志按生成顺序串成链表。这样可以一次性读取一个页并应用所有相关日志，将随机 IO 转为顺序处理
3. **应用日志恢复页面**：遍历哈希表，逐页应用 redo 日志
4. **跳过已刷盘页面**：每个数据页的 File Header 中有 `FIL_PAGE_LSN` 属性（等于该页的 `newest_modification`）。若该值 ≥ 某条 redo 日志的 lsn，说明该修改已经持久化，无需重复应用，进一步加速恢复
