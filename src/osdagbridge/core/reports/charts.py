"""
charts.py: matplotlib figures generated during report compilation.

* Utilization-ratio (UR = Demand / Capacity) summary for the primary members
  (Section 5.5, Overall Design Check Summary).
* Material quantity summary (Chapter 7, Material Take-off).

Figures are written as PNG into the report's temporary build directory and
embedded with :func:`chart_figure`. All styling comes from ``styles.CHART``.
"""
from __future__ import annotations

import os
import textwrap
from typing import Iterable, Optional, Sequence

from osdagbridge.core.reports.styles import CHART

# Primary element groups, in the order they are plotted.
UR_GROUPS = ("Steel Plate Girders", "Concrete Deck Slab", "Cross Bracing", "End Diaphragms")


def _plt():
    """Import pyplot on a non-interactive backend (safe inside the Qt app)."""
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": CHART["font_family"],
        "font.size": CHART["font_size"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#888888",
        "axes.labelcolor": "#333333",
        "xtick.color": "#333333",
        "ytick.color": "#333333",
        "axes.titleweight": "bold",
        "axes.titlesize": CHART["font_size"] + 1,
    })
    return plt


def _to_float(v) -> Optional[float]:
    try:
        f = float(str(v).replace(",", "").split()[0])
    except (TypeError, ValueError, IndexError):
        return None
    return f


def _value_label(ax, x, v, ymax, fmt="{:.2f}"):
    """Write a bar's value inside its top when tall enough, else just above it."""
    if v >= 0.18 * ymax:
        ax.text(x, v - 0.02 * ymax, fmt.format(v), ha="center", va="top",
                fontsize=CHART["font_size"] - 1, color="white", fontweight="bold", zorder=4)
    else:
        ax.text(x, v + 0.015 * ymax, fmt.format(v), ha="center", va="bottom",
                fontsize=CHART["font_size"] - 1, color="#222222", zorder=4)


def _wrap(label: str, width: int = 12) -> str:
    return "\n".join(textwrap.wrap(label, width, break_long_words=False)) or label


# ─────────────────────────────────────────────────────────────────────────────
# Utilization ratio
# ─────────────────────────────────────────────────────────────────────────────
def ur_summary_chart(entries: Iterable[tuple], out_path: str) -> Optional[str]:
    """Small-multiple bar charts of UR per check, one panel per primary element.

    Parameters
    ----------
    entries : iterable of (group, check_label, ur)
        ``group`` is one of :data:`UR_GROUPS`; ``ur`` may be None/"---" when a
        check is not available (shown as "n/a" on the axis).
    out_path : str
        PNG path to write.

    Returns the path, or None if there is nothing to plot.
    """
    by_group = {g: [] for g in UR_GROUPS}
    for group, label, ur in entries:
        if group in by_group:
            by_group[group].append((label, _to_float(ur)))
    if not any(v is not None for rows in by_group.values() for _, v in rows):
        return None

    plt = _plt()
    vals = [v for rows in by_group.values() for _, v in rows if v is not None]
    ymax = max(1.2, max(vals) * 1.18)

    # Girders and deck carry most checks -> full-width rows; bracing and
    # diaphragms (few checks each) share the bottom row.
    fig = plt.figure(figsize=(CHART["width_in"], CHART["height_in"] * 2.5))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1], hspace=0.75, wspace=0.12)
    axes = [fig.add_subplot(gs[0, :]), fig.add_subplot(gs[1, :]),
            fig.add_subplot(gs[2, 0]), fig.add_subplot(gs[2, 1])]
    for ax in axes[1:]:
        ax.sharey(axes[0])
    for ax, group in zip(axes, UR_GROUPS):
        rows = by_group[group]
        ax.set_title(group, loc="left")
        ax.set_ylim(0, ymax)
        ax.yaxis.grid(True, color=CHART["grid"], linewidth=0.6)
        ax.set_axisbelow(True)
        ax.axhline(1.0, color=CHART["ur_line"], linestyle="--", linewidth=1.4, zorder=3)
        if not rows:
            ax.set_xticks([])
            ax.text(0.5, 0.5, "No checks reported", transform=ax.transAxes,
                    ha="center", va="center", color="#777777", style="italic")
            continue
        xs = range(len(rows))
        heights = [v if v is not None else 0 for _, v in rows]
        colors = [CHART["bar_fail"] if (v is not None and v > 1.0) else CHART["bar_pass"]
                  for _, v in rows]
        ax.bar(xs, heights, width=0.62, color=colors, zorder=2)
        for x, (_, v) in zip(xs, rows):
            if v is None:
                ax.text(x, 0.02 * ymax, "n/a", ha="center", va="bottom",
                        fontsize=CHART["font_size"] - 1, color="#777777", style="italic")
            else:
                _value_label(ax, x, v, ymax)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([_wrap(lbl, 12) for lbl, _ in rows], fontsize=CHART["font_size"] - 1)
        ax.set_xlim(-0.6, max(len(rows), 3) - 0.4)
    for ax in (axes[0], axes[1], axes[2]):
        ax.set_ylabel("UR (D/C)")
    axes[3].tick_params(labelleft=False)

    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    handles = [Patch(color=CHART["bar_pass"], label="Pass (UR \u2264 1.0)"),
               Patch(color=CHART["bar_fail"], label="Fail (UR > 1.0)"),
               Line2D([0], [0], color=CHART["ur_line"], linestyle="--", label="Limit UR = 1.0")]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 0.995))
    fig.subplots_adjust(top=0.91, bottom=0.08, left=0.09, right=0.98)
    return _save(fig, out_path)


