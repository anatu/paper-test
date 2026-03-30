"""CLI entry point for papercheck."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from papercheck.config import PipelineConfig
from papercheck.models import DiagnosticReport
from papercheck.parsing.paper_loader import PaperLoadError, load_paper
from papercheck.pipeline import run_pipeline
from papercheck.report.json_report import render_json
from papercheck.report.markdown_report import render_markdown

console = Console()


@click.group()
def main():
    """papercheck — Multi-layer research paper verification pipeline."""
    pass


@main.command()
@click.argument("source")
@click.option(
    "--layers",
    default=None,
    help="Comma-separated layer numbers to run (default: all). E.g. --layers 1,2",
)
@click.option("--no-halt", is_flag=True, help="Continue pipeline after layer failure")
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Directory to write report files (default: stdout only)",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "md", "both"]),
    default="both",
    help="Output format (default: both)",
)
def run(source: str, layers: str | None, no_halt: bool, output_dir: str | None, fmt: str):
    """Run the verification pipeline on a paper.

    SOURCE can be an ArXiv ID (e.g. 2301.00001), a PDF path, or a .tex path.
    """
    config = PipelineConfig.from_env()
    if no_halt:
        config.halt_on_fail = False

    layer_list = None
    if layers:
        try:
            layer_list = [int(x.strip()) for x in layers.split(",")]
        except ValueError:
            console.print("[red]Error:[/red] --layers must be comma-separated integers")
            sys.exit(1)

    # Load paper
    console.print(f"Loading paper: [bold]{source}[/bold]")
    try:
        paper = load_paper(source, config)
    except PaperLoadError as e:
        console.print(f"[red]Error loading paper:[/red] {e}")
        sys.exit(1)

    console.print(f"  Title: {paper.title or '(unknown)'}")
    console.print(f"  Type: {paper.source_type}")
    console.print(f"  Sections: {len(paper.sections)}, References: {len(paper.references)}")
    console.print()

    # Run pipeline
    console.print("Running verification pipeline...")
    report = asyncio.run(run_pipeline(paper, config, layer_list))

    # Display summary
    _print_summary(report)

    # Write output
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if fmt in ("json", "both"):
            json_path = out / "report.json"
            json_path.write_text(render_json(report))
            console.print(f"  JSON report: {json_path}")
        if fmt in ("md", "both"):
            md_path = out / "report.md"
            md_path.write_text(render_markdown(report))
            console.print(f"  Markdown report: {md_path}")
    else:
        # Print to stdout
        if fmt in ("json", "both"):
            console.print()
            console.print(render_json(report))
        if fmt == "md":
            console.print()
            console.print(render_markdown(report))


@main.group()
def cache():
    """Cache management commands."""
    pass


@cache.command()
def stats():
    """Show cache statistics."""
    config = PipelineConfig.from_env()
    db_path = config.cache_dir / "cache.db"
    if not db_path.exists():
        console.print("No cache found.")
        return
    from papercheck.cache.store import CacheStore

    store = CacheStore(db_path, config.cache_ttl_hours)
    s = store.stats()
    store.close()
    console.print(f"Total entries: {s['total_entries']}")
    console.print(f"Expired entries: {s['expired_entries']}")
    console.print(f"Size: {s['size_bytes'] / 1024:.1f} KB")


@cache.command()
def clear():
    """Clear expired cache entries."""
    config = PipelineConfig.from_env()
    db_path = config.cache_dir / "cache.db"
    if not db_path.exists():
        console.print("No cache found.")
        return
    from papercheck.cache.store import CacheStore

    store = CacheStore(db_path, config.cache_ttl_hours)
    count = store.clear_expired()
    store.close()
    console.print(f"Cleared {count} expired entries.")


def _print_summary(report: DiagnosticReport):
    """Print a rich summary table to the console."""
    signal_style = {"pass": "green", "warn": "yellow", "fail": "red"}

    table = Table(title="Verification Results")
    table.add_column("Layer", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Signal")
    table.add_column("Findings")

    for lr in report.layer_results:
        if lr.skipped:
            table.add_row(
                f"{lr.layer}. {lr.layer_name}",
                "—",
                "[dim]SKIP[/dim]",
                lr.skip_reason or "",
            )
        else:
            style = signal_style.get(lr.signal, "white")
            finding_counts = {}
            for f in lr.findings:
                finding_counts[f.severity] = finding_counts.get(f.severity, 0) + 1
            finding_str = ", ".join(f"{v} {k}" for k, v in finding_counts.items()) or "none"
            table.add_row(
                f"{lr.layer}. {lr.layer_name}",
                f"{lr.score:.2f}",
                f"[{style}]{lr.signal.upper()}[/{style}]",
                finding_str,
            )

    console.print(table)

    style = signal_style.get(report.composite_signal, "white")
    console.print(
        f"\nComposite: [{style}]{report.composite_score:.2f} "
        f"{report.composite_signal.upper()}[/{style}] "
        f"({report.total_execution_time_seconds:.1f}s)"
    )


if __name__ == "__main__":
    main()
