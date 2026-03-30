# PLAN.md — Multi-Layer Research Paper Verification Pipeline (PoC)

**Codename**: `papercheck`
**Target domain**: ML/CS papers from ArXiv
**Status**: Planning

---

## 0. Relationship to Existing Repository

This project lives inside the existing `paper-test` repo (github.com/anatu/paper-test), which is an academic paper authoring workspace. The existing top-level layout is:

```
paper-test/                         # repo root — existing files untouched
├── CLAUDE.md                       # project instructions for Claude Code
├── README.md                       # repo overview
├── PLAN.md                         # this file
├── fetch_arxiv.py                  # ★ EXISTING — ArXiv search + LaTeX source download
├── visualize.py                    # ★ EXISTING — live-reloading LaTeX→PDF viewer
├── papers/                         # ★ EXISTING — LaTeX source files for authored papers
├── references/                     # ★ EXISTING — style/structure/citation/LaTeX guides
├── data/                           # ★ EXISTING — downloaded ArXiv papers (LaTeX source)
│   └── arxiv/                      #   manifest.tsv tracks fetched papers
└── .claude/skills/                 # ★ EXISTING — custom Claude Code skills
```

**Key reuse decisions**:
- **`fetch_arxiv.py`** already implements ArXiv API search, source download, tar/gz extraction, and manifest tracking. The pipeline reuses it directly (imported as a module) rather than creating a separate `external/arxiv_api.py`.
- **`data/arxiv/`** is the existing store for downloaded ArXiv paper source. Layer 3's claim corpus is built from papers already in `data/arxiv/` (fetched via `fetch_arxiv.py`), plus any additional papers fetched during corpus building.
- **`papers/`** contains the user's own authored papers — these can also be fed into the pipeline for self-verification.
- **`visualize.py`** is unrelated to the pipeline but coexists at the repo root.

The verification pipeline is added as a Python package under `papercheck/`, keeping it cleanly separated from the existing authoring tools.

---

## 1. Project Structure

New files added by this PoC (all under `papercheck/` unless noted):

```
papercheck/                         # new Python package — the verification pipeline
├── __init__.py
├── cli.py                          # CLI entry point (click-based)
├── pipeline.py                     # Orchestrator: runs layers sequentially, handles halt/override
├── config.py                       # Global config: API keys, weights, thresholds, timeouts
├── models.py                       # Shared data models (Pydantic): PaperData, LayerResult, DiagnosticReport
├── parsing/
│   ├── __init__.py
│   ├── pdf_parser.py               # PyMuPDF-based raw text extraction from PDF
│   ├── grobid_parser.py            # GROBID TEI XML structured parsing (sections, refs, equations)
│   ├── latex_parser.py             # LaTeX source parsing (when .tex source is available)
│   └── paper_loader.py             # Unified loader: accepts ArXiv ID, PDF path, or .tex path → PaperData
│                                   #   Uses fetch_arxiv.py (repo root) for ArXiv downloads
├── layers/
│   ├── __init__.py
│   ├── base.py                     # Abstract base class for all layers
│   ├── layer1_formal.py            # Layer 1: Formal consistency checks
│   ├── layer2_citations.py         # Layer 2: Citation verification
│   ├── layer3_corpus.py            # Layer 3: Cross-paper consistency (skeleton)
│   ├── layer4_reproducibility.py   # Layer 4: Reproducibility check (skeleton)
│   └── layer5_logic.py             # Layer 5: Logical structure verification (skeleton)
├── extractors/
│   ├── __init__.py
│   ├── statistics.py               # Extract reported stats (p-values, CIs, effect sizes, etc.)
│   ├── claims.py                   # Extract empirical claims via LLM
│   ├── equations.py                # Extract and track equations/variables
│   ├── references.py               # Extract citation keys and in-text citation contexts
│   └── metadata.py                 # Extract abstract, contributions, conclusions
├── checkers/
│   ├── __init__.py
│   ├── statcheck.py                # Statistical consistency logic (Python port of statcheck)
│   ├── math_consistency.py         # Variable naming, equation reuse, dimensional analysis
│   ├── xref_integrity.py           # Internal cross-reference resolution
│   └── claim_alignment.py          # Abstract↔conclusion, hypothesis↔experiment alignment
├── external/
│   ├── __init__.py
│   ├── semantic_scholar.py         # Semantic Scholar API client (search, paper details, recommendations)
│   ├── crossref.py                 # CrossRef API client (DOI resolution, fallback citation check)
│   ├── openal.py                  # OpenAlex API client (fallback citation/corpus data)
│   └── papers_with_code.py         # PapersWithCode API client (repo detection)
├── llm/
│   ├── __init__.py
│   ├── client.py                   # Anthropic API wrapper: retry, rate-limit, cost tracking
│   ├── prompts.py                  # Prompt template registry (all prompt specs centralized)
│   └── schemas.py                  # Pydantic models for expected LLM output structures
├── scoring/
│   ├── __init__.py
│   └── composite.py                # Per-layer normalization, weighted composite, report generation
├── cache/
│   ├── __init__.py
│   └── store.py                    # Disk-based cache (SQLite) for API responses and LLM results
├── report/
│   ├── __init__.py
│   ├── json_report.py              # Structured JSON diagnostic output
│   └── markdown_report.py          # Human-readable Markdown report renderer
├── tests/
│   ├── conftest.py                 # Shared fixtures: sample papers, mock API responses
│   ├── test_parsing.py             # Parser unit tests
│   ├── test_layer1.py              # Layer 1 tests with known-bad papers
│   ├── test_layer2.py              # Layer 2 tests with fabricated/valid citations
│   ├── test_layer3.py              # Layer 3 skeleton tests
│   ├── test_layer4.py              # Layer 4 skeleton tests
│   ├── test_layer5.py              # Layer 5 skeleton tests
│   ├── test_pipeline.py            # End-to-end integration tests
│   ├── test_statcheck.py           # Statistical checker unit tests
│   └── fixtures/                   # Test PDFs, .tex files, mock API responses
│       ├── sample_clean.tex        # Well-formed paper (should pass all layers)
│       ├── sample_statbug.tex      # Paper with known statistical error
│       ├── sample_dangling_ref.tex # Paper with broken cross-references
│       ├── sample_fake_cite.tex    # Paper with hallucinated citations
│       └── mock_responses/         # Cached API response fixtures
├── examples/
│   ├── run_examples.sh             # Script to run pipeline on 3-5 annotated papers
│   └── annotated/                  # Expected outputs + annotations for example papers
└── docker/
    ├── Dockerfile.grobid           # GROBID service container
    └── Dockerfile.repro            # Sandboxed reproducibility runner

# Also added at repo root:
pyproject.toml                      # Project metadata, dependencies, papercheck CLI entry point
```

