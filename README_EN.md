# graphrag-financial-report

**[中文文档 (Chinese)](README.md)** | **[English](README_EN.md)**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![Neo4j 4.4+](https://img.shields.io/badge/neo4j-4.4%2B-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

A research / teaching implementation of the **GraphRAG** paradigm
applied to **Chinese listed-company annual reports**. The pipeline
extracts a typed knowledge graph from fifteen reports (five
companies × three years), ingests it into **Neo4j 4.4+**, and
serves natural-language queries through a dual-mode retrieval API
that combines **Local Search** (entity-linked neighborhood
expansion) with **Global Search** (Leiden-community Map-Reduce).

> **A self-contained, no-GDS-plugin GraphRAG stack in ≈1,200 lines of
> Python, plus a FastAPI service and a side-by-side evaluation
> against a vector-RAG baseline.**

---

## 1. Why this project exists

Annual reports are dense, multi-hop, and entity-heavy (256 sections
per report, dozens of subsidiaries per company, overlapping boards).
Vector-RAG answers "find the paragraph that says X" well, but fails
at "which subsidiaries does the chairman of A also control?". The
GraphRAG paradigm (Edge et al., 2024) is the natural fit.

This repo implements both retrieval modes from scratch — no
`graphrag` package, no Neo4j GDS plugin — so the entire pipeline is
auditable and tunable. The code reads top-to-bottom in
`src/extract_triples.py → build_graph.py → community_detect.py →
serve.py`.

## 2. Headline results

Run on the 15-report corpus (5 companies × 3 years):

| Component | Value |
|-----------|-------|
| Reports processed | 15 |
| Blocks sampled per report | 25 |
| Triples extracted | **374** |
| Graph nodes (after ingest) | ~205 |
| Graph edges (after ingest) | ~223 |
| Leiden communities | 4 (modularity-optimized) |
| **GraphRAG answer accuracy** | **14/15** |
| vector-RAG answer accuracy | 15/15 |
| **GraphRAG latency (mean)** | **1.76 s** |
| vector-RAG latency (mean) | 6.02 s |

GraphRAG wins on **multi-hop relational** questions (e.g. "which
subsidiaries does the chairman of A control?"); vector-RAG wins on
**verbatim text-lookup** questions.

## 3. Pipeline at a glance

```
                ┌─────────────────────────┐
                │  data/parsed/ (15 JSONs) │
                └────────────┬────────────┘
                             │  (1) extract_triples.py
                             │      DeepSeek JSON-mode prompts
                             ▼
                ┌─────────────────────────┐
                │  outputs/triples.jsonl   │  374 triples
                └────────────┬────────────┘
                             │  (2) build_graph.py
                             ▼
                ┌─────────────────────────┐
                │   Neo4j 4.4 (bolt:7687) │
                └────────────┬────────────┘
                             │  (3) community_detect.py
                             ▼
                ┌─────────────────────────┐
                │  outputs/communities.json│ Leiden + per-community summaries
                └────────────┬────────────┘
                             │  (4) serve.py
                             ▼
                ┌─────────────────────────┐
                │   FastAPI :8000         │  /health /query /query/debug
                └─────────────────────────┘
```

## 4. Schema

Seven entity types and eight relation types, enforced **in the
extraction prompt** rather than in a post-hoc parser:

| Entity | Examples |
|--------|----------|
| Company | 贵州茅台, 宁德时代 |
| Person | 董监高, 实控人, 股东 |
| Subsidiary | 控股/参股公司 |
| Product | 主要产品 |
| Indicator | 营业收入, 净利润, 研发投入 |
| Segment | 业务板块 |
| Region | 境内 / 境外 |

| Relation | Schema | Edge property |
|----------|--------|----------------|
| REPORTS | (Company)→(Indicator) | `year`, value in object string |
| SERVES_AS | (Person)→(Company) | `role` |
| CONTROLS | (Person/Company)→(Company) | ratio |
| HAS_SUBSIDIARY | (Company)→(Subsidiary) | `ratio` |
| PRODUCES | (Company)→(Product) | – |
| OPERATES_IN | (Company)→(Region) | – |
| INVESTS_IN | (Company)→(Segment/Project) | – |
| RELATED_TO | fallback | – |

## 5. Local vs Global Search

| Aspect | Local Search | Global Search |
|--------|--------------|---------------|
| Trigger | "Which subsidiaries does X have?" | "Compare R&D across all 5 firms" |
| Pipeline | entity-link → 1-hop subgraph → DeepSeek | top-K community similarity → Map → Reduce |
| Latency (mean) | ≈ 1.76 s | higher (multiple LLM calls) |
| Strength | multi-hop relational, high context precision | holistic, cross-entity aggregation |

## 6. Quick start

```bash
git clone https://github.com/KBber/graphrag-financial-report
cd graphrag-financial-report
pip install -r requirements.txt

# Environment
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=123456
export DEEPSEEK_API_KEY=sk-...
export DASHSCOPE_API_KEY=sk-...

# Place 15 annual-report JSONs in data/parsed/ and run:
cd src
python extract_triples.py --max-blocks-per-report 25
python build_graph.py --clear
python community_detect.py
uvicorn serve:app --host 0.0.0.0 --port 8000

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"五粮液2023年的营业收入是多少？"}'
```

## 7. Repository layout

```
graphrag-financial-report/
├── README.md                   # Chinese narrative
├── README_EN.md                # this file
├── ARCHITECTURE.md             # design + pitfalls
├── USAGE.md                    # one-shot reproduction
├── LICENSE                     # MIT
├── requirements.txt
├── src/                        # ~1200 LOC across 7 files
├── outputs/                    # triples, communities, evaluation
└── static/                     # Swagger UI
```

## 8. Limitations

1. **The 15-report corpus is not in the repo.** Re-supply your
   own annual-report JSONs under `data/parsed/`.
2. **Schema is hand-curated** for Chinese A-share reports; foreign
   filings need a different prompt.
3. **Entity linking is FAISS over DashScope embeddings**; no alias
   resolution for company renames.
4. **No incremental updates** — every `build_graph.py --clear` wipes
   the graph.
5. **Global Search is sequential** over communities.

## 9. References

- Edge, D. et al. (2024). *From Local to Global: A GraphRAG Approach
  to Query-Focused Summarization*. arXiv:2404.16130.
- Traag, V. A., Waltman, L., van Eck, N. J. (2019). *From Louvain
  to Leiden: guaranteeing well-connected communities*. Sci. Rep.
- DeepSeek-AI. DeepSeek Chat API. <https://platform.deepseek.com>
- Neo4j, Inc. Neo4j 4.4 Operations Manual.

## 10. License

MIT. See [LICENSE](LICENSE).