"""
Experiment 6 — Prompt-format control (rules out H5).

H5: maybe the small-model collapse on the full schema is an artifact of the PROMPT TEMPLATE differing
between the filtered (with_instructions) and full (without_relevant_nodes) conditions, not the node/rel SET.

Control: take the EXACT `with_instructions` (filtered) template wording, but populate it with the FULL
schema — all node labels in the "relevant nodes" slot, all relationships in the "relationships they are
involved in" slot, all node descriptions/properties. Only the SET differs from real P2C; the wording is
byte-identical to the filtered condition.

Prediction:
  full-in-filtered-template ~= without_relevant_nodes (both collapse)  -> collapse is the SET. H5 RULED OUT.
  full-in-filtered-template ~= with_instructions (works despite full set) -> the wording did the work. H5 holds.

Saved condition: `full_in_filtered_template`. Grafts the model's own `with_instructions` (real P2C) and
`without_relevant_nodes` (baseline) from its base ablation file for side-by-side scoring.

Local Ollama only (open models). Run from project root.
Usage: python additional_experiments/exp6_format_control.py --model <gpt-oss|qwen-coder> --db <prokino-kg|ickg>
       add --dry_run to print the constructed prompt for the first query WITHOUT calling the model.
"""
import re, os, json, sys, datetime, argparse
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

MODELS = {
    "gpt-oss": ("gpt-oss:20b", "gpt-oss-20b", {
        "prokino": "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
        "ickg":    "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json"}),
    "qwen-coder": ("qwen2.5-coder:14b", "qwen2.5-coder-14b", {
        "prokino": "results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json",
        "ickg":    "results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json"}),
}

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS.keys()))
ap.add_argument("--db", required=True, choices=["prokino-kg", "ickg"])
ap.add_argument("--dry_run", action="store_true", help="print the prompt for the first query, no model call")
a = ap.parse_args()
os.environ["NEO4J_DATABASE_NAME"] = a.db
KG = "ickg" if a.db == "ickg" else "prokino"
TAG, STEM, BASE = MODELS[a.model]

schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]
schema["nodes_properties"]  = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()
base = json.load(open(BASE[KG]))

# FULL schema, dropped into the FILTERED-template slots.
all_nodes = list(schema["labels"].keys())
all_rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in schema.get("relationships", [])]
nodes_info_str = ""
for n in all_nodes:
    nodes_info_str += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
    for p, pd in schema["nodes_properties"].get(n, {}).items():
        nodes_info_str += f"- {p}: {pd}\n"
    nodes_info_str += "\n"

def build_prompt(user_query):
    # BYTE-IDENTICAL to generate_with_instructions' final_prompt, with all_nodes/all_rels in the slots.
    relevant_nodes = all_nodes
    relevant_relationships = all_rels
    return (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"Generate a Cypher query to answer the User query: ```{user_query}```\n"
        f"Consider the following information:\n"
        f"Given the relevant nodes ({relevant_nodes}) and all the relationships they are involved in: ```{relevant_relationships}```\n"
        f"Information about the relevant nodes:\n{nodes_info_str}\n"
        f"\nIMPORTANT Instructions: {instructions}\n"
        f"The Cypher query should answer the user query which is: {user_query}\n"
        f"Return only Cypher code with no explanations. Complete this task: the cypher query is: ...")

def clean_cypher(text):
    if not isinstance(text, str): return ""
    text = text.replace("`", "")
    i = text.find("MATCH")
    if i != -1: text = text[i:]
    j = text.rfind(";")
    if j != -1: text = text[:j+1]
    return text.replace("\n", " ").strip()

if a.dry_run:
    print("=== DRY RUN — constructed prompt for first query (no model call) ===\n")
    print(build_prompt(base[0]["query"])[:2000])
    print("\n... [truncated] ...")
    sys.exit(0)

client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")

def getc(v):
    return v.get("cypher_query", "") if isinstance(v, dict) else (v or "")

out = []
print(f"[exp6-format-control] model={TAG}  KG={KG}  {len(base)} queries")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]
    try:
        r = client.chat.completions.create(model=TAG, messages=[{"role": "user", "content": build_prompt(uq)}])
        cy = clean_cypher(r.choices[0].message.content)
    except Exception as ex:
        cy = "Error: " + str(ex)
    ar = e.get("ablation_results", {})
    out.append({
        "title": t, "query": uq,
        "ablation_results": {
            "full_in_filtered_template": cy,
            "with_instructions": getc(ar.get("with_instructions", "")),
            "without_relevant_nodes": getc(ar.get("without_relevant_nodes", "")),
        }
    })
    print(f"  [{i+1}/{len(base)}] {t}  len(cypher)={len(cy)}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-{STEM}-exp6fmt-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
