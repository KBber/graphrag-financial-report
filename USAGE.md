# USAGE

One-shot reproduction guide. The project ships with reproducible
artifacts in `outputs/` (triples, communities, evaluation), so you
can run the API service against an existing graph without re-extracting
or re-indexing.

## 0. Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Python    | ≥ 3.10  | tested on 3.14 |
| Neo4j     | ≥ 4.4   | bolt on `localhost:7687` |
| JDK       | 11+     | for Neo4j 4.x |
| DeepSeek API key | – | extraction + answer generation |
| DashScope API key | – | `text-embedding-v3` for entity linking |

Annual-report JSONs: 15 files, shape
`<stock_code>_<year>_<name>_<title>.json`, in `data/parsed/`.

## 1. Install

```bash
pip install -r requirements.txt
```

Key dependencies (full list in `requirements.txt`):
`openai`, `neo4j`, `networkx`, `igraph`, `leidenalg`,
`faiss-cpu`, `rank_bm25`, `jieba`, `fastapi`, `uvicorn`.

## 2. Configure environment

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_PASSWORD=your_local_neo4j_password
export DEEPSEEK_API_KEY=sk-...
export DASHSCOPE_API_KEY=sk-...
```

Use a dedicated local Neo4j instance with the `neo4j` user. The scripts
read the process environment. [.env.example](.env.example) lists the
variables for reference. On PowerShell, use `$env:NAME = 'value'`.

## 3. Prepare input

```bash
mkdir -p data/parsed
# Place 15 annual-report JSONs here
ls data/parsed/ | head
# 000858_2021_五粮液_五粮液2021年年度报告.json
# 000858_2022_五粮液_五粮液2022年年度报告.json
# ...
```

If the corpus is missing, the pipeline stops at `extract_triples.py`
with `FileNotFoundError: parsed file ... not found`.

## 4. Run the full pipeline

```bash
cd src

# 4.1 Triple extraction (~6 min for 15 reports × 25 blocks each)
python extract_triples.py --max-blocks-per-report 25

# 4.2 Ingest to a dedicated local Neo4j instance
python build_graph.py

# 4.3 Leiden community detection + DeepSeek summary
python community_detect.py

# 4.4 Start the API service
uvicorn serve:app --host 127.0.0.1 --port 8000
```

## 5. Try the API

```bash
# Health check
curl -sS http://localhost:8000/health
# {"status":"ok","neo4j":"connected","nodes":205,"edges":223,"global_ready":true}

# Standard query
curl -sS -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  --data '{"question":"五粮液2023年的营业收入是多少？"}'

# Debug (also returns linked entities + subgraph)
curl -sS -X POST http://localhost:8000/query/debug \
  -H "Content-Type: application/json" \
  --data '{"question":"五粮液有哪些子公司？持股比例是多少？"}'

# Swagger UI
open http://localhost:8000/
```

## 6. Re-run evaluation

```bash
python eval_compare.py
# reads outputs/eval_compare.json (snapshot) and reruns all 15 questions
# across GraphRAG and the optional vector-RAG baseline (if sibling
# rag_annual_report is present)
```

The `eval_compare.py` script degrades gracefully if the vector-RAG
dependency is missing — only GraphRAG is required.

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Neo.ClientError.Security.CredentialsExpired` | First-run password reset | In Neo4j Browser, set a new password for `neo4j` and update `NEO4J_PASSWORD` |
| `EnvironmentError: 请设置环境变量 DEEPSEEK_API_KEY` | Missing key | `export DEEPSEEK_API_KEY=sk-...` |
| `graphrag` answers empty for valid questions | `data/parsed` was not loaded or triples weren't ingested | Re-run `extract_triples.py` then `build_graph.py` |
| `ModuleNotFoundError: igraph` | install dropped | `pip install igraph==0.11.* leidenalg==0.10.*` |

## 8. Reuse the published artifacts

Run `python build_graph.py` from `src/` to load `outputs/triples.jsonl`
into a dedicated local Neo4j instance without calling a model. The source
annual-report JSON files are needed only when re-running extraction.
The API still needs DashScope for entity linking and DeepSeek for answer
generation. Run `python community_detect.py` to regenerate community
summaries if you change the graph.

`build_graph.py --clear` deletes the existing graph. Use it only when
resetting a disposable development database.
