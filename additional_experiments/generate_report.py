"""Generate a presentable Word report of the causation study (additional experiments)."""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

ACCENT = RGBColor(0x0B, 0x52, 0x94)
GREY   = RGBColor(0x55, 0x55, 0x55)

doc = Document()
# base styling
normal = doc.styles["Normal"]
normal.font.name = "Calibri"; normal.font.size = Pt(11)

def h(text, level=1):
    p = doc.add_heading(text, level=level)
    return p

def para(text, italic=False, size=11, color=None, bold=False, space_after=6):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic; r.bold = bold; r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(space_after)
    return p

def bullets(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        # allow simple **bold** segments
        parts = it.split("**")
        for i, seg in enumerate(parts):
            r = p.add_run(seg); r.bold = (i % 2 == 1); r.font.size = Pt(11)

def table(headers, rows, bold_last=False, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        run = hdr[i].paragraphs[0].add_run(htext); run.bold = True; run.font.size = Pt(10)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            r = cells[i].paragraphs[0].add_run(str(val)); r.font.size = Pt(10)
            if bold_last and i == len(row) - 1: r.bold = True
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t

# ---------------- Title ----------------
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
tr = title.add_run("Prompt2Cypher — Causation Study")
tr.bold = True; tr.font.size = Pt(22); tr.font.color.rgb = ACCENT
sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("Why the two-step method rescues small models and is redundant for frontier models")
sr.italic = True; sr.font.size = Pt(12); sr.font.color.rgb = GREY
meta = doc.add_paragraph(); meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run("Additional experiments and results — supporting documentation").font.size = Pt(10)
doc.add_paragraph()

# ---------------- Executive summary ----------------
h("Executive Summary", 1)
para("We investigated why the Prompt2Cypher (P2C) two-step pipeline dramatically improves small / local "
     "language models on Cypher generation, yet offers little or nothing to frontier models. Four experiments "
     "across two knowledge graphs and four models converge on a single mechanism:", space_after=6)
bullets([
    "**The bottleneck is relationship selection, not node selection.** Small models identify the right nodes but hallucinate relationships when handed the full schema.",
    "**The fix is removing the selection burden, proven causally.** Supplying the correct relationships (oracle) recovers small-model F1 by 3.5–7.5×; frontier models are unaffected.",
    "**It cannot be reproduced by prompting.** Asking the model to decompose the task itself — even with strict anti-hallucination instructions — collapses to ~0; only deterministic code-based filtering works.",
    "**It is a capacity / size effect, not adversarial confusion.** Adding any distractors degrades small models; look-alike distractors are no worse than random ones.",
    "**The benefit scales inversely with model capability** — large for weak models, ~0 for frontier models.",
])

# ---------------- Setup ----------------
h("Experimental Setup", 1)
para("Models. Two frontier models — DeepSeek-V4 Pro and GPT-5.4 — and two small / local models — "
     "GPT-OSS-20B and Qwen2.5-Coder-14B (run via local Ollama).")
para("Knowledge graphs. ProKinO (complex: 48 node types, 32 relationship names / 362 typed-edge rows, "
     "OWL-style has* naming, UPPERCASE relationships) and ICKG (focused: 18 node types, 18 relationship "
     "names / 75 rows, standard property names).")
para("Scoring. Flattened set-based F1 against ground-truth query results (30 queries per KG). "
     "\"Complete\" = full P2C two-step pipeline; \"baseline\" = single call with the full schema (no filtering).")

# ---------------- Study 1 ----------------
h("Study 1 — Selection-Quality Analysis", 1)
para("Purpose. Locate where small models fail: do they pick the wrong nodes, the wrong relationships, or "
     "invent (hallucinate) schema elements? Method: parse each generated Cypher, measure node/relationship "
     "recall against the gold query, and count hallucinations (tokens absent from the schema). No new model runs.")
table(["Model", "KG", "Condition", "Node Rec.", "Rel Rec.", "Halluc %"], [
    ["DeepSeek-V4 Pro","ProKinO","complete","0.987","0.990","6.7"],
    ["DeepSeek-V4 Pro","ProKinO","baseline","0.987","0.990","6.7"],
    ["DeepSeek-V4 Pro","ICKG","complete","0.883","0.967","0.0"],
    ["DeepSeek-V4 Pro","ICKG","baseline","0.872","1.000","0.0"],
    ["GPT-5.4","ProKinO","complete","0.976","0.990","6.7"],
    ["GPT-5.4","ProKinO","baseline","0.993","0.990","6.7"],
    ["GPT-5.4","ICKG","complete","0.989","1.000","0.0"],
    ["GPT-5.4","ICKG","baseline","0.911","1.000","0.0"],
    ["GPT-OSS-20B","ProKinO","complete","0.871","0.481","53.3"],
    ["GPT-OSS-20B","ProKinO","baseline","0.787","0.000","83.3"],
    ["GPT-OSS-20B","ICKG","complete","0.975","1.000","0.0"],
    ["GPT-OSS-20B","ICKG","baseline","0.908","0.283","66.7"],
    ["Qwen2.5-Coder-14B","ProKinO","complete","0.881","0.452","43.3"],
    ["Qwen2.5-Coder-14B","ProKinO","baseline","0.788","0.000","76.7"],
    ["Qwen2.5-Coder-14B","ICKG","complete","0.981","0.972","0.0"],
    ["Qwen2.5-Coder-14B","ICKG","baseline","0.964","0.172","76.7"],
])
para("Finding. Node recall stays high everywhere (~0.79–0.99). What collapses for small models on the full "
     "schema is relationship recall (to as low as 0.000) with hallucination spiking to 66–83%. Frontier models "
     "stay stable in both conditions. The problem is relationship selection.", bold=False)

# ---------------- Study 2 ----------------
h("Study 2 — Oracle Relationship Filtering (causal test)", 1)
para("Purpose. Test causality: if relationship selection is the bottleneck, supplying the correct "
     "relationships should rescue small models. Method: replace the model's selection with the exact "
     "relationship types from the gold query (\"oracle\"), and compare against the full P2C pipeline and the baseline.")
table(["Model", "KG", "P2C (complete)", "Baseline", "Oracle"], [
    ["DeepSeek-V4 Pro","ProKinO","0.864","0.884","0.862"],
    ["DeepSeek-V4 Pro","ICKG","0.846","0.846","0.859"],
    ["GPT-OSS-20B","ProKinO","0.369","0.100","0.750"],
    ["GPT-OSS-20B","ICKG","0.887","0.176","0.813"],
    ["Qwen2.5-Coder-14B","ProKinO","0.301","0.157","0.552"],
    ["Qwen2.5-Coder-14B","ICKG","0.692","0.178","0.684"],
], bold_last=True)
para("Finding. The oracle recovers small models by 3.5–7.5× over the baseline (e.g., GPT-OSS ProKinO "
     "0.100 → 0.750). Frontier models are invariant (~0.85 regardless of scope). On the complex schema the "
     "oracle even exceeds the model's own two-step selection, i.e. a perfect selection roughly doubles "
     "small-model performance — improving Step 1 is the highest-leverage lever.")

# ---------------- Study 3 ----------------
h("Study 3 — Single-Prompt Decomposition (architecture vs. prompt)", 1)
para("Purpose. Is the benefit the decomposition itself (which could be prompted in one call) or the two-CALL "
     "architecture where code filters relationships between calls? Method: give the model the full schema and "
     "ask it, in one prompt, to (Step 1) select relevant nodes/relationships then (Step 2) generate. A stricter "
     "variant additionally forbids inventing any name and lists the allowed relationship types verbatim.")
table(["Model", "KG", "P2C (complete)", "Baseline", "Single-prompt", "+ Strict"], [
    ["GPT-OSS-20B","ProKinO","0.369","0.100","0.000","0.000"],
    ["GPT-OSS-20B","ICKG","0.887","0.176","0.000","0.000"],
    ["Qwen2.5-Coder-14B","ProKinO","0.301","0.157","—","0.000"],
    ["Qwen2.5-Coder-14B","ICKG","0.692","0.178","—","0.004"],
])
para("Finding. The single-prompt decomposition collapses to ~0, even with strict anti-hallucination "
     "instructions. The strict constraint did suppress relationship hallucination (96% → 3% on ProKinO), but "
     "the hallucination simply relocated to node labels — 25/30 queries invented labels such as Gene, Drug, "
     "Disease, Therapy, which do not exist in ProKinO. Inspection of the raw chain-of-thought showed the model "
     "hallucinates inside its own Step-1 reasoning: it reasons fluently over a confabulated schema because it "
     "cannot retrieve the real names from a long list. Conclusion: the edge is the code-based filtering, not the prompt.")

# ---------------- Study 4 ----------------
h("Study 4 — Distractor / Schema-Size Sweep", 1)
para("Purpose. Separate two explanations for the collapse: raw SIZE of the candidate set (H1) vs. specifically "
     "CONFUSABLE distractors (H2). Method: interpolate between the oracle (0 distractors) and the full schema by "
     "adding a fraction of distractor relationships, in two flavors — random vs. lexically-similar. Small models "
     "only (Qwen shown; DeepSeek control unavailable — API credit exhausted mid-run).")
table(["Distractors added", "Qwen — ProKinO", "Qwen — ICKG"], [
    ["frac00 (none, oracle)","0.503","0.846"],
    ["frac33 · random","0.100","0.784"],
    ["frac33 · similar","0.133","0.725"],
    ["frac67 · random","0.067","0.284"],
    ["frac67 · similar","0.056","0.294"],
    ["frac100 (full schema)","0.133","0.058"],
])
para("Finding. Adding any distractors degrades performance; \"similar\" distractors are no worse than random "
     "ones. So the collapse is a capacity / selection-burden effect (H1), not adversarial confusion (H2). "
     "The degradation shape tracks schema complexity: ProKinO cliffs immediately (polymorphic relationships "
     "balloon the prompt), while ICKG declines gradually.")

# ---------------- Figure ----------------
h("Synthesis Figure — Benefit vs. Model Capability", 1)
para("Each model contributes two points (one per KG). x = standalone capability (baseline F1); "
     "y = P2C benefit (two-step − baseline). Capability, not parameter size, is the honest x-axis: "
     "the benefit is monotonic with capability but not with size (GPT-OSS-20B benefits more than the "
     "smaller Qwen-14B because it is weaker standalone).")
doc.add_picture("results/exp7_capability_vs_benefit.png", width=Inches(6.2))
last = doc.paragraphs[-1]; last.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
cr = cap.add_run("Figure 1. The two-step benefit shrinks as model capability rises, crossing zero at frontier scale.")
cr.italic = True; cr.font.size = Pt(9); cr.font.color.rgb = GREY

# ---------------- Mechanism ----------------
h("The Mechanism", 1)
para("Small models can reason but cannot ground: over a large relationship set they confabulate relationships "
     "that do not exist. P2C works because deterministic code shrinks that set to the relevant few — triggered by "
     "an easy node-tagging step — removing the selection burden entirely rather than asking the model to shoulder "
     "it. In the two-step pipeline the model never selects relationships at all: it selects nodes (a short, "
     "semantically transparent list), and code derives the relationships from graph topology. Frontier models "
     "never had the grounding problem, so the method is redundant for them; its value scales inversely with capability.")

# ---------------- Caveats ----------------
h("Caveats & Future Work", 1)
bullets([
    "All results are single-run; run-to-run variance is real (Qwen's oracle F1 varied ~0.68–0.85 across runs). Next: N≥3 runs with confidence intervals (bootstrap, McNemar).",
    "The distractor sweep currently covers one small model (Qwen); GPT-OSS would make it a two-model result.",
    "The scaling figure uses four models; adding gemma2-9B and gemma4-26B (local) would densify the middle of the curve.",
    "The frontier control for the sweep is taken from Study 2 (oracle invariance) rather than re-run, as the DeepSeek API credit was exhausted.",
])

# ---------------- Repro ----------------
h("Reproducibility", 1)
para("Scripts: additional_experiments/ (exp1_selection_analysis.py, exp2_oracle_generate.py, "
     "exp3_single_prompt_decomposition.py, exp3_fair_full_run.py, exp3_distractor_sweep.py, exp7_scaling_figure.py). "
     "Detailed write-ups: dump/exp*_results.md. Data artifacts: results/<kg>/ablation-*.json. "
     "Run logs: additional_experiments/logs/. A full file map is in additional_experiments/INDEX.md.")

out = "additional_experiments/Prompt2Cypher_Causation_Study.docx"
doc.save(out)
print("Saved:", out)
