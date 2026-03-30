# PLAN_v2.md — Peer-Review Reward Model (Layer 6)

**Codename**: `papercheck-reward`
**Depends on**: Fully implemented `papercheck` pipeline per `PLAN.md`
**Status**: Planning

---

## 0. Context & Motivation

The existing `papercheck` pipeline (Layers 1-5) performs verification through rule-based checks, API lookups, and LLM-driven analysis. Each layer catches a specific class of errors — statistical inconsistencies, citation fabrication, logical gaps — but none of them answer the question: *"How would expert reviewers actually receive this paper?"*

Peer reviews from open venues like ICLR and NeurIPS provide richly decomposed quality signals — soundness, presentation, contribution, novelty, overall rating — along with textual feedback. These are not just accept/reject labels; they form a multi-dimensional reward surface that encodes what expert reviewers value. The structural regularity of academic writing (the original thesis motivating `papercheck`) makes this mapping unusually learnable: the rigid conventions of abstracts, methodology sections, and results presentations create stable textual patterns that correlate with reviewer assessments.

**Layer 6 trains a reward model on this data and integrates it as the final verification stage**, producing predicted review scores and a natural-language "anticipated reviewer concerns" summary. It serves two purposes:

1. **As a standalone signal**: "This paper's presentation score is predicted at 4.2/10 — bottom quartile for ICLR" is immediately actionable feedback for authors.
2. **As a composite pipeline input**: The reward model score enters the weighted composite alongside Layers 1-5, providing a learned holistic assessment that complements the rule-based checks.

The key insight from recent work (REMOR, ReviewRL, Re2) is that peer review data is now available at sufficient scale and quality to train useful models, but existing efforts focus on generating reviews. We're solving the inverse problem: using review signals to assess paper quality, as part of a broader verification pipeline.

---

## 1. Project Structure

All new files live under `papercheck/reward_model/`. No existing files are modified until the integration step (Phase 4), which touches a small, well-defined set of existing modules.

```
papercheck/reward_model/            # new subpackage
├── __init__.py
├── data_ingestion.py               # OpenReview API scraper + Re2 dataset loader
├── data_processing.py              # Submission-review alignment, score normalization, splits
├── feature_extraction.py           # Paper text → model input features
├── model.py                        # Multi-head regression model (SPECTER2 backbone)
├── train.py                        # Training loop with multi-task loss
├── inference.py                    # Load checkpoint, predict scores for new papers
├── calibration.py                  # Isotonic regression calibration against held-out data
├── concern_generator.py            # LLM-based "anticipated reviewer concerns" from predicted weak dimensions
├── integration.py                  # Adapter: reward model → VerificationLayer (Layer 6)
└── configs/
    ├── default.yaml                # Default training hyperparameters
    └── small.yaml                  # Minimal config for fast iteration / CPU-only

papercheck/layers/
└── layer6_reward.py                # Layer 6 entry point (thin wrapper around integration.py)

papercheck/tests/
├── test_data_ingestion.py          # OpenReview scraping tests (mocked)
├── test_data_processing.py         # Alignment, normalization, split tests
├── test_reward_model.py            # Model forward pass, training loop, inference tests
├── test_layer6.py                  # Layer 6 integration tests
└── fixtures/
    ├── mock_openreview/            # Cached OpenReview API responses
    │   ├── iclr2024_sample.json    # 50 papers with reviews for testing
    │   └── venue_metadata.json     # Score ranges, review templates per venue
    └── reward_model/
        ├── tiny_checkpoint.pt      # Tiny model for unit tests (random weights, correct shape)
        └── sample_predictions.json # Expected outputs for test papers

data/openreview/                    # Downloaded review data (gitignored)
├── manifest.json                   # Tracks what's been downloaded
├── iclr_2023/
│   ├── papers/                     # Initial submissions (PDF or extracted text)
│   └── reviews.jsonl               # One review per line, linked to paper ID
├── iclr_2024/
│   └── ...
├── iclr_2025/
│   └── ...
└── neurips_2023/
    └── ...

models/reward_model/                # Trained model artifacts (gitignored)
├── checkpoint_best.pt              # Best validation checkpoint
├── config.yaml                     # Training config snapshot
├── calibration.pkl                 # Fitted calibration model
├── training_log.jsonl              # Per-epoch metrics
└── eval_report.json                # Test set performance summary
```

---

## 2. Dependencies (Additions to pyproject.toml)

```toml
# Reward model — add to [project.dependencies]
torch = ">=2.2"                     # PyTorch backend
transformers = ">=4.38"             # SPECTER2 / SciBERT backbone
datasets = ">=2.18"                 # HuggingFace datasets for batched loading
openreview-py = ">=1.30"            # OpenReview API client
scikit-learn = ">=1.4"              # Calibration, metrics, stratified splits
safetensors = ">=0.4"               # Safe model serialization
pyyaml = ">=6.0"                    # Training config files

# Add to [project.optional-dependencies]
gpu = [
    "torch >= 2.2",                 # with CUDA — user installs separately
]
```

### Additional API Credentials

| API | Credential | Free? | Purpose |
|-----|-----------|-------|---------|
| **OpenReview** | `OPENREVIEW_USERNAME` + `OPENREVIEW_PASSWORD` | Yes (free account at openreview.net) | Download peer review data for training |

