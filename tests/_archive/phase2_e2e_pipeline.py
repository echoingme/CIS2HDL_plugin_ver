"""Phase II End-to-End Pipeline Test with real RTL8367RB DSN file.

Tests the full 6-stage conversion pipeline.
"""
import sys
sys.path.insert(0, r"D:\26暑假\cis2hdl")

from pathlib import Path
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.diagnostics.report_gen import StructuredReportGenerator
import tempfile, shutil

results = []
errors = []

def check(name, condition, detail=""):
    if condition:
        results.append(f"  ✅ {name}: {detail}" if detail else f"  ✅ {name}")
        return True
    else:
        msg = f"  ❌ {name}: {detail}" if detail else f"  ❌ {name}"
        results.append(msg)
        errors.append(msg)
        return False

print("=" * 70)
print("PHASE II END-TO-END PIPELINE TEST")
print("=" * 70)

engine = ConversionEngine()
dsn = Path(r"D:\26暑假\cis2hdl\tests\fixtures\RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN")
check("DSN fixture exists", dsn.exists(), str(dsn))

edf = Path(r"D:\26暑假\cis2hdl\tests\fixtures\RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF")
check("EDF fixture exists", edf.exists(), str(edf))

# Collect progress callbacks
stages = []
def progress_cb(stage, pct, msg):
    stages.append(f"[{stage}] {pct}%: {msg}")

out = Path(tempfile.mkdtemp(prefix="cis2hdl_e2e_"))
print(f"\nOutput dir: {out}")

try:
    report = engine.convert(dsn, out, progress_callback=progress_cb)

    print(f"\n=== Pipeline Results ===")
    print(f"Project: {report.project_name}")
    print(f"Pages: {report.pages}, Instances: {report.instances}, Nets: {report.nets}")
    
    check("project_name not empty", bool(report.project_name), report.project_name)
    check("pages > 0", report.pages > 0, f"pages={report.pages}")
    check("instances > 0", report.instances > 0, f"instances={report.instances}")
    check("nets > 0", report.nets > 0, f"nets={report.nets}")
    
    # Stage execution
    stage_pcts = [s for s in stages if '%' in s]
    print(f"Stages executed: {len(stage_pcts)}")
    for s in stages:
        if '%' in s:
            print(f"  {s}")
    check("stages executed > 0", len(stage_pcts) > 0, f"{len(stage_pcts)} stages")
    
    # Output files
    output_files = report.output_files if hasattr(report, 'output_files') else []
    print(f"\nOutput files: {len(output_files)}")
    for f in sorted(output_files):
        print(f"  {f}")
    
    # Errors and warnings
    err_count = len(report.errors) if hasattr(report, 'errors') else 0
    warn_count = len(report.warnings) if hasattr(report, 'warnings') else 0
    print(f"\nErrors: {err_count}, Warnings: {warn_count}")
    for e in report.errors if hasattr(report, 'errors') else []:
        print(f"  ⚠️ Error: {e}")
    
    # Quality metrics
    if hasattr(report, 'quality') and report.quality:
        q = report.quality
        print(f"\nQuality Scores:")
        for key in ['logic_score', 'coordinate_score', 'match_score', 'symbol_score']:
            if hasattr(q, key):
                print(f"  {key}: {getattr(q, key):.1%}")
        
        if hasattr(q, 'logic_score'):
            check("quality.logic_score in [0,1]", 0 <= q.logic_score <= 1)

    # Match results
    if hasattr(report, 'match_results'):
        print(f"\nMatched: {len(report.match_results)} components")
        matched_count = sum(1 for m in report.match_results if hasattr(m, 'status') and m.status == 'exact')
        print(f"  Exact matches: {matched_count}")
    
    # ── Report Generation ─────────────────────────────────
    print(f"\n=== Report Generation ===")
    gen = StructuredReportGenerator()
    
    json_str = gen.generate_json(report)
    json_path = out / "report.json"
    json_path.write_text(json_str, encoding="utf-8")
    check("JSON report generated", len(json_str) > 100, f"{len(json_str)} bytes")
    
    html_str = gen.generate_html(report)
    html_path = out / "report.html"
    html_path.write_text(html_str, encoding="utf-8")
    check("HTML report generated", len(html_str) > 500, f"{len(html_str)} bytes")
    check("HTML has DOCTYPE", "<!DOCTYPE html>" in html_str)
    check("HTML has body", "<body" in html_str)
    
    print(f"\nReport files:")
    print(f"  JSON: {json_path} ({len(json_str)} bytes)")
    print(f"  HTML: {html_path} ({len(html_str)} bytes)")
    
except Exception as e:
    import traceback
    errors.append(f"E2E Pipeline: {e}")
    print(f"\n❌ Pipeline failed: {e}")
    traceback.print_exc()
finally:
    # Keep output for inspection this run
    pass

# ── SUMMARY ──────────────────────────────────────────────
print("\n" + "=" * 70)
print("E2E PIPELINE SUMMARY")
print("=" * 70)
for r in results:
    print(r)

print(f"\nErrors: {len(errors)}")
if errors:
    print("ERROR DETAILS:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n=== E2E PIPELINE TEST PASSED ===")
    sys.exit(0)
