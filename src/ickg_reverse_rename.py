"""
Reverses the accidental UPPERCASE rename of ICKG relationship types.
rename_rel_types.py was mistakenly run against ickg (via .env NEO4J_DATABASE_NAME=ickg)
instead of prokino-kg, uppercasing all ICKG relationship types.
This script renames them back to their original camelCase names.
"""
import time
from neo4j import GraphDatabase

NEO4J_URI  = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "YOUR_NEO4J_PASSWORD"
NEO4J_DB   = "ickg"

BATCH_SIZE = 10000

# exact reverse of what rename_rel_types.py did to ICKG
REVERSE_MAP = {
    "ASSOWITHBIOLOGICALPROCESS": "assoWithBiologicalProcess",
    "ASSOWITHCELLULARCOMPONENT": "assoWithCellularComponent",
    "ASSOWITHDISEASE":           "assoWithDisease",
    "ASSOWITHGENE":              "assoWithGene",
    "ASSOWITHMOLECULARFUNCTION": "assoWithMolecularFunction",
    "HASBIOLOGICALPROCESS":      "hasBiologicalProcess",
    "HASCELLULARCOMPONENT":      "hasCellularComponent",
    "HASFAMILY":                 "hasFamily",
    "HASFUNCTIONALDOMAIN":       "hasFunctionalDomain",
    "HASGATEMECHANISM":          "hasGateMechanism",
    "HASGROUP":                  "hasGroup",
    "HASIONASSO":                "hasIonAsso",
    "HASMOLECULARFUNCTION":      "hasMolecularFunction",
    "HASPATHWAY":                "hasPathway",
    "HASPREDPHOSSITE":           "hasPredPhosSite",
    "HASPTM":                    "hasPTM",
    "HASUNIT":                   "hasUnit",
    "IMPLICATEDINDISEASE":       "implicatedInDisease",
    "INTERACT":                  "interact",
}

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

with driver.session(database=NEO4J_DB) as s:
    current_types = [r["relationshipType"] for r in
                     s.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]

to_fix = {k: v for k, v in REVERSE_MAP.items() if k in current_types}
already_ok = [v for k, v in REVERSE_MAP.items() if k not in current_types]

print(f"Already restored (skip): {already_ok if already_ok else 'none'}")
print(f"To reverse-rename: {len(to_fix)} types\n")

total = 0
t0 = time.time()
for old, new in to_fix.items():
    print(f"  {old:35s} -> {new:35s} ...", end="", flush=True)
    t1 = time.time()
    with driver.session(database=NEO4J_DB) as s:
        result = s.run(
            "CALL apoc.refactor.rename.type($old, $new, [], {batchSize: $bs}) "
            "YIELD batches, total, timeTaken",
            old=old, new=new, bs=BATCH_SIZE
        ).single()
    if result:
        n = result["total"]
        total += n
        print(f" {n:>10,} rels | {time.time()-t1:.1f}s")
    else:
        print(f" done ({time.time()-t1:.1f}s)")

driver.close()
print(f"\nDone. {total:,} relationships restored in {time.time()-t0:.1f}s")
print("Next: run  python src/sanity_check.py  (with NEO4J_DATABASE_NAME=ickg)")