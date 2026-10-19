"""
Servico 1 - INGESTAO: recebe documentos, gera embeddings e armazena.

POST /indexar NAO vetoriza na hora: so coloca os documentos na fila Redis
e devolve 202 com um id (TAREFA 4 - mensageria). Quem vetoriza e grava o
indice e o worker (servicos/ingestao/worker.py). O indice fica em disco
(servicos/ingestao/armazenamento.py), compartilhado entre API e worker.

Rodar: uvicorn servicos.ingestao.app:app --port 8001
       python -m servicos.ingestao.worker
"""
import time

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from servicos.comum import fila
from servicos.comum.logging_utils import configurar_log
from servicos.ingestao import armazenamento

app = FastAPI(title="Ingestao - C2.A2")
log = configurar_log("ingestao")


class Documento(BaseModel):
    texto: str
    origem: str = "desconhecida"


@app.post("/indexar", status_code=202)
def indexar(docs: list[Documento]):
    """Enfileira os documentos e devolve o id para acompanhar em /indexacao/{id}."""
    if not docs or any(not d.texto.strip() for d in docs):
        raise HTTPException(400, "envie ao menos um documento, sem texto vazio")

    inicio = time.time()
    try:
        tarefa_id = fila.enfileirar([d.model_dump() for d in docs])
    except redis.RedisError as erro:
        log.error(f"fila indisponivel ao indexar: {erro}")
        raise HTTPException(503, "fila indisponivel, tente novamente em instantes")

    log.info(f"POST /indexar | tarefa={tarefa_id} | documentos={len(docs)} "
             f"| tempo_ms={round((time.time() - inicio) * 1000, 2)}")
    return {"id": tarefa_id, "status": "na_fila", "documentos": len(docs)}


@app.get("/indexacao/{tarefa_id}")
def indexacao(tarefa_id: str):
    try:
        status = fila.buscar_status(tarefa_id)
    except redis.RedisError:
        raise HTTPException(503, "fila indisponivel, tente novamente em instantes")
    if status is None:
        raise HTTPException(404, "tarefa nao encontrada")
    return status


@app.get("/indice")
def indice():
    """Consumido pelo servico de recuperacao."""
    itens = armazenamento.carregar()
    return {"total": len(itens),
            "itens": [{"texto": i["texto"], "origem": i["origem"],
                       "vetor": i["vetor"]} for i in itens]}


@app.get("/saude")
def saude():
    return {"status": "ok", "documentos": len(armazenamento.carregar()),
            "fila": "ok" if fila.disponivel() else "indisponivel"}
