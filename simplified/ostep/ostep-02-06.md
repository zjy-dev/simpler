# 信号量

信号量（semaphore）是 Dijkstra 提出的同步原语。一个信号量就是一个带等待队列的整数。

## 基本操作

```c
sem_init(&s, 0, value);  // 初始化为 value（第二个参数 0 表示线程间共享）
sem_wait(&s);             // 值减 1，如果减完 < 0 就休眠
sem_post(&s);             // 值加 1，如果有人在等就唤醒一个
```

信号量的值为负数时，绝对值就是等待队列里的线程数。

## 当锁用

初始值设为 1（二值信号量）。`sem_wait` 拿锁，`sem_post` 放锁。

```c
sem_t lock;
sem_init(&lock, 0, 1);
sem_wait(&lock);    // 值 1→0，拿到锁
// 临界区
sem_post(&lock);    // 值 0→1，释放锁
```

## 当条件变量用

初始值设为 0。`sem_wait` 等待，`sem_post` 通知。

用来做线程间排序：父线程 `sem_wait(&s)` 等子线程完成，子线程完成后 `sem_post(&s)`。

## 生产者/消费者

需要三个信号量：

```c
sem_t empty, full, mutex;
sem_init(&empty, 0, MAX);  // 空槽数量
sem_init(&full, 0, 0);     // 有数据的槽数量
sem_init(&mutex, 0, 1);    // 互斥（保护缓冲区操作）
```

```c
// 生产者
sem_wait(&empty);     // 等空槽（必须在 mutex 外面！）
sem_wait(&mutex);
put(value);
sem_post(&mutex);
sem_post(&full);      // 通知消费者

// 消费者
sem_wait(&full);      // 等有数据（必须在 mutex 外面！）
sem_wait(&mutex);
int val = get();
sem_post(&mutex);
sem_post(&empty);     // 通知生产者
```

`mutex` 必须在 `empty`/`full` 的**里面**。如果反过来，消费者持有 mutex 等 full，生产者持有 empty 等 mutex → 死锁。

## 读者-写者锁

多个读者可以同时读，写者需要独占。

```c
typedef struct {
    sem_t lock;       // 保护 readers 计数
    sem_t writelock;  // 写者锁
    int readers;
} rwlock_t;
```

第一个读者进入时获取 `writelock`（挡住写者），最后一个读者离开时释放 `writelock`。

问题：持续有读者进入时写者会饿死。

## 哲学家就餐

5 个哲学家围坐，每人左右各一把叉子（共 5 把），吃饭需要两把。每把叉子是一个信号量。

如果都先拿左边再拿右边 → 环形等待 → 死锁。

解法：让最后一个哲学家先拿右边再拿左边（打破环形等待）。

## 用锁和条件变量实现信号量

```c
typedef struct {
    int value;
    pthread_cond_t cond;
    pthread_mutex_t lock;
} Zem_t;

void Zem_wait(Zem_t *s) {
    pthread_mutex_lock(&s->lock);
    while (s->value <= 0)
        pthread_cond_wait(&s->cond, &s->lock);
    s->value--;
    pthread_mutex_unlock(&s->lock);
}

void Zem_post(Zem_t *s) {
    pthread_mutex_lock(&s->lock);
    s->value++;
    pthread_cond_signal(&s->cond);
    pthread_mutex_unlock(&s->lock);
}
```

这个实现的 value 不会小于 0（和 Linux 的 `sem_wait` 语义略有不同，Dijkstra 原始定义允许负值）。
