# Reproducing the Results

This document explains, end to end and with no steps left implicit, how to reproduce
every quantitative result in the paper: **Table 2** (main results), **Table 3**
(selection quality), **Table 4** (reference-schema / oracle), and **Figure 6**
(benefit vs. capability).

If you only want to *verify* the reported numbers, follow **Level A** — it re-scores the
model outputs shipped in this repository and makes no model API calls. If you want to
*regenerate* those outputs from the models themselves, follow **Level B**.

Before this document, complete the setup in [`SETUP.md`](SETUP.md): a Python environment,
both Neo4j databases built and running, and a filled-in `.env`.

---

## 1. Concepts you need before running anything

### 1.1 What a "run" is

The paper's numbers come from the **ablation framework** in
[`src/ablation/generate_cypher_ablation.py`](src/ablation/generate_cypher_ablation.py),
**not** from `src/run_benchmarks.py`. One execution of the ablation generator takes one
model and one knowledge graph, runs all 30 test queries, and for each query produces
**four** Cypher strings — one per ablation condition. The output is a single JSON file:

```
results/<kg>/ablation-<model>-<timestamp>.json
```

Each element of that JSON looks like:

```json
{
  "title": "A1",
  "query": "<the natural-language question>",
  "ablation_results": {
    "with_instructions":       "<Cypher>",
    "without_instructions":    "<Cypher>",
    "without_schema_comments": "<Cypher>",
    "without_relevant_nodes":  "<Cypher>"
  }
}
```

These generated-Cypher files are **shipped** in `results/prokino/` and `results/ickg/`,
which is why Level A needs no model calls.

### 1.2 The four ablation conditions, and how they map to the paper

| JSON key in `ablation_results` | Paper name | Meaning |
|---|---|---|
| `with_instructions` | **P2C** (complete system) | Full two-step pipeline: Step-1 LLM selects node **labels**; code derives the relevant relationships (keep a relationship if its `from` **or** `to` label was selected); Step-2 generates Cypher over the filtered subgraph **with** schema comments and task instructions. |
| `without_relevant_nodes` | **Baseline** | Single call over the **full** schema — no node filtering. This is the paper's "baseline." |
| `without_instructions` | (ablation only) | P2C pipeline but the Step-2 task instructions are removed. |
| `without_schema_comments` | (ablation only) | P2C pipeline but schema comments are removed. |

> Throughout the paper and this repo, **"P2C" = `with_instructions`** and
> **"Baseline" = `without_relevant_nodes`**. Keep this mapping in mind — the words
> "baseline" and "P2C" never appear as keys inside the JSON; they are the
> `without_relevant_nodes` and `with_instructions` conditions respectively.

A separate **oracle** (also called **reference-schema**) condition is produced by
[`additional_experiments/exp2_oracle_generate.py`](additional_experiments/exp2_oracle_generate.py)
and stored in `ablation-<model>-oracle-<timestamp>.json` under the key `oracle`. It feeds
the model only the *exact* schema elements the gold query needs — an upper bound on what
perfect node selection could achieve. It is reported for the two local models in Table 4.

### 1.3 How scoring works (identical for every table)

All F1 is **execution-based set overlap**, computed as follows (see
[`reproduce/full_rescore.py`](reproduce/full_rescore.py)):

1. **Strip the cap.** Any trailing `LIMIT 100` is removed from both the gold query and the
   generated query (case-insensitive) before execution. The paper reports **uncapped**
   numbers. (The `LIMIT 100` affected 14/60 gold queries; stripping it is why this is
   called the "uncapped" re-score. See [`additional_experiments/limit_check.py`](additional_experiments/limit_check.py).)
2. **Execute** both queries against the live Neo4j database for that KG, with a **30-second
   timeout**. A query that errors or times out yields an empty result.
3. **Flatten to a set.** Every returned value across all rows/columns is converted to a
   trimmed string and collected into a set (order and duplicates do not matter).
4. **Compare the two sets.** With `P = pred ∩ gold` sizes:
   - precision = `|pred ∩ gold| / |pred|`, recall = `|pred ∩ gold| / |gold|`, F1 = harmonic mean.
   - If **both** sets are empty → score `1.0` (correctly returning nothing).
   - If **exactly one** is empty → score `0.0`.
5. **Macro-average** over the 30 queries. That per-KG, per-condition average is the
   reported number.

The gold result sets are recomputed live from the gold Cypher (the shipped
`*-with_results.json` files are the reference queries + their stored results); the scorer
re-executes the gold Cypher so gold and generated are compared under identical, uncapped
conditions.

### 1.4 Determinism

- **Level A is deterministic.** It only re-executes fixed Cypher strings against the
  databases. Given correctly built databases, you will get the paper's numbers exactly.
- **Level B is stochastic.** It calls the models again; generated Cypher (and therefore the
  scores) will vary run to run, especially for the local models. Expect small deviations,
  not identical values.

---

## 2. Prerequisites (do these once)

