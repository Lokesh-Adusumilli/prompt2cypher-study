# Setup and Data Preparation

This guide takes you from a fresh checkout to a state where you can run the study:
a Python environment, the two Neo4j knowledge graphs built and running, and the derived
data artifacts in place. When it is done, proceed to [`REPRODUCTION.md`](REPRODUCTION.md).

It has three parts:

1. **Environment** — Python, dependencies, `.env`, Neo4j.
2. **Build the databases** — construct `prokino-kg` and `ickg` from their source data.
3. **Derived artifacts** — what is already shipped vs. what you can regenerate.

---

## 1. Environment

```bash
conda create -n prompt2cypher python=3.10
conda activate prompt2cypher
pip install -r requirements.txt
```

The repository ships a `.env` with placeholder values. Open it and replace each
placeholder with your real value.

`.env` keys:

| Key | Used for |
|---|---|
| `NEO4J_URI` | Bolt URI of your Neo4j server (e.g. `bolt://127.0.0.1:7687`). |
| `NEO4J_USERNAME`, `NEO4J_PASSWORD` | Neo4j credentials. |
| `NEO4J_DATABASE_NAME` | The *active* database for scripts that read it from the environment (`ickg` or `prokino-kg`). |
| `DEEPSEEK_API_KEY` | Only to regenerate DeepSeek runs (Level B in `REPRODUCTION.md`). |
| `OPENAI_API_KEY` | Only to regenerate GPT runs (Level B). |
| `GOOGLE_API_KEY` | Optional; not required for the reported results. |

Install Neo4j (Desktop or server, version **5.14**) and raise the heap size to suit your
machine, e.g. in the Neo4j config:

```
dbms.memory.heap.initial_size=4G
dbms.memory.heap.max_size=16G
```

Verify connectivity once the server is up:

```bash
python src/test_neo4j_connection.py
```

---

## 2. Build the databases

The two knowledge graphs are **not** shipped in this repository (they are large and derive
from external sources). You build each one from its source data, then run a short
normalization pipeline so the live database matches the shipped schema and gold queries.

The heavy, source-specific steps (downloading the data and the initial Neo4j import) are
documented in the two construction guides:

- ProKinO — [`data/prokino/README.md`](data/prokino/README.md)
- ICKG — [`data/ickg/README.md`](data/ickg/README.md)

The script pipelines below wrap and extend those guides. Run everything from the
repository root.

### 2.1 ProKinO → database `prokino-kg`

1. **Import the OWL ontology.** Follow the neosemantics setup in the ProKinO guide
   (`n10s.graphconfig.init`, plugin install), then run the import:
   ```bash
   python src/prokino_import.py
   ```
   Edit the constants at the top first (`OWL_PATH` to your downloaded
   `Prokino_v62_2021-09-15.owl`, and the Neo4j connection values). Import of ~58.6M triples
   takes 1–3 hours.
2. **Post-process.** Set `isDarkKinase = false` where missing and strip redundant
   `Resource` labels:
   ```bash
   python src/prokino_postprocess.py
   ```
3. **Normalize relationship casing.** ProKinO relationship types must be **UPPERCASE** to
   match the schema and test queries:
   ```bash
   # ensure NEO4J_DATABASE_NAME=prokino-kg in .env
   python src/rename_rel_types.py
   ```
4. **Generate the gold results** (reference query outputs) for the 30 test queries:
   ```bash
   NEO4J_DATABASE_NAME=prokino-kg python src/regenerate_results.py
   ```
   This writes `data/prokino/test_queries_updated_june_30-with_results.json` — **already
   shipped**, so this step is only needed if you rebuild the database and want to
   regenerate it yourself.

### 2.2 ICKG → database `ickg`

1. **Preprocess the raw CSVs** (id→name mapping, cleaning):
   ```bash
   python src/ickg_preprocess_step1.py
   python src/ickg_preprocess_step2.py   # merges UniProt / Excel / GO / Reactome
   ```
   Edit the input/output directory constants at the top of these scripts to point at your
   downloaded ICKG data.
2. **Transform to bulk-import format:**
   ```bash
   python src/ickg_transform.py          # -> nodes_import.csv, relationships_import.csv
   python src/validate_data.py           # checks for stray newlines in the CSVs
   ```
3. **Bulk import** with `neo4j-admin` and create the `ickg` database — see the ICKG guide
   for the exact `neo4j-admin database import full …` invocation and the one-database
   workaround.
   > ICKG relationship types are **camelCase** (`hasPathway`, `assoWithDisease`, …). Do
   > **not** run `rename_rel_types.py` against `ickg`. If you ever uppercase them by
   > accident, [`src/ickg_reverse_rename.py`](src/ickg_reverse_rename.py) restores the
   > camelCase names.
4. **Generate the gold results:**
   ```bash
   NEO4J_DATABASE_NAME=ickg python src/regenerate_results.py
   ```
   Writes `data/ickg/test_queries_updated_june_30-with_results.json` — **already shipped**.

### 2.3 Verify a build

```bash
# with NEO4J_DATABASE_NAME set to the KG you want to check
python src/sanity_check.py
```

This runs the gold queries and reports mismatches, which usually point to a missing
post-processing step or wrong relationship-type casing.

---

## 3. Derived artifacts — shipped vs. regenerable

For convenience, the derived data artifacts are **already in the repository**, so you do
**not** need to rebuild the databases merely to inspect the study inputs:

| Artifact | Location | Regenerated by |
|---|---|---|
| Graph schema | `data/<kg>/schema.json` | `src/helpers/extract_schema.py` (reads the live DB; edit its connection constants) |
| Schema comments | `data/<kg>/schema_comments.json` | hand-curated |
| Test queries | `data/<kg>/test_queries_updated_june_30.json` | hand-curated (the 30 queries + gold Cypher) |
| Gold results | `data/<kg>/test_queries_updated_june_30-with_results.json` | `src/regenerate_results.py` (needs the live DB) |

You only need a built database to (a) **execute** queries while reproducing Table 2 / Table 4,
or (b) **regenerate** any of the above from scratch.

---

## 4. A note on configuration in the build scripts

The reproduction/scoring scripts read Neo4j credentials from `.env`. A few of the
**one-time database-build** scripts instead carry configuration as constants at the top of
the file — edit these before running:

| Script | Edit before running |
|---|---|
| `src/prokino_import.py` | `OWL_PATH`, Neo4j connection constants |
| `src/prokino_postprocess.py` | Neo4j connection constants |
| `src/ickg_preprocess_step1.py` | `data_dir` (raw ICKG CSV directory) |
| `src/ickg_preprocess_step2.py` | UniProt / Excel / GO / Reactome input paths |
| `src/ickg_transform.py` | `RAW_DIR`, `STAGING_DIR` |
| `src/ickg_reverse_rename.py` | Neo4j connection constants |
| `src/helpers/extract_schema.py` | dotenv path and target database name |

These are run once to build the databases and are independent of the reproduction flow in
[`REPRODUCTION.md`](REPRODUCTION.md).

---

Once both databases are built and verified, continue to [`REPRODUCTION.md`](REPRODUCTION.md).
