"""
Experiment 4 — Decomposition vs reduction (H3 isolation).

Question: is P2C's benefit the two-STEP act (a separate selection/planning call), or just the smaller
resulting prompt (reduced context)? Hold the reduced context FIXED (oracle relationship set) and vary only
the structure:
  single_shot_oracle : ONE call, generate over the oracle-reduced set (identical to Exp 2 oracle).
  two_step_oracle    : TWO calls over the SAME oracle-reduced set — Call 1 plans the path (labels + rels +
                       direction), Call 2 generates from that plan. Same context, decomposed structure.

Both use the identical oracle context, so any gap is the decomposition ACT, not the reduction.
Prediction: two_step ~= single_shot -> benefit is context reduction (decomposition adds nothing);
            two_step  >  single_shot -> the separate planning step itself helps weak models.

Small models only (local Ollama). Grafts with_instructions / without_relevant_nodes from base for reference.
Run from project root. Usage: python additional_experiments/exp4_decomp_vs_reduction.py --model <gpt-oss|qwen-coder> --db <prokino-kg|ickg>
"""
import re, os, json, sys, datetime, argparse
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

def extract_labels(c):
    if not isinstance(c, str): return set()
    out = set()
    for x in re.findall(r'\(\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_|]*)', c):
        for p in x.split('|'):
            if p: out.add(p)
    return out

def extract_rels(c):
    if not isinstance(c, str): return set()
    out = set()
    for x in re.findall(r'\[\s*\w*\s*:\s*!?([A-Za-z_][A-Za-z0-9_|]*)', c):
        for p in x.split('|'):
            if p: out.add(p)
    return out

def clean_cypher(q):
    if not isinstance(q, str): return ""
    i = q.find("MATCH")
    if i != -1: q = q[i:]
    j = q.rfind(";")
    if j != -1: q = q[:j+1]
    return q.replace("`", "").replace("\n", " ").strip()

MODELS = {"gpt-oss": ("gpt-oss:20b", "gpt-oss-20b"), "qwen-coder": ("qwen2.5-coder:14b", "qwen2.5-coder-14b")}
BASE = {
    ("gpt-oss", "prokino"):    "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
    ("gpt-oss", "ickg"):       "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json",
    ("qwen-coder", "prokino"): "results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json",
    ("qwen-coder", "ickg"):    "results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json",
}

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS.keys()))
ap.add_argument("--db", required=True, choices=["prokino-kg", "ickg"])
a = ap.parse_args()
os.environ["NEO4J_DATABASE_NAME"] = a.db
KG = "ickg" if a.db == "ickg" else "prokino"
TAG, STEM = MODELS[a.model]
client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")

schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]; schema["nodes_properties"] = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()
gold = {q["title"]: q for q in json.load(open(f"data/{KG}/test_queries_updated_june_30-with_results.json"))}
base = json.load(open(BASE[(a.model, KG)]))
all_nodes = list(schema["labels"].keys())

def oracle_context(gold_cypher):
    req_labels = extract_labels(gold_cypher); req_rels = extract_rels(gold_cypher)
    oracle_rels = [r for r in schema.get("relationships", []) if r["name"] in req_rels]
    nodes = set(n for n in req_labels if n in schema["labels"])
    for r in oracle_rels: nodes.add(r["from"]); nodes.add(r["to"])
    nodes = [n for n in schema["labels"] if n in nodes] or list(req_labels) or all_nodes
    if not oracle_rels:
        oracle_rels = [r for r in schema.get("relationships", []) if r["from"] in nodes or r["to"] in nodes]
    rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in oracle_rels]
    info = ""
    for n in nodes:
        info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
        for p, pd in schema["nodes_properties"].get(n, {}).items():
            info += f"- {p}: {pd}\n"
        info += "\n"
    return nodes, rels, info

def call(prompt):
    try:
        r = client.chat.completions.create(model=TAG, messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content
    except Exception as e:
        return "Error: " + str(e)

def single_shot(uq, nodes, rels, info):
    p = (f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
         f"Generate a Cypher query to answer the User query: ```{uq}```\n"
         f"Consider the following information:\n"
         f"Given the relevant nodes ({nodes}) and all the relationships they are involved in: ```{rels}```\n"
         f"Information about the relevant nodes:\n{info}\n"
         f"\nIMPORTANT Instructions: {instructions}\n"
         f"The Cypher query should answer the user query which is: {uq}\n"
         f"Return only Cypher code with no explanations. Complete this task: the cypher query is: ...")
    return clean_cypher(call(p))

def two_step(uq, nodes, rels, info):
    plan_prompt = (
        f"You are an expert in graph databases. User query: ```{uq}```\n"
        f"Relevant node labels: {nodes}\n"
        f"Relevant relationships (with endpoints): ```{rels}```\n"
        f"STEP 1 (planning only — do NOT write Cypher): describe the exact graph path needed to answer the "
        f"query: which node labels, which relationship types, and in what direction they connect. "
        f"Answer in 1-3 short lines.")
    plan = call(plan_prompt)
    gen_prompt = (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"Generate a Cypher query to answer the User query: ```{uq}```\n"
        f"Consider the following information:\n"
        f"Given the relevant nodes ({nodes}) and all the relationships they are involved in: ```{rels}```\n"
        f"Information about the relevant nodes:\n{info}\n"
        f"Your plan for the graph path to use:\n{plan}\n"
        f"\nIMPORTANT Instructions: {instructions}\n"
        f"The Cypher query should answer the user query which is: {uq}\n"
        f"Return only Cypher code with no explanations. Complete this task: the cypher query is: ...")
    return clean_cypher(call(gen_prompt))

def getc(v): return v.get("cypher_query", "") if isinstance(v, dict) else (v or "")

out = []
print(f"[exp4] model={TAG} KG={KG} — single-shot vs two-step oracle, {len(base)} queries")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]; gold_cy = gold.get(t, {}).get("cypher", "")
    nodes, rels, info = oracle_context(gold_cy)
    ss = single_shot(uq, nodes, rels, info)
    ts_ = two_step(uq, nodes, rels, info)
    ar = e.get("ablation_results", {})
    out.append({"title": t, "query": uq, "ablation_results": {
        "single_shot_oracle": ss,
        "two_step_oracle": ts_,
        "with_instructions": getc(ar.get("with_instructions", "")),
        "without_relevant_nodes": getc(ar.get("without_relevant_nodes", "")),
    }})
    print(f"  [{i+1}/{len(base)}] {t}  ss={len(ss)} two={len(ts_)}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-{STEM}-exp4decomp-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
