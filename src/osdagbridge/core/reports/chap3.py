# =============================================================================
# Chapter 3: Loads and Load Combinations
# Extracted from report_generator.py — DO NOT add business logic here.
# =============================================================================

from osdagbridge.core.utils.common import (
    KEY_CB_LOAD,
    KEY_LL_CUSTOM_VEHICLES,
    KEY_LL_FOOTPATH_PRESSURE_MODE,
    KEY_LL_FOOTPATH_PRESSURE_VALUE,
    KEY_LL_IRC_70R_BOGIE,
    KEY_LL_IRC_70R_TRACKED,
    KEY_LL_IRC_70R_WHEELED,
    KEY_LL_IRC_AA_TRACKED,
    KEY_LL_IRC_AA_WHEELED,
    KEY_LL_IRC_CLASS_A,
    KEY_LL_IRC_CLASS_FATIGUE,
    KEY_LL_IRC_CLASS_SV,
    KEY_MATERIAL_DECK_DENSITY,
    KEY_MATERIAL_GIRDER_DENSITY,
    KEY_PL_SELF_WEIGHT_FACTOR,
    KEY_RL_LOAD_VALUE,
    KEY_SL_DAMPING,
    KEY_SL_DEAD_LOAD_MODE,
    KEY_SL_DEAD_LOAD_VALUE,
    KEY_SL_HORIZONTAL_COEFF,
    KEY_SL_IMPORTANCE_FACTOR,
    KEY_SL_LIVE_LOAD_MODE,
    KEY_SL_LIVE_LOAD_VALUE,
    KEY_SL_SEISMIC_ZONE,
    KEY_SL_SOIL_TYPE,
    KEY_SL_SPECTRAL_COEFF,
    KEY_SL_TIME_PERIOD,
    KEY_SL_VERTICAL_COEFF,
    KEY_SL_ZONE_FACTOR,
    KEY_SPAN,
    KEY_TL_BRIDGE_TEMP_MAX,
    KEY_TL_BRIDGE_TEMP_MIN,
    KEY_TL_HIGHEST_MAX_TEMP,
    KEY_TL_LOWEST_MIN_TEMP,
    KEY_TL_TEMP_FALL,
    KEY_TL_TEMP_RISE,
    KEY_WC_LD_LANE_TABLE_COUNT,
    KEY_FOOTPATH,
    KEY_TS_FOOTPATH_WIDTH,
    KEY_WC_MATERIAL,
    KEY_WC_THICKNESS,
    KEY_WL_AVG_EXPOSED_HEIGHT,
    KEY_WL_BASIC_WIND_SPEED,
    KEY_WL_HOURLY_MEAN_WIND,
    KEY_WL_HOURLY_WIND_PRESSURE,
    KEY_WL_LONGITUDINAL_WIND_FORCE,
    KEY_WL_TERRAIN_TYPE,
    KEY_WL_TRANSVERSE_WIND_FORCE,
    KEY_WL_VERTICAL_WIND_FORCE
)

from osdagbridge.core.reports.report_utils import _tex, _render_value, lt_open
from osdagbridge.core.reports.styles import COLS, ROW
from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017


# ── Live-load tables (vehicular + footway) ───────────────────────────────────
G = 9.81  # kN per tonne

# (input key, display name, impact-factor clause)
# (input key, display name, impact rule)
#   "208.2"   Class A / B rule        9 / (13.5 + L)
#   "208.3W"  wheeled AA / 70R rule   25 % below 23 m span, else 9 / (13.5 + L)
#   "208.3T"  tracked AA / 70R rule   25 % below 5 m, 10 % from 5 m to 45 m
#   "208.3"   value used by the analysis (OsdagBridge's cl_208_3_impact_factor)
_IRC_VEHICLES = [
    (KEY_LL_IRC_CLASS_A,       "IRC Class A",             "208.2"),
    (KEY_LL_IRC_70R_WHEELED,   "IRC Class 70R (Wheeled)", "208.3W"),
    (KEY_LL_IRC_70R_TRACKED,   "IRC Class 70R (Tracked)", "208.3T"),
    (KEY_LL_IRC_70R_BOGIE,     "IRC Class 70R (Bogie)",   "208.3W"),
    (KEY_LL_IRC_AA_WHEELED,    "IRC Class AA (Wheeled)",  "208.3W"),
    (KEY_LL_IRC_AA_TRACKED,    "IRC Class AA (Tracked)",  "208.3T"),
    (KEY_LL_IRC_CLASS_SV,      "Special Vehicle (SV)",    "208.3"),
    (KEY_LL_IRC_CLASS_FATIGUE, "Fatigue Vehicle",         "208.3"),
]


