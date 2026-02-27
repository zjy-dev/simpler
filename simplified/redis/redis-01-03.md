# 跳跃表

Redis 用跳跃表做有序集合（Sorted Set）的底层实现之一，也在集群节点内部用到。别的地方不用。

跳跃表查找平均 O(log N)，最坏 O(N)，实现比平衡树简单。

## 数据结构

```c
typedef struct zskiplistNode {
    struct zskiplistNode *backward; // 后退指针，只能回退一步
    double score;                   // 分值，节点按此排序
    robj *obj;                      // 成员对象（SDS 字符串）
    struct zskiplistLevel {
        struct zskiplistNode *forward; // 前进指针
        unsigned int span;             // 跨度（到下一个节点的距离）
    } level[]; // 层数组，随机 1~32 层
} zskiplistNode;

typedef struct zskiplist {
    struct zskiplistNode *header, *tail; // 表头、表尾
    unsigned long length;                // 节点数量
    int level;                           // 最大层数
} zskiplist;
```

## 核心概念

**层（level）：** 每个节点创建时随机生成 1~32 层（幂次定律，层越高概率越小）。层越多，跳过的节点越多，查找越快。

**前进指针：** 从表头向表尾方向遍历。高层指针跳得远，低层指针跳得近。

**跨度（span）：** 不是用来遍历的，是用来算排位（rank）的。查找过程中把沿途所有层的跨度加起来，就是目标节点的排位。

**后退指针：** 每个节点只有一个，只能回退到前一个节点。用于从表尾向表头遍历。

**排序规则：** 先按分值从小到大排，分值相同按成员对象的字典序排。成员对象必须唯一，分值可以重复。
