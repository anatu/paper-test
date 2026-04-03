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
    from dotenv import load_dotenv

    load_dotenv()  # Load .env for all subcommands (API keys, credentials)


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
        basename = _report_basename(report)
        if fmt in ("json", "both"):
            json_path = out / f"{basename}.json"
            json_path.write_text(render_json(report))
            console.print(f"  JSON report: {json_path}")
        if fmt in ("md", "both"):
            md_path = out / f"{basename}.md"
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


@main.group()
def reward():
    """Reward model commands — fetch, process, train, eval."""
    pass


@reward.command()
@click.option("--venue", default="iclr", help="Venue name (e.g. iclr, neurips)")
@click.option("--years", default="2024-2025", help="Year range (e.g. 2024-2025)")
def fetch(venue: str, years: str):
    """Fetch peer review data from OpenReview."""
    try:
        from papercheck.reward_model.data_ingestion import OpenReviewScraper
    except ImportError as e:
        console.print(f"[red]Missing dependency:[/red] {e}")
        sys.exit(1)

    import os
    try:
        scraper = OpenReviewScraper(
            username=os.environ.get("OPENREVIEW_USERNAME", ""),
            password=os.environ.get("OPENREVIEW_PASSWORD", ""),
            cache_dir=Path("data/openreview"),
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    start_year, end_year = _parse_year_range(years)
    for year in range(start_year, end_year + 1):
        console.print(f"Fetching {venue} {year}...")
        try:
            data = scraper.fetch_venue(venue, year)
        except RuntimeError as e:
            console.print(f"  [red]Failed:[/red] {e}")
            continue
        console.print(f"  Papers: {len(data.papers)}, Reviews: {data.total_reviews}")


@reward.command()
@click.option("--data-dir", default="data/openreview", help="Raw data directory")
@click.option("--output", default="data/openreview/processed", help="Output directory")
@click.option(
    "--source",
    multiple=True,
    help="Venue:year(s) pair, e.g. iclr:2024 or neurips:2023-2025. Repeatable.",
)
@click.option("--venue", default=None, help="[Deprecated] Use --source instead")
@click.option("--years", default=None, help="[Deprecated] Use --source instead")
def process(data_dir: str, output: str, source: tuple[str, ...], venue: str | None, years: str | None):
    """Process raw OpenReview data into training-ready format.

    Examples:

        papercheck reward process --source iclr:2024 --source neurips:2024

        papercheck reward process --source iclr:2023-2025
    """
    from papercheck.reward_model.data_processing import (
        ReviewDataProcessor,
        ProcessedDataset,
        load_venue_data_from_disk,
    )

    # Build list of (venue, year) pairs from --source flags or legacy --venue/--years
    venue_year_pairs: list[tuple[str, int]] = []
    if source:
        for s in source:
            if ":" not in s:
                console.print(f"[red]Invalid --source format:[/red] {s!r}. Expected venue:year(s), e.g. iclr:2024")
                sys.exit(1)
            v, yr_str = s.split(":", 1)
            start_y, end_y = _parse_year_range(yr_str)
            for y in range(start_y, end_y + 1):
                venue_year_pairs.append((v.strip().lower(), y))
    elif venue:
        yr = years or "2024-2025"
        start_y, end_y = _parse_year_range(yr)
        for y in range(start_y, end_y + 1):
            venue_year_pairs.append((venue, y))
    else:
        console.print("[red]Provide at least one --source (e.g. --source iclr:2024)[/red]")
        sys.exit(1)

    processor = ReviewDataProcessor()
    data_path = Path(data_dir)
    output_path = Path(output)
    all_papers = []
    all_venues = set()
    all_years = set()

    for v, y in venue_year_pairs:
        console.print(f"Loading {v} {y} from {data_path}...")
        try:
            venue_data = load_venue_data_from_disk(data_path, v, y)
        except FileNotFoundError as e:
            console.print(f"  [yellow]Skipped:[/yellow] {e}")
            continue
        console.print(f"  Loaded {len(venue_data.papers)} papers")
        dataset = processor.process_venue(venue_data)
        console.print(f"  After filtering: {len(dataset.papers)} papers")
        all_papers.extend(dataset.papers)
        all_venues.add(v)
        all_years.add(y)

    if not all_papers:
        console.print("[red]No papers found. Run `papercheck reward fetch` first.[/red]")
        sys.exit(1)

    combined = ProcessedDataset(
        papers=all_papers,
        venue="+".join(sorted(all_venues)),
        years=sorted(all_years),
    )
    processor.save_processed(combined, output_path)
    splits = processor.create_splits(combined)
    processor.save_splits(splits, output_path)

    console.print(f"\nProcessed {len(all_papers)} papers -> {output_path}")
    console.print(f"  Train: {len(splits.train)}, Val: {len(splits.val)}, Test: {len(splits.test)}")


@reward.command(name="train")
@click.option(
    "--config",
    "config_path",
    default="papercheck/reward_model/configs/small.yaml",
    help="Training config YAML file",
)
def train_cmd(config_path: str):
    """Train the reward model."""
    try:
        from papercheck.reward_model.train import RewardModelTrainer, TrainingConfig
    except ImportError as e:
        console.print(f"[red]Missing dependency:[/red] {e}")
        console.print("Install with: pip install -e '.[reward]'")
        sys.exit(1)

    config = TrainingConfig.from_yaml(config_path)
    console.print(f"Training with config: {config_path}")
    console.print(f"  Backbone: {config.backbone}")
    console.print(f"  Device: {config.device}")
    console.print(f"  Epochs: {config.num_epochs}")

    # Load processed data
    from papercheck.reward_model.data_processing import load_splits
    data_dir = Path(config.data_dir)
    try:
        splits = load_splits(data_dir)
    except FileNotFoundError as e:
        console.print(f"[red]No processed data:[/red] {e}")
        console.print("Run `papercheck reward process` first.")
        sys.exit(1)

    console.print(f"  Train: {len(splits.train)}, Val: {len(splits.val)}, Test: {len(splits.test)}")

    # Extract features
    from papercheck.reward_model.feature_extraction import PaperFeatureExtractor
    console.print(f"Extracting features (backbone: {config.backbone})...")
    extractor = PaperFeatureExtractor(backbone=config.backbone, max_length=config.max_length)
    train_features = extractor.batch_extract(splits.train)
    val_features = extractor.batch_extract(splits.val)

    # Compute and save normalization stats
    norm_stats = extractor.compute_normalization_stats(splits.train)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    norm_stats.save(output_dir / "norm_stats.json")

    # Re-extract with normalization applied
    train_features = extractor.batch_extract(splits.train)
    val_features = extractor.batch_extract(splits.val)

    # Train
    console.print("Training...")
    trainer = RewardModelTrainer(config)
    result = trainer.train(train_features, val_features)

    console.print(f"\nTraining complete:")
    console.print(f"  Best epoch: {result.best_epoch}")
    console.print(f"  Best val loss: {result.best_val_loss:.4f}")
    console.print(f"  Early stopped: {result.early_stopped}")
    console.print(f"  Checkpoint: {output_dir / 'checkpoint_best.pt'}")

    # Calibrate on validation set
    try:
        from papercheck.reward_model.calibration import ScoreCalibrator
        from papercheck.reward_model.inference import RewardModelInference

        console.print("Calibrating on validation set...")
        inferencer = RewardModelInference(model_dir=output_dir, device=config.device)
        inferencer.load(backbone=config.backbone, dropout=config.dropout)

        val_preds: dict[str, list[float]] = {d: [] for d in ["overall", "soundness", "presentation", "contribution", "accept_prob"]}
        val_labels: dict[str, list[float]] = {d: [] for d in ["overall", "soundness", "presentation", "contribution", "accept_prob"]}

        for feat in val_features:
            pred = inferencer.predict(feat)
            for dim in val_preds:
                val_preds[dim].append(getattr(pred, dim))
            val_labels["overall"].append(feat.labels.overall_rating)
            val_labels["soundness"].append(feat.labels.soundness if feat.labels.soundness is not None else float("nan"))
            val_labels["presentation"].append(feat.labels.presentation if feat.labels.presentation is not None else float("nan"))
            val_labels["contribution"].append(feat.labels.contribution if feat.labels.contribution is not None else float("nan"))
            val_labels["accept_prob"].append(feat.labels.accept_probability)

        calibrator = ScoreCalibrator()
        calibrator.fit(val_preds, val_labels)
        calibrator.save(output_dir / "calibration.pkl")
        console.print(f"  Calibration saved: {output_dir / 'calibration.pkl'}")
    except ImportError:
        console.print("[yellow]scikit-learn not installed — skipping calibration[/yellow]")


@reward.command(name="eval")
@click.option("--model-dir", default="models/reward_model", help="Model directory")
@click.option("--data-dir", default="data/openreview/processed", help="Processed data directory")
@click.option("--backbone", default="allenai/specter2", help="Model backbone")
def eval_cmd(model_dir: str, data_dir: str, backbone: str):
    """Evaluate a trained reward model on the test set."""
    model_path = Path(model_dir)
    checkpoint = model_path / "checkpoint_best.pt"
    if not checkpoint.exists():
        console.print(f"[red]Checkpoint not found:[/red] {checkpoint}")
        console.print("Run `papercheck reward train` first.")
        sys.exit(1)

    try:
        from papercheck.reward_model.inference import RewardModelInference
        from papercheck.reward_model.feature_extraction import PaperFeatureExtractor, NormStats
        from papercheck.reward_model.data_processing import load_splits
    except ImportError as e:
        console.print(f"[red]Missing dependency:[/red] {e}")
        console.print("Install with: pip install -e '.[reward]'")
        sys.exit(1)

    # Load test data
    try:
        splits = load_splits(Path(data_dir))
    except FileNotFoundError as e:
        console.print(f"[red]No processed data:[/red] {e}")
        sys.exit(1)

    console.print(f"Evaluating on {len(splits.test)} test papers...")

    # Extract features
    extractor = PaperFeatureExtractor(backbone=backbone)
    norm_path = model_path / "norm_stats.json"
    if norm_path.exists():
        extractor.set_norm_stats(NormStats.load(norm_path))
    test_features = extractor.batch_extract(splits.test)

    # Load model and predict
    inferencer = RewardModelInference(model_dir=model_path)
    inferencer.load(backbone=backbone)

    import json
    dims = ["overall", "soundness", "presentation", "contribution", "accept_prob"]
    all_preds = {d: [] for d in dims}
    all_labels = {d: [] for d in dims}

    for feat in test_features:
        pred = inferencer.predict(feat)
        for dim in dims:
            all_preds[dim].append(getattr(pred, dim))
        all_labels["overall"].append(feat.labels.overall_rating)
        all_labels["soundness"].append(feat.labels.soundness if feat.labels.soundness is not None else float("nan"))
        all_labels["presentation"].append(feat.labels.presentation if feat.labels.presentation is not None else float("nan"))
        all_labels["contribution"].append(feat.labels.contribution if feat.labels.contribution is not None else float("nan"))
        all_labels["accept_prob"].append(feat.labels.accept_probability)

    # Compute metrics
    metrics = {}
    for dim in dims:
        preds = all_preds[dim]
        labels = all_labels[dim]
        # Filter NaN
        valid = [(p, l) for p, l in zip(preds, labels) if l == l]
        if len(valid) < 5:
            continue
        p_arr, l_arr = zip(*valid)
        mse = sum((p - l) ** 2 for p, l in zip(p_arr, l_arr)) / len(p_arr)

        # Pearson correlation
        n = len(p_arr)
        mean_p = sum(p_arr) / n
        mean_l = sum(l_arr) / n
        cov = sum((p - mean_p) * (l - mean_l) for p, l in zip(p_arr, l_arr)) / n
        std_p = (sum((p - mean_p) ** 2 for p in p_arr) / n) ** 0.5
        std_l = (sum((l - mean_l) ** 2 for l in l_arr) / n) ** 0.5
        pearson_r = cov / (std_p * std_l) if std_p > 0 and std_l > 0 else 0.0

        metrics[dim] = {"mse": round(mse, 6), "pearson_r": round(pearson_r, 4), "n": n}

    # Print results
    table = Table(title="Evaluation Results")
    table.add_column("Dimension", style="bold")
    table.add_column("MSE", justify="right")
    table.add_column("Pearson r", justify="right")
    table.add_column("N", justify="right")

    for dim in dims:
        if dim in metrics:
            m = metrics[dim]
            table.add_row(dim, f"{m['mse']:.4f}", f"{m['pearson_r']:.4f}", str(m["n"]))
    console.print(table)

    # Save eval report
    eval_path = model_path / "eval_report.json"
    eval_path.write_text(json.dumps(metrics, indent=2))
    console.print(f"\nEval report saved: {eval_path}")


def _parse_year_range(years: str) -> tuple[int, int]:
    """Parse '2024-2025' into (2024, 2025)."""
    parts = years.split("-")
    if len(parts) == 1:
        y = int(parts[0])
        return y, y
    return int(parts[0]), int(parts[1])


def _report_basename(report: DiagnosticReport) -> str:
    """Generate a filename like 'ai_2024' from report metadata.

    Uses first author's last name + publication year.
    Falls back to 'report' if either is unavailable.
    """
    import re as _re

    parts = []

    # First author last name
    if report.authors:
        first_author = report.authors[0]
        # Handle "First Last" and "Last, First" formats
        if "," in first_author:
            lastname = first_author.split(",")[0].strip()
        else:
            lastname = first_author.split()[-1].strip() if first_author.split() else ""
        if lastname:
            # Sanitize for filesystem
            lastname = _re.sub(r"[^\w\-]", "", lastname).lower()
            parts.append(lastname)

    # Publication year from paper metadata
    year = report.paper.year
    if year:
        parts.append(str(year))

    return "_".join(parts) if parts else "report"


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
