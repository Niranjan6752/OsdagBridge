from osdagbridge.core.utils.common import (
    KEY_MP_GD_MEMBER_ID,
    KEY_MP_GD_SELECT_GIRDER,
    KEY_MP_GIRDER_DEPTH,
    KEY_TS_NO_OF_GIRDERS
)


def _tex(value):
    """Escape a Python value for safe LaTeX embedding."""
    s = str(value) if value is not None else ''
    if not s:
        return r''
    # Normalise non-ASCII glyphs from section designations (e.g. "∠ 100 ⅹ 100ⅹ 10")
    # that pdflatex cannot render.
    for uni, ascii_ in [('∠', 'L'), ('ⅹ', 'x'), ('×', 'x')]:
        s = s.replace(uni, ascii_)
    s = s.replace('\\', r'\textbackslash{}')
    for ch, esc in [('&', r'\&'), ('%', r'\%'), ('$', r'\$'), ('#', r'\#'),
                    ('{', r'\{'), ('}', r'\}'),          
                    ('_', r'\_\allowbreak{}'),            
                    ('~', r'\textasciitilde{}'), ('^', r'\^{}')]:
        s = s.replace(ch, esc)
    s = s.replace(':', r':\allowbreak{}')
    return s


def _render_value(source_dict, key, unit=""):
    val = source_dict.get(key)
    if val in ("", None):
        return ""
    return _tex(_num(val)) + unit


def get_girder_entries(input_dict):
    """
    Retrieve all girder labels and member IDs from backend keys.

    Usage Example:
    --------------------------
    girder_entries = get_girder_entries(bridge.input_dict)
    
    # 1. Fallback handling (if backend hasn't populated keys yet)
    if not girder_entries:
        n = int(bridge.input_dict.get(KEY_TS_NO_OF_GIRDERS, 1))
        girder_entries = [(f"Girder {i}", f"M1") for i in range(1, n + 1)]
        
    # 2. Get total number of girders safely
    n_girders = len(girder_entries)
    
    # 3. Iterate over the girders to build table rows
    for lbl, mid in girder_entries:
        # lbl will be e.g., "G1", mid will be e.g., "G1M1"
        # Access girder specific keys dynamically:
        # val = input_dict.get(f"{KEY_MP_GIRDER_DEPTH}.{lbl}.{mid}")
        pass

    Returns:
        List[Tuple[str, str]]
    """
    n = int(input_dict.get(KEY_TS_NO_OF_GIRDERS, 0))

    entries = []

    for i in range(1, n + 1):
        entries.append(
            (
                input_dict.get(f"{KEY_MP_GD_SELECT_GIRDER}.G{i}", ""),
                input_dict.get(f"{KEY_MP_GD_MEMBER_ID}.G{i}.M1", ""),
            )
        )

    return entries


def _fig_size(width, height=None):
    """includegraphics options: fit inside width x max height, keeping the aspect ratio."""
    from osdagbridge.core.reports.styles import FIGURE
    return 'width=' + width + ',height=' + (height or FIGURE['max_height']) + ',keepaspectratio'


def _fig_or_placeholder(path, caption, width=r'0.9\textwidth'):
    """Embed figure if path is provided (file already copied to assets), else show placeholder box.
    path is the relative path as pdflatex will see it (e.g. 'assets/plan.png').
    """
    if path:
        p = path.replace('\\', '/')
        return (r'\begin{figure}[H]' + '\n'
                r'\centering' + '\n'
                r'\includegraphics[' + _fig_size(width) + ']{' + p + '}\n'
                r'\caption*{' + caption + '}\n'
                r'\end{figure}')
    return (r'\begin{figure}[H]' + '\n'
            r'\centering' + '\n'
            r'\fbox{\parbox{0.97\textwidth}{' + '\n'
            r'\textit{[ PLACEHOLDER: ' + caption + r' ]}' + '\n'
            r'}}' + '\n'
            r'\caption*{' + caption + '}\n'
            r'\end{figure}')

