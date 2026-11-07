"""
Regenerates test_queries-with_results.json for any KG by running all ground-truth
Cypher queries against the live Neo4j DB and storing the results.
Use: NEO4J_DATABASE_NAME=ickg python src/regenerate_results.py
  or NEO4J_DATABASE_NAME=prokino-kg python src/regenerate_results.py
"""
import json, os, time
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from neo4j.graph import Node
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI  = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "YOUR_NEO4J_PASSWORD")
NEO4J_DB   = os.getenv("NEO4J_DATABASE_NAME", "ickg")

KG_NAME = None
if NEO4J_DB == "ickg":
    KG_NAME = "ickg"
elif NEO4J_DB in ("prokino-kg", "neo4j"):
    KG_NAME = "prokino"

if KG_NAME is None:
    raise ValueError(f"Unknown database '{NEO4J_DB}'. Set NEO4J_DATABASE_NAME to ickg or prokino-kg.")

# QUERIES_PATH = f"./data/{KG_NAME}/test_queries.json"
# OUTPUT_PATH  = f"./data/{KG_NAME}/test_queries-with_results.json"
QUERIES_PATH = f"./data/{KG_NAME}/test_queries_updated_june_30.json"
OUTPUT_PATH  = f"./data/{KG_NAME}/test_queries_updated_june_30-with_results.json"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def clean_value(value):
    if isinstance(value, Node):
        return dict(value.items())
    elif isinstance(value, str):
        return value.replace(' ', ' ').strip()
    return value

def run_query(cypher):
    try:
        with driver.session(database=NEO4J_DB) as session:
            results = session.run(cypher)
            return [[clean_value(v) for v in record.values()] for record in results], None
    except Neo4jError as e:
        return [], str(e)

with open(QUERIES_PATH) as f:
    queries = json.load(f)

print(f"Regenerating results for {len(queries)} queries against {NEO4J_DB} ({KG_NAME})...")
enriched = []
for q in queries:
    title = q['title']
    cypher = q['cypher']
    results, err = run_query(cypher)
    if err:
        print(f"  {title}: ERROR - {err}")
    else:
        print(f"  {title}: {len(results)} rows")
    entry = dict(q)
    entry['cypher_result'] = results
    if err:
        entry['error'] = err
    enriched.append(entry)

with open(OUTPUT_PATH, 'w') as f:
    json.dump(enriched, f, indent=4)

driver.close()
print(f"\nSaved to {OUTPUT_PATH}")
print(f"Next: run NEO4J_DATABASE_NAME={NEO4J_DB} python src/sanity_check.py")