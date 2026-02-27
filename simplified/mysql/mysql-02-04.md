# EXPLAIN 详解

在查询语句前加 `EXPLAIN`，MySQL 会输出该语句的执行计划，而非执行语句本身。执行计划展示了查询优化器选择的访问方法、使用的索引、预估扫描行数等关键信息。

## 基本用法

```sql
EXPLAIN SELECT * FROM s1 WHERE key1 = 'a';
```

输出包含 12 列：

| 列名 | 含义 |
|:--:|:--|
| `id` | 每个 SELECT 对应一个唯一 id |
| `select_type` | 查询类型（简单查询、子查询、UNION 等）|
| `table` | 当前行对应的表名 |
| `type` | 访问方法（性能关键列）|
| `possible_keys` | 可能用到的索引 |
| `key` | 实际使用的索引 |
| `key_len` | 使用索引的长度 |
| `ref` | 与索引列等值匹配的对象 |
| `rows` | 预估扫描行数 |
| `filtered` | 经过条件过滤后的百分比 |
| `Extra` | 额外信息 |

> `partitions` 列一般为 NULL，不常用，此处省略。

## 各列详解

### id

每个 `SELECT` 关键字分配一个唯一的 `id`。

**同一个 SELECT（含连接查询）**：多表的 id 相同，排在前面的是驱动表，后面的是被驱动表：

```sql
EXPLAIN SELECT * FROM s1 INNER JOIN s2;
-- 两条记录 id 都是 1，s1 为驱动表，s2 为被驱动表
```

**包含子查询**：每个 SELECT 各自有不同的 id：

```sql
EXPLAIN SELECT * FROM s1 WHERE key1 IN (SELECT key1 FROM s2) OR key3 = 'a';
-- s1 对应 id=1（PRIMARY），s2 对应 id=2（SUBQUERY）
```

**注意**：查询优化器可能将子查询重写为连接查询，此时所有记录的 id 相同。如果执行计划中子查询的 id 和外层一样，说明优化器做了这个转换。

**UNION 查询**：每个 SELECT 各自有不同 id，`UNION`（需去重）还会出现 id 为 NULL 的临时表记录；`UNION ALL` 不去重，没有临时表。

### select_type

| 值 | 含义 |
|:--|:--|
| `SIMPLE` | 简单查询，不含子查询或 UNION（连接查询也算 SIMPLE）|
| `PRIMARY` | 包含 UNION/子查询的大查询中，最外层的查询 |
| `UNION` | UNION 中第二个及之后的 SELECT |
| `UNION RESULT` | UNION 去重所用临时表 |
| `SUBQUERY` | 不相关子查询（会被物化，只执行一次）|
| `DEPENDENT SUBQUERY` | 相关子查询（可能执行多次）|
| `DEPENDENT UNION` | UNION 中依赖外层查询的第二个及之后的 SELECT |
| `DERIVED` | 派生表（FROM 子句中的子查询，物化执行）|
| `MATERIALIZED` | 子查询被物化后与外层表做连接 |

### table

每条执行计划记录对应一个表的访问方式。`table` 列显示表名，特殊情况：

- `<derivedN>`：id 为 N 的派生表（物化后的子查询）
- `<subqueryN>`：id 为 N 的物化子查询
- `<union1,2>`：UNION 去重用的临时表

### type（访问类型）

**性能从好到差排列**，这是优化查询时最需要关注的列：

| 类型 | 含义 | 典型场景 |
|:--|:--|:--|
| `system` | 表只有一行（MyISAM/Memory 引擎）| 极少见 |
| `const` | 主键或唯一索引等值匹配 | `WHERE id = 5` |
| `eq_ref` | 连接查询中，被驱动表通过主键/唯一索引等值匹配 | `JOIN ON s1.id = s2.id` |
| `ref` | 普通二级索引等值匹配 | `WHERE key1 = 'a'` |
| `ref_or_null` | 与 ref 类似，额外搜索 NULL 值 | `WHERE key1 = 'a' OR key1 IS NULL` |
| `index_merge` | 使用多个索引合并（Intersection/Union/Sort-Union）| `WHERE key1 = 'a' OR key3 = 'a'` |
| `range` | 索引范围扫描 | `WHERE key1 > 'a'`、`WHERE key1 IN ('a','b')` |
| `index` | 扫描整个索引树（覆盖索引但无法用范围/等值）| 查询列和条件都在某个索引中，但条件不是最左前缀 |
| `ALL` | 全表扫描 | 无可用索引 |

**核心口诀**：至少要优化到 `range` 级别，`ref` 及以上更好。出现 `ALL` 应重点排查。

> `unique_subquery` 和 `index_subquery` 是 IN 子查询转 EXISTS 后的特殊类型，实际中较少见。

### possible_keys 与 key

- `possible_keys`：查询中可能使用到的索引
- `key`：优化器最终选择的索引

possible_keys 不为空但 key 为 NULL，说明优化器经过成本计算后认为全表扫描更划算。

有一个特殊情况：`type = index` 时，possible_keys 可能为空而 key 不为空，因为此时虽然用了索引但不是通过正常的搜索条件命中的。

> possible_keys 越多，优化器计算成本的开销越大。应当删除不用的索引。

### key_len

`key_len` 表示实际使用的索引长度（字节数），主要用于**判断联合索引用到了几个列**。

**计算规则**：

| 因素 | 说明 |
|:--|:--|
| 固定长度类型 | INT = 4 字节，BIGINT = 8 字节 |
| 变长类型 | VARCHAR(N) × 字符集字节数（utf8=3, utf8mb4=4）|
| 允许 NULL | 多 1 字节 |
| 变长字段 | 多 2 字节（存储实际长度）|

