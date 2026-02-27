# 锁

锁提供互斥——同一时刻只有一个线程能持有锁。拿不到锁的线程要么自旋等待，要么休眠。

评价一个锁实现看三点：**正确性**（是否真的互斥）、**公平性**（是否有线程饿死）、**性能**（开销多大）。

## 关中断

最简单的方案：进临界区前关中断，出来再开。

问题一堆：只对单处理器有用；恶意程序可以关中断后死循环独占 CPU；关中断期间 I/O 信号全丢；现代多处理器上根本不可行。OS 内部访问自己的数据结构时偶尔会用。

## 自旋锁

### Test-And-Set（原子交换）

```c
int TestAndSet(int *old_ptr, int new) {
    int old = *old_ptr;
    *old_ptr = new;
    return old;  // 整个操作是原子的
}
```

锁的实现：`while (TestAndSet(&flag, 1) == 1);`（自旋等待 flag 变 0）。解锁时 `flag = 0`。

正确，但不公平（饿死可能），单 CPU 上性能差（自旋浪费整个时间片）。

### Compare-And-Swap（CAS）

```c
int CompareAndSwap(int *ptr, int expected, int new) {
    int actual = *ptr;
    if (actual == expected) *ptr = new;
    return actual;
}
```

只有 `*ptr == expected` 时才更新。做锁效果和 TAS 相同，但 CAS 更通用——是无锁数据结构的基础。

### Fetch-And-Add → 票锁

```c
int FetchAndAdd(int *ptr) {
    int old = *ptr;
    *ptr = old + 1;
    return old;
}
```

票锁（ticket lock）：每个线程取号（`FetchAndAdd(&ticket)`），然后等轮到自己的号（`while (turn != myticket)`）。**保证公平**——先来先服务。

## 自旋的问题

自旋锁在等待时疯狂烧 CPU。单 CPU 上尤其浪费：持有锁的线程被抢占后，其他线程自旋一整个时间片。

简单改进：拿不到锁就 `yield()`（主动让出 CPU）。比纯自旋好，但线程多时仍有大量无效切换。

## 基于队列的休眠锁

真正高效的方案：拿不到锁就休眠，锁释放时被唤醒。

Solaris 提供 `park()`（休眠）和 `unpark(tid)`（唤醒指定线程）。实现要点：

1. 用一个 guard 自旋锁保护锁内部的队列操作（只自旋极短时间）
2. 拿不到锁时把自己加入等待队列，然后 `park()` 休眠
3. 释放锁时如果队列非空，`unpark()` 唤醒队首线程
4. 有个"唤醒/等待竞争"问题：线程 A 准备 park 但还没睡，线程 B 已经 unpark 了 → A 永远睡过去。Solaris 用 `setpark()` 解决——调用后如果被 unpark，下次 `park()` 立即返回

## Linux futex

Linux 的 `futex`（fast userspace mutex）在用户空间和内核之间分工：

- `futex_wait(addr, expected)`：如果 `*addr == expected` 就休眠，否则立即返回
- `futex_wake(addr)`：唤醒一个在 addr 上等待的线程

glibc 的 nptl 锁实现用一个 32 位整数：最高位表示锁是否被持有，其余位是等待者计数。无竞争情况下一次原子操作就够了（快路径），有竞争才走系统调用休眠（慢路径）。

## 两阶段锁

先自旋一小会儿（赌锁很快释放），如果还拿不到再休眠。结合了自旋锁的低延迟和休眠锁的低浪费。Linux 的 futex 锁就是这个思路。
