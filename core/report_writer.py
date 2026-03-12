"""Write measurement results to JSON, CSV, and HTML report."""

from __future__ import annotations

import csv
import html
import json
import os
import subprocess
from datetime import datetime, timezone

from core.benchmark import RowComparison
from core.logger import get_logger
from core.metrics import MeasurementResult

logger = get_logger(__name__)

__all__ = [
    "write_benchmark_diff_csv",
    "write_benchmark_diff_json",
    "write_console_errors",
    "write_csv",
    "write_detailed_metrics_report",
    "write_html_report",
    "write_json",
    "write_markdown_report",
]

REPORTS_BASE = "reports"
BASE_URL = "https://app.preprod.fordefi.com"

_cached_default_run_dir: str | None = None


def _run_folder_timestamp() -> str:
    """Human-readable timestamp for report folder names (e.g. 2025-03-12_14-30-22)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def _default_run_dir() -> str:
    """Return a timestamped run directory under reports/ (cached per process)."""
    global _cached_default_run_dir
    if _cached_default_run_dir is not None:
        return _cached_default_run_dir
    _cached_default_run_dir = os.path.join(REPORTS_BASE, _run_folder_timestamp())
    os.makedirs(_cached_default_run_dir, exist_ok=True)
    return _cached_default_run_dir


def _output_base(run_dir: str | None) -> str:
    """Base directory for this run; uses run_dir or a default timestamped dir."""
    return run_dir if run_dir is not None else _default_run_dir()


def _run_subdir(base: str, subdir: str) -> str:
    """Return path for a subdir under the run base and ensure it exists."""
    out_dir = os.path.join(base, subdir)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _resolve_output_path(
    path: str | None,
    out_dir: str,
    default_filename: str,
    run_dir: str | None,
) -> str:
    """Resolve output file path: explicit path, run-dir default, or timestamped filename."""
    if path is not None:
        return path
    if run_dir is not None:
        return os.path.join(out_dir, default_filename)
    return os.path.join(out_dir, f"{_ts_prefix()}_{default_filename}")


def _report_file_path(base: str, filename: str, report_path: str | None) -> str:
    """Path for a report file in the run base, or an explicit report_path."""
    if report_path is not None:
        return report_path
    return os.path.join(base, filename)


# Page order for Performance Summary and Deep Dive (template order).
PERFORMANCE_SUMMARY_PAGES = [
    "Vaults",
    "Assets",
    "Connected Accounts",
    "Transactions",
    "Allowances",
    "Address Book",
    "Transaction Policy",
    "AML Policy",
    "User Management",
    "Settings",
    "Login",
]
DEEP_DIVE_PAGES = ["Vaults", "Transactions", "Assets", "Transaction Policy"]


def _get_git_version() -> str:
    """Return current git commit (short) or tag if available."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "—"


def _ts_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(
    results: list[MeasurementResult],
    path: str | None = None,
    run_dir: str | None = None,
) -> str:
    """Serialize results to JSON. Returns the file path."""
    base = _output_base(run_dir)
    out_dir = _run_subdir(base, "json")
    out_path = _resolve_output_path(path, out_dir, "results.json", run_dir)
    data = [r.to_dict() for r in results]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("JSON results written to %s", out_path)
    return out_path


