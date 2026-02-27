# B+ 树索引的使用

本章基于联合索引 `idx_name_birthday_phone_number(name, birthday, phone_number)` 讨论索引使用规则。B+ 树按 `name → birthday → phone_number` 逐级排序。

![联合索引 B+ 树示意](images/07-01.png)

## 索引的代价

- **空间**：每个索引对应一棵 B+ 树，索引越多占用空间越大。
- **时间**：增删改需同步维护所有 B+ 树的排序，涉及记录移位、页分裂、页回收。索引越多写入越慢。

## 索引的使用条件

### 全值匹配

搜索条件包含联合索引的所有列：

```sql
SELECT * FROM person_info
WHERE name = 'Ashburn' AND birthday = '1990-09-27' AND phone_number = '15123983239';
```

三个列全部命中索引。WHERE 子句中列的书写顺序不影响索引使用——查询优化器会自动调整匹配顺序。

### 最左前缀匹配

只使用联合索引最左边的连续列，也能命中索引：

```sql
-- 命中 name
SELECT * FROM person_info WHERE name = 'Ashburn';
-- 命中 name + birthday
SELECT * FROM person_info WHERE name = 'Ashburn' AND birthday = '1990-09-27';
```

跳过最左列则无法使用索引：

```sql
-- 无法使用 idx_name_birthday_phone_number
SELECT * FROM person_info WHERE birthday = '1990-09-27';
```

原因：B+ 树先按 `name` 排序，`name` 不同时 `birthday` 无序。

跳过中间列时，只能用到中断前的列：

```sql
-- 只用到 name，phone_number 无法命中
SELECT * FROM person_info WHERE name = 'Ashburn' AND phone_number = '15123983239';
```

### 列前缀匹配

字符串按字符逐位排序，因此前缀是有序的：

```sql
-- 命中索引
SELECT * FROM person_info WHERE name LIKE 'As%';
-- 无法命中索引（前缀不确定）
SELECT * FROM person_info WHERE name LIKE '%As%';
```

### 范围查询与索引

索引记录本身有序，天然支持范围查询：

```sql
SELECT * FROM person_info WHERE name > 'Asa' AND name < 'Barlow';
```

但对联合索引的多列同时做范围查询时，只有最左列的范围条件能用到索引：

```sql
-- 只有 name 的范围条件用到索引，birthday 的范围条件无法使用
SELECT * FROM person_info WHERE name > 'Asa' AND name < 'Barlow' AND birthday > '1980-01-01';
```

原因：`name` 范围查找结果中 `name` 值不同，`birthday` 不保证有序。

### 精确匹配某列并范围匹配另一列

左边列精确匹配后，结果集在该列上值相同，右边列仍有序，可继续用索引做范围查找：

```sql
-- name 精确匹配 → birthday 范围命中 → phone_number 无法命中
SELECT * FROM person_info
WHERE name = 'Ashburn'
  AND birthday > '1980-01-01' AND birthday < '2000-12-31'
  AND phone_number > '15100000000';
```

`name` 精确匹配后结果按 `birthday` 排序，`birthday` 范围有效；但范围查找后 `birthday` 值不同，`phone_number` 无序，无法命中。若前两列都精确匹配，第三列也可范围查找：

```sql
-- 三列均命中索引
SELECT * FROM person_info
WHERE name = 'Ashburn' AND birthday = '1980-01-01' AND phone_number > '15100000000';
```

## 索引失效的场景

| 场景 | 示例 | 原因 |
|------|------|------|
| 索引列参与计算/函数 | `WHERE my_col * 2 < 4` | 引擎需逐行计算表达式，无法利用 B+ 树 |
| 跳过最左列 | `WHERE birthday = '...'` | 联合索引先按 name 排序，跳过则无序 |
| 跳过中间列 | `WHERE name = 'A' AND phone = '...'` | 只能用到 name |
| LIKE 左模糊 | `WHERE name LIKE '%As%'` | 前缀不确定，无法利用排序 |
| 排序列 ASC/DESC 混用 | `ORDER BY name ASC, birthday DESC` | B+ 树单方向有序，混用无法直接读取 |
| 排序列不属于同一索引 | `ORDER BY name, country` | 不同索引无法协同排序 |
| 排序列使用函数 | `ORDER BY UPPER(name)` | 函数改变排序依据 |

