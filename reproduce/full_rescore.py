import json, re, logging
from neo4j import GraphDatabase, Query
from neo4j.graph import Node
import os
from dotenv import load_dotenv
load_dotenv()
logging.getLogger('neo4j').setLevel(logging.ERROR)
driver = GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'), auth=(os.getenv('NEO4J_USERNAME','neo4j'), os.getenv('NEO4J_PASSWORD')))

def cv(v):
    if isinstance(v,Node): return dict(v.items())
    if isinstance(v,str): return v.replace(' ',' ').strip()
    return v
def run(q, db, to=30):
    try:
        with driver.session(database=db) as s:
            return [[cv(v) for v in r.values()] for r in s.run(Query(q, timeout=to))]
    except Exception:
        return None
def flat(res):
    f=set()
    if not res: return f
    for row in res:
        for v in (row if isinstance(row,list) else [row]):
            if v is not None: f.add(str(v).strip())
    return f
def prf(pred, gold):
    if pred is None: pred=[]
    ps, gs = flat(pred), flat(gold)
    if not ps and not gs: return (1.0,1.0,1.0)
    if not ps or not gs: return (0.0,0.0,0.0)
    tp=len(ps&gs); fp=len(ps-gs); fn=len(gs-ps)
    p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
    f=2*p*r/(p+r) if p+r else 0
    return (p,r,f)
def strip(cy):
    return re.sub(r'\s+LIMIT\s+100\b','',cy,flags=re.I).strip() if isinstance(cy,str) else cy
def getcy(v):
    return v.get('cypher_query','') if isinstance(v,dict) else v

KGDB={'ProKinO':'prokino-kg','ICKG':'ickg'}
GOLDF={'ProKinO':'data/prokino/test_queries_updated_june_30-with_results.json',
       'ICKG':'data/ickg/test_queries_updated_june_30-with_results.json'}
RUNS={
 ('DeepSeek-V4 Pro','ProKinO'):'results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json',
 ('DeepSeek-V4 Pro','ICKG'):'results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json',
 ('GPT-5.4','ProKinO'):'results/prokino/ablation-gpt-5.4-2026_08_01-20_01_36.json',
 ('GPT-5.4','ICKG'):'results/ickg/ablation-gpt-5.4-2026_08_01-20_01_28.json',
 ('GPT-OSS-20B','ProKinO'):'results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json',
 ('GPT-OSS-20B','ICKG'):'results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json',
 ('Qwen2.5-Coder-14B','ProKinO'):'results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json',
 ('Qwen2.5-Coder-14B','ICKG'):'results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json',
}
COND={'Baseline':'without_relevant_nodes','P2C':'with_instructions'}

# cache gold uncapped per KG
goldunc={}
for kg,f in GOLDF.items():
    d=json.load(open(f)); goldunc[kg]={}
    for e in d:
        goldunc[kg][e['title']]=flat(run(strip(e['cypher']), KGDB[kg]))

out={}
for (model,kg),path in RUNS.items():
    base=json.load(open(path)); db=KGDB[kg]
    for cname,ckey in COND.items():
        P=R=F=0; n=0
        for e in base:
            t=e['title']
            if t not in goldunc[kg]: continue
            gen=strip(getcy(e['ablation_results'].get(ckey,'')))
            gset=goldunc[kg][t]
            pred=run(gen, db)
            # score against uncapped gold (as set)
            ps=flat(pred)
            if not ps and not gset: p,r,fa=1.0,1.0,1.0
            elif not ps or not gset: p,r,fa=0.0,0.0,0.0
            else:
                tp=len(ps&gset); fp=len(ps-gset); fn=len(gset-ps)
                p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0; fa=2*p*r/(p+r) if p+r else 0
            P+=p; R+=r; F+=fa; n+=1
        out[(model,kg,cname)]=(P/n,R/n,F/n)
        print(f"done {model} {kg} {cname}: P={P/n:.3f} R={R/n:.3f} F1={F/n:.3f}", flush=True)

json.dump({f"{k[0]}|{k[1]}|{k[2]}":v for k,v in out.items()}, open('results/uncapped_results.json','w'))
driver.close()
print("ALL_DONE")