**示例**（字符集 utf8）：

```
-- INT NOT NULL → key_len = 4
EXPLAIN SELECT * FROM s1 WHERE id = 5;              -- key_len: 4

-- INT（允许 NULL）→ key_len = 5
EXPLAIN SELECT * FROM s1 WHERE key2 = 5;             -- key_len: 5

-- VARCHAR(100)（允许 NULL）→ 100×3 + 1 + 2 = 303
EXPLAIN SELECT * FROM s1 WHERE key1 = 'a';           -- key_len: 303
```

**判断联合索引使用了几列**：

```sql
-- idx_key_part(key_part1, key_part2, key_part3)，每列 VARCHAR(100)

EXPLAIN SELECT * FROM s1 WHERE key_part1 = 'a';
-- key_len: 303 → 只用了 1 列

EXPLAIN SELECT * FROM s1 WHERE key_part1 = 'a' AND key_part2 = 'b';
-- key_len: 606 → 用了 2 列
```

### ref

当 type 为 `const`/`eq_ref`/`ref`/`ref_or_null` 等等值匹配时，ref 列显示与索引列匹配的对象：

- `const`：与常量匹配（如 `WHERE key1 = 'a'`）
- `db.table.column`：与某表的某列匹配（如连接条件 `ON s1.id = s2.id`）
- `func`：与函数返回值匹配（如 `ON s2.key1 = UPPER(s1.key1)`）

### rows 与 filtered

**rows**：预估需要扫描的行数。全表扫描时就是表的总行数估算，使用索引时是满足索引条件的估算行数。

**filtered**：在 rows 条记录中，满足其余搜索条件的百分比。

对于连接查询，**驱动表的扇出 = rows × filtered%**，决定了被驱动表被访问的次数：

```sql
EXPLAIN SELECT * FROM s1 INNER JOIN s2 ON s1.key1 = s2.key1 WHERE s1.common_field = 'a';
-- s1: rows=9688, filtered=10.00 → 扇出 = 968.8
-- 意味着 s2 会被查询约 968 次
```

### Extra

Extra 列提供额外的执行信息，以下是最常见且重要的值：

**Using index（覆盖索引）**

查询的列和条件都在索引中，不需要回表。性能好的标志。

```sql
EXPLAIN SELECT key1 FROM s1 WHERE key1 = 'a';
-- Extra: Using index
```

**Using where**

- 全表扫描 + WHERE 过滤条件
- 使用索引后，还有额外的非索引条件需要过滤

```sql
EXPLAIN SELECT * FROM s1 WHERE common_field = 'a';
-- type: ALL, Extra: Using where

EXPLAIN SELECT * FROM s1 WHERE key1 = 'a' AND common_field = 'a';
-- type: ref, Extra: Using where（key1 走索引，common_field 在服务层过滤）
```

**Using index condition（索引条件下推 ICP）**

索引列上的部分条件无法用于索引范围扫描，但可以在索引层面先过滤，减少回表次数。

```sql
-- key1 > 'z' 走索引范围扫描，key1 LIKE '%b' 在索引层下推过滤
EXPLAIN SELECT * FROM s1 WHERE key1 > 'z' AND key1 LIKE '%b';
-- Extra: Using index condition
```

**Using filesort（文件排序）**

排序无法利用索引，必须在内存或磁盘中完成排序。**性能警告，应尽量优化为索引排序。**

```sql
EXPLAIN SELECT * FROM s1 ORDER BY common_field LIMIT 10;
-- Extra: Using filesort
```

**Using temporary（临时表）**

执行 DISTINCT、GROUP BY、UNION 等操作时无法利用索引，创建了内部临时表。**性能警告，应尽量优化。**

```sql
EXPLAIN SELECT DISTINCT common_field FROM s1;
-- Extra: Using temporary

EXPLAIN SELECT common_field, COUNT(*) FROM s1 GROUP BY common_field;
-- Extra: Using temporary; Using filesort
-- GROUP BY 默认会加 ORDER BY，可追加 ORDER BY NULL 去掉排序
```

用索引列做 GROUP BY 就不需要临时表：

```sql
EXPLAIN SELECT key1, COUNT(*) FROM s1 GROUP BY key1;
-- Extra: Using index（直接扫描索引即可）
```

**Using join buffer (Block Nested Loop)**

连接查询中被驱动表无法有效利用索引，使用了 join buffer 加速。说明被驱动表的连接条件没有索引。

**Using intersect/union/sort_union**

使用了索引合并策略，括号内显示合并的索引名。

**其他值**：

| 值 | 含义 |
|:--|:--|
| `No tables used` | 查询没有 FROM 子句 |
| `Impossible WHERE` | WHERE 条件恒为 FALSE |
| `Not exists` | 左连接中被驱动表条件为 IS NULL，找到一条匹配即可 |
| `Start/End temporary` | semi-join 的 DuplicateWeedout 策略 |
| `LooseScan` | semi-join 的 LooseScan 策略 |
| `FirstMatch(tbl)` | semi-join 的 FirstMatch 策略 |

## 输出格式

除了默认的表格格式，还可以使用 JSON 格式查看更详细的成本信息：

```sql
EXPLAIN FORMAT=JSON SELECT * FROM s1 INNER JOIN s2 ON s1.key1 = s2.key2\G
```

JSON 格式额外提供：
- `cost_info.prefix_cost`：查询到当前表为止的总成本
- `rows_examined_per_scan`：每次扫描的行数
- `rows_produced_per_join`：扇出行数

使用 `EXPLAIN` 后紧接着执行 `SHOW WARNINGS`，可以查看优化器重写后的查询语句（Code=1003），帮助理解优化器的改写行为（如左连接优化为内连接）。
