# 线程 API（POSIX）

## 创建线程

```c
int pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                   void *(*start_routine)(void *), void *arg);
```

- `thread`：输出参数，线程标识符
- `attr`：线程属性，一般传 `NULL`（默认属性）
- `start_routine`：线程执行的函数
- `arg`：传给函数的参数（`void *` 类型，需要自己转型）

## 等待线程

```c
int pthread_join(pthread_t thread, void **retval);
```

阻塞等目标线程结束。`retval` 接收线程的返回值。不是所有线程都需要 join——后台干活的线程可以不管。

注意：不要返回指向线程栈上变量的指针——线程结束后栈被回收,指针悬空。

## 互斥锁

```c
pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
// 或 pthread_mutex_init(&lock, NULL);

pthread_mutex_lock(&lock);
// 临界区
pthread_mutex_unlock(&lock);
```

`lock` 和 `unlock` 必须配对。加锁失败会阻塞等待。每次调用都**必须检查返回值**——虽然很多人不检查。

## 条件变量

```c
pthread_cond_t cond = PTHREAD_COND_INITIALIZER;

pthread_cond_wait(&cond, &lock);   // 释放锁+休眠，被唤醒后重新加锁
pthread_cond_signal(&cond);         // 唤醒一个等待者
```

`wait` 必须在持有锁的状态下调用。等待条件时必须用 **while 循环**（不是 if），因为被唤醒后条件可能已经被其他线程改变了。

## 编译

编译时加 `-pthread` 链接线程库。
