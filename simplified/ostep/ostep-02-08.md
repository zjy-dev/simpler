# 基于事件的并发

除了线程，还有另一种并发模型：**事件循环**（event loop）。Node.js、Redis 都用这种方式。

## 事件循环

```python
while True:
    events = getEvents()    # 获取就绪事件
    for e in events:
        processEvent(e)     # 逐个处理
```

核心思路：单线程，一次处理一个事件，不需要锁（单 CPU 下没有并发访问共享数据的问题）。

## select()/poll()

事件循环需要知道哪些 I/O 就绪了。POSIX 的 `select()` / `poll()` 提供这个能力：

```c
int select(int nfds, fd_set *readfds, fd_set *writefds,
           fd_set *exceptfds, struct timeval *timeout);
```

传入一组文件描述符，`select` 阻塞直到其中某些就绪（可读/可写/异常），返回就绪的数量。

应用只在事件就绪后才调用 `read()`/`write()`，不会阻塞。

## 阻塞操作的问题

事件循环最怕**阻塞调用**。一旦某个事件处理程序调用了阻塞的系统调用（比如读磁盘），整个服务器都停下了。

解决方案：**异步 I/O**（AIO）。

```c
struct aiocb aio;
aio.aio_fildes = fd;
aio.aio_buf = buf;
aio.aio_nbytes = size;
aio.aio_offset = offset;
aio_read(&aio);          // 发起异步读，立即返回

// 后续检查是否完成
int status = aio_error(&aio);  // 返回 EINPROGRESS 表示还在读
```

也可以用信号通知完成，但信号处理本身又引入并发问题。

## 状态管理

线程模型里，每个线程的局部状态自然存在栈上。事件模型里，异步操作返回时需要知道之前执行到哪了——必须手动管理状态。

这叫**续体**（continuation）：把回调需要的上下文打包保存，异步操作完成后用它继续执行。代码比线程版复杂不少。

## 多核上的局限

单线程事件循环在多核机器上无法利用所有 CPU。要想用多核，就得跑多个事件循环（每核一个），一旦它们之间有共享数据，又需要加锁——事件模型的简洁性就打了折扣。

还有一个隐性阻塞问题：**缺页**。如果事件处理程序访问的内存页不在物理内存中，触发页错误，整个线程被阻塞等磁盘 I/O，事件循环无法推进。这一点是程序员无法完全控制的。
