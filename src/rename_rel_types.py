"""
Renames all camelCase relationship types in the Neo4j DB to UPPERCASE
using APOC apoc.refactor.rename.type procedure.

Run once to fix the casing mismatch between the live DB (camelCase from
neosemantics import) and the schema/test-queries (UPPERCASE convention).

After this script completes, run sanity_check.py to verify all ground-truth
queries return the expected results.
"""
import os, time
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI  = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD")
NEO4J_DB   = os.getenv("NEO4J_DATABASE_NAME")

BATCH_SIZE = 10000

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

with driver.session(database=NEO4J_DB) as s:
    rel_types = [r["relationshipType"] for r in
                 s.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]

to_rename     = sorted([(r, r.upper()) for r in rel_types if r != r.upper()])
already_upper = sorted([r for r in rel_types if r == r.upper()])

print(f"Already UPPERCASE (skip): {already_upper if already_upper else 'none'}")
print(f"To rename: {len(to_rename)} types\n")

total_rels = 0
t_start = time.time()

for old, new in to_rename:
    print(f"  {old:30s} -> {new:30s} ...", end="", flush=True)
    t0 = time.time()
    with driver.session(database=NEO4J_DB) as s:
        result = s.run(
            "CALL apoc.refactor.rename.type($old, $new, [], {batchSize: $bs}) "
            "YIELD batches, total, timeTaken",
            old=old, new=new, bs=BATCH_SIZE
        ).single()
    elapsed = time.time() - t0
    if result:
        n = result["total"]
        total_rels += n
        print(f" {n:>10,} rels | {result['batches']:>4} batches | {elapsed:.1f}s")
    else:
        print(f" done ({elapsed:.1f}s)")

driver.close()

print(f"\nDone. {total_rels:,} relationships renamed across {len(to_rename)} types in {time.time()-t_start:.1f}s total.")
print("Next: run  python src/sanity_check.py  to verify ground-truth queries return correct results.")
