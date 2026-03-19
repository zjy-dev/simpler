# LangChain 生态地图

`source/langchain` 不是一本书，而是一整个文档站源码。它把 LangChain 公司的几条产品线塞进了同一个站点里：开源框架、运行时、评测平台、无代码工具，全都在这里。先把边界弄清，后面才不会越看越乱。

## 这套文档站里到底有什么

| 入口 | 作用 | 适合什么时候看 |
|------|------|----------------|
| `docs.langchain.com` | 教程、概念、产品文档 | 想理解怎么用、怎么选型 |
| `reference.langchain.com` | API 参考文档 | 已经开写，需要查类、函数、参数 |
| `chat.langchain.com` | 文档问答助手 | 想快速问一个具体问题 |

这次精简版主要压 `docs.langchain.com` 这一层。API 参考、贡献指南、海量 provider 集成页都不放进来。

## LangChain 维护的项目区别

| 项目 | 本质 | 解决什么问题 | 什么时候用 |
|------|------|--------------|------------|
| **LangChain** | Agent 框架 | 给你统一的模型、工具、agent 抽象，先把应用跑起来 | 需要尽快做出一个可用 agent |
| **LangGraph** | Agent 运行时 / 编排框架 | 负责状态、持久化、流式输出、人类介入、长任务恢复 | 需要更细粒度控制，或任务会跑很久 |
| **Deep Agents** | 带电池的 agent harness | 预置上下文压缩、文件系统、子 agent、规划能力 | 想要更强自治能力，不想自己拼太多基础设施 |
| **LangSmith** | 平台 | 负责 tracing、评测、提示词管理、部署 | 需要调试、评测、上线和持续改进 |
| **Fleet** | 无代码入口 | 用可视化方式搭 agent | 不想写代码，或想先做原型 |

一个最实用的理解方式：

- `LangChain` 管“怎么写 agent”。
- `LangGraph` 管“agent 怎么稳定跑”。
- `LangSmith` 管“怎么观察、评估、上线、回收反馈”。
- `Deep Agents` 管“把一堆常见能力直接打包给你”。

## 常见选型

### 只想先做出一个 agent

从 **LangChain** 开始。它有现成的 `create_agent`，模型、工具、prompt、middleware 都能挂上去。

### agent 要长时间运行，能暂停、恢复、分支

上 **LangGraph**。这类需求本质上是运行时问题，不是 prompt 问题。

### 想少造轮子，直接要文件系统、子 agent、上下文管理

看 **Deep Agents**。它比 LangChain 更“重”，但也省事。

### 线上出了问题，想知道 agent 到底做了什么

接 **LangSmith**。没有 trace，复杂 agent 基本没法调。

### 不写代码也想搭一个 agent

看 **Fleet**。它更像产品工具，不是底层框架。

## 这份精简版保留什么

这套文档原站内容很多，删掉的主要是三类：

- 海量模型、向量库、加载器、provider 集成页
- 自托管、组织管理、权限、计费、企业部署细节
- 面向文档贡献者的流程、lint、仓库构建说明

保留下来的主线只有一条：

1. 先看 **LangChain**，理解 agent 是怎么搭出来的。
2. 再看 **LangGraph**，理解状态、持久化和人类介入为什么能成立。
3. 最后看 **LangSmith**，把 tracing、评测、prompt、部署串成闭环。

按这个顺序读，基本不会迷路。
