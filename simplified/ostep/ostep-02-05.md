# 条件变量

锁解决互斥，条件变量解决**等待**——线程需要等某个条件成立才能继续。

## 基本操作

```c
pthread_cond_wait(cond, mutex);   // 原子地释放 mutex 并休眠，被唤醒后重新获取 mutex
pthread_cond_signal(cond);        // 唤醒一个等待在 cond 上的线程
pthread_cond_broadcast(cond);     // 唤醒所有等待者
```

### 等待时必须用 while，不能用 if

```c
pthread_mutex_lock(&m);
while (!condition) {              // 必须用 while
    pthread_cond_wait(&cond, &m);
}
// 条件满足，执行操作
pthread_mutex_unlock(&m);
```

原因：**Mesa 语义**。`signal` 只是一个提示（"条件可能满足了"），被唤醒的线程不一定能立即运行，等它拿到锁开始跑的时候，条件可能又被别的线程改掉了。所以唤醒后必须重新检查条件。

（Hoare 语义保证唤醒后立即运行，条件一定成立。但几乎没有系统实现它。）

## 生产者/消费者（有界缓冲区）

经典并发问题。生产者往缓冲区放东西，消费者从里面取。缓冲区满了生产者等，空了消费者等。

### 错误写法演进

**单条件变量 + if**：消费者 A 被生产者唤醒，但消费者 B 在 A 之前先跑了并取走了数据，A 拿到锁时缓冲区又空了——坏了。

**单条件变量 + while**：条件检查没问题了，但消费者可能唤醒消费者（不是生产者），大家全在睡觉——死了。

### 最终方案

两个条件变量：`empty` 和 `fill`。

```c
// 全局
int buffer[MAX];
int count = 0, fill_ptr = 0, use_ptr = 0;

// 生产者
pthread_mutex_lock(&mutex);
while (count == MAX)
    pthread_cond_wait(&empty, &mutex);  // 缓冲区满了，等消费者
put(value);
pthread_cond_signal(&fill);             // 通知消费者有数据了
pthread_mutex_unlock(&mutex);

// 消费者
pthread_mutex_lock(&mutex);
while (count == 0)
    pthread_cond_wait(&fill, &mutex);   // 缓冲区空了，等生产者
int val = get();
pthread_cond_signal(&empty);            // 通知生产者有空间了
pthread_mutex_unlock(&mutex);
```

两个条件变量保证：消费者只唤醒生产者，生产者只唤醒消费者。

## 覆盖条件

有时候不知道该唤醒哪个等待者。比如内存分配器：线程 A 等 100 字节，线程 B 等 10 字节，释放了 50 字节应该唤醒谁？

保守方案：用 `pthread_cond_broadcast` 唤醒所有人，每个人自己检查条件。被称为**覆盖条件**（covering condition）。代价是可能唤醒很多不必要的线程，但保证正确。
