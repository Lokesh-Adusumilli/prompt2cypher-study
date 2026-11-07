"""
Experiment 3 (FAIR + STRICT) — full run, both open models.

Apples-to-apples single-prompt decomposition vs P2C:
  - Step 1 asks for NODES ONLY (mirrors prompts/node_relevance_instructions.txt); the model does
    NOT enumerate relationships in Step 1. Relationships are committed in Step 2 (generation).
  - The ONLY structural difference vs P2C is that P2C narrows relationships with CODE between the
    two calls; here there is no code filter (the model faces the full schema in Step 2).
  - PLUS a STRONG anti-hallucination constraint: use only labels/relationships that appear
    verbatim in the schema; never invent, rename, pluralize, or abbreviate.

Condition saved: `cot_fair_strict`. For side-by-side comparison we graft the model's already-saved
`with_instructions` (true two-step P2C) and `without_relevant_nodes` (baseline) from its ablation file.

Both models are local (Ollama) — allowed without paid-API permission.
Usage (from project root):
  python additional_experiments/exp3_fair_full_run.py --model <gpt-oss|qwen-coder> --db <prokino-kg|ickg>
"""
import re, os, json, sys, datetime, argparse
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

# model key -> (ollama tag, output filename stem, {kg: baseline ablation file})
MODELS = {
    "gpt-oss": ("gpt-oss:20b", "gpt-oss-20b", {
        "prokino": "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
        "ickg":    "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json",
    }),
    "qwen-coder": ("qwen2.5-coder:14b", "qwen2.5-coder-14b", {
        "prokino": "results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json",
        "ickg":    "results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json",
    }),
}

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS.keys()))
ap.add_argument("--db", required=True, choices=["prokino-kg", "ickg"])
a = ap.parse_args()
os.environ["NEO4J_DATABASE_NAME"] = a.db
KG = "ickg" if a.db == "ickg" else "prokino"
TAG, STEM, BASE = MODELS[a.model]

client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")

schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]
schema["nodes_properties"]  = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()
base = json.load(open(BASE[KG]))

all_nodes = list(schema["labels"].keys())
all_rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in schema.get("relationships", [])]
rel_names = sorted(r["name"] for r in schema.get("relationships", []))
nodes_info = ""
for n in all_nodes:
    nodes_info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
    for p, pd in schema["nodes_properties"].get(n, {}).items():
        nodes_info += f"- {p}: {pd}\n"
    nodes_info += "\n"

# STRONG anti-hallucination constraint (the new addition requested)
STRICT = (
    "CRITICAL SCHEMA CONSTRAINT — READ CAREFULLY:\n"
    "You MUST use ONLY node labels and relationship types that appear VERBATIM in the schema above. "
    "Do NOT invent, guess, rename, abbreviate, pluralize, singularize, or change the case of any name. "
    "Every label written after a colon (e.g. (:Label)) must be copied exactly from the Nodes list. "
    "Every relationship written as [:TYPE] must be copied exactly from this allowed relationship-type list:\n"
    f"{rel_names}\n"
    "If a name you want to use is not in these lists, it does NOT exist — pick the closest name that IS "
    "in the lists, or omit it. Any label or relationship not in the schema will make the query invalid."
)

def extract_final_cypher(text):
    if not isinstance(text, str): return ""
    blocks = re.findall(r"```(?:cypher)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    cand = blocks[-1] if blocks else text
    i = cand.rfind("MATCH")
    if i != -1: cand = cand[i:]
    j = cand.rfind(";")
    if j != -1: cand = cand[:j+1]
    return cand.replace("`", "").replace("\n", " ").strip()

def gen(user_query):
    prompt = (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"User query: ```{user_query}```\n"
        f"Here is the COMPLETE schema of the knowledge graph.\n"
        f"Nodes: {all_nodes}\n"
        f"Relationships: ```{all_rels}```\n"
        f"Information about the nodes:\n{nodes_info}\n"
        f"IMPORTANT Cypher rules: {instructions}\n\n"
        f"{STRICT}\n\n"
        f"Solve this in TWO explicit steps within your answer:\n"
        f"Step 1 — Relevant nodes: from the Nodes list above, return ONLY the node labels relevant to "
        f"this query (comma-separated, nothing else). Do NOT list relationships in this step.\n"
        f"Step 2 — Generation: write the Cypher query to answer the user query, using the nodes you "
        f"selected and only relationships from the allowed list, following the Cypher rules and the "
        f"schema constraint above.\n"
        f"After your reasoning, output the FINAL query inside a fenced block:\n```cypher\n<query>\n```"
    )
    try:
        r = client.chat.completions.create(model=TAG, messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content
    except Exception as e:
        return "Error: " + str(e)

out = []
print(f"[exp3-fair-strict] model={TAG}  KG={KG}  {len(base)} queries")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]
    raw = gen(uq)
    cy = extract_final_cypher(raw)
    ar = e.get("ablation_results", {})
    def getc(k):
        v = ar.get(k, "")
        return v.get("cypher_query", "") if isinstance(v, dict) else v
    out.append({
        "title": t, "query": uq,
        "ablation_results": {
            "cot_fair_strict": cy,
            "with_instructions": getc("with_instructions"),
            "without_relevant_nodes": getc("without_relevant_nodes"),
        }
    })
    print(f"  [{i+1}/{len(base)}] {t}  len(cypher)={len(cy)}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-{STEM}-exp3fair-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