def _gross_load_kN(key):
    """Gross vehicle load (kN) from the IRC:6 vehicle definitions; None if unknown."""
    from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017 as I
    try:
        if key == KEY_LL_IRC_CLASS_A:
            return sum(I.cl_204_1_ClassA_vehicle()["wheel_loads"]) / 1000.0
        if key in (KEY_LL_IRC_70R_WHEELED, KEY_LL_IRC_70R_BOGIE):
            return sum(I.cl_204_1_Class70R_vehicle_wheel()["wheel_loads"]) / 1000.0
        if key == KEY_LL_IRC_70R_TRACKED:
            v = I.cl_204_1_Class70R_vehicle_track()
            return 2 * v["wheel_loads_udl"] * (v["x"][-1] - v["x"][0]) / 1000.0
        if key == KEY_LL_IRC_AA_TRACKED:
            return 70 * G            # IRC:6 Cl. 204.1, Class AA tracked: 70 t
        if key == KEY_LL_IRC_AA_WHEELED:
            return 40 * G            # IRC:6 Cl. 204.1, Class AA wheeled: 40 t
        if key == KEY_LL_IRC_CLASS_SV:
            return float(I.cl_204_5_1_special_vehicle()["total_load_kN"])
        if key == KEY_LL_IRC_CLASS_FATIGUE:
            return sum(I.cl_204_6_fatigue_load()["wheel_loads"]) / 1000.0
    except Exception:
        return None
    return None


def _impact_factor(rule, span_m):
    """1 + IM for one vehicle (IRC:6-2017 Cl. 208.2 / 208.3).

    Cl. 208.3 distinguishes wheeled and tracked vehicles. The shared
    ``IRC6_2017.cl_208_3_impact_factor`` picks the branch from a module
    constant rather than the vehicle, so the report applies the clause
    per vehicle here.
    """
    from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017 as I
    L = min(span_m, 45.0)
    try:
        if rule == "208.2":
            im = I.cl_208_2_impact_factor(span_m)
        elif rule == "208.3W":
            im = 0.25 if L < 23.0 else 9.0 / (13.5 + L)
        elif rule == "208.3T":
            im = 0.25 if L < 5.0 else 0.10
        else:
            im = I.cl_208_3_impact_factor(span_m)
        return 1.0 + round(im, 3)
    except Exception:
        return None


def _wind_force_rows(input_dict):
    """Wind force rows, only for forces the analysis actually stored (no blank cells)."""
    rows = []
    for label, key in (("Transverse Wind Force", KEY_WL_TRANSVERSE_WIND_FORCE),
                       ("Longitudinal Wind Force", KEY_WL_LONGITUDINAL_WIND_FORCE),
                       ("Vertical Wind Force", KEY_WL_VERTICAL_WIND_FORCE)):
        val = _render_value(input_dict, key, " kN")
        if val:
            rows.append("\\textnormal{" + label + "} & " + val + " " + ROW + "\n\\hline\n")
    return "".join(rows)


def _fmt(v, nd=2):
    return "---" if v is None else f"{v:,.{nd}f}"


def selected_vehicles(input_dict):
    """Vehicles ticked in Additional Inputs -> Loading, plus custom vehicles.

    Returns a list of (name, gross_kN or None, clause or None).
    """
    out = [(name, _gross_load_kN(key), clause)
           for key, name, clause in _IRC_VEHICLES if input_dict.get(key)]
    custom = input_dict.get(KEY_LL_CUSTOM_VEHICLES)
    if isinstance(custom, list):
        for c in custom:
            name = c.get("name") if isinstance(c, dict) else c if isinstance(c, str) else None
            if not name:
                continue
            gross = None
            if isinstance(c, dict):
                loads = c.get("axle_loads") or c.get("loads") or c.get("wheel_loads")
                try:
                    gross = float(sum(float(x) for x in loads)) if loads else None
                except (TypeError, ValueError):
                    gross = None
            out.append((str(name) + " (Custom)", gross, "208.2"))
    return out


