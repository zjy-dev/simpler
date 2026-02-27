# Buffer Pool

## 什么是 Buffer Pool

InnoDB 的数据以页（16KB）为单位存储在磁盘上。磁盘 IO 远慢于 CPU，因此 InnoDB 在启动时向操作系统申请一块**连续的内存空间**作为缓存，称为 Buffer Pool。访问某页数据时，先将整页加载到 Buffer Pool，后续对该页的访问直接走内存，省去磁盘 IO。

即使只访问页中的一条记录，也需要将整个页加载到内存。读写完成后不立即释放，而是缓存起来供后续请求复用。

默认大小 128MB，通过 `innodb_buffer_pool_size` 配置，最小值 5MB：

```sql
[server]
innodb_buffer_pool_size = 268435456  -- 256MB
```

## Buffer Pool 内部结构

### 控制块与缓存页

Buffer Pool 中缓存页大小与磁盘页一致（16KB）。每个缓存页都有一个对应的**控制块**，记录表空间编号、页号、缓存页地址、链表指针、锁信息、LSN 等元信息。控制块约占缓存页大小的 5%（MySQL 5.7.21 中为 808 字节）。

内存布局：控制块在前，缓存页在后，中间可能产生不足一对的**碎片**。

![](images/18-01.png)

> `innodb_buffer_pool_size` 不包含控制块的空间，InnoDB 实际申请的内存约比配置值大 5%。

### free 链表

启动时所有缓存页都空闲，其控制块组成一个双向链表——**free 链表**。链表有一个独立分配的**基节点**（40 字节），记录头尾指针和节点数。

从磁盘加载页时：从 free 链表取一空闲缓存页 → 填充控制块信息 → 从 free 链表中移除该节点。

![](images/18-02.png)

### 缓存页的哈希表

如何判断某页是否已在 Buffer Pool 中？遍历太慢。InnoDB 用 `表空间号 + 页号` 作 key，缓存页作 value 建**哈希表**，O(1) 定位。访问某页时先查哈希表：命中则直接使用；未命中则从 free 链表分配缓存页，将磁盘数据加载进来，同时在哈希表中插入映射。

## flush 链表

修改了 Buffer Pool 中某缓存页的数据后，该页与磁盘不一致，称为**脏页**（dirty page）。脏页不会立即刷盘，而是将其控制块加入 **flush 链表**，等后台线程择机同步。

flush 链表结构与 free 链表类似，只是节点是所有被修改过的缓存页。

![](images/18-03.png)

## LRU 链表

Buffer Pool 容量有限，free 链表耗尽时需要淘汰旧页。InnoDB 用 **LRU（Least Recently Used）链表**管理淘汰策略。

### 简单 LRU 的问题

朴素做法：访问一页时将其移到链表头部，淘汰时从尾部移除。但有两个场景会严重拉低缓存命中率：

1. **预读（read ahead）**：InnoDB 可能预先加载后续页面到 Buffer Pool。如果预读页未被实际访问，却占据了链表头部，就会把真正的热页挤到尾部被淘汰。
   - **线性预读**：顺序访问某个区（extent）的页面超过 `innodb_read_ahead_threshold`（默认 56）时，异步预读下一个区的全部页面。
   - **随机预读**：Buffer Pool 中已缓存某区 13 个连续页面时触发（默认关闭，`innodb_random_read_ahead = OFF`）。

2. **全表扫描**：一次性加载大量页面，把整个 Buffer Pool 换血，其他热页全被淘汰。而全表扫描本身执行频率很低。

### 分区 LRU（young 区 + old 区）

InnoDB 将 LRU 链表分为两段：

| 区域 | 含义 | 默认占比 |
|------|------|----------|
| **young 区** | 热数据，使用频率高的缓存页 | 约 63% |
| **old 区** | 冷数据，使用频率低的缓存页 | 约 37% |

![](images/18-04.png)

`innodb_old_blocks_pct` 控制 old 区比例，默认 37（即 37%）。可动态修改：

```sql
SET GLOBAL innodb_old_blocks_pct = 40;
```

分区后的核心规则：

