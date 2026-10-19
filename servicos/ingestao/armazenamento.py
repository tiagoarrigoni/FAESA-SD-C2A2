"""
Armazenamento do indice em disco (TAREFA 1).

Versao minima em arquivo JSON, para o worker e a API compartilharem o
mesmo indice (sao processos separados). A escrita e atomica: grava num
arquivo temporario e troca de uma vez, entao quem le nunca pega o
arquivo pela metade.

Pontos para evoluir (TAREFA 1): ignorar documentos repetidos, rota para
limpar o indice, ou trocar o JSON por um banco vetorial (ex.: ChromaDB)
mantendo as funcoes carregar() e salvar().
"""
import json
import os

CAMINHO_INDICE = os.getenv(
    "INDICE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "dados", "indice.json"),
)


def carregar() -> list:
    """Devolve a lista de itens {texto, origem, vetor}, ou [] se nao houver indice."""
    if not os.path.exists(CAMINHO_INDICE):
        return []
    with open(CAMINHO_INDICE, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar(itens: list) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(CAMINHO_INDICE)), exist_ok=True)
    temporario = CAMINHO_INDICE + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(itens, arquivo, ensure_ascii=False)
    os.replace(temporario, CAMINHO_INDICE)