def _build_detailed_metrics_html(
    results: list[MeasurementResult],
    iterations: int | None = None,
    warmup: int | None = None,
) -> str:
    """Build HTML for detailed metrics report (tables per page/action)."""
    exec_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    iter_str = str(iterations) if iterations is not None else "—"
    warmup_str = str(warmup) if warmup is not None else "—"
    run_config_p = (
        f"<p><strong>Run config:</strong> iterations = {_h(iter_str)}, warmup = {_h(warmup_str)}"
        + (f" (measured runs = {iterations - warmup})" if (iterations is not None and warmup is not None) else "")
        + "</p>"
    )
    sections: list[str] = []
    for r in results:
        rows: list[str] = []
        for m in r._all_metrics():
            d = m.to_dict()
            rows.append(
                f"<tr><td>{_h(d['name'])}</td><td>{d['sample_count']}</td>"
                f"<td>{d['median_ms']}</td><td>{d['p95_ms']}</td><td>{d['p99_ms']}</td>"
                f"<td>{d['std_dev_ms']}</td><td>{d['min_ms']}</td><td>{d['max_ms']}</td></tr>"
            )
        table_body = "\n".join(rows)
        sections.append(
            f"<h3>{_h(r.page_name)} — {_h(r.action)}</h3>\n"
            f"<p>Console errors: {r.console_error_count}</p>\n"
            "<table>\n"
            "<thead><tr><th>Metric</th><th>sample_count</th><th>median_ms</th>"
            "<th>p95_ms</th><th>p99_ms</th><th>std_dev_ms</th><th>min_ms</th><th>max_ms</th></tr></thead>\n"
            f"<tbody>\n{table_body}\n</tbody>\n"
            "</table>"
        )
    body_sections = "\n<hr>\n\n".join(sections)
    metrics_explanation = """
<h2>What each metric measures</h2>
<ul>
<li><strong>wall_clock</strong> — Total time for the measured action (e.g. navigation or click), from test start to finish (ms).</li>
<li><strong>ttfb</strong> — Time to First Byte: time until the first byte of the response is received from the server (ms).</li>
<li><strong>dom_content_loaded</strong> — When the HTML has been fully loaded and parsed; DOM is ready, scripts may still run (ms).</li>
<li><strong>dom_interactive</strong> — When the document has finished loading and the DOM is ready for user interaction (ms).</li>
<li><strong>load_event_end</strong> — When the load event has finished and all resources have loaded (ms).</li>
<li><strong>lcp</strong> — Largest Contentful Paint: when the largest visible content element is rendered; Core Web Vital (ms).</li>
<li><strong>cls</strong> — Cumulative Layout Shift: measure of visual stability (unwanted layout jumps); lower is better; Core Web Vital (unitless).</li>
</ul>
"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Detailed Metrics Report — Fordefi Performance</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.5; max-width: 960px; margin: 0 auto; padding: 1.5rem; color: #1a1a1a; }}
h1 {{ font-size: 1.5rem; border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
h2 {{ font-size: 1.25rem; margin-top: 2rem; color: #333; }}
h3 {{ font-size: 1.1rem; margin-top: 1.25rem; }}
p {{ margin: 0.5rem 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0; font-size: 0.9rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
th {{ background: #f0f0f0; font-weight: 600; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
ul {{ margin: 0.5rem 0; padding-left: 1.5rem; }}
</style>
</head>
<body>
<h1>Detailed Metrics Report</h1>
<p><em>Generated: {exec_date}</em></p>
{run_config_p}
<p>Statistics across runs: sample count, median, P95, P99, std dev, min, max (ms unless noted).</p>
{metrics_explanation}
<hr>
{body_sections}
</body>
</html>
"""


