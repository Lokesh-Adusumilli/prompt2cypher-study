import json, re
from neo4j import GraphDatabase
from neo4j.graph import Node
import os
from dotenv import load_dotenv
load_dotenv()
driver = GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'), auth=(os.getenv('NEO4J_USERNAME','neo4j'), os.getenv('NEO4J_PASSWORD')))

def clean_value(v):
    if isinstance(v, Node): return dict(v.items())
    if isinstance(v, str): return v.replace(' ',' ').strip()
    return v

def run(q, db):
    try:
        with driver.session(database=db) as s:
            res = s.run(q)
            return [[clean_value(v) for v in rec.values()] for rec in res]
    except Exception:
        return None  # error/timeout

def flatten(results):
    flat=set()
    if not results: return flat
    for row in results:
        if isinstance(row,list):
            for val in row:
                if val is not None: flat.add(str(val).strip())
        elif row is not None: flat.add(str(row).strip())
    return flat

def f1(pred, gold):
    ps, gs = flatten(pred), flatten(gold)
    if not ps and not gs: return 1.0
    if not ps or not gs: return 0.0
    tp=len(ps&gs); fp=len(ps-gs); fn=len(gs-ps)
    p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
    return 2*p*r/(p+r) if p+r else 0.0

def strip_limit(cy):
    return re.sub(r'\s+LIMIT\s+100\b','',cy,flags=re.I).strip() if isinstance(cy,str) else cy

RUNS = {
 ('ProKinO','deepseek','prokino-kg'):'results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json',
 ('ICKG','deepseek','ickg'):'results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json',
 ('ProKinO','gpt-5.4','prokino-kg'):'results/prokino/ablation-gpt-5.4-2026_08_01-20_01_36.json',
 ('ICKG','gpt-5.4','ickg'):'results/ickg/ablation-gpt-5.4-2026_08_01-20_01_28.json',
 ('ProKinO','gpt-oss','prokino-kg'):'results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json',
 ('ICKG','gpt-oss','ickg'):'results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json',
 ('ProKinO','qwen','prokino-kg'):'results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json',
 ('ICKG','qwen','ickg'):'results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json',
}
# cache gold uncapped per KG
goldcap={}; golddb={'ProKinO':'prokino-kg','ICKG':'ickg'}
for kg in ['ProKinO','ICKG']:
    d=json.load(open(f"data/{kg.lower() if kg=='ICKG' else 'prokino'}/test_queries_updated_june_30-with_results.json"))
    goldcap[kg]={e['title']:(e['cypher'], e['cypher_result']) for e in d}

print(f"{'Model':10}{'KG':9}{'affected':>9}{'  mean dF1(affected)':>20}")
for (kg,model,db),path in RUNS.items():
    base=json.load(open(path))
    gold=goldcap[kg]
    affected=0; deltas=[]
    for e in base:
        t=e['title']
        gcy, gcap_res = gold.get(t,(None,None))
        if gcy is None: continue
        gen=e['ablation_results'].get('with_instructions','')
        if isinstance(gen,dict): gen=gen.get('cypher_query','')
        # capped F1: use saved gold capped result + re-exec generated capped
        gen_cap = run(gen, db)
        f1_cap = f1(gen_cap, gcap_res)
        # uncapped F1
        gold_unc = run(strip_limit(gcy), db)
        gen_unc  = run(strip_limit(gen), db)
        f1_unc = f1(gen_unc, gold_unc)
        if abs(f1_cap-f1_unc)>1e-6:
            affected+=1; deltas.append(f1_unc-f1_cap)
    md=sum(deltas)/len(deltas) if deltas else 0
    print(f"{model:10}{kg:9}{affected:>9}{md:>+20.3f}")
driver.close()
