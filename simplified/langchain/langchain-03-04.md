# Prompt 工程与部署

LangSmith 后半段其实在接两件事：

- prompt 怎么管，怎么试，怎么版本化
- agent 怎么上线，怎么运行，怎么调试

这两件事连在一起，才像一个完整工程流程。

## Prompt Engineering：prompt 不是一段字符串就完了

官方文档一上来先区分了两个概念：

| 概念 | 含义 |
|------|------|
| **Prompt** | 真正发给模型的消息内容 |
| **Prompt Template** | 带变量占位符的可复用模板 |

比如：

```text
你是客服助手。退款规则如下：

{refund_policy}

请回答用户问题：

{question}
```

模板的意义不只是复用，更重要的是**可测试、可版本化、可拉回代码里**。

比如把 prompt 当资源拉回应用代码，官方推荐的写法就是：

```python
from langsmith import Client
from langchain_openai import ChatOpenAI


client = Client()
prompt = client.pull_prompt("refund-bot:prod")
model = ChatOpenAI(model="gpt-4.1-mini")
chain = prompt | model

chain.invoke(
    {
        "refund_policy": "No refunds after 30 days.",
        "question": "Can I get a refund for this hat?",
    }
)
```

`refund-bot:prod` 这个写法的重点不在语法，而在版本控制：代码不需要改，移动 commit tag 就能切 prompt 版本。

## Prompt 工程里最值钱的几个功能

### Playground

拿来快速改 prompt、换模型、换工具、试输出 schema。

### Commit 和 Tag

- 每次保存都会生成 commit
- tag 是可移动的人类可读标签，比如 `staging`、`production`

这套设计的好处是：代码里不用永远绑死某个哈希，可以通过 tag 切版本。

### Dataset 驱动测试

Prompt 不该只凭感觉改。更稳的做法是在 Playground 里直接挂 dataset，跑实验看结果。

## Prompt 相关的几个硬结论

- 新项目优先用 **chat prompt**
- 模板变量要清楚，不要到处拼字符串
- 结构化输出和工具调用要分清：前者是“最终答案必须长这样”，后者是“模型可以决定要不要调工具”
- prompt 改动也应该走版本管理，而不是口头约定

## Deployment：LangSmith 不是只会看 trace

LangSmith Deployment 提供的是一个专门给 agent 用的运行时。文档里最核心的词是 **Agent Server**。

它提供的能力基本围绕四件事：

- **durable execution**
- **streaming**
- **Studio**
- **可扩展部署**

## Deployment 最值得记的能力

### Durable execution

任务可以中断、恢复、重试，不用从头跑。

### Streaming

可以持续往前端推消息，甚至断线后继续接流。

### Studio

可视化调试环境。能看图、看状态、回放 checkpoint、改状态继续跑。

### RemoteGraph / MCP / A2A

部署出去的 agent 不只是一个 HTTP 接口，还能继续作为别的 agent 的组成部分。

## 云端部署的最短路径

官方 quickstart 给的命令链很短：

```bash
uv tool install langgraph-cli
langgraph new path/to/app --template new-langgraph-project-python
cd path/to/app
echo 'LANGSMITH_API_KEY=lsv2_...' > .env
langgraph deploy
```

跑完以后，你会得到一个 deployment。接着可以：

- 在 Studio 里直接测
- 用 SDK 或 REST API 调它
- 看运行日志

最小调用示例也值得保留，因为它直接决定“部署成功后怎么接业务”：

```python
from langgraph_sdk import get_sync_client


client = get_sync_client(
    url="https://your-deployment-url",
    api_key="your-langsmith-api-key",
)

for chunk in client.runs.stream(
    None,
    "agent",
    input={
        "messages": [
            {"role": "human", "content": "What is LangGraph?"}
        ]
    },
    stream_mode="updates",
):
    print(chunk.event, chunk.data)
```

## 部署前至少要想清楚 3 件事

| 问题 | 否则会怎样 |
|------|------------|
| 状态放哪 | 多轮会话和恢复点会乱 |
| 怎么观察 | 出问题只能猜 |
| 怎么回归 | 每次改 prompt / 模型都像开盲盒 |

部署不是文档最后一章才开始考虑的事，前面的 tracing、evaluation、prompt versioning，本来就是部署准备的一部分。

## 这一章的真正结论

LangSmith 想做的不是单点工具，而是一套 agent 工程闭环：

1. 在 Playground 里调 prompt
2. 用 dataset 跑实验
3. 接 tracing 看真实行为
4. 把应用部署到 Agent Server
5. 在 Studio 里继续调和回放

把这些串起来之后，agent 才算进入“能持续演进”的阶段，而不是只停留在 demo。
