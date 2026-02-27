# 文件与目录

## 文件

**文件**就是一个字节数组，由**inode 号**唯一标识。OS 不关心文件内容的格式——它只存字节，怎么解读是应用的事。

## 目录

**目录**也是一种文件，里面存的是 (名字, inode 号) 的列表。通过目录的层级嵌套构成整棵文件系统树，根目录是 `/`。

## 文件操作 API

### 打开与关闭

```c
int fd = open("foo.txt", O_RDONLY);  // 返回文件描述符
// ... 使用 fd 读写 ...
close(fd);
```

`open()` 返回的**文件描述符**（fd）是一个整数。每个进程有自己的 fd 表。fd 0/1/2 分别是 stdin/stdout/stderr。`open()` 总是分配当前最小的可用 fd。

### 读写与偏移

```c
ssize_t read(int fd, void *buf, size_t count);   // 从当前偏移量读
ssize_t write(int fd, const void *buf, size_t count);
off_t lseek(int fd, off_t offset, int whence);   // 修改偏移量
```

每个 fd 有一个**当前偏移量**（offset），`read()`/`write()` 后自动前移。`lseek()` 可以随意移动偏移量。注意 `lseek` 只改内存中的偏移变量，不会触发磁盘寻道。

### fsync

```c
fsync(fd);    // 强制把该文件的脏数据刷到磁盘
```

普通 `write()` 可能只到了内核缓冲区，断电会丢。数据库等需要持久性保证的场景必须调 `fsync()`。要把目录项也持久化，还得对目录 fd 也调一次 `fsync()`。

### rename

```c
rename("tmp_file", "target_file");   // 原子操作
```

rename 是**原子的**。安全更新文件的惯用模式：先写入临时文件 → `fsync` 临时文件 → `rename` 覆盖目标文件。这样保证要么看到完整的新文件，要么看到完整的旧文件。

### stat

```c
struct stat st;
stat("foo.txt", &st);   // 获取文件元数据
```

返回 inode 号、大小、权限、链接数、各种时间戳等。

## 硬链接与软链接

### 硬链接

`link("old_name", "new_name")` 创建一个新的目录项指向同一个 inode。一个 inode 可以有多个名字，inode 内部维护**引用计数**。`unlink("name")` 删除目录项并将引用计数减 1，引用计数归零时文件被真正删除。

所以"删除文件"这个 API 叫 `unlink` 而不是 `delete`。

硬链接的限制：不能跨文件系统（因为 inode 号只在一个文件系统内有意义），不能链接目录（会导致目录树出现环）。

### 软链接（符号链接）

软链接是一个独立的文件，内容就是目标文件的路径字符串。访问软链接时 OS 自动跟随路径找到目标。

和硬链接的区别：软链接可以跨文件系统，可以链接目录，但目标被删后软链接就成了**悬空链接**（dangling link）。

## mount

`mount` 把一个文件系统挂载到目录树的某个节点上，把多个独立的文件系统统一到一棵树里。
