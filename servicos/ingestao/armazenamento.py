"""
Armazenamento do indice em disco (TAREFA 1).

Os documentos sao armazenados em JSON para que a API e o worker
compartilhem o mesmo indice, mesmo sendo processos separados.

A escrita e atomica: os dados sao gravados em um arquivo temporario
e depois substituem o arquivo principal.
"""

import json
import os

CAMINHO_INDICE = os.getenv(
    "INDICE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "dados", "indice.json"),
)


def carregar() -> list:
    """Carrega o indice e valida sua estrutura basica."""
    if not os.path.exists(CAMINHO_INDICE):
        return []

    try:
        with open(CAMINHO_INDICE, encoding="utf-8") as arquivo:
            itens = json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ValueError(
            f"O arquivo do indice contem JSON invalido: {CAMINHO_INDICE}"
        ) from erro

    if not isinstance(itens, list):
        raise ValueError(
            f"O arquivo do indice deve conter uma lista de documentos: "
            f"{CAMINHO_INDICE}"
        )

    return itens


def salvar(itens: list) -> None:
    """Salva o indice em JSON, usando escrita atomica."""
    os.makedirs(os.path.dirname(os.path.abspath(CAMINHO_INDICE)), exist_ok=True)

    temporario = CAMINHO_INDICE + ".tmp"

    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(itens, arquivo, ensure_ascii=False)

    os.replace(temporario, CAMINHO_INDICE)
