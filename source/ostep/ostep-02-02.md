# 插叙：线程 API

本章介绍了主要的线程API。后续章节也会进一步介绍如何使用API。更多的细节可以参考其他书籍和在线资源**[B89，B97，B+96，K+96]**。随后的章节会慢慢介绍锁和条件变量的概念，因此本章可以作为参考。

> **关键问题：如何创建和控制线程？**
>
> 操作系统应该提供哪些创建和控制线程的接口？这些接口如何设计得易用和实用？

## 27.1 线程创建

编写多线程程序的第一步就是创建新线程，因此必须存在某种线程创建接口。在POSIX中，很简单：

```c
#include <pthread.h>
int
pthread_create( pthread_t *            thread,
                const pthread_attr_t * attr,
                void *                 (*start_routine)(void*),
                void *                 arg);
```

这个函数声明可能看起来有一点复杂（尤其是如果你没在C中用过函数指针），但实际上它并不差。该函数有4个参数：`thread`、`attr`、`start_routine` 和 `arg`。第一个参数 `thread` 是指向 `pthread_t` 结构类型的指针，我们将利用这个结构与该线程交互，因此需要将它传入 `pthread_create()`，以便将它初始化。

第二个参数 `attr` 用于指定该线程可能具有的任何属性。一些例子包括设置栈大小，或关于该线程调度优先级的信息。一个属性通过单独调用 `pthread_attr_init()` 来初始化。有关详细信息，请参阅手册。但是，在大多数情况下，默认值就行。在这个例子中，我们只需传入 `NULL`。

第三个参数最复杂，但它实际上只是问：这个线程应该在哪个函数中运行？在 C 中，我们把它称为一个函数指针（function pointer），这个指针告诉我们需要以下内容：一个函数名称（`start_routine`），它被传入一个类型为 `void *` 的参数（`start_routine` 后面的括号表明了这一点），并且它返回一个 `void *` 类型的值（即一个void指针）。

如果这个函数需要一个整数参数，而不是一个void指针，那么声明看起来像这样：

```c
int pthread_create(..., // first two args are the same
                   void * (*start_routine)(int),
                   int arg);
```

## 27.2 线程完成

如果函数接受void指针作为参数，但返回一个整数，函数声明会变成：

```c
int pthread_create(..., // first two args are the same
                   int (*start_routine)(void *),
                   void * arg);
```

最后，第四个参数 `arg` 就是要传递给线程开始执行的函数的参数。你可能会问：为什么我们需要这些void指针？好吧，答案很简单：将void指针作为函数的参数 `start_routine`，允许我们传入任何类型的参数，将它作为返回值，允许线程返回任何类型的结果。

下面来看图 27.1 中的例子。这里我们只是创建了一个线程，传入两个参数，它们被打包成一个我们自己定义的类型（`myarg_t`）。该线程一旦创建，可以简单地将其参数转换为它所期望的类型，从而根据需要将参数解包。

```c
int pthread_join(pthread_t thread, void **value_ptr);
```

```c
#include <pthread.h>

typedef struct myarg_t {
    int a;
    int b;
} myarg_t;

void *mythread(void *arg) {
    myarg_t *m = (myarg_t *) arg;
    printf("%d %d\n", m->a, m->b);
    return NULL;
}

int
main(int argc, char *argv[]) {
    pthread_t p;
    int rc;

    myarg_t args;
    args.a = 10;
    args.b = 20;
    rc = pthread_create(&p, NULL, mythread, &args);
    ...
}
```

<!-- 图27.1 创建线程 -->

它就在那里！一旦你创建了一个线程，你确实拥有了另一个活着的执行实体，它有自己的调用栈，与程序中所有当前存在的线程在相同的地址空间内运行。好玩的事开始了！

上面的例子展示了如何创建一个线程。但是，如果你想等待线程完成，会发生什么情况？你需要做一些特别的事情来等待完成。具体来说，你必须调用函数 `pthread_join()`。

