# Interrupts 与人类介入

很多业务不是“全自动跑完”最难，最难的是：**跑到关键一步先停下来，等人看一眼。**

LangGraph 的 `interrupt()` 就是干这个的。

## `interrupt()` 做了什么

当节点执行到 `interrupt()` 时，LangGraph 会：

1. 暂停图执行
2. 通过持久化层把当前状态保存下来
3. 把中断 payload 返回给调用方
4. 一直等待，直到你用 `Command(resume=...)` 恢复

恢复后，这个 `resume` 的值会变成 `interrupt()` 的返回值。

## 最小例子

```python
from langgraph.types import Command, interrupt


def approval_node(state):
    approved = interrupt("Do you approve this action?")
    return {"approved": approved}


config = {"configurable": {"thread_id": "thread-1"}}

# 第一次调用：执行到 interrupt 后停下
app.invoke({"input": "data"}, config)

# 第二次调用：恢复执行
app.invoke(Command(resume=True), config)
```

## 使用 interrupt 的前提

少一个都不行：

- **checkpointer**
- **稳定的 `thread_id`**
- **可 JSON 序列化的中断 payload**

没有持久化，就没有“停住以后还能接着跑”。

## 一个非常容易踩的坑

恢复时，**触发 interrupt 的那个节点会从头再执行一遍**。

所以：

- `interrupt()` 前面的代码可能会重复跑
- 有副作用的动作不要放在 `interrupt()` 前面

正确姿势通常是：

- 先准备好展示给人的信息
- `interrupt()`
- 审核通过后再执行真正的副作用动作

## 最常见的用法

### 审批流

比如付款、发邮件、改数据库前先让人确认。

### Review and edit

先让模型生成 SQL、文案、工具调用计划，再让人改一版。

### 工具调用前拦截

工具本身没问题，问题是调用参数可能危险。中断后让人确认参数。

### 人工补充输入

模型缺信息时，不是让它瞎猜，而是停下来问人。

## 多个中断并行出现怎么办

文档里专门提了一个场景：并行分支里，多个节点同时 `interrupt()`。

这时恢复时要把**中断 ID** 和**对应输入**对上，别把 A 分支的回复喂给 B 分支。

## 和 streaming 的关系

做交互式 agent 时，常见做法是同时开两种流：

- 消息流：给用户看实时输出
- 更新流：检查有没有遇到 interrupt

这样前端可以做到：

- 平时像聊天一样流式显示
- 一旦遇到中断，立刻弹审批或输入框
- 用户提交后继续执行

## 什么时候该用 interrupt

适合：

- 真有外部输入才能继续
- 这一步风险高，必须审查
- 想做可恢复的人工介入流程

不适合：

- 只是想打个日志
- 只是想暂时停一停，但不需要保存现场

## 一个务实判断

如果你的业务里有“审批”“确认”“修改后继续”“等外部结果回来再跑”这些关键词，interrupt 基本就是刚需。

它让 agent 不再只有两种状态：跑着，或者死了。中间终于多了一个很重要的状态：**暂停并等待。**