def _fig_embed(path, caption, width=r'\textwidth', height=None):
    """Embed a real figure when path is provided (already copied); otherwise use an fbox placeholder."""
    if path:
        p = path.replace('\\', '/')
        opts = _fig_size(width, height)
        return (r'\begin{figure}[H]' + '\n'
                r'\vspace{-0.5em}' + '\n'
                r'\centering' + '\n'
                r'\includegraphics[' + opts + ']{' + p + '}\n'
                r'\vspace{0.5em}' + '\n'
                r'\caption*{\small ' + caption + '}\n'
                r'\vspace{-0.5em}' + '\n'
                r'\end{figure}')
    # fbox placeholder — matches template exactly
    return (r'\noindent\fbox{\parbox{0.97\textwidth}{' + '\n'
            r'\textit{[ PLACEHOLDER: ' + caption + r' ]}' + '\n'
            r'}}')




# ─────────────────────────────────────────────────────────────────────────────
# Longtable builder: repeated headers across page breaks
# ─────────────────────────────────────────────────────────────────────────────
def lt_open(colspec, caption=None, header=None, label=None, header_rows=None, tabcolsep=None):
    """Open a ``longtable`` whose caption and column-header row repeat on every page.

    Produces the four longtable head/foot sections:

    * ``\\endfirsthead``: caption + header row (first page)
    * ``\\endhead``: "Table n.m (continued)" + header row (every later page)
    * ``\\endfoot``: "Continued on next page" note (every page but the last)
    * ``\\endlastfoot``: nothing (the body's own final ``\\hline`` closes the table)

    Parameters
    ----------
    colspec : str
        LaTeX column spec, e.g. ``r"|L{5.5cm}|p{9.6cm}|"``.
    caption : str, optional
        Caption text (LaTeX). Omit for an uncaptioned table.
    header : str, optional
        One header row *without* the trailing ``\\\\``, e.g.
        ``r"\\textbf{Parameter} & \\textbf{Value}"``.
    header_rows : str, optional
        Raw multi-row header block (rows already terminated with ``\\\\`` and
        separated by ``\\hline``) for complex headers using ``\\multirow``.
    label : str, optional
        ``\\label`` key for cross-referencing.
    tabcolsep : str, optional
        Local ``\\tabcolsep`` if the caller overrides it (used for auto-fit).

    Close the table with ``\\end{longtable}`` as usual.
    """
    from osdagbridge.core.reports.styles import TABLE, col_count, fit_colspec

    colspec = fit_colspec(colspec, tabcolsep)
    n = col_count(colspec)
    if header_rows is not None:
        head = "\\hline\n" + header_rows.strip() + "\n\\hline\n"
    elif header is not None:
        head = ("\\hline\n\\rowcolor{osTableHeader}\n" + header.strip()
                + " \\\\\n\\hline\n")
    else:
        head = "\\hline\n"

    if caption:
        lbl = ("\\label{" + label + "}") if label else ""
        first_cap = "\\caption{" + caption + "}" + lbl + "\\\\\n"
        cont_cap = ("\\caption[]{" + caption + " " + TABLE["continued_cap"] + "}\\\\\n")
    else:
        first_cap = cont_cap = ""

    return (
        "\\begin{longtable}{" + colspec + "}\n"
        + first_cap + head + "\\endfirsthead\n"
        + cont_cap + head + "\\endhead\n"
        + "\\multicolumn{" + str(n) + "}{r}{\\footnotesize " + TABLE["continued_text"]
        + "} \\\\\n\\endfoot\n"
        + "\\endlastfoot\n"
    )


def _num(value, nd=3):
    """Format floats compactly (``12.149999999999999`` -> ``12.15``); pass others through."""
    if isinstance(value, float):
        s = f"{value:.{nd}f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    return value