### Hardware Requirements

| Config | Hardware | Training Time (5K papers) | Inference Time (per paper) |
|--------|----------|---------------------------|---------------------------|
| `small.yaml` | CPU only, 16GB RAM | ~8-12 hours | ~2 seconds |
| `default.yaml` | 1x GPU (A100/4090), 24GB VRAM | ~1-2 hours | ~0.3 seconds |

---

## 3. Implementation Phases

### Phase 1: Data Ingestion (Week 1)

**Goal**: Download and cache a complete dataset of ICLR submissions with reviews from OpenReview.

**Deliverables**:
- `reward_model/data_ingestion.py`
- Downloaded data for ICLR 2023-2025 in `data/openreview/`
- CLI command: `papercheck reward fetch --venue iclr --years 2023-2025`

#### `data_ingestion.py` Specification

```python
class OpenReviewScraper:
    """
    Downloads submissions and reviews from OpenReview API v2.
    
    Uses openreview-py client (openreview.Client(baseurl='https://api2.openreview.net')).
    
    Methods:
    - fetch_venue(venue: str, year: int) → VenueData
        Downloads all submissions + reviews for a venue-year.
        Stores raw API responses in data/openreview/{venue}_{year}/.
        Tracks progress in manifest.json (supports resume on interruption).
    
    - get_initial_submission(note_id: str) → Paper | None
        Retrieves the FIRST version of a submission (before revisions).
        Critical: later versions reflect author changes after reviews.
        Uses note.content['_bibtex'] or iterates note versions.
    
    - get_reviews(note_id: str) → list[Review]
        Returns all official reviews (invitation contains 'Official_Review').
        Extracts structured fields: summary, strengths, weaknesses,
        questions, rating, confidence, soundness, presentation, contribution.
    
    - get_decision(note_id: str) → Decision
        Returns accept/reject/withdrawn decision.
    
    Rate limiting: 1 request/second with retry on 429.
    All responses cached via papercheck cache/store.py.
    """

class VenueData(BaseModel):
    venue: str                          # "iclr"
    year: int
    papers: list[SubmissionRecord]
    total_reviews: int

class SubmissionRecord(BaseModel):
    openreview_id: str                  # OpenReview note ID
    title: str
    authors: list[str]
    abstract: str
    full_text: str | None               # extracted via GROBID from PDF, or from LaTeX
    pdf_url: str | None
    reviews: list[ReviewRecord]
    decision: str                       # "Accept", "Reject", "Withdrawn"
    venue: str
    year: int

class ReviewRecord(BaseModel):
    reviewer_id: str                    # anonymized
    overall_rating: float               # normalized to venue scale
    soundness: float | None
    presentation: float | None
    contribution: float | None
    confidence: float
    summary: str
    strengths: str
    weaknesses: str
    questions: str
    raw_scores: dict[str, Any]          # original unprocessed scores
```

**OpenReview API specifics**:
- ICLR 2023+ uses API v2 (`api2.openreview.net`). Older venues may need v1.
- Submissions: `client.get_all_notes(invitation='ICLR.cc/{year}/Conference/-/Blind_Submission')`
- Reviews: `client.get_all_notes(forum=paper_id, invitation='ICLR.cc/{year}/Conference/Paper.*/-/Official_Review')`
- Decisions: `client.get_all_notes(forum=paper_id, invitation='ICLR.cc/{year}/Conference/Paper.*/-/Decision')`
- Score field names vary by year (e.g., `rating` vs `recommendation` vs `overall`). The scraper must map venue-specific field names to canonical names.

**Data volume estimates**:

| Venue-Year | Submissions | Reviews | Size (text only) |
|-----------|-------------|---------|------------------|
| ICLR 2023 | ~4,900 | ~17,000 | ~2 GB |
| ICLR 2024 | ~7,200 | ~25,000 | ~3 GB |
| ICLR 2025 | ~9,000 | ~31,000 | ~4 GB |
| **PoC target** | **~5,000** (ICLR 2024-2025 subset) | **~17,000** | **~3 GB** |

For the PoC, ICLR 2024-2025 alone provides sufficient data. NeurIPS can be added later for cross-venue generalization.

**Exit criteria**: `papercheck reward fetch --venue iclr --years 2024-2025` completes without errors. `data/openreview/manifest.json` shows ~12K+ papers downloaded with reviews. At least 90% of submissions have ≥3 reviews each.

---

### Phase 2: Data Processing & Feature Extraction (Week 2)

**Goal**: Clean, normalize, and align the raw OpenReview data into training-ready features and labels.

**Deliverables**:
- `reward_model/data_processing.py`
- `reward_model/feature_extraction.py`
- Processed dataset files in `data/openreview/processed/`
- CLI command: `papercheck reward process --venue iclr --years 2024-2025`

#### `data_processing.py` Specification

