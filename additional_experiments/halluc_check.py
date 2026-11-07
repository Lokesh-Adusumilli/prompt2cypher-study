import json, re
def load_schema(kg):
    s=json.load(open(f'data/{kg}/schema.json'))
    return set(s['labels'].keys()), set(r['name'] for r in s['relationships'])
def extract(c):
    if not isinstance(c,str): return set()
    node=re.findall(r'\(\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_|]*)',c)
    rel =re.findall(r'\[\s*\w*\s*:\s*!?([A-Za-z_][A-Za-z0-9_|]*)',c)
    out=set()
    for x in node+rel:
        for p in x.split('|'):
            if p: out.add(p)
    return out
FILES={('ProKinO','GPT-OSS-20B'):'results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json',
       ('ICKG','GPT-OSS-20B'):'results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json',
       ('ProKinO','Qwen2.5-Coder-14B'):'results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json',
       ('ICKG','Qwen2.5-Coder-14B'):'results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json',
       ('ProKinO','DeepSeek-V4 Pro'):'results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json',
       ('ICKG','DeepSeek-V4 Pro'):'results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json'}
KGDB={'ProKinO':'prokino','ICKG':'ickg'}
print(f"{'Model':18}{'KG':8}{'Cond':6}{'per-query %':>12}{'per-element %':>14}")
for (kg,model),path in FILES.items():
    labels,rels=load_schema(KGDB[kg]); valid=labels|rels
    data=json.load(open(path))
    for cond,lbl in [('with_instructions','P2C'),('without_relevant_nodes','Base')]:
        pq=0; pe=[]; n=0
        for e in data:
            cy=e['ablation_results'].get(cond,'')
            if isinstance(cy,dict): cy=cy.get('cypher_query','')
            used=extract(cy)
            if not used: 
                n+=1; continue
            bad=used-valid
            if bad: pq+=1
            pe.append(len(bad)/len(used))
            n+=1
        pqv=100*pq/n; pev=100*sum(pe)/len(pe) if pe else 0
        print(f"{model:18}{kg:8}{lbl:6}{pqv:12.1f}{pev:14.1f}")
