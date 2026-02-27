# RDB 持久化

RDB 把某个时间点的数据库快照保存为二进制文件。

## SAVE vs BGSAVE

| | SAVE | BGSAVE |
|--|------|--------|
| 执行方式 | 主进程直接执行 | fork 子进程执行 |
| 是否阻塞 | 阻塞，拒绝所有命令 | 不阻塞，父进程继续处理请求 |
| 互斥 | — | 执行期间拒绝再次 SAVE/BGSAVE；BGREWRITEAOF 延迟到 BGSAVE 结束后 |

载入 RDB 文件是在服务器启动时自动进行的。如果开启了 AOF，优先用 AOF 还原；AOF 关闭才用 RDB。

## 自动保存

默认配置（任一条件满足就触发 `BGSAVE`）：

```text
save 900 1      # 900 秒内至少 1 次修改
save 300 10     # 300 秒内至少 10 次修改
save 60 10000   # 60 秒内至少 10000 次修改
```

实现：`dirty` 计数器记录上次保存后的修改次数，`lastsave` 记录上次保存时间。`serverCron` 每 100ms 检查一次条件。

## RDB 文件结构

```text
[REDIS][db_version][databases][EOF][check_sum]
```

- `REDIS`：5 字节魔数
- `db_version`：4 字节版本号
- `databases`：每个非空数据库的数据
  - `SELECTDB | db_number | key_value_pairs`
  - 键值对可带过期时间：`EXPIRETIME_MS | ms_timestamp | TYPE | key | value`
- `EOF`：1 字节结束标记
- `check_sum`：8 字节校验和
