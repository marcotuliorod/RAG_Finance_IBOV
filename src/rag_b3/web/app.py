"""Interface web local para conversar com a camada de geração
(`rag_b3.generation.answer.answer_question`) sem precisar escrever um
script Python. Uso pessoal, sem autenticação — o entrypoint
(`scripts/run_chat_web.py`) faz bind só em localhost por padrão."""

from collections.abc import Iterator
from contextlib import asynccontextmanager

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from psycopg import Connection
from pydantic import BaseModel

from rag_b3.common.db import get_connection
from rag_b3.config.settings import get_settings
from rag_b3.generation.answer import GenerationLoopExceededError, answer_question
from rag_b3.generation.client import get_anthropic_client
from rag_b3.web.page import CHAT_PAGE_HTML


class AskRequest(BaseModel):
    query: str


class ToolCallOut(BaseModel):
    name: str
    input: dict
    result: dict | list


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallOut]


def _get_conn() -> Iterator[Connection]:
    settings = get_settings()
    with get_connection(settings.supabase_db_url) as conn:
        yield conn


def _get_client(request: Request) -> anthropic.Anthropic:
    return request.app.state.anthropic_client


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.anthropic_client = get_anthropic_client()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Ibovespa — Chat", lifespan=_lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return CHAT_PAGE_HTML

    @app.post("/api/ask", response_model=AskResponse)
    def ask(
        payload: AskRequest,
        conn: Connection = Depends(_get_conn),
        client: anthropic.Anthropic = Depends(_get_client),
    ) -> AskResponse:
        try:
            result = answer_question(conn, payload.query, client=client)
        except GenerationLoopExceededError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return AskResponse(
            answer=result.text,
            tool_calls=[
                ToolCallOut(name=tc["name"], input=tc["input"], result=tc["result"])
                for tc in result.tool_calls
            ],
        )

    return app


app = create_app()