**Notes**:
- No new `README.md` is created inside `papercheck/` — the existing repo-root `README.md` is updated to document the pipeline alongside the existing authoring tools. `PLAN.md` stays at repo root.
- `.papercheck_cache/` (the default cache directory) must be added to `.gitignore` during setup, alongside the existing `data/` entry.

---

## 2. Dependency List

### Python Packages (pyproject.toml)

```toml
[project]
requires-python = ">=3.11"

[project.dependencies]
# CLI
click = ">=8.1"

# Data models
pydantic = ">=2.5"

# PDF parsing
pymupdf = ">=1.23"           # PyMuPDF (fitz)

# LaTeX parsing
pylatexenc = ">=2.10"        # LaTeX to text decoding
tex2py = ">=0.5"             # LaTeX AST parsing (lightweight)

# XML parsing (GROBID TEI output)
lxml = ">=5.0"

# LLM
anthropic = ">=0.40"         # Anthropic Python SDK

# External APIs
httpx = ">=0.27"             # Async HTTP client (all API calls)
tenacity = ">=8.2"           # Retry logic for API calls

# Vector store (Layer 3)
chromadb = ">=0.4"

# Embeddings
sentence-transformers = ">=2.3"  # Local embeddings for claim vectors

# Caching
diskcache = ">=5.6"          # Simple disk cache (alternative to raw SQLite)

# Report generation
jinja2 = ">=3.1"             # Markdown report templating

# Utilities
rich = ">=13.0"              # CLI progress bars, formatted output
regex = ">=2023.0"           # Advanced regex for statistical extraction

[project.optional-dependencies]
dev = [
    "pytest >= 8.0",
    "pytest-asyncio >= 0.23",
    "pytest-mock >= 3.12",
    "ruff >= 0.4",
]
```

### External Tools

| Tool | Version | Purpose | Required? |
|------|---------|---------|-----------|
| **GROBID** | 0.8.x | Structured PDF→TEI XML parsing | Required for PDF input (run via Docker) |
| **Docker** | 24+ | GROBID hosting + reproducibility sandbox | Required |
| **pdflatex** | TeX Live 2023+ | Compile .tex fixtures for testing | Optional (only for test fixture generation) |

### API Keys Required

| API | Key env var | Free tier? | Purpose |
|-----|-------------|------------|---------|
| **Anthropic** | `ANTHROPIC_API_KEY` | No (paid) | All LLM analysis steps |
| **Semantic Scholar** | `S2_API_KEY` | Yes (rate-limited without key, higher limits with key) | Citation verification, paper search |
| **CrossRef** | None (polite pool: set `mailto` header) | Yes | DOI resolution fallback |
| **OpenAlex** | None (polite pool: set `mailto` header) | Yes | Citation/corpus fallback |

---

## 3. Implementation Phases

### Phase 1: Skeleton End-to-End (Week 1)

**Goal**: A single CLI command processes an ArXiv ID and produces a report. Every layer exists but does minimal work. The pipeline orchestration, data model, caching, and reporting are all functional.

**Deliverables**:
- `models.py` with all core data structures
- `parsing/paper_loader.py` — resolve ArXiv IDs via `fetch_arxiv.py` (reuse existing), extract raw text via PyMuPDF, return `PaperData`
- `layers/base.py` — abstract layer interface
- All 5 layer files with stub implementations that return placeholder `LayerResult` objects
- `pipeline.py` — sequential execution with halt-on-fail logic
- `scoring/composite.py` — weighted scoring with configurable weights
- `report/json_report.py` and `report/markdown_report.py` — output generation
- `cli.py` — `papercheck run <arxiv_id_or_path>` command
- `cache/store.py` — disk cache with TTL
- `config.py` — env-based configuration

**Exit criteria**: `papercheck run 2301.00001` downloads the paper, runs through all 5 stub layers, and produces a JSON + Markdown report.

### Phase 2: Layer 1 Full Implementation (Week 2)

**Goal**: All Layer 1 checks are functional and tested.

**Deliverables**:
- `parsing/grobid_parser.py` — GROBID integration (Docker service)
- `parsing/latex_parser.py` — .tex source parsing
- `extractors/statistics.py` — regex + LLM extraction of reported statistics
- `extractors/equations.py` — equation/variable tracking
- `extractors/metadata.py` — abstract, contributions, conclusions extraction
- `checkers/statcheck.py` — statistical consistency verification
- `checkers/math_consistency.py` — variable/equation consistency
- `checkers/xref_integrity.py` — cross-reference resolution
- `checkers/claim_alignment.py` — abstract↔conclusion alignment (LLM-based)
- `llm/client.py`, `llm/prompts.py`, `llm/schemas.py` — LLM infrastructure
- Test suite for Layer 1 with known-error papers

**Exit criteria**: Layer 1 correctly identifies a planted statistical error, a dangling reference, and an abstract/conclusion mismatch in test fixtures.

### Phase 3: Layer 2 Full Implementation (Week 3)

**Goal**: Citation verification is functional and tested.

**Deliverables**:
- `external/semantic_scholar.py` — full client with search, details, recommendations
- `external/crossref.py` — DOI resolution
- `external/openal.py` — fallback
- `extractors/references.py` — citation context extraction
- Layer 2 implementation: existence check, claim-citation alignment, recency analysis
- Aggressive caching of API responses
- Test suite for Layer 2 with fabricated and valid citations

**Exit criteria**: Layer 2 correctly identifies a hallucinated citation and a misattributed claim in test fixtures.

### Phase 4: Layers 3-5 Skeleton Deepening (Week 4)

**Goal**: Layers 3-5 go from stubs to functional skeletons with real (but simplified) logic.

**Deliverables**:
- Layer 3: Claim extraction + ChromaDB storage + basic contradiction search (against a small pre-indexed corpus of ~100 papers fetched into `data/arxiv/` via `fetch_arxiv.py`)
- Layer 4: Repo detection (PapersWithCode API) + build verification in Docker (clone + `pip install` only, no execution)
- Layer 5: LLM-based hypothesis↔experiment alignment check + results↔conclusion check
- `external/papers_with_code.py` — repo detection client
- `docker/Dockerfile.repro` — sandbox container for Layer 4

**Exit criteria**: Each skeleton layer produces meaningful (non-stub) diagnostics for at least one test paper.

### Phase 5: Polish, Examples, Documentation (Week 5)

**Goal**: Run 3-5 real ArXiv papers through the full pipeline. Annotate results. Write documentation.

**Deliverables**:
- 3-5 example papers with annotated pipeline output in `examples/annotated/`
- Tuned scoring weights based on example runs
- Update existing repo-root `README.md` with pipeline setup instructions, architecture diagram, usage guide
- CI-friendly test suite (all tests pass without API keys using cached fixtures)

