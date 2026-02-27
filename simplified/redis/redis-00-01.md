# 常用命令速查

面试和日常开发中最常碰到的 Redis 命令，按数据结构分类。

## 连接与服务器

```text
AUTH password                   # 密码认证
AUTH username password          # Redis 6+ ACL 认证
PING                            # 测试连通，返回 PONG
SELECT db                       # 切换数据库（默认 0~15）
INFO [section]                  # 服务器状态信息
DBSIZE                          # 当前库的键数量
FLUSHDB [ASYNC]                 # 清空当前库
FLUSHALL [ASYNC]                # 清空所有库
CLIENT LIST                     # 查看所有连接
CONFIG GET/SET param            # 读/写运行时配置
SLOWLOG GET [n]                 # 查看慢查询日志
```

## 键管理

```text
DEL key [key ...]               # 同步删除
UNLINK key [key ...]            # 异步删除（非阻塞，4.0+）
EXISTS key [key ...]            # 返回存在的键数量
TYPE key                        # 返回值类型
RENAME key newkey               # 重命名
COPY source dest [REPLACE]      # 复制键（6.2+）

EXPIRE key seconds              # 设置秒级过期
PEXPIRE key ms                  # 毫秒级过期
EXPIREAT key timestamp          # 指定过期时间点
PERSIST key                     # 移除过期时间
TTL key                         # 剩余秒数（-1 永不过期，-2 不存在）
PTTL key                        # 剩余毫秒数

SCAN cursor [MATCH pat] [COUNT n]  # 增量遍历（生产环境别用 KEYS）
OBJECT ENCODING key             # 查看底层编码
OBJECT IDLETIME key             # 空转时间
```

## String

最基础的类型，值可以是字符串、整数或浮点数。

```text
SET key value [EX s | PX ms] [NX|XX] [KEEPTTL]  # 核心写命令
GET key                         # 读
GETDEL key                      # 读完就删（6.2+）
GETEX key [EX s|PX ms|PERSIST]  # 读并改过期（6.2+）

MSET k1 v1 k2 v2 ...           # 批量写
MGET k1 k2 ...                  # 批量读

INCR key                        # +1（原子操作）
DECR key                        # -1
INCRBY key n                    # +n
DECRBY key n                    # -n
INCRBYFLOAT key f               # +浮点数

SETNX key value                 # 不存在才写（等价于 SET ... NX）
SETEX key seconds value         # 写+设过期（等价于 SET ... EX）

APPEND key value                # 追加字符串
STRLEN key                      # 字符串长度
GETRANGE key start end          # 截取子串
SETRANGE key offset value       # 覆盖子串
```

SET 的选项组合：
- `SET key value NX EX 30`：分布式锁的标准写法——不存在才写，30 秒自动过期
- `SET key value XX KEEPTTL`：仅覆盖已有键，保留原 TTL

## Hash

适合存对象，比如用户信息 `user:1001 → {name: ..., age: ...}`。

```text
HSET key field value [field value ...]   # 写字段（支持批量，4.0+）
HGET key field                  # 读单个字段
HMGET key f1 f2 ...             # 读多个字段
HGETALL key                     # 读全部字段+值（键多时小心阻塞）
HDEL key field [field ...]      # 删字段
HEXISTS key field               # 字段是否存在
HLEN key                        # 字段数量
HINCRBY key field n             # 字段值 +n
HINCRBYFLOAT key field f        # 字段值 +浮点数
HKEYS key                       # 所有字段名
HVALS key                       # 所有字段值
HSCAN key cursor [MATCH] [COUNT]  # 增量遍历字段
HRANDFIELD key [count]          # 随机返回字段（6.2+）
```

## List

双端队列，左右都能推入弹出。

```text
LPUSH key value [value ...]     # 左端推入
RPUSH key value [value ...]     # 右端推入
LPOP key [count]                # 左端弹出（count 参数 6.2+）
RPOP key [count]                # 右端弹出

LRANGE key start stop           # 范围读取（0 -1 读全部）
LINDEX key index                # 按索引读
LLEN key                        # 长度
LPOS key value                  # 查找值的索引（6.0.6+）

LSET key index value            # 按索引写
LREM key count value            # 删除 count 个匹配元素
LTRIM key start stop            # 只保留指定范围

LMOVE src dst LEFT|RIGHT LEFT|RIGHT   # 原子弹出并推入另一个列表（6.2+）

BLPOP key [key ...] timeout     # 阻塞左弹出（用作消息队列）
BRPOP key [key ...] timeout     # 阻塞右弹出
BLMOVE src dst ... timeout      # 阻塞版 LMOVE（6.2+）
```

