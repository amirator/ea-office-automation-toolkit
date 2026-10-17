"""One-page executive KPI pack (PDF + PNG) with RAG status, trends and auto-written exceptions."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from toolkit.common import GREY, LIGHT, NAVY, RAG_COLOURS, SAMPLE_BANNER, ensure_dir, read_csv  # noqa: E402


@dataclass
class KPI:
    name: str
    function: str
    unit: str
    direction: str  # "higher" or "lower" is better
    tolerance_pct: float
    history: "OrderedDict[str, tuple[float, float]]" = field(default_factory=OrderedDict)  # period -> (actual, target)


def rag_status(actual: float, target: float, direction: str, tolerance_pct: float) -> str:
    """Green = on/better than target; Amber = within tolerance; Red = outside tolerance."""
    tol = abs(target) * tolerance_pct / 100
    if direction == "higher":
        if actual >= target:
            return "Green"
        return "Amber" if actual >= target - tol else "Red"
    if direction == "lower":
        if actual <= target:
            return "Green"
        return "Amber" if actual <= target + tol else "Red"
    raise ValueError(f"direction must be 'higher' or 'lower', got {direction!r}")


def load_kpis(path) -> list[KPI]:
    kpis: "OrderedDict[str, KPI]" = OrderedDict()
    for r in read_csv(path):
        k = kpis.setdefault(r["kpi"], KPI(r["kpi"], r["function"], r["unit"], r["direction"].lower(),
                                          float(r["amber_tolerance_pct"])))
        k.history[r["period"]] = (float(r["actual"]), float(r["target"]))
    for k in kpis.values():
        k.history = OrderedDict(sorted(k.history.items()))
    return list(kpis.values())


def fmt(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v:.0f}%"
    if unit == "SAR":
        return f"SAR {v:,.0f}"
    return f"{v:g} {unit}"


def assess(kpis: list[KPI], period: str | None = None) -> tuple[str, list[dict]]:
    periods = sorted({p for k in kpis for p in k.history})
    period = period or periods[-1]
    rows = []
    for k in kpis:
        if period not in k.history:
            raise ValueError(f"KPI '{k.name}' has no value for {period}")
        keys = list(k.history)
        idx = keys.index(period)
        actual, target = k.history[period]
        prev = k.history[keys[idx - 1]][0] if idx else None
        status = rag_status(actual, target, k.direction, k.tolerance_pct)
        # consecutive periods (ending now) off target
        streak = 0
        for p in reversed(keys[: idx + 1]):
            a, t = k.history[p]
            if rag_status(a, t, k.direction, k.tolerance_pct) == "Green":
                break
            streak += 1
        rows.append({"kpi": k, "actual": actual, "target": target, "prev": prev, "status": status, "streak": streak,
                     "series": [k.history[p][0] for p in keys[: idx + 1]], "periods": keys[: idx + 1]})
    return period, rows


def commentary(r: dict) -> str:
    k = r["kpi"]
    unit_word = " pts" if k.unit == "%" else (f" {k.unit}" if k.unit != "SAR" else "")
    s = f"{k.name}: {fmt(r['actual'], k.unit)} vs target {fmt(r['target'], k.unit)}"
    if r["prev"] is not None:
        d = r["actual"] - r["prev"]
        better = (d > 0) == (k.direction == "higher")
        mag = f"{abs(d):,.0f}" if k.unit in ("%", "SAR") else f"{abs(d):g}"
        s += f", {'improving' if better and d else 'worsening' if d else 'flat'}" + (
            f" ({'+' if d > 0 else '-'}{mag}{unit_word} on last month)" if d else "")
    if r["streak"] > 1:
        s += f"; off target for {r['streak']} consecutive months"
    return s + f". Owner: {k.function}."


def render(kpis: list[KPI], out_dir, period: str | None = None, title: str = "Executive KPI Pack",
           sample: bool = True) -> dict:
    period, rows = assess(kpis, period)
    month = datetime.strptime(period, "%Y-%m").strftime("%B %Y")
    c = lambda h: "#" + h
    fig = plt.figure(figsize=(11.69, 8.27), dpi=100)
    fig.patch.set_facecolor("white")
    plt.rcParams["font.family"] = "DejaVu Sans"

    # Header band
    fig.add_artist(Rectangle((0, 0.885), 1, 0.115, transform=fig.transFigure, color=c(NAVY), zorder=0))
    fig.text(0.03, 0.948, f"{title}  |  {month}", color="white", fontsize=20, fontweight="bold", va="center")
    fig.text(0.03, 0.905, "Demo Holding Co.  |  Executive Office" + (f"   ·   {SAMPLE_BANNER}" if sample else ""),
             color="#C9D3DF", fontsize=9, va="center")
    counts = {s: sum(r["status"] == s for r in rows) for s in ("Green", "Amber", "Red")}
    x = 0.735
    for s in ("Green", "Amber", "Red"):
        fig.add_artist(FancyBboxPatch((x, 0.925), 0.064, 0.04, boxstyle="round,pad=0.004,rounding_size=0.012",
                                      transform=fig.transFigure, color=c(RAG_COLOURS[s])))
        fig.text(x + 0.032, 0.945, f"{counts[s]} {s}", color="white", fontsize=9.5, fontweight="bold",
                 ha="center", va="center")
        x += 0.08

    # KPI tiles: 2 rows x 4 columns
    cols, w, h, gap = 4, 0.225, 0.29, 0.016
    for i, r in enumerate(rows):
        k = r["kpi"]
        col, row = i % cols, i // cols
        x0 = 0.03 + col * (w + gap)
        y0 = 0.565 - row * (h + 0.025)
        colour = c(RAG_COLOURS[r["status"]])
        fig.add_artist(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.008",
                                      transform=fig.transFigure, facecolor=c(LIGHT), edgecolor="#E1E5EA"))
        fig.add_artist(Rectangle((x0, y0), 0.006, h, transform=fig.transFigure, color=colour))
        fig.text(x0 + 0.016, y0 + h - 0.018, "\n".join(textwrap.wrap(k.name, 32)[:2]), fontsize=9.2,
                 fontweight="bold", color=c(NAVY), va="top", linespacing=1.25)
        fig.text(x0 + 0.016, y0 + h - 0.068, k.function, fontsize=7.5, color=c(GREY), va="top")
        fig.text(x0 + 0.016, y0 + h - 0.088, fmt(r["actual"], k.unit), fontsize=19, fontweight="bold",
                 color=c(NAVY), va="top")
        fig.add_artist(FancyBboxPatch((x0 + w - 0.068, y0 + h - 0.118), 0.056, 0.028,
                                      boxstyle="round,pad=0,rounding_size=0.01", transform=fig.transFigure,
                                      color=colour))
        fig.text(x0 + w - 0.040, y0 + h - 0.104, r["status"].upper(), fontsize=7.5, fontweight="bold",
                 color="white", ha="center", va="center")
        better = "higher is better" if k.direction == "higher" else "lower is better"
        fig.text(x0 + 0.016, y0 + h - 0.142, f"Target {fmt(r['target'], k.unit)}  ({better})",
                 fontsize=7.8, color=c(GREY), va="top")
        if r["prev"] is not None:
            d = r["actual"] - r["prev"]
            prev_month = datetime.strptime(r["periods"][-2], "%Y-%m").strftime("%b")
            if d == 0:
                delta, dcol = f"= no change vs {prev_month}", c(GREY)
            else:
                mag = f"{abs(d):,.0f}" if k.unit in ("%", "SAR") else f"{abs(d):g}"
                unit = " pts" if k.unit == "%" else ("" if k.unit == "SAR" else f" {k.unit}")
                good = (d > 0) == (k.direction == "higher")
                delta = f"{'▲' if d > 0 else '▼'} {'+' if d > 0 else '-'}{mag}{unit} vs {prev_month}"
                dcol = c(RAG_COLOURS["Green"]) if good else c(RAG_COLOURS["Red"])
            fig.text(x0 + 0.016, y0 + h - 0.162, delta, fontsize=7.8, color=dcol, va="top", fontweight="bold")
        ax = fig.add_axes([x0 + 0.03, y0 + 0.024, w - 0.042, 0.072])
        ax.set_zorder(5)
        xs = range(len(r["series"]))
        ax.plot(xs, r["series"], color=c(NAVY), lw=1.6, marker="o", ms=2.8)
        ax.plot(xs[-1], r["series"][-1], marker="o", ms=5.5, color=colour)
        ax.axhline(r["target"], color=colour if r["status"] != "Green" else c(RAG_COLOURS["Green"]), lw=0.9,
                   ls="--", alpha=0.8)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([datetime.strptime(p, "%Y-%m").strftime("%b")[:3] for p in r["periods"]], fontsize=6,
                           color=c(GREY))
        ax.tick_params(axis="y", labelsize=6, colors=c(GREY), length=0)
        ax.tick_params(axis="x", length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#C9D3DF")
        ax.set_facecolor(c(LIGHT))
        lo, hi = min(r["series"] + [r["target"]]), max(r["series"] + [r["target"]])
        pad = (hi - lo) * 0.25 or 1
        ax.set_ylim(lo - pad, hi + pad)

    # Exceptions panel
    exc = sorted([r for r in rows if r["status"] != "Green"], key=lambda r: (r["status"] != "Red", r["kpi"].name))
    fig.text(0.03, 0.212, "Exceptions requiring attention", fontsize=11.5, fontweight="bold", color=c(NAVY))
    y = 0.180
    for r in exc[:5]:
        fig.add_artist(FancyBboxPatch((0.03, y - 0.010), 0.011, 0.02, boxstyle="round,pad=0,rounding_size=0.004",
                                      transform=fig.transFigure, color=c(RAG_COLOURS[r["status"]])))
        fig.text(0.05, y, commentary(r), fontsize=8.4, color="#1F2937", va="center")
        y -= 0.033
    if not exc:
        fig.text(0.05, y, "All KPIs are on target this month.", fontsize=8.4, color="#1F2937")
    fig.text(0.03, 0.034, "RAG rule: Green = on or better than target; Amber = within the KPI's tolerance band; "
             "Red = outside tolerance. Trend lines show the last 6 months; dashed line = target.",
             fontsize=7, color=c(GREY))
    fig.text(0.03, 0.014, f"Generated {datetime.now():%d %b %Y} · EA Office Automation Toolkit", fontsize=7,
             color=c(GREY))

    out = ensure_dir(out_dir)
    stem = f"kpi_pack_{period}"
    pdf, png = out / f"{stem}.pdf", out / f"{stem}.png"
    fig.savefig(pdf)
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return {"pdf": pdf, "png": png, "period": period, "rows": rows, "counts": counts}
