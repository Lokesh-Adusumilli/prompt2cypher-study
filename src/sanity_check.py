"""
Sanity check: run the ground-truth Cypher queries from test_queries.json
against the live Neo4j database and compare the live results with the
pre-stored results in test_queries-with_results.json.

Outputs:
  - Console summary table
  - results/{KG_NAME}/sanity_check_results.json  (full detail)
  - results/{KG_NAME}/sanity_check.html          (visual diff)
"""

import json, os, html as htmllib, difflib
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from neo4j.graph import Node
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI          = os.getenv("NEO4J_URI")
NEO4J_USERNAME     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD     = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE     = os.getenv("NEO4J_DATABASE_NAME")

KG_NAME = None
if NEO4J_DATABASE == "neo4j":
    KG_NAME = "prokino"
elif NEO4J_DATABASE == "prokino-kg":
    KG_NAME = "prokino"
elif NEO4J_DATABASE == "ickg":
    KG_NAME = "ickg"

# QUERIES_PATH = f"./data/{KG_NAME}/test_queries.json"
# STORED_PATH  = f"./data/{KG_NAME}/test_queries-with_results.json"
QUERIES_PATH      = f"./data/{KG_NAME}/test_queries_updated_june_30.json"
STORED_PATH       = f"./data/{KG_NAME}/test_queries_updated_june_30-with_results.json"
OUTPUT_JSON       = f"./results/{KG_NAME}/sanity_check_results.json"
OUTPUT_HTML       = f"./results/{KG_NAME}/sanity_check.html"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def clean_value(value):
    if isinstance(value, Node):
        return dict(value.items())
    elif isinstance(value, str):
        return value.replace(' ', ' ').strip()
    return value


def run_query(cypher):
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            results = session.run(cypher)
            return [[clean_value(v) for v in record.values()] for record in results], None
    except Neo4jError as e:
        return [], str(e)


def flatten(results):
    out = []
    for r in results:
        if isinstance(r, list):
            for x in r:
                if x is not None and str(x).strip():
                    out.append(str(x).strip())
        elif isinstance(r, dict):
            for x in r.values():
                if x is not None and str(x).strip():
                    out.append(str(x).strip())
        else:
            s = str(r) if r is not None else ''
            if s.strip():
                out.append(s.strip())
    return set(out)


def word_diff_html(a, b):
    a_words, b_words = a.split(), b.split()
    matcher = difflib.SequenceMatcher(None, a_words, b_words)
    a_parts, b_parts = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            t = htmllib.escape(' '.join(a_words[i1:i2]))
            a_parts.append(t); b_parts.append(t)
        elif tag == 'replace':
            a_parts.append(f'<mark>{htmllib.escape(" ".join(a_words[i1:i2]))}</mark>')
            b_parts.append(f'<mark>{htmllib.escape(" ".join(b_words[j1:j2]))}</mark>')
        elif tag == 'delete':
            a_parts.append(f'<mark>{htmllib.escape(" ".join(a_words[i1:i2]))}</mark>')
        elif tag == 'insert':
            b_parts.append(f'<mark>{htmllib.escape(" ".join(b_words[j1:j2]))}</mark>')
    return ' '.join(a_parts), ' '.join(b_parts)


# ── Load data ──────────────────────────────────────────────────────────────────
with open(QUERIES_PATH) as f:
    queries = json.load(f)

with open(STORED_PATH) as f:
    stored_data = json.load(f)

stored_map = {item['title']: item.get('cypher_result', []) for item in stored_data}

# ── Run queries and compare ────────────────────────────────────────────────────
results = []
passed = failed = errored = 0

for item in queries:
    title  = item['title']
    query  = item['query']
    cypher = item['cypher']
    stored = stored_map.get(title, [])

    live_raw, error = run_query(cypher)

    stored_flat = flatten(stored)
    live_flat   = flatten(live_raw)

    tp        = len(live_flat & stored_flat)
    precision = tp / len(live_flat)  if live_flat   else 0.0
    recall    = tp / len(stored_flat) if stored_flat else 0.0
    f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    exact     = live_flat == stored_flat

    status = 'ERROR' if error else ('PASS' if exact else 'MISMATCH')
    if status == 'PASS':    passed   += 1
    elif status == 'ERROR': errored  += 1
    else:                   failed   += 1

    print(f"{title:4s} | {status:8s} | stored={len(stored_flat):3d} live={len(live_flat):3d} | F1={f1:.2f} | {cypher[:60]}...")

    results.append({
        "title":         title,
        "nl_query":      query,
        "cypher":        cypher,
        "error":         error,
        "stored_count":  len(stored_flat),
        "live_count":    len(live_flat),
        "stored_sample": list(stored_flat)[:5],
        "live_sample":   list(live_flat)[:5],
        "only_in_stored": list(stored_flat - live_flat)[:10],
        "only_in_live":   list(live_flat - stored_flat)[:10],
        "precision":     round(precision, 4),
        "recall":        round(recall, 4),
        "f1":            round(f1, 4),
        "exact_match":   exact,
        "status":        status,
    })