- **新页首次加载**时放入 **old 区头部**，而非整条链表头部。预读但未使用的页自然从 old 区淘汰，不影响 young 区。
- old 区的页被再次访问时，若距首次访问的时间间隔**超过** `innodb_old_blocks_time`（默认 1000ms），才移动到 young 区头部。全表扫描中同一页的多次访问通常在 1s 内完成，因此不会进入 young 区。

### 预读与全表扫描的优化

分区 LRU + `innodb_old_blocks_time` 两道防线：

1. 预读页只进 old 区，用不到自然被淘汰。
2. 全表扫描的页虽在短时间内被多次访问，但因时间间隔不足而留在 old 区。

进一步优化：young 区内的缓存页，如果位于 young 区前 1/4，再次访问时**不移动**到头部，降低链表操作频率。

当 Buffer Pool 中无空闲缓存页时，从 LRU 链表尾部（old 区末端）淘汰最冷的页面。

## 刷脏页

后台线程负责将脏页异步刷盘，主要有三种方式：

| 方式 | 来源 | 说明 |
|------|------|------|
| **BUF_FLUSH_LRU** | LRU 链表尾部 | 定时从尾部扫描 `innodb_lru_scan_depth` 个页面，发现脏页就刷盘 |
| **BUF_FLUSH_LIST** | flush 链表 | 定时从 flush 链表刷一批脏页，速率随系统负载调节 |
| **BUF_FLUSH_SINGLE_PAGE** | LRU 链表尾部 | 用户线程找不到空闲页时，同步刷 LRU 尾部的一个脏页（影响性能） |

第三种是兜底策略——后台线程刷新不够快，用户线程被迫同步刷盘，会显著拖慢请求处理速度。

系统特别繁忙时，用户线程甚至会批量从 flush 链表刷脏页，这与 redo log 的 checkpoint 机制有关。

## 多 Buffer Pool 实例

多线程并发访问 Buffer Pool 需要加锁。当 Buffer Pool 很大时，单实例锁竞争成为瓶颈。InnoDB 支持拆分为多个独立实例，各自维护 free、flush、LRU 链表，互不干扰。

```sql
[server]
innodb_buffer_pool_instances = 2
```

![](images/18-05.png)

每个实例大小 = `innodb_buffer_pool_size / innodb_buffer_pool_instances`。

> 当 `innodb_buffer_pool_size < 1GB` 时，多实例设置无效，InnoDB 强制使用 1 个实例。

### chunk 机制

MySQL 5.7.5 起支持运行时动态调整 Buffer Pool 大小。为避免重新申请整块连续内存，引入 **chunk** 概念——每个实例由若干 chunk 组成，每个 chunk 是一片连续内存（默认 128MB，`innodb_buffer_pool_chunk_size` 启动时指定，运行时不可更改）。

![](images/18-06.png)

配置约束：

- `innodb_buffer_pool_size` 必须是 `chunk_size × instances` 的整数倍，否则自动向上取整。
- 若 `chunk_size × instances > buffer_pool_size`，chunk_size 会被自动调整为 `buffer_pool_size / instances`。

### 查看 Buffer Pool 状态

```sql
SHOW ENGINE INNODB STATUS\G
```

关键指标：

| 字段 | 含义 |
|------|------|
| Buffer pool size | 可容纳的缓存页数（单位：页） |
| Free buffers | free 链表剩余节点数 |
| Database pages | LRU 链表总页数 |
| Old database pages | LRU old 区页数 |
| Modified db pages | flush 链表节点数（脏页数） |
| Buffer pool hit rate | 缓存命中率（X / 1000） |
| Pages made young | 从 old 区移入 young 区的累计次数 |
| youngs/s / non-youngs/s | 每秒移入 young 区 / 因时间限制未移入的次数 |

## 其他信息

Buffer Pool 除了缓存数据页，还存储**锁信息**和**自适应哈希索引**（Adaptive Hash Index）。自适应哈希索引由 InnoDB 自动为热点页建立，将 B+ 树的查找从 O(log n) 优化为 O(1)，无需手动干预。
