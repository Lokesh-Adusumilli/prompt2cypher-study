# Prompt2Cypher

Prompt2Cypher (P2C) is a two-step method for translating natural-language questions into
Cypher queries over a knowledge graph:

1. **Step 1 — node selection.** An LLM is shown the graph's node **labels** and selects the
   ones relevant to the question.
2. **Relationship derivation (deterministic).** Code keeps a relationship whenever its
   `from` **or** `to` label was selected, yielding a focused subgraph.
3. **Step 2 — generation.** The LLM generates Cypher over that filtered subgraph, with
   schema comments and task instructions.

The study evaluates P2C against a single-call **baseline** (full schema, no filtering) on
two biomedical knowledge graphs — **ProKinO** (protein kinases) and **ICKG** (ion
channels) — across hosted and local models, and reports where the two-step decomposition
helps and why.

## Documentation

Read these in order:

| Document | Purpose |
|---|---|
| [`SETUP.md`](SETUP.md) | Environment, and building the two Neo4j databases from source. |
| [`data/prokino/README.md`](data/prokino/README.md) | ProKinO construction guide (download + import). |
| [`data/ickg/README.md`](data/ickg/README.md) | ICKG construction guide (download + import). |
| [`REPRODUCTION.md`](REPRODUCTION.md) | Reproducing Table 2, Table 3, Table 4, and Figure 6 — step by step. |

## Repository layout

```
data/<kg>/        schema, schema comments, the 30 test queries, and gold results per KG
prompts/          Step-1 node-relevance and per-KG Step-2 instruction templates
src/              database-build pipeline + the generation/execution/scoring code
src/ablation/     the ablation framework that produces the paper's runs
reproduce/        re-score the shipped runs into the paper's numbers (no model calls)
additional_experiments/  Table 3, Figure 6, and supporting diagnostics (see its README)
results/<kg>/     shipped generated-Cypher runs the reproduction reads
```

## Quick start

```bash
conda create -n prompt2cypher python=3.10 && conda activate prompt2cypher
pip install -r requirements.txt
# then open .env and replace the placeholder values (Neo4j credentials, etc.)
```

Build the databases ([`SETUP.md`](SETUP.md)), then reproduce the results
([`REPRODUCTION.md`](REPRODUCTION.md)). The reported numbers come from the **ablation
framework** (`src/ablation/`); the mapping from ablation conditions to paper tables, and
the exact commands, are in [`REPRODUCTION.md`](REPRODUCTION.md).