```python
class ReviewDataProcessor:
    """
    Transforms raw OpenReview data into training-ready format.
    
    Methods:
    - process_venue(venue_data: VenueData) → ProcessedDataset
        Full processing pipeline for one venue-year.
    
    - filter_submissions(papers: list[SubmissionRecord]) → list[SubmissionRecord]
        Remove:
        - Papers with < 3 reviews (insufficient signal)
        - Withdrawn papers (no decision signal)
        - Papers with placeholder abstracts (< 100 chars)
        - Papers in top/bottom 1% by length (outliers)
    
    - normalize_scores(reviews: list[ReviewRecord], venue: str, year: int) → list[NormalizedReview]
        Map venue-specific score scales to unified 0-1 range.
        ICLR 2024-2025 uses discrete {1, 3, 5, 6, 8, 10} for overall rating.
        Normalization: (score - min) / (max - min) per dimension per venue.
        
    - compute_consensus_labels(reviews: list[NormalizedReview]) → ConsensusLabels
        For each score dimension:
        - confidence_weighted_mean: Σ(score_i × confidence_i) / Σ(confidence_i)
        - reviewer_variance: variance of scores (signal of disagreement)
        - review_count: number of reviews
        Note: high variance dimensions are HARDER to predict but potentially
        MORE USEFUL — they indicate where expert opinion diverges.
    
    - create_splits(dataset: ProcessedDataset) → TrainValTestSplit
        80/10/10 split, stratified by:
        - Decision (accept/reject proportions preserved)
        - Year (prevents temporal leakage — don't train on 2025, test on 2024)
        - Score quartile (balanced representation across quality spectrum)
    """

class ConsensusLabels(BaseModel):
    overall_rating: float               # 0-1, confidence-weighted mean
    soundness: float | None
    presentation: float | None
    contribution: float | None
    accept_probability: float           # 1.0 if accepted, 0.0 if rejected
    reviewer_variance: dict[str, float] # per-dimension variance
    review_count: int
    confidence_weighted: bool           # whether confidence weighting was applied

class ProcessedPaper(BaseModel):
    openreview_id: str
    title: str
    abstract: str
    full_text: str | None
    sections: dict[str, str] | None     # parsed sections if GROBID succeeded
    labels: ConsensusLabels
    venue: str
    year: int
    decision: str
```

#### `feature_extraction.py` Specification

```python
class PaperFeatureExtractor:
    """
    Converts processed papers into model input tensors.
    
    Two feature types:
    
    1. TEXT FEATURES (primary — fed to transformer encoder):
       - Primary input: abstract + introduction + conclusion (concatenated)
         Rationale: PeerRead showed these sections are most predictive of
         reviewer scores. Methods/experiments are informative but longer;
         including them requires longer context or a two-pass approach.
       - Truncated to max_length tokens (default 512).
       - Tokenized with SPECTER2 tokenizer.
    
    2. STRUCTURAL FEATURES (auxiliary — concatenated to [CLS] embedding):
       - paper_length_tokens: int (total paper length)
       - num_references: int
       - num_figures: int
       - num_tables: int
       - num_equations: int
       - methods_to_results_ratio: float (section length ratio)
       - citation_density: float (references per 1000 tokens)
       - has_code_link: bool (GitHub/GitLab URL detected)
       - num_empirical_claims: int (from extractors/claims.py if available)
       
       These are computed from PaperData (reusing existing extractors)
       and normalized to zero-mean unit-variance using training set statistics.
    
    Methods:
    - extract(paper: ProcessedPaper, tokenizer) → PaperFeatures
    - batch_extract(papers: list[ProcessedPaper], tokenizer) → BatchFeatures
    - compute_normalization_stats(papers: list[ProcessedPaper]) → NormStats
        Computed on training set, saved alongside model checkpoint.
    """

class PaperFeatures(BaseModel):
    input_ids: list[int]                # tokenized text
    attention_mask: list[int]
    structural_features: list[float]    # normalized auxiliary features
    labels: ConsensusLabels             # target scores
```

**Integration with existing pipeline**: Feature extraction reuses `papercheck.parsing.grobid_parser` for section extraction and `papercheck.extractors.*` for claims, equations, and reference counts. If GROBID parsing fails for a training paper, fall back to abstract-only features (still useful, just less informative).

**Exit criteria**: Processed dataset for ICLR 2024-2025 with ~5K papers, each having text features and consensus labels. Train/val/test splits created. Feature distributions visualized and sanity-checked (no extreme outliers, label distributions match expected ICLR patterns).

---

### Phase 3: Model Training & Evaluation (Weeks 3-4)

**Goal**: Train a multi-task regression model that predicts review scores from paper text, beating simple baselines. Calibrate outputs to produce meaningful confidence intervals.

**Deliverables**:
- `reward_model/model.py` — model architecture
- `reward_model/train.py` — training loop
- `reward_model/calibration.py` — post-hoc calibration
- Trained checkpoint in `models/reward_model/`
- Evaluation report comparing against baselines
- CLI commands: `papercheck reward train`, `papercheck reward eval`

#### `model.py` Specification

