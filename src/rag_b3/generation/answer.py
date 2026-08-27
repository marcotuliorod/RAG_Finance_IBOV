"""Loop de tool-use: o Claude decide quais ferramentas chamar (nunca calcula
ou busca "de cabeça"), o app executa contra o Postgres real e devolve o
resultado; repete até o modelo produzir uma resposta final em texto."""

import json
import logging
import time
from dataclasses import dataclass, field

import anthropic
from psycopg import Connection

from rag_b3.generation.client import get_anthropic_client, get_model
from rag_b3.generation.prompt import SYSTEM_PROMPT
from rag_b3.generation.tools import TOOL_SPECS, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


@dataclass
class AnswerResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    # Métricas de engenharia (Fase 3/10 do roadmap de evaluation/observability):
    # tokens brutos reportados pela API por chamada — não estimados — e
    # latência de parede do answer_question inteiro (todas as rodadas de
    # tool-use). model_id é o que a API realmente executou (response.model),
    # não o que foi pedido, para detectar silenciosamente um fallback/roteamento.
    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    latency_seconds: float = 0.0
    model_id: str = ""


class GenerationLoopExceededError(Exception):
    """O modelo não chegou a uma resposta final dentro de MAX_TOOL_ITERATIONS
    rodadas de tool-use — sinal de loop ou ferramenta insuficiente, nunca
    deve virar resposta especulativa para o usuário."""


def answer_question(
    conn: Connection,
    query: str,
    client: anthropic.Anthropic | None = None,
    model: str | None = None,
) -> AnswerResult:
    client = client or get_anthropic_client()
    model = model or get_model()

    messages: list[dict] = [{"role": "user", "content": query}]
    tool_calls_log: list[dict] = []
    input_tokens = 0
    output_tokens = 0
    api_calls = 0
    model_id = ""
    started_at = time.monotonic()

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_SPECS,
            messages=messages,
        )
        api_calls += 1
        # response.usage/model podem faltar em mocks de teste que não os
        # simulam; nunca deve derrubar a resposta real ao usuário por causa
        # de uma métrica de observabilidade.
        usage = getattr(response, "usage", None)
        input_tokens += getattr(usage, "input_tokens", 0) or 0
        output_tokens += getattr(usage, "output_tokens", 0) or 0
        model_id = getattr(response, "model", "") or model_id

        if response.stop_reason != "tool_use":
            text = "".join(block.text for block in response.content if block.type == "text")
            return AnswerResult(
                text=text,
                tool_calls=tool_calls_log,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_calls=api_calls,
                latency_seconds=time.monotonic() - started_at,
                model_id=model_id,
            )

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            logger.debug("tool_use round=%d name=%s", api_calls, block.name)
            result = execute_tool(conn, block.name, block.input)
            if isinstance(result, dict) and "error" in result:
                # Não é necessariamente um bug — pode ser o comportamento
                # correto (RF-07: dado insuficiente). Fica em WARNING, não
                # ERROR, porque é esperado que aconteça sob uso normal
                # (ex.: pergunta fora do período coberto pela série).
                logger.warning("tool_error name=%s error=%s", block.name, result["error"])
            tool_calls_log.append({"name": block.name, "input": block.input, "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    logger.warning(
        "generation_loop_exceeded max_iterations=%d tool_calls=%d",
        MAX_TOOL_ITERATIONS,
        len(tool_calls_log),
    )
    raise GenerationLoopExceededError(
        f"Excedeu {MAX_TOOL_ITERATIONS} rodadas de tool-use sem resposta final"
    )