---

## 4. Per-File Specifications

### `models.py`

Core data structures shared across the entire pipeline.

```python
class PaperData(BaseModel):
    """Unified representation of a parsed paper."""
    source_type: Literal["arxiv", "pdf", "latex"]
    arxiv_id: str | None
    title: str
    authors: list[str]
    abstract: str
    sections: list[Section]           # ordered list of sections
    raw_text: str                     # full concatenated text
    references: list[Reference]       # bibliography entries
    figures: list[FigureRef]          # figure captions + labels
    tables: list[TableRef]            # table captions + labels + content if extractable
    equations: list[EquationRef]      # labeled equations
    latex_source: str | None          # raw .tex if available
    tei_xml: str | None               # GROBID TEI XML if available
    metadata: PaperMetadata           # year, venue, DOI, URLs

class Section(BaseModel):
    heading: str
    level: int                        # 1=section, 2=subsection, etc.
    text: str
    label: str | None                 # LaTeX label if available

class Reference(BaseModel):
    key: str                          # citation key (e.g., "smith2023")
    title: str | None
    authors: list[str]
    year: int | None
    venue: str | None
    doi: str | None
    raw_text: str                     # raw bibliography entry text
    in_text_contexts: list[CitationContext]  # every place this ref is cited

class CitationContext(BaseModel):
    section: str                      # which section the citation appears in
    surrounding_text: str             # ±2 sentences around the citation
    claim_text: str | None            # the specific claim attributed to this citation

class LayerResult(BaseModel):
    layer: int                        # 1-5
    layer_name: str
    score: float                      # 0.0-1.0 normalized
    signal: Literal["pass", "warn", "fail"]
    findings: list[Finding]
    execution_time_seconds: float
    skipped: bool                     # True if layer was skipped (e.g., no code repo for Layer 4)
    skip_reason: str | None

class Finding(BaseModel):
    severity: Literal["info", "warning", "error", "critical"]
    category: str                     # e.g., "statistical_error", "dangling_reference"
    message: str                      # human-readable description
    location: str | None              # section/page/line reference
    evidence: str | None              # supporting text or data
    suggestion: str | None            # recommended fix

class DiagnosticReport(BaseModel):
    paper: PaperMetadata
    layer_results: list[LayerResult]
    composite_score: float
    composite_signal: Literal["pass", "warn", "fail"]
    scoring_weights: dict[int, float]
    timestamp: str
    pipeline_version: str
    total_execution_time_seconds: float
    total_llm_cost_usd: float         # tracked from LLM client
```

### `config.py`

```python
class PipelineConfig(BaseModel):
    """Loaded from env vars + optional config file."""
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-20250514"
    s2_api_key: str | None = None
    grobid_url: str = "http://localhost:8070"
    cache_dir: Path = Path(".papercheck_cache")
    cache_ttl_hours: int = 168          # 1 week
    layer_weights: dict[int, float] = {1: 0.30, 2: 0.25, 3: 0.20, 4: 0.15, 5: 0.10}
    fail_thresholds: dict[int, float] = {1: 0.3, 2: 0.3, 3: 0.2, 4: 0.2, 5: 0.2}
    warn_thresholds: dict[int, float] = {1: 0.6, 2: 0.6, 3: 0.5, 4: 0.5, 5: 0.5}
    halt_on_fail: bool = True           # stop pipeline on layer failure
    max_concurrent_api_calls: int = 5
    docker_timeout_seconds: int = 300   # Layer 4 container timeout
```

### `parsing/paper_loader.py`

```python
async def load_paper(source: str, config: PipelineConfig) -> PaperData:
    """
    Unified entry point. Accepts:
      - ArXiv ID (e.g., "2301.00001") → downloads source via fetch_arxiv.py (repo root)
      - PDF file path → parses with PyMuPDF + GROBID
      - .tex file path → parses with latex_parser + compiles metadata
    Returns fully populated PaperData.
    Raises: PaperLoadError on download/parse failure.
    """
```

### `parsing/grobid_parser.py`

```python
async def parse_pdf_with_grobid(pdf_path: Path, grobid_url: str) -> GrobidResult:
    """
    Sends PDF to GROBID service, parses TEI XML response.
    Returns structured sections, references, equations, figures, tables.
    Raises: GrobidUnavailableError if service is down.
    Falls back gracefully: returns partial result with warnings.
    """

class GrobidResult(BaseModel):
    sections: list[Section]
    references: list[Reference]
    equations: list[EquationRef]
    figures: list[FigureRef]
    tables: list[TableRef]
    tei_xml: str
    parse_quality: float              # 0-1, GROBID's own confidence
```

### `parsing/latex_parser.py`

```python
def parse_latex_source(tex_path: Path) -> LatexParseResult:
    """
    Parse .tex source directly. Extracts:
    - Section structure via \\section{}, \\subsection{}, etc.
    - Labels and refs (\\label{}, \\ref{}, \\cite{})
    - Equations (equation/align environments)
    - Bibliography entries (from .bib or \\bibitem)
    No external service needed. Pure text processing.
    """
```

### `layers/base.py`

```python
class VerificationLayer(ABC):
    """Base class for all verification layers."""

    layer_number: int
    layer_name: str

    @abstractmethod
    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run verification. Must return LayerResult within timeout."""
        ...

    def _score_findings(self, findings: list[Finding]) -> tuple[float, str]:
        """
        Convert findings to (score, signal).
        Score: 1.0 = perfect, 0.0 = critical failures.
        Signal: "pass" if score >= warn_threshold, "warn" if >= fail_threshold, else "fail".
        Scoring formula: start at 1.0, subtract per finding based on severity:
          critical=-0.3, error=-0.15, warning=-0.05, info=0.0
        Clamp to [0.0, 1.0].
        """
```

### `layers/layer1_formal.py`

```python
class FormalConsistencyLayer(VerificationLayer):
    layer_number = 1
    layer_name = "Formal Consistency"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """
        Runs four sub-checks in parallel:
        1. statistical_audit(paper) → list[Finding]
        2. math_consistency(paper) → list[Finding]
        3. xref_integrity(paper) → list[Finding]
        4. metadata_alignment(paper, config) → list[Finding]  # uses LLM
        Merges all findings, computes score.
        """
```

### `layers/layer2_citations.py`

```python
class CitationVerificationLayer(VerificationLayer):
    layer_number = 2
    layer_name = "Citation Verification"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """
        For each reference in paper.references:
        1. Check existence via Semantic Scholar → CrossRef fallback
        2. If exists, retrieve abstract
        3. For each in_text_context, check claim-citation alignment (LLM)
        4. Assess recency/coverage of related work (LLM + S2 recommendations)
        All API calls are cached. Rate-limited to max_concurrent_api_calls.
        """
```

