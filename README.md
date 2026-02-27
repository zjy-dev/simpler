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

### 第一步：拿到素材

原书在 GitHub 上有 Markdown 版本，27 个 `.md` 文件加 220 张图片：

```bash
git clone --depth 1 https://github.com/user/mysql-book.git /tmp/mysql-book
cp -r /tmp/mysql-book/docs/mysql/* source/mysql/
cp -r /tmp/mysql-book/docs/images source/mysql/images
```

### 第二步：决定砍哪些

原书 27 章，逐章过一遍：

| 处理方式 | 原始章节 | 理由 |
|---------|---------|------|
| **删除** | ch00 阅读指南 | 看了简化版不需要 |
| **删除** | ch01 重新认识 MySQL (465行) | 入门铺垫，面试不考 |
| **删除** | ch02 启动选项和系统变量 (517行) | 运维向，查文档就行 |
| **删除** | ch03 字符集和比较规则 (767行) | 全书最长的章之一，但面试几乎不问 |
| **删除** | ch08 MySQL 的数据目录 (225行) | 文件系统细节，用不上 |
| **删除** | ch09 InnoDB 的表空间 (646行) | 底层存储细节，面试极少涉及 |
| **删除** | ch12 基于成本的优化 (748行) | 内部实现，知道概念就够 |
| **删除** | ch13 InnoDB 统计数据收集 (355行) | 同上 |
| **删除** | ch17 optimizer trace (369行) | 调试工具，不是核心知识 |
| **删除** | ch26 参考资料 (109行) | 无实际内容 |
| **合并** | ch15+ch16 Explain 上下 (1190行) | 拆成两章没必要 |
| **合并** | ch20+ch21 redo 日志上下 (609行) | 同上 |
| **合并** | ch22+ch23 undo 日志上下 (747行) | 同上 |
| **保留** | ch04 InnoDB 记录结构 (541行) | 核心 |
| **保留** | ch05 InnoDB 数据页结构 (389行) | 核心 |
| **保留** | ch06 B+ 树索引 (406行) | 高频考点 |
| **保留** | ch07 B+ 树索引的使用 (494行) | 高频考点 |
| **保留** | ch10 单表访问方法 (500行) | 查询优化基础 |
| **保留** | ch11 连接的原理 (388行) | 面试常问 |
| **保留** | ch14 基于规则的优化 (1048行) | 核心，但要大砍 |
| **保留** | ch18 Buffer Pool (379行) | 核心 |
| **保留** | ch19 事务简介 (432行) | 核心 |
| **保留** | ch24 MVCC (455行) | 高频考点 |
| **保留** | ch25 锁 (666行) | 高频考点 |
| **新增** | 常用命令速查 | 原书没有，但查起来方便 |

10 章直接删（4201 行），3 对上下篇合并，剩下的逐章精简。

### 第三步：给 agent 的提示词

每次丢给 agent 一批文件（2-3 个），附上精简要求。下面是实际使用的提示词模板：

```text
简化 source/mysql/ 下的以下章节，输出到 simplified/mysql/：

source/mysql/04-从一条记录说起-InnoDB记录结构.md → mysql-01-01.md
source/mysql/05-盛放记录的大盒子-InnoDB数据页结构.md → mysql-01-02.md
source/mysql/06-快速查询的秘籍-B+树索引.md → mysql-01-03.md

简化要求：
- 这是后端面试速查笔记，读者已有基础，不需要从零讲起
- 删掉所有铺垫性的故事和比喻（原书用了大量生活类比，全部去掉）
- 保留核心概念、数据结构、关键参数、SQL 示例
- 图片引用保留，路径改为 images/xx-xx.png
- 每章控制在 120-260 行
```

对于合并型章节，提示词稍有不同：

```text
将以下两章合并简化为一个文件：

source/mysql/20-说过的话就一定要办到-redo日志（上）.md (273行)
source/mysql/21-说过的话就一定要办到-redo日志（下）.md (336行)
→ 输出: mysql-03-02.md

合并要求：
- 两章本来就是一个主题，合并后去掉重复的引言和过渡
- redo log 的写入流程、刷盘策略、崩溃恢复是重点
- Mini-Transaction 概念保留但压缩
- 目标 200 行左右
```

对于新增章节：

```text
根据 MySQL 常用操作，新写一个命令速查：

输出: mysql-00-01.md

要求：
- 涵盖：连接、DDL、DML、索引、事务、锁、变量查看、性能排查
- 全部是可直接复制粘贴的 SQL
- 不需要解释原理，注释写清楚用途就行
- 参考真实业务场景（建表用 BIGINT 主键、utf8mb4 字符集等）
```

### 第四步：结果

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

### 第五步：生成 PDF

在 `build_pdf.py` 的 `BOOKS` 里加一条：

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

然后跑：

```bash
.venv/bin/python scripts/build_pdf.py mysql
# → simplified/mysql-simplified.pdf (449KB)
```

浅黄底色 + 天蓝标题 + 红色重点标注。封面、可点击目录、分部分隔页。中文用文泉驿微米黑，代码用 NotoSansMono。

---

## AI 辅助

用 [opencode](https://github.com/opencode-ai/opencode) 的 agent 跑简化流程。配置在 `.opencode/agents/simpler.md`，技能包在 `.opencode/skills/`（PDF/DOCX/PPTX/XLSX 提取、`humanizer-zh` 去 AI 味）。
