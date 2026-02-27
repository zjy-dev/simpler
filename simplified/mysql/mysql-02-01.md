# 单表访问方法

MySQL 查询优化器在执行单表查询时，会选择不同的**访问方法**（access method）来获取数据。访问方法的选择直接决定查询性能。

下文以 `single_table` 表为例。索引：聚簇索引（id）、普通二级索引 idx_key1（key1）、唯一二级索引 idx_key2（key2）、普通二级索引 idx_key3（key3）、联合索引 idx_key_part（key_part1, key_part2, key_part3）。

## 访问方法概述

单表查询的执行方式分两大类：

- **全表扫描**：逐行遍历聚簇索引，逐条匹配搜索条件。代价最高。
- **索引查询**：利用索引快速定位记录，细分为以下几种访问方法。

性能排序（由优到劣）：`const` > `ref` > `ref_or_null` > `range` > `index` > `ALL`

## const

通过**主键**或**唯一二级索引**与常数进行等值比较，最多定位一条记录。

```sql
SELECT * FROM single_table WHERE id = 1438;
SELECT * FROM single_table WHERE key2 = 3841;
```

![](images/10-01.png)

![](images/10-02.png)

- 主键直接在聚簇索引定位；唯一二级索引先定位再回表。
- 联合唯一索引必须**所有列都等值匹配**才能用 const。
- `WHERE key2 IS NULL` 不能用 const——唯一索引不限制 NULL 数量，可能匹配多行。

## ref

通过**普通二级索引**与常数进行等值比较。可能匹配多条连续记录，需逐一回表。

```sql
SELECT * FROM single_table WHERE key1 = 'abc';
```

![](images/10-03.png)

- 效率取决于匹配的记录条数，越少回表代价越低。
- `key IS NULL` 最多用 ref，不能用 const。
- 联合索引只要**最左连续列都是等值匹配**即可用 ref。若中间出现范围匹配则不行。

## ref_or_null

在 ref 基础上额外检索索引列为 NULL 的记录。

```sql
SELECT * FROM single_table WHERE key1 = 'abc' OR key1 IS NULL;
```

![](images/10-04.png)

相当于在二级索引 B+ 树中找出 `key1 IS NULL` 和 `key1 = 'abc'` 两个连续范围的记录，再回表。

## range

索引列与常数进行**范围匹配**，包括 `=`、`IN`、`IS NULL`、`>`、`<`、`>=`、`<=`、`BETWEEN`、`!=`、`LIKE 前缀匹配` 等操作符产生的区间。

```sql
SELECT * FROM single_table WHERE key2 IN (1438, 6328) OR (key2 >= 38 AND key2 <= 79);
```

![](images/10-05.png)

上述查询产生三个范围区间：`key2 = 1438`（单点区间）、`key2 = 6328`（单点区间）、`key2 ∈ [38, 79]`（连续范围区间）。

**范围区间的确定规则：**

- 多条件用 AND 连接 → 取各区间**交集**
- 多条件用 OR 连接 → 取各区间**并集**
- 无法使用当前索引的搜索条件替换为 TRUE 后化简
- 若化简结果为 `(-∞, +∞)` 则该索引不值得使用

典型场景：一个索引条件 OR 一个非索引条件 → 化简后区间为全部，不走索引。

```sql
-- 化简：key2 > 100 OR TRUE → TRUE → 全表扫描
SELECT * FROM single_table WHERE key2 > 100 OR common_field = 'abc';
```

## index

遍历二级索引的全部叶子节点，不回表。适用条件：

1. 查询列全部包含在某个二级索引中（覆盖索引）
2. 搜索条件列也包含在该索引中

```sql
SELECT key_part1, key_part2, key_part3 FROM single_table WHERE key_part2 = 'abc';
```

`key_part2` 不是联合索引最左列，无法用 ref/range，但查询列和条件列都在 idx_key_part 中。直接遍历二级索引比遍历聚簇索引代价小得多（二级索引记录更紧凑，且无需回表）。

## ALL

全表扫描，直接遍历聚簇索引所有记录。所有查询都可以用这种方式执行，但代价最高。

## 二级索引 + 回表的执行流程

一般情况下一条查询**只使用一个二级索引**。以 `WHERE key1 = 'abc' AND key2 > 1000` 为例：优化器选扫描行数更少的索引（假设 idx_key1）→ 取出匹配记录 → 回表取完整行 → 用剩余条件 `key2 > 1000` 过滤。

关键点：**索引定位阶段只能用当前索引相关的条件，其余条件在回表后才能过滤。**

## Index Merge（索引合并）

特殊情况下，MySQL 可以同时使用多个二级索引完成查询，称为索引合并。

### Intersection（交集合并）

适用于多个搜索条件用 **AND** 连接的场景。

```sql
SELECT * FROM single_table WHERE key1 = 'a' AND key3 = 'b';
```

执行过程：分别从 idx_key1 和 idx_key3 取出主键值集合 → 求主键交集 → 按交集结果回表。

使用条件：

- 二级索引列必须**等值匹配**（联合索引每列都要匹配完整）
- 主键列可以范围匹配（直接在二级索引结果上过滤）

**原理：** 等值匹配时二级索引结果集天然按主键排序，两个有序集合求交集只需 O(n) 归并。非等值匹配则主键无序，排序代价太高。按有序主键回表称为 **ROR**（Rowid Ordered Retrieval）。

### Union（并集合并）

适用于多个搜索条件用 **OR** 连接的场景。

```sql
SELECT * FROM single_table WHERE key1 = 'a' OR key3 = 'b';
```

使用条件与 Intersection 类似：二级索引列等值匹配、主键可范围匹配。另外搜索条件的部分子集可以先 Intersection 合并再参与 Union。原理相同——等值匹配保证主键有序，求并集 O(n)。

### Sort-Union（排序并集合并）

放宽了 Union 的等值匹配限制，允许范围条件。

```sql
SELECT * FROM single_table WHERE key1 < 'a' OR key3 > 'z';
```

执行过程：分别从各二级索引取出记录 → **按主键排序** → 按 Union 方式求并集 → 回表。

多了一步主键排序，但因为范围条件获取的记录通常不多，排序代价可接受。

> **为什么没有 Sort-Intersection？** Intersection 的场景是单索引匹配记录太多才需要合并减少回表量。而大量记录的排序代价可能比直接回表还高，因此没有引入 Sort-Intersection。

## 注意事项

- 索引合并发生的条件是**必要条件而非充分条件**，最终由优化器根据成本估算决定。
- 如果查询经常触发 Intersection 合并，优先考虑建**联合索引**替代多个单列索引，避免多棵 B+ 树的额外开销。
- 索引列 OR 非索引列的条件组合无法使用该索引（化简后区间为全集）。
- 回表操作是**随机 I/O**，二级索引扫描是**顺序 I/O**。当回表记录数过多时，全表扫描可能反而更快。