### `layers/layer3_corpus.py` (skeleton)

```python
class CrossPaperConsistencyLayer(VerificationLayer):
    layer_number = 3
    layer_name = "Cross-Paper Consistency"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """
        SKELETON — simplified for PoC:
        1. Extract core claims via LLM (extractors/claims.py)
        2. Embed claims using sentence-transformers
        3. Query ChromaDB for similar claims in pre-indexed corpus
        4. For top-k matches, use LLM to check for contradictions
        TODO: Benchmark result validation against leaderboards
        TODO: Methodology red flag detection
        """
```

### `layers/layer4_reproducibility.py` (skeleton)

```python
class ReproducibilityLayer(VerificationLayer):
    layer_number = 4
    layer_name = "Reproducibility Check"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """
        SKELETON — simplified for PoC:
        1. Extract GitHub/GitLab URLs from paper text
        2. If none found, query PapersWithCode API
        3. If repo found: clone into Docker container, attempt pip install
        4. Report build success/failure
        TODO: Smoke test execution
        TODO: Code-paper architecture alignment (LLM)
        Skips with LayerResult(skipped=True) if no repo found.
        """
```

### `layers/layer5_logic.py` (skeleton)

```python
class LogicalStructureLayer(VerificationLayer):
    layer_number = 5
    layer_name = "Logical Structure"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """
        SKELETON — simplified for PoC:
        1. Extract hypothesis from intro/abstract (LLM)
        2. Extract experimental setup from methods (LLM)
        3. Check hypothesis↔experiment alignment (LLM)
        4. Check results↔conclusion alignment (LLM)
        TODO: Full argumentation DAG construction
        TODO: Limitation acknowledgment check
        """
```

### `extractors/statistics.py`

```python
def extract_statistics(text: str) -> list[ReportedStatistic]:
    """
    Regex-based extraction of:
    - p-values: p < 0.05, p = 0.003, p-value of 0.01
    - Confidence intervals: 95% CI [1.2, 3.4], (1.2-3.4)
    - Test statistics: t(45) = 2.31, F(2, 97) = 4.56, χ²(3) = 8.92
    - Effect sizes: d = 0.5, η² = 0.12, r = 0.45
    - Sample sizes: n = 150, N = 1200
    - Percentages in tables
    Returns structured objects with value, location, and surrounding context.
    """

class ReportedStatistic(BaseModel):
    stat_type: str                    # "p_value", "ci", "test_statistic", "effect_size", "sample_size"
    value: float | str                # numeric value or interval
    test_type: str | None             # "t", "F", "chi_squared", etc.
    df: tuple[int, ...] | None       # degrees of freedom
    location: str                     # section + approximate position
    raw_text: str                     # the matched text
```

### `checkers/statcheck.py`

```python
def check_statistical_consistency(stats: list[ReportedStatistic]) -> list[Finding]:
    """
    For each test statistic with associated p-value:
    1. Recompute p-value from test statistic and df
    2. Compare recomputed p with reported p
    3. Flag if discrepancy exceeds tolerance (default: one significance bracket)

    Also checks:
    - Correlations in [-1, 1]
    - Proportions in [0, 1]
    - Negative variance or standard deviation
    - CI lower bound > upper bound
    - Percentages summing to >100% (±rounding tolerance)

    Uses scipy.stats for p-value recomputation.
    """
```

### `external/semantic_scholar.py`

```python
class SemanticScholarClient:
    """
    Async client for Semantic Scholar API.
    Base URL: https://api.semanticscholar.org/graph/v1

    Methods:
    - search_paper(query: str) → list[S2Paper]
    - get_paper(paper_id: str) → S2Paper | None
    - get_paper_by_title(title: str, authors: list[str]) → S2Paper | None
    - get_citations(paper_id: str) → list[S2Paper]
    - get_references(paper_id: str) → list[S2Paper]
    - get_recommended(paper_id: str, limit: int) → list[S2Paper]

    Rate limiting: 100 req/sec with key, 10 req/sec without.
    Caching: All responses cached via cache/store.py with configurable TTL.
    Retry: 3 retries with exponential backoff on 429/500/503.
    """
```

### `llm/client.py`

```python
class LLMClient:
    """
    Thin wrapper around Anthropic SDK.

    - Tracks cumulative token usage and estimated cost
    - Implements retry with exponential backoff on rate limits
    - Validates structured output against Pydantic schemas
    - Logs all prompts/responses when debug mode is enabled

    Methods:
    - async query(prompt_name: str, variables: dict, output_schema: type[BaseModel]) → BaseModel
      Looks up prompt template by name, fills variables, calls API,
      parses response into output_schema, retries once on parse failure.

    - get_cost_summary() → dict with total_input_tokens, total_output_tokens, estimated_cost_usd
    """
```

### `llm/prompts.py`

```python
"""
Central registry of all prompt templates.
Each prompt is a PromptSpec dataclass with:
  - name: str (unique key)
  - system: str (system prompt)
  - user_template: str (user message with {variable} placeholders)
  - output_schema: type[BaseModel] (expected response structure)
  - temperature: float
  - max_tokens: int

Prompts are retrieved by name via get_prompt(name: str) → PromptSpec.
See Section 7 for detailed prompt specifications.
"""
```

### `cache/store.py`

```python
class CacheStore:
    """
    SQLite-backed key-value cache with TTL.

    Table schema: (key TEXT PRIMARY KEY, value BLOB, created_at REAL, ttl_hours INT)

    Methods:
    - get(key: str) → bytes | None (returns None if expired or missing)
    - set(key: str, value: bytes, ttl_hours: int | None = None)
    - invalidate(key: str)
    - clear_expired()
    - stats() → dict with total_entries, expired_entries, size_bytes

    Keys are constructed by callers as "{namespace}:{identifier}" e.g.:
    - "s2:paper:649def34f8..." (Semantic Scholar paper by ID)
    - "s2:search:transformer+attention" (search query)
    - "llm:claim_extraction:sha256(input)" (LLM response caching)
    """
```

### `scoring/composite.py`

```python
def compute_composite_score(
    layer_results: list[LayerResult],
    weights: dict[int, float],
) -> tuple[float, str]:
    """
    Weighted average of layer scores, skipping layers with skipped=True.
    Re-normalizes weights to sum to 1.0 after excluding skipped layers.
    Returns (composite_score, composite_signal).
    Signal thresholds: pass >= 0.6, warn >= 0.3, fail < 0.3.
    """

def generate_report(
    paper: PaperData,
    layer_results: list[LayerResult],
    config: PipelineConfig,
) -> DiagnosticReport:
    """Assembles the full DiagnosticReport model."""
```

