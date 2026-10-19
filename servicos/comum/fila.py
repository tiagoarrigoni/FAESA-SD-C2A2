"""
Fila de indexacao (Redis) - mensageria do fluxo (TAREFA 4).

Quem chama POST /indexar nao espera a vetorizacao: a API so enfileira e
devolve um id. O worker de ingestao consome a fila, vetoriza e grava o
indice. Conceito da Aula 8. Adaptado da fila do trabalho C1.A2.

Chaves usadas (ver docs/CONTRATOS.md):
  ingestao:tarefas        -> tarefas pendentes
  ingestao:descarte       -> dead-letter (falhou 3x)
  ingestao:status:<id>    -> status de cada tarefa
  ingestao:trava-indice   -> lock para dois workers nao gravarem juntos
"""
import json
import os
import uuid

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
FILA_TAREFAS = "ingestao:tarefas"
FILA_DESCARTE = "ingestao:descarte"
PREFIXO_STATUS = "ingestao:status:"
CHAVE_TRAVA = "ingestao:trava-indice"
VALIDADE_STATUS_S = 24 * 60 * 60

_cliente = None


def cliente():
    global _cliente
    if _cliente is None:
        _cliente = redis.from_url(REDIS_URL, decode_responses=True,
                                  socket_connect_timeout=3)
    return _cliente


def enfileirar(documentos: list) -> str:
    """Coloca os documentos na fila e devolve o id para consulta posterior."""
    tarefa_id = str(uuid.uuid4())
    guardar_status(tarefa_id, {"status": "na_fila"})
    cliente().rpush(FILA_TAREFAS,
                    json.dumps({"id": tarefa_id, "documentos": documentos}))
    return tarefa_id


def proxima_tarefa(timeout: int = 5):
    """Bloqueia ate chegar tarefa (ou timeout). Usado pelo worker."""
    item = cliente().blpop(FILA_TAREFAS, timeout=timeout)
    if item is None:
        return None
    return json.loads(item[1])


def guardar_status(tarefa_id: str, status: dict) -> None:
    cliente().set(PREFIXO_STATUS + tarefa_id, json.dumps(status),
                  ex=VALIDADE_STATUS_S)


def buscar_status(tarefa_id: str):
    bruto = cliente().get(PREFIXO_STATUS + tarefa_id)
    return json.loads(bruto) if bruto else None


def enviar_para_descarte(tarefa: dict, erro: str) -> None:
    """Move uma tarefa que falhou 3x para a fila de dead-letter."""
    cliente().rpush(FILA_DESCARTE, json.dumps({**tarefa, "erro": erro}))


def listar_descarte() -> list:
    """Lista as tarefas na dead-letter, sem remove-las. Uso de depuracao."""
    return [json.loads(item) for item in cliente().lrange(FILA_DESCARTE, 0, -1)]


def trava_indice(timeout_s: int = 30):
    """Lock distribuido: com 2+ workers, so um grava o indice por vez."""
    return cliente().lock(CHAVE_TRAVA, timeout=timeout_s, blocking_timeout=timeout_s)


def disponivel() -> bool:
    try:
        return bool(cliente().ping())
    except redis.RedisError:
        return False
