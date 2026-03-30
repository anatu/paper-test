"""Verification layers."""

from papercheck.layers.layer1_formal import FormalConsistencyLayer
from papercheck.layers.layer2_citations import CitationVerificationLayer
from papercheck.layers.layer3_corpus import CrossPaperConsistencyLayer
from papercheck.layers.layer4_reproducibility import ReproducibilityLayer
from papercheck.layers.layer5_logic import LogicalStructureLayer

ALL_LAYERS = [
    FormalConsistencyLayer(),
    CitationVerificationLayer(),
    CrossPaperConsistencyLayer(),
    ReproducibilityLayer(),
    LogicalStructureLayer(),
]