### `report/markdown_report.py`

```python
def render_markdown(report: DiagnosticReport) -> str:
    """
    Renders a Jinja2 template producing a Markdown document with:
    - Header: paper title, authors, composite score badge
    - Summary table: layer | score | signal | finding count
    - Per-layer sections with detailed findings sorted by severity
    - Each finding shows: severity icon, message, location, evidence, suggestion
    - Footer: execution time, LLM cost, pipeline version
    """
```

### `cli.py`

```python
"""
CLI entry point using Click.

Commands:
  papercheck run <source> [--layers 1,2,3,4,5] [--no-halt] [--output-dir ./out] [--format json|md|both]
    Run the verification pipeline on a paper.
    <source> can be an ArXiv ID, PDF path, or .tex path.

  papercheck index <arxiv_query> --max N [--category cs.CL]
    Build/extend the claim corpus for Layer 3. Delegates paper fetching to the
    existing fetch_arxiv.py (downloads into data/arxiv/), then extracts and
    embeds claims from fetched papers into ChromaDB.

  papercheck cache stats
    Show cache statistics.

  papercheck cache clear
    Clear expired cache entries.
"""
```

---

## 5. Data Flow Diagram

```
                            ┌─────────────┐
                            │   CLI Input  │
                            │  (ArXiv ID,  │
                            │  PDF, .tex)  │
                            └──────┬───────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │   paper_loader    │
                         │  ─────────────── │
                         │  Download/read   │
                         │  Parse (GROBID   │
                         │  or LaTeX)       │
                         └────────┬─────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │  PaperData   │◄─── Canonical representation
                          └──────┬───────┘     passed to every layer
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
     ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
     │  Extractors  │   │   Cache      │   │  LLM Client      │
     │  (stats,     │   │  (SQLite)    │   │  (Anthropic API)  │
     │  claims,     │   │              │   │                   │
     │  equations,  │   │  API resp.   │   │  Structured       │
     │  refs, meta) │   │  LLM resp.   │   │  output parsing   │
     └──────┬──────┘   └──────────────┘   └──────────────────┘
            │                  ▲ ▲                  ▲
            │                  │ │                  │
            ▼                  │ │                  │
  ┌───────────────────────────────────────────────────────────┐
  │                    PIPELINE ORCHESTRATOR                    │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────┐  ┌────┐  │
  │  │ Layer 1 │→│ Layer 2 │→│ Layer 3 │→│ L4 │→│ L5 │  │
  │  │ Formal  │  │Citation │  │ Corpus  │  │Repr│  │Logic│  │
  │  │         │  │         │  │         │  │    │  │    │  │
  │  │→Result  │  │→Result  │  │→Result  │  │→R  │  │→R  │  │
  │  └─────────┘  └─────────┘  └─────────┘  └────┘  └────┘  │
  │       │            │            │           │       │      │
  │       └────────────┴────────────┴───────────┴───────┘      │
  │                           │                                │
  │                    list[LayerResult]                        │
  └───────────────────────────┬────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Composite       │
                    │  Scoring         │
                    │  ──────────────  │
                    │  Weighted avg    │
                    │  DiagnosticReport│
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
           ┌──────────────┐  ┌───────────────┐
           │  JSON Report  │  │ Markdown Report│
           │  (structured) │  │  (human-read.) │
           └──────────────┘  └───────────────┘
```

### Data Structures Passed Between Stages

| From → To | Data Structure | Notes |
|-----------|---------------|-------|
| CLI → paper_loader | `str` (ArXiv ID / file path) | |
| paper_loader → pipeline | `PaperData` | Immutable after creation |
| pipeline → each layer | `PaperData` + `PipelineConfig` | Layers do not modify PaperData |
| each layer → pipeline | `LayerResult` | Contains score + findings |
| layer internals → extractors | `PaperData` fields (text, sections, etc.) | Extractors are stateless |
| layer internals → LLM client | prompt name + variables | Returns parsed Pydantic model |
| layer internals → external APIs | query strings, IDs | Returns cached responses |
| pipeline → scoring | `list[LayerResult]` + config weights | |
| scoring → report | `DiagnosticReport` | Complete output model |

### Caching Strategy

| What | Cache Key Pattern | TTL | Size Estimate |
|------|-------------------|-----|---------------|
| Semantic Scholar paper lookups | `s2:paper:{s2_id}` | 7 days | ~2KB per paper |
| Semantic Scholar search results | `s2:search:{query_hash}` | 24 hours | ~5KB per query |
| CrossRef DOI lookups | `crossref:doi:{doi}` | 30 days | ~1KB per DOI |
| LLM responses (claim extraction) | `llm:{prompt_name}:{input_hash}` | 30 days | ~3KB per response |
| LLM responses (alignment checks) | `llm:{prompt_name}:{input_hash}` | 30 days | ~2KB per response |
| GROBID parse results | `grobid:{pdf_hash}` | 90 days | ~50KB per paper |
| ArXiv paper downloads | File-system cache in `cache_dir/arxiv/` | 90 days | ~1MB per paper |

---

## 6. API Usage Plan

### Semantic Scholar API

**Endpoints used**:
- `GET /paper/search?query={title}` — find papers by title (citation existence check)
- `GET /paper/{id}?fields=title,abstract,authors,year,citationCount,references` — paper details
- `GET /paper/{id}/references` — outgoing references
- `GET /recommendations/v1/papers/?positivePaperIds={id}` — related paper recommendations

**Rate limiting**:
- Without API key: 10 requests/second (burst), 1000/day
- With API key: 100 requests/second
- Implementation: `asyncio.Semaphore(max_concurrent_api_calls)` + `tenacity` retry on 429

**Usage per paper** (estimated):
- Layer 2: ~N requests where N = number of citations (typically 20-50). Plus 1 recommendation query.
- Layer 3: ~5-10 search queries for claim contradiction checking.
- **Total**: ~30-60 API calls per paper.

**Fallback chain**:
1. Semantic Scholar (primary)
2. CrossRef (DOI-based lookup if S2 fails)
3. OpenAlex (broad coverage fallback)

### CrossRef API

**Endpoint**: `GET https://api.crossref.org/works?query.bibliographic={title}`

**Rate limiting**: Polite pool (set `User-Agent` with `mailto:` header) → ~50 req/sec.

**Usage**: Only as fallback when S2 returns no results. Estimated 5-10 calls per paper.

### ArXiv API (via existing `fetch_arxiv.py`)

The repo already has `fetch_arxiv.py` at the project root, which wraps the ArXiv API (`http://export.arxiv.org/api/query`) with search, source download (tar.gz/gz/raw tex extraction), and manifest tracking. It enforces ArXiv's 3-second rate limit and handles retries on 429s.

