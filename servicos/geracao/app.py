"""
Servico 3 - GERACAO: monta o prompt com o contexto e chama o LLM.

TAREFA 3: resiliencia do LLM com circuit breaker,
retentativas, timeout e fontes.

Rodar: uvicorn servicos.geracao.app:app --port 8003
"""

import logging
import os
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto
from servicos.comum.llm import gerar
from servicos.comum.http_resiliente import ClienteHTTPResiliente, ServicoIndisponivel


app = FastAPI(title="Geracao - C2.A2")

URL_RECUPERACAO = os.getenv(
    "URL_RECUPERACAO",
    "http://localhost:8002",
)

disjuntor = CircuitBreaker(
    limite_falhas=3,
    espera_segundos=20,
)

logger = logging.getLogger(__name__)

TENTATIVAS_LLM = 3
BACKOFF_INICIAL = 0.5

# Circuito REST independente do LLM; aguarda as tentativas da ingestao.
cliente_recuperacao = ClienteHTTPResiliente("recuperacao", timeout=(1, 12))


class Pergunta(BaseModel):
    pergunta: str


def gerar_com_retentativas(pergunta: str, contexto: list) -> str:
    """Tenta gerar a resposta novamente quando o LLM falha."""

    ultimo_erro = None

    for tentativa in range(1, TENTATIVAS_LLM + 1):
        try:
            return gerar(pergunta, contexto)

        except Exception as erro:
            ultimo_erro = erro

            logger.warning(
                "Falha no LLM: tentativa %s de %s.",
                tentativa,
                TENTATIVAS_LLM,
            )

            if tentativa < TENTATIVAS_LLM:
                espera = BACKOFF_INICIAL * (2 ** (tentativa - 1))
                time.sleep(espera)

    raise RuntimeError(
        "O LLM falhou após todas as tentativas."
    ) from ultimo_erro


@app.post("/perguntar")
def perguntar(p: Pergunta):
    try:
        dados = cliente_recuperacao.solicitar_json(
            "POST", f"{URL_RECUPERACAO}/buscar", campo_lista="resultados",
            json={"pergunta": p.pergunta, "top_k": 3},
        )
    except ServicoIndisponivel as erro:
        raise HTTPException(503, str(erro)) from erro

    resultados = dados["resultados"]

    contexto = [
        item["texto"]
        for item in resultados
        if item.get("texto")
    ]

    # Guarda as origens para devolver as fontes ao usuário.
    fontes = list(dict.fromkeys(
        item["origem"]
        for item in resultados
        if item.get("origem")
    ))

    try:
        # O disjuntor envolve todas as tentativas como uma operação.
        resposta = disjuntor.chamar(
            gerar_com_retentativas,
            p.pergunta,
            contexto,
        )

    except CircuitoAberto as erro:
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM temporariamente indisponível: "
                "o disjuntor está aberto. Tente novamente mais tarde."
            ),
        ) from erro

    except Exception as erro:
        logger.exception("Falha ao gerar resposta com o LLM.")

        # Se esta falha abriu o disjuntor, devolve 503.
        if disjuntor.estado == "aberto":
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM temporariamente indisponível: "
                    "o disjuntor está aberto. Tente novamente mais tarde."
                ),
            ) from erro

        # Com o circuito ainda fechado, preserva as fontes
        # e informa que não foi possível gerar uma resposta.
        return {
            "pergunta": p.pergunta,
            "resposta": (
                "Não foi possível gerar uma resposta neste momento. "
                "Consulte as fontes recuperadas e tente novamente."
            ),
            "fontes": fontes,
            "contexto": contexto,
            "degradado": True,
        }

    return {
        "pergunta": p.pergunta,
        "resposta": resposta,
        "fontes": fontes,
        "contexto": contexto,
        "degradado": False,
    }


@app.get("/saude")
def saude():
    return {
        "status": "ok",
        "disjuntor": disjuntor.estado,
    }
