"""
Experiment 1 — Step-1 / generation selection-quality analysis (NO new API runs).
Parses gold Cypher for the required node labels + relationship types per query,
extracts what each generated Cypher actually used, and reports generation-level
recall + hallucination rate per condition per model.
"""
import json, re, os, glob

KG_SCHEMA = {}
def load_schema(kg):
    if kg in KG_SCHEMA: return KG_SCHEMA[kg]
    s = json.load(open(f'data/{kg}/schema.json'))
    labels = set(s['labels'].keys())
    rels = set(r['name'] for r in s['relationships'])
    KG_SCHEMA[kg] = (labels, rels)
    return labels, rels

def extract(cypher):
    """Return (node_label_tokens, rel_type_tokens) used in a Cypher string."""
    if not isinstance(cypher, str): return set(), set()
    # node labels: token right after ':' inside (...)
    node = re.findall(r'\(\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_|]*)', cypher)
    # rel types: token right after ':' inside [...]
    rel  = re.findall(r'\[\s*\w*\s*:\s*!?([A-Za-z_][A-Za-z0-9_|]*)', cypher)
    def flat(lst):
        out=set()
        for x in lst:
            for p in x.split('|'):
                if p: out.add(p)
        return out
    return flat(node), flat(rel)

# base ablation files (generated Cypher). ICKG deepseek uses the corrected 10_57_21 run.
FILES = {
    ('ProKinO','DeepSeek-V4 Pro','frontier'): ('prokino','results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json'),
    ('ICKG','DeepSeek-V4 Pro','frontier'):    ('ickg','results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json'),
    ('ProKinO','GPT-5.4','frontier'):         ('prokino','results/prokino/ablation-gpt-5.4-2026_08_01-20_01_36.json'),
    ('ICKG','GPT-5.4','frontier'):            ('ickg','results/ickg/ablation-gpt-5.4-2026_08_01-20_01_28.json'),
    ('ProKinO','GPT-OSS-20B','small'):        ('prokino','results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json'),
    ('ICKG','GPT-OSS-20B','small'):           ('ickg','results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json'),
    ('ProKinO','Qwen2.5-Coder-14B','small'):  ('prokino','results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json'),
    ('ICKG','Qwen2.5-Coder-14B','small'):     ('ickg','results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json'),
}

def gold_required(kg):
    gt = json.load(open(f'data/{kg}/test_queries_updated_june_30-with_results.json'))
    req={}
    for q in gt:
        n,r = extract(q.get('cypher',''))
        req[q['title']] = (n,r)
    return req

CONDS = ['with_instructions','without_relevant_nodes']
print(f"{'Model':20} {'KG':8} {'Cond':22} {'NodeRec':>8} {'RelRec':>8} {'Halluc%':>8}")
print('-'*80)
h4_hits = []
for (kg_name, model, tier), (kg, path) in FILES.items():
    if not os.path.exists(path):
        print(f"MISSING: {path}"); continue
    labels, rels = load_schema(kg)
    req = gold_required(kg)
    data = json.load(open(path))
    per_cond = {c: {'nrec':[], 'rrec':[], 'halluc':0, 'n':0} for c in CONDS}
    # store used labels per query for H4 proxy
    used_by_q = {}
    for e in data:
        t = e['title']
        ar = e.get('ablation_results', {})
        req_n, req_r = req.get(t, (set(), set()))
        used_by_q[t] = {}
        for c in CONDS:
            cy = ar.get(c, '')
            if isinstance(cy, dict): cy = cy.get('cypher_query','')
            un, ur = extract(cy)
            used_by_q[t][c] = (un, ur)
            # node recall vs gold-required
            if req_n:
                per_cond[c]['nrec'].append(len(req_n & un)/len(req_n))
            if req_r:
                per_cond[c]['rrec'].append(len(req_r & ur)/len(req_r))
            # hallucination: used token not in schema
            halluc = (un - labels) | (ur - rels)
            if halluc: per_cond[c]['halluc'] += 1
            per_cond[c]['n'] += 1
    for c in CONDS:
        d = per_cond[c]
        nrec = sum(d['nrec'])/len(d['nrec']) if d['nrec'] else float('nan')
        rrec = sum(d['rrec'])/len(d['rrec']) if d['rrec'] else float('nan')
        hp = 100*d['halluc']/d['n'] if d['n'] else 0
        print(f"{model:20} {kg_name:8} {c:22} {nrec:8.3f} {rrec:8.3f} {hp:8.1f}")
    # H4 proxy: queries where complete OMITS a required node that no-filtering INCLUDES
    for t,(rn,rr) in req.items():
        if t not in used_by_q: continue
        comp_n = used_by_q[t]['with_instructions'][0]
        nof_n  = used_by_q[t]['without_relevant_nodes'][0]
        missing_in_complete = (rn - comp_n) & nof_n  # required, absent in complete, present in no-filter
        if missing_in_complete:
            h4_hits.append((model, kg_name, t, sorted(missing_in_complete)))
    print()

print("\n=== H4 proxy: queries where COMPLETE dropped a required node that NO-FILTERING kept ===")
if h4_hits:
    for m,kg,t,miss in h4_hits:
        print(f"  {m:20} {kg:8} {t:5} missing nodes: {miss}")
else:
    print("  none")