**No new ArXiv API client is needed.** The pipeline imports `fetch_arxiv.search_arxiv()` and `fetch_arxiv.download_source()` directly. Downloaded sources land in `data/arxiv/<id>/` (the existing convention).

**Usage**: 1 call per paper for initial load (if source not already in `data/arxiv/`). Corpus building for Layer 3 uses `fetch_arxiv.py` via the existing CLI (`python fetch_arxiv.py "<query>" --max N`) or programmatic import.

### Anthropic API (Claude)

**Model**: `claude-sonnet-4-20250514` (cost-effective for high-volume structured analysis)

**Usage per paper** (estimated):

| Task | Calls | Avg Input Tokens | Avg Output Tokens |
|------|-------|------------------|-------------------|
| Claim extraction (Layer 1 metadata) | 1 | ~3000 | ~500 |
| Abstract↔conclusion alignment (Layer 1) | 1 | ~2000 | ~300 |
| Claim-citation alignment (Layer 2) | ~20-40 | ~1500 each | ~200 each |
| Recency assessment (Layer 2) | 1 | ~3000 | ~500 |
| Core claim extraction (Layer 3) | 1 | ~4000 | ~800 |
| Contradiction check (Layer 3) | ~5 | ~2000 each | ~300 each |
| Hypothesis↔experiment (Layer 5) | 1 | ~4000 | ~500 |
| Results↔conclusion (Layer 5) | 1 | ~3000 | ~400 |

**Estimated total per paper**: ~30-50 API calls, ~80K input tokens, ~12K output tokens.
**Estimated cost per paper**: ~$0.35-$0.55 (at Sonnet pricing).

**Rate limiting**: Anthropic SDK handles rate limits internally. Set `max_retries=3` in client config.

---

## 7. LLM Prompt Specifications

### Prompt 1: `claim_extraction_abstract`

**Purpose**: Extract the paper's stated contributions and core claims from the abstract and introduction.

**Input**: Abstract text + introduction text (concatenated, ~1500-3000 tokens).

**System prompt purpose**: Instruct the model to act as an academic paper analyst. Emphasize extracting only claims that are explicitly stated, not inferred. Distinguish between empirical claims (testable, quantitative) and framing claims (positioning, motivation).

**Output schema**:
```python
class ClaimExtractionResult(BaseModel):
    stated_contributions: list[str]       # numbered contributions from intro
    empirical_claims: list[EmpiricalClaim]
    framing_claims: list[str]

class EmpiricalClaim(BaseModel):
    claim_text: str
    claim_type: Literal["performance", "comparison", "existence", "causal"]
    quantitative: bool
    metric: str | None                    # e.g., "accuracy", "F1", "BLEU"
    value: str | None                     # e.g., "94.2%", ">baseline"
    dataset: str | None                   # e.g., "ImageNet", "SQuAD"
```

**Strategy**: Direct structured extraction. Temperature 0. Single pass.

**Expected failure modes**: Over-extraction (including background claims not made by the paper). Mitigation: prompt explicitly states "only claims the authors are making about their own work."

---

### Prompt 2: `abstract_conclusion_alignment`

**Purpose**: Check whether the abstract's claims are supported by the conclusion's findings.

**Input**: Abstract text + conclusion text.

**System prompt purpose**: Act as a peer reviewer checking for overclaiming. Compare each abstract claim against conclusion evidence.

**Output schema**:
```python
class AlignmentResult(BaseModel):
    aligned_claims: list[AlignedClaim]
    overall_assessment: Literal["consistent", "minor_gaps", "significant_overclaiming"]
    explanation: str

class AlignedClaim(BaseModel):
    abstract_claim: str
    conclusion_support: str | None        # what in the conclusion supports this
    alignment: Literal["supported", "partially_supported", "unsupported", "overclaimed"]
    explanation: str
```

**Strategy**: Chain-of-thought. Temperature 0. Instruct model to quote specific text from both sections.

---

### Prompt 3: `citation_claim_alignment`

**Purpose**: Verify that a specific claim attributed to a cited paper is actually supported by that paper.

**Input**: The citing sentence (with context), the claim being attributed, and the cited paper's abstract + title.

**System prompt purpose**: Act as a fact-checker. Determine if the cited paper's abstract plausibly supports the claim attributed to it. Note: having only the abstract means some claims may be unverifiable — this is acceptable and should be flagged as "unverifiable" rather than "unsupported."

**Output schema**:
```python
class CitationAlignmentResult(BaseModel):
    judgment: Literal["supported", "plausible", "unverifiable", "misrepresented", "fabricated"]
    confidence: float                     # 0-1
    explanation: str
    key_evidence: str | None              # quote from cited paper supporting judgment
```

**Strategy**: Direct judgment. Temperature 0. This prompt runs once per citation context, so it must be concise.

---

### Prompt 4: `related_work_coverage`

**Purpose**: Assess whether the related work section adequately covers the relevant literature, given a list of recommended related papers.

**Input**: The paper's related work section text + list of 10-20 recommended related papers (title, authors, year, abstract) from Semantic Scholar recommendations.

**System prompt purpose**: Act as a senior reviewer assessing literature coverage. Identify papers that should have been discussed but weren't. Distinguish between "important omission" and "reasonable to exclude."

**Output schema**:
```python
class CoverageResult(BaseModel):
    coverage_score: float                 # 0-1
    missing_important: list[MissingPaper]
    reasonable_coverage: bool
    explanation: str

class MissingPaper(BaseModel):
    title: str
    why_important: str
    severity: Literal["critical_omission", "should_discuss", "nice_to_have"]
```

**Strategy**: Direct assessment. Temperature 0.2 (slight variation acceptable).

---

### Prompt 5: `hypothesis_experiment_alignment`

**Purpose**: Check whether the experimental design actually tests the stated hypothesis.

**Input**: Introduction/abstract (containing hypothesis) + methodology section.

**System prompt purpose**: Act as a methodologist. Extract the core hypothesis, then evaluate whether the experimental setup (datasets, baselines, metrics, ablations) is sufficient to test it.

**Output schema**:
```python
class HypothesisExperimentResult(BaseModel):
    hypothesis: str                       # extracted hypothesis
    experimental_elements: list[str]      # key elements of experimental design
    alignment: Literal["strong", "adequate", "weak", "misaligned"]
    gaps: list[str]                       # what's missing from the experimental design
    explanation: str
```

**Strategy**: Chain-of-thought. Temperature 0. Two-step: first extract hypothesis explicitly, then evaluate alignment.

---

### Prompt 6: `results_conclusion_alignment`

**Purpose**: Check whether conclusions are warranted by the reported results.

