"""
Experiment 2 — Oracle node filtering.
Feeds Step-2 generation the PERFECT node set (from gold Cypher) instead of LLM Step-1 selection.
Reuses already-saved `with_instructions` and `without_relevant_nodes` Cypher (no regeneration);
only the new `oracle` condition calls the model.

Allowed models only (DeepSeek + local Ollama). No GPT-class paid models.
Usage (run from project root): python additional_experiments/exp2_oracle_generate.py --model <deepseek-v4-pro|gpt-oss|qwen-coder> --db <prokino-kg|ickg>
"""
import re, os, json, sys, datetime, argparse
from openai import OpenAI
from dotenv import load_dotenv
# [moved to additional_experiments/] folder is one level below project root -> dirname x2  [was x3 under src/ablation]
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

def extract_labels(cypher):
    if not isinstance(cypher, str): return set()
    node = re.findall(r'\(\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_|]*)', cypher)
    out = set()
    for x in node:
        for p in x.split('|'):
            if p: out.add(p)
    return out

def extract_rels(cypher):
    if not isinstance(cypher, str): return set()
    rel = re.findall(r'\[\s*\w*\s*:\s*!?([A-Za-z_][A-Za-z0-9_|]*)', cypher)
    out = set()
    for x in rel:
        for p in x.split('|'):
            if p: out.add(p)
    return out

def oracle_node_set(gold_cypher, schema):
    """Complete oracle: labels in gold Cypher + schema endpoints of every relationship it uses
    (captures unlabeled traversed nodes, e.g. (m) after HASMUTATION -> Mutation/Missense)."""
    nodes = extract_labels(gold_cypher)
    req_rels = extract_rels(gold_cypher)
    for r in schema.get("relationships", []):
        if r["name"] in req_rels:
            nodes.add(r["from"]); nodes.add(r["to"])
    return nodes

def clean_cypher(query):
    if not isinstance(query, str): return ""
    i = query.find("MATCH")
    if i != -1: query = query[i:]
    j = query.rfind(";")
    if j != -1: query = query[:j+1]
    return query.replace("`","").replace("\n"," ").strip()

MODELS = {
    "deepseek-v4-pro": {"name":"deepseek-v4-pro","filename":"deepseek-v4-pro","provider":"deepseek"},
    "gpt-oss":         {"name":"gpt-oss:20b","filename":"gpt-oss-20b","provider":"ollama"},
    "qwen-coder":      {"name":"qwen2.5-coder:14b","filename":"qwen2.5-coder-14b","provider":"ollama"},
}
# base files with already-generated complete / no-filter cypher (reused, no regeneration)
BASE = {
    ("deepseek-v4-pro","prokino"): "results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json",
    ("deepseek-v4-pro","ickg"):    "results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json",
    ("gpt-oss","prokino"):         "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
    ("gpt-oss","ickg"):            "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json",
    ("qwen-coder","prokino"):      "results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json",
    ("qwen-coder","ickg"):         "results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json",
}

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS.keys()))
ap.add_argument("--db", required=True)
a = ap.parse_args()
os.environ["NEO4J_DATABASE_NAME"] = a.db
KG = "ickg" if a.db == "ickg" else "prokino"
MI = MODELS[a.model]

if MI["provider"] == "deepseek":
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")
elif MI["provider"] == "ollama":
    client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")

schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]
schema["nodes_properties"]  = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()

gold = {q["title"]: q for q in json.load(open(f"data/{KG}/test_queries_updated_june_30-with_results.json"))}
base = json.load(open(BASE[(a.model, KG)]))
all_nodes = list(schema["labels"].keys())

def gen_oracle(user_query, gold_cypher):
    # Faithful oracle centered on the gold query's RELATIONSHIP TYPES (Exp-1 showed rel
    # selection is the bottleneck). Give exactly those relationships + their endpoint nodes.
    req_labels = extract_labels(gold_cypher)
    req_rels   = extract_rels(gold_cypher)
    oracle_rels = [r for r in schema.get("relationships", []) if r["name"] in req_rels]
    nodes = set(n for n in req_labels if n in schema["labels"])
    for r in oracle_rels:
        nodes.add(r["from"]); nodes.add(r["to"])
    nodes = [n for n in schema["labels"] if n in nodes]
    if not nodes:               # single-node / label-less query: fall back to gold labels or all
        nodes = list(req_labels) or all_nodes
    if not oracle_rels:         # no relationship in gold (single-node lookup): rels touching nodes
        oracle_rels = [r for r in schema.get("relationships", []) if r["from"] in nodes or r["to"] in nodes]
    rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in oracle_rels]
    info = ""
    for n in nodes:
        info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
        for p, pd in schema["nodes_properties"].get(n, {}).items():
            info += f"- {p}: {pd}\n"
        info += "\n"
    prompt = (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"Generate a Cypher query to answer the User query: ```{user_query}```\n"
        f"Consider the following information:\n"
        f"Given the relevant nodes ({nodes}) and all the relationships they are involved in: ```{rels}```\n"
        f"Information about the relevant nodes:\n{info}\n"
        f"\nIMPORTANT Instructions: {instructions}\n"
        f"The Cypher query should answer the user query which is: {user_query}\n"
        f"Return only Cypher code with no explanations. Complete this task: the cypher query is: ...")
    try:
        resp = client.chat.completions.create(model=MI["name"], messages=[{"role":"user","content":prompt}])
        return resp.choices[0].message.content.strip().replace("\n"," ")
    except Exception as e:
        return "Error: " + str(e)

out = []
print(f"[exp2] model={MI['filename']} KG={KG} — generating oracle for {len(base)} queries")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]
    gold_cy = gold.get(t, {}).get("cypher", "")
    oracle_cy = clean_cypher(gen_oracle(uq, gold_cy))
    ar = e.get("ablation_results", {})
    def getc(k):
        v = ar.get(k, "")
        return v.get("cypher_query","") if isinstance(v, dict) else v
    out.append({
        "title": t, "query": uq,
        "ablation_results": {
            "oracle": oracle_cy,
            "with_instructions": getc("with_instructions"),
            "without_relevant_nodes": getc("without_relevant_nodes"),
        }
    })
    print(f"  [{i+1}/{len(base)}] {t}  oracle_rels={sorted(extract_rels(gold_cy)) or 'NONE'}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-{MI['filename']}-oracle-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
