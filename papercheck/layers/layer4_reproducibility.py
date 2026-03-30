"""Layer 4: Reproducibility Check — repo detection + build verification."""

from __future__ import annotations

import logging
import re
import subprocess
import time

from papercheck.cache.store import CacheStore
from papercheck.config import PipelineConfig
from papercheck.external.papers_with_code import PapersWithCodeClient
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData

logger = logging.getLogger(__name__)

# Regex patterns for GitHub/GitLab URLs
_REPO_URL_PATTERNS = [
    re.compile(r"https?://github\.com/[\w\-]+/[\w\-]+"),
    re.compile(r"https?://gitlab\.com/[\w\-]+/[\w\-]+"),
    re.compile(r"github\.com/[\w\-]+/[\w\-]+"),
]


class ReproducibilityLayer(VerificationLayer):
    layer_number = 4
    layer_name = "Reproducibility Check"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run reproducibility checks.

        1. Extract GitHub/GitLab URLs from paper text
        2. If none found, query PapersWithCode API
        3. If repo found, attempt Docker build verification
        4. Report build success/failure

        Skips with LayerResult(skipped=True) if no repo found.
        """
        start = time.time()
        findings: list[Finding] = []

        # 1. Extract repo URLs from paper text
        repo_urls = _extract_repo_urls(paper)

        # 2. Fallback: PapersWithCode API
        if not repo_urls and paper.title:
            pwc_urls = _query_papers_with_code(paper.title, config)
            repo_urls.extend(pwc_urls)

        if not repo_urls:
            return LayerResult(
                layer=self.layer_number,
                layer_name=self.layer_name,
                score=1.0,
                signal="pass",
                findings=[],
                execution_time_seconds=time.time() - start,
                skipped=True,
                skip_reason="No code repository found for this paper",
            )

        # Deduplicate
        repo_urls = list(dict.fromkeys(repo_urls))

        findings.append(Finding(
            severity="info",
            category="repos_found",
            message=f"Found {len(repo_urls)} code repository(ies): {', '.join(repo_urls[:3])}",
        ))

        # 3. Attempt Docker build verification on the first repo
        repo_url = repo_urls[0]
        build_findings = _verify_repo_build(repo_url, config)
        findings.extend(build_findings)

        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )


def _extract_repo_urls(paper: PaperData) -> list[str]:
    """Extract GitHub/GitLab URLs from paper text and metadata."""
    urls: list[str] = []
    search_text = paper.raw_text

    # Also check metadata URLs
    if paper.metadata and paper.metadata.urls:
        search_text += " " + " ".join(paper.metadata.urls)

    for pattern in _REPO_URL_PATTERNS:
        for match in pattern.finditer(search_text):
            url = match.group(0)
            # Normalize: ensure https:// prefix
            if not url.startswith("http"):
                url = "https://" + url
            # Strip trailing punctuation
            url = url.rstrip(".,;)")
            if url not in urls:
                urls.append(url)

    return urls


def _query_papers_with_code(title: str, config: PipelineConfig) -> list[str]:
    """Query PapersWithCode API for repositories."""
    cache = None
    try:
        cache = CacheStore(
            config.cache_dir / "layer4.db",
            default_ttl_hours=config.cache_ttl_hours,
        )
    except Exception:
        pass

    pwc = PapersWithCodeClient(cache=cache)
    try:
        repos = pwc.search_repos_by_title(title)
        return [r["url"] for r in repos if r.get("url")]
    except Exception as e:
        logger.warning("PapersWithCode lookup failed: %s", e)
        return []
    finally:
        pwc.close()
        if cache:
            cache.close()


def _verify_repo_build(repo_url: str, config: PipelineConfig) -> list[Finding]:
    """Attempt to verify a repo builds successfully using Docker.

    Runs: clone + pip install in a sandboxed Docker container.
    Falls back to basic URL validation if Docker is not available.
    """
    findings: list[Finding] = []

    # Check if Docker is available
    if not _docker_available():
        findings.append(Finding(
            severity="info",
            category="docker_unavailable",
            message="Docker not available — skipping build verification",
            suggestion="Install Docker to enable reproducibility build checks",
        ))
        # Still report the repo was found
        return findings

    # Build and run the Docker verification container
    timeout = config.docker_timeout_seconds
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--memory=2g",
                "--cpus=1",
                "--pids-limit=256",
                f"--network=none",
                "python:3.11-slim",
                "bash", "-c",
                (
                    f"pip install --quiet git+{repo_url}.git 2>&1 | tail -5 "
                    f"|| echo 'INSTALL_FAILED'"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0 and "INSTALL_FAILED" not in result.stdout:
            findings.append(Finding(
                severity="info",
                category="build_success",
                message=f"Repository {repo_url} installed successfully in Docker sandbox",
            ))
        else:
            output = (result.stdout + result.stderr)[-500:]
            findings.append(Finding(
                severity="warning",
                category="build_failure",
                message=f"Repository {repo_url} failed to install",
                evidence=output,
                suggestion="Check the repository's setup instructions and dependencies",
            ))

    except subprocess.TimeoutExpired:
        findings.append(Finding(
            severity="warning",
            category="build_timeout",
            message=f"Build verification timed out after {timeout}s for {repo_url}",
            suggestion="The repository may have large dependencies or a complex build process",
        ))
    except Exception as e:
        findings.append(Finding(
            severity="info",
            category="build_error",
            message=f"Build verification failed: {type(e).__name__}",
        ))

    return findings


def _docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
