# GraphRAG Financial Report

**GraphRAG over Chinese listed-company annual reports: Typed Knowledge Graph + Neo4j + Local/Global Search**

> 用知识图谱解决财报里的多跳关联查询 —— "这家公司的控股股东，和它第二大客户是什么关系？"

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-018BFF)](https://neo4j.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.10%2B-009688)](https://fastapi.tiangolo.com)

---

## 🎯 问题

传统 RAG 在财报场景的三个失效点：

| 问题 | 表现 |
|---|---|
| **多跳割裂** | "A 的母公司 → A 的子公司 → 子公司持股 B" 中间断开 |
| **事实错误** | 表格里的数字被切碎后召回不完整，LLM 自行补全 |
| **推理不足** | 单点检索拿不到"为什么"和"怎么" |

财报里恰好**全是**多跳关系：股权穿透、关联交易、担保链条、子公司合并范围。

---

## ✨ 架构

```
年报 PDF
   │
   ▼
┌──────────────┐
│ 知识抽取      │  Pydantic 强类型 Schema + 实体消歧
│ Extract      │  → 企业 / 财务指标 / 股东 / 关联交易
└──────┬───────┘
       ▼
┌──────────────┐
│ 质量控制      │  多路校验 + 置信度过滤 + 异常关系拦截
│ Validate     │  → 写入 Neo4j 前的最后一道闸
└──────┬───────┘
       ▼
   ┌──────────┐
   │  Neo4j   │  Typed Knowledge Graph
   └────┬─────┘
        │
   ┌────┴─────────────────┐
   ▼                      ▼
┌─────────────┐   ┌─────────────┐
│ Local Search │   │Global Search│
│ 向量+子图扩展 │   │社区发现+汇总 │
│ 具体事实      │   │ 全局趋势     │
└──────┬──────┘   └──────┬──────┘
       └────────┬─────────┘
                ▼
        ┌──────────────┐
        │  FastAPI      │  Debug Context + 子图可视化
        └──────────────┘
```

---

## ⚡ 关键优化：Global Search 延迟

Leiden 社区发现 + Map-Reduce 汇总天然是 **token 杀手** —— 每个问题都要重跑整张图。

本项目的三板斧：

| 手段 | 效果 |
|---|---|
| **层次化社区摘要缓存** | 社区摘要按层级预计算并缓存，图不变则复用 |
| **异步并发 Map-Reduce** | 并发跑社区摘要，避免串行瓶颈 |
| **高频查询结果预计算** | 宏观分析类问题提前算好，直接命中 |

**结果：15 题多跳复杂测试集，端到端平均延迟 ~1.76s**

---

## 📊 评测

用 Ragas 从三个维度量化：

| 维度 | 衡量什么 |
|---|---|
| **实体召回率** | 该找到的实体有没有被检索出来 |
| **关系准确性** | 抽出的边对不对、有没有错连 |
| **回答忠实度** | 答案是否有原文支撑，是否幻觉 |

配合 **FastAPI + Debug Context + Neo4j 子图可视化**，可以完整追踪：

```
用户问题 → 检索召回 → 子图扩展 → LLM 生成 → 最终答案
   ↑          ↑           ↑           ↑
   └── 每一步都能点开看中间结果 ────┘
```

---

## 🚀 快速开始

```bash
git clone https://github.com/KBber/graphrag-financial-report.git
cd graphrag-financial-report
pip install -e .
```

```bash
# 配置 Neo4j
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
```

```python
from graphrag_financial import GraphRAGService

service = GraphRAGService.from_env()

# 局部查询：具体事实
answer = service.query(
    "宁德时代 2023 年营业收入是多少？",
    mode="local",
)

# 全局查询：宏观趋势
answer = service.query(
    "近三年哪些行业的新能源企业营收增速最快？",
    mode="global",
)
```

---

## 💡 设计取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| Schema | Pydantic 强类型 | 弱 Schema 下实体歧义和关系错连无法在写入前拦住 |
| 图谱写入 | 多路校验 + 置信度过滤 | 图谱一旦污染，检索越准错得越离谱 |
| 全局检索 | 摘要缓存 + 异步并发 | Map-Reduce 的成本主要在重复计算 |
| 可观测性 | Debug Context + 子图可视化 | 无法归因的检索优化 = 玄学调参 |

---

## 📁 Layout

```
graphrag-financial-report/
├── src/
│   ├── extraction/     # 实体关系抽取、消歧
│   ├── graph/          # Neo4j 写入、校验、置信度过滤
│   ├── retrieval/      # Local / Global Search
│   ├── eval/           # Ragas 评测
│   └── api/            # FastAPI + Debug Context
├── benchmarks/         # 15 题多跳测试集
├── docs/
└── tests/
```

---

## 📈 路线图

- [x] 强类型 Schema 知识抽取 + 实体消歧
- [x] Neo4j 多路校验 + 异常关系拦截
- [x] 层次化社区摘要缓存 + 异步 Map-Reduce
- [x] Ragas 评测体系（实体召回 / 关系准确 / 忠实度）
- [x] Debug Context + 子图可视化
- [ ] 增量图谱更新（增量财报不重建全图）
- [ ] 跨年度实体对齐（公司更名、代码变更）
- [ ] Benchmark 公开化 + 多模型对比基线

---

## 📄 License

MIT