核心原则：**索引列必须以单独列的形式出现在比较表达式中**。`WHERE my_col < 4/2` 可以用索引，`WHERE my_col * 2 < 4` 不行。

## 回表的代价与覆盖索引

### 回表过程

1. 在二级索引 B+ 树中找到符合条件的记录（**顺序 I/O**，索引记录物理连续）。
2. 取出每条记录的主键 `id`，到聚簇索引中查完整记录（**随机 I/O**，`id` 值不连续，完整记录分散在不同页）。

回表记录越多，随机 I/O 开销越大。当回表行数占比过高时，优化器宁愿全表扫描也不走二级索引。添加 `LIMIT` 可减少回表量，促使优化器选择索引。

### 覆盖索引

查询列全部包含在索引中，无需回表：

```sql
-- 覆盖索引：只查 name, birthday, phone_number
SELECT name, birthday, phone_number FROM person_info
WHERE name > 'Asa' AND name < 'Barlow';
```

排序查询同理——覆盖索引可避免 filesort 和回表的双重开销：

```sql
SELECT name, birthday, phone_number FROM person_info
ORDER BY name, birthday, phone_number;
```

**避免 `SELECT *`，只查需要的列，尽量覆盖索引。**

## 索引用于排序

### filesort vs 索引排序

- **filesort**：将记录加载到内存（或借助磁盘临时文件）进行排序，代价高。
- **索引排序**：B+ 树本身有序，直接按序读取，无需额外排序。

```sql
-- 索引排序：ORDER BY 顺序与索引列顺序一致
SELECT * FROM person_info ORDER BY name, birthday, phone_number LIMIT 10;
```

左边列为常量时，后续列也可用于索引排序：

```sql
-- name 固定后，结果集按 birthday, phone_number 排序
SELECT * FROM person_info WHERE name = 'A' ORDER BY birthday, phone_number LIMIT 10;
```

### 不能使用索引排序的场景

1. **排序列顺序与索引列顺序不一致**：`ORDER BY phone_number, birthday, name` 无法使用索引。
2. **ASC/DESC 混用**：`ORDER BY name ASC, birthday DESC` 无法使用索引。B+ 树全升序或全降序扫描均可，但混合方向不行。
3. **WHERE 使用了非索引列过滤**：`WHERE country = 'China' ORDER BY name` 无法使用索引排序（`country` 不在索引中）。
4. **排序列来自不同索引**：`ORDER BY name, country` 中两列不属于同一索引。
5. **排序列使用表达式或函数**：`ORDER BY UPPER(name)` 无法使用索引。

## 索引用于分组

GROUP BY 原理与排序类似。B+ 树索引已排好序，相同值自然聚集，可直接分组：

```sql
SELECT name, birthday, phone_number, COUNT(*)
FROM person_info
GROUP BY name, birthday, phone_number;
```

规则与排序相同：分组列顺序必须与索引列顺序一致，可只使用左边的连续列。

## 索引设计原则

### 只为搜索、排序、分组的列建索引

只为 `WHERE`、`JOIN`、`ORDER BY`、`GROUP BY` 中出现的列创建索引。查询列表中的列不需要单独建索引。

### 选择区分度高的列

列的基数（不重复值个数）越大，索引越有效。基数极低的列建索引无意义，且会产生大量回表。

### 索引列类型尽量小

类型越小，比较越快，单页容纳更多记录，减少 I/O。对主键尤为重要——主键值存储在所有二级索引中。能用 `INT` 就不用 `BIGINT`。

### 使用前缀索引

对长字符串只索引前 N 个字符，节省空间并加速比较：

```sql
KEY idx_name_birthday_phone_number (name(10), birthday, phone_number)
```

代价：前缀索引无法支持索引排序。

### 主键自增

主键值递增插入时，记录依次追加到页尾，不会触发页分裂。主键值若忽大忽小，插入已满的页面会导致页分裂和记录移位，带来性能损耗。

![页分裂示意](images/07-02.png)

建议主键使用 `AUTO_INCREMENT`：

```sql
id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY
```

### 避免冗余和重复索引

联合索引 `(name, birthday, phone_number)` 已覆盖对 `name` 的搜索，无需再单独建索引。同一列同时定义主键、唯一索引、普通索引属于重复索引，应清理。

### 优先覆盖索引

设计索引时考虑常用查询列，让查询只访问索引即可获取全部所需数据。
