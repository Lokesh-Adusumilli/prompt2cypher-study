"""
Post-import postprocessing for prokino-kg:
1. Set isDarkKinase = false for Protein nodes where it is null
2. Remove the 'Resource' label from nodes that have other labels too
Run after prokino_import.py and before rename_rel_types.py.
"""
import os, time
from neo4j import GraphDatabase

NEO4J_URI  = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "YOUR_NEO4J_PASSWORD"
NEO4J_DB   = "prokino-kg"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

print("Step 1: Set isDarkKinase = false where null...")
with driver.session(database=NEO4J_DB) as s:
    result = s.run(
        "MATCH (p:Protein) WHERE p.isDarkKinase IS NULL SET p.isDarkKinase = false RETURN count(p) AS UpdatedNodes"
    ).single()
    print(f"  Updated {result['UpdatedNodes']} Protein nodes")

print("Step 2: Remove Resource label from multi-label nodes...")
with driver.session(database=NEO4J_DB) as s:
    result = s.run(
        "MATCH (n) WHERE 'Resource' IN labels(n) AND size(labels(n)) > 1 REMOVE n:Resource RETURN count(n) AS UpdatedNodes"
    ).single()
    print(f"  Removed Resource label from {result['UpdatedNodes']} nodes")

print("Postprocessing complete. Next: run rename_rel_types.py")
driver.close()