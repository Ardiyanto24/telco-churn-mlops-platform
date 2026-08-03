"""Read-only, token-protected M18 investigation dashboard."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from html import escape
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from telco_churn.metrics_store import MetricsStore, MetricsStoreError


def create_internal_dashboard(
    *, store: MetricsStore, access_token: str, now: Callable[[], datetime] | None = None,
    expected_interval: timedelta = timedelta(days=1),
) -> FastAPI:
    """Create a separately hosted dashboard; it cannot alter prediction serving."""
    if not access_token:
        raise ValueError("internal dashboard access_token is required")
    clock = now or (lambda: datetime.now(timezone.utc))
    app = FastAPI(title="Telco Churn Internal MLOps Dashboard", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
        return response

    @app.get("/internal/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request) -> HTMLResponse:
        supplied = request.headers.get("X-Internal-Metrics-Token", "")
        if not compare_digest(supplied, access_token):
            raise HTTPException(status_code=401, detail="Unauthorized")
        try:
            snapshot = store.dashboard_snapshot(now=clock(), expected_interval=expected_interval)
        except MetricsStoreError as exc:
            raise HTTPException(status_code=503, detail="Dashboard data unavailable") from exc
        return HTMLResponse(_render_dashboard(snapshot))

    return app


def _render_dashboard(snapshot: dict[str, Any]) -> str:
    state = _text(snapshot["state"])
    freshness = snapshot["freshness"]
    freshness_state = _text(freshness["state"])
    result_cards = "".join(_render_result(result) for result in snapshot["results"]) or (
        '<section class="empty" role="status"><h2>No metrics available</h2>'
        '<p>The store has no completed aggregate result. This is <strong>not_available</strong>, not stable.</p></section>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internal MLOps Metrics</title><style>{_CSS}</style></head>
<body><main><header><p class="eyebrow">TELCO CHURN · INTERNAL ONLY</p><h1>Internal MLOps Metrics</h1>
<p class="subtitle">Read-only aggregate evidence. Candidate, replayed, and synthetic results are not production health claims.</p></header>
<section class="overview" aria-label="Current evidence"><div><span>Current evidence</span><strong class="badge state-{state}">{state}</strong></div>
<div><span>Freshness</span><strong class="badge fresh-{freshness_state}">{freshness_state}</strong></div>
<div><span>Latest completed window</span><strong>{_text(freshness.get('window_end', 'not_available'))}</strong></div></section>
<section aria-labelledby="results-heading"><h2 id="results-heading">Investigation results</h2>{result_cards}</section>
</main></body></html>"""


def _render_result(result: dict[str, Any]) -> str:
    distribution = _text(json.dumps(result["distribution"], sort_keys=True, separators=(",", ":")))
    coverage = "not_available" if result["label_coverage"] is None else str(result["label_coverage"])
    return f"""<article class="result"><div class="result-heading"><h3>{_text(result['result_type'])}</h3>
<span class="badge state-{_text(result['status'])}">{_text(result['status'])}</span></div>
<dl><div><dt>Data origin</dt><dd>{_text(result['data_origin'])}</dd></div><div><dt>Sample size</dt><dd>{_text(result['sample_size'])}</dd></div>
<div><dt>Label coverage</dt><dd>{_text(coverage)}</dd></div><div><dt>Window</dt><dd>{_text(result['window_start'])} → {_text(result['window_end'])}</dd></div>
<div><dt>Method / config</dt><dd>{_text(result['method_version'])} / {_text(result['config_version'])}</dd></div>
<div><dt>Model / baseline</dt><dd>{_text(result['model_version'])} / {_text(result['baseline_id'] or 'not_available')}</dd></div></dl>
<details><summary>Baseline/current distribution</summary><pre>{distribution}</pre></details></article>"""


def _text(value: object) -> str:
    return escape(str(value), quote=True)


_CSS = """
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #14213d; background: #f6f8fb; }
* { box-sizing: border-box; } body { margin: 0; } main { max-width: 1120px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
header { border-left: .3rem solid #007c91; padding-left: 1rem; } .eyebrow { color: #007c91; font-size: .75rem; font-weight: 700; letter-spacing: .08em; }
h1 { margin: .25rem 0; font-size: clamp(1.8rem, 4vw, 2.7rem); } h2 { margin-top: 2.5rem; } h3 { margin: 0; text-transform: capitalize; }
.subtitle { color: #52606d; max-width: 50rem; } .overview { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin-top: 1.75rem; }
.overview > div, .result, .empty { background: #fff; border: 1px solid #d9e2ec; border-radius: .4rem; padding: 1rem; } .overview span, dt { display: block; color: #52606d; font-size: .8rem; }
.overview strong { display: block; margin-top: .35rem; overflow-wrap: anywhere; } .result { margin-top: 1rem; } .result-heading { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.badge { border-radius: 999px; display: inline-block; font-size: .78rem; font-weight: 700; padding: .25rem .55rem; } .state-stable, .fresh-fresh { background: #d9f7e6; color: #075c32; }
.state-warning, .fresh-late { background: #fff3cd; color: #7a4b00; } .state-critical, .fresh-stale { background: #fde2e2; color: #9b1c1c; }
.state-unknown, .state-insufficient_data, .state-not_available, .fresh-not_available { background: #e9eef5; color: #334e68; }
dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; } dd { margin: .25rem 0 0; overflow-wrap: anywhere; } details { margin-top: 1rem; } summary { cursor: pointer; font-weight: 600; } pre { overflow: auto; background: #f6f8fb; border: 1px solid #d9e2ec; padding: .75rem; white-space: pre-wrap; }
@media (max-width: 720px) { main { padding: 1.5rem 1rem 3rem; } .overview, dl { grid-template-columns: 1fr; } }
"""
