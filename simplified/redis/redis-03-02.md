# Sentinel

Sentinel（哨兵）监控 Redis 主从服务器，主服务器挂了就自动做故障转移。

## 启动与初始化

Sentinel 本质上是运行在特殊模式下的 Redis 服务器，不使用数据库功能，不载入 RDB/AOF。启动后根据配置文件中的主服务器地址建立连接，自动发现该主服务器的所有从服务器和其他 Sentinel。

每个 Sentinel 对每个被监控的主/从服务器建立两条连接：

- **命令连接**：发送命令并接收回复
- **订阅连接**：订阅 `__sentinel__:hello` 频道，用于 Sentinel 之间互相发现

## 监控

- 每 10 秒向主/从服务器发 `INFO`，获取当前信息（从服务器列表、角色、偏移量等）
- 每 2 秒通过 `__sentinel__:hello` 频道发布自己的信息和主服务器信息
- 每 1 秒向所有主/从服务器和其他 Sentinel 发 `PING`，检测存活

## 下线判断

**主观下线（SDOWN）**：一个 Sentinel 在 `down-after-milliseconds` 内没收到有效回复，判定目标主观下线。

**客观下线（ODOWN）**：Sentinel 向其他 Sentinel 询问（`SENTINEL is-master-down-by-addr`），如果足够多数量的 Sentinel 都同意下线（`quorum` 配置），判定客观下线。客观下线判断只针对主服务器。

## 选举 Leader

主服务器被判定客观下线后，Sentinel 之间需要选出一个 Leader 来执行故障转移。算法和 Raft 的领头选举类似：

- 每个 Sentinel 在每个配置纪元中有一票，先到先得
- 收到投票请求后，把票投给第一个请求的 Sentinel
- 获得半数以上票的 Sentinel 成为 Leader
- 如果这一轮没选出来，等一段时间后重新开始

## 故障转移

Leader Sentinel 执行三步：

1. **选新主服务器**：从下线主服务器的从服务器中挑选——排除断线的、最近没有回复 INFO 的，然后按优先级→复制偏移量→runID 排序，选最合适的
2. **让新主服务器转换角色**：向选中的从服务器发 `SLAVEOF no one`，然后持续发 `INFO` 确认它已经变成主服务器
3. **让其他从服务器复制新主**：向剩余从服务器发 `SLAVEOF <新主 IP> <新主端口>`
4. **将旧主设为从服务器**：在旧主服务器的实例结构中设置目标，等它重新上线时向它发 `SLAVEOF`