1. **Databases built and running** — `prokino-kg` and `ickg`, per [`SETUP.md`](SETUP.md)
   and the two construction guides it links. Table 2 and Table 4 execute queries against
   them; Table 3 and Figure 6 do not.
2. **Python environment** — `conda activate prompt2cypher` and
   `pip install -r requirements.txt` (Python 3.10).
3. **`.env` filled in** (copy the placeholders to real values):
   - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` — required for Table 2 and Table 4.
   - `NEO4J_DATABASE_NAME` — only read by Level B's generator and the regeneration helpers;
     the re-score scripts select the database per KG internally.
   - `DEEPSEEK_API_KEY`, `OPENAI_API_KEY` — only for Level B (regenerating the hosted-model
     runs). Not needed for Level A.
4. **Run every command from the repository root** (paths in all scripts are relative to it).

---

## 3. Level A — reproduce the reported numbers from the shipped runs

No model calls. Four commands. Run them in this order (Figure 6 consumes the output of the
Table 2 step).

### Step A1 — Table 2 (main results)

```bash
python reproduce/full_rescore.py
```

- **Needs Neo4j:** yes (both databases).
- **Reads:** the 8 shipped base runs (listed in §5) and the two gold files.
- **Prints:** one line per model × KG × condition, e.g.
  `done DeepSeek-V4 Pro ProKinO P2C: P=0.936 R=0.936 F1=0.936`.
- **Writes:** [`results/uncapped_results.json`](results/uncapped_results.json) — a map with
  keys `"<model>|<kg>|<Baseline|P2C>"` → `[precision, recall, f1]`.

**Reading it into Table 2:** each row of Table 2 is a model; the Baseline and P2C columns
for ProKinO and ICKG are the `F1` (third element) of the corresponding keys. The four
models are `DeepSeek-V4 Pro`, `GPT-5.4`, `GPT-OSS-20B`, `Qwen2.5-Coder-14B`.

### Step A2 — Table 4 (reference-schema / oracle)

```bash
python reproduce/oracle_rescore.py
```

- **Needs Neo4j:** yes.
- **Reads:** the 4 shipped **oracle** runs for the two local models (§5).
- **Prints:** `GPT-OSS-20B ProKinO Ref-schema uncapped F1 = 0.xxx` (one line per local
  model × KG).

**Reading it into Table 4:** Table 4 has three F1 columns for the two **local** models:
- **Baseline** and **P2C** columns = the local-model rows already produced in Step A1
  (`GPT-OSS-20B|…` and `Qwen2.5-Coder-14B|…`, keys `…|Baseline` and `…|P2C`).
- **Ref. schema** (oracle) column = the numbers printed by this script.

So Table 4 is fully reproduced by A1 + A2 together; A2 only adds the oracle column.

### Step A3 — Table 3 (selection quality)

```bash
python additional_experiments/exp1_selection_analysis.py
```

- **Needs Neo4j:** **no** — it parses the Cypher text only.
- **Reads:** the same 8 base runs, plus each KG's `schema.json` and gold file.
- **Prints:** a table with columns `NodeRec`, `RelRec`, `Halluc%` for the two reported
  conditions (`with_instructions` = P2C, `without_relevant_nodes` = Baseline) per model.

**What the columns mean:** for each generated query it extracts the node labels and
relationship types actually written in the Cypher, compares them to the labels/types the
gold query requires (node recall, relationship recall), and flags **hallucination** when a
generated query uses any schema element absent from that KG's `schema.json`. `Halluc%` is
the **per-query** rate — the percentage of queries containing at least one hallucinated
element — matching the paper's hallucination definition.

### Step A4 — Figure 6 (benefit vs. capability)

```bash
python additional_experiments/exp7_scaling_figure.py
```

- **Needs Neo4j:** no.
- **Reads:** `results/uncapped_results.json` from Step A1 **if present** (it prints
  `[exp7] using uncapped scores from results/uncapped_results.json`); otherwise it falls
  back to the reported values baked into the script and prints
  `[exp7] results/uncapped_results.json not found - using reported fallback values`.
  To reproduce the figure from your own re-score, run Step A1 first.
- **Writes:** [`results/fig6_capability_vs_benefit_uncapped.png`](results/fig6_capability_vs_benefit_uncapped.png).

The figure plots, for each model × KG point, ΔF1 = F1(P2C) − F1(Baseline) on the y-axis
against baseline F1 on the x-axis.

### Optional diagnostics (referenced in the text, not a table)

```bash
python additional_experiments/limit_check.py    # quantifies the LIMIT 100 effect (needs Neo4j)
python additional_experiments/halluc_check.py   # per-query vs per-element hallucination (no DB)
```

---

## 4. Level B — regenerate the runs from scratch (re-run the models)

This re-creates the `ablation-*.json` files that Level A consumes. Use it only if you want
to reproduce the generation step itself. **Results will differ run to run** (§1.4).

### Step B1 — generate

```bash
python src/ablation/generate_cypher_ablation.py --model <model_key> --db <db_name>
```

- `--model` is one of:
  `deepseek-v4-pro`, `gpt-5.4`, `gpt-oss`, `qwen-coder` (the four reported models), plus
  `deepseek-chat` and `gpt-4o-mini` (available but not reported). Default: `deepseek-v4-pro`.
- `--db` is the Neo4j database name and **must be** `prokino-kg` or `ickg` (it overrides
  `NEO4J_DATABASE_NAME`; any other value leaves the KG unresolved and the script will stop).
- **Providers / credentials:**
  - `gpt-oss` and `qwen-coder` run **locally via Ollama** at `http://localhost:11434`
    (pull the models first: `ollama pull gpt-oss:20b`, `ollama pull qwen2.5-coder:14b`).
  - `deepseek-v4-pro` / `deepseek-chat` need `DEEPSEEK_API_KEY`.
  - `gpt-5.4` / `gpt-4o-mini` need `OPENAI_API_KEY`.
