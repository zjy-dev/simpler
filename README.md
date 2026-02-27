# Simpler

把厚内容读薄。PDF、DOCX、PPTX、XLSX 丢进来，砍完输出 Markdown，需要的话再生成 PDF。

不限技术书——教材、论文、培训手册、规范文档，太长的都能砍。

已经处理过：

| 内容 | 原始 | 精简后 | 压缩率 |
|------|------|--------|--------|
| MySQL 是怎样运行的 | 27 章 / 12507 行 | 15 节 / 2868 行 | 77% |
| OSTEP（操作系统导论） | 26 章 | 26 节 / 1396 行 | — |
| Redis 设计与实现 | 23 章 | 14 节 / 895 行 | — |

## 目录

```text
source/<名称>/                ← 原始素材
simplified/<名称>/            ← 精简后 Markdown
simplified/<名称>-simplified.pdf  ← PDF（可选）
scripts/build_pdf.py          ← PDF 生成
.opencode/agents/simpler.md   ← agent 配置
.opencode/skills/             ← 技能包（提取、去 AI 味等）
```

## 快速开始

```bash
# 装字体（PDF 渲染需要）
apt-get install -y fonts-wqy-microhei fonts-noto-mono

# Python 环境
uv venv .venv && uv pip install reportlab markdown
```

素材丢进 `source/<名称>/`，然后交给 [opencode](https://github.com/opencode-ai/opencode) 的 simpler agent 跑简化。手动简化也行，文件名按 `<名称>-<部分>-<章>.md` 排就好。

生成 PDF：

```bash
.venv/bin/python scripts/build_pdf.py mysql    # 只构建 MySQL
.venv/bin/python scripts/build_pdf.py          # 全部构建
```

---

## 拿 MySQL 举个例子

用《MySQL 是怎样运行的》走一遍从拿素材到出 PDF 的流程。

### 提示词

在 opencode 里选 simpler agent，一条提示词搞定。处理 MySQL 时实际用的：

```text
简化《MySQL 是怎样运行的：从根儿上理解 MySQL》, 要求:

- 内容在 git@github.com:Relph1119/mysql-learning-notes.git 仓库, 自己 clone 并 mv 进 source, 注意维护好图片
- 以后端面试为目的简化
- 直接删掉无关章节, 可以重新编号
- 只保留纯知识内容, 引用、问题、作业都删掉
- 抛砖引玉的砖也删掉（比如调度算法只留多级反馈队列就够了）
- 原书没有的话, 新增一节 MySQL 常用命令速查
- 用 humanizer-zh 改写, 符合我的阅读习惯
- 最后生成 PDF, 参考 ostep 和 redis 的配置
```

agent 自己完成了整个流程：爬取素材 → 分析 27 章决定删哪些 → 逐批简化 → 去 AI 味 → 配置并生成 PDF。

### agent 做了什么

原书 27 章，agent 逐章过了一遍：

| 处理方式 | 章节 | 理由 |
|---------|------|------|
| **删** | ch00 阅读指南, ch01 认识 MySQL (465行), ch02 启动选项 (517行), ch03 字符集 (767行), ch08 数据目录 (225行), ch09 表空间 (646行), ch12 成本优化 (748行), ch13 统计数据 (355行), ch17 optimizer trace (369行), ch26 参考资料 (109行) | 铺垫、运维向、调试工具、非面试内容 |
| **合并** | ch15+ch16 Explain 上下 (1190行), ch20+ch21 redo 上下 (609行), ch22+ch23 undo 上下 (747行) | 本来就是同一主题 |
| **保留** | ch04-ch07 记录/页/索引, ch10-ch11 查询, ch14 优化规则, ch18 Buffer Pool, ch19 事务, ch24 MVCC, ch25 锁 | 核心知识 + 面试高频 |
| **新增** | 常用命令速查 | 原书没有，补一个 |

10 章直接删（4201 行），3 对合并，剩下逐章精简。

### 输出

27 章砍到 15 个文件，12507 行压到 2868 行：

```text
simplified/mysql/
├── mysql-00-01.md   常用命令速查            (235行, 新写)
├── mysql-01-01.md   InnoDB 记录结构         (124行, ← ch04 541行)
├── mysql-01-02.md   InnoDB 数据页结构       (115行, ← ch05 389行)
├── mysql-01-03.md   B+ 树索引               (208行, ← ch06 406行)
├── mysql-01-04.md   B+ 树索引的使用         (223行, ← ch07 494行)
├── mysql-01-05.md   Buffer Pool             (145行, ← ch18 379行)
├── mysql-02-01.md   单表访问方法            (130行, ← ch10 500行)
├── mysql-02-02.md   连接的原理              (108行, ← ch11 388行)
├── mysql-02-03.md   查询优化规则            (186行, ← ch14 1048行, 压缩 82%)
├── mysql-02-04.md   EXPLAIN 详解            (263行, ← ch15+ch16 合并 1190行)
├── mysql-03-01.md   事务简介                (133行, ← ch19 432行)
├── mysql-03-02.md   redo 日志               (202行, ← ch20+ch21 合并 609行)
├── mysql-03-03.md   undo 日志               (186行, ← ch22+ch23 合并 747行)
├── mysql-03-04.md   MVCC 与隔离级别         (212行, ← ch24 455行)
└── mysql-03-05.md   锁                      (261行, ← ch25 666行)
```

### PDF

agent 自动在 `build_pdf.py` 的 `BOOKS` 里加了一条配置，跑了构建：

```python
"mysql": {
    "title": "MySQL 是怎样运行的 精简版",
    "subtitle": "How MySQL Works: Understanding from the Root",
    "tagline": "速查笔记",
    "tags": "常用命令 · 存储与索引 · 查询优化 · 事务与锁",
    "dir": "mysql",
    "parts": {
        "00": "常用命令速查",
        "01": "第一部分：存储引擎与索引",
        "02": "第二部分：查询优化",
        "03": "第三部分：事务与锁",
    },
    "files": ["mysql-00-01", "mysql-01-01", ...],
}
```

运行 `build_pdf.py mysql` 得到 `mysql-simplified.pdf`（449KB）。浅黄底色 + 天蓝标题 + 红色重点。封面、可点击目录、分部分隔页。中文用文泉驿微米黑，代码用 NotoSansMono。

---

## AI 辅助

用 [opencode](https://github.com/opencode-ai/opencode) 的 agent 跑简化流程。配置在 `.opencode/agents/simpler.md`，技能包在 `.opencode/skills/`（PDF/DOCX/PPTX/XLSX 提取、`humanizer-zh` 去 AI 味）。
