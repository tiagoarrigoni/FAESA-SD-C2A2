"""
Worker de ingestao: consome a fila, vetoriza e grava o indice (TAREFA 4).

  - retentativa: ate 3 tentativas por tarefa
  - dead-letter: depois da 3a falha, a tarefa vai para "ingestao:descarte"
    e o status fica "falhou" (o cliente nunca fica esperando para sempre)
  - lock no Redis: com 2+ workers, so um grava o indice por vez

Como o vocabulario do TF-IDF depende de TODOS os documentos, a cada tarefa
o worker junta os documentos novos com os ja indexados e revetoriza tudo.

Rodar: python -m servicos.ingestao.worker
Suba mais de um worker e veja as tarefas se dividirem entre eles.
"""
import time

from servicos.comum import fila
from servicos.comum.embeddings import Vetorizador
from servicos.comum.logging_utils import configurar_log
from servicos.ingestao import armazenamento

MAX_TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS_S = 0.5

log = configurar_log("worker_ingestao")


def indexar(documentos: list) -> int:
    """Acrescenta os documentos ao indice e revetoriza tudo. Devolve o total."""
    with fila.trava_indice():
        itens = [{"texto": i["texto"], "origem": i["origem"]}
                 for i in armazenamento.carregar()]
        itens += [{"texto": d["texto"], "origem": d.get("origem", "desconhecida")}
                  for d in documentos]

        vetorizador = Vetorizador()
        vetorizador.ajustar([i["texto"] for i in itens])
        for item in itens:
            item["vetor"] = vetorizador.vetorizar(item["texto"])

        armazenamento.salvar(itens)
        return len(itens)


def processar_tarefa(tarefa: dict) -> int:
    """Indexa com retentativa. Levanta a ultima excecao se esgotar as tentativas."""
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            return indexar(tarefa["documentos"])
        except Exception as erro:  # noqa: BLE001
            ultimo_erro = erro
            log.warning(f"tarefa {tarefa['id']} falhou na tentativa "
                        f"{tentativa}/{MAX_TENTATIVAS}: {erro}")
            if tentativa < MAX_TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS_S * tentativa)
    raise ultimo_erro


def tratar(tarefa: dict) -> None:
    inicio = time.time()
    fila.guardar_status(tarefa["id"], {"status": "processando"})
    try:
        total = processar_tarefa(tarefa)
    except Exception as erro:  # noqa: BLE001
        fila.enviar_para_descarte(tarefa, str(erro))
        fila.guardar_status(tarefa["id"], {"status": "falhou", "erro": str(erro)})
        log.error(f"tarefa {tarefa['id']} enviada para dead-letter apos "
                  f"{MAX_TENTATIVAS} tentativas | erro={erro}")
        return
    tempo_ms = round((time.time() - inicio) * 1000, 2)
    fila.guardar_status(tarefa["id"], {"status": "pronto", "indexados": total,
                                       "tempo_ms": tempo_ms})
    log.info(f"tarefa {tarefa['id']} concluida | documentos={len(tarefa['documentos'])} "
             f"| total_indice={total} | tempo_ms={tempo_ms}")


def main():
    log.info("worker de ingestao pronto, aguardando tarefas (Ctrl+C para sair)")
    while True:
        try:
            tarefa = fila.proxima_tarefa(timeout=5)
        except Exception as erro:  # noqa: BLE001
            # Redis fora do ar: espera e tenta de novo em vez de derrubar o worker
            log.error(f"falha ao consultar a fila: {erro}")
            time.sleep(2)
            continue
        if tarefa is not None:
            tratar(tarefa)


if __name__ == "__main__":
    main()