该函数有两个参数。第一个是 `pthread_t` 类型，用于指定要等待的线程。这个变量是由线程创建函数初始化的（当你将一个指针作为参数传递给 `pthread_create()` 时）。如果你保留了它，就可以用它来等待该线程终止。

第二个参数是一个指针，指向你希望得到的返回值。因为函数可以返回任何东西，所以它被定义为返回一个指向 void 的指针。因为 `pthread_join()` 函数改变了传入参数的值，所以你需要传入一个指向该值的指针，而不只是该值本身。

我们来看另一个例子（见图 27.2）。在代码中，再次创建单个线程，并通过 `myarg_t` 结构传递一些参数。对于返回值，使用 `myret_t` 型。当线程完成运行时，主线程已经在 `pthread_join()` 函数内等待了①。然后会返回，我们可以访问线程返回的值，即在 `myret_t` 中的内容。

有几点需要说明。首先，我们常常不需要这样痛苦地打包、解包参数。如果我们不需要参数，创建线程时传入 `NULL` 即可。类似的，如果不需要返回值，那么 `pthread_join()` 调用也可以传入 `NULL`。

```c
#include <stdio.h>
#include <pthread.h>
#include <assert.h>
#include <stdlib.h>

typedef struct myarg_t {
    int a;
    int b;
} myarg_t;

typedef struct myret_t {
    int x;
    int y;
} myret_t;

void *mythread(void *arg) {
    myarg_t *m = (myarg_t *) arg;
    printf("%d %d\n", m->a, m->b);
    myret_t *r = Malloc(sizeof(myret_t));
    r->x = 1;
    r->y = 2;
    return (void *) r;
}

int
main(int argc, char *argv[]) {
    int rc;
    pthread_t p;
    myret_t *m;

    myarg_t args;
    args.a = 10;
    args.b = 20;
    Pthread_create(&p, NULL, mythread, &args);
    Pthread_join(p, (void **) &m);
    printf("returned %d %d\n", m->x, m->y);
    return 0;
}
```

① 注意我们在这里使用了包装的函数。具体来说，我们调用了 `Malloc()`、`Pthread_join()` 和 `Pthread_create()`，它们只是调用了与它们命名相似的小写版本，并确保函数不会返回任何意外。

<!-- 图27.2 等待线程完成 -->

其次，如果我们只传入一个值（例如，一个int），也不必将它打包为一个参数。图27.3展示了一个例子。在这种情况下，更简单一些，因为我们不必在结构中打包参数和返回值。

```c
void *mythread(void *arg) {
    int m = (int) arg;
    printf("%d\n", m);
    return (void *) (arg + 1);
}
int main(int argc, char *argv[]) {
    pthread_t p;
    int rc, m;
    Pthread_create(&p, NULL, mythread, (void *) 100);
    Pthread_join(p, (void **) &m);
    printf("returned %d\n", m);
    return 0;
}
```

<!-- 图27.3 较简单的向线程传递参数示例 -->

再次，我们应该注意，必须非常小心如何从线程返回值。特别是，永远不要返回一个指针，并让它指向线程调用栈上分配的东西。如果这样做，你认为会发生什么？（想一想！）下面是一段危险的代码示例，对图27.2中的示例做了修改。

```c
void *mythread(void *arg) {
    myarg_t *m = (myarg_t *) arg;
    printf("%d %d\n", m->a, m->b);
    myret_t r; // ALLOCATED ON STACK: BAD!
    r.x = 1;
    r.y = 2;
    return (void *) &r;
}
```

在这个例子中，变量 `r` 被分配在 `mythread` 的栈上。但是，当它返回时，该值会自动释放（这就是栈使用起来很简单的原因！），因此，将指针传回现在已释放的变量将导致各种不好的结果。当然，当你打印出你以为的返回值时，你可能会感到惊讶（但不一定！）。试试看，自己找出真相①！

① 幸运的是，编译器 `gcc` 在编译这样的代码时可能会报警，这是注意编译器警告的又一个原因。

