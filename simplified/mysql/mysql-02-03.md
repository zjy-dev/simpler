# 查询优化规则

MySQL 查询优化器会在执行前对语句进行**查询重写**，通过一系列规则将低效语句转换为高效形式。

---

## 条件化简

优化器会自动简化 WHERE 条件表达式：

- **移除不必要的括号**：去掉多余嵌套括号
- **常量传递**：`a = 5 AND b > a` → `a = 5 AND b > 5`（仅 AND 连接时有效，OR 不行）
- **等值传递**：`a = b AND b = c AND c = 5` → `a = 5 AND b = 5 AND c = 5`
- **移除恒真/恒假条件**：`b = b` → TRUE，`5 != 5` → FALSE，然后继续简化
- **常量折叠**：`a = 5 + 1` → `a = 6`（仅限纯常量表达式）
- **HAVING 合并**：无聚集函数和 GROUP BY 时，HAVING 合并到 WHERE
- **常量表检测**：主键等值匹配或唯一索引等值匹配的表被视为常量表，优先执行后用常量替换相关条件

> **面试要点**：索引列必须以**单独形式**出现才能使用索引。`ABS(a) > 5` 或 `-a < -8` 都无法使用索引。

---

## 外连接消除

外连接的驱动表和被驱动表位置固定，无法像内连接那样自由调整连接顺序来优化成本。

**核心规则：空值拒绝（Reject-NULL）**

当 WHERE 子句中包含被驱动表的列**不为 NULL** 的条件时，外连接等价于内连接：

```sql
-- 以下左连接等价于内连接（WHERE 隐含拒绝 NULL）
SELECT * FROM t1 LEFT JOIN t2 ON t1.m1 = t2.m2 WHERE t2.m2 = 2;
-- 等价于
SELECT * FROM t1 INNER JOIN t2 ON t1.m1 = t2.m2 WHERE t2.m2 = 2;
```

不需要显式写 `IS NOT NULL`，只要 WHERE 条件**隐含**被驱动表列非空即可。转为内连接后，优化器可以自由评估不同连接顺序的成本，选出最优方案。

---

## 子查询优化

### 子查询分类

**按结果集分类：**

| 类型 | 说明 | 示例 |
|------|------|------|
| 标量子查询 | 返回单一值 | `WHERE m1 = (SELECT MIN(m2) FROM t2)` |
| 行子查询 | 返回一行多列 | `WHERE (m1,n1) = (SELECT m2,n2 FROM t2 LIMIT 1)` |
| 列子查询 | 返回一列多行 | `WHERE m1 IN (SELECT m2 FROM t2)` |
| 表子查询 | 返回多行多列 | `WHERE (m1,n1) IN (SELECT m2,n2 FROM t2)` |

**按关联性分类：**

- **不相关子查询**：可独立执行，不依赖外层查询
- **相关子查询**：执行依赖外层查询的值，如 `WHERE n1 = n2` 中 n1 来自外层表

### 标量/行子查询执行方式

- 不相关：先执行子查询，结果作为常量代入外层查询（两个独立单表查询）
- 相关：逐行取外层记录 → 代入子查询执行 → 检查条件 → 循环

无特殊优化，执行方式符合直觉。

### IN 子查询优化

IN 子查询是最常用的子查询类型，MySQL 投入了大量优化。

#### 物化（Materialization）

**问题**：子查询结果集过大时，直接当 IN 参数会导致：内存放不下、无法用索引、逐条比对代价高。

**方案**：将子查询结果集写入**临时表（物化表）**：

- 自动去重（IN 不关心重复值）
- 小结果集 → Memory 引擎 + **哈希索引**（查询极快）
- 大结果集（超过 `tmp_table_size`）→ 磁盘引擎 + B+ 树索引

**物化表转连接**：物化后，原查询等价于外层表与物化表的内连接：

```sql
-- 原始
SELECT * FROM s1 WHERE key1 IN (SELECT common_field FROM s2 WHERE key3 = 'a');
-- 物化后等价于
SELECT s1.* FROM s1 INNER JOIN materialized_table ON key1 = m_val;
```

转为连接后，优化器可以评估不同连接顺序的成本，选最优方案。

