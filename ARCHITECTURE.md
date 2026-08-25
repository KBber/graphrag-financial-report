# ARCHITECTURE

Design choices and pitfalls for the GraphRAG annual-report pipeline.

## 1. Goal and design constraints

- **Goal**: a *teaching-grade* implementation of the GraphRAG
  paradigm (local + global search over a typed knowledge graph), not a
  production system.
- **Corpus**: 15 Chinese listed-company annual reports (5 companies
  × 3 years), pre-parsed into JSON blocks (~256 sections per report).
- **Constraints**:
  - Use **Neo4j 4.x** (community edition, no GDS plugin).
  - Use **OpenAI-compatible LLM** (DeepSeek) + **DashScope embeddings**.
  - Re-implement Local / Global Search in <2 k LOC, no external
    `graphrag` library.

## 2. Schema

Seven entity types, eight relation types. The schema lives in
`src/extract_triples.py::SYSTEM_PROMPT` and is enforced in-prompt:

| Entity | Examples |
|--------|----------|
| Company | 贵州茅台, 宁德时代 |
| Person | 张某 (高管), 曾从钦 (董事长) |
| Subsidiary | 四川省宜宾五粮液酒厂有限公司 |
| Product | (示例中尚未出现, 预留给研报命名产品) |
| Indicator | 营业收入832.72亿元 |
| Segment | 主营业务, 其他业务 |
| Region | 境内, 境外 |

| Relation | Pattern |
|----------|---------|
| REPORTS | (Company) → (Indicator)         object 携带数值+年份 |
| SERVES_AS | (Person) → (Company)        object 携带职务 |
| CONTROLS | (Person/Company) → (Company)  控股股东/实控人 |
| HAS_SUBSIDIARY | (Company) → (Subsidiary)  object 携带持股比例 |
| PRODUCES | (Company) → (Product)         |
| OPERATES_IN | (Company) → (Region)       |
| INVESTS_IN | (Company) → (Segment/Project) |
| RELATED_TO | (entity) → (entity)         兜底 |

## 3. Graph build

`build_graph.py` writes via `MERGE` keyed on `Entity.uid =
uid_of(name, type)`. Same (name, type) across reports collapses to one
node; relations store `year / role / ratio` as edge properties so
multi-year / multi-role facts are preserved.

Schema (constraints) is installed by `ensure_constraints()`:

```cypher
CREATE CONSTRAINT entity_uid IF NOT EXISTS FOR (n:Entity) REQUIRE n.uid IS UNIQUE;
```

## 4. Subgraph truncation policy (Local Search)

`retrieve.py::_expand_subgraph` walks 1 hop from linked entities, then
sorts neighbors so that non-`Indicator` nodes come first. Without this
trick, `Indicator` would dominate (it accounts for ~63% of the graph),
and the LLM context would be a wall of "营业收入X亿元" triples with
no company / person / region information.

Truncation bound: `MAX_SUBGRAPH=40` nodes, configurable at the top of
`retrieve.py`.

## 5. Community detection (no GDS plugin)

`community_detect.py` uses `python-igraph` + `leidenalg`:

```python
g = ig.Graph.from_networkx(G_nx)
partition = leidenalg.find_partition(
    g, leidenalg.ModularityVertexPartition,
    n_iterations=2, seed=42
)
```

Each community's representative entities (top-15 by degree) are
summarized by DeepSeek; the result is cached in
`outputs/communities.json` for `GraphRAGGlobal` to read at boot.

## 6. Local vs Global Search

### Local Search (default)
1. `NodeNameIndex.link(qvec, top_k=3)` — DashScope embedding of
   the question, FAISS cosine against pre-computed node-name vectors.
2. Neighbor expansion (1 hop, type-prioritized truncation).
3. Build `[实体] / [关系]` context string.
4. DeepSeek `deepseek-chat` composes the answer.

### Global Search
1. Cosine-similarity over pre-computed community-summary vectors.
2. Take top-K (`COMM_TOPK=3`) communities.
3. **Map** step: DeepSeek generates a partial answer per community.
4. **Reduce** step: DeepSeek integrates the partials.

The Map-Reduce decomposition is sequential in this implementation;
parallelization is straightforward via `concurrent.futures.ThreadPoolExecutor`
but was omitted to keep the teaching artifact readable.

## 7. Service lifecycle

`serve.py::lifespan` loads both retrievers once at startup. GraphRAGLocal
hits Neo4j directly on every query; GraphRAGGlobal loads
`outputs/communities.json` into memory at startup.

## 8. Engineering pitfalls (踩坑表)

| Symptom | Root cause | Fix |
|---------|------------|-----|
| `Neo4j 4.x` 默认 `neo4j/neo4j` 强制首次改密 | Security policy | ALTER USER … SET PASSWORD … CHANGE NOT REQUIRED |
| `No module named 'graphrag'` | 故意不依赖外部 `graphrag` 库 | 自实现 Local/Global Search |
| 抽取 `Indicator` 节点太多淹没人名/地区 | `Indicator` 占节点总数 ~63% | Local Search 子图截断按类型优先 |
| `find_partition` 缺 `ModularityVertexPartition` | `leidenalg 0.12` 与 `igraph 1.0` 接口变化 | 显式传 `ModularityVertexPartition + Optimiser` |
| 实体链接命中率低 | 节点名向量化只用一次 | 节点名首尾空白 strip + 同名合并 |
| 评估向量 RAG 缺依赖 | `rag_annual_report` 子项目未在同级目录 | `eval_compare.py` 检测后优雅降级 |

## 9. Reproducibility hooks

- **Random seed**: `community_detect.py` uses `seed=42` for Leiden
  partitioning.
- **Cacheable outputs**: `outputs/triples.jsonl` and
  `outputs/communities.json` are the canonical artifacts. Re-running
  the pipeline overwrites them but produces the same effective results
  (modulo LLM stochasticity).
- **Cost control**: 15 reports × 25 blocks = 375 extraction calls.
  Each call uses `response_format=json_object` so the LLM returns a
  single parseable JSON object. `extract_stats.json` records the
  total tokens and elapsed seconds.

## 10. What is *not* in this repo

- The 15 parsed annual-report JSONs (deliberately not committed;
  re-supply your own under `data/parsed/`).
- A Neo4j dump (the graph is reproducible from `triples.jsonl`).
- The vector-RAG pipeline (optional baseline; see
  `eval_compare.py::run_vectorrag`).