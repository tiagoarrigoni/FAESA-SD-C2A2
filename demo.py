"""Demonstra o fluxo indexacao assincrona -> recuperacao -> geracao."""
import os
from pathlib import Path
import sys
import time

import requests

URL_INGESTAO = os.getenv("URL_INGESTAO", "http://localhost:8001").rstrip("/")
URL_GERACAO = os.getenv("URL_GERACAO", "http://localhost:8003").rstrip("/")
PASTA_DOCS = Path(__file__).resolve().parent / "documentos"
TIMEOUT_HTTP = (3, 5)
TIMEOUT_PERGUNTA = (3, 120)  # Inclui as retentativas REST e do LLM.


def avaliar_cobertura(resposta: str, trechos_recuperados: list[str]) -> float:
    palavras_resposta = set(resposta.lower().split())
    palavras_fontes = set(" ".join(trechos_recuperados).lower().split())
    if not palavras_resposta:
        return 0.0
    intersecao = palavras_resposta.intersection(palavras_fontes)
    return round((len(intersecao) / len(palavras_resposta)) * 100, 2)


def aguardar_indexacao(tarefa_id: str, limite_segundos: float = 60):
    prazo = time.monotonic() + limite_segundos
    while time.monotonic() < prazo:
        resposta = requests.get(f"{URL_INGESTAO}/indexacao/{tarefa_id}", timeout=TIMEOUT_HTTP)
        resposta.raise_for_status()
        status = resposta.json()["status"]
        if status == "pronto":
            return
        if status == "falhou":
            raise RuntimeError(f"indexacao da tarefa {tarefa_id} falhou")
        if status not in {"na_fila", "processando"}:
            raise ValueError(f"status de indexacao desconhecido: {status}")
        time.sleep(min(1, max(0, prazo - time.monotonic())))
    raise TimeoutError(f"indexacao da tarefa {tarefa_id} excedeu {limite_segundos}s")


def indexar_documentos() -> bool:
    print("=== Iniciando ingestao de documentos ===")
    arquivos = sorted(PASTA_DOCS.glob("*.txt"))
    if not arquivos:
        print(f"Nenhum documento .txt encontrado em {PASTA_DOCS}.")
        return False
    for arquivo in arquivos:
        try:
            payload = [{"texto": arquivo.read_text(encoding="utf-8"), "origem": arquivo.name}]
            resposta = requests.post(f"{URL_INGESTAO}/indexar", json=payload, timeout=TIMEOUT_HTTP)
            resposta.raise_for_status()
            if resposta.status_code != 202:
                raise ValueError(f"esperado HTTP 202, recebido {resposta.status_code}")
            tarefa_id = resposta.json()["id"]
            aguardar_indexacao(tarefa_id)
            print(f"Indexado {arquivo.name}: tarefa {tarefa_id} pronta.")
        except (OSError, requests.RequestException, ValueError, KeyError, RuntimeError, TimeoutError) as erro:
            print(f"Falha ao indexar {arquivo.name}: {erro}")
            return False
    return True


def fazer_perguntas() -> bool:
    print("\n=== Iniciando teste de perguntas ===")
    perguntas = [
        "O que diz o teorema CAP?",
        "Quais sao os desafios da consistencia eventual?",
        "Como funciona a replicacao em sistemas distribuidos?",
    ]
    sucesso = True
    for pergunta in perguntas:
        print(f"\nPergunta: {pergunta}")
        try:
            resposta = requests.post(f"{URL_GERACAO}/perguntar", json={"pergunta": pergunta},
                                     timeout=TIMEOUT_PERGUNTA)
            resposta.raise_for_status()
            dados = resposta.json()
            texto = dados["resposta"]
            cobertura = avaliar_cobertura(texto, dados.get("contexto", []))
            print(f"Resposta: {texto}")
            print(f"Cobertura lexical: {cobertura}% das palavras estao no contexto recuperado.")
            print(f"Fontes utilizadas: {dados.get('fontes', [])}")
            if dados.get("degradado"):
                print("LLM indisponivel: resposta de contingencia, consulte as fontes.")
        except (requests.RequestException, ValueError, KeyError) as erro:
            print(f"Falha na geracao: {erro}")
            sucesso = False
    return sucesso


def main() -> int:
    if not indexar_documentos():
        print("Demonstracao interrompida: a indexacao nao foi concluida.")
        return 1
    return 0 if fazer_perguntas() else 1


if __name__ == "__main__":
    sys.exit(main())