```python
class PaperRewardModel(nn.Module):
    """
    Multi-head regression model for predicting peer review scores.
    
    Architecture:
        Paper text → SPECTER2 encoder → [CLS] embedding (768-d)
            ↓
        Concatenate with structural features (10-d) → (778-d)
            ↓
        Shared projection layer: Linear(778, 256) + ReLU + Dropout(0.1)
            ↓
        Per-dimension regression heads:
            - overall_head: Linear(256, 1) + Sigmoid → [0, 1]
            - soundness_head: Linear(256, 1) + Sigmoid → [0, 1]
            - presentation_head: Linear(256, 1) + Sigmoid → [0, 1]
            - contribution_head: Linear(256, 1) + Sigmoid → [0, 1]
            - accept_head: Linear(256, 1) + Sigmoid → [0, 1] (probability)
    
    Backbone: allenai/specter2 (preferred) or allenai/scibert_scivocab_uncased
    SPECTER2 is specifically trained on scientific paper representations,
    making it a strong prior for this task.
    
    Forward pass:
        def forward(self, input_ids, attention_mask, structural_features):
            encoder_output = self.encoder(input_ids, attention_mask)
            cls_embedding = encoder_output.last_hidden_state[:, 0, :]
            combined = torch.cat([cls_embedding, structural_features], dim=-1)
            shared = self.projection(combined)
            return {
                'overall': self.overall_head(shared),
                'soundness': self.soundness_head(shared),
                'presentation': self.presentation_head(shared),
                'contribution': self.contribution_head(shared),
                'accept_prob': self.accept_head(shared),
            }
    """

class MultiTaskLoss(nn.Module):
    """
    Weighted multi-task MSE loss.
    
    loss = Σ(w_d × MSE(pred_d, label_d)) for each dimension d
    
    Default weights:
        overall: 2.0  (primary target, double-weighted)
        soundness: 1.0
        presentation: 1.0
        contribution: 1.0
        accept_prob: 1.5  (binary cross-entropy, not MSE)
    
    Dimensions with None labels (missing scores) are masked out.
    accept_prob uses BCELoss instead of MSE.
    """
```

**Why SPECTER2 over general-purpose encoders**: SPECTER2 is pre-trained on scientific paper pairs (citation-linked) and produces embeddings where citation-connected papers are close. This gives us a strong initialization — the encoder already "understands" that papers in the same subfield should have similar representations, which is a useful inductive bias for predicting review scores.

#### `train.py` Specification

```python
class RewardModelTrainer:
    """
    Training loop with early stopping, logging, and checkpoint management.
    
    Methods:
    - train(config: TrainingConfig) → TrainingResult
        Full training run. Loads data, initializes model, runs epochs,
        evaluates on val set, saves best checkpoint.
    
    Training procedure:
    1. Load processed dataset from data/openreview/processed/
    2. Initialize SPECTER2 encoder + regression heads
    3. For each epoch:
       a. Train on batches with multi-task loss
       b. Evaluate on validation set
       c. Log per-dimension metrics (MSE, Pearson r, Spearman ρ)
       d. Save checkpoint if val loss improves
       e. Early stop if no improvement for patience=3 epochs
    4. Load best checkpoint, evaluate on test set
    5. Save eval report to models/reward_model/eval_report.json
    
    Checkpointing: Save full state (model, optimizer, scheduler, epoch, best_val_loss).
    Logging: Per-epoch metrics to models/reward_model/training_log.jsonl.
    """

class TrainingConfig(BaseModel):
    """Loaded from configs/default.yaml or configs/small.yaml."""
    backbone: str = "allenai/specter2"
    max_length: int = 512
    batch_size: int = 16
    gradient_accumulation_steps: int = 2
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    lr_scheduler: str = "cosine"
    num_epochs: int = 10
    patience: int = 3
    dropout: float = 0.1
    loss_weights: dict[str, float] = {
        "overall": 2.0,
        "soundness": 1.0,
        "presentation": 1.0,
        "contribution": 1.0,
        "accept_prob": 1.5,
    }
    device: str = "auto"               # "auto", "cuda", "cpu"
    seed: int = 42
    output_dir: str = "models/reward_model"
    data_dir: str = "data/openreview/processed"
```

#### Baselines

The trained model must outperform these baselines on the test set:

| Baseline | Description | Expected Pearson r (overall) |
|----------|------------|------------------------------|
| **Mean baseline** | Predict venue-year mean for all papers | 0.0 (by definition) |
| **TF-IDF + Ridge** | TF-IDF on abstract → Ridge regression | ~0.15-0.20 |
| **SPECTER2 linear probe** | Frozen SPECTER2 → Linear head (no fine-tuning) | ~0.20-0.25 |
| **Full model (ours)** | Fine-tuned SPECTER2 + structural features | ~0.30-0.40 (target) |

**Expected performance context**: Inter-reviewer correlation on ICLR is ~0.40 (Pearson). A model achieving r=0.35 is performing comparably to adding a fourth reviewer — which is meaningful even though it's far from perfect. The model's value is not in replacing human review but in providing a fast, consistent signal.

**Per-dimension expected performance**:
- `overall_rating`: r ≈ 0.30-0.40 (moderate, reviewers themselves disagree)
- `presentation`: r ≈ 0.35-0.45 (most learnable from text — stylistic quality is surface-level)
- `soundness`: r ≈ 0.20-0.30 (harder — requires understanding methodology)
- `contribution`: r ≈ 0.15-0.25 (hardest — requires field context, closest to "significance")
- `accept_prob`: AUC ≈ 0.70-0.75 (binary classification, easier than regression)

#### `calibration.py` Specification