最后，你可能会注意到，使用 `pthread_create()` 创建线程，然后立即调用 `pthread_join()`，这是创建线程的一种非常奇怪的方式。事实上，有一个更简单的方法来完成这个任务，它被称为过程调用（procedure call）。显然，我们通常会创建不止一个线程并等待它完成，否则根本没有太多的用途。

我们应该注意，并非所有多线程代码都使用join函数。例如，多线程Web服务器可能会创建大量工作线程，然后使用主线程接受请求，并将其无限期地传递给工作线程。因此这样的长期程序可能不需要join。然而，创建线程来（并行）执行特定任务的并行程序，很可能会使用join来确保在退出或进入下一阶段计算之前完成所有这些工作。

## 27.3 锁

除了线程创建和join之外，POSIX线程库提供的最有用的函数集，可能是通过锁（lock）来提供互斥进入临界区的那些函数。这方面最基本的一对函数是：

```c
int pthread_mutex_lock(pthread_mutex_t *mutex);
int pthread_mutex_unlock(pthread_mutex_t *mutex);
```

函数应该易于理解和使用。如果你意识到有一段代码是一个临界区，就需要通过锁来保护，以便像需要的那样运行。你大概可以想象代码的样子：

```c
pthread_mutex_t lock;
pthread_mutex_lock(&lock);
x = x + 1; // or whatever your critical section is
pthread_mutex_unlock(&lock);
```

这段代码的意思是：如果在调用 `pthread_mutex_lock()` 时没有其他线程持有锁，线程将获取该锁并进入临界区。如果另一个线程确实持有该锁，那么尝试获取该锁的线程将不会从该调用返回，直到获得该锁（意味着持有该锁的线程通过解锁调用释放该锁）。当然，在给定的时间内，许多线程可能会卡住，在获取锁的函数内部等待。然而，只有获得锁的线程才应该调用解锁。

遗憾的是，这段代码有两个重要的问题。第一个问题是缺乏正确的初始化（lack of proper initialization）。所有锁必须正确初始化，以确保它们具有正确的值，并在锁和解锁被调用时按照需要工作。

对于 POSIX 线程，有两种方法来初始化锁。一种方法是使用 `PTHREAD_MUTEX_INITIALIZER`，如下所示：

```c
pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
```

这样做会将锁设置为默认值，从而使锁可用。初始化的动态方法（即在运行时）是调用 `pthread_mutex_init()`，如下所示：

```c
int rc = pthread_mutex_init(&lock, NULL);
assert(rc == 0); // always check success!
```

## 27.4 条件变量

此函数的第一个参数是锁本身的地址，而第二个参数是一组可选属性。请你自己去详细了解这些属性。传入 `NULL` 就是使用默认值。无论哪种方式都有效，但我们通常使用动态（后者）方法。请注意，当你用完锁时，还应该相应地调用 `pthread_mutex_destroy()`，所有细节请参阅手册。

上述代码的第二个问题是在调用获取锁和释放锁时没有检查错误代码。就像 UNIX 系统中调用的任何库函数一样，这些函数也可能会失败！如果你的代码没有正确地检查错误代码，失败将会静静地发生，在这种情况下，可能会允许多个线程进入临界区。至少要使用包装的函数，它对函数成功加上断言（见图27.4）。更复杂的（非玩具）程序，在出现问题时不能简单地退出，应该检查失败并在获取锁或释放锁未成功时执行适当的操作。

```c
// Use this to keep your code clean but check for failures
// Only use if exiting program is OK upon failure
void Pthread_mutex_lock(pthread_mutex_t *mutex) {
    int rc = pthread_mutex_lock(mutex);
    assert(rc == 0);
}
```

<!-- 图27.4 包装函数示例 -->

获取锁和释放锁函数不是pthread与锁进行交互的仅有的函数。特别是，这里有两个你可能感兴趣的函数：

```c
int pthread_mutex_trylock(pthread_mutex_t *mutex);
int pthread_mutex_timedlock(pthread_mutex_t *mutex,
                            struct timespec *abs_timeout);
```

