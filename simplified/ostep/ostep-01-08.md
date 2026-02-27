# 内存 API

## 栈内存 vs 堆内存

- **栈内存**：编译器自动管理，函数里声明的局部变量在函数返回时自动释放
- **堆内存**：程序员手动管理，`malloc()` 分配，`free()` 释放

## 核心 API

```c
void *malloc(size_t size);    // 分配 size 字节，返回 void 指针
void free(void *ptr);          // 释放之前 malloc 的内存
void *calloc(size_t n, size_t size);   // 分配并清零
void *realloc(void *ptr, size_t size); // 调整已分配内存大小
```

`malloc()` 的参数是字节数，通常配合 `sizeof` 使用：`malloc(sizeof(int) * 10)`。`sizeof` 在编译期求值（变长数组除外）。

`free()` 只需要指针，不需要传大小——分配器内部记录了每块的大小。

## 常见错误

| 错误 | 说明 |
|------|------|
| 忘记分配 | 直接用未分配的指针，如 `strcpy(dst, src)` 但 `dst` 没 malloc |
| 分配不够 | 少分了一个字节（比如忘了字符串末尾的 `\0`），缓冲区溢出 |
| 忘记初始化 | `malloc` 不清零，读到随机值 |
| 忘记释放 | 内存泄漏。短命程序无所谓，长期运行的程序（如服务器、OS）会慢慢耗光内存 |
| 用完还在用 | 悬空指针（dangling pointer），`free` 之后又去读写 |
| 重复释放 | double free，结果未定义，通常导致崩溃 |
| 释放错误地址 | 传给 `free` 的不是 `malloc` 返回的地址 |

## 底层机制

`malloc`/`free` 是**库函数**，不是系统调用。它们在用户空间管理内存。

底下的系统调用是 `brk`/`sbrk`（调整堆分界点）和 `mmap`（映射匿名页或文件）。一般不应直接调用 `brk`/`sbrk`。

所以内存管理分两层：OS 给进程分页级别的内存，`malloc` 库在这些页里面做细粒度的分配和回收。
