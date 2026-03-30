#!/usr/bin/env python3
"""
LaTeX Paper Viewer — compile a .tex file and serve a live-reloading PDF viewer.

Usage:
    python visualize_latex.py paper.tex
    python visualize_latex.py paper.tex --port 8080
    python visualize_latex.py paper.pdf          # skip compilation, just view
"""

import argparse
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LaTeX Viewer — {filename}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: #16213e;
    border-bottom: 1px solid #0f3460;
    flex-shrink: 0;
  }
  header h1 {
    font-size: 14px;
    font-weight: 500;
    color: #a8b2d1;
  }
  header .status {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 12px;
    background: #0f3460;
  }
  header .status.ok { color: #64ffda; }
  header .status.compiling { color: #ffd166; }
  header .status.error { color: #ff6b6b; }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 16px;
    background: #16213e;
    border-bottom: 1px solid #0f3460;
    flex-shrink: 0;
  }
  .toolbar button {
    background: #0f3460;
    color: #a8b2d1;
    border: none;
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
  }
  .toolbar button:hover { background: #1a4a8a; color: #fff; }
  .toolbar .info { font-size: 12px; color: #8892b0; margin-left: auto; }
  #viewer {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: auto;
    padding: 16px;
  }
  #viewer embed, #viewer iframe, #viewer object {
    width: 100%;
    height: 100%;
    border: none;
    border-radius: 4px;
  }
  #error-panel {
    display: none;
    background: #2d1117;
    border: 1px solid #ff6b6b;
    border-radius: 6px;
    padding: 16px;
    margin: 16px;
    max-height: 40vh;
    overflow: auto;
    font-family: "SF Mono", "Fira Code", monospace;
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    color: #ffa0a0;
  }
</style>
</head>
<body>
  <header>
    <h1>{filename}</h1>
    <span class="status ok" id="status">Ready</span>
  </header>
  <div class="toolbar">
    <button onclick="recompile()">Recompile</button>
    <button onclick="toggleAutoReload()">Auto-reload: <span id="auto-label">ON</span></button>
    <span class="info" id="last-compiled"></span>
  </div>
  <div id="error-panel"></div>
  <div id="viewer">
    <embed id="pdf-embed" src="/pdf?t=0" type="application/pdf">
  </div>

<script>
  let autoReload = true;
  let lastMtime = 0;

  function setStatus(text, cls) {
    const el = document.getElementById("status");
    el.textContent = text;
    el.className = "status " + cls;
  }

  async function checkForUpdates() {
    if (!autoReload) return;
    try {
      const resp = await fetch("/status");
      const data = await resp.json();
      if (data.mtime > lastMtime) {
        lastMtime = data.mtime;
        refreshPdf();
        if (data.compile_error) {
          document.getElementById("error-panel").style.display = "block";
          document.getElementById("error-panel").textContent = data.compile_error;
          setStatus("Compile error", "error");
        } else {
          document.getElementById("error-panel").style.display = "none";
          setStatus("Ready", "ok");
        }
        document.getElementById("last-compiled").textContent =
          "Last compiled: " + new Date(data.mtime * 1000).toLocaleTimeString();
      }
    } catch (e) {}
  }

  function refreshPdf() {
    const embed = document.getElementById("pdf-embed");
    embed.src = "/pdf?t=" + Date.now();
  }

  async function recompile() {
    setStatus("Compiling...", "compiling");
    try {
      const resp = await fetch("/recompile", { method: "POST" });
      const data = await resp.json();
      lastMtime = data.mtime;
      refreshPdf();
      if (data.compile_error) {
        document.getElementById("error-panel").style.display = "block";
        document.getElementById("error-panel").textContent = data.compile_error;
        setStatus("Compile error", "error");
      } else {
        document.getElementById("error-panel").style.display = "none";
        setStatus("Ready", "ok");
      }
      document.getElementById("last-compiled").textContent =
        "Last compiled: " + new Date(data.mtime * 1000).toLocaleTimeString();
    } catch (e) {
      setStatus("Error", "error");
    }
  }

  function toggleAutoReload() {
    autoReload = !autoReload;
    document.getElementById("auto-label").textContent = autoReload ? "ON" : "OFF";
  }

  // Poll for changes every 2 seconds
  setInterval(checkForUpdates, 2000);
  // Initial load
  checkForUpdates();
</script>
</body>
</html>"""


# ── LaTeX compilation ────────────────────────────────────────────────────────

def find_compiler():
    """Find an available LaTeX compiler."""
    # macOS MacTeX installs here but some Python environments don't inherit the full shell PATH
    extra_paths = "/Library/TeX/texbin"
    env_path = os.environ.get("PATH", "")
    if extra_paths not in env_path:
        os.environ["PATH"] = env_path + os.pathsep + extra_paths
    for cmd in ("latexmk", "pdflatex"):
        if shutil.which(cmd):
            return cmd
    return None


def compile_latex(tex_path: Path, pdf_path: Path) -> str | None:
    """Compile a .tex file to PDF. Returns error string or None on success."""
    compiler = find_compiler()
    if compiler is None:
        return "No LaTeX compiler found. Install texlive or mactex (brew install --cask mactex)."

    tex_dir = tex_path.parent
    tex_name = tex_path.name

    if compiler == "latexmk":
        cmd = [
            "latexmk", "-pdf", "-interaction=nonstopmode",
            "-output-directory=" + str(pdf_path.parent),
            str(tex_path),
        ]
    else:
        cmd = [
            "pdflatex", "-interaction=nonstopmode",
            "-output-directory=" + str(pdf_path.parent),
            str(tex_path),
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=str(tex_dir)
        )
        # latexmk names output based on the tex filename
        expected = pdf_path.parent / tex_path.with_suffix(".pdf").name
        if expected != pdf_path and expected.exists():
            shutil.copy2(expected, pdf_path)

        if not pdf_path.exists():
            # Pull the useful part of the log
            log = result.stdout + "\n" + result.stderr
            # Extract lines with "!" (LaTeX errors)
            error_lines = [l for l in log.splitlines() if l.startswith("!") or "Error" in l]
            snippet = "\n".join(error_lines[:30]) if error_lines else log[-3000:]
            return f"Compilation failed (exit {result.returncode}):\n{snippet}"

        return None
    except subprocess.TimeoutExpired:
        return "Compilation timed out after 120 seconds."
    except Exception as e:
        return str(e)


# ── File watcher ─────────────────────────────────────────────────────────────

class TexWatcher:
    """Watch a .tex file (and its directory) for changes and recompile."""

    def __init__(self, tex_path: Path, pdf_path: Path):
        self.tex_path = tex_path
        self.pdf_path = pdf_path
        self.mtime = 0.0
        self.compile_error: str | None = None
        self.lock = threading.Lock()
        self._source_is_pdf = tex_path.suffix.lower() == ".pdf"

        if self._source_is_pdf:
            # No compilation needed — just serve the PDF directly
            shutil.copy2(tex_path, pdf_path)
            self.mtime = time.time()
        else:
            self.recompile()

    def _get_source_mtime(self) -> float:
        """Get the latest mtime of the .tex file and any .bib/.sty in its directory."""
        try:
            best = self.tex_path.stat().st_mtime
            tex_dir = self.tex_path.parent
            for ext in ("*.tex", "*.bib", "*.sty", "*.cls"):
                for f in tex_dir.glob(ext):
                    best = max(best, f.stat().st_mtime)
            return best
        except OSError:
            return 0.0

    def recompile(self) -> dict:
        """Force a recompile and return status."""
        with self.lock:
            if self._source_is_pdf:
                shutil.copy2(self.tex_path, self.pdf_path)
                self.mtime = time.time()
                self.compile_error = None
            else:
                err = compile_latex(self.tex_path, self.pdf_path)
                self.compile_error = err
                self.mtime = time.time()
            return {"mtime": self.mtime, "compile_error": self.compile_error}

    def check(self):
        """Check if sources changed and recompile if needed."""
        if self._source_is_pdf:
            try:
                current = self.tex_path.stat().st_mtime
                if current > self.mtime:
                    self.recompile()
            except OSError:
                pass
            return
        source_mtime = self._get_source_mtime()
        if source_mtime > self.mtime:
            self.recompile()

    def run_watcher(self):
        """Background thread: poll for changes every 2 seconds."""
        while True:
            time.sleep(2)
            self.check()


# ── HTTP server ──────────────────────────────────────────────────────────────

def make_handler(watcher: TexWatcher, tex_filename: str):

    class Handler(http.server.BaseHTTPRequestHandler):

        def do_GET(self):
            path = self.path.split("?")[0]

            if path == "/":
                html = VIEWER_HTML.replace("{filename}", tex_filename)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())

            elif path == "/pdf":
                try:
                    data = watcher.pdf_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                except FileNotFoundError:
                    self.send_response(404)
                    self.end_headers()

            elif path == "/status":
                body = json.dumps({
                    "mtime": watcher.mtime,
                    "compile_error": watcher.compile_error,
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            path = self.path.split("?")[0]

            if path == "/recompile":
                result = watcher.recompile()
                body = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            # Suppress default access logs
            pass

    return Handler


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LaTeX Paper Viewer")
    parser.add_argument("file", type=str, help="Path to .tex or .pdf file")
    parser.add_argument("--port", type=int, default=8088, help="Port for the web server (default: 8088)")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    tex_path = Path(args.file).resolve()
    if not tex_path.exists():
        print(f"Error: {tex_path} not found", file=sys.stderr)
        sys.exit(1)
    if tex_path.suffix.lower() not in (".tex", ".pdf"):
        print(f"Error: expected a .tex or .pdf file, got {tex_path.suffix}", file=sys.stderr)
        sys.exit(1)

    # PDF output goes to a temp directory to avoid polluting the source tree
    tmp_dir = Path(tempfile.mkdtemp(prefix="latex_viewer_"))
    pdf_path = tmp_dir / "output.pdf"

    print(f"Source:  {tex_path}")
    print(f"Output:  {pdf_path}")

    if tex_path.suffix.lower() == ".tex":
        print("Compiling LaTeX...")
    watcher = TexWatcher(tex_path, pdf_path)

    if watcher.compile_error:
        print(f"\nCompilation error:\n{watcher.compile_error}", file=sys.stderr)
        print("\nStarting viewer anyway — you can fix errors and click Recompile.\n")
    else:
        print("Compilation successful.")

    # Start file watcher thread
    watcher_thread = threading.Thread(target=watcher.run_watcher, daemon=True)
    watcher_thread.start()

    # Start HTTP server
    handler = make_handler(watcher, tex_path.name)
    server = http.server.HTTPServer(("127.0.0.1", args.port), handler)

    url = f"http://127.0.0.1:{args.port}"
    print(f"\nViewer running at: {url}")
    print("Press Ctrl+C to stop.\n")

    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
    finally:
        # Clean up temp files
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
