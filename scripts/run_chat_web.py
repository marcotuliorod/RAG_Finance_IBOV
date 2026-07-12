#!/usr/bin/env python3
"""Sobe a interface web de consulta (chat) sobre o RAG Ibovespa.

Bind só em 127.0.0.1 por padrão — não há autenticação, então não deve ficar
exposto na rede sem querer. Para acessar de outro dispositivo na rede local
(por sua conta e risco), rode com HOST=0.0.0.0."""

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("rag_b3.web.app:app", host=host, port=port)
