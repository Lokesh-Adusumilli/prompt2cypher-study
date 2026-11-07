"""
Experiment 3 — Single-prompt two-fold decomposition (GPT-OSS, local).

Question: does the small-model edge come from the DECOMPOSITION (planning) or from the
two-CALL architecture where code filters relationships between calls?

Condition `cot_single_prompt`: give the model the SAME full schema as the baseline
(all nodes + all relationships + descriptions + instructions), but in ONE call ask it to
(Step 1) identify the relevant nodes/relationships itself, then (Step 2) generate Cypher.
No code-based filtering between steps — the model must narrow the schema in its own reasoning.

Compare vs the saved GPT-OSS runs:
  - with_instructions      = true two-step P2C (Step 1 call + code filter + Step 2 call)
  - without_relevant_nodes = baseline (full schema, single call, no decomposition prompt)

Interpretation:
  cot ~ with_instructions  -> edge is the DECOMPOSITION (prompt); two calls not needed.
  cot ~ without_relevant_nodes -> edge is the CODE-based two-step architecture, not prompting.

GPT-OSS is local (Ollama) — allowed without paid-API permission.
Usage: python dump/exp3_single_prompt_decomposition.py --db <prokino-kg|ickg>
"""
import re, os, json, sys, datetime, argparse
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

BASE = {
    "prokino": "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
    "ickg":    "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json",
}

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
a = ap.parse_args()
os.environ["NEO4J_DATABASE_NAME"] = a.db
KG = "ickg" if a.db == "ickg" else "prokino"

client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
MODEL = "gpt-oss:20b"

schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]
schema["nodes_properties"]  = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()
gold = {q["title"]: q for q in json.load(open(f"data/{KG}/test_queries_updated_june_30-with_results.json"))}
base = json.load(open(BASE[KG]))

# Build the FULL-schema context (identical to the baseline / without_relevant_nodes condition)
all_nodes = list(schema["labels"].keys())
all_rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in schema.get("relationships", [])]
nodes_info = ""
for n in all_nodes:
    nodes_info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
    for p, pd in schema["nodes_properties"].get(n, {}).items():
        nodes_info += f"- {p}: {pd}\n"
    nodes_info += "\n"

def extract_final_cypher(text):
    if not isinstance(text, str): return ""
    # prefer the last fenced code block
    blocks = re.findall(r"```(?:cypher)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    cand = blocks[-1] if blocks else text
    # from last MATCH to end / last ;
    i = cand.rfind("MATCH")
    if i != -1: cand = cand[i:]
    j = cand.rfind(";")
    if j != -1: cand = cand[:j+1]
    return cand.replace("`", "").replace("\n", " ").strip()

def gen_cot(user_query):
    prompt = (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"User query: ```{user_query}```\n"
        f"Here is the COMPLETE schema of the knowledge graph.\n"
        f"Nodes: {all_nodes}\n"
        f"Relationships: ```{all_rels}```\n"
        f"Information about the nodes:\n{nodes_info}\n"
        f"IMPORTANT Cypher rules: {instructions}\n\n"
        f"Solve this in TWO explicit steps within your answer:\n"
        f"Step 1 — Relevance: from the complete schema above, list ONLY the node labels and the "
        f"relationship types that are relevant to this query. Ignore everything else.\n"
        f"Step 2 — Generation: using ONLY the relevant nodes and relationships you selected in Step 1, "
        f"write the Cypher query, following the Cypher rules above.\n"
        f"After your reasoning, output the FINAL query inside a fenced block:\n```cypher\n<query>\n```"
    )
    try:
        r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content
    except Exception as e:
        return "Error: " + str(e)

out = []
print(f"[exp3] GPT-OSS single-prompt decomposition — KG={KG}, {len(base)} queries")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]
    raw = gen_cot(uq)
    cot_cy = extract_final_cypher(raw)
    ar = e.get("ablation_results", {})
    def getc(k):
        v = ar.get(k, "")
        return v.get("cypher_query", "") if isinstance(v, dict) else v
    out.append({
        "title": t, "query": uq,
        "ablation_results": {
            "cot_single_prompt": cot_cy,
            "with_instructions": getc("with_instructions"),
            "without_relevant_nodes": getc("without_relevant_nodes"),
        }
    })
    print(f"  [{i+1}/{len(base)}] {t}  len(cypher)={len(cot_cy)}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-gpt-oss-20b-exp3cot-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