#### 半连接（Semi-Join）

**核心思想**：将 IN 子查询直接转为连接，但只关心被驱动表中**是否存在**匹配记录，不关心有多少条。

```sql
-- 概念上等价于（MySQL 内部表示，非合法语法）
SELECT s1.* FROM s1 SEMI JOIN s2 ON s1.key1 = s2.common_field WHERE s2.key3 = 'a';
```

**五种执行策略：**

| 策略 | 原理 | 适用场景 |
|------|------|----------|
| **Table Pullout** | 子查询表直接上拉到外层 FROM，转为普通内连接 | 子查询列是主键或唯一索引 |
| **DuplicateWeedout** | 建临时表（以外层表主键去重），消除重复结果 | 通用 |
| **LooseScan** | 扫描子查询表索引时，相同值只取第一条去匹配 | 子查询可用索引且查询列就是索引列 |
| **Materialization** | 先物化子查询再转连接（物化表天然去重） | 不相关子查询 |
| **FirstMatch** | 逐行取外层记录，找到第一条匹配就停止 | 通用（最原始方式） |

**Semi-Join 适用条件：**

- IN 子查询在 WHERE 或 ON 子句中，且与其他条件用 **AND** 连接
- 子查询是单一查询（非 UNION）
- 子查询不含 GROUP BY、HAVING、聚集函数

**不能用 Semi-Join 的情况：**

- IN 与其他条件用 **OR** 连接
- **NOT IN**
- IN 子查询在 SELECT 子句中
- 子查询含 GROUP BY / HAVING / 聚集函数 / UNION

#### 不能 Semi-Join 时的后备策略

1. **物化后查询**（仅不相关子查询）：物化子查询结果，但**不转为连接**，逐行判断值是否在物化表中
2. **IN 转 EXISTS**：转为 EXISTS 后可能用到子查询表的索引。仅在 WHERE/ON 中使用时 NULL 语义差异可忽略

```sql
-- 转换后可能用上 idx_key3 索引
WHERE EXISTS (SELECT 1 FROM s2 WHERE s1.common_field = s2.common_field AND s2.key3 = s1.key1)
```

#### IN 子查询优化决策总结

```
IN 子查询
├── 满足 semi-join 条件
│   └── 从 5 种策略中选成本最低的执行
└── 不满足 semi-join 条件
    ├── 不相关子查询 → 物化
    └── 相关子查询（或物化成本太高）→ IN 转 EXISTS
```

### ANY/ALL 子查询优化

不相关的 ANY/ALL 子查询会转换为标量子查询：

| 原始表达式 | 转换为 |
|------------|--------|
| `< ANY (SELECT ...)` | `< (SELECT MAX(...))` |
| `> ANY (SELECT ...)` | `> (SELECT MIN(...))` |
| `< ALL (SELECT ...)` | `< (SELECT MIN(...))` |
| `> ALL (SELECT ...)` | `> (SELECT MAX(...))` |

### EXISTS 子查询

- **不相关 EXISTS**：先执行子查询得到 TRUE/FALSE，直接重写外层条件
- **相关 EXISTS**：只能按逐行关联方式执行，但如果子查询能用索引则速度可观

---

## 派生表优化

FROM 子句中的子查询结果称为**派生表**（Derived Table）。两种优化策略：

### 合并到外层查询（优先）

将派生表展开，搜索条件合并到外层：

```sql
-- 原始
SELECT * FROM (SELECT * FROM s1 WHERE key1 = 'a') AS derived_s1
    INNER JOIN s2 ON derived_s1.key1 = s2.key1 WHERE s2.key2 = 1;
-- 合并后
SELECT * FROM s1 INNER JOIN s2 ON s1.key1 = s2.key1
    WHERE s1.key1 = 'a' AND s2.key2 = 1;
```

**不能合并的情况**：派生表含聚集函数、DISTINCT、GROUP BY、HAVING、LIMIT、UNION 或嵌套子查询。

### 物化

不能合并时，将派生表结果写入临时表。MySQL 采用**延迟物化**策略——只有真正用到派生表时才物化，避免不必要的开销。

**决策顺序**：优先尝试合并 → 不行则物化。
