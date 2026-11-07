# Additional experiments

Diagnostic and exploratory analyses that support the paper. Each reads the generated
Cypher in `results/<kg>/ablation-*.json` (the base ablation runs) and/or the gold queries
in `data/<kg>/test_queries_updated_june_30-with_results.json`. Run from the repository root.

## In the paper

| Script | Produces | Paper element |
|---|---|---|
| `exp1_selection_analysis.py` | node/relationship recall + hallucination, parsed from the generated Cypher | **Table 3** |
| `exp2_oracle_generate.py` | the reference-schema (oracle) generations for the local models | **Table 4** (scored by `reproduce/oracle_rescore.py`) |
| `exp7_scaling_figure.py` | ΔF1 (P2C − baseline) vs. baseline F1 | **Figure 6** |

The main results (**Table 2**) and the reference-schema F1 (**Table 4**) are scored
uncapped by the scripts in [`../reproduce/`](../reproduce) — see the top-level README.

## Diagnostics (referenced in the text, no standalone table)

| Script | Purpose |
|---|---|
| `limit_check.py` | quantifies how the `LIMIT 100` cap affects scoring (Evaluation Metrics) |
| `halluc_check.py` | per-query vs. per-element hallucination comparison |

## Exploratory — not in the paper

`exp3_*` (single-prompt decomposition, fair/strict, distractor sweep), `exp4_decomp_vs_reduction.py`,
`exp5_error_taxonomy.py`, `exp6_format_control.py`, `exp8_lost_in_middle.py`, `generate_report.py`.

These were run during development to probe the mechanism (relationship-selection burden,
decomposition vs. code-based filtering, size vs. confusability). They are retained for
transparency but their outputs are not reported; some hardcode paths to intermediate runs
that are not shipped.
