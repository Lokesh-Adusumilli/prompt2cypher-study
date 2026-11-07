"""
Experiment 5 — Error taxonomy of failures.

Categorizes each generated Cypher deterministically (no LLM judging, no new generation).
For every model x KG x condition it classifies the query into one PRIMARY failure mode and also
reports an overlay hallucination rate. Reuses the saved base ablation files; re-executes each query
on Neo4j only to separate genuine syntax errors from valid-but-empty results.

Conditions compared: with_instructions (P2C / filtered) vs without_relevant_nodes (baseline / full schema).
Contrast axes the proposal asks for: filtered vs full, small vs large.

Token classification (per label / per relationship used in the query):
  exact_ok      — appears verbatim in the schema
  case_mismatch — same name up to case, but not verbatim (Neo4j is case-sensitive -> would miss)
  invented      — no case-insensitive match in the schema (pure hallucination)

Primary category precedence:
  1 syntax_error    — Neo4j raised a syntax/semantic error (malformed Cypher)
  2 invented_schema — references >=1 invented label or relationship
  3 case_mismatch   — references >=1 case-mismatched name (no invented), otherwise schema-valid
  4 empty_valid     — schema-exact, executes, returns 0 rows (logic/value error)
  5 wrong_answer    — returns rows but F1 == 0 vs gold
  6 correct_partial — F1 > 0 vs gold

Run from project root (Neo4j must be up). Local only, no API.
Usage: python additional_experiments/exp5_error_taxonomy.py
"""
import re, os, json, sys
from collections import defaultdict, OrderedDict
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from neo4j.graph import Node
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

MODELS = OrderedDict([
    ("GPT-OSS-20B",       ("small", {"prokino": "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
                                     "ickg":    "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json"})),
    ("Qwen2.5-Coder-14B", ("small", {"prokino": "results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json",
                                     "ickg":    "results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json"})),
    ("DeepSeek-V4 Pro",   ("frontier", {"prokino": "results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json",
                                        "ickg":    "results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json"})),
    ("GPT-5.4",           ("frontier", {"prokino": "results/prokino/ablation-gpt-5.4-2026_08_01-20_01_36.json",
                                        "ickg":    "results/ickg/ablation-gpt-5.4-2026_08_01-20_01_28.json"})),
])
DB = {"prokino": "prokino-kg", "ickg": "ickg"}
CONDITIONS = ["with_instructions", "without_relevant_nodes"]
CATS = ["syntax_error", "invented_schema", "case_mismatch", "empty_valid", "wrong_answer", "correct_partial"]

driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def flatten(results):
    flat = set()
    for row in results:
        vals = row if isinstance(row, list) else [row]
        for v in vals:
            if v is not None:
                flat.add(str(v).strip())
    return flat

def clean_value(v):
    if isinstance(v, Node): return dict(v.items())
    if isinstance(v, str):  return v.replace(' ', ' ').strip()
    return v

def run_query(db, q):
    """Return (status, rows). status in {'ok','error'}."""
    if not q or "MATCH" not in q.upper():
        return "error", []
    try:
        with driver.session(database=db) as s:
            rows = [[clean_value(v) for v in rec.values()] for rec in s.run(q)]
            return "ok", rows
    except Neo4jError:
        return "error", []
    except Exception:
        return "error", []

def extract_tokens(cypher):
    rels = set(re.findall(r'\[\s*\w*\s*:\s*([A-Za-z_]\w*)', cypher))
    no_rel = re.sub(r'\[[^\]]*\]', '', cypher)
    labels = set(re.findall(r':\s*([A-Za-z_]\w*)', no_rel))
    return labels, rels

def classify_tokens(used, real):
    real_lc = {x.lower(): x for x in real}
    invented, case_mm = set(), set()
    for t in used:
        if t in real: continue
        if t.lower() in real_lc: case_mm.add(t)
        else: invented.add(t)
    return invented, case_mm

def getc(v):
    return v.get("cypher_query", "") if isinstance(v, dict) else (v or "")

# results[model][kg][cond] = {cat: count}, plus halluc overlay
summary = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
halluc = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"label_inv": 0, "rel_inv": 0, "any_inv": 0})))

for model, (tier, files) in MODELS.items():
    for kg, path in files.items():
        schema, sc = load_schema(f"data/{kg}/schema.json", f"data/{kg}/schema_comments.json")
        real_labels = set(schema["labels"].keys())
        real_rels = set(r["name"] for r in schema.get("relationships", []))
        gold = {q["title"]: flatten(q.get("cypher_result", []))
                for q in json.load(open(f"data/{kg}/test_queries_updated_june_30-with_results.json"))}
        data = json.load(open(path))
        for e in data:
            t = e["title"]; ar = e.get("ablation_results", {})
            for cond in CONDITIONS:
                cy = getc(ar.get(cond, ""))
                labels, rels = extract_tokens(cy)
                lab_inv, lab_cm = classify_tokens(labels, real_labels)
                rel_inv, rel_cm = classify_tokens(rels, real_rels)
                if lab_inv: halluc[model][kg][cond]["label_inv"] += 1
                if rel_inv: halluc[model][kg][cond]["rel_inv"] += 1
                if lab_inv or rel_inv: halluc[model][kg][cond]["any_inv"] += 1

                status, rows = run_query(DB[kg], cy)
                f1_hit = len(flatten(rows) & gold.get(t, set())) > 0

                if status == "error":
                    cat = "syntax_error"
                elif lab_inv or rel_inv:
                    cat = "invented_schema"
                elif lab_cm or rel_cm:
                    cat = "case_mismatch"
                elif not rows:
                    cat = "empty_valid"
                elif not f1_hit:
                    cat = "wrong_answer"
                else:
                    cat = "correct_partial"
                summary[model][kg][cond][cat] += 1

driver.close()

# ---- report ----
def bar(counts, n):
    return "  ".join(f"{c}={counts.get(c,0)}" for c in CATS)

print("\n================ EXP 5 — ERROR TAXONOMY ================\n")
for model, (tier, files) in MODELS.items():
    print(f"### {model}  ({tier})")
    for kg in ["prokino", "ickg"]:
        for cond in CONDITIONS:
            cnt = summary[model][kg][cond]
            n = sum(cnt.values())
            h = halluc[model][kg][cond]
            tag = "P2C/filtered" if cond == "with_instructions" else "baseline/full"
            print(f"  {kg:8s} {tag:14s} | " + bar(cnt, n) +
                  f"   [invented: lbl={h['label_inv']} rel={h['rel_inv']} any={h['any_inv']}/{n}]")
    print()

# aggregate small vs frontier, filtered vs full
print("================ AGGREGATES (share of 30 queries, per KG avg) ================\n")
def agg(tier_filter, cond):
    tot = defaultdict(int); n = 0; inv = 0
    for model, (tier, files) in MODELS.items():
        if tier != tier_filter: continue
        for kg in ["prokino", "ickg"]:
            cnt = summary[model][kg][cond]
            for c in CATS: tot[c] += cnt.get(c, 0)
            n += sum(cnt.values())
            inv += halluc[model][kg][cond]["any_inv"]
    return tot, n, inv

for tier in ["small", "frontier"]:
    for cond in CONDITIONS:
        tot, n, inv = agg(tier, cond)
        tag = "P2C/filtered" if cond == "with_instructions" else "baseline/full"
        pcts = "  ".join(f"{c}={100*tot[c]/n:.0f}%" for c in CATS)
        print(f"{tier:8s} {tag:14s} (N={n}) | {pcts}   [invented={100*inv/n:.0f}%]")
    print()
