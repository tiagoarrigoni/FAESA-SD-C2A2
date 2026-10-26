"""
Servico 2 - RECUPERACAO: dada uma pergunta, acha os trechos mais relevantes.

TAREFA 2: implementar a busca por similaridade.

Rodar: uvicorn servicos.recuperacao.app:app --port 8002
"""
import os

import requests  # Mantem compatibilidade com os mocks dos testes de recuperacao.
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from servicos.comum.embeddings import Vetorizador, similaridade
from servicos.comum.http_resiliente import ClienteHTTPResiliente, ServicoIndisponivel

app = FastAPI(title="Recuperacao - C2.A2")
URL_INGESTAO = os.getenv("URL_INGESTAO", "http://localhost:8001")
cliente_ingestao = ClienteHTTPResiliente("ingestao")


class Consulta(BaseModel):
    pergunta: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1)


@app.post("/buscar")
def buscar(consulta: Consulta):
    """Deve devolver os top_k trechos mais parecidos com a pergunta."""
    try:
        dados = cliente_ingestao.solicitar_json(
            "GET", f"{URL_INGESTAO}/indice", campo_lista="itens"
        )
    except ServicoIndisponivel as erro:
        raise HTTPException(503, str(erro)) from erro
    itens = dados["itens"]

    
    # Se nao houver documentos, retorna uma lista vazia
    if not itens:
        return {
            "pergunta": consulta.pergunta,
            "resultados": []
        }

    # Extrai os textos dos documentos indexados
    textos = [item["texto"] for item in itens]

    # Cria e ajusta o vetorizador com os textos
    vetorizador = Vetorizador()
    vetorizador.ajustar(textos)

    # Transforma a pergunta em um vetor numerico
    vetor_pergunta = vetorizador.vetorizar(
        consulta.pergunta
    )

    # Calcula a similaridade de cada documento
    resultados = []

    for item in itens:
        vetor_documento = vetorizador.vetorizar(
            item["texto"]
        )

        score = similaridade(
            vetor_pergunta,
            vetor_documento
        )

        resultados.append({
            "texto": item["texto"],
            "origem": item["origem"],
            "score": score
        })

    # Ordena do mais relevante para o menos relevante
    resultados.sort(
        key=lambda resultado: resultado["score"],
        reverse=True
    )

    # Retorna somente os top_k documentos
    return {
        "pergunta": consulta.pergunta,
        "resultados": resultados[:consulta.top_k]
    }


@app.get("/saude")
def saude():
    return {"status": "ok"}
