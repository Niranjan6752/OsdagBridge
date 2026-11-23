"""
styles.py — single source of truth for the OsdagBridge design-report look.

Every visual / layout parameter used by the report generator lives here:
page geometry, header/footer spacing, fonts, colour palette, table padding,
column presets and chart styling.  Chapter modules must NOT hard-code these
values; they import from this module instead, so a global restyle is a
one-file change.

Layout
------
    PAGE      page size, margins, header/footer clearances
    FONT      base size, line spacing, table/caption font sizes
    COLOR     brand palette (hex, no '#') + semantic colours (pass/fail, UR line)
    TABLE     cell padding, row height, rule widths, page-break thresholds
    COLS      reusable column-spec presets for common table shapes
    CHART     matplotlib styling for generated plots

    latex_style_block()   -> LaTeX preamble fragment generated from the above
    ROW                   -> row terminator with the configured extra row gap
    col_count(spec)       -> number of columns in a LaTeX column spec
"""
from __future__ import annotations

import re

# ── Page geometry ────────────────────────────────────────────────────────────
# `bottom` + `footskip` are sized together so the footer (incl. the optional
# "* Software default value" note above the footer rule) can never overlap the
# last line of body text or the last row of a table.
PAGE = {
    "paper":      "a4paper",
    "left":       "1in",
    "right":      "1in",
    "top":        "1in",      # same text block as the original report, so
    "bottom":     "1in",      # full-width CAD figures still fit two per page
    "headheight": "17pt",
    "headsep":    "6mm",
    "footskip":   "12mm",     # room for the software-default note above the rule
}

# ── Typography ───────────────────────────────────────────────────────────────
FONT = {
    "base_size":     "12pt",         # \documentclass option
    "line_stretch":  1.15,           # \setstretch
    "table_size":    r"\small",      # body text inside tables
    "caption_size":  r"\normalsize",
    "header_size":   r"\small",      # running header / footer
    "note_size":     r"\footnotesize",
}

# ── Colour palette (hex without '#') ─────────────────────────────────────────
COLOR = {
    "brand":         "91B014",   # Osdag green: header/footer rules
    "table_header":  "EEF4DC",   # header-row shading
    "table_alt":     "F7F9F2",   # (optional) zebra rows
    "rule":          "4D4D4D",   # table rules
    "pass":          "2E7D32",
    "fail":          "C62828",
    "ur_limit":      "D32F2F",   # UR = 1.0 reference line in charts
    "muted":         "6B6B6B",
}

# ── Tables ───────────────────────────────────────────────────────────────────
TABLE = {
    "tabcolsep":        "6pt",      # horizontal cell padding
    "arraystretch":     1.15,       # row height multiplier
    "extrarowheight":   "1pt",
    "row_gap":          "4pt",      # extra space after each body row (ROW)
    "rule_width":       "0.5pt",
    "lt_pre":           "4pt",      # space above a longtable
    "lt_post":          "8pt",      # space below a longtable
    # Start a new page rather than begin a table with fewer than this many
    # lines left (stops orphaned captions/headers at the page bottom).
    "needspace_lines":  6,
    "continued_text":   r"\textit{Continued on next page}",
    "continued_cap":    r"(continued)",
}

# Row terminator used by every chapter body row. Chapters write the LaTeX macro
# \osrow{} (defined in latex_style_block from TABLE["row_gap"]); ROW is the
# same terminator for Python code that assembles rows directly.
ROW = r"\osrow{}"

# ── Column presets (total width ≈ 15.5 cm text width) ────────────────────────
COLS = {
    "param_value":     r"|L{5.5cm}|p{9.6cm}|",
    "param_value_wide": r"|L{7cm}|p{8.1cm}|",
}

# ── Figures (CAD screenshots, analysis plots) ────────────────────────────────
# CAD captures take the shape of the viewer window, so a figure is limited in
# BOTH width and height (aspect ratio kept). 0.40 textheight lets two figures
# and their captions share a page whatever the capture's shape.
FIGURE = {
    "max_height": r"0.40\textheight",
}

# ── Charts (matplotlib) ──────────────────────────────────────────────────────
CHART = {
    "dpi":          200,
    "width_in":     7.2,
    "height_in":    3.4,
    "font_family":  "DejaVu Sans",
    "font_size":    9,
    "bar_pass":     "#" + COLOR["brand"],
    "bar_fail":     "#" + COLOR["fail"],
    "bar_neutral":  "#5B7BA6",
    "bar_neutral_2": "#C9A227",
    "ur_line":      "#" + COLOR["ur_limit"],
    "grid":         "#DDDDDD",
    "latex_width":  r"0.95\textwidth",
}