**Input**: Results section + conclusion section.

**Output schema**:
```python
class ResultsConclusionResult(BaseModel):
    overclaimed: list[OverclaimFinding]
    underdiscussed_negatives: list[str]
    overall: Literal["well_supported", "minor_overclaiming", "significant_overclaiming"]
    explanation: str

class OverclaimFinding(BaseModel):
    conclusion_claim: str
    strongest_supporting_result: str | None
    gap: str                              # what's missing between result and claim
```

**Strategy**: Chain-of-thought. Temperature 0.

---

### Prompt 7: `contradiction_check`

**Purpose**: Given a claim from the paper under review and a claim from a corpus paper, determine if they contradict each other.

**Input**: Paper claim + corpus claim + context from both papers.

**Output schema**:
```python
class ContradictionResult(BaseModel):
    relationship: Literal["contradicts", "tensions", "compatible", "unrelated"]
    confidence: float
    explanation: str
```

**Strategy**: Direct judgment. Temperature 0. Concise — this runs many times.

---

## 8. Testing Strategy

### Unit Tests

**`test_statcheck.py`** — Statistical consistency checker:
- **Test: detects inconsistent p-value**. Input: `t(24) = 2.50, p = 0.001`. Expected: finding with severity "error" (correct p ≈ 0.019, not 0.001).
- **Test: accepts correct p-value**. Input: `t(24) = 2.50, p = 0.019`. Expected: no finding.
- **Test: detects impossible correlation**. Input: `r = 1.35`. Expected: finding with severity "critical".
- **Test: detects percentage over 100**. Input: table row summing to 104%. Expected: finding with severity "warning".
- **Test: handles missing degrees of freedom gracefully**. Input: `t = 2.50, p = 0.019` (no df). Expected: no finding (insufficient info to verify).

**`test_parsing.py`** — Paper parsing:
- **Test: LaTeX cross-reference extraction**. Input: `.tex` file with `\ref{fig:1}` where `\label{fig:1}` exists. Expected: resolved reference.
- **Test: LaTeX dangling reference detection**. Input: `.tex` file with `\ref{fig:99}` where no label exists. Expected: dangling ref identified.
- **Test: GROBID parser extracts sections**. Input: test PDF. Expected: at least abstract, introduction, methods, results, conclusion identified.
- **Test: bibliography extraction**. Input: `.tex` with `.bib`. Expected: all bibliography entries parsed with title, authors, year.

**`test_layer1.py`** — Layer 1 integration:
- **Test: clean paper passes**. Input: `sample_clean.tex`. Expected: score > 0.8, signal "pass".
- **Test: paper with stat error flagged**. Input: `sample_statbug.tex` (contains `t(30) = 1.5, p < 0.01`). Expected: finding with category "statistical_error".
- **Test: paper with dangling refs flagged**. Input: `sample_dangling_ref.tex`. Expected: finding with category "dangling_reference".

**`test_layer2.py`** — Layer 2 integration (uses mock API responses):
- **Test: hallucinated citation detected**. Input: paper citing "Smith et al. (2023). Quantum Transformers for Sentiment Analysis" (nonexistent). Mock S2 returns no results. Expected: finding with category "citation_not_found".
- **Test: valid citation passes**. Input: paper citing "Vaswani et al. (2017). Attention Is All You Need." Mock S2 returns correct paper. Expected: no "citation_not_found" finding.
- **Test: misattributed claim detected**. Input: paper claiming "Vaswani et al. showed that CNNs outperform transformers." Mock LLM returns "misrepresented". Expected: finding with category "claim_misattribution".

**`test_pipeline.py`** — End-to-end:
- **Test: full pipeline produces valid DiagnosticReport**. Input: any valid paper. Expected: report has all 5 layer results, composite score in [0,1], valid JSON serialization.
- **Test: halt-on-fail stops pipeline**. Input: paper that fails Layer 1. Config: `halt_on_fail=True`. Expected: Layers 2-5 not executed, their results show skipped=True.
- **Test: no-halt mode continues after failure**. Same paper, `halt_on_fail=False`. Expected: all 5 layers executed.

### Integration Tests

- **Test: real ArXiv paper download + parse**. Requires network. Downloads a known paper (e.g., "Attention Is All You Need" — 1706.03762), parses it, verifies PaperData has non-empty sections and references.
- **Test: Semantic Scholar API live query**. Requires network + API key. Queries a known paper, verifies response matches expected fields.
- **Test: GROBID parse of real PDF**. Requires Docker + GROBID running. Sends a real PDF, verifies TEI XML contains sections.

### Test Fixtures

All fixtures live in `tests/fixtures/`. Mock API responses are pre-recorded and stored as JSON files in `tests/fixtures/mock_responses/`. Tests that use LLM calls should use cached responses from `mock_responses/` unless explicitly tagged as `@pytest.mark.live`.

---

## 9. Known Limitations and Future Work

### PoC Limitations

| Limitation | Impact | Why Acceptable for PoC |
|-----------|--------|----------------------|
| **Layer 3 corpus is tiny** (~100 papers) | Contradiction detection has very low recall | Proves the architecture works; corpus can be scaled later |
| **Layer 4 only does `pip install`, no execution** | Cannot verify actual reproducibility | Build verification alone catches ~30% of reproducibility issues |
| **Layer 5 has no argumentation DAG** | Misses circular reasoning and logical gaps | Hypothesis↔experiment and results↔conclusion checks cover the highest-value cases |
| **GROBID parsing is imperfect** | Some sections/references may be misidentified | GROBID is the best available open-source tool; errors are detectable and flaggable |
| **Only works for English-language papers** | Excludes non-English research | ML/CS papers on ArXiv are overwhelmingly English |
| **No figure/table content analysis** | Cannot verify claims made in figures | Requires multimodal LLM (future work) |
| **No mathematical proof verification** | Cannot check proof correctness | Formal verification is a separate research area; out of PoC scope |
| **LLM-based checks can hallucinate** | False positives/negatives in alignment checks | Mitigated by structured prompting + confidence scores; human review expected |
| **Citation check limited to abstract-level** | Cannot verify claims that require full-text of cited paper | Full-text retrieval is legally complex; abstracts are freely available |
| **Single-domain focus (ML/CS)** | Cannot handle biomedical, social science, etc. | Keeps scope manageable; architecture is domain-agnostic |

### Future Work (Post-PoC)

