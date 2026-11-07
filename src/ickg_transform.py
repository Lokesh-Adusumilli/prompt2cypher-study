"""
Transforms raw ICKG CSVs into neo4j-admin bulk import format.

Input  (from raw data directory):
  df_node.csv   — id, name, type_id, type
  df_edges.csv  — h, t, r, h_id, t_id, r_id, h_c, t_c, h_c_id, t_c_id

Output (to staging directory):
  nodes_import.csv         — id:ID, label, :LABEL
  relationships_import.csv — :START_ID, :END_ID, :TYPE

Run from the project root:
  python src/ickg_transform.py
"""

import os
import csv

RAW_DIR     = "/home/lokeshadusumilli/Desktop/P2C_ver_2/ionChanWithPhosSTpred_KG"
STAGING_DIR = "/home/lokeshadusumilli/Desktop/P2C_ver_2/ickg_import"
CHUNK_SIZE  = 100_000

os.makedirs(STAGING_DIR, exist_ok=True)

# ── Nodes ──────────────────────────────────────────────────────────────────────
nodes_in  = os.path.join(RAW_DIR,     "df_node.csv")
nodes_out = os.path.join(STAGING_DIR, "nodes_import.csv")

print("Transforming nodes...")
node_count = 0
with open(nodes_in,  "r", encoding="utf-8") as fin, \
     open(nodes_out, "w", encoding="utf-8", newline="") as fout:

    reader = csv.DictReader(fin)
    writer = csv.writer(fout)
    writer.writerow(["id:ID", "label", ":LABEL"])

    for row in reader:
        writer.writerow([
            row["id"],      # id:ID
            row["name"],    # label  (renamed from 'name' — queries use .label)
            row["type"],    # :LABEL
        ])
        node_count += 1
        if node_count % CHUNK_SIZE == 0:
            print(f"  ... {node_count:,} nodes written")

print(f"  Done: {node_count:,} nodes → {nodes_out}\n")

# ── Relationships ──────────────────────────────────────────────────────────────
edges_in  = os.path.join(RAW_DIR,     "df_edges.csv")
edges_out = os.path.join(STAGING_DIR, "relationships_import.csv")

print("Transforming relationships...")
edge_count = 0
with open(edges_in,  "r", encoding="utf-8") as fin, \
     open(edges_out, "w", encoding="utf-8", newline="") as fout:

    reader = csv.DictReader(fin)
    writer = csv.writer(fout)
    writer.writerow([":START_ID", ":END_ID", ":TYPE"])

    for row in reader:
        writer.writerow([
            row["h_id"],    # :START_ID
            row["t_id"],    # :END_ID
            row["r"],       # :TYPE  (camelCase — matches test queries directly)
        ])
        edge_count += 1
        if edge_count % CHUNK_SIZE == 0:
            print(f"  ... {edge_count:,} edges written")

print(f"  Done: {edge_count:,} relationships → {edges_out}\n")

# ── Summary ────────────────────────────────────────────────────────────────────
print("Transformation complete.")
print(f"  Nodes file:         {nodes_out}")
print(f"  Relationships file: {edges_out}")
print()
print("Next step: stop the DBMS in Neo4j Desktop, then run neo4j-admin import.")