这两个调用用于获取锁。如果锁已被占用，则 `trylock` 版本将失败。获取锁的 `timedlock` 版本会在超时或获取锁后返回，以先发生者为准。因此，具有零超时的 `timedlock` 退化为 `trylock` 的情况。通常应避免使用这两种版本，但有些情况下，避免卡在（可能无限期的）获取锁的函数中会很有用，我们将在以后的章节中看到（例如，当我们研究死锁时）。

所有线程库还有一个主要组件（当然 POSIX 线程也是如此），就是存在一个条件变量（condition variable）。当线程之间必须发生某种信号时，如果一个线程在等待另一个线程继续执行某些操作，条件变量就很有用。希望以这种方式进行交互的程序使用两个主要函数：

```c
int pthread_cond_wait(pthread_cond_t *cond, pthread_mutex_t *mutex);
int pthread_cond_signal(pthread_cond_t *cond);
```

要使用条件变量，必须另外有一个与此条件相关的锁。在调用上述任何一个函数时，应该持有这个锁。

第一个函数 `pthread_cond_wait()` 使调用线程进入休眠状态，因此等待其他线程发出信号，通常当程序中的某些内容发生变化时，现在正在休眠的线程可能会关心它。典型的用法如下所示：

```c
pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t  cond = PTHREAD_COND_INITIALIZER;

Pthread_mutex_lock(&lock);
while (ready == 0)
    Pthread_cond_wait(&cond, &lock);
Pthread_mutex_unlock(&lock);
```

在这段代码中，在初始化相关的锁和条件之后①，一个线程检查变量 `ready` 是否已经被设置为零以外的值。如果没有，那么线程只是简单地调用等待函数以便休眠，直到其他线程唤醒它。

唤醒线程的代码运行在另外某个线程中，像下面这样：

```c
Pthread_mutex_lock(&lock);
ready = 1;
Pthread_cond_signal(&cond);
Pthread_mutex_unlock(&lock);
```

关于这段代码有一些注意事项。首先，在发出信号时（以及修改全局变量 `ready` 时），我们始终确保持有锁。这确保我们不会在代码中意外引入竞态条件。

其次，你可能会注意到等待调用将锁作为其第二个参数，而信号调用仅需要一个条件。造成这种差异的原因在于，等待调用除了使调用线程进入睡眠状态外，还会让调用者睡眠时释放锁。想象一下，如果不是这样：其他线程如何获得锁并将其唤醒？但是，在被唤醒之后返回之前，`pthread_cond_wait()` 会重新获取该锁，从而确保等待线程在等待序列开始时获取锁与结束时释放锁之间运行的任何时间，它持有锁。

最后一点需要注意：等待线程在while循环中重新检查条件，而不是简单的if语句。在后续章节中研究条件变量时，我们会详细讨论这个问题，但是通常使用while循环是一件简单而安全的事情。虽然它重新检查了这种情况（可能会增加一点开销），但有一些 pthread 实现可能会错误地唤醒等待的线程。在这种情况下，没有重新检查，等待的线程会继续认为条件已经改变。因此，将唤醒视为某种事物可能已经发生变化的暗示，而不是绝对的事实，这样更安全。

请注意，有时候线程之间不用条件变量和锁，用一个标记变量会看起来很简单，很吸引人。例如，我们可以重写上面的等待代码，像这样：

```c
while (ready == 0)
    ; // spin
```

相关的发信号代码看起来像这样：

```c
ready = 1;
```

千万不要这么做。首先，多数情况下性能差（长时间的自旋浪费CPU）。其次，容易出错。最近的研究**[X+10]**显示，线程之间通过标志同步（像上面那样），出错的可能性让人吃惊。在那项研究中，这些不正规的同步方法半数以上都是有问题的。不要偷懒，就算你想到可以不用条件变量，还是用吧。

如果条件变量听起来让人迷惑，也不要太担心。后面的章节会详细介绍。在此之前，只要知道它们存在，并对为什么要使用它们有一些概念即可。

① 请注意，可以使用 `pthread_cond_init()`（和对应的 `pthread_cond_destroy()` 调用），而不是使用静态初始化程序 `PTHREAD_COND_INITIALIZER`。听起来像是工作更多了？是的。

