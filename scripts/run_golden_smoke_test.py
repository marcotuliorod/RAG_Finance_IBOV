#!/usr/bin/env python3
"""Smoke test manual: roda os 15 casos do golden dataset através da camada
de geração real (Claude + tool-use) e imprime a resposta ao lado do
`expected_answer` de referência para inspeção humana — não é um assert
automático (texto livre), serve para revisar guardrails/citação antes de
uma avaliação RAGAS formal."""

import json
import logging
import sys
from pathlib import Path

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings
from rag_b3.generation.answer import GenerationLoopExceededError, answer_question

logger = logging.getLogger(__name__)

GOLDEN_PATH = Path(__file__).parent.parent / "data" / "datasets" / "eval" / "golden_v1.json"


def main() -> int:
    configure_logging()
    settings = get_settings()
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]

    failures = 0
    with get_connection(settings.supabase_db_url) as conn:
        for case in cases:
            print("=" * 100)
            print(f"[{case['id']}] {case['query']}")
            print(f"esperado : {case['expected_answer']}")
            try:
                result = answer_question(conn, case["query"])
            except GenerationLoopExceededError as exc:
                failures += 1
                print(f"FALHOU   : {exc}")
                continue
            tools_used = [c["name"] for c in result.tool_calls]
            print(f"obtido   : {result.text}")
            print(f"tools    : {tools_used or '(nenhuma)'}")

    print("=" * 100)
    print(f"{len(cases)} casos rodados, {failures} falharam por loop excedido")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
