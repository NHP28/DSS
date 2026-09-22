"""Hinh so sanh tai lap vs paper (Bang 1, Gowalla) + qua trinh tim tham so.

  python src/plots.py   -> outputs/fig_compare.png, outputs/fig_tuning.png
"""
import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs")
KS = ["5", "10", "20", "50"]
PAPER = {"USG": ([0.0605, 0.0490, 0.0384, 0.0274], [0.0431, 0.0685, 0.1059, 0.1828]),
         "CPR": ([0.0722, 0.0586, 0.0462, 0.0322], [0.0491, 0.0789, 0.1224, 0.2073])}
BLUE, BLUE_L, ORANGE, ORANGE_L = "#2a78d6", "#9cc3f0", "#eb6834", "#f6b99f"
INK, INK2 = "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
                     "grid.color": "#e6e5e0", "figure.dpi": 150})


def compare():
    usg = json.load(open(os.path.join(OUT, "usg_results.json")))["test"]["USG"]
    cpr = json.load(open(os.path.join(OUT, "cpr_results.json")))["test"]
    ours = {"USG": ([usg[k][0] for k in KS], [usg[k][1] for k in KS]),
            "CPR": ([cpr[k][0] for k in KS], [cpr[k][1] for k in KS])}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    x = np.arange(len(KS)); w = 0.2
    series = [("USG — paper", PAPER["USG"], BLUE_L), ("USG — tái lập", ours["USG"], BLUE),
              ("CPR — paper", PAPER["CPR"], ORANGE_L), ("CPR — tái lập", ours["CPR"], ORANGE)]
    for ax, mi, name in [(axes[0], 0, "Precision@K"), (axes[1], 1, "Recall@K")]:
        for i, (lab, vals, col) in enumerate(series):
            bars = ax.bar(x + (i - 1.5) * w, vals[mi], w * 0.92, color=col, label=lab)
            for b_, v in zip(bars, vals[mi]):
                ax.text(b_.get_x() + b_.get_width() / 2, v, f"{v:.3f}", ha="center", va="bottom", fontsize=6.5,
                        color=INK2, rotation=90)
        ax.set_xticks(x, [f"K={k}" for k in KS]); ax.set_title(name, loc="left", color=INK)
        ax.grid(axis="x", visible=False)
    axes[0].legend(frameon=False, fontsize=9, ncol=2)
    fig.suptitle("Gowalla (18.737 user, 32.510 POI) — tái lập so với Bảng 1 của paper CPR", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_compare.png"))


def tuning():
    df = pd.read_csv(os.path.join(OUT, "cpr_tuning.csv"))
    usg_tune = json.load(open(os.path.join(OUT, "usg_results.json")))["tune_best"]["10"][0]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    best = df["P@10"].cummax()
    ax.plot(np.arange(1, len(df) + 1), df["P@10"], "o", color=ORANGE, ms=5, label="Mỗi cấu hình CPR")
    ax.step(np.arange(1, len(df) + 1), best, where="post", color=ORANGE, lw=2, label="Tốt nhất đến thời điểm đó")
    ax.axhline(usg_tune, color=BLUE, ls="--", lw=1.5, label=f"USG (tốt nhất) = {usg_tune:.4f}")
    ax.set_xlabel("Lần thử cấu hình"); ax.set_ylabel("P@10 trên tập tune")
    ax.set_title("Tìm tham số CPR trên tập tune", loc="left", color=INK)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_tuning.png"))


if __name__ == "__main__":
    compare()
    tuning()
    print("Da luu outputs/fig_compare.png, outputs/fig_tuning.png")
