"""
Exp 7 — Scaling figure: P2C benefit vs standalone model capability.
y = delta-F1 (P2C two-step - baseline single-call);  x = baseline F1 (model's standalone capability).
The benefit is monotonic with CAPABILITY, not parameter size (GPT-OSS-20B benefits more than Qwen-14B
because it is weaker standalone), so capability is the honest x-axis.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

# Model/KG F1 for the figure. Preferred source: the uncapped scores written by
# reproduce/full_rescore.py (results/uncapped_results.json). If that file is absent,
# fall back to the reported values so the figure can still be regenerated standalone.
import json, os
_DISPLAY = {"DeepSeek-V4 Pro": "DeepSeek-V4 Pro", "GPT-5.4": "GPT-5.4",
            "GPT-OSS-20B": "GPT-OSS-20B", "Qwen2.5-Coder-14B": "Qwen-14B"}
_RESULTS = "results/uncapped_results.json"
if os.path.exists(_RESULTS):
    _r = json.load(open(_RESULTS))
    DATA = [(disp, kg, _r[f"{full}|{kg}|P2C"][2], _r[f"{full}|{kg}|Baseline"][2])
            for full, disp in _DISPLAY.items() for kg in ("ProKinO", "ICKG")]
    print(f"[exp7] using uncapped scores from {_RESULTS}")
else:
    print(f"[exp7] {_RESULTS} not found - using reported fallback values")
    DATA = [
        ("Qwen-14B",   "ProKinO", 0.300, 0.186),
        ("Qwen-14B",   "ICKG",    0.709, 0.177),
        ("GPT-OSS-20B","ProKinO", 0.400, 0.100),
        ("GPT-OSS-20B","ICKG",    0.909, 0.192),
        ("DeepSeek-V4 Pro","ProKinO", 0.915, 0.936),
        ("DeepSeek-V4 Pro","ICKG",    0.860, 0.860),
        ("GPT-5.4",    "ProKinO", 0.894, 0.936),
        ("GPT-5.4",    "ICKG",    0.823, 0.844),
    ]
# Okabe-Ito CVD-safe pair; marker shape = secondary encoding (identity never color-alone)
STYLE = {"ProKinO": ("#0072B2", "o"), "ICKG": ("#E69F00", "s")}

xs = np.array([d[3] for d in DATA])
ys = np.array([d[2] - d[3] for d in DATA])

plt.rcParams.update({"font.size": 12, "font.family": "DejaVu Sans", "axes.edgecolor": "#666"})
fig, ax = plt.subplots(figsize=(8.4, 5.6), dpi=200)

# guide lines / regions
ax.axhline(0, color="#444", lw=1.4, ls="--", zorder=1)
ax.axhspan(0, 0.8, color="#0072B2", alpha=0.04, zorder=0)
# linear trend across all 8 points (visualizes the inverse relationship)
m, b = np.polyfit(xs, ys, 1)
gx = np.linspace(0.05, 0.97, 100)
ax.plot(gx, m*gx + b, color="#999", lw=1.6, ls=(0, (4, 3)), zorder=2, label="_trend")

# hand-placed label positions (data coords) + leader lines, to avoid collisions in the frontier cluster
LABELS = {
    ("Qwen-14B", "ProKinO"):        (0.25, 0.15, "left"),
    ("Qwen-14B", "ICKG"):           (0.25, 0.50, "left"),
    ("GPT-OSS-20B", "ProKinO"):     (0.15, 0.31, "left"),
    ("GPT-OSS-20B", "ICKG"):        (0.23, 0.735, "left"),
    ("DeepSeek-V4 Pro", "ProKinO"): (0.95, 0.11, "right"),
    ("DeepSeek-V4 Pro", "ICKG"):    (0.60, 0.11, "left"),
    ("GPT-5.4", "ProKinO"):         (0.96, -0.13, "right"),
    ("GPT-5.4", "ICKG"):            (0.58, -0.055, "left"),
}
for model, kg, comp, base in DATA:
    c, mk = STYLE[kg]
    x, y = base, comp - base
    ax.scatter([x], [y], s=130, c=c, marker=mk, edgecolors="white", linewidths=1.4, zorder=4)
    lx, ly, ha = LABELS[(model, kg)]
    ax.annotate(model, (x, y), xytext=(lx, ly), ha=ha, fontsize=9.5, color="#222", zorder=5,
                arrowprops=dict(arrowstyle="-", color="#bbb", lw=0.8, shrinkA=2, shrinkB=4))

# region captions
ax.text(0.14, 0.60, "local models", ha="center", va="center",
        fontsize=11, color="#0072B2", weight="bold")
ax.text(0.87, 0.16, "hosted models", ha="center", va="center",
        fontsize=11, color="#7a5200", weight="bold")

ax.set_xlabel("baseline F1", fontsize=12)
ax.set_ylabel("P2C advantage   ΔF1 = P2C − baseline", fontsize=12)
ax.set_xlim(0.0, 1.0); ax.set_ylim(-0.15, 0.8)
ax.grid(True, color="#e6e6e6", lw=0.8, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)

legend = [Line2D([0],[0], marker="o", linestyle="none", markerfacecolor="#0072B2", markeredgecolor="white", markersize=11, label="ProKinO (complex schema)"),
          Line2D([0],[0], marker="s", linestyle="none", markerfacecolor="#E69F00", markeredgecolor="white", markersize=10, label="ICKG (focused schema)")]
ax.legend(handles=legend, loc="upper right", frameon=False, fontsize=10.5)

fig.tight_layout()
out = "results/fig6_capability_vs_benefit_uncapped.png"
fig.savefig(out, bbox_inches="tight")
print(f"Saved: {out}")