## 27.5 编译和运行

本章所有代码很容易运行。代码需要包括头文件 `pthread.h` 才能编译。链接时需要pthread库，增加 `-pthread` 标记。

例如，要编译一个简单的多线程程序，只需像下面这样做：

```bash
prompt> gcc -o main main.c -Wall -pthread
```

只要 `main.c` 包含pthreads头文件，你就已经成功地编译了一个并发程序。像往常一样，它是否能工作完全是另一回事。

## 27.6 小结

我们介绍了基本的pthread库，包括线程创建，通过锁创建互斥执行，通过条件变量的信号和等待。要想写出健壮高效的多线程代码，只需要耐心和万分小心！

本章结尾我们给出编写一些多线程代码的建议（参见补充内容）。API 的其他方面也很有趣。如果需要更多信息，请在Linux系统上输入 `man -k pthread`，查看构成整个接口的超过一百个API。但是，这里讨论的基础知识应该让你能够构建复杂的（并且希望是正确的和高性能的）多线程程序。线程难的部分不是API，而是如何构建并发程序的棘手逻辑。请继续阅读以了解更多信息。

> **补充：线程API指导**
>
> 当你使用 POSIX 线程库（或者实际上，任何线程库）来构建多线程程序时，需要记住一些小而重要的事情：
>
> - 保持简洁。最重要的一点，线程之间的锁和信号的代码应该尽可能简洁。复杂的线程交互容易产生缺陷。
> - 让线程交互减到最少。尽量减少线程之间的交互。每次交互都应该想清楚，并用验证过的、正确的方法来实现（很多方法会在后续章节中学习）。
> - 初始化锁和条件变量。未初始化的代码有时工作正常，有时失败，会产生奇怪的结果。
> - 检查返回值。当然，任何C和UNIX的程序，都应该检查返回值，这里也是一样。否则会导致古怪而难以理解的行为，让你尖叫，或者痛苦地揪自己的头发。
> - 注意传给线程的参数和返回值。具体来说，如果传递在栈上分配的变量的引用，可能就是在犯错误。
> - 每个线程都有自己的栈。类似于上一条，记住每一个线程都有自己的栈。因此，线程局部变量应该是线程私有的，其他线程不应该访问。线程之间共享数据，值要在堆（heap）或者其他全局可访问的位置。
> - 线程之间总是通过条件变量发送信号。切记不要用标记变量来同步。
> - 多查手册。尤其是Linux的pthread手册，有更多的细节、更丰富的内容。请仔细阅读！

## 参考资料

**[B89]** "An Introduction to Programming with Threads" Andrew D. Birrell.
DEC Technical Report, January, 1989.
它是线程编程的经典，但内容较陈旧。不过，仍然值得一读，而且是免费的。

**[B97]** "Programming with POSIX Threads" David R. Butenhof.
Addison-Wesley, May 1997.
又是一本关于编程的书。

**[B+96]** "PThreads Programming: A POSIX Standard for Better Multiprocessing"
Dick Buttlar, Jacqueline Farrell, Bradford Nichols. O'Reilly, September 1996.
O'Reilly出版的一本不错的书。我们的书架当然包含了这家公司的大量书籍，其中包括一些关于Perl、Python和JavaScript的优秀产品（特别是Crockford的"JavaScript: The Good Parts"）。

**[K+96]** "Programming With Threads"
Steve Kleiman, Devang Shah, Bart Smaalders. Prentice Hall, January 1996.
这可能是这个领域较好的书籍之一。从当地图书馆借阅，或从老一辈程序员那里"偷"来读。认真地说，只要向老一辈程序员借的话，他们会借给你的，不用担心。

**[X+10]** "Ad Hoc Synchronization Considered Harmful"
Weiwei Xiong, Soyeon Park, Jiaqi Zhang, Yuanyuan Zhou, Zhiqiang Ma. OSDI 2010, Vancouver, Canada.
本文展示了看似简单的同步代码是如何导致大量错误的。使用条件变量并正确地发送信号！
