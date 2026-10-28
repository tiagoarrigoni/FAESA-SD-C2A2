import contextlib
import os
import tempfile
import unittest
from unittest.mock import patch

from servicos.ingestao import armazenamento, worker


class TestWorkerIngestao(unittest.TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)
        caminho = os.path.join(self.diretorio.name, "indice.json")
        self.enterContext(patch.object(armazenamento, "CAMINHO_INDICE", caminho))
        # Sem Redis: o lock vira um contexto vazio.
        self.enterContext(patch.object(worker.fila, "trava_indice", contextlib.nullcontext))

    def test_acrescenta_documentos_e_vetoriza_todos(self):
        worker.indexar([{"texto": "teorema CAP", "origem": "cap.txt"}])
        total = worker.indexar([{"texto": "consenso Raft", "origem": "raft.txt"}])
        itens = armazenamento.carregar()
        self.assertEqual(total, 2)
        self.assertEqual([i["origem"] for i in itens], ["cap.txt", "raft.txt"])
        self.assertTrue(all(len(i["vetor"]) == len(itens[0]["vetor"]) for i in itens))

    def test_reindexar_mesmo_documento_nao_duplica(self):
        documento = {"texto": "teorema CAP", "origem": "cap.txt"}
        worker.indexar([documento])
        # Simula a retentativa de uma tarefa cujo indice ja foi gravado.
        total = worker.indexar([documento, documento])
        self.assertEqual(total, 1)

    def test_mesmo_texto_com_origem_diferente_e_mantido(self):
        worker.indexar([{"texto": "teorema CAP", "origem": "aula10"}])
        total = worker.indexar([{"texto": "teorema CAP", "origem": "aula11"}])
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()
