# 评测体系：离线、在线、Dataset、Evaluator

LangSmith 的评测部分不是为了“做一张好看的分数表”，而是为了让 agent 的改动能被比较、被回归、被复现。

## 两类评测

| 类型 | 什么时候跑 | 目的 |
|------|------------|------|
| **Offline Evaluation** | 上线前 | 比较版本、做回归、跑基准集 |
| **Online Evaluation** | 线上 | 实时监控真实用户流量里的质量问题 |

这两个不要互相替代。离线评测能控变量，在线评测更贴近真实世界。

## 一次评测最少要有 3 样东西

| 组件 | 作用 |
|------|------|
| **Dataset** | 测试样本集合，含输入，必要时含参考输出 |
| **Target Function** | 你想评的对象，可以是一段 prompt、一个模块、整个工作流 |
| **Evaluator** | 打分逻辑，可以是规则、代码、人工、模型裁判 |

少一个都跑不起来。

## 离线评测怎么走

官方文档的离线流程可以压成四步：

1. **建数据集**
2. **定义 evaluator**
3. **运行 experiment**
4. **分析结果**

数据集的来源一般有三种：

- 人工整理的典型样本
- 线上 trace 里捞出来的问题样本
- 合成数据

最小离线评测通常就是下面这套：

```python
from langsmith import Client, wrappers
from openai import OpenAI
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT


client = Client()
openai_client = wrappers.wrap_openai(OpenAI())

dataset = client.create_dataset("sample-qa")
client.create_examples(
    dataset_id=dataset.id,
    examples=[
        {
            "inputs": {"question": "Which country is Mount Kilimanjaro in?"},
            "outputs": {"answer": "Mount Kilimanjaro is in Tanzania."},
        }
    ],
)


def target(inputs: dict) -> dict:
    resp = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "Answer accurately."},
            {"role": "user", "content": inputs["question"]},
        ],
    )
    return {"answer": resp.choices[0].message.content.strip()}


judge = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    model="openai:o3-mini",
    feedback_key="correctness",
)


def correctness(inputs: dict, outputs: dict, reference_outputs: dict):
    return judge(
        inputs=inputs,
        outputs=outputs,
        reference_outputs=reference_outputs,
    )


client.evaluate(
    target,
    data="sample-qa",
    evaluators=[correctness],
    experiment_prefix="qa-eval",
)
```

## 在线评测怎么走

在线评测的思路不一样。它面对的是没有标准答案的真实流量。

典型流程：

1. 应用上线，持续产生 run / trace
2. 给线上流量挂自动 evaluator
3. 实时监控异常和评分波动
4. 把坏样本回灌到离线 dataset

这里和离线评测最大的区别是：线上 evaluator 往往没有标准答案，更多是在做格式检查、安全检查、参考无关的质量打分。

这就形成了一个闭环：**线上发现问题，线下复现和修复。**

## Evaluator 常见类型

| 类型 | 特点 | 适合场景 |
|------|------|----------|
| **Human** | 最准，但贵且慢 | 高价值样本抽检 |
| **Code** | 稳定、便宜 | 格式检查、关键词、规则校验 |
| **LLM-as-judge** | 灵活，覆盖面广 | 语义质量、相关性、礼貌性 |
| **Pairwise** | 比较两个版本谁更好 | prompt / 模型 AB 对比 |

一个很务实的组合通常是：

- 格式类问题用 code evaluator
- 语义类问题用 LLM-as-judge
- 关键路径再抽一些人工 review

## Offline 和 Online 的分工

### Offline 适合回答

- 新 prompt 比旧 prompt 好了吗
- 换模型后有没有回归
- 某个工具调用策略是不是更稳

### Online 适合回答

- 线上最近是不是突然变差了
- 某类用户请求是否持续翻车
- 某个模型版本上线后成本和质量有没有异常

## 一个最实用的数据来源

很多团队一开始卡在“没有 dataset”。LangSmith 文档其实给了非常现实的答案：**先从 trace 里捞。**

最该进数据集的，往往不是你脑补出来的样本，而是线上真的把系统打崩过的那些输入。

## 评测别只看总分

总分经常没什么用。更该看的是：

- 哪一类样本退化了
- 哪个 evaluator 开始掉分
- 哪个版本提升了质量但把时延和成本拉高了

也就是说，评测不是只看“高不高”，而是看“变了什么，代价是什么”。

## 一个简化的闭环

```text
线上 trace
   ↓
筛坏样本
   ↓
沉淀 dataset
   ↓
离线 experiment
   ↓
改 prompt / 模型 / 工作流
   ↓
重新上线
   ↓
继续在线监控
```

这才是 LangSmith 评测章节最想传达的东西。
