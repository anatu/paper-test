#!/usr/bin/env python3
"""
Fetch arXiv papers with LaTeX source.

Usage:
    python fetch_arxiv.py "large language models" --max 10
    python fetch_arxiv.py "transformer architecture" --max 5 --category cs.CL
    python fetch_arxiv.py "neural scaling laws" --out data/scaling
"""

import argparse
import gzip
import io
import os
import re
import tarfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_EPRINT = "https://export.arxiv.org/e-print/"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def search_arxiv(query: str, category: str | None = None, max_results: int = 10,
                 sort_by: str = "relevance") -> list[dict]:
    """Search arXiv and return paper metadata."""
    search_query = f"all:{query}"
    if category:
        search_query = f"cat:{category} AND {search_query}"

    params = urllib.parse.urlencode({
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API}?{params}"

    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-test/1.0"})
            with urllib.request.urlopen(req) as resp:
                tree = ET.parse(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                wait = 3 * (attempt + 1)
                print(f"  Rate limited, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

    root = tree.getroot()
    papers = []
    for entry in root.findall("atom:entry", NS):
        arxiv_id = entry.find("atom:id", NS).text.strip().split("/abs/")[-1]
        # Strip version suffix for e-print download
        arxiv_id_base = re.sub(r"v\d+$", "", arxiv_id)
        title = " ".join(entry.find("atom:title", NS).text.split())
        summary = " ".join(entry.find("atom:summary", NS).text.split())
        authors = [a.find("atom:name", NS).text
                    for a in entry.findall("atom:author", NS)]
        published = entry.find("atom:published", NS).text[:10]
        categories = [c.get("term")
                      for c in entry.findall("atom:category", NS)]

        papers.append({
            "id": arxiv_id_base,
            "title": title,
            "authors": authors,
            "summary": summary,
            "published": published,
            "categories": categories,
        })
    return papers


def download_source(arxiv_id: str, out_dir: Path) -> Path | None:
    """Download and extract LaTeX source for a paper. Returns the paper directory."""
    paper_dir = out_dir / arxiv_id.replace("/", "_")
    if paper_dir.exists() and any(paper_dir.glob("*.tex")):
        print(f"  Already downloaded: {paper_dir}")
        return paper_dir

    paper_dir.mkdir(parents=True, exist_ok=True)
    url = f"{ARXIV_EPRINT}{arxiv_id}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "paper-test/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        print(f"  Failed to download {arxiv_id}: HTTP {e.code}")
        return None

    # arXiv returns either a .tar.gz, a single .gz file, or raw TeX
    try:
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
        tar.extractall(path=paper_dir, filter="data")
        tar.close()
    except tarfile.TarError:
        # Might be a single gzipped file
        try:
            content = gzip.decompress(data)
            (paper_dir / "main.tex").write_bytes(content)
        except gzip.BadGzipFile:
            # Raw TeX
            (paper_dir / "main.tex").write_bytes(data)

    tex_files = list(paper_dir.glob("*.tex"))
    if not tex_files:
        print(f"  No .tex files found for {arxiv_id}")
        return None

    return paper_dir


def find_main_tex(paper_dir: Path) -> Path | None:
    """Identify the main .tex file in a paper directory."""
    tex_files = list(paper_dir.glob("*.tex"))
    if not tex_files:
        return None
    if len(tex_files) == 1:
        return tex_files[0]
    # Look for \documentclass
    for f in tex_files:
        content = f.read_text(errors="ignore")
        if r"\documentclass" in content:
            return f
    return tex_files[0]


def save_metadata(papers: list[dict], out_dir: Path):
    """Save a manifest of downloaded papers."""
    manifest = out_dir / "manifest.tsv"
    with open(manifest, "w") as f:
        f.write("id\tpublished\ttitle\tauthors\tcategories\n")
        for p in papers:
            authors = "; ".join(p["authors"][:5])
            if len(p["authors"]) > 5:
                authors += f" (+{len(p['authors']) - 5} more)"
            cats = ", ".join(p["categories"][:3])
            f.write(f"{p['id']}\t{p['published']}\t{p['title']}\t{authors}\t{cats}\n")
    print(f"\nManifest saved to {manifest}")


def main():
    parser = argparse.ArgumentParser(description="Fetch arXiv papers with LaTeX source")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--max", type=int, default=10, help="Max papers to fetch (default: 10)")
    parser.add_argument("--category", help="arXiv category filter (e.g. cs.CL, cs.LG, stat.ML)")
    parser.add_argument("--out", default="data/arxiv", help="Output directory (default: data/arxiv)")
    parser.add_argument("--sort", choices=["relevance", "lastUpdatedDate", "submittedDate"],
                        default="relevance", help="Sort order (default: relevance)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching arXiv for: {args.query}")
    if args.category:
        print(f"Category filter: {args.category}")

    papers = search_arxiv(args.query, category=args.category,
                          max_results=args.max, sort_by=args.sort)
    print(f"Found {len(papers)} papers\n")

    downloaded = []
    for i, paper in enumerate(papers, 1):
        print(f"[{i}/{len(papers)}] {paper['title'][:80]}")
        print(f"  ID: {paper['id']}  |  {paper['published']}  |  {', '.join(paper['categories'][:3])}")

        paper_dir = download_source(paper["id"], out_dir)
        if paper_dir:
            main_tex = find_main_tex(paper_dir)
            tex_count = len(list(paper_dir.glob("*.tex")))
            print(f"  Saved to {paper_dir} ({tex_count} .tex file{'s' if tex_count != 1 else ''})")
            if main_tex:
                print(f"  Main file: {main_tex.name}")
            downloaded.append(paper)
        else:
            print("  Skipped (no source available)")

        # Be polite to arXiv API
        if i < len(papers):
            time.sleep(3)

    save_metadata(downloaded, out_dir)
    print(f"\nDone: {len(downloaded)}/{len(papers)} papers downloaded to {out_dir}")


if __name__ == "__main__":
    main()
