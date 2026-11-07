"""
Imports the ProKinO OWL file into the prokino-kg Neo4j database via neosemantics.
Run once after n10s.graphconfig.init with IGNORE + ARRAY settings.
Takes 1-3 hours for ~58M triples.
"""
import os, time
from neo4j import GraphDatabase

NEO4J_URI  = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "YOUR_NEO4J_PASSWORD"
NEO4J_DB   = "prokino-kg"
OWL_PATH   = "file:///home/lokeshadusumilli/Downloads/Prokino_v62_2021-09-15.owl"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

print(f"Starting ProKinO OWL import at {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Source: {OWL_PATH}")
print(f"Database: {NEO4J_DB}")
print("This will take 1-3 hours...")

t_start = time.time()
with driver.session(database=NEO4J_DB) as s:
    result = s.run(
        f'CALL n10s.rdf.import.fetch("{OWL_PATH}", "RDF/XML")',
        timeout=14400
    ).single()
    if result:
        print(f"\nImport result: {dict(result)}")

elapsed = time.time() - t_start
print(f"\nImport completed in {elapsed/3600:.2f} hours ({elapsed:.0f}s)")
print("Next: run postprocessing (isDarkKinase + remove Resource labels) then rename_rel_types.py")
driver.close()