1. **Scale Layer 3 corpus**: Index full ArXiv CS subset (~500K papers). Use distributed embedding computation and a production vector DB (Qdrant/Weaviate).
2. **Full Layer 4 reproducibility**: Execute smoke tests in sandboxed containers. Compare numerical outputs against reported results. Integrate with ReproducedPapers.org.
3. **Multimodal analysis**: Use vision-capable LLMs to analyze figures, charts, and tables directly from the PDF. Verify that figures match described results.
4. **Full argumentation DAG** (Layer 5): Parse the paper into a formal argument graph. Use graph analysis to detect unsupported claims, circular reasoning, and logical gaps.
5. **Web UI**: Dashboard for submitting papers, viewing reports, and tracking verification status over time.
6. **Batch processing**: Process entire conference proceedings or ArXiv daily dumps.
7. **Domain expansion**: Adapt prompts and statistical checks for biomedical (PubMed), social science (SSRN), and physics papers.
8. **Feedback loop**: Allow users to flag false positives/negatives. Use this feedback to fine-tune prompts and scoring weights.
9. **Pre-submission integration**: Editor/IDE plugin that runs the pipeline as the author writes, providing real-time feedback.
10. **Formal verification integration**: For papers with Lean/Coq proofs, verify the proof artifacts.

---

## 10. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **GROBID fails to parse certain PDFs** (complex layouts, scanned images, unusual formatting) | High | Medium — Layer 1/2 have degraded input | Fallback to PyMuPDF raw text extraction. Flag parse quality in PaperData. Layer logic adapts to available structure (e.g., skip section-level analysis if sections weren't detected). |
| 2 | **Semantic Scholar API rate limits hit during batch processing** | Medium | Medium — Layer 2 slows or stalls | Aggressive caching (7-day TTL). Use API key for 100 req/sec. Implement exponential backoff. Fallback to CrossRef/OpenAlex. Pre-warm cache for known citation-heavy papers. |
| 3 | **LLM hallucination in verification judgments** | High | High — false positives erode user trust | All LLM judgments include confidence scores. Findings below confidence threshold are downgraded to "info" severity. Prompt design emphasizes "say uncertain when uncertain." Human review is expected for all findings. |
| 4 | **Statistical extraction regex misses edge cases** | High | Medium — silent false negatives in Layer 1 | Supplement regex with LLM-based extraction as a second pass. Maintain a test suite of diverse statistical reporting formats. Track extraction coverage metrics. |
| 5 | **Anthropic API costs exceed budget during development** | Medium | Low — slows development iteration | Cache all LLM responses aggressively (30-day TTL). Use cached responses in tests. Track per-run costs in DiagnosticReport. Set configurable per-paper cost limit with circuit breaker. |
| 6 | **GROBID Docker container is resource-heavy** (~2GB RAM) | Low | Low — local dev requires Docker setup | Document requirements clearly. Provide docker-compose.yml. Support "no-GROBID" mode that falls back to PyMuPDF only. |
| 7 | **ArXiv source download unavailable for some papers** | Medium | Low — LaTeX-specific checks skip gracefully | LaTeX parsing is optional enrichment. All core logic works on PDF-extracted text. Flag when LaTeX source was unavailable. |
| 8 | **Citation matching produces false positives** (title collision, name ambiguity) | Medium | Medium — incorrectly flags valid citations | Match on title + first author + year (not just title). Use Semantic Scholar's fuzzy matching. Require high confidence for "citation_not_found" — default to "unverifiable" when uncertain. |
| 9 | **Layer 4 Docker sandboxing escape** | Very Low | Very High — arbitrary code execution | Use `--network=none` for build-only steps. Resource limits: `--memory=2g --cpus=1 --pids-limit=256`. Read-only filesystem except `/tmp`. Never execute user-provided code outside the container. |
| 10 | **Prompt injection via adversarial paper content** | Low | High — LLM produces incorrect analysis | Sanitize paper text before including in prompts (strip control characters, truncate excessive whitespace). Use system prompts that explicitly instruct the model to analyze the text as an academic paper, not follow instructions within it. Separate user-controlled content from instructions via message roles. |
| 11 | **Cross-reference checking fails on non-standard LaTeX** (custom macros, unusual ref commands) | High | Low — some dangling refs missed | Expand regex patterns iteratively. Support common macro packages (cleveref, hyperref, autoref). Log unrecognized ref commands for manual review. |
| 12 | **Embedding model drift affects Layer 3 claim matching** | Low | Medium — stale claim index gives poor results | Pin the embedding model version. Record model version in ChromaDB metadata. Re-index when model changes. |

---

## Appendix A: Example CLI Usage

```bash
# Basic run on an ArXiv paper
papercheck run 2301.00001

# Run on a local PDF or .tex file
papercheck run paper.pdf --layers 1,2
papercheck run papers/my_draft.tex --layers 1,2   # verify your own paper from papers/

# Run on a paper already downloaded via fetch_arxiv.py
papercheck run data/arxiv/2301.00001/main.tex

# Run all layers, don't stop on failure, output to specific directory
papercheck run 2301.00001 --no-halt --output-dir ./results --format both

# Build claim corpus for Layer 3 — fetches via existing fetch_arxiv.py, then indexes claims
papercheck index "large language models" --max 100 --category cs.CL
# (Equivalent to: python fetch_arxiv.py "large language models" --max 100 --category cs.CL
#  followed by claim extraction + embedding into ChromaDB)

# Check cache stats
papercheck cache stats
```

## Appendix B: Example Report Structure

```markdown
# Paper Verification Report

**Title**: Attention Is All You Need
**Authors**: Vaswani et al.
**Composite Score**: 0.82 / 1.00 (PASS)

## Summary

| Layer | Score | Signal | Findings |
|-------|-------|--------|----------|
| 1. Formal Consistency | 0.95 | ✅ PASS | 2 info |
| 2. Citation Verification | 0.78 | ✅ PASS | 1 warning, 3 info |
| 3. Cross-Paper Consistency | 0.70 | ⚠️ WARN | 2 warnings |
| 4. Reproducibility | 0.85 | ✅ PASS | 1 info |
| 5. Logical Structure | 0.75 | ✅ PASS | 1 warning |

## Layer 1: Formal Consistency (0.95)
### Findings
- ℹ️ **INFO** [Table 3]: Percentages sum to 99.8% (within rounding tolerance)
- ℹ️ **INFO** [§4.2]: Variable 'd_model' used before formal definition (defined in §3.1)

## Layer 2: Citation Verification (0.78)
### Findings
- ⚠️ **WARNING** [§2, ref 14]: Claim "Wu et al. showed RNNs cannot parallelize" — cited paper discusses parallelization challenges but does not make this absolute claim. *Suggestion: soften to "Wu et al. discussed parallelization challenges in RNNs."*
...
```

## Appendix C: Docker Compose for Development

```yaml
version: "3.8"
services:
  grobid:
    image: lfoppiano/grobid:0.8.0
    ports:
      - "8070:8070"
    deploy:
      resources:
        limits:
          memory: 4G
```