- **Reads:** `data/<kg>/test_queries_updated_june_30.json`, `data/<kg>/schema.json`,
  `data/<kg>/schema_comments.json`, `prompts/<kg>_instructions.txt`,
  `prompts/node_relevance_instructions.txt`.
- **Writes:** a new `results/<kg>/ablation-<model>-<timestamp>.json` with the four
  conditions per query.

Run it once per model × KG you want to regenerate (e.g. 8 runs to rebuild all of Table 2).
To also regenerate the oracle condition for Table 4, use
`additional_experiments/exp2_oracle_generate.py` (local models only).

### Step B2 — score your fresh runs

The re-score scripts reference specific shipped filenames by timestamp. To score your own
runs, point them at your new files:

- In [`reproduce/full_rescore.py`](reproduce/full_rescore.py), edit the **`RUNS`** dict
  (the eight `('<model>','<kg>'): 'results/<kg>/ablation-...json'` entries) to your new
  paths.
- In [`reproduce/oracle_rescore.py`](reproduce/oracle_rescore.py), edit the **`ORC`** dict
  the same way.

Then run Level A (§3) as usual.

---

## 5. Shipped run-file inventory (for verification)

Level A reads exactly these files. If any are missing, Level A cannot reproduce the
corresponding number.

**Base runs (Table 2, Table 3) — 8 files:**

| Model | ProKinO | ICKG |
|---|---|---|
| DeepSeek-V4 Pro | `results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json` | `results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json` |
| GPT-5.4 | `results/prokino/ablation-gpt-5.4-2026_08_01-20_01_36.json` | `results/ickg/ablation-gpt-5.4-2026_08_01-20_01_28.json` |
| GPT-OSS-20B | `results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json` | `results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json` |
| Qwen2.5-Coder-14B | `results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json` | `results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json` |

**Oracle runs (Table 4, reference-schema column) — 4 files (local models):**

| Model | ProKinO | ICKG |
|---|---|---|
| GPT-OSS-20B | `results/prokino/ablation-gpt-oss-20b-oracle-2026_08_03-07_19_34.json` | `results/ickg/ablation-gpt-oss-20b-oracle-2026_08_03-07_24_26.json` |
| Qwen2.5-Coder-14B | `results/prokino/ablation-qwen2.5-coder-14b-oracle-2026_08_03-07_26_22.json` | `results/ickg/ablation-qwen2.5-coder-14b-oracle-2026_08_03-07_27_54.json` |

(DeepSeek oracle runs are also shipped for completeness but are not part of the reported
Table 4, which covers the two local models.)

**Gold files (reference queries + stored results) — 2 files:**
`data/prokino/test_queries_updated_june_30-with_results.json`,
`data/ickg/test_queries_updated_june_30-with_results.json`.

`results/uncapped_results.json` and `results/fig6_capability_vs_benefit_uncapped.png` are
**generated** by Steps A1 and A4; the PNG is also shipped for convenience.

---

## 6. Troubleshooting

- **`Neo.ClientError…` / authentication failed** — check `NEO4J_URI`, `NEO4J_USERNAME`,
  `NEO4J_PASSWORD` in `.env` and that Neo4j is running.
- **Every score is 0 for one KG** — the wrong database is loaded, or relationship-type
  casing in the live DB does not match the queries. Re-check the database-build steps in
  [`SETUP.md`](SETUP.md) (ProKinO relationship types are UPPERCASE; ICKG are camelCase) and
  run `python src/sanity_check.py` against the suspect KG.
- **`FileNotFoundError` on a run file** — confirm the files in §5 exist; if you regenerated
  runs (Level B), update the `RUNS` / `ORC` dicts (§4, Step B2).
- **Figure 6 shows the reported values, not mine** — run Step A1 first so
  `results/uncapped_results.json` exists before Step A4.
- **Level B numbers differ from the paper** — expected; Level B is stochastic (§1.4). Use
  Level A to verify the reported values exactly.
