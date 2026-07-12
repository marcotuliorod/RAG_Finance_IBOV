"""Loop de tool-use: o Claude decide quais ferramentas chamar (nunca calcula
ou busca "de cabeça"), o app executa contra o Postgres real e devolve o
resultado; repete até o modelo produzir uma resposta final em texto."""

import json
from dataclasses import dataclass, field

import anthropic
from psycopg import Connection

from rag_b3.generation.client import get_anthropic_client, get_model
from rag_b3.generation.prompt import SYSTEM_PROMPT
from rag_b3.generation.tools import TOOL_SPECS, execute_tool

MAX_TOOL_ITERATIONS = 5


@dataclass
class AnswerResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)


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

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_SPECS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text = "".join(block.text for block in response.content if block.type == "text")
            return AnswerResult(text=text, tool_calls=tool_calls_log)

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = execute_tool(conn, block.name, block.input)
            tool_calls_log.append({"name": block.name, "input": block.input, "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    raise GenerationLoopExceededError(
        f"Excedeu {MAX_TOOL_ITERATIONS} rodadas de tool-use sem resposta final"
    )