def col_count(spec: str) -> int:
    """Count the columns in a LaTeX tabular/longtable column specification.

    Handles array-package prefixes like ``>{\\centering\\arraybackslash}p{3cm}``
    and the custom ``L{..}``/``C{..}``/``R{..}`` types defined in the preamble.
    """
    s = re.sub(r"\s+", "", spec)
    s = _strip_braced_after(s, ">")   # >{...} cell prefixes
    s = _strip_braced_after(s, "<")   # <{...} cell suffixes
    s = _strip_braced_after(s, "@")   # @{...} inter-column material
    s = _strip_braced_after(s, "!")
    return len(re.findall(r"[LCRpmb]\{[^{}]*\}|[lcrX]", s))


def _strip_braced_after(s: str, marker: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == marker and i + 1 < len(s) and s[i + 1] == "{":
            depth, j = 0, i + 1
            while j < len(s):
                depth += {"{": 1, "}": -1}.get(s[j], 0)
                j += 1
                if depth == 0:
                    break
            i = j
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def geometry_options() -> str:
    return ",".join(f"{k}={v}" for k, v in PAGE.items() if k != "paper") + "," + PAGE["paper"]


def latex_style_block() -> str:
    """Preamble fragment: geometry, palette, table lengths and break rules."""
    colors = "\n".join(rf"\definecolor{{os{_camel(k)}}}{{HTML}}{{{v}}}" for k, v in COLOR.items())
    return rf"""
\usepackage[{geometry_options()}]{{geometry}}

% ── Colour palette (styles.COLOR) ──
{colors}
\colorlet{{osdagGreen}}{{osBrand}}

% ── Table layout (styles.TABLE) ──
\setlength{{\tabcolsep}}{{{TABLE['tabcolsep']}}}
\renewcommand{{\arraystretch}}{{{TABLE['arraystretch']}}}
\setlength{{\extrarowheight}}{{{TABLE['extrarowheight']}}}
\setlength{{\arrayrulewidth}}{{{TABLE['rule_width']}}}
\setlength{{\LTpre}}{{{TABLE['lt_pre']}}}
\setlength{{\LTpost}}{{{TABLE['lt_post']}}}
\setlength{{\LTleft}}{{\fill}}
\setlength{{\LTright}}{{\fill}}
\arrayrulecolor{{osRule}}
% Row terminator used by all generated tables (row gap from styles.TABLE)
% (takes one empty argument so that `\osrow{{}}` is safe before \hline)
\newcommand{{\osrow}}[1]{{\\[{TABLE['row_gap']}]}}

% Never start a floating table with fewer than N lines left on the page.
% (Not applied to longtable: \needspace before a longtable made LaTeX emit the
%  first head *and* the continuation head on the same page. longtable already
%  breaks cleanly and repeats its head via \endhead.)
\BeforeBeginEnvironment{{table}}{{\needspace{{{TABLE['needspace_lines']}\baselineskip}}}}

% Table body font (styles.FONT['table_size'])
\AtBeginEnvironment{{longtable}}{{{FONT['table_size']}}}
\AtBeginEnvironment{{tabular}}{{{FONT['table_size']}}}
"""


def _camel(key: str) -> str:
    return "".join(p.capitalize() for p in key.split("_"))


# ── Column auto-fit ──────────────────────────────────────────────────────────
_UNIT_CM = {"cm": 1.0, "mm": 0.1, "in": 2.54, "pt": 2.54 / 72.27}
_PAPER_WIDTH_CM = {"a4paper": 21.0, "letterpaper": 21.59}


def _to_cm(length: str) -> float:
    m = re.fullmatch(r"\s*([0-9.]+)\s*(cm|mm|in|pt)\s*", length)
    if not m:
        raise ValueError(f"unsupported length {length!r}")
    return float(m.group(1)) * _UNIT_CM[m.group(2)]


def text_width_cm() -> float:
    """Usable text width implied by PAGE (paper width minus side margins)."""
    return _PAPER_WIDTH_CM[PAGE["paper"]] - _to_cm(PAGE["left"]) - _to_cm(PAGE["right"])


def fit_colspec(spec: str, tabcolsep: str | None = None) -> str:
    """Shrink fixed-width columns proportionally so the table fits the text width.

    Each column costs its declared width plus 2 x tabcolsep of padding. If the
    total exceeds the text width, every ``p/L/C/R{<len>}`` width is scaled by
    the same factor. Specs that already fit are returned unchanged.
    """
    pad = 2 * _to_cm(tabcolsep or TABLE["tabcolsep"])
    widths = [(m.start(1), m.end(1), _to_cm(m.group(1)))
              for m in re.finditer(r"[pmbLCR]\{([0-9.]+\s*(?:cm|mm|in|pt))\}", spec)]
    n = col_count(spec)
    if not widths or n != len(widths):
        return spec                      # has l/c/r/X columns: leave alone
    budget = text_width_cm() - n * pad - 0.05   # 0.05 cm for vertical rules
    total = sum(w for _, _, w in widths)
    if total <= budget:
        return spec
    k = budget / total
    out, pos = [], 0
    for a, b, w in widths:
        out.append(spec[pos:a]); out.append(f"{w * k:.2f}cm"); pos = b
    out.append(spec[pos:])
    return "".join(out)
