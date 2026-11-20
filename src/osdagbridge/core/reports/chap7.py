# =============================================================================
# Chapter 7: Material Take-off & Quantity Summary
# =============================================================================
import logging
import os

from osdagbridge.core.reports.report_utils import lt_open
from osdagbridge.core.reports.styles import ROW

# (S.N., description, BOQ key prefix, counts towards structural steel)
_BOQ_ROWS = [
    ("1",    "Structural Steel (IS 2062) for Girders", "steel_girders",  True),
    ("2(a)", "Cross Bracing --- Top Chord",             "bracing_top",    True),
    ("2(b)", "Cross Bracing --- Bottom Chord",          "bracing_bot",    True),
    ("2(c)", "Cross Bracing --- Diagonals",             "bracing_diag",   True),
    ("3",    "End Diaphragms (both supports)",          "end_diaphragm",  True),
    ("4",    "Concrete (M40) for Deck Slab",            "concrete_deck",  False),
    ("5",    "Reinforcement Steel (Fe 500)",            "rebar_deck",     False),
    ("6",    "Shear Stud Connectors",                   "shear_studs",    True),
    ("7",    "Crash Barrier",                           "crash_barrier",  False),
]


def _f(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _boq_table(q):
    rows = []
    steel_total = 0.0
    for sn, desc, key, is_steel in _BOQ_ROWS:
        cells = [str(q.get(f"{key}_{c}", "N.A.")) for c in
                 ("vol_formula", "qty", "vol_total", "wt_single", "wt_total")]
        rows.append(f"{sn} & {desc} & " + " & ".join(cells) + " " + ROW + "\n\\hline")
        if is_steel and _f(q.get(f"{key}_wt_total")) is not None:
            steel_total += _f(q.get(f"{key}_wt_total"))
    rows.append(r"\rowcolor{osTableAlt}\multicolumn{6}{|r|}{\textbf{Total structural steel (items 1, 2, 3, 6)}} & \textbf{"
                + f"{steel_total:.2f}" + "} " + ROW + "\n\\hline")

    header = (r"\textbf{S.N.} & \textbf{Item Description} & \textbf{Volume} & \textbf{Quantity}"
              r" & \textbf{Total Volume (m\textsuperscript{3})} & \textbf{Weight (MT)} & \textbf{Total Weight (MT)}")
    return (
        "\\begingroup\n\\setlength{\\tabcolsep}{3.5pt}\n"
        + lt_open(r"|C{1.0cm}|L{3.6cm}|C{2.9cm}|C{1.75cm}|C{1.8cm}|C{1.7cm}|C{1.8cm}|",
                  r"\textbf{Bill of Materials (Steel, Concrete, and Reinforcement Quantities)}",
                  header, label="tab:boq", tabcolsep="3.5pt")
        + "\n".join(rows) + "\n\\end{longtable}\n\\endgroup\n"
    )


def ch7_quantities(input_dict, chart_dir=None):
    figs = ""
    if chart_dir:
        from osdagbridge.core.reports.charts import quantity_charts, chart_figure
        try:
            path = quantity_charts(input_dict, os.path.join(chart_dir, "charts", "quantities.png"))
        except Exception as exc:          # never let a plotting issue break the report
            logging.getLogger(__name__).warning("Quantity chart generation failed: %s", exc)
            path = None
        figs = chart_figure(path and "charts/quantities.png",
                            r"Material quantity summary: structural steel tonnage by member, "
                            r"deck concrete volume and reinforcement weight",
                            "fig:quantities")

    return r"""
\chapter{Material Take-off \& Quantity Summary}
\label{ch:material-takeoff}

""" + _boq_table(input_dict) + r"""

\noindent{\footnotesize\textit{Steel weights use 7.85 t/m\textsuperscript{3}; reinforcement is estimated at 120 kg per m\textsuperscript{3} of deck concrete. End-diaphragm length per bay = 2 chords + 2 diagonals (cross-bracing type) or one beam (rolled/welded type).}}

\vspace{0.8em}
""" + figs + r"""
"""
