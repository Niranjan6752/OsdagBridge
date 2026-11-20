"""Regenerate the OsdagBridge PDF report without clicking through the GUI.

Usage
-----
1. Capture a real payload once from the GUI (Design -> Generate Report) by
   running the desktop app with:

       OSDAG_DUMP_PAYLOAD=/tmp/osdag_payload.pkl python -m osdagbridge.desktop

   generate_report() then pickles the payload and request it receives.

2. Rebuild the report from that snapshot as often as needed:

       python scripts/regen_report.py /tmp/osdag_payload.pkl -o out/

   Run with no pickle argument to build a smoke-test report from empty
   inputs. That checks only that the LaTeX compiles; it contains no real
   design values.
"""
from __future__ import annotations

import argparse
import copy
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from osdagbridge.core.reports.report_generator import (  # noqa: E402
    ReportMetadata, ReportOptions, ReportRequest, build_report_payload, generate_report,
)

ALL_SECTIONS = ["loads", "analysis", "design_checks", "drawings"]


def _smoke_request(out_dir: str, stem: str) -> ReportRequest:
    md = ReportMetadata(project_name="Smoke Test", project_location="", designer="-",
                        client="-", company="-", job_number="J-0", report_date="")
    opts = ReportOptions(sections=ALL_SECTIONS, include_figures=True,
                         include_toc=True, include_pdf=True)
    return ReportRequest(metadata=md, options=opts, output_dir=out_dir, file_stem=stem)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pickle", nargs="?", help="payload pickle written via OSDAG_DUMP_PAYLOAD")
    ap.add_argument("-o", "--out", default="report_out", help="output directory")
    ap.add_argument("-n", "--name", default="Report_After", help="output file stem")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    if args.pickle:
        with open(args.pickle, "rb") as fh:
            snap = pickle.load(fh)
        payload, request = copy.deepcopy(snap["payload"]), snap["request"]
        request.output_dir, request.file_stem = out_dir, args.name
    else:
        request = _smoke_request(out_dir, args.name)
        payload = build_report_payload(request, {}, {})

    res = generate_report(payload, request)
    print("PDF:", res.pdf_path)
    print("TEX:", res.tex_path)
    return 0 if res.pdf_path else 1


if __name__ == "__main__":
    raise SystemExit(main())