```python
class ScoreCalibrator:
    """
    Post-hoc calibration so predicted scores are interpretable.
    
    Problem: Raw model outputs are often miscalibrated — a predicted 0.6
    doesn't necessarily correspond to the 60th percentile of actual scores.
    
    Solution: Isotonic regression on held-out validation predictions.
    For each dimension, fit an isotonic regression mapping raw predictions
    to calibrated scores that match the empirical CDF of true scores.
    
    Methods:
    - fit(val_predictions: dict[str, np.array], val_labels: dict[str, np.array])
        Fit one isotonic regressor per dimension.
    
    - calibrate(raw_predictions: dict[str, float]) → CalibratedScores
        Apply fitted calibrators to raw model output.
    
    - get_percentile(calibrated_score: float, dimension: str) → float
        What percentile of the training distribution does this score fall at?
        Enables statements like "predicted soundness is 72nd percentile for ICLR."
    
    Serialization: Save/load via pickle to models/reward_model/calibration.pkl.
    """

class CalibratedScores(BaseModel):
    overall_rating: float               # 0-1 calibrated
    overall_percentile: float           # 0-100, percentile in training distribution
    soundness: float | None
    soundness_percentile: float | None
    presentation: float | None
    presentation_percentile: float | None
    contribution: float | None
    contribution_percentile: float | None
    accept_probability: float           # 0-1 calibrated probability
    model_confidence: float             # based on structural feature completeness + text length
```

**Exit criteria**: Trained model beats all three baselines on test set Pearson r for `overall_rating`. Calibrated scores produce reasonable percentile rankings when applied to known accepted vs. rejected papers. `eval_report.json` documents all metrics.

---

### Phase 4: Pipeline Integration (Week 5)

**Goal**: Wire the trained reward model into the `papercheck` pipeline as Layer 6. Update scoring, config, reporting, and CLI.

**Deliverables**:
- `reward_model/concern_generator.py` — LLM-based anticipated concerns
- `reward_model/integration.py` — VerificationLayer adapter
- `layers/layer6_reward.py` — Layer 6 entry point
- Modifications to existing files (listed below)
- `tests/test_layer6.py`

#### `concern_generator.py` Specification

```python
class ConcernGenerator:
    """
    Uses LLM to generate "anticipated reviewer concerns" based on
    the reward model's predicted weak dimensions.
    
    Rationale: Raw scores ("presentation: 0.35") are useful but not
    actionable. By identifying which dimensions scored low and prompting
    the LLM with the paper text + dimension context, we can generate
    specific, actionable feedback like "Reviewers may find the experimental
    setup description insufficient — the baseline comparison in Section 4
    lacks detail on hyperparameter selection."
    
    Methods:
    - generate(paper: PaperData, scores: CalibratedScores, config: PipelineConfig) → list[Finding]
        For each dimension scoring below the 40th percentile:
        1. Identify the relevant paper sections for that dimension
           (presentation → all sections; soundness → methods + results;
            contribution → intro + related work + conclusion)
        2. Prompt LLM with section text + dimension definition + low score context
        3. Parse response into Finding objects with specific suggestions
        
        Only generates concerns for dimensions scoring below 40th percentile
        (avoids noise from dimensions where the model is uncertain).
    """
```

#### `layers/layer6_reward.py` Specification

```python
class RewardModelLayer(VerificationLayer):
    layer_number = 6
    layer_name = "Peer-Review Reward Model"

    def __init__(self):
        self.model = None                # lazy-loaded on first call
        self.calibrator = None

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """
        1. Load trained reward model (lazy, cached after first load)
        2. Extract features from PaperData using feature_extraction.py
        3. Run inference → raw predicted scores
        4. Calibrate scores → CalibratedScores with percentiles
        5. Generate anticipated concerns for low-scoring dimensions (LLM)
        6. Construct LayerResult:
           - score: calibrated overall_rating (0-1)
           - signal: pass if overall ≥ 50th percentile,
                     warn if ≥ 25th percentile,
                     fail if < 25th percentile
           - findings: per-dimension scores as INFO findings +
                       anticipated concerns as WARNING findings
        
        Skips with LayerResult(skipped=True) if:
        - No trained model found at config.reward_model_path
        - Paper has no extractable text (shouldn't happen at Layer 6)
        """
```

#### Modifications to Existing Files