典型用法：
- 消息队列：LPUSH 生产 + BRPOP 消费
- 最新 N 条记录：LPUSH + LTRIM

## Set

无序集合，自动去重，支持交并差运算。

```text
SADD key member [member ...]    # 添加
SREM key member [member ...]    # 移除
SISMEMBER key member            # 是否存在
SMISMEMBER key m1 m2 ...        # 批量判断（6.2+）
SMEMBERS key                    # 返回所有成员
SCARD key                       # 成员数
SRANDMEMBER key [count]         # 随机取成员（不删除）
SPOP key [count]                # 随机弹出（会删除）

SINTER key [key ...]            # 交集
SUNION key [key ...]            # 并集
SDIFF key [key ...]             # 差集（第一个集合减去其余）
SINTERCARD numkeys key [key ...] [LIMIT n]  # 交集大小（7.0+）
SINTERSTORE dest key [key ...]  # 交集结果存到 dest
```

典型用法：
- 共同关注：SINTER user:A:follows user:B:follows
- 抽奖：SPOP / SRANDMEMBER

## Sorted Set

有序集合，每个成员关联一个分值，自动按分值排序。

```text
ZADD key [NX|XX] [GT|LT] [CH] score member [score member ...]
                                # GT/LT：只在新分值更大/更小时更新（6.2+）
                                # CH：返回被修改的成员数而非新增数
ZREM key member [member ...]    # 删除
ZSCORE key member               # 查分值
ZMSCORE key m1 m2 ...           # 批量查分值（6.2+）
ZRANK key member                # 正序排名（从 0 开始）
ZREVRANK key member             # 倒序排名
ZINCRBY key increment member    # 分值 +increment
ZCARD key                       # 成员数
ZCOUNT key min max              # 分值在 [min, max] 的成员数

ZRANGE key min max [BYSCORE|BYLEX] [REV] [LIMIT offset count]
                                # 7.0 统一了范围查询语法
                                # 按排名：ZRANGE key 0 -1
                                # 按分值：ZRANGE key 0 100 BYSCORE
                                # 倒序：  ZRANGE key 0 -1 REV
ZRANGESTORE dst src min max ... # 范围查询结果存到 dst（6.2+）

ZPOPMIN key [count]             # 弹出分值最小的
ZPOPMAX key [count]             # 弹出分值最大的
BZPOPMIN key [key ...] timeout  # 阻塞版
ZRANDMEMBER key [count]         # 随机取成员（6.2+）

ZUNIONSTORE dest numkeys key [key ...] [WEIGHTS ...] [AGGREGATE SUM|MIN|MAX]
ZINTERSTORE dest numkeys key [key ...]
```

典型用法：
- 排行榜：ZADD + ZRANGE REV + ZRANK
- 延迟队列：ZADD 用时间戳做分值 + BZPOPMIN

## HyperLogLog

基数估算，不存储实际元素，标准误差 0.81%，每个键只占 12KB。

```text
PFADD key element [element ...] # 添加元素
PFCOUNT key [key ...]           # 估算基数（多个键时取并集）
PFMERGE dest key [key ...]      # 合并多个 HLL
```

典型用法：统计 UV。PFADD 把每次访问的 user_id 记进去，PFCOUNT 读 UV 数。

## Bitmap

字符串类型的位操作接口，每个 bit 位可以独立读写。

```text
SETBIT key offset 0|1           # 设置某一位
GETBIT key offset               # 读某一位
BITCOUNT key [start end [BYTE|BIT]]   # 统计值为 1 的位数
BITPOS key 0|1 [start end [BYTE|BIT]] # 第一个 0 或 1 的位置
BITOP AND|OR|XOR|NOT dest key [key ...]  # 位运算
BITFIELD key GET type offset | SET type offset value | INCRBY type offset increment
                                # 多位整数操作
```

