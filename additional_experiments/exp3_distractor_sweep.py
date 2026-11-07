"""
Experiment 3 — Distractor / schema-size sweep (H1 raw-size vs H2 confusable-distractors).

Interpolates between the Exp-2 oracle (correct relationships only) and the baseline (full schema)
by giving the generator: correct relationships + K distractor relationships, for K in {0,5,20,all},
with two distractor flavors:
  - random  : distractor relationship NAMES sampled uniformly from the rest of the schema
  - similar : distractor NAMES that share an endpoint node with a correct relationship (and/or are
              lexically close) -> the confusable kind the model might be lured into

Same prompt template for every condition (only the relationship set changes), so the ONLY variable is
the distractor count/flavor. Metric downstream: F1 and hallucination vs K.
  H1 (size)      -> F1 falls smoothly with K, random ~= similar at equal K.
  H2 (confusion) -> similar distractors crater F1 far faster than random at equal K.

Small models only (skip DeepSeek). Local Ollama — no paid API. Deterministic (seeded) distractors.
Usage: python additional_experiments/exp3_distractor_sweep.py --model <gpt-oss|qwen-coder> --db <prokino-kg|ickg>
"""
import re, os, json, sys, datetime, argparse, random, difflib
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.helpers import load_schema
load_dotenv()

MODELS = {
    "gpt-oss":    {"tag": "gpt-oss:20b", "stem": "gpt-oss-20b", "provider": "ollama",
                   "base": {"prokino": "results/prokino/ablation-gpt-oss-20b-2026_07_27-20_17_44.json",
                            "ickg":    "results/ickg/ablation-gpt-oss-20b-2026_07_27-20_18_06.json"}},
    "qwen-coder": {"tag": "qwen2.5-coder:14b", "stem": "qwen2.5-coder-14b", "provider": "ollama",
                   "base": {"prokino": "results/prokino/ablation-qwen2.5-coder-14b-2026_07_30-00_03_21.json",
                            "ickg":    "results/ickg/ablation-qwen2.5-coder-14b-2026_07_30-00_03_36.json"}},
    # frontier control (allowed: DeepSeek). Uses the DeepSeek API, not Ollama.
    "deepseek-v4-pro": {"tag": "deepseek-v4-pro", "stem": "deepseek-v4-pro", "provider": "deepseek",
                   "base": {"prokino": "results/prokino/ablation-deepseek-v4-pro-2026_07_23-04_45_47.json",
                            "ickg":    "results/ickg/ablation-deepseek-v4-pro-2026_07_27-10_57_21.json"}},
}
# distractor count as a FRACTION of the available pool (rel-name spaces are small: ProKinO 32, ICKG 18),
# so the sweep is comparable across KGs. 0.0 = oracle, 1.0 = full schema; middle points get both flavors.
K_FRACS = [0.0, 1/3, 2/3, 1.0]

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS.keys()))
ap.add_argument("--db", required=True, choices=["prokino-kg", "ickg"])
a = ap.parse_args()
os.environ["NEO4J_DATABASE_NAME"] = a.db
KG = "ickg" if a.db == "ickg" else "prokino"
MI = MODELS[a.model]
TAG, STEM = MI["tag"], MI["stem"]

if MI["provider"] == "deepseek":
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")
else:
    client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
schema, sc = load_schema(f"data/{KG}/schema.json", f"data/{KG}/schema_comments.json")
schema["nodes_description"] = sc["nodes_description"]; schema["nodes_properties"] = sc["nodes_properties"]
schema["relationship_comments"] = sc["relationship_comments"]
instructions = open(f"prompts/{KG}_instructions.txt").read()
gold = {q["title"]: q for q in json.load(open(f"data/{KG}/test_queries_updated_june_30-with_results.json"))}
base = json.load(open(MI["base"][KG]))

ALL_RELS = schema.get("relationships", [])
ALL_REL_NAMES = sorted(set(r["name"] for r in ALL_RELS))
rows_by_name = {}
for r in ALL_RELS:
    rows_by_name.setdefault(r["name"], []).append(r)

def extract_labels(c):
    return {p for x in re.findall(r'\(\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_|]*)', c or "") for p in x.split('|') if p}
def extract_rels(c):
    return {p for x in re.findall(r'\[\s*\w*\s*:\s*!?([A-Za-z_][A-Za-z0-9_|]*)', c or "") for p in x.split('|') if p}
