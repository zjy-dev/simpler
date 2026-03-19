# Graph API：State、Node、Edge、Compile

LangGraph 的 Graph API 可以压成一句话：

**节点干活，边决定下一步，状态把一切串起来。**

## 四个核心概念

| 概念 | 作用 |
|------|------|
| **State** | 图当前的共享快照 |
| **Node** | 真正执行逻辑的函数 |
| **Edge** | 决定下一步去哪个节点 |
| **Compile** | 检查图结构，并注入运行时能力 |

## State：共享状态

State 是整个图的公共数据面。每个节点读当前状态，返回局部更新，LangGraph 再把这些更新合并回状态。

最常见的几种状态内容：

- 消息列表
- 当前步骤名
- 计数器
- 中间推理结果
- 工具输出

## State 不是普通字典那么简单

文档一直强调一个点：**状态更新要有规则。**

比如：

- 某个字段是“覆盖旧值”
- 某个字段是“追加到列表”
- 某个字段并行分支写入时要做 reducer 合并

这也是为什么 LangGraph 会单独区分：

- 普通字段
- `MessagesValue`
- `ReducedValue`

## Node：图里的工作单元

Node 就是函数。输入是状态，输出是状态更新。

```python
def llm_call(state):
    response = model.invoke(state["messages"])
    return {"messages": [response]}
```

一个 node 可以做任何事：

- 调模型
- 调工具
- 写数据库
- 做纯逻辑判断
- 调其他服务

最稳的写法是：**node 尽量只关心单一步骤。**

## Edge：控制执行流

边有两种。

### 固定边

写死下一步。

```python
builder.add_edge("node_a", "node_b")
```

### 条件边

根据当前状态决定去哪。

```python
def should_continue(state):
    if state["done"]:
        return END
    return "tool_node"
```

这是 agent loop、分支流程、重试逻辑成立的关键。

## Compile：不是可有可无的一步

`compile()` 必须调，原因有两个：

1. 做基本结构检查，避免孤儿节点、断边之类的低级错误
2. 把运行时能力挂上去，比如 checkpointer、breakpoint 等

```python
app = builder.compile(checkpointer=checkpointer)
```

少了这步，图不能执行。

## Graph API 的思考方式

刚接触 LangGraph 时，最容易把它想复杂。其实可以用最土的办法理解：

- **State**：当前局面
- **Node**：执行一个动作
- **Edge**：决定下一步

只不过这个“局面”可以被持久化，“下一步”可以由模型或代码决定，“动作”也可以中途暂停。

## 一个最小骨架

```python
from langgraph.graph import StateGraph, START, END


builder = StateGraph(MyState)
builder.add_node("step_a", step_a)
builder.add_node("step_b", step_b)
builder.add_edge(START, "step_a")
builder.add_conditional_edges("step_a", router, {"next": "step_b", "end": END})
builder.add_edge("step_b", END)

app = builder.compile()
```

## 什么时候要多 schema

文档里还提到一个很实用的点：图的输入、输出和内部状态不一定要完全一样。

典型场景：

- 输入只关心用户请求
- 图内部还需要很多中间字段
- 输出只想暴露最终结果

这时可以把 schema 拆成：

- input schema
- internal schema
- output schema

这样接口更干净，状态也不会越长越乱。

## 一条经验

如果你发现自己在写一个复杂 agent，却始终说不清：

- 当前状态有哪些字段
- 哪些字段会被谁改
- 失败后从哪里继续

那多半不是模型的问题，而是流程还没被你“图化”。