典型用法：用户签到。每人一个 key，offset = 年内第几天。SETBIT 签到，BITCOUNT 统计次数。

## Geo

基于 Sorted Set，用 Geohash 编码经纬度作为分值。

```text
GEOADD key [NX|XX] [CH] lng lat member [lng lat member ...]
GEODIST key m1 m2 [m|km|mi|ft] # 两点距离
GEOPOS key member [member ...]  # 查经纬度
GEOHASH key member [member ...] # 查 Geohash 值
GEOSEARCH key FROMMEMBER m | FROMLONLAT lng lat
    BYRADIUS r m|km | BYBOX w h m|km [ASC|DESC] [COUNT n]
                                # 范围搜索（6.2+，取代旧的 GEORADIUS）
GEOSEARCHSTORE dest src ...     # 搜索结果存到 dest
```

典型用法：附近的人/店。GEOADD 存位置，GEOSEARCH BYRADIUS 查附近。

## Stream

Redis 5.0 引入的日志型数据结构，比 List 做消息队列靠谱得多。支持消费者组、消息确认和待处理列表。

```text
XADD key [NOMKSTREAM] [MAXLEN|MINID [=|~] threshold] *|id field value [field value ...]
                                # 写消息，* 自动生成 ID
XLEN key                        # 消息数量
XRANGE key start end [COUNT n]  # 正序范围读（- + 表示最小最大）
XREVRANGE key end start [COUNT n]  # 倒序
XREAD [COUNT n] [BLOCK ms] STREAMS key [key ...] id [id ...]
                                # 读新消息（BLOCK 0 = 永久阻塞）

# 消费者组
XGROUP CREATE key group id|$ [MKSTREAM]    # 创建消费者组
XREADGROUP GROUP group consumer [COUNT n] [BLOCK ms] STREAMS key > 
                                # 组内消费（> = 未分配的新消息）
XACK key group id [id ...]      # 确认消息
XPENDING key group [IDLE ms] start end count [consumer]
                                # 查看未确认消息
XCLAIM key group consumer min-idle-time id [id ...]
                                # 转移超时消息给其他消费者
XAUTOCLAIM key group consumer min-idle-time start [COUNT n]
                                # 自动转移（6.2+）
XTRIM key MAXLEN|MINID [=|~] threshold  # 裁剪
XINFO STREAM|GROUPS|CONSUMERS key [group]  # 查看元信息
```

与 List 消息队列的区别：
- 消息持久化，消费后不丢失
- 支持多消费者组独立消费同一条流
- 有 ACK 机制，消费失败可重试
- 有消息 ID，可以回溯

## Pub/Sub

发布订阅，消息即发即弃，不持久化，离线的订阅者收不到。

```text
SUBSCRIBE channel [channel ...] # 订阅频道
UNSUBSCRIBE [channel ...]       # 退订
PUBLISH channel message         # 发布消息（返回收到的订阅者数）
PSUBSCRIBE pattern [pattern ...]  # 按模式订阅（如 news.*）
```

需要可靠投递就用 Stream，Pub/Sub 适合实时通知这类丢了也无所谓的场景。

## 事务与脚本

```text
# 事务
MULTI                           # 开启事务
...命令入队...
EXEC                            # 执行
DISCARD                         # 放弃
WATCH key [key ...]             # 乐观锁，EXEC 前键被改则事务失败

# Lua 脚本
EVAL "lua代码" numkeys key [key ...] arg [arg ...]
EVALSHA sha1 numkeys ...        # 用 SHA1 缓存调脚本
EVALRO / EVALSHA_RO             # 只读脚本（7.0+）

# Redis Functions（7.0+，取代 EVAL）
FUNCTION LOAD [REPLACE] "library代码"
FCALL function numkeys key [key ...] arg [arg ...]
FCALL_RO ...                    # 只读调用
FUNCTION LIST / DELETE / DUMP / RESTORE
```

EVAL 里的 Lua 脚本在 Redis 单线程上原子执行，非常适合需要多步操作保持原子性的场景（比如「读→判断→写」）。7.0 的 Functions 把脚本当一等公民管理，比裸 EVAL 方便持久化和分发。
