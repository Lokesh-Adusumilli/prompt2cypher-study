"""
Experiment 8 — Lost-in-the-middle probe.

Question: is the small-model collapse a POSITION / long-context attention effect, or a selection-burden
effect? Hold the content FIXED (full schema, single call, baseline wording) and vary only the POSITION of
the gold-required relationships within the full relationship list:
  pos_start  : required relationships placed FIRST, then all other (distractor) relationships.
  pos_middle : required relationships in the MIDDLE of the list.
  pos_end    : required relationships placed LAST.

If F1 varies strongly by position -> a lost-in-the-middle attention effect (supports H1-attention).
If F1 is flat across positions -> not a position artifact; the collapse is the selection burden itself.

Small models only (local Ollama). Grafts with_instructions / without_relevant_nodes for reference.
Run from project root. Usage: python additional_experiments/exp8_lost_in_middle.py --model <gpt-oss|qwen-coder> --db <prokino-kg|ickg>
"""
import re, os, json, sys, datetime, argparse
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

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
ALL_RELS = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in schema.get("relationships", [])]
nodes_info = ""
for n in all_nodes:
    nodes_info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
    for p, pd in schema["nodes_properties"].get(n, {}).items():
        nodes_info += f"- {p}: {pd}\n"
    nodes_info += "\n"

def ordered_rels(req_rel_names, where):
    """Return the FULL relationship list with required rels moved to start/middle/end (content identical)."""
    req = [r for r in ALL_RELS if r["name"] in req_rel_names]
    other = [r for r in ALL_RELS if r["name"] not in req_rel_names]
    if not req:  # single-node query with no relationship: nothing to move; return canonical order
        return list(ALL_RELS)
    if where == "start":  return req + other
    if where == "end":    return other + req
    mid = len(other) // 2  # middle
    return other[:mid] + req + other[mid:]

def build_prompt(uq, rels):
    return (f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
            f"Generate a Cypher query to answer the User query: ```{uq}```\n"
            f"Consider the following information about the knowledge graph:\n"
            f"Here are all the nodes and relationships in the knowledge graph.\n"
            f"Nodes: {all_nodes}\n"
            f"Relationships: ```{rels}```\n"
            f"Information about the nodes:\n{nodes_info}\n"
            f"\nIMPORTANT Instructions: {instructions}\n"
            f"The Cypher query should answer the user query which is: {uq}\n"
            f"Return only Cypher code with no explanations. Complete this task: the cypher query is: ...")

def gen(uq, rels):
    try:
        r = client.chat.completions.create(model=TAG, messages=[{"role": "user", "content": build_prompt(uq, rels)}])
        return clean_cypher(r.choices[0].message.content)
    except Exception as e:
        return "Error: " + str(e)

def getc(v): return v.get("cypher_query", "") if isinstance(v, dict) else (v or "")

out = []
print(f"[exp8] model={TAG} KG={KG} — lost-in-the-middle position sweep, {len(base)} queries")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]
    req = extract_rels(gold.get(t, {}).get("cypher", ""))
    conds = {}
    for where, key in [("start", "pos_start"), ("middle", "pos_middle"), ("end", "pos_end")]:
        conds[key] = gen(uq, ordered_rels(req, where))
    ar = e.get("ablation_results", {})
    conds["with_instructions"] = getc(ar.get("with_instructions", ""))
    conds["without_relevant_nodes"] = getc(ar.get("without_relevant_nodes", ""))
    out.append({"title": t, "query": uq, "ablation_results": conds})
    print(f"  [{i+1}/{len(base)}] {t}  req_rels={sorted(req) or 'NONE'}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-{STEM}-exp8lim-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
