# Simpler

把厚内容读薄。丢进来 PDF、DOCX、PPTX、XLSX，砍掉废话，输出干净的 Markdown（可选生成 PDF）。

不限于技术书，什么材料都能简化——教材、论文、培训手册、规范文档，只要你觉得太长了。

目前处理过的：

| 内容 | 原始规模 | 精简后 | PDF |
|------|---------|--------|-----|
| OSTEP（操作系统导论） | 26 章 | 26 节 / 1396 行 | `ostep-simplified.pdf` |
| Redis 设计与实现 | 23 章 | 14 节 / 895 行 | `redis-simplified.pdf` |
| MySQL 是怎样运行的 | 27 章 | 15 节 / 2868 行 | `mysql-simplified.pdf` |

## 目录结构

```text
source/<名称>/        ← 原始素材（PDF/DOCX/PPTX/XLSX/Markdown 等）
simplified/<名称>/    ← 精简后的 Markdown
simplified/*-simplified.pdf  ← 生成的 PDF（可选）
scripts/build_pdf.py  ← PDF 生成脚本
.opencode/agents/     ← AI 代理配置（简化工作流）
.opencode/skills/     ← AI 技能包（文件提取、去 AI 味等）
```

## 用法

### 环境准备

```bash
# 系统字体（PDF 渲染需要）
apt-get install -y fonts-wqy-microhei fonts-noto-mono

# Python 依赖
uv venv .venv
uv pip install reportlab markdown
```

### 简化内容

把素材丢进 `source/<名称>/`，用 opencode 的 simpler agent 跑简化。agent 会自动识别文件类型、提取文本、精简、输出 Markdown 到 `simplified/<名称>/`。

手动简化也行，按下面的命名规则来就好。

### 生成 PDF

```bash
.venv/bin/python scripts/build_pdf.py          # 全部构建
.venv/bin/python scripts/build_pdf.py mysql    # 只构建 MySQL
.venv/bin/python scripts/build_pdf.py ostep    # 只构建 OSTEP
.venv/bin/python scripts/build_pdf.py redis    # 只构建 Redis
```

输出到 `simplified/<名称>-simplified.pdf`。

### 添加新内容

1. 素材放到 `source/<名称>/`
2. 精简后输出到 `simplified/<名称>/`，文件命名 `<名称>-<部分>-<章>.md`
3. 要生成 PDF 的话，在 `scripts/build_pdf.py` 的 `BOOKS` 字典里加一条配置
4. 跑 `build_pdf.py <名称>`

## 例子：MySQL 是怎样运行的

原书 27 章。砍掉阅读指南、字符集、数据目录、optimizer trace 这类看了也记不住的章节（9 章），剩下的该合并合并、该缩短缩短，最后分三个部分加一个速查：

```text
simplified/mysql/
├── mysql-00-01.md   ← 常用命令速查（新写的，原书没有）
├── mysql-01-01.md   ← InnoDB 记录结构
├── mysql-01-02.md   ← InnoDB 数据页结构
├── mysql-01-03.md   ← B+ 树索引
├── mysql-01-04.md   ← B+ 树索引的使用
├── mysql-01-05.md   ← Buffer Pool
├── mysql-02-01.md   ← 单表访问方法
├── mysql-02-02.md   ← 连接的原理
├── mysql-02-03.md   ← 查询优化规则（原书 1048 行 → 186 行）
├── mysql-02-04.md   ← EXPLAIN 详解（两章合一章）
├── mysql-03-01.md   ← 事务简介
├── mysql-03-02.md   ← redo 日志（两章合一章）
├── mysql-03-03.md   ← undo 日志（两章合一章）
├── mysql-03-04.md   ← 事务隔离级别与 MVCC
└── mysql-03-05.md   ← 锁
```

怎么砍的：

- 铺垫性章节（字符集、数据目录等）直接删，9 章没了
- 上下篇合并（redo 上 + redo 下 → 一个文件）
- 核心概念多留细节，边角内容压缩或删掉
- 补了个命令速查——原书没有但查起来方便

PDF 配置在 `build_pdf.py` 的 `BOOKS["mysql"]` 里：

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
    "files": [ ... ],
}
```

## PDF 效果

浅黄底色、天蓝标题、红色重点标注。有封面、可点击目录、分部分隔页、自动分页。中文用文泉驿微米黑，代码用 NotoSansMono。

## AI 辅助

用 [opencode](https://github.com/opencode-ai/opencode) 的 agent 跑简化流程。配置在 `.opencode/agents/simpler.md`，技能包在 `.opencode/skills/`（PDF/DOCX/PPTX/XLSX 提取、`humanizer-zh` 去 AI 味）。
