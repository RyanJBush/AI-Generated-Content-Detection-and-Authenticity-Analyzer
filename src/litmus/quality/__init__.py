"""Text quality observers (R1-C; SPEC §8.3, docs/plans/R1-C-PLAN.md).

Quality observations do not establish AI origin and never affect origin
results. This package must not import torch, transformers, or litmus.scorer.

R1-C1 provides the building blocks only: packaged lexicons and their
loader/validator (``lexicon``), the word index (``words``), and the lexicon
entry compiler (``matcher``). Observers are R1-C2.
"""