def vehicular_live_load_table(input_dict, braking_total_str):
    """Table: one row per selected vehicle with impact, braking and centrifugal effects."""
    try:
        span_m = float(input_dict.get(KEY_SPAN))
    except (TypeError, ValueError):
        span_m = None

    rows = []
    for name, gross, clause in selected_vehicles(input_dict):
        ifac = _impact_factor(clause, span_m) if (span_m and clause) else None
        braking = 0.20 * gross if gross is not None else None   # Cl. 211.2: 20 % of train load
        rows.append(
            _tex(name) + " & " + _fmt(gross, 1) + " & " + _fmt(ifac, 3)
            + " & " + (("Cl. " + clause.rstrip("WT")) if clause else "---")
            + " & " + _fmt(braking, 1) + r" & N.A.$^{\dagger}$ " + ROW + "\n\\hline"
        )
    if not rows:
        rows.append(r"\multicolumn{6}{|c|}{\textit{No vehicle selected in Additional Inputs $\rightarrow$ Loading}} " + ROW + "\n\\hline")

    spec = r"|L{3.4cm}|C{1.9cm}|C{1.9cm}|C{1.7cm}|C{2.0cm}|C{2.1cm}|"
    header = (r"\textbf{Vehicle Class} & \textbf{Gross Load (kN)} & \textbf{Impact Factor (1+IM)}"
              r" & \textbf{IRC:6 Clause} & \textbf{Braking, 20\%W (kN)} & \textbf{Centrifugal (kN)}")
    span_note = (f"span $L$ = {span_m:g} m" if span_m else "span not available")
    # Governing braking force across all design lanes: only when the lane data exists.
    governing = ""
    if braking_total_str and braking_total_str not in ("N/A", "N.A."):
        governing = (r"\multicolumn{4}{|l|}{\textbf{Governing braking force, all design lanes}}"
                     r" & \multicolumn{2}{c|}{\textbf{" + _tex(braking_total_str) + "}} " + ROW + "\n\\hline\n")
    return (
        lt_open(spec, r"\textbf{Vehicular Live Load (LL)}", header, label="tab:vehicular-ll")
        + "\n".join(rows) + "\n"
        + governing
        + "\\end{longtable}\n"
        + r"\noindent{\footnotesize\textit{Impact factor per IRC:6 Cl. 208 for "
        + span_note + r". Braking per vehicle = 20\% of gross load (Cl. 211.2, first train in one lane); "
        r"the governing value for multiple lanes, where shown, follows Cl. 211.2. "
        r"$^{\dagger}$Centrifugal force (Cl. 212) applies to curved bridges only; this bridge is straight in plan.}}"
        + "\n\n\\vspace{0.8em}\n"
    )


def footway_live_load_table(input_dict, fp_str):
    """Table: footway (pedestrian) live load; a one-line note when there is no footpath."""
    fp_cfg = str(input_dict.get(KEY_FOOTPATH, "None") or "None").strip()
    if fp_cfg in ("None", "", "No"):
        return (r"\noindent\textit{No footpath is provided, so footway live load (IRC:6 Cl. 206.1) is not applicable.}"
                "\n\n\\vspace{0.8em}\n")
    mode = str(input_dict.get(KEY_LL_FOOTPATH_PRESSURE_MODE, "") or "---")
    spec = r"|L{5.0cm}|C{4.2cm}|C{2.0cm}|L{3.0cm}|"
    header = r"\textbf{Parameter} & \textbf{Value} & \textbf{Unit} & \textbf{Reference}"
    rows = [
        ("Footpath Provided", _tex(fp_cfg), "---", "Basic Inputs"),
        ("Footpath Width", _render_value(input_dict, KEY_TS_FOOTPATH_WIDTH), "m", "Typical Section"),
        ("Pressure Input Mode", _tex(mode), "---", "Loading Tab"),
        ("Footway Live Load Intensity",
         _tex(fp_str.split(" kN")[0]) if fp_str and fp_str != "N/A" else "N/A",
         r"kN/m\textsuperscript{2}", "IRC:6 Cl. 206.1"),
    ]
    body = "\n".join(f"{a} & {b} & {c} & {d} " + ROW + "\n\\hline" for a, b, c, d in rows)
    return (lt_open(spec, r"\textbf{Footway Live Load (Pedestrian)}", header, label="tab:footway-ll")
            + body + "\n\\end{longtable}\n\n\\vspace{0.8em}\n")

