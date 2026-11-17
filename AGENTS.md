# GraphRAG Financial Report

- Read USAGE.md for setup and ARCHITECTURE.md for the pipeline and design.
- Keep the existing CLI entry points in src/ and the FastAPI routes documented in USAGE.md working.
- Run `python -m compileall -q src` and `python -m unittest discover -s tests -v` from the repository root after installing requirements.txt. Keep default CI offline with respect to Neo4j and model providers.
- Use a disposable Neo4j database for integration tests. The optional `build_graph.py --clear` flag deletes the existing graph.
- Keep local environment files, real credentials, and source annual-report inputs out of Git. Use .env.example for variable names and keep changes to published evaluation snapshots reproducible.
- When reporting new evaluation results, record the input corpus, question set, model configuration, baseline, and reproduction command.
