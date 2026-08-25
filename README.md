# graphrag-financial-report

**[English documentation](README_EN.md)**

A **GraphRAG (Graph + Retrieval-Augmented Generation)** pipeline for
**Chinese listed-company annual reports**: it extracts a typed
knowledge graph from 15 reports (5 companies × 3 years), stores it in
**Neo4j**, and answers natural-language questions through a
**dual-mode retrieval service** (Local Search + Global Search).

> **A research project that turns a financial PDF corpus into a
> queryable knowledge graph and compares it head-to-head with a
> classical vector-RAG baseline.**

---

## TL;DR

Given the 15 annual reports in `data/parsed/`, the full pipeline:

1. **Extract** structured triples (Company / Person / Subsidiary /
   Product / Indicator / Segment / Region entities; 8 relation types)
   using **DeepSeek** structured-output prompts.
2. **Build** a Neo4j graph (~205 nodes / ~223 edges after one run)
   with a stable `Entity.uid` schema and merge-on-write.
3. **Detect communities** with the **Leiden algorithm** (python-igraph
   fallback, no GDS plugin required) and produce a community
   summary per cluster.
4. **Serve** a FastAPI / uvicorn service at
   `http://localhost:8000` with `/health`, `/query`, and
   `/query/debug` endpoints.
5. **Evaluate** GraphRAG vs vector-RAG on 15 fixed questions
   (See `outputs/eval_compare.json`).

> **Live numbers from a representative run:**
> - 15 reports · 156 blocks · **374 triples** extracted
> - **GraphRAG: 14/15 answer-correct** vs **vector-RAG: 15/15**
> - GraphRAG **latency ≈ 1.76 s** vs vector-RAG **≈ 6.02 s**
> - GraphRAG wins on **multi-hop relational questions**, vector-RAG
>   wins on **verbatim text-lookup questions**.

---

## Table of Contents

