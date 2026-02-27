# 集群

Redis Cluster 把数据分片存到多个节点上，节点之间互为备份。

## 节点

每个节点就是一个运行在集群模式下的 Redis 服务器。通过 `CLUSTER MEET <ip> <port>` 让节点握手加入集群。节点之间用 Gossip 协议通信，信息在集群中扩散传播。

## 槽指派

集群一共有 **16384 个槽**（slot），所有槽全部分配完毕后集群才能上线。

每个节点用一个 16384 位的位数组 `slots` 记录自己负责哪些槽——第 i 位为 1 表示负责槽 i。同时 `clusterState.slots[i]` 数组直接指向负责该槽的节点，查找 O(1)。

键到槽的映射：

```text
slot = CRC16(key) & 16383
```

## MOVED 与 ASK

**MOVED**：客户端请求的键不在当前节点。节点回复 `MOVED <slot> <ip>:<port>`，客户端转向目标节点重新请求，**并更新本地槽映射缓存**。

**ASK**：槽正在迁移中，键已经转移到目标节点。回复 `ASK <slot> <ip>:<port>`，客户端先向目标节点发 `ASKING`，再发命令。ASK 是一次性的，**不更新本地缓存**。

## 重新分片

在线操作，不需要停机。由 `redis-trib` 工具驱动：

1. 通知目标节点准备导入槽（`CLUSTER SETSLOT <slot> IMPORTING <source_id>`）
2. 通知源节点准备迁出槽（`CLUSTER SETSLOT <slot> MIGRATING <target_id>`）
3. 源节点逐个获取键（`CLUSTER GETKEYSINSLOT`），然后 `MIGRATE` 到目标节点
4. 全部迁移完毕后 `CLUSTER SETSLOT <slot> NODE <target_id>` 通知所有节点

## 故障检测

集群节点定期互相发 `PING`：

- **PFAIL（疑似下线）**：节点 A 在超时时间内没收到节点 B 的回复，A 把 B 标记为 PFAIL
- **FAIL（已下线）**：半数以上负责槽的主节点都把 B 标记为 PFAIL，那么 B 被标记为 FAIL，并广播到整个集群

## 故障转移

下线主节点的从节点发起选举：

1. 从节点广播 `CLUSTERMSG_TYPE_FAILOVER_AUTH_REQUEST`
2. 只有负责槽的主节点有投票权，每个配置纪元一票
3. 获得半数以上票的从节点成为新主
4. 新主接管原主的所有槽并广播 `PONG`

从节点选举优先级：复制偏移量最大的（数据最新的）从节点更容易先发起选举。

## Gossip 协议

节点间通过 Gossip 消息交换状态：

| 消息类型 | 用途 |
|----------|------|
| MEET | 通知接收方加入集群 |
| PING | 检测在线状态，随机选若干节点 |
| PONG | 回复 MEET/PING，或广播自身信息 |
| FAIL | 广播某节点已下线 |
| PUBLISH | 向集群所有节点广播消息 |
