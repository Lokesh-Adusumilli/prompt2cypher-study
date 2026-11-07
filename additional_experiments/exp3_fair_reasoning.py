"""
Experiment 3 (FAIR) — apples-to-apples single-prompt decomposition.

Fixes the earlier exp3 flaw: P2C's Step 1 selects ONLY nodes (relationships are derived by CODE),
so a fair single-prompt must also ask for nodes in Step 1 and let the model commit relationships
in Step 2 (generation). The ONLY variable vs P2C is whether relationship narrowing is done by code.

Step 1 here mirrors prompts/node_relevance_instructions.txt (nodes only).
Step 2 asks the model to generate, choosing relationships from the FULL schema during generation
(no code filtering — that absence is exactly the variable under test).

Model: gpt-oss:20b (local, free). Run from project root.
"""
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
        f"Step 1 — Relevant nodes: from the node list above, return ONLY the node labels that are "
        f"relevant to this query (a comma-separated list, nothing else). Do NOT list relationships here.\n"
        f"Step 2 — Generation: now write the Cypher query to answer the user query, using the nodes "
        f"you selected and the appropriate relationships from the schema, following the Cypher rules above.\n"
        f"After your reasoning, output the FINAL query inside a fenced block:\n```cypher\n<query>\n```"
    )

for t in ["A1", "C9"]:
    q = gold[t]
    print("=" * 90)
    print(f"QUERY {t}: {q['query']}")
    print(f"GOLD cypher: {q['cypher']}")
    print("-" * 90)
    r = client.chat.completions.create(model="gpt-oss:20b", messages=[{"role": "user", "content": prompt_for(q['query'])}])
    text = r.choices[0].message.content
    print("RAW MODEL OUTPUT:\n")
    print(text)
    used = set(re.findall(r'\[:([A-Za-z_]+)\]', text))  # relationship tokens actually used in the query
    print("\n[relationship tokens used but NOT in schema]:", sorted(u for u in used if u not in real_rels))
    print("=" * 90 + "\n")