def write_detailed_metrics_report(
    results: list[MeasurementResult],
    run_dir: str | None = None,
    iterations: int | None = None,
    warmup: int | None = None,
) -> tuple[str, str]:
    """Write a separate report focused on metrics (sample_count, median, P95, std dev, etc.).

    Produces:
    - detailed_metrics_report.json: run_config (iterations, warmup) + per (page_name, action) full metrics block.
    - detailed_metrics_report.html: same content as HTML with metric explanations at the top.

    Returns (json_path, html_path).
    """
    base = _output_base(run_dir)
    json_dir = _run_subdir(base, "json")
    json_path = os.path.join(json_dir, "detailed_metrics_report.json")
    html_path = os.path.join(base, "detailed_metrics_report.html")

    run_config = {
        "iterations": iterations if iterations is not None else 1,
        "warmup": warmup if warmup is not None else 0,
    }

    entries: list[dict] = []
    for r in results:
        entries.append({
            "page_name": r.page_name,
            "action": r.action,
            "timestamp": r.timestamp,
            "console_error_count": r.console_error_count,
            "metrics": {m.name: m.to_dict() for m in r._all_metrics()},
        })

    json_payload = {"run_config": run_config, "results": entries}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2, ensure_ascii=False)
    logger.info("Detailed metrics JSON written to %s", json_path)

    html_content = _build_detailed_metrics_html(
        results,
        iterations=iterations,
        warmup=warmup,
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("Detailed metrics HTML written to %s", html_path)
    return (json_path, html_path)


def write_csv(
    results: list[MeasurementResult],
    path: str | None = None,
    run_dir: str | None = None,
) -> str:
    """Flatten results into a CSV table. Returns the file path."""
    base = _output_base(run_dir)
    out_dir = _run_subdir(base, "csv")
    out_path = _resolve_output_path(path, out_dir, "results.csv", run_dir)
    fieldnames = [
        "page_name",
        "action",
        "timestamp",
        "wall_clock_median_ms",
        "wall_clock_p95_ms",
        "ttfb_median_ms",
        "dom_content_loaded_median_ms",
        "dom_interactive_median_ms",
        "load_event_end_median_ms",
        "lcp_median_ms",
        "cls_median",
        "console_error_count",
        "network_request_count",
        "network_total_duration_ms",
        "network_slow_count",
        "network_failed_count",
        "screenshot_path",
        "notes",
    ]

    def _network_row(r: MeasurementResult) -> dict:
        summary = r.network_summary or {}
        return {
            "page_name": r.page_name,
            "action": r.action,
            "timestamp": r.timestamp,
            "wall_clock_median_ms": round(r.wall_clock.median, 2),
            "wall_clock_p95_ms": round(r.wall_clock.p95, 2),
            "ttfb_median_ms": round(r.ttfb.median, 2),
            "dom_content_loaded_median_ms": round(r.dom_content_loaded.median, 2),
            "dom_interactive_median_ms": round(r.dom_interactive.median, 2),
            "load_event_end_median_ms": round(r.load_event_end.median, 2),
            "lcp_median_ms": round(r.lcp.median, 2),
            "cls_median": round(r.cls.median, 4),
            "console_error_count": r.console_error_count,
            "network_request_count": summary.get("request_count", ""),
            "network_total_duration_ms": summary.get("total_duration_ms", ""),
            "network_slow_count": summary.get("slow_count", ""),
            "network_failed_count": summary.get("failed_count", ""),
            "screenshot_path": r.screenshot_path,
            "notes": r.notes,
        }

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(_network_row(r))
    logger.info("CSV results written to %s", out_path)
    return out_path


def write_console_errors(
    entries: list[dict],
    path: str | None = None,
    run_dir: str | None = None,
) -> str:
    """Write console error entries to a JSON file."""
    base = _output_base(run_dir)
    out_dir = _run_subdir(base, "json")
    out_path = _resolve_output_path(path, out_dir, "console_errors.json", run_dir)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    logger.info("Console errors written to %s", out_path)
    return out_path


def write_benchmark_diff_json(
    comparison_data: list[dict],
    path: str | None = None,
    run_dir: str | None = None,
) -> str:
    """Write benchmark comparison to JSON. comparison_data from benchmark.comparison_to_dict."""
    base = _output_base(run_dir)
    out_dir = _run_subdir(base, "json")
    out_path = _resolve_output_path(path, out_dir, "benchmark_diff.json", run_dir)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(comparison_data, f, indent=2, ensure_ascii=False)
    logger.info("Benchmark diff JSON written to %s", out_path)
    return out_path


def write_benchmark_diff_csv(
    comparison_data: list[dict],
    path: str | None = None,
    run_dir: str | None = None,
) -> str:
    """Write benchmark comparison summary to CSV (one row per page+action, key metrics)."""
    base = _output_base(run_dir)
    out_dir = _run_subdir(base, "csv")
    out_path = _resolve_output_path(path, out_dir, "benchmark_diff.csv", run_dir)
    fieldnames = [
        "page_name", "action", "row_status",
        "wall_clock_baseline_ms", "wall_clock_current_ms", "wall_clock_pct_change", "wall_clock_status",
        "ttfb_baseline_ms", "ttfb_current_ms", "ttfb_pct_change", "ttfb_status",
        "lcp_baseline_ms", "lcp_current_ms", "lcp_pct_change", "lcp_status",
        "console_errors_baseline", "console_errors_current",
    ]
    rows = []
    for c in comparison_data:
        metrics_map = {m["name"]: m for m in c.get("metrics", [])}
        wc = metrics_map.get("wall_clock", {})
        ttfb = metrics_map.get("ttfb", {})
        lcp = metrics_map.get("lcp", {})
        rows.append({
            "page_name": c.get("page_name", ""),
            "action": c.get("action", ""),
            "row_status": c.get("row_status", ""),
            "wall_clock_baseline_ms": wc.get("baseline_median_ms", ""),
            "wall_clock_current_ms": wc.get("current_median_ms", ""),
            "wall_clock_pct_change": wc.get("pct_change", ""),
            "wall_clock_status": wc.get("status", ""),
            "ttfb_baseline_ms": ttfb.get("baseline_median_ms", ""),
            "ttfb_current_ms": ttfb.get("current_median_ms", ""),
            "ttfb_pct_change": ttfb.get("pct_change", ""),
            "ttfb_status": ttfb.get("status", ""),
            "lcp_baseline_ms": lcp.get("baseline_median_ms", ""),
            "lcp_current_ms": lcp.get("current_median_ms", ""),
            "lcp_pct_change": lcp.get("pct_change", ""),
            "lcp_status": lcp.get("status", ""),
            "console_errors_baseline": c.get("console_errors_baseline", ""),
            "console_errors_current": c.get("console_errors_current", ""),
        })
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Benchmark diff CSV written to %s", out_path)
    return out_path


def write_markdown_report(
    results: list[MeasurementResult],
    report_path: str | None = None,
    comparison: list[RowComparison] | None = None,
    json_path: str = "",
    csv_path: str = "",
    run_dir: str | None = None,
) -> str:
    """Generate performance investigation report (markdown)."""
    base = _output_base(run_dir)
    os.makedirs(base, exist_ok=True)
    report_path = _report_file_path(base, "performance_investigation_report.md", report_path)
    lines: list[str] = []

    lines.append("# Fordefi Preprod — Performance Investigation Report")
    lines.append("")
    lines.append(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append("This report summarizes UI performance measurements for Fordefi preprod key flows: ")
    lines.append("nav-tab loads, single-item (vault/connected account) loads, and login. ")
    lines.append("Metrics include wall-clock time, TTFB, DOM timings, LCP, CLS, and console error counts.")
    if comparison:
        regressed = sum(1 for c in comparison if c.row_status == "regressed")
        improved = sum(1 for c in comparison if c.row_status == "improved")
        lines.append("")
        lines.append(f"**Benchmark comparison:** {regressed} regressed, {improved} improved vs baseline.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 2. Methodology
    lines.append("## 2. Methodology")
    lines.append("")
    lines.append("- **Tooling:** Playwright + pytest; browser Performance API for navigation timing and LCP/CLS.")
    lines.append("- **Environment:** Viewer role, read-only; headless browser, viewport 1280×720.")
    lines.append("- **Metrics:** Wall-clock (Python), TTFB, domContentLoaded, domInteractive, loadEventEnd, LCP, CLS; per-test network request count, total duration, slow (>1s) and failed (4xx/5xx) counts.")
    lines.append("- **Artifacts:** Screenshots per flow; results in JSON/CSV (including network_calls and network_summary).")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 3. Scope and Coverage
    lines.append("## 3. Scope and Coverage")
    lines.append("")
    lines.append("| Area | Flows |")
    lines.append("|------|--------|")
    lines.append("| Nav tabs | All sidebar tabs (Vaults, Connected Accounts, Assets, Transactions, etc.) — load + pagination |")
    lines.append("| Single item | Vault detail, Connected account detail (click first row from list) |")
    lines.append("| Login | Unauthenticated page load + form submit until dashboard |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 5. Broad Scan Results
    lines.append("## 5. Broad Scan Results")
    lines.append("")
    lines.append("| Page | Action | Wall (ms) | TTFB (ms) | LCP (ms) | CLS | Console errors | Network requests | Network total (ms) | Slow (>1s) | Failed |")
    lines.append("|------|--------|-----------|-----------|----------|-----|----------------|------------------|--------------------|-----------|--------|")
    for r in results:
        ns = r.network_summary or {}
        req_count = ns.get("request_count", "")
        total_ms = ns.get("total_duration_ms", "")
        slow = ns.get("slow_count", "")
        failed = ns.get("failed_count", "")
        lines.append(
            f"| {r.page_name} | {r.action} | {r.wall_clock.median:.0f} | {r.ttfb.median:.0f} | "
            f"{r.lcp.median:.0f} | {r.cls.median:.4f} | {r.console_error_count} | "
            f"{req_count} | {total_ms} | {slow} | {failed} |"
        )
    lines.append("")
    if json_path or csv_path:
        lines.append("**Artifacts:**")
        if json_path:
            lines.append(f"- JSON: `{json_path}`")
        if csv_path:
            lines.append(f"- CSV: `{csv_path}`")
        lines.append("")
    lines.append("---")
    lines.append("")

    # 6. Network Calls Summary
    lines.append("## 6. Network Calls (per test)")
    lines.append("")
    lines.append("Each measured flow captures all HTTP requests during the action. Summary: request count, total duration (ms), slow requests (>1s), failed (4xx/5xx). Full request list is in the JSON artifact under `network_calls`.")
    lines.append("")
    for r in results:
        ns = r.network_summary or {}
        if not ns:
            lines.append(f"- **{r.page_name} / {r.action}**: no network capture")
            continue
        lines.append(f"- **{r.page_name} / {r.action}**: {ns.get('request_count', 0)} requests, {ns.get('total_duration_ms', 0):.0f} ms total, {ns.get('slow_count', 0)} slow, {ns.get('failed_count', 0)} failed")
        slow_list = sorted(
            (c for c in (r.network_calls or []) if c.get("duration_ms", 0) > 1_000),
            key=lambda x: x.get("duration_ms", 0),
            reverse=True,
        )[:5]
        if slow_list:
            lines.append("  Slow requests (top 5):")
            for req in slow_list:
                url_short = (req.get("url") or "")[:80] + ("..." if len(req.get("url") or "") > 80 else "")
                lines.append(f"  - {req.get('duration_ms', 0):.0f} ms {req.get('method', '')} {url_short}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 7. Console Error Analysis
    lines.append("## 7. Console Error Analysis")
    lines.append("")
    total_errors = sum(r.console_error_count for r in results)
    if total_errors == 0:
        lines.append("No console errors captured across measured flows.")
    else:
        lines.append(f"Total console errors across flows: **{total_errors}**. ")
        lines.append("Flows with errors:")
        for r in results:
            if r.console_error_count > 0:
                lines.append(f"- **{r.page_name} / {r.action}**: {r.console_error_count} errors")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Benchmark comparison (if present)
    if comparison:
        lines.append("## Benchmark Comparison")
        lines.append("")
        lines.append("| Page | Action | Status | Wall Δ% | TTFB Δ% | LCP Δ% |")
        lines.append("|------|--------|--------|--------|--------|--------|")
        for c in comparison:
            wc = next((m for m in c.metrics if m.name == "wall_clock"), None)
            ttfb = next((m for m in c.metrics if m.name == "ttfb"), None)
            lcp = next((m for m in c.metrics if m.name == "lcp"), None)
            wc_s = f"{wc.pct_change:+.1f}%" if wc else "—"
            ttfb_s = f"{ttfb.pct_change:+.1f}%" if ttfb else "—"
            lcp_s = f"{lcp.pct_change:+.1f}%" if lcp else "—"
            lines.append(f"| {c.page_name} | {c.action} | {c.row_status} | {wc_s} | {ttfb_s} | {lcp_s} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 11. Benchmark / Regression Design
    lines.append("## 11. Benchmark / Regression Design")
    lines.append("")
    lines.append("- **Measure mode:** `pytest -m performance --mode=measure` — runs flows and writes results to a timestamped run dir under `reports/<timestamp>/` (json, csv, HTML).")
    lines.append("- **Benchmark mode:** `pytest -m performance --mode=benchmark --baseline=reports/<run>/json/results.json` — runs flows, compares to baseline, writes diff JSON/CSV and report.")
    lines.append("- **Thresholds:** Warning >10%, critical >20% (config in `configs/thresholds.py`).")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 12. Extensibility
    lines.append("## 12. Extensibility / How to Add New Test Cases")
    lines.append("")
    lines.append("1. Add a scenario row to the appropriate CSV in `data/scenarios/` (e.g. `nav_tabs.csv`, `single_item_load.csv`).")
    lines.append("2. If the flow needs a new page object, add it under `pages/` and expose selectors and wait/action methods.")
    lines.append("3. Add or parametrize a test that requests `results_collector`, runs the flow, builds `MeasurementResult.from_page_load(...)`, and appends to `results_collector`.")
    lines.append("4. Re-run measure mode to refresh baseline; use benchmark mode to compare.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 13. Appendix
    lines.append("## 13. Appendix — Screenshots")
    lines.append("")
    for r in results:
        if r.screenshot_path:
            lines.append(f"- **{r.page_name} / {r.action}:** `{r.screenshot_path}`")
    lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Markdown report written to %s", report_path)
    return report_path


def _h(s: str) -> str:
    """Escape for HTML text content."""
    return html.escape(str(s), quote=True)


def _ms(r: MeasurementResult | None) -> str:
    """Format wall_clock median as string or —."""
    if r is None:
        return "—"
    return f"{r.wall_clock.median:.0f} ms"


def _by_page(results: list[MeasurementResult]) -> dict[str, list[MeasurementResult]]:
    """Group results by page_name."""
    by_page: dict[str, list[MeasurementResult]] = {}
    for r in results:
        by_page.setdefault(r.page_name, []).append(r)
    return by_page


def _get_load_time(results_for_page: list[MeasurementResult]) -> str:
    """Page load = nav_tab_load or page_load wall_clock."""
    for r in results_for_page:
        if r.action in ("nav_tab_load", "page_load"):
            return f"{r.wall_clock.median:.0f} ms"
    return "—"


def _get_console_errors(results_for_page: list[MeasurementResult]) -> int:
    """Max console_error_count for page."""
    if not results_for_page:
        return 0
    return max(r.console_error_count for r in results_for_page)


def _get_table_render_time(results_for_page: list[MeasurementResult]) -> str:
    """Table render = table_render wall_clock, if measured."""
    for r in results_for_page:
        if r.action == "table_render":
            return f"{r.wall_clock.median:.0f} ms"
    return "—"


def _get_pagination_time(results_for_page: list[MeasurementResult]) -> str:
    """Pagination render = pagination_next wall_clock, if measured."""
    for r in results_for_page:
        if r.action == "pagination_next":
            return f"{r.wall_clock.median:.0f} ms"
    return "—"


REPORT_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "templates", "performance_report.html"
)


def _build_performance_summary_rows(by_page: dict[str, list[MeasurementResult]]) -> str:
    rows = []
    for page in PERFORMANCE_SUMMARY_PAGES:
        page_rows = by_page.get(page, [])
        load_time = _get_load_time(page_rows) if page_rows else "—"
        table_time = _get_table_render_time(page_rows) if page_rows else "—"
        table_class = "" if table_time != "—" else "na"
        err_count = _get_console_errors(page_rows) if page_rows else 0
        rows.append(
            f"<tr><td>{_h(page)}</td><td>{_h(load_time)}</td>"
            f"<td class=\"{table_class}\">{_h(table_time)}</td>"
            f"<td class=\"na\">—</td><td class=\"na\">—</td><td class=\"na\">—</td><td>{err_count}</td></tr>"
        )
    return "\n".join(rows)


def _build_deep_dive_sections(by_page: dict[str, list[MeasurementResult]]) -> str:
    parts = []
    for page in DEEP_DIVE_PAGES:
        page_rows = by_page.get(page, [])
        load_val = _get_load_time(page_rows) if page_rows else "—"
        table_val = _get_table_render_time(page_rows) if page_rows else "—"
        pagination_val = _get_pagination_time(page_rows) if page_rows else "—"
        table_class = "" if table_val != "—" else "na"
        pagination_class = "" if pagination_val != "—" else "na"
        err_count = _get_console_errors(page_rows) if page_rows else 0
        parts.append(f"<h3>{_h(page)}</h3>")
        if page == "Transaction Policy":
            metric_rows = (
                f"<tr><td>Page Load</td><td>{_h(load_val)}</td></tr>"
                f"<tr><td>Table Render</td><td class=\"{table_class}\">{_h(table_val)}</td></tr>"
                f"<tr><td>Pagination (next-page)</td><td class=\"{pagination_class}\">{_h(pagination_val)}</td></tr>"
                f"<tr><td>Console Errors</td><td>{err_count}</td></tr>"
            )
        else:
            metric_rows = (
                f"<tr><td>Page Load</td><td>{_h(load_val)}</td></tr>"
                f"<tr><td>Table Render</td><td class=\"{table_class}\">{_h(table_val)}</td></tr>"
                f"<tr><td>Pagination (next-page)</td><td class=\"{pagination_class}\">{_h(pagination_val)}</td></tr>"
                "<tr><td>Sort</td><td class=\"na\">—</td></tr>"
                "<tr><td>Filter</td><td class=\"na\">—</td></tr>"
                "<tr><td>Search</td><td class=\"na\">—</td></tr>"
                f"<tr><td>Console Errors</td><td>{err_count}</td></tr>"
            )
        parts.append(
            "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
            f"<tbody>{metric_rows}</tbody></table>"
        )
        parts.append("<p><em>Notes</em><br><span class=\"na\">—</span></p>")
    return "\n".join(parts)


def _build_benchmark_section(comparison: list[RowComparison] | None) -> str:
    if not comparison:
        return "<p>Included only when running in <strong>benchmark mode</strong>. Not applicable for this run.</p>"
    rows = []
    for c in comparison:
        wc = next((m for m in c.metrics if m.name == "wall_clock"), None)
        if wc:
            prev = f"{wc.baseline_median:.0f} ms"
            curr = f"{wc.current_median:.0f} ms"
            chg = f"{wc.pct_change:+.1f}%"
            status_class = f" status-{c.row_status}" if c.row_status in ("regressed", "improved") else ""
            rows.append(f"<tr><td>{_h(c.page_name)}</td><td>Page Load</td><td>{_h(prev)}</td><td>{_h(curr)}</td><td class=\"{status_class}\">{_h(chg)}</td></tr>")
    regressed = sum(1 for c in comparison if c.row_status == "regressed")
    improved = sum(1 for c in comparison if c.row_status == "improved")
    rows_html = "\n".join(rows)
    table_html = (
        "<table><thead><tr><th>Page</th><th>Metric</th><th>Previous Run</th><th>Current Run</th><th>Change</th></tr></thead>"
        f"<tbody>\n{rows_html}</tbody></table>"
    )
    return f"<p>Included only when running in <strong>benchmark mode</strong>.</p>{table_html}<p><strong>Summary</strong><br>{regressed} regressed, {improved} improved vs baseline.</p>"


def _build_console_errors_rows(by_page: dict[str, list[MeasurementResult]]) -> str:
    return "\n".join(
        f"<tr><td>{_h(page)}</td><td>{_get_console_errors(by_page.get(page, []))}</td><td class=\"na\">—</td></tr>"
        for page in PERFORMANCE_SUMMARY_PAGES
    )


def _get_network_summary_for_page(results_for_page: list[MeasurementResult]) -> dict:
    """Return network_summary for primary load action (nav_tab_load or page_load)."""
    for r in results_for_page:
        if r.action in ("nav_tab_load", "page_load"):
            return r.network_summary or {}
    return {}


def _build_network_summary_rows(by_page: dict[str, list[MeasurementResult]]) -> str:
    """HTML rows for Network Summary section."""
    rows: list[str] = []
    for page in PERFORMANCE_SUMMARY_PAGES:
        page_rows = by_page.get(page, [])
        ns = _get_network_summary_for_page(page_rows) if page_rows else {}
        req = ns.get("request_count", "—")
        total = ns.get("total_duration_ms", "—")
        slow = ns.get("slow_count", "—")
        failed = ns.get("failed_count", "—")
        rows.append(
            f"<tr><td>{_h(page)}</td><td>{_h(req)}</td><td>{_h(total)}</td>"
            f"<td>{_h(slow)}</td><td>{_h(failed)}</td></tr>"
        )
    return "\n".join(rows)


def _build_artifacts_rows(
    json_path: str,
    html_path: str,
    run_dir: str | None = None,
) -> str:
    """Build HTML rows for artifacts table. Uses relative paths (all outputs live in run dir)."""
    traces_dir = "traces"
    screenshots_dir = "screenshots"
    har_dir = "har"
    raw_metrics = "json/results.json"
    html_display = "performance_investigation_report.html"
    detailed_report = "detailed_metrics_report.html"
    return "\n".join([
        f"<tr><td>Playwright traces</td><td>{_h(traces_dir)}</td></tr>",
        f"<tr><td>Screenshots</td><td>{_h(screenshots_dir)}</td></tr>",
        f"<tr><td>HAR files</td><td>{_h(har_dir)}</td></tr>",
        f"<tr><td>JSON metrics</td><td>{_h(raw_metrics)}</td></tr>",
        f"<tr><td>HTML report</td><td>{_h(html_display)}</td></tr>",
        f"<tr><td>Detailed metrics report</td><td><a href=\"{_h(detailed_report)}\">{_h(detailed_report)}</a></td></tr>",
    ])


def write_html_report(
    results: list[MeasurementResult],
    report_path: str | None = None,
    comparison: list[RowComparison] | None = None,
    json_path: str = "",
    run_mode: str = "measure",
    run_dir: str | None = None,
    iterations: int | None = None,
    warmup: int | None = None,
) -> str:
    """Generate performance investigation report as HTML (concise template)."""
    base = _output_base(run_dir)
    os.makedirs(base, exist_ok=True)
    out_path = _report_file_path(base, "performance_investigation_report.html", report_path)
    html_artifact_path = out_path

    exec_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    git_version = _get_git_version()
    by_page = _by_page(results)

    load_times = [r.wall_clock.median for r in results if r.action in ("nav_tab_load", "page_load")]
    median_load = f"{sum(load_times) / len(load_times):.0f} ms" if load_times else "—"
    total_errors = sum(r.console_error_count for r in results)
    if comparison:
        regressed = sum(1 for c in comparison if c.row_status == "regressed")
        improved = sum(1 for c in comparison if c.row_status == "improved")
        conclusion = f"Run in benchmark mode: {regressed} regressed, {improved} improved vs baseline. Median page load (current run): {median_load}. Console errors: {total_errors}."
    else:
        conclusion = f"Median page load across flows: {median_load}. Total console errors captured: {total_errors}."

    with open(REPORT_TEMPLATE_PATH, encoding="utf-8") as f:
        raw_template = f.read()

    # Escape all braces, then restore known placeholders so CSS remains valid
    safe_template = raw_template.replace("{", "{{").replace("}", "}}")
    for name in [
        "base_url",
        "exec_date",
        "run_mode",
        "iterations",
        "warmup",
        "git_version",
        "performance_summary_rows",
        "deep_dive_sections",
        "benchmark_section",
        "network_summary_rows",
        "console_errors_rows",
        "artifacts_rows",
        "conclusion",
    ]:
        safe_template = safe_template.replace(f"{{{{{name}}}}}", f"{{{name}}}")

    iter_str = str(iterations) if iterations is not None else "—"
    warmup_str = str(warmup) if warmup is not None else "—"
    html = safe_template.format(
        base_url=_h(BASE_URL),
        exec_date=_h(exec_date),
        run_mode=_h(run_mode),
        iterations=_h(iter_str),
        warmup=_h(warmup_str),
        git_version=_h(git_version),
        performance_summary_rows=_build_performance_summary_rows(by_page),
        deep_dive_sections=_build_deep_dive_sections(by_page),
        benchmark_section=_build_benchmark_section(comparison),
        network_summary_rows=_build_network_summary_rows(by_page),
        console_errors_rows=_build_console_errors_rows(by_page),
        artifacts_rows=_build_artifacts_rows(
            json_path, html_artifact_path, run_dir=base
        ),
        conclusion=_h(conclusion),
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("HTML report written to %s", out_path)
    return out_path
