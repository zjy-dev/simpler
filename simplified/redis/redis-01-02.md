# 字典

Redis 用字典做数据库的底层实现，也用它做哈希键的底层实现。C 语言没有内置字典，Redis 自己写了一套。

## 数据结构

三层嵌套：

```c
// 哈希表节点
typedef struct dictEntry {
    void *key;
    union { void *val; uint64_t u64; int64_t s64; } v;
    struct dictEntry *next;  // 链地址法解决冲突
} dictEntry;

// 哈希表
typedef struct dictht {
    dictEntry **table;      // 桶数组
    unsigned long size;     // 桶数量
    unsigned long sizemask; // size - 1，用于计算索引
    unsigned long used;     // 已有键值对数量
} dictht;

// 字典
typedef struct dict {
    dictType *type;    // 类型特定函数（哈希函数、键比较等）
    void *privdata;
    dictht ht[2];      // 两个哈希表，ht[1] 仅 rehash 时使用
    int rehashidx;      // rehash 进度，-1 表示没在 rehash
} dict;
```

## 哈希算法

索引计算：`index = hash(key) & ht[x].sizemask`

Redis 对数据库和哈希键使用 MurmurHash2 算法，输入有规律也能给出好的随机分布。

## 键冲突处理

链地址法：同一个桶里的节点用 `next` 指针串成单向链表。新节点插到链表头部（O(1)）。

## rehash

负载因子 = `ht[0].used / ht[0].size`

**触发条件：**

- 没在执行 `BGSAVE`/`BGREWRITEAOF` 时，负载因子 >= 1 → 扩容
- 正在执行 `BGSAVE`/`BGREWRITEAOF` 时，负载因子 >= 5 → 扩容（阈值提高是因为 fork 子进程期间要避免写时复制开销）
- 负载因子 < 0.1 → 缩容

**扩容大小：** 第一个 >= `ht[0].used * 2` 的 $2^n$

**缩容大小：** 第一个 >= `ht[0].used` 的 $2^n$

## 渐进式 rehash

如果哈希表有几百万个键值对，一次性迁移会卡住服务。Redis 的方案是分步搬迁：

1. 给 `ht[1]` 分配空间，`rehashidx` 设为 0
2. 每次对字典执行增删查改，顺带把 `ht[0]` 在 `rehashidx` 索引上的所有键值对迁移到 `ht[1]`，然后 `rehashidx++`
3. 全部搬完后，释放 `ht[0]`，把 `ht[1]` 变成 `ht[0]`，新建空的 `ht[1]`，`rehashidx` 设回 -1

**rehash 期间的操作规则：**

- 查找/删除/更新：先查 `ht[0]`，没找到再查 `ht[1]`
- 新增：只往 `ht[1]` 写，保证 `ht[0]` 只减不增
