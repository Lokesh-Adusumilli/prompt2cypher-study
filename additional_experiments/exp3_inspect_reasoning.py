"""Inspect GPT-OSS raw reasoning for the single-prompt decomposition (a few ProKinO queries)."""
import json, os, sys, re
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

KG = "prokino"
client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]; schema["nodes_properties"] = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()
gold = {q["title"]: q for q in json.load(open(f"data/{KG}/test_queries_updated_june_30-with_results.json"))}
real_rels = set(r["name"] for r in schema["relationships"])

all_nodes = list(schema["labels"].keys())
all_rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for r in schema["relationships"]]
nodes_info = ""
for n in all_nodes:
    nodes_info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
    for p, pd in schema["nodes_properties"].get(n, {}).items():
        nodes_info += f"- {p}: {pd}\n"
    nodes_info += "\n"

def prompt_for(uq):
    return (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"User query: ```{uq}```\n"
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

for t in ["A1", "C9"]:
    q = gold[t]
    print("="*90)
    print(f"QUERY {t}: {q['query']}")
    print(f"GOLD cypher: {q['cypher']}")
    print("-"*90)
    r = client.chat.completions.create(model="gpt-oss:20b", messages=[{"role":"user","content":prompt_for(q['query'])}])
    text = r.choices[0].message.content
    print("RAW MODEL OUTPUT:\n")
    print(text)
    used = set(re.findall(r'\b([A-Z][A-Z_]{3,})\b', text))  # uppercase-ish tokens (ProKinO rel style)
    halluc = {u for u in used if u not in real_rels and any(c.islower() for c in q['cypher']) is False}
    print("\n[relationship-like tokens NOT in schema]:", sorted(u for u in used if u.isupper() and u not in real_rels and len(u)>4))
    print("="*90 + "\n")