driver.close()

print(f"\nSummary: {passed} PASS | {failed} MISMATCH | {errored} ERROR out of {len(queries)} queries")

# ── Save JSON ──────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
with open(OUTPUT_JSON, 'w') as f:
    json.dump(results, f, indent=2)
print(f"JSON saved: {OUTPUT_JSON}")

# ── Save HTML ──────────────────────────────────────────────────────────────────
rows_html = []
for r in results:
    if r['error']:
        row_bg = '#FFF3CD'  # yellow — errored
        stored_html = htmllib.escape(', '.join(r['stored_sample']))
        live_html   = f'<span style="color:red"><b>ERROR:</b> {htmllib.escape(r["error"][:200])}</span>'
        diff_note   = ''
    elif r['exact_match']:
        row_bg = '#C6EFCE'  # green — pass
        stored_html = htmllib.escape(', '.join(r['stored_sample']))
        live_html   = htmllib.escape(', '.join(r['live_sample']))
        diff_note   = ''
    else:
        row_bg = '#FFC7CE'  # red — mismatch
        stored_str  = ' | '.join(sorted(r['stored_sample']))
        live_str    = ' | '.join(sorted(r['live_sample']))
        stored_html, live_html = word_diff_html(stored_str, live_str)
        only_stored = r['only_in_stored']
        only_live   = r['only_in_live']
        parts = []
        if only_stored: parts.append(f'<b>Missing from live ({len(r["only_in_stored"])}):</b> {htmllib.escape(", ".join(only_stored))}')
        if only_live:   parts.append(f'<b>Extra in live ({len(r["only_in_live"])}):</b> {htmllib.escape(", ".join(only_live))}')
        diff_note = '<br>'.join(parts)

    rows_html.append(f"""
    <tr style="background:{row_bg}">
      <td><b>{r['title']}</b></td>
      <td>{htmllib.escape(r['nl_query'])}</td>
      <td><code>{htmllib.escape(r['cypher'])}</code></td>
      <td>stored={r['stored_count']} | live={r['live_count']}<br>
          <small>{stored_html}</small></td>
      <td><small>{live_html}</small><br>{diff_note}</td>
      <td style="text-align:center"><b>{r['f1']:.2f}</b></td>
      <td style="text-align:center">{r['status']}</td>
    </tr>""")

html_out = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Sanity Check — {KG_NAME}</title>
<style>
  body {{ font-family: sans-serif; font-size: 12px; padding: 20px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 7px 9px; vertical-align: top; }}
  th {{ background: #333; color: white; }}
  code {{ white-space: pre-wrap; font-size: 11px; }}
  mark {{ background: #FFD700; padding: 1px 2px; border-radius: 2px; }}
  .summary {{ background:#f5f5f5; padding:12px 16px; border-radius:6px; margin-bottom:14px; }}
</style>
</head>
<body>
<h2>Sanity Check: Ground-Truth Queries vs Live DB — {KG_NAME.upper()}</h2>
<div class="summary">
  <b>{passed}</b> PASS &nbsp;|&nbsp;
  <b>{failed}</b> MISMATCH &nbsp;|&nbsp;
  <b>{errored}</b> ERROR &nbsp;|&nbsp;
  Total: {len(queries)} queries<br><br>
  <span style="background:#C6EFCE;padding:2px 6px">Green</span> = live results match stored &nbsp;|&nbsp;
  <span style="background:#FFC7CE;padding:2px 6px">Red</span> = mismatch &nbsp;|&nbsp;
  <span style="background:#FFF3CD;padding:2px 6px">Yellow</span> = query error &nbsp;|&nbsp;
  <mark>Yellow text</mark> = differing tokens
</div>
<table>
  <thead>
    <tr><th>ID</th><th>NL Query</th><th>Cypher</th><th>Stored Results</th><th>Live Results</th><th>F1</th><th>Status</th></tr>
  </thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
</body>
</html>"""

with open(OUTPUT_HTML, 'w') as f:
    f.write(html_out)
print(f"HTML saved: {OUTPUT_HTML}")