def clean_cypher(q):
    if not isinstance(q, str): return ""
    i = q.find("MATCH");  q = q[i:] if i != -1 else q
    j = q.rfind(";");     q = q[:j+1] if j != -1 else q
    return q.replace("`", "").replace("\n", " ").strip()

def correct_names(gold_cypher):
    req = extract_rels(gold_cypher)
    return [n for n in ALL_REL_NAMES if n in req]

def endpoints_of(names):
    ep = set()
    for n in names:
        for r in rows_by_name.get(n, []):
            ep.add(r["from"]); ep.add(r["to"])
    return ep

def pick_distractors(correct, K, flavor, seed):
    pool = [n for n in ALL_REL_NAMES if n not in set(correct)]
    if K >= len(pool):
        return pool
    if K <= 0:
        return []
    if flavor == "random":
        return random.Random(seed).sample(pool, K)
    # similar: lexically closest names to any correct rel (matches the observed failure mode -
    # the model confuses similar-sounding names), endpoint overlap as tiebreak
    corr_ep = endpoints_of(correct)
    def score(n):
        lex = max((difflib.SequenceMatcher(None, n, c).ratio() for c in correct), default=0)
        shared = len(endpoints_of([n]) & corr_ep)
        return (lex, shared)
    return sorted(pool, key=score, reverse=True)[:K]

def build_prompt(user_query, rel_names):
    nodes = [n for n in schema["labels"] if n in (endpoints_of(rel_names) | set())] or list(schema["labels"].keys())
    rels = [dict(r, comment=schema["relationship_comments"].get(r["name"], "")) for n in rel_names for r in rows_by_name.get(n, [])]
    info = ""
    for n in nodes:
        info += f"Node: {n}\nDescription: {schema['nodes_description'].get(n,'')}\nProperties:\n"
        for p, pd in schema["nodes_properties"].get(n, {}).items():
            info += f"- {p}: {pd}\n"
        info += "\n"
    return (
        f"You are a helpful AI assistant that generates Cypher queries to answer user queries.\n"
        f"Generate a Cypher query to answer the User query: ```{user_query}```\n"
        f"Consider the following information:\n"
        f"Given the relevant nodes ({nodes}) and all the relationships they are involved in: ```{rels}```\n"
        f"Information about the relevant nodes:\n{info}\n"
        f"\nIMPORTANT Instructions: {instructions}\n"
        f"The Cypher query should answer the user query which is: {user_query}\n"
        f"Return only Cypher code with no explanations. Complete this task: the cypher query is: ...")

def conditions_for(correct, seed):
    """Return {condition_key: [relationship names given to the model]}."""
    pool_size = len(ALL_REL_NAMES) - len(set(correct))
    conds = {}
    conds["frac00"] = list(correct)                              # oracle (0 distractors)
    for frac in K_FRACS:
        if frac in (0.0, 1.0):
            continue
        K = max(1, round(frac * pool_size))
        tag = f"frac{int(round(frac*100)):02d}"
        conds[f"{tag}_random"]  = list(correct) + pick_distractors(correct, K, "random",  seed)
        conds[f"{tag}_similar"] = list(correct) + pick_distractors(correct, K, "similar", seed)
    conds["frac100"] = list(ALL_REL_NAMES)                       # full schema (all distractors)
    return conds

def gen(user_query, rel_names):
    try:
        r = client.chat.completions.create(model=TAG, messages=[{"role":"user","content":build_prompt(user_query, rel_names)}])
        return clean_cypher(r.choices[0].message.content)
    except Exception as e:
        return "Error: " + str(e)

out = []
print(f"[exp3-sweep] model={TAG} KG={KG} K_fracs={K_FRACS}, flavors=random/similar")
for i, e in enumerate(base):
    t = e["title"]; uq = e["query"]
    correct = correct_names(gold.get(t, {}).get("cypher", ""))
    conds = conditions_for(correct, seed=1000 + i)
    ar = {}
    for key, rel_names in conds.items():
        ar[key] = gen(uq, rel_names)
    out.append({"title": t, "query": uq, "correct_rels": correct, "ablation_results": ar})
    print(f"  [{i+1}/{len(base)}] {t}  correct={correct}  conds={list(conds)}")

ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
path = f"results/{KG}/ablation-{STEM}-exp3sweep-{ts}.json"
json.dump(out, open(path, "w"), indent=4)
print(f"Saved: {path}")