def governing_ur_chart(entries: Iterable[tuple], out_path: str) -> Optional[str]:
    """One bar per primary element: its governing (maximum) UR across all checks."""
    worst = {}
    for group, label, ur in entries:
        v = _to_float(ur)
        if group in UR_GROUPS and v is not None and (group not in worst or v > worst[group][1]):
            worst[group] = (label, v)
    if not worst:
        return None
    plt = _plt()
    groups = list(UR_GROUPS)
    fig, ax = plt.subplots(figsize=(CHART["width_in"], CHART["height_in"]))
    vals = [worst[g][1] if g in worst else 0.0 for g in groups]
    ymax = max(1.2, max(vals) * 1.25)
    colors = [CHART["bar_fail"] if v > 1.0 else CHART["bar_pass"] for v in vals]
    ax.bar(range(len(groups)), vals, width=0.55, color=colors, zorder=2)
    ax.axhline(1.0, color=CHART["ur_line"], linestyle="--", linewidth=1.4, zorder=3)
    ax.text(len(groups) - 0.55, 1.0 + 0.015 * ymax, "UR = 1.0", color=CHART["ur_line"],
            ha="right", va="bottom", fontsize=CHART["font_size"] - 1)
    ticks = []
    for i, g in enumerate(groups):
        if g in worst:
            lbl, v = worst[g]
            _value_label(ax, i, v, ymax)
            ticks.append(g + "\n(" + _wrap(lbl.split(" --- ")[-1], 22) + ")")
        else:
            ax.text(i, 0.02 * ymax, "n/a", ha="center", va="bottom", color="#777777", style="italic")
            ticks.append(g + "\n(not available)")
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(ticks, fontsize=CHART["font_size"] - 0.5)
    ax.set_ylim(0, ymax)
    ax.set_ylabel("Governing Utilization Ratio")
    ax.yaxis.grid(True, color=CHART["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return _save(fig, out_path)


# ─────────────────────────────────────────────────────────────────────────────
# Material quantities
# ─────────────────────────────────────────────────────────────────────────────
def quantity_charts(q: dict, out_path: str) -> Optional[str]:
    """Three panels: structural-steel tonnage by member, concrete volume, rebar weight.

    ``q`` is the BOQ dict from ``calculate_material_quantities`` (string values,
    "N.A." when unavailable). Concrete (m³) and reinforcement (MT) have different
    units, so they get separate panels rather than a dual axis.
    """
    def total(*keys):
        vals = [_to_float(q.get(k)) for k in keys]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    steel = [
        ("Girders", total("steel_girders_wt_total")),
        ("Cross Bracing", total("bracing_top_wt_total", "bracing_bot_wt_total", "bracing_diag_wt_total")),
        ("End Diaphragms", total("end_diaphragm_wt_total")),
    ]
    concrete = total("concrete_deck_vol_total")
    rebar = total("rebar_deck_wt_total")
    if all(v is None for _, v in steel) and concrete is None and rebar is None:
        return None

    plt = _plt()
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(CHART["width_in"], CHART["height_in"]),
                                     gridspec_kw={"width_ratios": [2.4, 1, 1]})
    _bars(a1, steel, CHART["bar_neutral"], "Structural Steel (MT)", "{:.2f}")
    a1.set_title("Structural steel by member", loc="left")
    _bars(a2, [("Deck Slab", concrete)], CHART["bar_neutral_2"], "Concrete Volume (m\u00b3)", "{:.1f}")
    a2.set_title("Concrete", loc="left")
    _bars(a3, [("Deck Slab", rebar)], CHART["bar_neutral"], "Reinforcement (MT)", "{:.2f}")
    a3.set_title("Reinforcement", loc="left")
    fig.tight_layout(w_pad=2.0)
    return _save(fig, out_path)


def _bars(ax, items: Sequence[tuple], color: str, ylabel: str, fmt: str):
    vals = [v if v is not None else 0.0 for _, v in items]
    top = max(vals) if any(vals) else 1.0
    ax.bar(range(len(items)), vals, width=0.55, color=color, zorder=2)
    for i, (_, v) in enumerate(items):
        txt = fmt.format(v) if v is not None else "n/a"
        ax.text(i, (v or 0) + top * 0.02, txt, ha="center", va="bottom",
                fontsize=CHART["font_size"] - 1, color="#222222" if v is not None else "#777777")
    ax.set_xticks(range(len(items)))
    ax.set_xticklabels([_wrap(l, 12) for l, _ in items])
    ax.set_ylim(0, top * 1.18)
    ax.set_ylabel(ylabel)
    ax.set_xlim(-0.6, len(items) - 0.4)
    ax.yaxis.grid(True, color=CHART["grid"], linewidth=0.6)
    ax.set_axisbelow(True)


def _save(fig, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=CHART["dpi"], bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# LaTeX embedding
# ─────────────────────────────────────────────────────────────────────────────
def chart_figure(rel_path: Optional[str], caption: str, label: str) -> str:
    """Numbered LaTeX figure for a generated chart ('' when the chart was skipped)."""
    if not rel_path:
        return ""
    return (
        "\\begin{figure}[H]\n\\centering\n"
        "\\includegraphics[width=" + CHART["latex_width"] + "]{" + rel_path.replace("\\", "/") + "}\n"
        "\\caption{" + caption + "}\\label{" + label + "}\n"
        "\\end{figure}\n"
    )