| File | Change | Details |
|------|--------|---------|
| `config.py` | Add Layer 6 config fields | `reward_model_path: Path = Path("models/reward_model")`, add layer 6 to `layer_weights` (default 0.10), `fail_thresholds`, `warn_thresholds`. Add `reward_model_device: str = "auto"`. |
| `pipeline.py` | Register Layer 6 | Add `RewardModelLayer` to the layer list. Layer 6 runs last. If no trained model exists, skip gracefully (don't error — the pipeline should work without Layer 6). |
| `scoring/composite.py` | Handle 6 layers | No logic changes needed — existing weighted average with skip handling already supports arbitrary layer counts. Just update default weights to sum to 1.0 across 6 layers. |
| `report/markdown_report.py` | Render Layer 6 findings | Add a special rendering block for Layer 6 that shows predicted scores as a table (dimension / score / percentile) followed by anticipated concerns. |
| `cli.py` | Add `reward` subcommand group | `papercheck reward fetch`, `papercheck reward process`, `papercheck reward train`, `papercheck reward eval`. Also update `papercheck run` to accept `--layers 1,2,3,4,5,6`. |
| `models.py` | No changes | Existing `LayerResult` and `Finding` models are sufficient. |

#### Updated Default Weights

```python
# config.py — updated layer_weights
layer_weights: dict[int, float] = {
    1: 0.25,    # Formal consistency (was 0.30)
    2: 0.20,    # Citation verification (was 0.25)
    3: 0.18,    # Cross-paper consistency (was 0.20)
    4: 0.12,    # Reproducibility (was 0.15)
    5: 0.10,    # Logical structure (was 0.10)
    6: 0.15,    # Peer-review reward model (new)
}
```

Layer 6 is weighted at 0.15 — significant but not dominant. It's weighted above Layers 4-5 (which are skeletons in the PoC) but below the fully-implemented Layers 1-2. Rationale: the reward model provides a holistic learned signal that's complementary to the rule-based layers, but its prediction quality (~0.35 correlation) means it shouldn't override confident findings from other layers.

#### LLM Prompt Specification: `anticipated_concerns`

**Purpose**: Given a paper's text and a specific low-scoring review dimension, generate the reviewer concerns that likely drove the low prediction.

**Input**: Paper section text relevant to the dimension + dimension name + predicted score + percentile + brief dimension definition.

**System prompt purpose**: Act as an experienced peer reviewer at a top ML venue. You've been told this paper scores in the Nth percentile on [dimension]. Based on the paper text provided, identify the 2-3 most likely specific concerns a reviewer would raise about this dimension. Be concrete — cite specific sections, claims, or missing elements. Don't be generic.

**Output schema**:
```python
class AnticipatedConcerns(BaseModel):
    dimension: str
    concerns: list[ReviewerConcern]

class ReviewerConcern(BaseModel):
    concern: str                        # specific issue description
    location: str | None                # section/paragraph reference
    suggestion: str | None              # concrete improvement suggestion
    severity: Literal["minor", "moderate", "major"]
```

**Strategy**: Direct generation. Temperature 0.3 (allow some variation in concern framing). Max 1 LLM call per low-scoring dimension (cap at 3 dimensions max to control cost). Estimated 0-3 calls per paper.

**Exit criteria**: `papercheck run <arxiv_id> --layers 1,2,3,4,5,6` produces a report that includes Layer 6 with predicted review scores, percentile rankings, and 0-3 anticipated concerns. Layer 6 gracefully skips if no model is trained. All existing Layer 1-5 tests still pass.

---

## 4. Data Flow (Layer 6 Only)

```
                  ┌─────────────────┐
                  │   PaperData     │◄── from pipeline (same as Layers 1-5)
                  └────────┬────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  feature_extraction.py │
              │  ─────────────────────│
              │  Reuse GROBID sections │
              │  Extract structural    │
              │  features              │
              │  Tokenize text         │
              └────────────┬───────────┘
                           │
                    PaperFeatures
                           │
                           ▼
              ┌────────────────────────┐
              │     inference.py       │
              │  ─────────────────────│
              │  Load checkpoint       │
              │  (lazy, cached)        │
              │  Forward pass          │
              └────────────┬───────────┘
                           │
                   Raw predictions
                           │
                           ▼
              ┌────────────────────────┐
              │    calibration.py      │
              │  ─────────────────────│
              │  Isotonic regression   │
              │  Percentile mapping    │
              └────────────┬───────────┘
                           │
                  CalibratedScores
                           │
              ┌────────────┴───────────┐
              │                        │
              ▼                        ▼
   ┌───────────────────┐    ┌──────────────────────┐
   │  Predicted score   │    │ concern_generator.py  │
   │  findings (INFO)   │    │ ────────────────────  │
   │                    │    │ LLM call per low dim  │
   │  Per-dimension     │    │ → WARNING findings    │
   │  scores + %iles    │    │   with suggestions    │
   └─────────┬─────────┘    └──────────┬───────────┘
             │                         │
             └────────────┬────────────┘
                          │
                   list[Finding]
                          │
                          ▼
                 ┌──────────────┐
                 │ LayerResult  │──→ back to pipeline orchestrator
                 │ (Layer 6)    │
                 └──────────────┘
```

### Cost Estimates (Layer 6 per paper)

| Step | Compute | API Calls | Estimated Cost |
|------|---------|-----------|----------------|
| Feature extraction | Negligible (reuse parsed data) | 0 | $0.00 |
| Model inference | ~0.3s GPU / ~2s CPU | 0 | $0.00 |
| Calibration | Negligible | 0 | $0.00 |
| Concern generation | — | 0-3 LLM calls | $0.00-$0.08 |
| **Total Layer 6** | **~2-5s** | **0-3** | **$0.00-$0.08** |

Layer 6 is cheaper per-paper than Layers 2 or 5 because the heavy lifting (model inference) is local compute, not API calls.

---

## 5. Testing Strategy

### Unit Tests

**`test_data_ingestion.py`** (mocked OpenReview API):
- **Test: fetches ICLR 2024 submissions**. Mock OpenReview client returns 50 sample submissions. Expected: 50 SubmissionRecords with non-empty abstracts.
- **Test: extracts initial submission version**. Mock returns multiple note versions. Expected: returns earliest version, not camera-ready.
- **Test: handles missing review fields gracefully**. Mock returns review with `soundness: None`. Expected: ReviewRecord created with `soundness=None`, no crash.
- **Test: resume on interruption**. Mock manifest shows 30/50 papers downloaded. Expected: only fetches remaining 20.

**`test_data_processing.py`**:
- **Test: score normalization for ICLR scale**. Input: raw rating=8 on {1,3,5,6,8,10} scale. Expected: normalized value = (8-1)/(10-1) ≈ 0.778.
- **Test: confidence-weighted consensus**. Input: three reviews with ratings [0.6, 0.8, 0.4] and confidences [4, 5, 3]. Expected: weighted mean ≈ 0.633, not simple mean 0.6.
- **Test: filters papers with < 3 reviews**. Input: 100 papers, 10 with only 2 reviews. Expected: 90 papers in output.
- **Test: stratified split preserves decision ratio**. Input: dataset with 30% accept rate. Expected: train/val/test all have ~30% accept rate (within ±5%).
- **Test: temporal split prevents leakage**. Input: dataset with 2024 and 2025 papers. Expected: 2025 papers never appear in training set when test set contains 2025 papers.

**`test_reward_model.py`**:
- **Test: model forward pass produces correct output shape**. Input: batch of 4 papers (random tensors). Expected: dict with 5 keys, each value shape (4, 1).
- **Test: multi-task loss handles missing dimensions**. Input: batch where 2 papers have `soundness=None`. Expected: loss computed only over non-None dimensions, no NaN.
- **Test: training loop reduces loss over 3 epochs**. Input: 50 sample papers. Expected: epoch 3 train loss < epoch 1 train loss.
- **Test: calibration maps to correct percentiles**. Input: calibrator fit on [0.1, 0.3, 0.5, 0.7, 0.9]. Expected: calibrate(0.5) ≈ 50th percentile.
- **Test: inference on real paper produces reasonable scores**. Input: known high-quality ICLR paper. Expected: all predicted scores in [0, 1], accept_prob > 0.5.

**`test_layer6.py`** (integration):
- **Test: Layer 6 produces valid LayerResult**. Input: PaperData from a parsed test paper. Expected: LayerResult with score in [0,1], signal in {pass, warn, fail}, ≥1 finding.
- **Test: Layer 6 skips gracefully when no model exists**. Config points to nonexistent model path. Expected: LayerResult with skipped=True, skip_reason set.
- **Test: Layer 6 findings include per-dimension scores**. Expected: at least 5 INFO findings (one per dimension) with percentile information.
- **Test: concern generation triggers for low-scoring dimensions only**. Mock model predicts presentation at 20th percentile, others at 60th+. Expected: WARNING finding about presentation, none about soundness.
- **Test: full pipeline with Layer 6**. Run `papercheck run` on test paper with all 6 layers. Expected: DiagnosticReport has 6 LayerResults, composite score reflects Layer 6 weight.

### Test Fixtures

- `tests/fixtures/mock_openreview/iclr2024_sample.json`: 50 papers with full review data, pre-downloaded from OpenReview. Used for ingestion + processing tests without API access.
- `tests/fixtures/reward_model/tiny_checkpoint.pt`: A SPECTER2 model with 2 hidden layers instead of 12, random weights. Correct architecture for integration tests without requiring a trained model.
- `tests/fixtures/reward_model/sample_predictions.json`: Expected model outputs for 5 test papers, used to validate inference pipeline consistency.

---

## 6. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **OpenReview API changes or rate-limits aggressively** | Medium | High — cannot download training data | Cache all raw API responses. Also support loading from Re2 dataset (HuggingFace) as a fallback data source — Re2 covers the same venues and is pre-cleaned. Add `--source re2` flag to `papercheck reward fetch`. |
| 2 | **Initial submission versions unavailable for older venues** | High | Medium — training on revised versions biases model toward higher-quality text | Restrict to ICLR 2023+ where OpenReview v2 reliably exposes version history. For venues where only final versions are available, add a `version_quality` flag and optionally down-weight in training. |
| 3 | **Inter-reviewer noise limits prediction ceiling** | Certain | Medium — model cannot exceed ~0.40 Pearson r on overall rating | This is inherent, not a bug. Frame the model's value as "consistent reviewer-level signal" rather than "ground truth." Use reviewer variance as an auxiliary output to flag dimensions where the model's prediction is inherently unreliable. |
| 4 | **SPECTER2 max context length (512 tokens) loses information** | High | Medium — methods/results sections are truncated | For the PoC, abstract+intro+conclusion in 512 tokens captures the most predictive content. Future work: use Longformer or hierarchical encoding. The structural features partially compensate by encoding paper-level statistics. |
| 5 | **Score distributions shift across years (distribution shift)** | Medium | Medium — model trained on 2024 data may miscalibrate on 2026 papers | Calibrate on the most recent year's data. Track calibration drift by periodically re-evaluating on newly available review data. Add year as an auxiliary feature so the model can learn temporal trends. |
| 6 | **Model learns venue/topic biases instead of quality signals** | High | High — Goodharting on superficial features | Monitor per-topic and per-subfield performance. Check that the model doesn't simply learn "papers about LLMs score higher" (which would reflect ICLR topic trends, not quality). Include adversarial tests: high-quality papers in unpopular subfields should still score well. |
| 7 | **GPU unavailable in CI or on user's machine** | Medium | Low — blocks training and slows inference | Support CPU-only mode via `configs/small.yaml` (smaller batch, no mixed precision). Pre-train a model and distribute the checkpoint so users don't need to train locally. Inference on CPU is ~2s/paper, which is acceptable. |
| 8 | **Concern generator (LLM) produces generic, unhelpful feedback** | Medium | Medium — undermines the actionable value of Layer 6 | Prompt engineering: require the LLM to cite specific sections and claims. Include a "specificity check" — if the generated concern could apply to any paper, regenerate with a stronger prompt. Include 2-3 few-shot examples of good vs. bad concerns in the prompt. |
| 9 | **Ethical risk: authors game the model by optimizing for predicted scores** | Low (PoC) | High (at scale) | The model should never be used as the sole decision signal. Frame it explicitly as "anticipated reviewer perception" not "paper quality." At scale, periodically retrain on recent data so gaming strategies become stale. Disclose the model's existence and limitations. |
| 10 | **Re2/OpenReview data includes papers from the pipeline's own test set** | Low | Medium — contaminates evaluation of the integrated pipeline | When running `papercheck` on a specific paper, check if that paper's OpenReview ID exists in the reward model's training set. If so, flag the Layer 6 result with a contamination warning and optionally exclude it from the composite score. |

---

## 7. CLI Extensions

```bash
# Data collection
papercheck reward fetch --venue iclr --years 2024-2025
papercheck reward fetch --venue neurips --years 2023-2024
papercheck reward fetch --source re2 --output data/openreview  # fallback: load from Re2 HuggingFace dataset

# Data processing
papercheck reward process --data-dir data/openreview --output data/openreview/processed

# Training
papercheck reward train --config papercheck/reward_model/configs/default.yaml
papercheck reward train --config papercheck/reward_model/configs/small.yaml  # CPU-only, fast iteration

# Evaluation
papercheck reward eval --checkpoint models/reward_model/checkpoint_best.pt --test-set data/openreview/processed/test.jsonl

# Full pipeline including Layer 6
papercheck run 2301.00001 --layers 1,2,3,4,5,6
papercheck run paper.pdf --layers 6            # Layer 6 only — quick "review prediction"
```

---

## 8. Example Layer 6 Report Output

```markdown
## Layer 6: Peer-Review Reward Model (0.62)

### Predicted Review Scores

| Dimension     | Score | Percentile | Signal |
|---------------|-------|------------|--------|
| Overall       | 5.8   | 58th       | ✅ PASS |
| Soundness     | 6.2   | 65th       | ✅ PASS |
| Presentation  | 4.1   | 28th       | ⚠️ WARN |
| Contribution  | 5.5   | 52nd       | ✅ PASS |
| Accept Prob.  | 0.54  | —          | ✅ PASS |

*Scores mapped to ICLR 2024 scale (1-10). Percentiles relative to ICLR 2024-2025 submissions.*

### Anticipated Reviewer Concerns

- ⚠️ **WARNING** [Presentation — 28th percentile]: The experimental setup in §4.1 describes the baseline comparison but does not specify hyperparameter selection criteria or tuning budget. Reviewers at ICLR frequently flag insufficient experimental detail. *Suggestion: Add a hyperparameter appendix or table listing all tuning decisions and their justification.*

- ⚠️ **WARNING** [Presentation — 28th percentile]: Figures 3 and 4 present results without confidence intervals or error bars across runs. The absence of variance reporting is a common reviewer criticism for empirical ML papers. *Suggestion: Report mean ± std over at least 3 random seeds for all main results.*
```

---

## 9. Future Work (Post-PoC)

1. **Cross-venue generalization**: Train on ICLR + NeurIPS + ACL + ICML jointly. Investigate whether a single model generalizes across venues or venue-specific models perform better.
2. **Full-text encoding**: Replace 512-token truncation with a hierarchical encoder (section-level SPECTER2 → paper-level attention) or a long-context model (Longformer, LED).
3. **Review text generation**: Extend the reward model to generate full synthetic reviews (bridging to REMOR-style approaches). The reward model becomes the critic in an actor-critic framework.
4. **Temporal dynamics**: Model how review standards evolve over time. A paper that would have scored 7/10 at ICLR 2020 might score 5/10 at ICLR 2025 as the field's bar rises.
5. **Subfield-aware calibration**: Calibrate separately per subfield (NLP, CV, RL, theory) since score distributions and reviewer expectations vary significantly.
6. **Multi-modal input**: Incorporate figure quality and table structure as additional features (requires vision encoder).
7. **Rebuttal simulation**: Given predicted concerns, generate a mock rebuttal and re-score — simulating the full review cycle.
8. **Active learning for the pipeline**: Use Layer 6 predictions to prioritize which papers to run through the expensive Layers 3-5, creating an efficient triage system.
9. **Feedback loop**: When users run the pipeline on their own papers and later submit to a venue, collect the actual review scores (with consent) and use them to continuously improve the model.