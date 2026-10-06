"""合成设计说明语料（自制带真值，用于解析与核查评测）。"""

from .generator import (DEFAULT_SEED, build_document, compare_corpus, corpus_files,
                        corpus_payloads, generate_corpus)
from .rng import SplitMix64

__all__ = ["DEFAULT_SEED", "SplitMix64", "build_document", "compare_corpus",
           "corpus_files", "corpus_payloads", "generate_corpus"]
