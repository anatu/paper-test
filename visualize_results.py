#!/usr/bin/env python3
"""Papercheck Results Dashboard — interactive local web viewer for pipeline output.

Usage:
    python visualize_results.py results/report.json
    python visualize_results.py results/              # looks for report.json inside
    python visualize_results.py report.json --port 9000 --no-open
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Papercheck Report</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg-primary:#1a1a2e;--bg-secondary:#16213e;--bg-card:#1e2a45;
  --bg-card-hover:#243352;--border:#0f3460;--border-light:#1a4080;
  --text-primary:#e0e0e0;--text-secondary:#8892b0;--text-muted:#5a6785;
  --signal-pass:#64ffda;--signal-warn:#ffd166;--signal-fail:#ff6b6b;
  --sev-info:#64b5f6;--sev-warning:#ffd166;--sev-error:#ff6b6b;--sev-critical:#ff3d71;
  --radius:8px;--gap:16px;
}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:var(--bg-primary);color:var(--text-primary);line-height:1.6;
  padding:0;min-height:100vh}
.container{max-width:1100px;margin:0 auto;padding:24px var(--gap)}
a{color:var(--signal-pass);text-decoration:none}

/* Header */
.header{display:flex;align-items:center;gap:24px;padding:32px 0 24px;
  border-bottom:1px solid var(--border);margin-bottom:24px;flex-wrap:wrap}
.header-info{flex:1;min-width:250px}
.header-info h1{font-size:1.5rem;font-weight:600;margin-bottom:4px}
.header-info .authors{color:var(--text-secondary);font-size:0.9rem}
.meta-row{display:flex;gap:16px;margin-top:12px;flex-wrap:wrap}
.meta-item{font-size:0.8rem;color:var(--text-muted)}
.meta-item span{color:var(--text-secondary)}

/* Gauge */
.gauge{position:relative;width:120px;height:120px;flex-shrink:0}
.gauge svg{width:120px;height:120px;transform:rotate(-90deg)}
.gauge-bg{fill:none;stroke:var(--border);stroke-width:10}
.gauge-fill{fill:none;stroke-width:10;stroke-linecap:round;
  transition:stroke-dashoffset 1s ease-out}
.gauge-center{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center}
.gauge-score{font-size:1.6rem;font-weight:700;line-height:1}
.gauge-label{font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;margin-top:2px}

/* Signal badge */
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75rem;
  font-weight:600;text-transform:uppercase;letter-spacing:0.04em;border:1.5px solid}
.badge-pass{color:var(--signal-pass);border-color:var(--signal-pass)}
.badge-warn{color:var(--signal-warn);border-color:var(--signal-warn)}
.badge-fail{color:var(--signal-fail);border-color:var(--signal-fail)}
.badge-skip{color:var(--text-muted);border-color:var(--text-muted)}

/* Layer grid */
.layer-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:var(--gap);margin-bottom:24px}
.layer-card{background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px;cursor:pointer;
  transition:background 0.15s,border-color 0.15s}
.layer-card:hover{background:var(--bg-card-hover);border-color:var(--border-light)}
.layer-card.skipped{opacity:0.55;border-style:dashed;cursor:default}
.layer-card .lnum{font-size:2rem;font-weight:700;color:var(--text-muted);line-height:1}
.layer-card .lname{font-size:0.82rem;color:var(--text-secondary);margin:4px 0 8px}
.score-bar{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-bottom:8px}
.score-bar-fill{height:100%;border-radius:3px;transition:width 0.8s ease-out}
.layer-card .card-footer{display:flex;justify-content:space-between;align-items:center}
.severity-dots{display:flex;gap:3px}
.severity-dot{width:8px;height:8px;border-radius:50%}

/* Findings summary bar */
.summary-bar{display:flex;gap:10px;align-items:center;margin-bottom:24px;flex-wrap:wrap}
.summary-pill{padding:4px 12px;border-radius:14px;font-size:0.8rem;font-weight:600;
  cursor:pointer;border:1.5px solid;transition:opacity 0.15s;user-select:none}
.summary-pill:hover{opacity:0.8}
.summary-pill.active{opacity:1}.summary-pill.muted{opacity:0.3}
.summary-pill-info{color:var(--sev-info);border-color:var(--sev-info)}
.summary-pill-warning{color:var(--sev-warning);border-color:var(--sev-warning)}
.summary-pill-error{color:var(--sev-error);border-color:var(--sev-error)}
.summary-pill-critical{color:var(--sev-critical);border-color:var(--sev-critical)}

/* Detail sections */
.details-controls{display:flex;gap:8px;margin-bottom:12px}
.details-controls button{background:var(--bg-card);color:var(--text-secondary);
  border:1px solid var(--border);border-radius:var(--radius);padding:6px 14px;
  font-size:0.8rem;cursor:pointer}
.details-controls button:hover{background:var(--bg-card-hover)}
details.layer-detail{background:var(--bg-secondary);border:1px solid var(--border);
  border-radius:var(--radius);margin-bottom:12px}
details.layer-detail[open]{border-color:var(--border-light)}
details.layer-detail summary{padding:14px 18px;cursor:pointer;display:flex;
  align-items:center;gap:12px;list-style:none;user-select:none}
details.layer-detail summary::-webkit-details-marker{display:none}
details.layer-detail summary::before{content:'\25B6';font-size:0.7rem;
  color:var(--text-muted);transition:transform 0.15s;flex-shrink:0}
details.layer-detail[open] summary::before{transform:rotate(90deg)}
.detail-header{flex:1;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.detail-header .dlname{font-weight:600;font-size:0.95rem}
.detail-header .dlscore{color:var(--text-secondary);font-size:0.85rem}
.detail-header .dltime{color:var(--text-muted);font-size:0.75rem;margin-left:auto}
.detail-body{padding:0 18px 18px}
.skip-reason{color:var(--text-muted);font-style:italic;font-size:0.85rem}

/* Findings list */
.finding{padding:10px 0;border-top:1px solid var(--border)}
.finding:first-child{border-top:none}
.finding-header{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap}
.finding .sev-badge{font-size:0.7rem;padding:1px 8px;border-radius:10px;font-weight:600;
  text-transform:uppercase;flex-shrink:0;border:1px solid}
.sev-info{color:var(--sev-info);border-color:var(--sev-info)}
.sev-warning{color:var(--sev-warning);border-color:var(--sev-warning)}
.sev-error{color:var(--sev-error);border-color:var(--sev-error)}
.sev-critical{color:var(--sev-critical);border-color:var(--sev-critical)}
.finding .cat-tag{font-family:"SF Mono","Fira Code",monospace;font-size:0.75rem;
  color:var(--text-muted);background:var(--bg-primary);padding:1px 7px;border-radius:4px}
.finding .msg{font-size:0.88rem;margin-top:4px}
.finding .evidence{margin-top:6px;padding:8px 12px;background:var(--bg-primary);
  border-left:3px solid var(--border-light);border-radius:0 4px 4px 0;
  font-size:0.82rem;color:var(--text-secondary);overflow-wrap:break-word}
.finding .suggestion{margin-top:6px;padding:8px 12px;background:rgba(100,255,218,0.05);
  border-left:3px solid var(--signal-pass);border-radius:0 4px 4px 0;
  font-size:0.82rem;color:var(--text-secondary);overflow-wrap:break-word}
.finding .location{font-size:0.75rem;color:var(--text-muted);margin-top:4px}
.no-findings{color:var(--text-muted);font-size:0.85rem;padding:8px 0}

/* Severity filter */
body.hide-info .finding-info{display:none}
body.hide-warning .finding-warning{display:none}
body.hide-error .finding-error{display:none}
body.hide-critical .finding-critical{display:none}
</style>
</head>
<body>
<div class="container">
  <div class="header" id="header"></div>
  <div class="layer-grid" id="layer-grid"></div>
  <div class="summary-bar" id="summary-bar"></div>
  <div class="details-controls" id="details-controls"></div>
  <div id="layer-details"></div>
</div>
<script>
const R = __REPORT_JSON__;

function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}
function scoreColor(s){return s>=0.8?'var(--signal-pass)':s>=0.5?'var(--signal-warn)':'var(--signal-fail)'}
function signalClass(s){return 'badge-'+(s==='pass'?'pass':s==='warn'?'warn':s==='fail'?'fail':'skip')}
function sevOrder(s){return{critical:0,error:1,warning:2,info:3}[s]??4}

function renderHeader(){
  const h=document.getElementById('header');
  const title=R.title||'Untitled Paper';
  const authors=R.authors&&R.authors.length?R.authors.join(', '):'No authors listed';
  const score=R.composite_score;
  const sig=R.composite_signal;
  const c=scoreColor(score);
  const pct=score*100;
  const circ=2*Math.PI*50;
  const ts=R.timestamp?new Date(R.timestamp).toLocaleString():'—';

  h.innerHTML=`
    <div class="header-info">
      <h1>${esc(title)}</h1>
      <div class="authors">${esc(authors)}</div>
      <div class="meta-row">
        <div class="meta-item">Version <span>${esc(R.pipeline_version||'?')}</span></div>
        <div class="meta-item">Time <span>${R.total_execution_time_seconds?.toFixed(1)||'?'}s</span></div>
        <div class="meta-item">LLM Cost <span>$${R.total_llm_cost_usd?.toFixed(2)||'0.00'}</span></div>
        <div class="meta-item">${esc(ts)}</div>
      </div>
    </div>
    <div class="gauge">
      <svg viewBox="0 0 120 120">
        <circle class="gauge-bg" cx="60" cy="60" r="50"/>
        <circle class="gauge-fill" cx="60" cy="60" r="50"
          stroke="${c}"
          stroke-dasharray="${circ}"
          stroke-dashoffset="${circ}"
          data-target="${circ*(1-score)}"/>
      </svg>
      <div class="gauge-center">
        <div class="gauge-score" style="color:${c}" data-target="${pct}" >0</div>
        <div class="gauge-label"><span class="badge ${signalClass(sig)}">${sig}</span></div>
      </div>
    </div>`;

  // Animate gauge
  requestAnimationFrame(()=>{
    const fill=h.querySelector('.gauge-fill');
    fill.style.strokeDashoffset=fill.dataset.target;
    const num=h.querySelector('.gauge-score');
    animateNumber(num,0,score,800);
  });
}

function animateNumber(el,from,to,dur){
  const start=performance.now();
  function step(now){
    const t=Math.min((now-start)/dur,1);
    const ease=1-Math.pow(1-t,3);
    el.textContent=(from+(to-from)*ease).toFixed(2);
    if(t<1)requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function renderGrid(){
  const g=document.getElementById('layer-grid');
  g.innerHTML=R.layer_results.map(lr=>{
    const skipped=lr.skipped;
    const c=scoreColor(lr.score);
    const sevCounts={};
    (lr.findings||[]).forEach(f=>{sevCounts[f.severity]=(sevCounts[f.severity]||0)+1});
    const dots=Object.entries(sevCounts).sort((a,b)=>sevOrder(a[0])-sevOrder(b[0]))
      .map(([s,n])=>`<span class="severity-dot" style="background:var(--sev-${s})" title="${n} ${s}"></span>`.repeat(Math.min(n,5))).join('');
    return `
    <div class="layer-card${skipped?' skipped':''}" data-layer="${lr.layer}" onclick="jumpToLayer(${lr.layer})">
      <div class="lnum">${lr.layer}</div>
      <div class="lname">${esc(lr.layer_name)}</div>
      ${skipped?`<div class="skip-reason">${esc(lr.skip_reason||'Skipped')}</div>`:`
      <div class="score-bar"><div class="score-bar-fill" style="width:${lr.score*100}%;background:${c}"></div></div>
      <div class="card-footer">
        <span class="badge ${signalClass(lr.signal)}">${lr.signal}</span>
        <div class="severity-dots">${dots}</div>
      </div>`}
    </div>`;
  }).join('');
}

function renderSummaryBar(){
  const bar=document.getElementById('summary-bar');
  const totals={info:0,warning:0,error:0,critical:0};
  R.layer_results.forEach(lr=>(lr.findings||[]).forEach(f=>{if(totals[f.severity]!==undefined)totals[f.severity]++}));
  const sevs=['critical','error','warning','info'];
  bar.innerHTML='<span style="font-size:0.85rem;color:var(--text-secondary)">Filter:</span>'+
    sevs.filter(s=>totals[s]>0).map(s=>
      `<span class="summary-pill summary-pill-${s} active" data-sev="${s}" onclick="toggleSev('${s}')">${totals[s]} ${s}</span>`
    ).join('');
}

function toggleSev(sev){
  document.body.classList.toggle('hide-'+sev);
  const pill=document.querySelector(`.summary-pill[data-sev="${sev}"]`);
  if(pill)pill.classList.toggle('active'),pill.classList.toggle('muted');
}

function renderDetails(){
  const ctrl=document.getElementById('details-controls');
  ctrl.innerHTML=`<button onclick="toggleAll(true)">Expand All</button><button onclick="toggleAll(false)">Collapse All</button>`;
  const det=document.getElementById('layer-details');
  det.innerHTML=R.layer_results.map(lr=>{
    const findings=(lr.findings||[]).slice().sort((a,b)=>sevOrder(a.severity)-sevOrder(b.severity));
    const time=lr.execution_time_seconds>=0.01?lr.execution_time_seconds.toFixed(2)+'s':'<0.01s';
    return `
    <details class="layer-detail" id="layer-${lr.layer}">
      <summary>
        <div class="detail-header">
          <span class="dlname">Layer ${lr.layer}: ${esc(lr.layer_name)}</span>
          <span class="badge ${signalClass(lr.skipped?'skip':lr.signal)}">${lr.skipped?'SKIP':lr.signal}</span>
          ${lr.skipped?'':`<span class="dlscore">${lr.score.toFixed(2)}</span>`}
          <span class="dltime">${time}</span>
        </div>
      </summary>
      <div class="detail-body">
        ${lr.skipped?`<div class="skip-reason">${esc(lr.skip_reason||'Skipped')}</div>`:
          findings.length===0?'<div class="no-findings">No findings</div>':
          findings.map(f=>`
          <div class="finding finding-${f.severity}">
            <div class="finding-header">
              <span class="sev-badge sev-${f.severity}">${f.severity}</span>
              <span class="cat-tag">${esc(f.category)}</span>
            </div>
            <div class="msg">${esc(f.message)}</div>
            ${f.evidence?`<div class="evidence">${esc(f.evidence)}</div>`:''}
            ${f.suggestion?`<div class="suggestion">${esc(f.suggestion)}</div>`:''}
            ${f.location?`<div class="location">${esc(f.location)}</div>`:''}
          </div>`).join('')}
      </div>
    </details>`;
  }).join('');
}

function jumpToLayer(n){
  const el=document.getElementById('layer-'+n);
  if(el){el.open=true;el.scrollIntoView({behavior:'smooth',block:'start'})}
}
function toggleAll(open){
  document.querySelectorAll('.layer-detail').forEach(d=>d.open=open);
}

document.addEventListener('DOMContentLoaded',()=>{renderHeader();renderGrid();renderSummaryBar();renderDetails()});
</script>
</body>
</html>
"""


def make_handler(html_content: str):
    """Create an HTTP handler that serves the dashboard."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(html_content.encode())
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            pass  # Suppress request logs

    return Handler


def load_report(path: Path) -> dict:
    """Load and validate a report JSON file."""
    if path.is_dir():
        path = path / "report.json"
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)
    if "layer_results" not in data:
        print(f"Error: {path} does not look like a papercheck report (missing layer_results)", file=sys.stderr)
        sys.exit(1)
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Papercheck Results Dashboard — interactive viewer for pipeline output"
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to report.json or directory containing it",
    )
    parser.add_argument(
        "--port", type=int, default=8089, help="Port (default: 8089)"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't auto-open browser"
    )
    args = parser.parse_args()

    report = load_report(Path(args.path))
    html = DASHBOARD_HTML.replace("__REPORT_JSON__", json.dumps(report))
    handler = make_handler(html)

    import socket

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
        allow_reuse_port = True

        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()

    server = ReusableHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Serving dashboard at {url}")
    print("Press Ctrl+C to stop")

    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