- [Why GraphRAG?](#why-graphrag)
- [Architecture](#architecture)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Evaluation](#evaluation)
- [Limitations](#limitations)
- [References](#references)
- [License](#license)

---

## Why GraphRAG?

Annual reports are **dense, multi-hop, and entity-heavy**: 256
sections per report, hierarchical layout, dozens of subsidiaries
per company, overlapping boards. Vector-RAG excels at "find the
paragraph that says X" but fails at "which subsidiaries does the
chairman of company A also control?". GraphRAG builds an explicit
**typed graph** and supports both:

- **Local Search**: entity-linking → neighbor expansion → subgraph →
  LLM composition (answers "give me the subsidiaries of X").
- **Global Search**: Leiden community detection → per-community
  summaries → Map-Reduce over communities (answers "compare R&D
  investment across all 5 companies").

This repo implements both modes in **~1,200 lines of Python** with no
external GraphRAG library — useful as a teaching artifact.

## Architecture

```
┌────────────────┐  1. extract_triples.py
│  data/parsed/  │ ────────────────────────────►  outputs/triples.jsonl
│  (15 reports)  │   (DeepSeek JSON-mode)
└────────────────┘
                          │
                          ▼
┌────────────────┐  2. build_graph.py
│   Neo4j 4.4+   │ ◄───────── MERGE / Entity.uid ─────────┐
│  (bolt:7687)   │                                        │
└────────────────┘                                        │
                          ▲                               │
                          │                               │
┌────────────────┐  3. community_detect.py                │
│ Leiden clusters │ →  outputs/communities.json           │
└────────────────┘   (community summaries)                │
                                                           │
┌────────────────┐  4. retrieve.py (GraphRAG)             │
│ FastAPI service │ ◄─────────────────────────────────────┘
│  GET  /health   │
│  POST /query    │  ← Local or Global
│  POST /query/d… │  ← Local + subgraph
└────────────────┘
        │
        ▼
┌────────────────┐  5. eval_compare.py
│ outputs/eval_…  │   (GraphRAG vs vector-RAG)
└────────────────┘
```

### Design choices

- **Entity.uid is the merge key** (`uid_of(name, type)`), so the same
  company or person mentioned in two reports collapses to one node.
- **Schema is enforced in the prompt**, not the parser. Eight
  relation types and seven entity types — anything else is
  rejected.
- **Subgraph truncation** prefers non-`Indicator` neighbors first;
  Indicators are the majority class and would crowd out human-relevant
  entities if unfiltered.
- **Global Search** uses Leiden *via igraph + leidenalg* (no Neo4j
  GDS plugin required), then a separate DeepSeek call summarizes each
  community.
- **No external GraphRAG library**. The naming borrows the paradigm,
  not Microsoft's reference implementation.

## Repository Layout

```
graphrag-financial-report/
├── README.md                   # this file
├── README_EN.md                # English edition
├── ARCHITECTURE.md             # design choices and pitfalls
├── USAGE.md                    # one-shot reproduction
├── LICENSE                     # MIT
├── requirements.txt            # pinned versions (see below)
├── src/
│   ├── llm_client.py           # DeepSeek + DashScope clients (env-driven)
│   ├── extract_triples.py      # prompt + structured-output → triples.jsonl
│   ├── build_graph.py          # MERGE-based Neo4j writer
│   ├── community_detect.py     # Leiden + community summarization
│   ├── retrieve.py             # GraphRAGLocal, GraphRAGGlobal
│   ├── serve.py                # FastAPI app + lifespan + endpoints
│   └── eval_compare.py         # GraphRAG vs vector-RAG (15 questions)
├── outputs/                    # reproducible artifacts
│   ├── triples.jsonl           # 374 triples from the 15-report run
│   ├── communities.json        # Leiden clusters + DeepSeek summaries
│   └── eval_compare.json       # 15-question evaluation table
├── static/                     # front-end for `/` Swagger UI
│   ├── index.html
│   └── viz/force_graph.js
└── (legacy: data/parsed, evaluation/ exist in the original layout
    but are intentionally not tracked in this repo — see USAGE.md)
```

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Neo4j 4.4+** running locally on `bolt://localhost:7687`
  (default credentials overridden by env vars; see below)
- **DeepSeek API key** (extraction + answer generation)
- **DashScope API key** (text-embedding-v3 for entity linking)
- Annual-report JSONs in `data/parsed/` — 15 files of shape
  `000858_2021_五粮液_五粮液2021年年度报告.json`

### Setup

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure secrets and Neo4j
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=123456
export DEEPSEEK_API_KEY=sk-...
export DASHSCOPE_API_KEY=sk-...

# 3. (Optional) place your reports in data/parsed/
mkdir -p data/parsed
# copy / generate the 15 JSON files there
```

### Run the full pipeline

```bash
cd src
python extract_triples.py --max-blocks-per-report 25   # ~6 min
python build_graph.py --clear                           # reset + write graph
python community_detect.py                             # Leiden + summaries
uvicorn serve:app --host 0.0.0.0 --port 8000          # API service
```

### Ask a question

```bash
curl -sS -m 90 -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  --data '{"question":"五粮液2023年的营业收入是多少？"}'
```

## API Reference

| Method | Path | Returns |
|--------|------|---------|
| GET  | `/health`      | `{status, neo4j, nodes, edges, global_ready}` |
| POST | `/query`       | `{answer, context}` (mode auto-detected) |
| POST | `/query/debug` | same + `linked_entities` + `subgraph` |
| GET  | `/`            | Swagger UI |

`QueryRequest`: `{question: str, mode?: "local"|"global"}`.

`GraphRAGLocal` pipeline: embedding → entity-link (FAISS) →
neighbor expansion (1-hop, type-prioritized truncation) →
context assembly → DeepSeek composition.

`GraphRAGGlobal` pipeline: community-similarity retrieval →
**Map** (per-community partial answer) → **Reduce** (final answer).

## Evaluation

`outputs/eval_compare.json` ships a snapshot from one end-to-end run:

| Side | Answer accuracy | Context hit-rate | Avg latency |
|------|----------------:|-----------------:|------------:|
| **GraphRAG** | **14/15** | **14/14** | **1.76 s** |
| vector-RAG (FAISS+BM25) | 15/15 | 14/14 | 6.02 s |

Where **GraphRAG wins**:

- "Which subsidiaries does company X have and at what stake?"
- "Where does company Y operate and who serves as board secretary?"
- Any multi-hop relational query (e.g. chairman → controlling
  shareholder → other company).

Where **vector-RAG is more robust**:

- "Quote the 2023 net-income figure for company X verbatim."
  (Text-lookup with high lexical overlap.)

Re-run on a different corpus by replacing `data/parsed/` and
executing the same four commands.

## Limitations

1. **Annual-report corpus is not in this repo** — the original 15
   JSONs lived in a sibling project that was not published. Place
   your own reports in `data/parsed/` (15 JSONs of the same schema)
   before running.
2. **Schema is hand-curated** — the seven entity types and eight
   relations are appropriate for Chinese A-share reports but not for
   Hong Kong or US filings without modification.
3. **Entity linking uses FAISS over DashScope embeddings** — name
   matches are lexical, not semantic. Renamed companies (e.g.
   "Tencent" vs "腾讯") require manual aliases.
4. **No incremental updates** — every `python build_graph.py --clear`
   wipes the graph. Switch to a true MERGE-only path for production.
5. **Global Search is sequential over communities** — parallelize
   across `community_id` if you exceed ~20 communities.

## References

- Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A.,
  Truitt, S., Larson, J. (2024). *From Local to Global: A GraphRAG
  Approach to Query-Focused Summarization*. arXiv:2404.16130.
- Traag, V. A., Waltman, L., van Eck, N. J. (2019). *From Louvain
  to Leiden: guaranteeing well-connected communities*. Sci. Rep.
- DeepSeek-AI (2024). DeepSeek-V2 / DeepSeek Chat API.
  <https://platform.deepseek.com>
- Neo4j, Inc. *Neo4j 4.4 Operations Manual*.
  <https://neo4j.com/docs/operations-manual/4.4/>

## License

MIT. See [LICENSE](LICENSE).