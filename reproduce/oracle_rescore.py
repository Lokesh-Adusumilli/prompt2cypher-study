import json, re, logging
from neo4j import GraphDatabase, Query
from neo4j.graph import Node
import os
from dotenv import load_dotenv
load_dotenv()
logging.getLogger('neo4j').setLevel(logging.ERROR)
driver=GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'),auth=(os.getenv('NEO4J_USERNAME','neo4j'), os.getenv('NEO4J_PASSWORD')))
def cv(v):
    if isinstance(v,Node): return dict(v.items())
    if isinstance(v,str): return v.replace(' ',' ').strip()
    return v
def run(q,db,to=30):
    try:
        with driver.session(database=db) as s:
            return [[cv(v) for v in r.values()] for r in s.run(Query(q,timeout=to))]
    except Exception: return None
def flat(res):
    f=set()
    if not res: return f
    for row in res:
        for v in (row if isinstance(row,list) else [row]):
            if v is not None: f.add(str(v).strip())
    return f
def strip(cy): return re.sub(r'\s+LIMIT\s+100\b','',cy,flags=re.I).strip() if isinstance(cy,str) else cy
def getcy(v): return v.get('cypher_query','') if isinstance(v,dict) else v
KGDB={'ProKinO':'prokino-kg','ICKG':'ickg'}
GOLDF={'ProKinO':'data/prokino/test_queries_updated_june_30-with_results.json','ICKG':'data/ickg/test_queries_updated_june_30-with_results.json'}
ORC={('GPT-OSS-20B','ProKinO'):'results/prokino/ablation-gpt-oss-20b-oracle-2026_08_03-07_19_34.json',
     ('GPT-OSS-20B','ICKG'):'results/ickg/ablation-gpt-oss-20b-oracle-2026_08_03-07_24_26.json',
     ('Qwen2.5-Coder-14B','ProKinO'):'results/prokino/ablation-qwen2.5-coder-14b-oracle-2026_08_03-07_26_22.json',
     ('Qwen2.5-Coder-14B','ICKG'):'results/ickg/ablation-qwen2.5-coder-14b-oracle-2026_08_03-07_27_54.json'}
goldunc={}
for kg,f in GOLDF.items():
    goldunc[kg]={e['title']:flat(run(strip(e['cypher']),KGDB[kg])) for e in json.load(open(f))}
for (model,kg),path in ORC.items():
    base=json.load(open(path)); db=KGDB[kg]; F=0;n=0
    for e in base:
        t=e['title']; gset=goldunc[kg].get(t)
        if gset is None: continue
        gen=strip(getcy(e['ablation_results'].get('oracle','')))
        ps=flat(run(gen,db))
        if not ps and not gset: fa=1.0
        elif not ps or not gset: fa=0.0
        else:
            tp=len(ps&gset);fp=len(ps-gset);fn=len(gset-ps)
            p=tp/(tp+fp) if tp+fp else 0;r=tp/(tp+fn) if tp+fn else 0;fa=2*p*r/(p+r) if p+r else 0
        F+=fa;n+=1
    print(f"{model} {kg} Ref-schema uncapped F1 = {F/n:.3f}", flush=True)
driver.close()
