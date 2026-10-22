"""
Servico 3 - GERACAO: monta o prompt com o contexto e chama o LLM.

TAREFA 3: proteger a chamada ao LLM com o circuit breaker.

Rodar: uvicorn servicos.geracao.app:app --port 8003
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto
from servicos.comum.llm import gerar
from servicos.comum.http_resiliente import ClienteHTTPResiliente, ServicoIndisponivel

app = FastAPI(title="Geracao - C2.A2")
URL_RECUPERACAO = os.getenv("URL_RECUPERACAO", "http://localhost:8002")

disjuntor = CircuitBreaker(limite_falhas=3, espera_segundos=20)
# A recuperacao pode aguardar as tres tentativas de acesso a ingestao.
cliente_recuperacao = ClienteHTTPResiliente("recuperacao", timeout=(1, 12))


class Pergunta(BaseModel):
    pergunta: str


@app.post("/perguntar")
def perguntar(p: Pergunta):
    try:
        dados = cliente_recuperacao.solicitar_json(
            "POST", f"{URL_RECUPERACAO}/buscar", campo_lista="resultados",
            json={"pergunta": p.pergunta, "top_k": 3},
        )
    except ServicoIndisponivel as erro:
        raise HTTPException(503, str(erro)) from erro
    contexto = [t["texto"] for t in dados["resultados"]]

    # TAREFA 3: envolva a chamada gerar(...) com disjuntor.chamar(...)
    # e trate CircuitoAberto devolvendo 503 com mensagem clara.
    resposta = gerar(p.pergunta, contexto)

    return {"pergunta": p.pergunta, "resposta": resposta, "contexto": contexto}


@app.get("/saude")
def saude():
    return {"status": "ok", "disjuntor": disjuntor.estado}