def ch3_loads(input_dict):
    lanes = input_dict.get(KEY_WC_LD_LANE_TABLE_COUNT)
    braking_force_str = ""
    if lanes not in (None, ""):
        try:
            lanes_int = int(lanes)
            braking_force_t = IRC6_2017.cl_211_2_braking_force(lanes_int)
            braking_force_kN = braking_force_t * 9.81
            braking_force_str = f"{braking_force_kN:.2f} kN ({braking_force_t:.2f} tonnes)"
        except Exception:
            braking_force_str = "N/A"
    else:
        braking_force_str = "N/A"

    fp_mode  = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_MODE, "")
    fp_value = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_VALUE, "")
    if str(fp_mode).strip().lower() in ("as per irc 6", "as per irc6", "automatic"):
        try:
            fp_str = f"{IRC6_2017.cl_206_1_footway_load():.3f} kN/m² (IRC 6 Cl. 206.1)"
        except Exception:
            fp_str = "N/A"
    elif fp_value not in (None, ""):
        fp_str = f"{fp_value} kN/m²"
    else:
        fp_str = "N/A"

    # Vz / Pz — prefer stored computed values; fall back to IRC6 Table 12
    vz_val = input_dict.get(KEY_WL_HOURLY_MEAN_WIND)
    pz_val = input_dict.get(KEY_WL_HOURLY_WIND_PRESSURE)
    if not vz_val or not pz_val:
        try:
            _vb  = input_dict.get(KEY_WL_BASIC_WIND_SPEED) or input_dict.get('wind_speed')
            _h   = input_dict.get(KEY_WL_AVG_EXPOSED_HEIGHT)
            _ter = {
                "Plain Terrain": "plain",
                "Terrain with Obstructions": "obstructed",
            }.get(str(input_dict.get(KEY_WL_TERRAIN_TYPE, "")).strip(), "plain")
            _res = IRC6_2017.table_12(float(_h), _ter, float(_vb))
            if not vz_val:
                vz_val = _res.get("Vz")
            if not pz_val:
                pz_val = _res.get("Pz")
        except Exception:
            pass
    vz_str = f"{float(vz_val):.2f} m/s" if vz_val not in (None, "") else "N/A"
    pz_str = f"{float(pz_val):.2f} N/m²" if pz_val not in (None, "") else "N/A"

    # Table 3.5 — Seismic: prefer stored computed values; fall back to IRC6 cl_218_5_1
    sl_zone_factor = input_dict.get(KEY_SL_ZONE_FACTOR)
    sl_spectral    = input_dict.get(KEY_SL_SPECTRAL_COEFF)
    sl_ah          = input_dict.get(KEY_SL_HORIZONTAL_COEFF)
    sl_av          = input_dict.get(KEY_SL_VERTICAL_COEFF)
    if not sl_ah or not sl_zone_factor:
        try:
            _zone = input_dict.get(KEY_SL_SEISMIC_ZONE) or input_dict.get('seismic_zone')
            _zmap = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
            _z    = str(_zone).strip().upper()
            if _z.isdigit():
                _z = _zmap.get(_z)
            _smap = {"Type I – Rocky or Hard": 1, "Type II – Medium Soil": 2, "Type III – Soft Soil": 3}
            _st   = _smap.get(str(input_dict.get(KEY_SL_SOIL_TYPE, "")), 1)
            _tp   = input_dict.get(KEY_SL_TIME_PERIOD)
            _damp = input_dict.get(KEY_SL_DAMPING) or "5"
            _dl_v = input_dict.get(KEY_SL_DEAD_LOAD_VALUE)
            _ll_v = input_dict.get(KEY_SL_LIVE_LOAD_VALUE)
            _dead = float(_dl_v) if str(input_dict.get(KEY_SL_DEAD_LOAD_MODE, "")) == "Custom" and _dl_v else 0.0
            _live = float(_ll_v) if str(input_dict.get(KEY_SL_LIVE_LOAD_MODE, "")) == "Custom" and _ll_v else 0.0
            _res  = IRC6_2017.cl_218_5_1(zone=f"Zone {_z}", soil_type=_st, dead_load_kN=_dead,
                        live_load_kN=_live, period_T=float(_tp) if _tp else None,
                        damping_percent=float(_damp))
            if not sl_zone_factor:
                sl_zone_factor = _res.get("Z")
            if not sl_spectral:
                sl_spectral    = _res.get("Sa_g_adjusted")
            if not sl_ah:
                sl_ah          = _res.get("Ah")
            if not sl_av:
                sl_av          = round(_res.get("Ah", 0) * 2 / 3, 4)
        except Exception:
            pass

    def _sl(v, unit=""):
        return f"{float(v):.4f}{unit}" if v not in (None, "") else "N/A"

    # Table 3.6 — Temperature: compute effective bridge temp range from shade temps
    tl_temp_min = tl_temp_max = tl_rise = tl_fall = "N/A"
    try:
        _tmax = input_dict.get(KEY_TL_HIGHEST_MAX_TEMP) or input_dict.get('shade_temp_max')
        _tmin = input_dict.get(KEY_TL_LOWEST_MIN_TEMP)  or input_dict.get('shade_temp_min')
        if _tmax and _tmin:
            _res    = IRC6_2017.cl_215_2_effective_bridge_temperature(
                          float(_tmax), float(_tmin), 'metallic', False)
            _bt_min = _res.get('T_min', 0)
            _bt_max = _res.get('T_max', 0)
            _mean   = (_bt_max + _bt_min) / 2.0
            tl_temp_min = f"{_bt_min:.2f}"
            tl_temp_max = f"{_bt_max:.2f}"
            tl_rise     = f"{_bt_max - _mean:.2f}"
            tl_fall     = f"{_mean - _bt_min:.2f}"
    except Exception:
        pass

    # --- Table 3.7: Load Combinations (dynamically generated from IRC 6) ---
    _LOAD_LABEL_MAP = {
        'dead_load':         'DL',
        'surfacing':         'SIDL',
        'live_load':         'LL',
        'wind_load':         'WL',
        'thermal_load':      'TL',
        'vehicle_collision': 'VC',
        'barge_impact':      'BI',
        'floating_bodies':   'FB',
        'seismic':           'EQ',
    }

    def _fmt_factors(factors):
        """Format a factors dict into a compact load-case string for the table."""
        parts = []
        for load, val in factors.items():
            label = _LOAD_LABEL_MAP.get(load, load.upper())
            if isinstance(val, dict):  # permanent load with adding/relieving
                add = val.get('adding')
                rel = val.get('relieving')
                add_s = f"{add:.2f}" if add is not None else '--'
                rel_s = f"{rel:.2f}" if rel is not None else '--'
                parts.append(f"{label}({add_s}/{rel_s})")
            else:
                if val is None:
                    continue  # skip N/A factors
                parts.append(f"{label}({val:.2f})")
        return ' + '.join(parts)

    uls_combos = IRC6_2017.uls_load_combinations()
    sls_combos = IRC6_2017.sls_load_combinations()
    lc_rows = []
    for i, combo in enumerate(uls_combos, start=1):
        cases = _fmt_factors(combo['factors'])
        lc_rows.append(
            f"ULS-{i:02d}" + r" & " + cases + r" \osrow{}" + "\n"
            + r"\hline"
        )
    for i, combo in enumerate(sls_combos, start=1):
        cases = _fmt_factors(combo['factors'])
        lc_rows.append(
            f"SLS-{i:02d}" + r" & " + cases + r" \osrow{}" + "\n"
            + r"\hline"
        )

    lc_rows_str = "\n".join(lc_rows)

    return r"""
\chapter{Loads and Load Combinations}

This section summarizes all loads applied to the bridge and the load combinations considered for analysis and design.

\vspace{1em}
""" + lt_open(COLS["param_value"], r"\textbf{Dead Load -- Self Weight}", r"\textbf{Parameter} & \textbf{Value}") + r"""
\textnormal{Steel Self-Weight Applied} & """ + (_render_value(input_dict, KEY_MATERIAL_GIRDER_DENSITY, ' kN/m\\textsuperscript{3}')) + r""" \osrow{}
\hline
\textnormal{Concrete Deck Weight} & """ + (_render_value(input_dict, KEY_MATERIAL_DECK_DENSITY, ' kN/m\\textsuperscript{3}')) + r""" \osrow{}
\hline
\textnormal{Self-Weight Factor} & """ + (_render_value(input_dict, KEY_PL_SELF_WEIGHT_FACTOR)) + r""" \osrow{}
\hline
\end{longtable}

\vspace{1em}
""" + lt_open(COLS["param_value"], r"\textbf{Dead Load for Surfacing (DW)}", r"\textbf{Parameter} & \textbf{Value}") + r"""
\textnormal{Wearing Course Load} & """ + (_render_value(input_dict, KEY_WC_MATERIAL)) + r""" x """ + (_render_value(input_dict, KEY_WC_THICKNESS)) + r""" \osrow{}
\hline
\textnormal{Additional SIDL (Crash Barrier)} & """ + (_render_value(input_dict, KEY_CB_LOAD)) + r""" kN/m per barrier \osrow{}
\hline
\textnormal{Railing Load} & """ + (_render_value(input_dict, KEY_RL_LOAD_VALUE)) + r""" kN/m\sdstar{} \osrow{}
\hline
\end{longtable}

\vspace{1em}
""" + vehicular_live_load_table(input_dict, braking_force_str) + footway_live_load_table(input_dict, fp_str) + r"""

\vspace{1em}
""" + lt_open(COLS["param_value"], r"\textbf{Wind Load (WL) --- per IRC 6}", r"\textbf{Parameter} & \textbf{Value}") + r"""
\textnormal{Basic Wind Speed, Vb} & """ + (_render_value(input_dict,'wind_speed', ' m/s')) + r""" [from Project Location] \osrow{}
\hline
\textnormal{Terrain Type} & """ + (_render_value(input_dict, KEY_WL_TERRAIN_TYPE)) + r""" \osrow{}
\hline
\textnormal{Average Exposed Height, H (m)} & """ + (_render_value(input_dict, KEY_WL_AVG_EXPOSED_HEIGHT, ' m')) + r""" \osrow{}
\hline
\textnormal{Hourly Mean Wind Speed, Vz} & """ + _tex(vz_str) + r""" (IRC:6 Table 12) \osrow{}
\hline
\textnormal{Hourly Wind Pressure, Pz} & """ + _tex(pz_str) + r""" (IRC:6 Table 12) \osrow{}
\hline
""" + _wind_force_rows(input_dict) + r"""\end{longtable}

\vspace{1em}
""" + lt_open(COLS["param_value"], r"\textbf{Earthquake Load (EL) --- per IRC 6}", r"\textbf{Parameter} & \textbf{Value}") + r"""
\textnormal{Seismic Zone} & """ + (_render_value(input_dict,'seismic_zone')) + r""" [from Project Location] \osrow{}
\hline
\textnormal{Zone Factor, Z} & """ + (_render_value(input_dict, KEY_SL_ZONE_FACTOR)) + r""" \osrow{}
\hline
\textnormal{Importance Factor, I} & """ + (_render_value(input_dict, KEY_SL_IMPORTANCE_FACTOR)) + r""" \osrow{}
\hline
\textnormal{Type of Soil} & """ + (_render_value(input_dict, KEY_SL_SOIL_TYPE)) + r""" \osrow{}
\hline
\textnormal{Sa/g} & """ + (_render_value(input_dict, KEY_SL_SPECTRAL_COEFF)) + r""" \osrow{}
\hline
\textnormal{Horizontal Seismic Coefficient, Ah} & """ + (_render_value(input_dict, KEY_SL_HORIZONTAL_COEFF)) + r""" \osrow{}
\hline
\textnormal{Vertical Seismic Coefficient, Av} & """ + (_render_value(input_dict, KEY_SL_VERTICAL_COEFF)) + r""" \osrow{}
\hline
\textnormal{Horizontal Seismic Force (longitudinal)} & """ + '' + r""" kN \osrow{}
\hline
\textnormal{Horizontal Seismic Force (transverse)} & """ + '' + r""" kN \osrow{}
\hline
\end{longtable}

\vspace{1em}
""" + lt_open(COLS["param_value"], r"\textbf{Temperature Load (TL) --- per IRC 6}", r"\textbf{Parameter} & \textbf{Value}") + r"""
\textnormal{Maximum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_max')) + r""" $^\circ$C \osrow{}
\hline
\textnormal{Minimum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_min')) + r""" $^\circ$C \osrow{}
\hline
\textnormal{Effective Bridge Temp. Range} & """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MIN)) + r""" to """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MAX)) + r""" $^\circ$C \osrow{}
\hline
\textnormal{Temperature Rise / Fall for Design} & +""" + (_render_value(input_dict, KEY_TL_TEMP_RISE)) + r""" $^\circ$C / \textminus{}""" + (_render_value(input_dict, KEY_TL_TEMP_FALL)) + r""" $^\circ$C \osrow{}
\hline
\end{longtable}

\vspace{1em}
""" + lt_open(r"|C{4.0cm}|p{11.5cm}|", r"\textbf{Load Combinations}", r"\textbf{Combination ID} & \textbf{Load Cases}") + r"""
""" + lc_rows_str + r"""
\end{longtable}

\noindent\textit{Note: All IRC 6 load combinations are auto-generated by OsdagBridge. User-defined custom combinations, if any, are appended.}
"""


