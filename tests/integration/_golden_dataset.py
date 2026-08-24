"""Loader compartilhado do golden dataset — usado tanto por
test_golden_dataset.py (resolvers SQL puros, sem LLM) quanto por
test_golden_dataset_generation.py (geração real via LLM + LLM-judge)."""

import json
from pathlib import Path

GOLDEN_PATH = Path(__file__).parent.parent.parent / "data" / "datasets" / "eval" / "golden_v1.json"


def load_cases() -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return data["cases"]
