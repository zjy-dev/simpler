# LangChain 快速上手

LangChain 是一层偏高层的 agent 框架。它把模型调用、工具调用、agent loop、middleware 这些东西先帮你搭好，让你不用一上来就自己写状态机。

一句话概括：**LangChain 适合先把 agent 做出来，LangGraph 适合把 agent 做扎实。**

## LangChain 的定位

LangChain 解决的不是“模型够不够强”，而是“怎样把模型、工具和应用逻辑拼成一个能跑的 agent”。

它最核心的价值有四个：

- **统一模型接口**：同一套代码可以换 OpenAI、Anthropic、Google 等不同模型提供商。
- **现成的 agent 抽象**：`create_agent` 已经把常见的工具调用循环搭好了。
- **和 LangGraph 打通**：LangChain agent 底下就是 LangGraph，所以天然能接持久化、流式输出、人类介入。
- **和 LangSmith 打通**：调试和评测不需要自己再搭一套监控系统。

## 什么时候该用 LangChain

适合：

- 想快速做一个有工具调用能力的 agent
- 团队希望用统一抽象封装模型和工具
- 业务流程不算太怪，至少还能装进“模型思考 -> 调工具 -> 回答”这个循环里

不太适合：

- 需要非常细粒度的编排控制
- 任务会持续很久，且要精确处理暂停、恢复、分叉、并发
- 你已经知道自己要写一个显式工作流，而不是通用 agent

这时候直接上 LangGraph 更顺。

## 最小例子

官方文档里最常见的入口就是 `create_agent`：

```python
from langchain.agents import create_agent


def get_weather(city: str) -> str:
    """查询城市天气。"""
    return f"{city} is sunny."


agent = create_agent(
    model="openai:gpt-5",
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
)

result = agent.invoke(
    {
        "messages": [
            {"role": "user", "content": "What is the weather in Tokyo?"}
        ]
    }
)
```

这段代码背后做了几件事：

1. 把模型和工具描述整理成模型能理解的上下文
2. 让模型自己决定要不要调工具
3. 执行工具，把结果回喂给模型
4. 一直循环到模型给出最终答案或达到上限

## LangChain 的常用积木

| 积木 | 作用 |
|------|------|
| `model` | 决定推理能力、成本和响应速度 |
| `tools` | 让 agent 能查外部信息、调系统、执行动作 |
| `system_prompt` | 约束 agent 的角色、边界和回答风格 |
| `middleware` | 在模型调用前后做裁剪、路由、检查、改写 |
| `response_format` | 强制最终输出满足某个结构 |
| `checkpointer` | 给 agent 增加线程级短期记忆 |

## 一个实际判断标准

如果你现在的问题是：

- 怎么把工具接进去
- 怎么管 prompt
- 怎么让模型用统一接口跑起来

那就从 LangChain 开始。

如果你的问题已经变成：

- 这个节点失败后怎么恢复
- 人工审核后怎么从中断点继续
- 一个任务怎么拆成多个分支并在状态上合流

那你关心的已经不是 LangChain 的抽象层，而是 LangGraph 的运行时能力。

## 开发顺手的做法

- 原型阶段先用 LangChain 把流程跑通
- 一开始就接 LangSmith tracing，不然后面很难补
- 真碰到复杂编排，再把核心流程下沉到 LangGraph

这比一上来全手写图省事得多。
